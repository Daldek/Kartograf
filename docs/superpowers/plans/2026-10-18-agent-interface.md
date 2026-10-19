# Interfejs dla agentow AI: dokumenty JSON, kody bledow, katalog komend i serwer MCP - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-18

**Status:** WYKONANY 2026-10-18 na galezi `feat/agent-interface` (T0-T9; raport E2E:
`docs/research/2026-10-18-agent-interface-e2e/raport.md`; odstepstwa i pomiary: errata 1 ADR-046 i sesja
2026-10-18 w `docs/PROGRESS.md`; plan liczyl 16 komend w T4d, jest 15, razem 41 deklaracji; E2E poprawilo
liczby i przyklady planu T9: 30 parametrow `elevation download`, arkusz Krakowa `M-34-64-D-d-1-2`, status
ponownego przebiegu `local`).

**Goal:** To samo zadanie wykonane przez CLI z `--json`, przez biblioteke (`to_dict()`)
i przez serwer MCP daje ten sam dokument `kartograf-<rodzaj>/1`; blad ma
stabilny `code`, `exit_code` i `hint` (`kartograf-error/1`); katalog komend
(`get_catalog()` = `kartograf catalog --json` = narzedzie MCP `get_catalog`)
jest jedynym zrodlem prawdy o komendach i z niego powstaja parser CLI, opcje
`COMMANDS` projektu i schematy wejscia narzedzi MCP; `kartograf[mcp]`
wystawia 29 narzedzi; `py.typed`, `llms.txt`, `scripts/gate.sh`,
`python -m kartograf` i regula dla agentow z innych repozytoriow w `CLAUDE.md`.
Calosc w wydaniu 0.8.0 (zmiany lamiace dozwolone, jedno wydanie).

**Architecture:** Nowe moduly biblioteki: `kartograf/serialization.py` (mixin
`Document`, koder, rejestr `SCHEMAS`), `kartograf/error_report.py`
(`ErrorReport`, `error_report`, tabele kodow), `kartograf/source_info.py`,
`kartograf/cache_info.py`, `kartograf/store_documents.py`,
`kartograf/sheet_info.py` (nowe raporty z logika przeniesiona z CLI),
pakiet `kartograf/catalog/` (deklaracje komend, `get_catalog`, parser argparse
z deklaracji, `tools.py` narzedzi MCP), `kartograf/commands.py` (KB-2..KB-5),
`kartograf/mcp_server.py` (opcjonalny, extra `mcp`). Wyjatki dostaja `code`,
`exit_code`, `hint`, `option`/`allowed`. CLI tylko tlumaczy: parser z katalogu,
`--json` drukuje `to_json()`, `main()` zamienia wyjatki na `kartograf-error/1`
i kody wyjscia 0/1/2/130.

**Spec:** `docs/superpowers/specs/2026-10-18-agent-interface-design.md`
(zaakceptowany przez koordynatora 2026-10-18: D1-D21, O1-O9 rozstrzygniete w
sekcji 16; sekcja 16.1: uzgodnienia z przegladem API odczytu magazynu).
Dalej "spec N" = sekcja N tego dokumentu.

**Wersja docelowa:** 0.8.0 (bez wydania posredniego). **ADR:** ADR-046 (status
`Przyjeta`, tekst jest w `docs/DECISIONS.md`; T8 dopisuje errate z wynikami
E2E).

**Kod wyjsciowy:** `feat/agent-interface` (kod `8c65f4e` = merge poprawek
przegladu API odczytu magazynu; spec i plan jako commity `docs`). Stan
zmierzony 2026-10-18: 5339 testow offline zielonych w 123 s (Python 3.13.5,
pytest 9.0.2, ruff 0.15.0, mypy 2.3.0), `ruff check`, `ruff format --check` i
`mypy kartograf/ tests/` czyste. Przed startem kazdego toru:
`git log --oneline -3` i `git status` (czysty); zmiana symbolu z sekcji
"Fakty o obecnym kodzie" = zatrzymaj sie i opisz roznice koordynatorowi.

---

## Weryfikacja specu wzgledem kodu i pomiarow (2026-10-18)

1. **Liczby ze specu potwierdzone:** 36 komend-lisci CLI i 50 parserow (korzen +
   13 grup + 36 lisci), 14 plikow `kartograf/cli/groups/` (1925 linii),
   `COMMANDS` z 12 komendami danych (kolejnosc: `elevation`, `imagery`,
   `landcover`, `soil download`, `soil hsg`, `boundaries`, `cadastre`,
   `models3d`, `hydro`, `names`, `maps`, `geodesy`). Zrzut odniesienia
   (Dodatek A) dziala offline w ok. 1 s, jest deterministyczny i niezalezny od
   szerokosci terminala (`COLUMNS`), liczy 36 lisci i 33 przebiegi tekstowe.
2. **API SDK `mcp` 2.3.0 potwierdzone na zrodlach wheel:** `Server(name, *, version,
   title, description, instructions, ..., on_list_tools, on_call_tool)`,
   handlery `async (ctx, params)`; `ctx.session.report_progress(progress, total,
   message)` (`mcp/server/session.py`, no-op bez tokenu); `stdio_server()` jako
   asynchroniczny menedzer kontekstu, `Server.run(read, write,
   create_initialization_options())`; typy w `mcp_types` (`Tool`,
   `ToolAnnotations`, `CallToolResult(content, structured_content, is_error)`,
   `TextContent`); klient `Client(server, raise_exceptions=True)` laczy sie w
   pamieci, `call_tool(..., progress_callback=)`; wyjatek handlera = blad
   `-32603` bez tresci (`raise_exceptions=True`: ponowiony). `starlette` i
   `uvicorn` sa zaleznosciami twardymi.
3. **Instalacja `mcp>=2.3.0,<3` jest addytywna:** `pip install --dry-run` w
   `.venv` glownego checkoutu: 21 nowych pakietow (m.in. `anyio`, `httpx2`,
   `jsonschema`, `mcp`, `mcp-types`, `pydantic`, `starlette`, `uvicorn`), zero
   aktualizacji istniejacych (O7). `jsonschema` i `pydantic` nie sa dzis w
   `.venv`: testy `tools.py` uzywajace `jsonschema` maja `importorskip`.
4. **Spojnosc z poprawkami przegladu API odczytu magazynu (merge `8c65f4e`):**
   `Sidecar.unit` (plik krajowy z motywem = nazwa pliku slotu, np.
   `pl_miejscowosci`, przyjmowana przez `iter_store(units=...)`),
   `InvalidSidecarError` takze dla braku sidecara, `Sidecar.schema` zawsze
   `kartograf-meta/1`, `ValidationError` przy wywolaniu dla zarezerwowanych i
   zbyt dlugich jednostek, `OSError` dla nieistniejacego `output_dir`,
   niehashowalne `Sidecar` i `StoreEntry`. Spec poprawiony (D21, 5.4.10, 6.1-6.3,
   16.1): kod `io_error` dla `OSError`, `option` dla walidatorow magazynu,
   kontekst kodera `ctx.omit` (`Sidecar.raw`).
5. **Poprawki specu wykonane przy tym planie:** (a) `list_sources` i `list_layers`
   w `kartograf/source_info.py` (poza `catalog/`: tor A nie moze tworzyc plikow w
   pakiecie toru B); (b) `describe_sheet` i `find_sheets` w `kartograf/sheet_info.py`
   w zadaniu T4d: `SheetInfo.commands` wylicza sie z `ParamInfo.accepts`
   katalogu, wiec funkcja musi powstac po deklaracjach; (c) nowe pliki katalogu
   `kinds.py`, `formatting.py`, `hints.py` (wspolny kod T5 i T6 bez cyklu
   `catalog` <-> `commands`); (d) skladnik (b) hintu bledu (przyklad z katalogu)
   wpina T5, nie T2 (ten sam plik `error_report.py` nie jest edytowany przez dwa
   tory); (e) spec 9.2: `kartograf.mcp_server` importuje sie bez `mcp`,
   `create_server` rzuca `ImportError` z napisem, a `main()` go drukuje (stare
   sformulowanie "import rzuca ImportError" i "main() drukuje" bylo sprzeczne).
6. **Skala przepisywania testow (O2, kod wyjscia 2 dla bledow wejscia):**
   23 asercje `main([...]) == 1` i ok. 156 asercji `rc`/`code`/`exit_code`/`result == 1`
   w `tests/` (liczone wyrazeniem regularnym: czesc nie dotyczy kodow wyjscia;
   `test_cli.py` ok. 127); T5 klasyfikuje kazda czerwona: blad wejscia -> 2,
   awaria zrodla i `ok: false` -> 1.
7. **Schemat jako pole dataclass:** `UpdatePlan.schema` i
   `AvailabilityReport.schema` sa dzis polami (`kartograf/download/plan.py:80`,
   `availability.py:261`); `tests/test_plan.py:86` buduje
   `dataclasses.replace(plan, schema="kartograf-plan/2")` - po przejsciu na
   `ClassVar` ten test (i sprawdzenie schematu w `require_store`) przepisuje T1
   (nieznany schemat odrzuca `UpdatePlan.from_dict`).
8. **`BBox` to `NamedTuple`** (`kartograf/core/bbox.py:36`): koder nie importuje
   `core`, wiec `BBox` dostaje metode `__json__` (hak kodera, spec 5.1).

## Organizacja wykonania (tory i fale)

Wykonawcy: **koordynator** (tworzy worktree, merguje, uruchamia brame na wyniku
scalenia, rozstrzyga konflikty) i **implementatorzy** w osobnych worktree (maks.
2 naraz). Galaz integracyjna `feat/agent-interface` (worktree
`wt/feat/agent-interface`): merguje do niej tylko koordynator. Implementator
nie robi merge, push ani tagow; jedyny wyjatek: `git merge feat/agent-interface`
w swoim worktree na polecenie koordynatora (punkty S1 i S2).

```
fala 1  Tor A: T0.1 -> T1.1 -> T2.1 -> [K1] -> T0.2-4 -> T1.2-T1.5 -> T2.2-T2.7 -> T3 --> [S2] -+
        Tor B: T4a.1-2, T4b.1 -> [K1] -> T4a.3-4 -> T4b.2 -> T4c -> [S2] -> T4d ---------------+--> scalenie
fala 2  T5  (jeden wlasciciel, worktree integracyjny)
fala 3  T6 (MCP)  ||  T7 (llms.txt)           dwa worktree, rozlaczne pliki
fala 4  T8  (dokumentacja, jeden wlasciciel)
fala 5  T9  (brama pelna, smoke, wheel)
```

| Fala | Zadania | Implementator, galaz, worktree (siostrzany katalog) | Wejscie | Wyjscie |
|---|---|---|---|---|
| 1 | Tor A: T0, T1, T2, T3 | A, `feat/agent-interface-a`, `../agent-interface-a` | `feat/agent-interface` | pelna brama zielona, raport toru |
| 1 | Tor B: T4a-T4d | B, `feat/agent-interface-b`, `../agent-interface-b` | j.w. | pelna brama zielona, raport toru |
| 2 | T5 | jeden, `feat/agent-interface` (worktree integracyjny) | scalone A i B | brama zielona, zrzut przed/po bez roznic |
| 3 | T6 | `feat/agent-interface-mcp`, `../agent-interface-mcp` | po T5 | brama zielona (z `mcp` w `.venv`) |
| 3 | T7 | `feat/agent-interface-llms`, `../agent-interface-llms` | po T5 | brama zielona |
| 4 | T8 | jeden, `feat/agent-interface` | scalone T6 i T7 | dokumentacja, CHANGELOG, PROGRESS |
| 5 | T9 | jeden, `feat/agent-interface` | po T8 | brama pelna, smoke, raport koncowy |

Worktree tworzy koordynator z worktree integracyjnego:
`git worktree add ../agent-interface-a -b feat/agent-interface-a feat/agent-interface`
(analogicznie `-b`, `-mcp`, `-llms`). Srodowisko: wspolne `.venv` glownego checkoutu;
polecenia `python -m ...` z korzenia WLASNEGO worktree importuja kod z worktree.

### Fala 1: Tor A i Tor B (rownolegle)

**Pliki na wlasnosc.** Zbiory rozlaczne; potrzeba zmiany cudzego pliku =
zatrzymaj sie i zglos koordynatorowi (nie edytuj).

| Tor A (T0-T3) tworzy lub zmienia | Tor B (T4a-T4d) tworzy lub zmienia |
|---|---|
| `kartograf/py.typed`, `kartograf/__main__.py`, `scripts/gate.sh`, `pyproject.toml`, `MANIFEST.in` | `kartograf/catalog/**` (nowy pakiet: `__init__`, `spec`, `shared`, `kinds`, `model`, `build`, `cliparser`, `formatting`, `hints`, `commands/*`) |
| `kartograf/serialization.py`, `kartograf/error_report.py` (nowe) | `kartograf/sheet_info.py` (nowy, T4d) |
| `kartograf/exceptions.py`, `kartograf/transform/crs.py` (tylko klasy bledow), `kartograf/core/bbox.py` (`BBox.__json__`) | `tests/test_catalog.py`, `tests/test_catalog_parser.py`, `tests/test_catalog_declarations.py`, `tests/test_catalog_formatting.py`, `tests/test_sheet_info.py` (nowe) |
| raporty: `kartograf/download/{plan,availability,data,collections}.py`, `kartograf/landcover/manager.py`, `kartograf/hydrology/hsg.py`, `kartograf/project/model.py` | - |
| walidatory (`option`/`allowed`): `kartograf/download/{options,area,arguments}.py`, `kartograf/store.py`, `kartograf/project/operations.py` oraz moduly z lista w T2 Step 2 | - |
| nowe: `kartograf/source_info.py`, `kartograf/cache_info.py`, `kartograf/store_documents.py` | - |
| `kartograf/__init__.py` (jedyny wlasciciel w fali 1; eksporty B dopisuje T5) | - |
| `tests/test_serialization.py`, `test_json_contract.py`, `test_errors.py`, `test_source_info.py`, `test_cache_info.py`, `test_store_documents.py`, `test_main_module.py` (nowe); `tests/test_public_api.py`, `tests/conftest.py`, `tests/test_plan.py`, `tests/test_availability.py` (tylko tam, gdzie zmiana A tego wymaga) | - |

Zamrozone w fali 1 (nikt nie edytuje): `kartograf/cli/**` (T3 NIE zmienia CLI;
przelaczenie CLI na funkcje biblioteki robi T5), `kartograf/project/{commands,manifest}.py`,
`tests/test_cli*.py`, `tests/test_project_*.py`, `tests/parity.py`, `docs/**`,
`README.md`, `CLAUDE.md`. CHANGELOG i PROGRESS dopisuje T8 z komunikatow commitow
i raportow torow (commit opisuje zmiane lamiaca wprost: "BREAKING: ...").

**Kontrakt K1 (A -> B), zamrozony tekstem tego planu.** Tor A publikuje go jako
swoje DWA PIERWSZE commity po zrzucie (T0 Step 1): T1 Step 1 i T2 Step 1; zglasza
koordynatorowi hash. Koordynator merguje go do `feat/agent-interface`, B robi
`git merge feat/agent-interface` (bez konfliktow: rozlaczne pliki). Do K1 tor B
robi tylko to, co go nie wymaga: `spec.py`, `shared.py`, `kinds.py`,
`formatting.py`, deklaracje `commands/elevation.py` i `commands/imagery.py` (czyste
dane na typach z `spec.py`).

```python
# kartograf/serialization.py (T1 Step 1)
@dataclass
class EncodeContext:
    store: Path | None = None                       # katalog magazynu dla sciezek pinow projektu
    omit: frozenset[tuple[str, str]] = frozenset()  # pary (klasa, pole) pomijane w kodowaniu dataclass

class Document:                                     # mixin klas @dataclass(frozen=True)
    SCHEMA: ClassVar[str]                           # "kartograf-download/1"
    JSON_KEYS: ClassVar[tuple[str, ...] | None] = None
    JSON_FILL: ClassVar[Mapping[str, object]] = {}
    @property
    def schema(self) -> str: ...
    def prepare_context(self, ctx: EncodeContext) -> None: ...   # hak, domyslnie nic
    def to_dict(self) -> dict[str, object]: ...
    def to_json(self, *, indent: int | None = 2) -> str: ...

SCHEMAS: dict[str, tuple[type[Document], ...]]      # wypelnia __init_subclass__
def encode(value: object, ctx: EncodeContext | None = None) -> object

# kartograf/exceptions.py (T2 Step 1): nowe argumenty tylko nazwane i opcjonalne
class KartografError(Exception):
    code: ClassVar[str]; exit_code: ClassVar[int]
    DETAIL_FIELDS: ClassVar[tuple[str, ...]]; DEFAULT_HINT: ClassVar[str | None]
    hint: str | None
    def details(self) -> dict[str, object]: ...
class ValidationError(KartografError):              # exit_code 2
    option: str | None; options: tuple[str, ...] | None; allowed: tuple[str, ...] | None
    def __init__(self, message: str, *, option=None, options=None, allowed=None, hint=None): ...
class UsageError(ValidationError): ...              # code "usage_error"

# kartograf/error_report.py (T2 Step 1)
ERROR_CODES: tuple[ErrorCodeSpec, ...]   # tabela 6.2: code, exception, exit_code, meaning
EXIT_CODES: tuple[ExitCodeSpec, ...]     # tabela 6.5: code, name, meaning
@dataclass(frozen=True)
class ErrorReport(Document): code, message, hint, exception, exit_code, command, details
def error_report(exc: BaseException, *, command: str | None = None) -> ErrorReport: ...
```

**Punkty synchronizacji.**

- **S1 = K1** (patrz wyzej).
- **S2 = koniec Toru A** (T0-T3 zielone): koordynator merguje A do
  `feat/agent-interface`, B robi `git merge feat/agent-interface` i dopiero wtedy
  zaczyna T4d (funkcje z `kartograf.__all__`, `SCHEMAS` raportow, `ERROR_CODES`,
  `ValidationError.option` w walidatorach). Kolejnosc Toru B (T4a, T4b, T4c, potem
  T4d) ma ten punkt wypadac bez czekania; tor A raportuje ETA po K1.
- **Scalenie fali 1:** koordynator merguje B do `feat/agent-interface` (A juz
  jest), uruchamia pelna brame; konflikty: oczekiwany brak (rozlaczne pliki).

**Punkty integracji, ktore da sie sprawdzic dopiero po scaleniu** (wykonuje je
T5 Step 0 i dopisane tam testy): funkcje deklarowane w katalogu naleza do
`kartograf.__all__` (eksporty `get_catalog`, `data_commands`, `Catalog`,
`CommandInfo`, `ParamInfo` dopisuje T5); `Catalog.errors` i `exit_codes` =
`ERROR_CODES`, `EXIT_CODES`; `result_schema` w `SCHEMAS` (B moze to sprawdzic
w T4d po S2).

**Ryzyko konfliktow i mitygacja (fala 1).**

| Ryzyko | Skutek | Mitygacja |
|---|---|---|
| wspolny plik (`kartograf/__init__.py`, `tests/conftest.py`, `pyproject.toml`) edytowany przez oba tory | konflikt przy scaleniu | w fali 1 tylko A (`__init__`, `conftest`, `pyproject`); eksporty B dopisuje T5; B nie dotyka plikow spoza `kartograf/catalog/`, `kartograf/sheet_info.py` i swoich testow |
| B potrzebuje pomocnika w module A (np. listy wartosci w `download/options.py`) | pokusa edycji cudzego pliku | B liczy `allowed` z rejestru (`sources/variants.py`, `sources/registry.py`) i stalych `options.py`, ktorych A nie zmienia (K2 nizej); zmiana cudzego pliku = zgloszenie |
| A zmienia sygnature, ktorej uzywa B | B pada po merge | A zmienia tylko: typ zwracany `*_option_error` i `_*_error` w `download/options.py` (B ich nie importuje), argumenty `ValidationError(...)`, pola raportow (dodatki), `UpdatePlan.schema` (pole -> ClassVar); wszystko inne zamrozone |
| K1 spozniony | B stoi | B robi prace niezalezne od K1; A zaczyna od T1.1 i T2.1 |
| T3 spozniony wzgledem T4d | B stoi | B robi T4d ostatnie (po T4b i T4c); opcja koordynatora: przekazac czesc T4d (pliki rozlaczne: `catalog/commands/{project,misc}.py`, `catalog/hints.py`, `sheet_info.py`, testy) wykonawcy A po T3, po scaleniu B@T4a |
| rozjazd flag miedzy starym i nowym parserem | regresja CLI w T5 | w fali 1 stary parser zostaje nietkniety (`cli/**` zamrozone); test rownowaznosci stary <-> nowy (T4a, T4b-d) i zrzut przed/po (Dodatek A) |

**K2 (wyjscie fali 1 -> T5): nazwy, na ktorych opiera sie T5.**
Tor B: `kartograf.catalog.get_catalog(*, group=None, command=None, params=None)`,
`data_commands()`, typy dokumentu (`Catalog`, `GroupInfo`, `ProductInfo`,
`CommandInfo`, `ParamInfo`, `ConstraintInfo`, `ExampleInfo`, `ExitCodeInfo`,
`ErrorCodeInfo`, `SchemaInfo`), `kartograf.catalog.cliparser.build_parser(...)`,
`parse_command_line(...)`, `removed_command_error(...)`,
`kartograf.catalog.formatting.format_command_line(command, options, run=None)`,
`kartograf.catalog.hints.example_for(command, option)`,
`kartograf.catalog.kinds.parse_bbox_arg`, `parse_per_country`, `layer_codes`,
`kartograf.sheet_info.describe_sheet`, `find_sheets`. Tor A: `Document`, `encode`,
`SCHEMAS`, `error_report`, `ERROR_CODES`, `EXIT_CODES`, `list_sources`,
`list_layers`, `get_cache_info`, `clear_cache`, `describe_store`,
`list_store_entries`, `read_store_sidecar` (wszystkie w `kartograf.__all__`),
`UsageError`, `ValidationError.option`/`options`/`allowed`.

### Fale 2-5: jeden wlasciciel albo rozlaczne pary

| Fala | Pliki na wlasnosc | Punkty integracji | Ryzyko konfliktow |
|---|---|---|---|
| 2: T5 | `kartograf/cli/**`, `kartograf/commands.py` (nowy), `kartograf/project/{commands,operations,manifest}.py`, `kartograf/catalog/{kinds,cliparser}.py` (poprawki po scaleniu), `kartograf/error_report.py` (wpiecie `example_for`), `kartograf/__init__.py` (eksporty), `tests/**` wymagajace aktualizacji (12.10-12.11), `tests/test_cli_json.py`, `tests/test_commands_layer.py` | scalone A i B (Step 0); K2; zrzut przed/po | brak (jeden wlasciciel); ryzyko wielkosci: 11 commitow z zielona brama kazdy |
| 3: T6 | `kartograf/catalog/tools.py`, `kartograf/mcp_server.py`, `pyproject.toml` (`mcp`, `dev`, `kartograf-mcp`, override mypy), `tests/test_mcp_tools.py`, `tests/test_mcp_server.py` | K3: `get_catalog(params=True)`, `run_command`/`check_command`, `options_from_json` (kinds), `error_report`; instalacja `mcp` w `.venv` (O7) | rozlaczne z T7 (T7 nie dotyka `pyproject.toml`) |
| 3: T7 | `llms.txt`, `MANIFEST.in` (`include llms.txt`), `tests/test_llms_txt.py` | polecenia z `llms.txt` parsuja sie prawdziwym parserem (T5); tabela kodow bledow = `get_catalog().errors` | rozlaczne z T6; sekcja "Serwer MCP" w `llms.txt` zgodna ze specem 9.2 (flagi `--tools`, `--allow-dir`, `--cache-file`, `--no-cache`) - sprawdza koordynator po scaleniu |
| 4: T8 | `docs/**`, `README.md`, `CLAUDE.md`, `kartograf/__init__.py` (docstring modulu) | wszystkie fale scalone | brak |
| 5: T9 | brak zmian w kodzie (poprawki tylko jako osobne commity `fix:`); `docs/research/2026-10-xx-agent-interface-e2e/raport.md` | pelna brama, wheel, smoke live | brak |

**K3 (T5 -> T6, T7):** `kartograf.parse_command`, `validate_command`,
`format_command`, `run_command`, `check_command`, `CommandCall` (spec 8.7);
`kartograf.catalog.kinds`: `convert_arguments(kinds, data, *, base_dir=None)`
(wspolna konwersja JSON -> argumenty biblioteki, uzywana tez przez
`options_from_json`); `get_catalog(params=True)` (parametry, ograniczenia,
przyklady, `supports_check`); `create_parser()` jako fasada.

## Global Constraints

- Python: `.venv` glownego checkoutu (worktree nie ma wlasnego); skrot w tym
  planie `PY`. Polecenia uruchamiaj Z KORZENIA WLASNEGO worktree: `$PY -m pytest`,
  `$PY -m ruff`, `$PY -m mypy`; CLI `$PY -m kartograf.cli.commands ...` (po T0 tez
  `$PY -m kartograf ...`). Kontrola: `$PY -c "import kartograf; print(kartograf.__file__)"`
  musi wskazac sciezke w worktree, w ktorym pracujesz.
- TDD: kazdy krok "Test RED" to test zachowania; uruchom go i zobacz porazke z
  wlasciwego powodu (nowy modul: `ModuleNotFoundError` albo `ImportError`; zmiana
  istniejacego zachowania: konkretna asercja), dopiero potem implementacja.
  Bez testow okablowania, kopii stalych, tekstu zrodla i atrap-echa (STANDARDS 10).
- Testy offline (`tests/conftest.py::_block_network` jest autouse); `live` tylko w
  T9, dane do `<katalog-danych>` z jawnym `--output`, nigdy w repo ani w `/tmp`;
  sciezki katalogu danych nie zapisuj w repo. Pliki tymczasowe testow w `tmp_path`.
- Jezyk: identyfikatory i docstringi po angielsku; teksty dla czlowieka
  (`message`, `hint`, `Notice.text`, opisy katalogu i narzedzi) po polsku w ASCII
  (Z5, A9); dokumentacja po polsku; klucze, schematy, kody bledow, nazwy narzedzi
  i wartosci wyliczen po angielsku, `snake_case`. `docs/DECISIONS.md` ma CRLF.
- Bez wartosci domyslnych wplywajacych na dane (STANDARDS 11.2); nowe funkcje
  biblioteki maja argumenty tylko nazwane (`*`), z wyjatkiem argumentu
  identyfikujacego obiekt (`describe_store(output_dir)`, `read_store_sidecar(path)`).
- **Brama kroku** (przed kazdym commitem): `$PY -m ruff check .`,
  `$PY -m ruff format --check .`, `$PY -m mypy kartograf/ tests/`, `$PY -m pytest
  <testy dotkniete krokiem> -q`. **Brama zadania** (przed ostatnim commitem zadania
  i przed zgloszeniem toru): pelna - `$PY -m pytest tests/ -m "not live" -q` (ok. 2
  min) i trzy poprzednie; po T0 skrot `scripts/gate.sh`.
- Commity: Conventional Commits po polsku (`feat`, `fix`, `refactor`, `test`,
  `build`, `docs`; zmiana lamiaca: `!` i linia "BREAKING: ..." w tresci), autor
  `Daldek <git@debever.pl>`, bez `Co-Authored-By`; commit przez straznik wzorcow:
  `! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git -c user.name=Daldek -c user.email=git@debever.pl commit ...`
  (brak pliku wzorcow = zatrzymaj sie i zapytaj). Jedna zmiana logiczna = jeden commit,
  kazdy z zielona brama kroku.
- Testy, ktore przypinaja usuwane zachowanie, usuwaj albo przepisuj na nowa intencje
  (STANDARDS 10): bez aliasow, wrapperow i podwojnych sciezek po przelaczeniu (T5).
- Zakaz skrotow: bez stubow, atrap, `TODO`, pustych implementacji; pelne rozwiazanie
  albo jawnie nazwany bloker w raporcie.
- Raport toru/zadania do koordynatora (krotki): co zrobione, commity (hash +
  tytul), wynik bramy (liczby z komend), odchylenia od planu, otwarte kwestie.
  Raport zastepuje wpis `docs/PROGRESS.md` (wpis robi T8).

## Decyzje implementacyjne (bez nowych decyzji produktowych)

1. **Koder (T1 Step 1).** `encode(value, ctx)` przetwarza rekurencyjnie, w tej
   kolejnosci: `None`/`bool`/`int`/`str` bez zmian; `float` skonczony (`NaN` i
   `Infinity` = `ValueError`); `Enum` -> `value`; typ z `__json__(self, ctx)` -> jego
   wynik zakodowany dalej; `Path` -> `Path.absolute().as_posix()` (bez `resolve()`);
   `Decimal` -> napis; `datetime` -> ISO 8601 UTC `+00:00` do sekund; dataclass ->
   obiekt w kolejnosci pol (pola z `metadata={"json": False}` i pary z `ctx.omit`
   pominiete); `Mapping` -> obiekt (klucze musza byc `str`); `tuple`/`list` ->
   tablica; `frozenset`/`set` -> tablica posortowana; inny typ = `TypeError`.
   `Document.to_dict()` tworzy `EncodeContext`, wola `prepare_context(ctx)` (hak
   dokumentow: `Project*` ustawiaja `ctx.store`, `StoreEntries` ustawia
   `ctx.omit`), zwraca `{"schema": SCHEMA, **klucze}`; wartosc klucza: pole
   dataclass, a gdy brak - wlasciwosc o tej nazwie (np. `UpdatePlan.ok`), a gdy
   brak - `JSON_FILL[klucz]`, inaczej `ValueError` (blad programu). Dokument
   zagniezdzony nie ma klucza `schema`. `Document.__init_subclass__` odrzuca
   (`ValueError` przy imporcie): nazwe schematu spoza
   `^kartograf-[a-z][a-z0-9-]*/[1-9][0-9]*$`, pole dataclass o nazwie `schema`
   (`__init_subclass__` dziala PRZED dekoratorem `@dataclass`, wiec nazwe pola czyta z
   `cls.__annotations__`; rejestracja w `SCHEMAS` dotyczy tej samej klasy, bo dekorator
   bez `slots` nie tworzy nowej). `BBox` (NamedTuple) dostaje `__json__` w
   `kartograf/core/bbox.py`: `{"bbox": [min_x, min_y, max_x, max_y], "crs": crs}`.
2. **Rodzina `kartograf-download/1` (T1 Step 3).** Stale rodziny w
   `kartograf/download/data.py`: `DOWNLOAD_SCHEMA`, `DOWNLOAD_KEYS` (`files`,
   `raw`, `inputs`, `failed`, `stale`, `superseded`, `summary`, `notices`, `ok`),
   `DOWNLOAD_FILL` (`[]`, a dla `summary` `None`); kazda z pieciu klas
   (`DataReport`, `CollectionReport`, `LandCoverReport`, `SoilReport`,
   `HsgReport`) deklaruje `SCHEMA = DOWNLOAD_SCHEMA`, `JSON_KEYS = DOWNLOAD_KEYS`,
   `JSON_FILL` z kluczami, ktorych nie ma. `HsgReport.summary: dict | None = None`
   (ostatnie pole z domyslna); `calculate_hsg(..., summary: bool = False)`:
   `True` = `dataclasses.replace(report, summary=hsg_statistics(<plik HSG>))` z
   pliku `report.files[0].file.path`, gdy raport ma plik; inaczej `None`.
3. **Plan (T1 Step 2).** `UpdatePlan`: pola `store`, `checked_at`,
   `kartograf_version`, `items`, `notices: tuple[Notice, ...] = ()`;
   `SCHEMA = PLAN_SCHEMA`; wlasciwosc `ok` (brak pozycji `check_failed`);
   `from_dict(payload)` (czytnik: `from_json` wola `from_dict(json.loads(...))`;
   toleruje brak `notices` i `ok`, ignoruje `ok`, odrzuca inny `schema` jako
   `ValidationError`); `merge` laczy `notices` bez powtorzen w kolejnosci;
   `require_store` nie sprawdza juz schematu (obiekt zawsze ma `kartograf-plan/1`).
   Funkcje poziomu komendy `check_data`, `check_collection`, `check_landcover`,
   `check_soil`, `check_hsg` zwracaja plan z `notices` = komunikaty swojego
   `NoticeSink` (`dataclasses.replace(plan, notices=sink.notices)`); nizsze
   `check_*` torow nie zmieniaja sie. Stale `PLAN_SCHEMA` i `AVAILABILITY_SCHEMA`
   zostaja (importuja je testy). `AvailabilityReport` traci pole `schema` i
   wlasny `to_json`; `JSON_KEYS` = `request`, `checked_at`, `areas`,
   `combinations`, `notices`, `ok`.
4. **Wyjatki i `error_report` (T2).** `code` w `__dict__` kazdej klasy
   (`KartografError`, `ValidationError`, `ParseError`, `UsageError`,
   `DownloadError`, `NoCoverageError`, `YearRangeError`, `CacheError`,
   `InvalidSidecarError`, `TransformError`, `TransformUnavailableError`); atrybut
   `hint` jest zwyklym polem instancji ustawianym w konstruktorze;
   `ValidationError.option`/`options`/`allowed` sa zwyklymi atrybutami (mozna je
   ustawic przy re-raise z `raise ... from`). Funkcje
   `pl_option_error`, `cz_option_error`, `cz_orto_option_error`,
   `_contours_error`, `_file_variant_error`, `_direction_error` w
   `download/options.py` zwracaja dzis `str | None`: po T2 zwracaja
   `ValidationError | None`, a wywolujacy robia `raise error` (dziesiec miejsc wywolania w
   `download/data.py` i `options.py`). `error_report` zna trzy kody spoza klas:
   `interrupted` (`KeyboardInterrupt`, 130), `io_error` (`OSError`, 1; `details`
   `{"errno": nazwa symboliczna, "path": filename}` tylko niepuste),
   `internal_error` (1). Hint: algorytm ze specu 6.3 bez skladnika (b) (przyklad z
   katalogu - T5); bez katalogu flaga w skladniku (a) to nazwa `option`.
5. **Moduly T3 i T4d poza `catalog/`.** `kartograf/source_info.py`:
   `SourceInfo`, `SourceList`, `list_sources`, `LayerList`, `list_layers`
   (logika `_source_choice`/`_product_flag` z `cli/groups/*.py` i warstw z
   `cli/landcover_cmd.py`, `cli/soil_cmd.py`; `select` to obiekt opcja ->
   wartosc | lista; tekst WYBOR tabeli CLI = `select` zlozony z powrotem we
   flagi - renderuje T5); `kartograf/cache_info.py`: `CacheInfo`,
   `get_cache_info`, `clear_cache` (logika z `cli/cache_cmd.py`);
   `kartograf/store_documents.py`: `StoreOverview`, `StoreEntries`,
   `StoreSidecar`, `describe_store`, `list_store_entries`, `read_store_sidecar`
   (`truncated` = pobranie `limit + 1` wpisow z `iter_store`; `StoreEntries.prepare_context`
   ustawia `ctx.omit = {("Sidecar", "raw")}`); `kartograf/sheet_info.py`
   (T4d): `SheetInfo`, `describe_sheet`, `SheetList`, `find_sheets`.
   Wszystkie dokumenty to `@dataclass(frozen=True)` z `Document`.
6. **Katalog (T4).** Deklaracje w `kartograf/catalog/commands/<grupa>.py`
   odkrywane po nazwie modulu (`pkgutil`, jak dzis `register_groups`): nowa grupa
   = nowy plik, zadnego wspolnego pliku do edycji (podzial T4b, T4c, T4d bez
   konfliktow). `spec.py`: `Param`, `Command`, `Group`, `Constraint`, `Example`
   (frozen; wartownik `AUTO` dla `flag` i `argument` = "wyprowadz z nazwy", `None` =
   brak CLI albo API). Dostawcy (`allowed`, `description` jako funkcje bez
   argumentow) rozstrzyga `build`/`cliparser` w chwili budowy, nigdy przy imporcie
   modulu. `build.py`: `build_catalog(commands, groups) -> Catalog` (czysta;
   testowalna na deklaracjach syntetycznych) i `get_catalog(...)` na deklaracjach
   z `commands/` (pelny katalog budowany raz na proces, filtry tworza widoki).
   `cliparser.py`: `build_parser(commands, groups, *, prog="kartograf",
   usage_errors=False)`; tryb `usage_errors=True` zglasza `UsageError` zamiast
   wypisac `usage:` i zakonczyc kodem 2; kazdy parser-lisc dostaje
   `set_defaults(_command_id=<id>)`, parser grupy `_group_parser` (jak dzis
   `add_group`); flagi nigdy `required=True`; `dest` = `Param.dest`; logika
   `_Parser`, `_HelpFormatter`, `_LazyVersionAction`, `removed_command_error`,
   `_unknown_text`, `_UNKNOWN_HINTS`, `_join_bbox_values` kopiowana z
   `cli/_parser.py` (etap 1; `cli/` zamrozone, usuniecie dubla w T5).
   `formatting.py`: `format_command_line(command, options, run=None)` (kanoniczna
   linia `kartograf <grupa> <komenda> ...`; to samo wyliczalo `ExampleInfo.command_line`
   i `kartograf.format_command`). `hints.py`: `example_for(command, option)` ->
   `(flaga, command_line)`; skladnik (b) hintu: pierwszy przyklad komendy uzywajacy
   opcji, inaczej pierwszy przyklad. `kinds.py`: `parse_bbox_arg`,
   `parse_per_country`, `layer_codes` (kopie z `cli/_args.py`, T5 usuwa dubel);
   po T5 takze `convert_arguments` i `options_to_json`/`options_from_json`/
   `check_options_json` (przeniesione z `project/commands.py`).
7. **Rownowaznosc parsera (T4, O6).** Test (bez zmiany `cli/`): stary
   `kartograf.cli._parser.create_parser()` vs `build_parser(...)` zbudowany z
   deklaracji BEZ parametru `json` i bez komendy `catalog`, z `COLUMNS=100`:
   dla kazdej zadeklarowanej komendy te same akcje (opcje, `dest`, nazwa typu,
   `choices`, `default`, `nargs`, `required`, `const`, `metavar`, `help`, sekcja,
   grupa wykluczajaca) i **identyczny `format_help()`**; test kompletnosci (T4d): kazda
   komenda-lisc starego parsera jest zadeklarowana. Po T5 stary parser znika, a
   test (a) specu 12.5 porownuje prawdziwy parser z `get_catalog(params=True)`.
8. **`--json` i `main()` (T5).** Tryb JSON wykrywa `"--json" in argv` przed
   parsowaniem; w trybie JSON parser jest budowany z `usage_errors=True`, a wszystkie
   bledy ida przez `error_report`; stdout przestawiony na UTF-8
   (`sys.stdout.reconfigure(encoding="utf-8")`); handler komendy zwraca kod, a
   dokument drukuje wspolna funkcja `emit_document(document)` (`to_json()`);
   kod wyjscia: `0` gdy dokument nie ma `ok` albo `ok` jest prawda, `1` gdy `ok` falsz,
   `e.exit_code` dla bledow; `KARTOGRAF_DEBUG=1` ponawia wyjatek takze w trybie JSON.
   Handlery nie drukuja wlasnych `Error:` za bledy wejscia: zglaszaja
   `ValidationError` z `option`, a `main` je tlumaczy.
9. **Serwer MCP (T6).** `kartograf/catalog/tools.py` (czyste dane, bez `mcp`):
   `ToolSpec(name, title, description, input_schema, annotations, family,
   command)`, `tool_specs(families=None)`, `check_arguments_schema(tool)`,
   `FAMILIES`; `kartograf/mcp_server.py`: `create_server(*, families, cache,
   allow_dirs) -> Server` i `main(argv=None) -> int`; praca w watku
   (`anyio.to_thread.run_sync`, `anyio.CapacityLimiter(4)` dla narzedzi danych i
   sprawdzajacych), postep przez `anyio.from_thread.run(ctx.session.report_progress,
   n, None, tekst)` z licznikiem zdarzen pod blokada; wynik
   `CallToolResult(content=[TextContent(text=to_json(indent=None))],
   structured_content=to_dict(), is_error=<kod wyjscia != 0>)`.

## Fakty o obecnym kodzie (zweryfikowane 2026-10-18 na `8c65f4e`)

- Parser CLI: `kartograf/cli/_parser.py` (354 linie): `_HelpFormatter` :20, `_Parser`
  :35, `_LazyVersionAction` :48, `_REMOVED_COMMANDS` :74, `removed_command_error` :94,
  `_BBOX_VALUE` :119, `_UNKNOWN_HINTS` :126, `_join_bbox_values` :142, `_subparsers`
  :161, `_flag_owners` :184, `_unknown_text` :203, `parse_command_line` :219,
  `create_parser` :237. Importuja go `cli/commands.py` i `cli/project_cmd.py`; w
  `tests/` 4 pliki (`test_cli_help.py`, `test_project_cli.py`, `test_cli_language.py`,
  `test_availability.py`).
- `kartograf/cli/_args.py` (198): `BBOX_HELP` :26, `SELECTION_TITLE`/`PRODUCT_TITLE`/
  `OUTPUT_TITLE` :41-43 (= `section` flag w specu), `add_output` :46, `examples` :58,
  `add_update_flags` :64, `add_bbox_crs` :81, `add_area_flags` :92, `add_quiet` :120,
  `layer_codes` :131, `parse_per_country` :137, `parse_bbox_arg` :162.
- `kartograf/cli/commands.py` (130): `_dispatch` :48 (osobne galezie `parse` i
  `cache` :50-53, brak handlera -> pomoc i kod 2 :55-61, `--plan` wymaga trybu
  :62-66), `_StderrLines`/`_retry_lines` :70-83 (logger `kartograf.transport.http`),
  `main` :86 (`removed_command_error` -> `parser.error` :103-105, `parse_command_line`
  poza `try` :107, `KeyboardInterrupt` -> 130 :111, `KartografError` -> 1 :116,
  `Exception` -> 1 :121, `KARTOGRAF_DEBUG` :117, :122).
- Handlery (`kartograf/cli/*_cmd.py`, linie): `download_cmd.py` 510, `availability_cmd.py`
  313, `project_cmd.py` 279, `parse_cmd.py` 253 (`format_cz_sheet` :25,
  `format_sheet_info` :65, `format_hierarchy` :99, `format_children` :125,
  `format_descendants` :158, `cmd_parse` :196), `landcover_cmd.py` 186
  (`cmd_landcover_list_layers` :41, `landcover_task_arguments` :130,
  `cmd_landcover_download` :145), `soil_cmd.py` 167 (`soil_download_task_arguments`
  :33, `soil_hsg_task_arguments` :43, `cmd_soil_download` :48,
  `cmd_soil_list_layers` :76, `cmd_soil_hsg` :99), `collection_cmd.py` 103,
  `cache_cmd.py` 100 (`cmd_cache` :41). `download_cmd.py`: cykl pliku planu
  `run_with_plan_file`, linie planu `_plan_line`, `_report_plan` (kod 1 przy
  `check_failed`), `_print_notice` (`Info:`/`Warning:` na stderr).
- Grupy: `kartograf/cli/groups/` 14 plikow (1925 linii; `__init__.py` 100 z
  `register_groups` :24, `add_group` :31, `add_list_sources` :50; `_collection.py` 167;
  `elevation.py` 406 z `_source_choice` :43; `imagery.py` 258; `landcover.py` 221;
  `soil.py` 151; `project.py` 155; pozostale 4-82). Komendy: 36 lisci = `parse` (1),
  `cache stats|path|clear` (3), `elevation download|list-sources|availability` (3),
  `imagery download|list-sources` (2), `landcover download|list-sources|list-layers`
  (3), `soil download|hsg|list-sources|list-layers` (4), 7 grup kolekcji po
  `download|list-sources` (14), `project init|add|remove|download|status|verify` (6).
- Projekt: `kartograf/project/commands.py` (770): `OptionKind` :75, `TaskDownload` :82,
  `TaskCheck` :104, `TaskFiles` :119, `TaskCommand` :133, `COMMANDS` :464,
  `data_commands_text` :578, `task_command` :597, `options_to_json` :666,
  `check_options_json` :712, `options_from_json` :746. `model.py`: `PinnedFile` :32,
  `ProjectTask` :53, `Project` :74, `TaskResult` :84, `ProjectReport` :102, `FileCheck`
  :114, `ProjectCheck` :133. `project_cmd.py`: odrzucenie komend nie-danych i flag
  uruchomienia (`--workers` przez `_workers_given`, `--summary`, `--check-updates`,
  `--upgrade`, `--force`, `--plan`, `--output` rozny od magazynu).
- Raporty: `UnitFile` `download/data.py:144`, `UnitFailure` :156, `DataReport` :170;
  `VersionedFile` `download/fetch.py:135`; `PlanItem` `download/plan.py:47`,
  `UpdatePlan` :73 (pole `schema` :80, `to_json` :82, `from_json` :89, `merge` :112,
  `items_for` :131, `new_plan` :163, `require_store` :173); `AvailabilityArea`
  `download/availability.py:183`, `AvailabilityCombination` :201, `AvailabilityReport`
  :245 (pole `schema` :261, `to_json` :263); `CollectionReport`
  `download/collections.py:483`; `LandCoverReport` `landcover/manager.py:296`,
  `SoilReport` :319; `HsgReport` `hydrology/hsg.py:398`, `calculate_hsg` :854,
  `check_hsg` :923, `hsg_statistics` :980; `Notice` `notices.py:99`, `NoticeSink`
  :111; `LazTile` `providers/pl/gugik_laz.py:91` (nie frozen), `SupersededLazTile`
  :164; `BBox` `core/bbox.py:36` (NamedTuple); `DownloadProgress`
  `download/manager.py:102` (nie frozen). Funkcje komend: `download_data`
  `download/data.py:294`, `check_data` :394, `download_collection`
  `download/collections.py:2730`, `check_collection` :3158, `download_landcover`
  `landcover/manager.py:1722`, `check_landcover` :1836, `download_soil` :1923,
  `check_soil` :1993, `check_availability` `download/availability.py:371`.
- Wyjatki: `kartograf/exceptions.py` (180 linii, 8 klas; `ParseError` jest
  `ValidationError`), `kartograf/transform/crs.py` `TransformError` :31,
  `TransformUnavailableError` :35 (`rejected`, `remedy`). Miejsc `raise
  ValidationError(` jest 376 w kodzie pakietu (najwiecej: `download/collections.py`
  44, `download/options.py` 41, `landcover/manager.py` 24, `download/data.py` 18,
  `core/geometry.py` 12, `project/operations.py` 11, `download/availability.py`
  10, `project/manifest.py` 10). Walidatory: `require_product` `download/options.py:81`,
  `pl_option_error` :352, `cz_option_error` :528, `_contours_error` :588,
  `cz_orto_option_error` :627, `validate_request_bbox` :785, `validate_area_choice`
  :810, `check_layer` :832, `output_required` :857, `validate_request` :886,
  `_direction_error` :1042; `require_collection_product` `collections.py:365`,
  `validate_collection_request` :1210; `require_landcover_product`
  `landcover/manager.py:203`, `validate_landcover_request` :1887,
  `validate_soil_request` :2025; `validate_hsg_request` `hydrology/hsg.py:955`;
  `validate_data_request` `download/data.py:449`.
- Odczyt magazynu (`kartograf/store.py`, 1483 linie, po przegladzie): `Sidecar` :55,
  `StoreEntry` :112, `SegmentInfo` :169, `read_sidecar` :508, `describe_segment`
  :731, `list_segments` :792, `_unit_slot` :1202, `_validated_segment` :1330,
  `iter_store` :1361, `link_target` :1441; `Sidecar.schema` zawsze
  `kartograf-meta/1` (:433); `ValidationError` bez `option` w :1337, :1348, :1422.
- Cache: `kartograf/cache/defaults.py` `default_cache_path` :13 (cwd), `open_cache` :19.
  Rejestr zrodel: `kartograf/sources/registry.py` `sources_for` :3055.
- Pakiet: `kartograf/__init__.py` 409 linii, `__version__ = "0.8.0"`; `pyproject.toml` bez
  `package-data` i bez `py.typed`; `[project.scripts]` tylko `kartograf`;
  `MANIFEST.in` = `graft tests` + `global-exclude __pycache__ *.py[cod]`; brak
  `scripts/`, `kartograf/__main__.py`, `llms.txt`; `tests/__init__.py` istnieje (pytest
  wstawia korzen repo do `sys.path`); `addopts = "-v --tb=short"`, `fail_under = 60`.
- Testy: 5339 offline (18 `live`), 139 plikow w `tests/`; infrastruktura zgodnosci:
  `tests/parity.py` (`run_both`, `assert_same_store`, `assert_notices_printed`),
  `tests/conftest.py` (autouse `_block_network`, `_isolated_default_cache`,
  `_offline_wms_layers`, `_offline_wfs_types`; `frozen_clock`, `RecordedIndex`,
  `make_provider`); odwolania do wnetrznosci CLI: `create_parser` 68 w 7 plikach
  (`test_cli.py` 47), `_download_arguments` 6 (`test_availability.py`),
  `_subparsers` 4 (`test_cli_help.py`), `kartograf.cli._args` 3 (`test_cli.py`),
  `_task_arguments` 2 (`test_cli.py`), `COMMANDS` 11 (`test_project_commands.py`,
  `test_project_cli.py`), `options_from_json`/`options_to_json`/`check_options_json`
  12 (`test_project_commands.py`), `format_sheet_info` 12 i `cmd_parse` 10
  (`test_cli.py`), `cmd_cache` 5 (`test_metadata_cache.py`); `tests/test_plan.py:86`
  (`dataclasses.replace(plan, schema=...)`), `tests/test_cli_translation.py::test_cli_imports_no_data_logic`.
- Srodowisko: Python 3.13.5; pytest 9.0.2, pytest-cov 7.0.0, ruff 0.15.0, mypy 2.3.0,
  build 1.6.0; brak `mcp`, `jsonschema`, `pydantic`, `setuptools`.

## Mapa plikow

| Plik | Zmiana | Zadanie (tor/fala) |
|---|---|---|
| `kartograf/py.typed`, `pyproject.toml`, `MANIFEST.in` | NOWY / package-data, klasyfikator, `include` | T0 (A) |
| `scripts/gate.sh`, `kartograf/__main__.py`, `tests/test_main_module.py` | NOWE | T0 (A) |
| `kartograf/serialization.py`, `tests/test_serialization.py`, `tests/test_json_contract.py` | NOWE | T1 (A) |
| `kartograf/core/bbox.py` | `BBox.__json__` | T1 (A) |
| `kartograf/download/{plan,availability,data,collections}.py`, `kartograf/landcover/manager.py`, `kartograf/hydrology/hsg.py`, `kartograf/project/model.py` | `Document`, `JSON_KEYS`, `notices`/`ok`, `summary` | T1 (A) |
| `kartograf/exceptions.py`, `kartograf/transform/crs.py`, `kartograf/error_report.py`, `tests/test_errors.py` | atrybuty bledow, `ErrorReport` | T2 (A) |
| `kartograf/download/{options,area,arguments,data,availability,collections}.py`, `kartograf/landcover/manager.py`, `kartograf/hydrology/hsg.py`, `kartograf/store.py`, `kartograf/project/operations.py`, `kartograf/core/bbox.py` | `option`/`allowed` w walidatorach | T2 (A) |
| `kartograf/source_info.py`, `kartograf/cache_info.py`, `kartograf/store_documents.py`, `tests/test_{source_info,cache_info,store_documents}.py`, `kartograf/__init__.py` | NOWE funkcje i eksporty | T3 (A) |
| `kartograf/catalog/{__init__,spec,shared,kinds,formatting,model,build,cliparser}.py`, `tests/test_catalog*.py` | NOWE | T4a (B) |
| `kartograf/catalog/commands/{elevation,imagery}.py` | NOWE | T4b (B) |
| `kartograf/catalog/commands/{landcover,soil,boundaries,cadastre,models3d,hydro,names,maps,geodesy}.py` | NOWE | T4c (B) |
| `kartograf/catalog/commands/{project,misc}.py`, `kartograf/catalog/hints.py`, `kartograf/sheet_info.py`, `tests/test_sheet_info.py` | NOWE | T4d (B) |
| `kartograf/commands.py`, `kartograf/catalog/{kinds,cliparser}.py`, `kartograf/cli/**`, `kartograf/project/{commands,operations}.py`, `kartograf/error_report.py`, `kartograf/__init__.py` | KB-2..KB-5, parser z katalogu, `--json`, kody wyjscia | T5 |
| `tests/test_commands_layer.py`, `tests/test_cli_json.py`, `tests/test_cli_handlers.py` oraz aktualizacje `tests/test_cli*.py`, `tests/test_project_*.py`, `tests/test_public_api.py`, `tests/test_cli_translation.py` | NOWE i przepisane | T5 |
| `kartograf/catalog/tools.py`, `kartograf/mcp_server.py`, `pyproject.toml`, `tests/test_mcp_tools.py`, `tests/test_mcp_server.py` | NOWE / extra `mcp`, skrypt | T6 |
| `llms.txt`, `MANIFEST.in`, `tests/test_llms_txt.py` | NOWE | T7 |
| `docs/USAGE.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`, `docs/SCOPE.md`, `docs/PRD.md`, `docs/CHANGELOG.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md` (CRLF), `README.md`, `CLAUDE.md`, `tests/test_docs_tables.py` | dokumentacja | T8 |
| `docs/research/2026-10-xx-agent-interface-e2e/raport.md` | NOWY | T9 |

---

## Fala 1, Tor A (biblioteka): T0-T3

Kolejnosc toru: T0 Step 1 (zrzut) -> **T1 Step 1 -> T2 Step 1 (= K1, zglos koordynatorowi hash)** ->
T0 Step 2-4 -> T1 Step 2-5 -> T2 Step 2-7 -> T3. Worktree `../agent-interface-a`,
galaz `feat/agent-interface-a`.

### Task T0: zrzut odniesienia, `py.typed`, `scripts/gate.sh`, `python -m kartograf`

**Files:**
- Create: `kartograf/py.typed`, `kartograf/__main__.py`, `scripts/gate.sh`, `tests/test_main_module.py`
- Modify: `pyproject.toml`, `MANIFEST.in`
- Poza repo: zrzut odniesienia (Dodatek A)

- [x] **Step 1: Zrzut odniesienia (poza repo, bez commita).** Zapisz skrypt z Dodatku A
  poza repo (`<katalog-danych>/kartograf/agent-interface/baseline_dump.py`) i uruchom z
  korzenia worktree PRZED zmiana kodu:
  `$PY <katalog-danych>/kartograf/agent-interface/baseline_dump.py <katalog-danych>/kartograf/agent-interface/before`.
  Oczekiwany wydruk: `leaf commands: 36; parsers: 50; text runs: 33`. Uruchom drugi raz
  do `before-2`: `diff -r before before-2` pusty (determinizm). Skrypt nic nie
  pobiera (siec zablokowana w skrypcie). Katalog `before` przekaz koordynatorowi:
  korzystaja z niego T4 (kontrola `--help` i `list-sources`) i T5 (porownanie przed/po).
- [x] **Step 2: `py.typed` i pakowanie (D17).** `kartograf/py.typed` (pusty plik);
  `pyproject.toml`: `[tool.setuptools.package-data]` z `kartograf = ["py.typed"]` i
  klasyfikator `"Typing :: Typed"`; `MANIFEST.in`: `include kartograf/py.typed`. Brak testu
  stalego (plik jest w drzewie zrodel, wiec test nie dowodzi pakowania - spec 10.1).
  Weryfikacja jednorazowa (siec: `build` pobiera `setuptools` do izolowanego srodowiska):
  ```
  $PY -m build --wheel --sdist --outdir <katalog-danych>/kartograf/agent-interface/dist .
  $PY -m zipfile -l <...>/dist/kartograf-0.8.0-py3-none-any.whl     # zawiera kartograf/py.typed
  tar tzf <...>/dist/kartograf-0.8.0.tar.gz | grep py.typed          # zawiera py.typed
  ```
  Usun `build/` i `*.egg-info` z korzenia worktree (sa w `.gitignore`).
  Commit: `build(packaging): py.typed (PEP 561), package-data i klasyfikator Typing :: Typed`
- [x] **Step 3: `scripts/gate.sh` (D19).** Zapisz skrypt z Dodatku B (implementacja
  referencyjna, sprawdzona 2026-10-18), `chmod +x`, konce linii LF (`.editorconfig`).
  Weryfikacja (wszystkie wyniki do raportu):
  - `bash -n scripts/gate.sh`; `scripts/gate.sh -x -k test_version` -> kod 0, ostatnia
    linia `GATE OK (<N> s)`;
  - zepsuty plik: `echo "x = (" > kartograf/_gate_probe.py; scripts/gate.sh -x; echo $?`
    -> kod 1, wynik urywa sie po `== ruff check`; usun plik;
  - inny checkout: skopiuj skrypt do pustego katalogu `<tmp>/x/scripts/` po `git init`
    i uruchom z `KARTOGRAF_PYTHON=$PY` -> kod 2 i komunikat `brama sprawdza inny checkout`;
  - pelny przebieg `scripts/gate.sh` w worktree: `GATE OK` (czas ok. 2 min).
  Commit: `build(dev): scripts/gate.sh - jedna komenda bramy (ruff, format, mypy, pytest offline)`
- [x] **Step 4: `python -m kartograf` (D20).**
  - Test RED (`tests/test_main_module.py`): `test_python_dash_m_kartograf_runs_the_cli`:
    `subprocess.run([sys.executable, "-m", "kartograf", "--version"], cwd=<korzen repo =
    Path(kartograf.__file__).resolve().parents[1]>, capture_output=True, text=True,
    timeout=60)` -> `returncode == 0` i `stdout.startswith("kartograf ")`. `cwd` musi byc
    korzeniem testowanego drzewa (instalacja edytowalna wskazuje glowny checkout, a
    `-m` dopisuje cwd do `sys.path`). RED: `No module named kartograf.__main__`.
  - Implementacja `kartograf/__main__.py`: docstring, `import sys`, `from
    kartograf.cli.commands import main`, `if __name__ == "__main__": sys.exit(main())`.
  - Weryfikacja: test zielony; `$PY -m kartograf parse N-34-130-D` drukuje opis godla;
    `$PY -m kartograf.cli.commands --version` dziala jak dotad.
  Commit: `feat(cli): python -m kartograf`
- [x] **Step 5: Brama zadania** (`scripts/gate.sh`) - zielona.

### Task T1: serializacja i dokumenty JSON (D1, D2, spec 5)

**Files:**
- Create: `kartograf/serialization.py`, `tests/test_serialization.py`, `tests/test_json_contract.py`
- Modify: `kartograf/core/bbox.py`, `kartograf/download/{plan,availability,data,collections}.py`,
  `kartograf/landcover/manager.py`, `kartograf/hydrology/hsg.py`, `kartograf/project/model.py`,
  `tests/test_plan.py`, `tests/test_updates.py`, `tests/test_availability.py`

- [x] **Step 1: `Document` i koder (K1, czesc 1).**
  - Test RED (`tests/test_serialization.py`; przyklady `Document` definiowane w pliku
    testu; RED = `ModuleNotFoundError: kartograf.serialization`):
    `test_scalars_and_finite_floats` (`NaN` i `inf` = `ValueError`);
    `test_path_is_absolute_posix` (sciezka wzgledna dostaje `Path.cwd()`; bez `resolve()`:
    dowiazanie nie jest rozwiazywane); `test_sequences_and_sets_sorted` (`tuple` i `list` ->
    tablica, `frozenset({"b", "a"})` -> `["a", "b"]`); `test_mapping_keys_must_be_str`
    (`TypeError`); `test_decimal_is_string_and_datetime_is_utc_seconds` (`Decimal("0.5")` ->
    `"0.5"`; aware `+02:00` -> UTC `+00:00` bez mikrosekund; naive = `ValueError`: strefa nie
    jest zgadywana); `test_bbox_hook` (`BBox(1, 2, 3, 4, "EPSG:2180")` -> `{"bbox": [1, 2, 3, 4],
    "crs": "EPSG:2180"}`); `test_enum_value`; `test_unknown_type_is_type_error`
    (`object()`, `bytes`); `test_dataclass_order_and_json_false` (pole z
    `metadata={"json": False}` pominiete); `test_omit_pairs_skip_one_class_field` (`ctx.omit`
    pomija `raw` tylko klasy `Inner`); `test_unhashable_frozen_dataclass_encodes` (dataclass z
    `__hash__ = None` i polem `dict`); `test_document_key_resolution` (pole -> wlasciwosc ->
    `JSON_FILL`; klucz bez zrodla = `ValueError`; kolejnosc `JSON_KEYS`); `test_schema_is_first_key_and_nested_has_none`;
    `test_json_hook_sees_context_from_prepare_context` (`prepare_context` ustawia `ctx.store`,
    `__json__` zagniezdzonego typu sklada sciezke `ctx.store / wartosc` - jak `PinnedFile`);
    `test_to_json_format` (wciecie 2, `ensure_ascii=False`, `\n` na koncu; `indent=None`:
    separatory `(",", ":")` i brak `\n`; `NaN` w danych = `ValueError`, nie `NaN` w tekscie);
    `test_to_json_is_byte_stable`; `test_schemas_registry` (rejestr zbiera klasy, dwie klasy
    jednego schematu razem; zla nazwa schematu i pole dataclass `schema` = `ValueError` przy
    definicji klasy).
  - Implementacja: `kartograf/serialization.py` wg "Decyzje implementacyjne" 1 i
    sygnatur K1; `BBox.__json__` w `kartograf/core/bbox.py` (NamedTuple moze miec metode).
    Modul importuje tylko stdlib i `kartograf.exceptions` (test importu: `python -c "import
    kartograf.serialization"` w czystym procesie nie ladowal `kartograf.cli`, `kartograf.catalog`).
  - Weryfikacja: `$PY -m pytest tests/test_serialization.py -q`; brama kroku.
  Commit: `feat(serialization): mixin Document, koder JSON i rejestr schematow (D1)`
- [x] **Step 2: `UpdatePlan` i `AvailabilityReport` na `Document` (`kartograf-plan/1`,
  `kartograf-availability/1`).**
  - Test RED (`tests/test_plan.py`, `tests/test_availability.py`, `tests/test_updates.py`):
    `test_plan_to_dict_schema_first` (RED: `AttributeError: ... no attribute 'to_dict'`; klucze
    `schema, store, checked_at, kartograf_version, items, notices, ok`);
    `test_plan_ok_is_false_with_check_failed`; `test_plan_from_dict_reads_0_8_dev_plans`
    (plan bez `notices` i `ok` oraz z obcym `ok` wczytuje sie; `ok` wyliczane);
    `test_plan_from_dict_rejects_other_schema` (`ValidationError`, `match="schemat"` - zastepuje
    `test_plan.py:86`); `test_plan_json_round_trip_with_notices`;
    `test_merge_joins_notices_without_repeats`;
    `test_check_plan_carries_the_notices_of_the_call` parametryzowany po `check_data`,
    `check_collection`, `check_landcover`, `check_soil`, `check_hsg`: scenariusz z istniejacych
    testow danej funkcji, w ktorym `on_notice` dostaje komunikat (asercja: `plan.notices ==
    tuple(odebrane)`, niepuste); `test_availability_json_has_schema_first_and_same_content`
    (`json.loads` rowny dotychczasowemu dokumentowi poza kolejnoscia klucza `schema`; pierwszy klucz
    `schema`).
  - Implementacja wg "Decyzje implementacyjne" 3: `UpdatePlan(Document)` i
    `AvailabilityReport(Document)` (ClassVar `SCHEMA`, `JSON_KEYS`; wlasne `to_json` usuniete),
    `UpdatePlan.notices`/`ok`/`from_dict`/`merge`, `require_store` bez sprawdzenia schematu,
    `check_*` poziomu komendy z `notices`; `tests/test_plan.py:86` przepisany, pozostale testy
    bez zmiany asercji o zachowaniu.
  - Weryfikacja: `$PY -m pytest tests/test_plan.py tests/test_availability.py tests/test_updates.py
    tests/test_cli_availability.py tests/test_parity.py -q` (bajtowa zgodnosc `--json` CLI = API
    raportu dostepnosci zostaje zielona: oba wola `to_json`); brama kroku.
  Commit: `refactor(plan)!: UpdatePlan i AvailabilityReport jako Document (schema pierwszym kluczem, notices, ok, from_dict)`
  w tresci: `BREAKING: pole dataclass schema zastapione ClassVar i wlasciwoscia; kod budujacy
  AvailabilityReport(schema=...) i dataclasses.replace(plan, schema=...) przestaje dzialac; plany
  0.8.0-dev nadal sie wczytuja`
- [x] **Step 3: pieciu raportow komend danych na `kartograf-download/1` i `HsgReport.summary` (D2).**
  - Test RED (`tests/test_serialization.py`, `tests/test_hsg*.py`): `test_download_family_has_one_key_set`
    (po jednym minimalnym raporcie z `DataReport`, `CollectionReport`, `LandCoverReport`,
    `SoilReport`, `HsgReport`: `list(report.to_dict()) == ["schema", *DOWNLOAD_KEYS]`; klucze
    spoza klasy: `[]`, `summary` `None`); `test_download_report_equals_the_spec_example`
    (raport zbudowany wg przykladu specu 5.4.1: `to_dict()` rowne literalowi, sciezki bezwzgledne,
    `notices` z `Notice`); `test_superseded_encodes_tile_and_covered_by` (`DataReport` z
    `SupersededLazTile`); `test_calculate_hsg_summary_matches_hsg_statistics` (istniejacy scenariusz
    HSG: `summary=True` -> `report.summary == hsg_statistics(<plik HSG>)`; `summary=False` ->
    `None`; raport bez pliku -> `None`); `test_unit_failure_and_unit_file_keys`.
  - Implementacja wg "Decyzje implementacyjne" 2 (`DOWNLOAD_SCHEMA`, `DOWNLOAD_KEYS`,
    `DOWNLOAD_FILL` w `download/data.py`; klasy w `collections.py`, `landcover/manager.py`,
    `hydrology/hsg.py` je importuja); `calculate_hsg(..., summary=False)`; CLI zostaje bez zmian
    (wola `hsg_statistics` po obliczeniu - przelacza T5).
  - Weryfikacja: `$PY -m pytest tests/test_serialization.py tests/test_hsg*.py
    tests/test_parity_landcover.py tests/test_download_data.py -q`; brama kroku.
  Commit: `feat(api): kartograf-download/1 dla DataReport, CollectionReport, LandCoverReport, SoilReport i HsgReport; calculate_hsg(summary=)`
- [x] **Step 4: `Project`, `ProjectReport`, `ProjectCheck` jako dokumenty projektu.**
  - Test RED (`tests/test_serialization.py`): `test_project_state_document` (klucze
    `schema` = `kartograf-project-state/1`, `directory`, `output_dir`, `tasks`; zadanie:
    `name, command, options, pinned_at, kartograf_version, geometry_sha256, files`; `PinnedFile`:
    `role, unit, path, version, label, sha256, size_bytes`, a `path` i `version` bezwzgledne =
    `output_dir` + wartosc manifestu); `test_project_report_nests_project_without_schema` (`schema,
    project, tasks, notices, ok`; zagniezdzony `project` bez klucza `schema`; `TaskResult`: `name,
    outcome, pinned, unpinned, errors`); `test_project_check_document` (`schema, project, files,
    not_downloaded, notices, ok`; `FileCheck.path` bezwzgledna);
    `test_pinned_file_outside_a_project_document_is_an_error` (`encode(PinnedFile(...))` bez
    `ctx.store` = `ValueError`); `test_task_options_keep_manifest_form` (sciezka wzgledna
    geometrii w `tasks[].options` zostaje wzgledna).
  - Implementacja: `Project`, `ProjectReport`, `ProjectCheck` z `Document` (`SCHEMA`,
    `JSON_KEYS`, `prepare_context` ustawia `ctx.store = project.output_dir`); `PinnedFile.__json__` i
    `FileCheck.__json__` skladaja sciezki wzgledem `ctx.store`; `ProjectTask` i reszta - kodowanie
    ogolne dataclass.
  - Weryfikacja: `$PY -m pytest tests/test_serialization.py tests/test_project_*.py -q`; brama kroku.
  Commit: `feat(project): Project, ProjectReport i ProjectCheck jako dokumenty JSON (sciezki pinow bezwzgledne)`
- [x] **Step 5: kontrakt kluczy dokumentow (spec 12.2).**
  - `tests/test_json_contract.py`: tabela `CONTRACT = {schemat: [dokladna lista kluczy w
    kolejnosci]}` dla dokumentow istniejacych po T1 (plan, availability, download, project-state,
    project-report, project-check) oraz kluczy typow zagniezdzonych (`UnitFile`, `VersionedFile`,
    `UnitFailure`, `PlanItem`, `LazTile`, `AvailabilityArea`, `AvailabilityCombination`,
    `PinnedFile`, `FileCheck`, `TaskResult`) - kopie ze specu 5.3-5.4, zmiana klucza = blad testu
    (A3). Dokumenty budowane z fixtur w pliku (bez sieci). `test_every_document_class_is_registered`
    (kazda podklasa `Document` w `SCHEMAS`). Kolejne zadania Toru A dopisuja swoje wiersze
    (`kartograf-error/1` w T2, dokumenty T3).
  - Weryfikacja: `$PY -m pytest tests/test_json_contract.py -q`; **brama zadania** (pelna).
  Commit: `test(json): kontrakt kluczy dokumentow kartograf-*/1`

### Task T2: kody bledow, `error_report`, `option`/`allowed` w walidatorach (D3, D4, D21, spec 6)

**Files:**
- Create: `kartograf/error_report.py`, `tests/test_errors.py`
- Modify: `kartograf/exceptions.py`, `kartograf/transform/crs.py`, `kartograf/__init__.py`
  (eksporty `UsageError`, `ErrorReport`, `error_report`); Step 2-6: `kartograf/download/{options,area,arguments,data,availability,collections}.py`,
  `kartograf/landcover/manager.py`, `kartograf/hydrology/hsg.py`, `kartograf/core/bbox.py`,
  `kartograf/store.py`, `kartograf/project/operations.py`

- [x] **Step 1: atrybuty wyjatkow i `error_report` (K1, czesc 2).**
  - Test RED (`tests/test_errors.py`): `test_every_kartograf_error_class_has_its_own_code`
    (import wszystkich modulow pakietu przez `pkgutil.walk_packages`; kazda podklasa
    `KartografError`: `"code" in cls.__dict__`, wzorzec `^[a-z][a-z0-9_]*$`, kody unikalne;
    RED: `AttributeError`/brak `code`); `test_error_code_table_equals_the_spec` (literal w
    tescie: `(code, wyjatek, exit_code)` = `(kartograf_error, KartografError, 1)`,
    `(invalid_input, ValidationError, 2)`, `(usage_error, UsageError, 2)`,
    `(invalid_sheet_code, ParseError, 2)`, `(download_failed, DownloadError, 1)`,
    `(no_coverage, NoCoverageError, 1)`, `(year_out_of_range, YearRangeError, 1)`,
    `(cache_error, CacheError, 1)`, `(invalid_sidecar, InvalidSidecarError, 1)`,
    `(transform_failed, TransformError, 1)`, `(transform_unavailable,
    TransformUnavailableError, 1)`, `(io_error, OSError, 1)`, `(interrupted,
    KeyboardInterrupt, 130)`, `(internal_error, Exception, 1)` == `ERROR_CODES`; `EXIT_CODES` =
    `0 ok`, `1 failed`, `2 usage`, `130 interrupted`);
    `test_existing_constructors_keep_working_and_take_hint` (`DownloadError("m", sheet="x",
    status_code=404)`, `NoCoverageError("m", hints=("a",))`, `YearRangeError(...)`,
    `InvalidSidecarError("m", path=p)` - dotychczasowe wywolania bez zmian, nowe `hint=`);
    `test_validation_error_attributes_and_details` (`option`, `options`, `allowed` jako krotki;
    `details()` pomija puste; `exit_code == 2`); `test_usage_error_is_a_validation_error`
    (`except ValidationError` lapie `UsageError`; kod `usage_error`);
    `test_error_report_document` (klucze `schema, code, message, hint, exception, exit_code,
    command, details`; `message` = `str(exc)`); `test_hint_sources_in_order` (`exc.hint` ->
    `hints` polaczone `"; "` (`NoCoverageError`, `YearRangeError`) -> `remedy`
    (`TransformUnavailableError`) -> `DEFAULT_HINT` (`CacheError`, `InvalidSidecarError`,
    `UsageError`)); `test_validation_hint_lists_allowed_values_with_option_name` (bez katalogu:
    `Dozwolone wartosci vertical_crs: EVRF2007, KRON86.`; ponad 40 wartosci -> 40 i `...`);
    `test_oserror_is_io_error` (`FileNotFoundError(2, "No such file", "/x")` -> `io_error`, kod 1,
    `details == {"errno": "ENOENT", "path": "/x"}`, `hint == "Sprawdz sciezke i uprawnienia: /x"`);
    `test_foreign_exception_is_internal_error` (`KeyError` -> `internal_error`, `message ==
    "KeyError: 'x'"`, hint o `KARTOGRAF_DEBUG`); `test_keyboard_interrupt_is_interrupted` (kod
    130); `test_hint_is_one_ascii_line_up_to_400_chars` (sciezka z polskimi znakami w
    `OSError`: `backslashreplace`; nowe linie -> spacje; obciecie z `...`);
    `test_error_report_is_registered` (`kartograf-error/1` w `SCHEMAS`). Dopisz wiersz
    `kartograf-error/1` do `tests/test_json_contract.py`.
  - Implementacja: `exceptions.py` i `transform/crs.py` wg "Decyzje implementacyjne" 4 i
    spec 6.1-6.2 (`code` w `__dict__` kazdej klasy; konstruktory z opcjonalnym `hint=`;
    `DETAIL_FIELDS`: `DownloadError` `("sheet", "status_code")`, `NoCoverageError` + `hints`,
    `YearRangeError` `("sheets", "min_year", "max_year", "hints")`, `InvalidSidecarError`
    `("path",)`, `TransformUnavailableError` `("rejected", "remedy")`, `ValidationError`
    `("option", "options", "allowed")`; `DEFAULT_HINT`: `CacheError`, `InvalidSidecarError`,
    `UsageError`); `error_report.py`: `ErrorCodeSpec`, `ExitCodeSpec` (frozen), `ERROR_CODES`,
    `EXIT_CODES` (teksty `meaning` po polsku ASCII), `ErrorReport(Document)`
    (`SCHEMA = "kartograf-error/1"`, `JSON_KEYS` jak w tescie), `error_report`; wyjatki spoza
    hierarchii: `message = f"{type(exc).__name__}: {exc}"` z `backslashreplace` dla znakow spoza
    ASCII. Eksporty w `kartograf/__init__.py` (`UsageError`, `ErrorReport`, `error_report`).
  - Weryfikacja: `$PY -m pytest tests/test_errors.py tests/test_json_contract.py -q`; brama
    kroku; pelny `pytest` (nowe atrybuty nie zmieniaja zachowania istniejacych wywolan).
  Commit: `feat(errors): stabilne kody bledow, exit_code, hint i UsageError; ErrorReport i error_report (D3)`
  **-> K1 gotowy: zglos koordynatorowi hash tego commita i commita T1 Step 1.**
- [x] **Step 2: `option`/`allowed` we wspolnych walidatorach opcji.** Pliki:
  `download/options.py`, `download/area.py`, `download/arguments.py`, `core/bbox.py`.
  - Test RED (`tests/test_errors.py::test_input_error_names_the_option`, tabela
    `OPTION_SCENARIOS` - lista minimalna; implementator dopisuje wiersz dla kazdego miejsca,
    ktore zmienia; `allowed` ma pochodzic z tego samego zrodla co tekst komunikatu):

    | Scenariusz | Wywolanie (`tmp` = katalog magazynu) | Oczekiwane |
    |---|---|---|
    | brak `product` | `download_data(product=None, output_dir=tmp, sheet="N-34-130-D-d-2-4")` | `option="product"`, `allowed` zawiera `nmt`, `nmpt`, `orto` |
    | zly `product` | `product="xyz"` | `option="product"` |
    | brak `output_dir` | `download_data(product="nmt", output_dir=None, ...)` | `option="output_dir"` |
    | brak `vertical_crs` | NMT 1m PL bez `vertical_crs` | `option="vertical_crs"`, `allowed == ("EVRF2007", "KRON86")` |
    | zly `vertical_crs` | `vertical_crs="XYZ"` | j.w. |
    | brak i zla `resolution` | NMT PL bez `resolution`; `resolution="7m"` | `option="resolution"`, `allowed` = etykiety rejestru wariantow |
    | brak obszaru | bez `sheet`, `bbox`, `geometry` | `options == ("sheet", "bbox", "geometry")` |
    | dwa obszary | `sheet` + `bbox` | `options` zawiera oba |
    | zly `bbox` | `BBox(5, 5, 1, 1, "EPSG:2180")` | `option="bbox"` |
    | zle godlo | `sheet="XYZ"` | `ParseError`, `option="sheet"` |
    | zly `sheet_system` | `sheet_system="1965"` | `option="sheet_system"`, `allowed == ("1992", "2000")` |
    | zla `country` | `country="xx"` | `option="country"`, `allowed == ("pl", "cz", "auto")` |
    | odwrocony przedzial lat | `min_year=2025, max_year=2020` | `options == ("min_year", "max_year")` |

    RED: `AssertionError: option is None` (dzis `option` nie istnieje: `AttributeError`).
  - Implementacja: `raise ValidationError(tekst, option=..., allowed=...)`; funkcje
    `pl_option_error`, `cz_option_error`, `cz_orto_option_error`, `_contours_error`,
    `_file_variant_error`, `_direction_error` zwracaja `ValidationError | None`, a ich dziesiec
    miejsc wywolania (`download/data.py` :792-800, :1731, :1810, :1875; `download/options.py`
    :945, :950, :977, :1137) robi `raise error`; `output_required` zostaje funkcja tekstu, a miejsca
    jej uzycia ustawiaja `option="output_dir"`; `ParseError` z `SheetParser` jest ponownie
    zglaszany z `option="sheet"` (`raise ParseError(str(e), option="sheet") from e`).
    Tekst komunikatow bez zmian (testy tekstu CLI zielone).
  - Weryfikacja: `$PY -m pytest tests/test_errors.py tests/test_input_errors.py tests/test_ux_messages.py
    tests/test_download_data.py tests/test_cli_language.py -q`; brama kroku.
  Commit: `feat(errors): option i allowed w walidatorach opcji danych (options, area, arguments, bbox)`
- [x] **Step 3: `download/data.py` i `download/availability.py`.** Test RED: wiersze tabeli dla
  `download_data`/`check_data` (pozostale walidatory `validate_data_request`) i
  `check_availability` (zly `product`: `allowed == ("nmt", "nmpt", "laz")`; `country`; obszar;
  `min_year`/`max_year` w przedziale roku warstw). Implementacja jak Step 2.
  Commit: `feat(errors): option i allowed w download_data, check_data i check_availability`
- [x] **Step 4: `download/collections.py`** (44 miejsca `raise ValidationError`):
  `require_collection_product`, `validate_collection_request` (wymagane i niedozwolone opcje:
  `product`, `country`, `teryt`/`ku`/`sheet`/`bbox`/`geometry`, `level`, `format`, `network`,
  `lod`, `year`, `scale`, `sheet_system`, `horizontal_crs`). Test RED: wiersz na kazda klase
  komunikatu (min. brak `product` grupy z `allowed` = produkty grupy, zly `format` z `allowed`
  formatow produktu, opcja niedozwolona dla produktu -> `option` tej opcji, `one_of` obszaru ->
  `options`). Commit: `feat(errors): option i allowed w download_collection i check_collection`
- [x] **Step 5: `landcover/manager.py` i `hydrology/hsg.py`:** `require_landcover_product`
  (`allowed == LANDCOVER_PRODUCTS`), `validate_landcover_request`, `validate_soil_request`
  (`property`, `depth`, `stat`, `output_dir`, obszar), `validate_hsg_request` (`depth` z
  `allowed` = przedzialy glebokosci, obszar). Test RED: wiersze dla `download_landcover`,
  `download_soil`, `calculate_hsg`. Commit: `feat(errors): option i allowed w land cover, SoilGrids i HSG`
- [x] **Step 6: odczyt magazynu i projekt.**
  - `kartograf/store.py`: `_validated_segment` -> `option="segment"`; `_unit_slot` i bledy
    zarezerwowanych i zbyt dlugich nazw -> `option="units"`; `units wymaga segment` ->
    `option="units"`; `skip_versions` jako napis -> `option="skip_versions"`.
    `kartograf/project/operations.py`: `add_project_task` (`name` wzorzec, `command` z
    `allowed` = 12 komend danych), `remove_project_task` (`name`).
  - Test RED (tabela): `iter_store(root, segment="zly")` -> `segment`; `iter_store(root,
    units=["x"])` -> `units`; `iter_store(root, segment="nmt/pl_1992_1m_evrf2007", units=["versions"])`
    -> `units`; `add_project_task(dir, name="zla nazwa", ...)` -> `name`; komenda spoza `COMMANDS`
    -> `command`, `allowed` = 12 komend. `tests/test_store_api.py` i `tests/test_project_api.py`
    zostaja zielone (tekst bez zmian).
  Commit: `feat(errors): option w walidatorach odczytu magazynu i operacji projektu`
- [x] **Step 7: brama zadania** (pelna); raport: liczba miejsc z `option` (`git grep -c "option="`
  przed/po), lista miejsc `ValidationError` pozostawionych bez `option` z uzasadnieniem
  (dozwolone przez spec 6.1 - bledy pliku wejsciowego i niezmienniki).

### Task T3: nowe raporty biblioteki - zrodla, warstwy, cache, odczyt magazynu (spec 5.4.6-5.4.10)

**Files:**
- Create: `kartograf/source_info.py`, `kartograf/cache_info.py`, `kartograf/store_documents.py`,
  `tests/test_source_info.py`, `tests/test_cache_info.py`, `tests/test_store_documents.py`
- Modify: `kartograf/__init__.py` (eksporty), `tests/test_public_api.py`, `tests/test_json_contract.py`
- NIE zmieniaj `kartograf/cli/**` (cutover w T5); logika zostaje w CLI do T5 i jest
  zdublowana tylko na ten czas.

- [x] **Step 1: `list_sources` i `list_layers` (`kartograf-sources/1`, `kartograf-layers/1`).**
  - Test RED (`tests/test_source_info.py`; RED = `ModuleNotFoundError`):
    `test_every_registered_source_of_a_group_is_listed_once` (suma `sources[].key` po 11
    grupach = klucze rejestru dla produktow tych grup, bez powtorzen);
    `test_select_names_the_options_that_choose_the_source` (`pl.gugik.nmt_1m`: `{"product":
    "nmt", "country": "pl", "resolution": "1m", "vertical_crs": ["EVRF2007", "KRON86"]}`;
    ortofotomapa i kolekcje: opcje wymagane do wyboru; CORINE: `year` jako lista);
    `test_select_options_are_arguments_of_the_group_function` (klucze `select` naleza do
    argumentow `download_data`/`download_collection`/`download_landcover`/`download_soil` danej
    grupy); `test_source_fields` (`license.id`, `auth == "clms_oauth"` dla CORINE,
    `update_signals` z kanalow); `test_unknown_group_and_product_are_input_errors` (`option="group"`
    z `allowed` = 11 grup, `option="product"`); `test_list_sources_is_offline_and_writes_nothing`
    (atrapa sieci z conftest + `tmp_path` bez nowych plikow); `test_list_layers_bdot10k`,
    `test_list_layers_corine_years_and_data`, `test_list_layers_bdoo_classes`,
    `test_list_layers_soil_properties_depths_statistics`,
    `test_list_layers_landcover_requires_product` (`option="product"`);
    `test_documents_are_registered_with_spec_keys` (klucze wg specu 5.4.6-5.4.7).
  - Implementacja wg "Decyzje implementacyjne" 5: `SourceInfo`, `SourceList`, `LayerList` jako
    `Document` (`kartograf-sources/1`, `kartograf-layers/1`); logika z `cli/groups/*.py`
    (`_source_choice`, `_product_flag`, `_national_file_crs`, `add_list_sources` :50),
    `cli/landcover_cmd.py::cmd_landcover_list_layers` :41, `cli/soil_cmd.py::cmd_soil_list_layers` :76;
    `list_sources(*, group, product=None)`, `list_layers(*, group, product=None)`.
  - Kontrola jednorazowa (skrypt poza repo): dla kazdej z 11 grup porownaj wiersze tabeli z
    `before/text/00x_<grupa>_list-sources.json` (KLUCZ, NAZWA, KRAJ, DOSTAWCA, KATALOG, WYBOR)
    z `list_sources(group=...)`, skladajac `select` z powrotem we flagi (`--opcja wartosc`,
    lista -> `a|b`, kolejnosc kluczy); porownaj tez warstwy z `before/text/*list-layers*`.
    Oczekiwane: 0 roznic; wynik (liczba wierszy) do opisu commita. T5 powtorzy to bajtowo na
    prawdziwym CLI.
  - Weryfikacja: `$PY -m pytest tests/test_source_info.py -q`; brama kroku.
  Commit: `feat(api): list_sources i list_layers - zrodla i warstwy jako dokumenty (kartograf-sources/1, -layers/1)`
- [x] **Step 2: `get_cache_info` i `clear_cache` (`kartograf-cache/1`).**
  - Test RED (`tests/test_cache_info.py`; `monkeypatch.chdir(tmp_path)`):
    `test_info_without_a_database_does_not_create_it` (`exists False`, `size_bytes None`,
    `entries None`, `action == "info"`, `cleared None`, `path == <cwd>/.kartograf_cache.db`
    bezwzgledna, plik nie powstaje); `test_info_counts_entries` (klucze `records, campaigns, teryt,
    sheets, index_areas, atom_feeds` z `MetadataCache.stats()`); `test_clear_empties_the_cache`
    (`action == "clear"`, `cleared True`, `entries None`, kolejne `info` pokazuje 0);
    `test_clear_removes_an_unreadable_file_with_wal_and_shm` (`removed_unreadable True`, brak
    `-wal`, `-shm`); `test_clear_never_removes_a_locked_database` (baza zablokowana przez inne
    polaczenie SQLite -> `CacheError`, plik zostaje); `test_info_of_an_unreadable_database_is_cache_error`
    (`hint` z `DEFAULT_HINT`).
  - Implementacja: logika `cmd_cache` z `cli/cache_cmd.py` (:12-99: `_unreadable_message`,
    `_remove_unreadable`, `stats`, `clear`); `open_cache(True, force=False, on_notice=...)`;
    bledy jako `CacheError` z tekstem dzisiejszych linii `Error:` (bez prefiksu).
  - Weryfikacja: `$PY -m pytest tests/test_cache_info.py tests/test_metadata_cache.py -q`.
  Commit: `feat(api): get_cache_info i clear_cache jako dokument kartograf-cache/1`
- [x] **Step 3: dokumenty odczytu magazynu (`kartograf-store-overview/1`, `-store-entries/1`,
  `-store-sidecar/1`).**
  - Test RED (`tests/test_store_documents.py`; magazyn budowany jak w `tests/test_store_api.py`):
    `test_describe_store_lists_segments_with_info`; `test_describe_store_missing_output_dir_is_oserror`
    (kontrakt ADR-045: brak magazynu to `OSError`, nie pusty magazyn);
    `test_entries_limit_and_truncated` (3 wpisy, `limit=2` -> 2 i `truncated True`, `limit=3` ->
    `truncated False`); `test_entries_require_segment_and_a_positive_limit` (`option="segment"`,
    `option="limit"` dla `0` i ujemnego); `test_unit_of_a_sidecar_selects_the_same_unit_again`
    (plik krajowy z motywem: `sidecar.unit == "pl_miejscowosci"` ze `list_store_entries` ->
    `list_store_entries(..., units=[ta wartosc])` zwraca ten plik); `test_reserved_unit_option_units`
    (`versions`, `full_sheet`, `kampanie`, nazwa > 255 bajtow);
    `test_entries_document_omits_raw_and_sidecar_document_keeps_it` (`to_dict()["entries"][0]
    ["sidecar"]` bez `raw`, `read_store_sidecar(...).to_dict()["sidecar"]["raw"]` jest);
    `test_read_store_sidecar_missing_file_is_invalid_sidecar_error` (`exc.path`, kod
    `invalid_sidecar`); `test_bare_sidecar_without_schema_reads_with_schema_constant` (sidecar w
    ksztalcie `emit_sidecar`: `sidecar.schema == "kartograf-meta/1"`, `raw` bez klucza `schema`);
    `test_paths_are_absolute_for_a_relative_output_dir`.
  - Implementacja wg "Decyzje implementacyjne" 5 (`describe_store(output_dir)`,
    `list_store_entries(output_dir, *, segment, units=None, limit)`, `read_store_sidecar(path)`;
    `StoreEntries.prepare_context` ustawia `ctx.omit = {("Sidecar", "raw")}`; `skip_versions` nie
    jest wystawione).
  - Weryfikacja: `$PY -m pytest tests/test_store_documents.py tests/test_store_api.py -q`.
  Commit: `feat(api): describe_store, list_store_entries i read_store_sidecar - dokumenty odczytu magazynu`
- [x] **Step 4: eksporty, kontrakt, brama.**
  - `kartograf/__init__.py`: nowe nazwy (`list_sources`, `SourceList`, `list_layers`, `LayerList`,
    `get_cache_info`, `clear_cache`, `CacheInfo`, `describe_store`, `list_store_entries`,
    `read_store_sidecar`, `StoreOverview`, `StoreEntries`, `StoreSidecar`) w `__all__` (docstring
    modulu aktualizuje T8); `tests/test_public_api.py::test_document_functions_are_keyword_only`
    (nowe funkcje maja argumenty tylko nazwane, z wyjatkiem `describe_store(output_dir)`,
    `list_store_entries(output_dir, *, ...)`, `read_store_sidecar(path)`); wiersze dokumentow T3 w
    `tests/test_json_contract.py` (klucze wg specu 5.4.6-5.4.10; `StoreEntries`: `schema, output_dir,
    segment, units, limit, truncated, entries`).
  - **Brama zadania i toru** (pelna, `scripts/gate.sh`). Raport toru do koordynatora: hashe
    commitow, liczby bramy, lista nazw z K2 (Tor A), odchylenia. **= S2** (koordynator merguje A do
    `feat/agent-interface`; B robi merge przed T4d).
  Commit: `feat(api): eksporty dokumentow T3 i kontrakt kluczy kartograf-*/1`

---

## Fala 1, Tor B (katalog i deklaracje): T4a-T4d

Worktree `../agent-interface-b`, galaz `feat/agent-interface-b`. Kolejnosc toru: T4a Step 1-2
(niezalezne od K1) -> T4b Step 1 deklaracje `elevation`/`imagery` (czyste dane) -> **[K1:
`git merge feat/agent-interface`]** -> T4a Step 3-4 -> T4b Step 2 (testy rownowaznosci) ->
T4c -> **[S2: `git merge feat/agent-interface`]** -> T4d. Tor B nie edytuje niczego poza
`kartograf/catalog/**`, `kartograf/sheet_info.py` i swoimi testami; `kartograf/cli/**` jest
zamrozone (stary parser jest wzorcem porownania, stage 1 migracji D7).

### Task T4a: model deklaracji, katalog i parser z deklaracji

**Files:**
- Create: `kartograf/catalog/{__init__,spec,shared,kinds,formatting,model,build,cliparser}.py`,
  `kartograf/catalog/commands/__init__.py`, `tests/test_catalog.py`, `tests/test_catalog_parser.py`,
  `tests/test_catalog_declarations.py`, `tests/test_catalog_formatting.py`

- [x] **Step 1: typy deklaracji, parametry wspolne, rodzaje (bez K1).**
  - Test RED (`tests/test_catalog_declarations.py`, `tests/test_catalog_formatting.py`; RED =
    `ModuleNotFoundError: kartograf.catalog`): `test_param_derives_flag_and_argument_from_name`
    (`Param("vertical_crs", "str")` -> flaga `--vertical-crs`, argument `vertical_crs`; `flag=None` =
    tylko API, `argument=None` = tylko CLI); `test_providers_are_called_late` (dostawca `allowed` i
    `description` nie jest wolany przy tworzeniu `Param`/`Command` ani przy imporcie modulu, tylko
    przez `resolve`); `test_shared_param_can_be_overridden` (`dataclasses.replace` zmienia
    `description`, `allowed`, `required`); `test_required_needs_an_api_argument` (`required=True` przy
    `argument=None` = `ValueError`: spec 8.3 pkt 5); `test_kinds_parse_like_the_cli_helpers`
    (`parse_bbox_arg`, `parse_per_country`, `layer_codes` daja te same wyniki i te same teksty
    bledow co `kartograf.cli._args` - test przejsciowy, usuwany w T5 razem z dublem).
  - Implementacja: `spec.py` (frozen dataclasses `Param`, `Command`, `Group`, `Constraint`,
    `Example`; pola `Param` = `ParamInfo` + pola tylko CLI `dest`, `metavar`, `normalize`,
    `exclusive`, `choices`, `nargs` wg spec 8.1 i 8.3; wartownik `AUTO`; typ `Kind` = osiem rodzajow
    `OptionKind` + `plan`, `options`); `shared.py` (parametry wspolne: obszar `sheet`, `bbox`,
    `bbox_crs`, `geometry`, `layer`; `product`, `country`, `output_dir`, `workers`, `quiet`, `json`,
    `check_updates`, `upgrade`, `force`, `plan`, `update`; opisy i sekcje z `cli/_args.py`:
    `BBOX_HELP`, `SELECTION_TITLE`, `PRODUCT_TITLE`, `OUTPUT_TITLE`, `add_update_flags`,
    `add_area_flags`); `kinds.py` (kopie `parse_bbox_arg`, `parse_per_country`, `layer_codes`);
    `commands/__init__.py` (`declared()` zbiera `COMMANDS` i `GROUPS` z modulow pakietu po nazwie, jak
    `register_groups`); `__init__.py` na tym etapie bez eksportow.
  - Weryfikacja: `$PY -m pytest tests/test_catalog_declarations.py tests/test_catalog_formatting.py -q`;
    brama kroku.
  Commit: `feat(catalog): typy deklaracji komend i parametry wspolne (D7)`
- [x] **Step 2: kanoniczna linia komendy (`formatting.py`).**
  - Test RED (`tests/test_catalog_formatting.py`, deklaracje syntetyczne):
    `test_flags_follow_declaration_order`; `test_bbox_omits_the_default_crs_flag` (`--bbox-crs X`
    pomijane, gdy `X == cli_default`; inny uklad zostaje); `test_per_country_forms` (`v` albo
    `pl=v,cz=w`); `test_str_list_joined_with_commas`; `test_path_is_shell_quoted` (`shlex.quote`);
    `test_flag_kind_prints_the_bare_flag_and_false_none_are_omitted`;
    `test_run_options_append_output_as_short_flag` (`run={"output_dir": "./data"}` -> `-o ./data`).
  - Implementacja: `format_command_line(command, options, run=None) -> str` (spec 8.7:
    `kartograf <grupa> <komenda> ...`).
  Commit: `feat(catalog): format_command_line - kanoniczna linia komendy z opcji`
- [x] **Step 3: dokument katalogu (`model.py`, `build.py`) - PO K1.**
  - Test RED (`tests/test_catalog.py`, deklaracje syntetyczne przez `build_catalog`):
    `test_catalog_document_keys` (klucze `schema, kartograf_version, language, groups, commands,
    exit_codes, errors, schemas` - dokladna kolejnosc; `kartograf-catalog/1` jest w `SCHEMAS`);
    `test_default_view_has_no_params` (`params`, `constraints`, `examples` = `None`);
    `test_command_view_has_params_constraints_examples`; `test_group_filter_and_unknown_group`
    (`ValidationError`, `option="group"`, `allowed` = grupy; `command` nieznana: `option="command"`);
    `test_params_flag_overrides_the_default` (`params=True` dla widoku ogolnego, `False` nawet
    dla `command`); `test_supports_check_is_derived` (`supports_check == (check_function is not
    None)` i `check_result_schema` ustawione razem); `test_exit_codes_and_errors_are_the_library_tables`
    (`exit_codes`/`errors` rowne `EXIT_CODES`/`ERROR_CODES`); `test_schemas_list_produced_by`
    (kolejnosc `SCHEMAS`); `test_full_catalog_is_built_once` (ten sam obiekt przy kolejnych
    wywolaniach, filtry to widoki); `test_provider_values_reach_the_document` (dostawca
    `allowed` -> `ParamInfo.allowed`).
  - Implementacja: `model.py` (`Catalog`, `GroupInfo`, `ProductInfo`, `CommandInfo` (z
    `supports_check`, bez `check_tool`), `ParamInfo`, `ConstraintInfo`, `ExampleInfo`, `ExitCodeInfo`,
    `ErrorCodeInfo`, `SchemaInfo` jako `Document`; spec 8.1); `build.py`:
    `build_catalog(commands, groups, *, params=None, group=None, command=None)`, `get_catalog(*,
    group=None, command=None, params=None)`, `data_commands()` (komendy z `project_task`, z
    parametrami); `ProductInfo` liczone z rejestru (`sources_for`), nie z `list_sources`.
  - Weryfikacja: `$PY -m pytest tests/test_catalog.py -q`; brama kroku.
  Commit: `feat(catalog): dokument kartograf-catalog/1 i get_catalog (D7, D9)`
- [x] **Step 4: parser z deklaracji (`cliparser.py`) - PO K1.**
  - Test RED (`tests/test_catalog_parser.py`, deklaracje syntetyczne): `test_actions_follow_params`
    (flagi, `dest`, `type`, `choices` tylko gdy `choices=True`, `default`, `nargs`);
    `test_flags_are_never_required` (brak flagi nie konczy parsowania - brak zglasza biblioteka);
    `test_normalize_lower_upper_strip`; `test_exclusive_group` (`--check-updates` razem z
    `--upgrade` = blad); `test_sections_and_epilog_in_help` (tytuly z `section`, przyklady w
    `epilog`); `test_usage_error_mode` (`usage_errors=True`: nieznana flaga, brak argumentu
    pozycyjnego i wartosc spoza `choices` = `UsageError`; domyslnie `SystemExit(2)` z `usage:` na
    stderr); `test_negative_bbox_values_are_joined` (`--bbox -447000,...`);
    `test_leaf_parsers_carry_command_id_and_groups_carry_group_parser`;
    `test_removed_command_and_unknown_flag_texts_equal_the_old_parser` (te same wyniki
    `removed_command_error`, `_unknown_text` co `kartograf.cli._parser` na zestawie wejsc -
    test przejsciowy do T5); `test_version_action_prints_version`.
  - Implementacja wg "Decyzje implementacyjne" 6: `build_parser(commands, groups, *, prog="kartograf",
    usage_errors=False)`; logika `_Parser`, `_HelpFormatter`, `_LazyVersionAction`, `_REMOVED_COMMANDS`,
    `removed_command_error`, `_UNKNOWN_HINTS`, `_unknown_text`, `_join_bbox_values`,
    `parse_command_line` skopiowana z `cli/_parser.py` (stary plik zostaje do T5); komunikaty bledow
    bez zmian.
  - Weryfikacja: `$PY -m pytest tests/test_catalog_parser.py -q`; brama kroku.
  Commit: `feat(catalog): parser CLI budowany z deklaracji (D7, stage 1)`

### Task T4b: deklaracje `elevation` i `imagery`

**Files:** Create: `kartograf/catalog/commands/{elevation,imagery}.py`; testy w
`tests/test_catalog_parser.py` i `tests/test_catalog_declarations.py`. Opisy komend i flag przenos
DOSLOWNIE z `kartograf/cli/groups/{elevation,imagery}.py` (komendy `download`, `list-sources`,
`availability`; sekcje `--help`, przyklady `epilog`, `metavar`, `normalize`); wartosci z rejestru jako
dostawcy (`allowed`, teksty z `download/options.py`: `resolution_text`, `vertical_crs_text`,
`format_text`, `product_choices`, `country_choices`, `cz_resolution_help`), nigdy kopie list.

- [x] **Step 1: deklaracje i testy deklaracji (bez K1 - korzystaja tylko z `spec.py`, `COMMANDS` i
  istniejacego kodu).** `elevation download` (30 parametrow: 29 z flaga CLI i `update`, w kolejnosci flag `--help`; `task: true`
  dla opcji, ktore sa kluczami `COMMANDS["elevation download"].options`; `argument` wg sygnatury
  `download_data`; ograniczenia: `one_of` (`sheet`, `bbox`, `geometry`), `requires` (`cutout` ->
  `horizontal_crs`), `applies_to` dla opcji ograniczonych do produktow; przyklady PL i CZ jako opcje
  zadania), `elevation list-sources`, `elevation availability` (`function: check_availability`,
  parametr `json` wlasny jak dzis), `imagery download`, `imagery list-sources`; parametr `sheet` z
  `accepts` (systemy godel akceptowane przez komende, wg tekstu `--help` flagi).
  `function`/`check_function`/`result_schema`/`check_result_schema`/`tool` wg specu 8.1 i 9.3
  (`elevation_download`, `imagery_download`, `elevation_availability`, `list_sources`).
  - Test RED (`tests/test_catalog_declarations.py`, parametryzowane po `declared()`, wiec obejmuja tez
    T4c i T4d bez edycji pliku): `test_task_options_equal_manifest_options[<komenda>]`
    (`{p.name: p.kind for p in params if p.task} == dict(COMMANDS[komenda].options)`; kolejnosc
    pomijana - spec 8.3 pkt 7); `test_examples_pass_task_validation[<komenda>]` (kazdy przyklad:
    `COMMANDS[...].validate(tmp, options_from_json(...))` bez bledu - jak
    `tests/test_cli_help.py::test_help_example_is_a_valid_task`); `test_examples_cover_pl_and_cz`
    (kazda komenda danych: >= 1 przyklad PL i, gdy produkt ma CZ, >= 1 CZ);
    `test_allowed_comes_from_a_provider_not_a_copy` (parametry `product`, `country`, `resolution`,
    `vertical_crs`, `format`, `model`, `scale`, `sheet_system`, `bbox_crs`: `allowed` to dostawca, a
    wartosc rowna wynikowi funkcji rejestru); `test_texts_are_ascii_and_summary_is_short` (`summary`
    <= 120 znakow, ASCII wszystkich opisow); `test_constraints_reference_declared_params`.
    Dodatkowo `test_elevation_and_imagery_commands_are_declared` (zbior zadeklarowanych id zawiera
    `elevation download`, `elevation list-sources`, `elevation availability`, `imagery download`,
    `imagery list-sources`). RED: ten test (`declared()` jest puste, wiec testy parametryzowane
    zbieraja sie dopiero po dodaniu modulow `commands/elevation.py` i `commands/imagery.py`).
  - Weryfikacja: `$PY -m pytest tests/test_catalog_declarations.py -q`; brama kroku.
  Commit: `feat(catalog): deklaracje komend elevation i imagery z testami deklaracji (D7)`
- [x] **Step 2: testy rownowaznosci parsera (PO K1; parametryzowane po `declared()`, wiec obejmuja tez T4c i T4d).**
  - Test RED (`tests/test_catalog_parser.py`, stary parser z `kartograf.cli._parser.create_parser()`):
    `test_new_parser_equals_old_parser[<komenda>]` - dla kazdej zadeklarowanej komendy-liscia
    parser z `build_parser(...)` zbudowany z deklaracji BEZ parametru `json` (z wyjatkiem
    `elevation availability`) i bez komendy `catalog`, przy `COLUMNS=100`: te same akcje (opcje,
    `dest`, nazwa typu, `choices`, `default`, `nargs`, `required`, `const`, `metavar`, `help`, sekcja,
    grupa wykluczajaca) i **identyczny `format_help()`**; `test_group_help_equals_old[<grupa>]`;
    `test_example_command_lines_round_trip` (`format_command_line` -> `build_parser().parse_args` daje
    te same opcje zadania po konwersji `kinds`). RED: roznica tekstu `--help` albo akcji ujawniona
    przez test (pierwsze uruchomienie moze byc zielone tylko wtedy, gdy deklaracje sa wierne - wtedy
    dowodem RED jest celowo zepsuty opis w deklaracji: zmien jeden znak, zobacz czerwony test, cofnij).
  - Weryfikacja: `$PY -m pytest tests/test_catalog_parser.py -q`; jednorazowo (poza repo) `diff`
    `format_help()` z `before/help/elevation_download.txt` i innych (kontrola niezalezna od testu);
    brama kroku.
  Commit: `test(catalog): rownowaznosc parsera z deklaracji i starego parsera (D7, stage 1)`

### Task T4c: deklaracje `landcover`, `soil` i siedmiu grup kolekcji

**Files:** Create: `kartograf/catalog/commands/{landcover,soil,boundaries,cadastre,models3d,hydro,names,maps,geodesy}.py`.
Zrodlo tekstow: `kartograf/cli/groups/{landcover,soil,_collection,boundaries,cadastre,models3d,hydro,names,maps,geodesy}.py`
(wspolny wzorzec grup kolekcji z `_collection.py:add_collection_commands` zapisz jako funkcje
budujaca `Command`y w `catalog/commands/_collection.py` - modul pomocniczy z prefiksem `_`, pomijany
przez `declared()`).

- [x] **Step 1: testy (RED).** (`tests/test_catalog_declarations.py`)
  `test_landcover_soil_and_collection_commands_are_declared` (zbior zadeklarowanych id zawiera
  `landcover download|list-sources|list-layers`, `soil download|hsg|list-sources|list-layers` oraz
  `<grupa> download|list-sources` dla `boundaries`, `cadastre`, `models3d`, `hydro`, `names`, `maps`,
  `geodesy`: razem 21 komend); `test_collection_groups_share_the_declared_pattern` (siedem grup: parametry
  wspolne `product`, `country`, obszar, `output_dir`, `workers`, `check_updates`/`upgrade`/`force`/`plan`;
  roznice tylko tam, gdzie dzis `--help` je ma: `hydro` bez `teryt`/`ku`/`sheet`);
  `test_soil_hsg_summary_is_cli_and_api` (`summary`: flaga `--summary`, argument `summary`).
  Parametryzowane testy z T4b (Step 1 i Step 2) obejmuja nowe komendy bez edycji (`declared()`).
  RED: pierwszy z powyzszych (brak modulow).
- [x] **Step 2: deklaracje** wszystkich komend tych grup; `function`/`check_function`:
  `download_landcover`/`check_landcover`, `download_soil`/`check_soil`, `calculate_hsg`/`check_hsg`
  (`soil hsg`: dodatkowy parametr tylko CLI `summary` i jego odpowiednik API `summary`),
  `download_collection`/`check_collection`; `list-sources` -> `list_sources` (parametr `group` tylko API z
  jedna dozwolona wartoscia), `list-layers` -> `list_layers`; `soil download` i `soil hsg`: `result_schema`
  `kartograf-download/1`, narzedzia MCP `soil_download`, `soil_hsg`. Opisy przenos doslownie (test
  rownowaznosci `format_help()` z T4b Step 2 jest bramka).
  Weryfikacja: `$PY -m pytest tests/test_catalog_declarations.py tests/test_catalog_parser.py -q`;
  **brama zadania** (pelny `pytest` w worktree B: stary CLI nietkniety, wiec 5339 testow nadal zielone).
  Commit: `feat(catalog): deklaracje landcover, soil i siedmiu grup kolekcji`

### Task T4d: `project`, `cache`, `parse`, `catalog`, komendy tylko-API, podpowiedzi, `sheet_info`

**Files:**
- Create: `kartograf/catalog/commands/{project,misc}.py`, `kartograf/catalog/hints.py`,
  `kartograf/sheet_info.py`, `tests/test_sheet_info.py`
- Modify: `kartograf/catalog/__init__.py` (eksport `get_catalog`, `data_commands`),
  `tests/test_catalog.py`, `tests/test_catalog_declarations.py`

- [x] **Step 0: S2.** `git merge feat/agent-interface` (po komunikacie koordynatora, ze A jest scalone).
  Brama zielona na wyniku przed dalsza praca.
- [x] **Step 1: `describe_sheet` i `find_sheets` (`kartograf-sheet/1`, `kartograf-sheets/1`).**
  - Test RED (`tests/test_sheet_info.py`; RED = `ModuleNotFoundError: kartograf.sheet_info`):
    `test_describe_pl1992_sheet` (`N-34-130-D-d-2-4`: `system == "pl1992"`, `country == "PL"`,
    `scale == "1:10000"`, `components`, `crs == "EPSG:2180"`, `bounds` = `SheetParser(...).get_bbox`);
    `test_describe_pl2000_and_cz_codes` (`6.179.12.20`, `CTES96` (SM5: `bounds None`), `302_5550`
    (TM33), arkusz ZTM); `test_hierarchy_children_descendants` (godlo PL: hierarchia do 1:1000000,
    potomkowie, `descendants="1:10000"` bez ucinania; dla godla CZ `option` = `hierarchy`/`children`/
    `descendants`); `test_bad_code_is_parse_error_with_option_sheet`; `test_describe_matches_the_cli_text_facts`
    (te same fakty co dzisiejszy tekst: skala, uklad, obwiednia - porownanie z wynikiem
    `kartograf.cli.parse_cmd.format_sheet_info` dla zestawu godel; test przejsciowy do T5);
    `test_commands_follow_the_accepts_of_the_catalog` (dla kazdego z pieciu systemow godel `commands` =
    komendy, ktorych parametr `sheet` ma ten system w `accepts`, w kolejnosci katalogu; dla
    `N-34-130-D-d-2-4` literal ze specu 5.4.4); `test_find_sheets_equals_library_functions`
    (`find_sheets(bbox=..., scale=..., sheet_system=...)` = `find_sheets_for_bbox`/
    `find_sheets_for_geometry`; `sheets`, `count`, `request`; dokladnie jedno z `bbox`/`geometry`;
    `scale` i `sheet_system` wymagane: `option`).
  - Implementacja: `SheetInfo`, `describe_sheet(sheet, *, hierarchy=False, children=False,
    descendants=None)`, `SheetList`, `find_sheets(*, bbox=None, geometry=None, layer=None, scale,
    sheet_system)` (logika z `cli/parse_cmd.py`: `format_cz_sheet` :25, `format_sheet_info` :65,
    `format_hierarchy` :99, `format_children` :125, `format_descendants` :158 - tu jako dane, nie
    tekst); `SheetInfo.commands` z `get_catalog(params=True)` (`ParamInfo.accepts` parametru `sheet`).
  Commit: `feat(api): describe_sheet i find_sheets - godla jako dokumenty (kartograf-sheet/1, -sheets/1)`
- [x] **Step 2: deklaracje `project`, `cache`, `parse`, `catalog` i komend tylko-API.**
  Test RED (`tests/test_catalog_declarations.py`): `test_project_cache_parse_catalog_and_api_only_commands_are_declared`
  (zbior id zawiera `project init|add|remove|download|status|verify`, `cache stats|path|clear`, `parse`,
  `catalog`, `find_sheets`, `store_overview`, `store_entries`, `store_sidecar`: 16 komend; RED: brak modulow
  `commands/project.py` i `commands/misc.py`). Deklaracje:
  `project init|add|remove|download|status|verify` (`project_task: false`; `function` wg specu 7.2 i
  9.3: `init_project`, `add_project_task`, `remove_project_task`, `download_project`,
  `get_project_status`, `verify_project`; `project download`: `check_function: check_project`,
  `supports_check: true`, narzedzia `project_init`, `project_add` (parametry `command` z `allowed` =
  12 komend danych i `options` rodzaju `options`), `project_remove`, `project_download`,
  `project_status`, `project_verify`; narzedzie sprawdzenia `project_check_updates` jest w T6),
  `cache stats|path|clear` (`get_cache_info`, `clear_cache`; `clear`: `destructive: true`),
  `parse` (`describe_sheet`, narzedzie `parse_sheet`), `catalog` (`get_catalog`, narzedzie
  `get_catalog`; parametry `group`, `command` pozycyjne, `params`, `json`), komendy tylko-API z
  `cli: null`: `find_sheets`, `store_overview`, `store_entries`, `store_sidecar`
  (`describe_store`, `list_store_entries`, `read_store_sidecar`; `store_entries`: `segment` i `limit`
  wymagane). Parametr `check_updates` komendy `project download` nalezy do deklaracji jak w
  `kartograf/cli/groups/project.py`. Testy parametryzowane po `declared()` (T4b) obejmuja je od razu.
  Commit: `feat(catalog): deklaracje project, cache, parse, catalog i komend tylko-API`
- [x] **Step 3: `hints.py` (skladnik (b) hintu bledu).**
  - Test RED (`tests/test_catalog.py`): `test_example_for_prefers_an_example_using_the_option`
    (`example_for("elevation download", "vertical_crs")` -> `("--vertical-crs", <command_line
    przykladu z vertical_crs>)`); `test_example_for_falls_back_to_the_first_example`;
    `test_example_for_unknown_command_or_option` (`(None, None)` lub `(None, <pierwszy przyklad>)`,
    bez wyjatku); `test_example_command_line_is_valid` (wynik parsuje sie prawdziwym parserem).
  - Implementacja: `example_for(command, option) -> tuple[str | None, str | None]` (flaga z katalogu,
    gdy parametr istnieje; `command_line` = `format_command_line` przykladu). Wpiecie w
    `error_report` robi T5.
  Commit: `feat(catalog): example_for - skladnik (b) podpowiedzi bledu z przykladow katalogu`
- [x] **Step 4: testy zamykajace tor (PO S2).**
  - `tests/test_catalog.py`: `test_every_old_leaf_command_is_declared` (36 lisci starego parsera =
    zadeklarowane komendy z `cli`; plus `catalog`; razem 37 lisci nowego parsera);
    `test_data_commands_are_the_twelve_in_COMMANDS_order` (KB-1, `data_commands()` = klucze
    `COMMANDS`, z parametrami, `project_task`); `test_result_schemas_are_registered` (kazdy
    `result_schema` i `check_result_schema` w `SCHEMAS`); `test_catalog_filters_and_errors` (spec 8.5);
    `test_constraint_violations_raise_validation_error_naming_the_option` - dla kazdego ograniczenia
    typu `one_of`, `requires`, `excludes`, `applies_to` test wyprowadzony z przykladu komendy (spec
    8.4: `one_of` - usun wszystkie `params` i dodaj dwa; `requires` - usun wymagane; `excludes` -
    dodaj wykluczone; `applies_to` - dodaj opcje przy produkcie spoza `when`): `COMMANDS[...].validate`
    rzuca `ValidationError`, a `option`/`options` wskazuje opcje ograniczenia; `required_when` bez
    testu generowanego (dokumentacja); `test_catalog_does_not_import_cli_or_mcp` (importy
    `kartograf.catalog.*` w czystym procesie nie ladowaly `kartograf.cli` ani `mcp`).
  - Eksporty `kartograf.catalog.__init__`: `get_catalog`, `data_commands`.
  - **Brama zadania i toru** (pelna). Raport toru: hashe, liczby bramy, liczba komend/parametrow
    w katalogu, lista nazw K2 (Tor B), odchylenia, **lista roznic tekstu `--help` ze zrzutu
    (spodziewana: brak)**.
  Commit: `test(catalog): kompletnosc deklaracji, ograniczenia i schematy wynikow (D7, D10)`

---

## Fala 2: T5 - CLI na katalogu, `--json`, warstwa komend, kody wyjscia

Jeden wlasciciel, worktree integracyjny (`feat/agent-interface`) po scaleniu A i B przez koordynatora.
Kazdy krok konczy sie zielona brama (stary i nowy parser nigdy nie sa jednoczesnie zrodlem prawdy
dluzej niz do Step 4). Zrzut przed/po (Dodatek A): `before` z T0, `after` zdejmowany po Step 4, Step 8
i Step 10.

### Task T5: integracja, KB-2..KB-5, parser z katalogu, `--json`, kody wyjscia

**Files:**
- Create: `kartograf/commands.py`, `kartograf/cli/_handlers.py`, `kartograf/cli/catalog_cmd.py`,
  `kartograf/cli/_json.py`, `tests/test_commands_layer.py`, `tests/test_cli_handlers.py`,
  `tests/test_cli_json.py`, `tests/test_cli_errors.py`, `tests/test_catalog_kinds.py`
- Modify: `kartograf/catalog/{kinds,cliparser,build}.py`, `kartograf/cli/{commands,_parser,_args,download_cmd,collection_cmd,landcover_cmd,soil_cmd,parse_cmd,cache_cmd,availability_cmd,project_cmd}.py`,
  `kartograf/project/{commands,operations,manifest}.py`, `kartograf/error_report.py`,
  `kartograf/__init__.py`, istniejace testy z 12.10-12.11
- Delete (Step 9): `kartograf/cli/groups/**`, flagi w `kartograf/cli/_args.py`, `*_task_arguments`

- [x] **Step 0: integracja i kontrola kontraktu K2.** Po scaleniu A i B: `scripts/gate.sh` w calosci;
  wszystkie roznice integracyjne naprawiaj commitami `fix(...)` (tresc opisuje przyczyne).
  - Test RED (`tests/test_catalog.py`): `test_catalog_functions_exist_and_match_signatures` (spec 12.5 c:
    kazda nazwa `function` i `check_function` jest w `kartograf.__all__` i wywoluje sie; kazdy `argument`
    komendy jest parametrem tej funkcji; parametr funkcji bez wartosci domyslnej jest `required` w
    katalogu; funkcje maja argumenty tylko nazwane, z wyjatkiem identyfikujacych: `describe_sheet`,
    `describe_store`, `read_store_sidecar`, `list_store_entries` i funkcje projektu z `project_dir`).
    RED: `describe_sheet`, `find_sheets`, `get_catalog` nie sa jeszcze w `__all__`.
  - Implementacja: eksporty w `kartograf/__init__.py` (`get_catalog`, `data_commands`, `Catalog`,
    `CommandInfo`, `ParamInfo`, `describe_sheet`, `SheetInfo`, `find_sheets`, `SheetList`); popraw
    rozbieznosci deklaracji i sygnatur ujawnione przez test.
  Commit: `feat(api): eksporty katalogu i sheet_info; test kontraktowy katalog <-> funkcje API (spec 12.5 c)`
- [x] **Step 1: konwersja rodzajow w `catalog/kinds.py` (bez zmiany zachowania).**
  - Test RED (`tests/test_catalog_kinds.py`): `test_convert_arguments_by_kind` (`bbox` + `bbox_crs` ->
    `BBox`; `path` -> `Path` wzgledem `base_dir`; `per_country` napis albo `{pl, cz}`; `str_list` ->
    krotka; `flag` `True`; klucz spoza deklaracji = `ValidationError(option=klucz)`);
    `test_options_round_trip` (przeniesiony `test_options_roundtrip`: `options_to_json` ->
    `check_options_json` -> `options_from_json`); `test_check_options_json_errors` (przeniesione
    przypadki z `tests/test_project_commands.py`). RED: `ImportError: cannot import name 'convert_arguments'`.
  - Implementacja: `options_to_json(kinds, options)`, `check_options_json(kinds, data)`,
    `options_from_json(kinds, data, *, base_dir)`, `convert_arguments(kinds, data, *, base_dir=None)`
    w `catalog/kinds.py` (z `project/commands.py` :666, :712, :746; `kinds` = `Mapping[nazwa, Kind]`);
    `project/commands.py`, `project/operations.py`, `project/manifest.py` importuja je z `catalog`;
    `OptionKind` w `project/commands.py` staje sie aliasem `Kind`. Zaktualizuj importy w
    `tests/test_project_commands.py` (12 odwolan) i w `tests/test_catalog_declarations.py` (Tor B
    uzywa tam `options_from_json` z `project/commands.py`).
  - Weryfikacja: `$PY -m pytest tests/test_catalog_kinds.py tests/test_catalog_declarations.py
    tests/test_project_*.py -q`; brama kroku.
  Commit: `refactor(catalog): konwersja opcji zadania (options_from_json, options_to_json, check_options_json) w catalog/kinds.py`
- [x] **Step 2: warstwa komend `kartograf/commands.py` (KB-2..KB-5, O5) i podpowiedz bledu.**
  - Test RED (`tests/test_commands_layer.py`, spec 12.6; RED: `ImportError: cannot import name
    'parse_command'`): `test_parse_command_returns_only_given_options` (`"elevation download --product
    nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 -o ./data"` ->
    `CommandCall("elevation download", {"product": "nmt", "sheet": ..., "resolution": "1m",
    "vertical_crs": "EVRF2007"}, {"output_dir": "./data"})`; lista tokenow = napis);
    `test_parse_command_bbox_always_comes_with_crs` (`--bbox 1,2,3,4` -> `bbox` i `bbox_crs ==
    "EPSG:2180"` takze przy domyslnej wartosci flagi); `test_parse_command_distinguishes_given_workers`
    (`run` ma `workers` tylko gdy podano flage - zastepuje `_workers_given`);
    `test_parse_command_syntax_error_is_usage_error` (nieznana flaga, brak argumentu, wartosc spoza
    `choices`); `test_parse_command_rejects_non_data_commands` (`parse`, `elevation availability`:
    `ValidationError` z lista 12 komend, ten sam tekst co `project add`);
    `test_validate_command_is_offline_and_names_the_option` (atrapa transportu odrzuca kazde zapytanie;
    brak `vertical_crs` -> `ValidationError(option="vertical_crs")`; `output_dir=None` dziala);
    `test_format_parse_round_trip_for_every_catalog_example`
    (`parse_command(format_command(c, o, run=r)[len("kartograf "):]) == (c, o, r)`);
    `test_run_command_equals_download_data` i `test_check_command_equals_check_data` (parzystosc z
    wywolaniem funkcji na tych samych fixturach co `tests/test_download_data.py`; `plan` i `update`
    przekazane do funkcji; `check_command` zwraca `UpdatePlan`); `test_unknown_command_names_the_option`
    (`option="command"`, `allowed` = 12 komend).
  - Implementacja wg specu 8.7: `CommandCall`, `parse_command`, `validate_command`, `format_command`
    (wola `catalog.formatting.format_command_line`), `run_command`, `check_command`;
    `TaskDownload.__call__` w `project/commands.py` dostaje `plan: UpdatePlan | None` (projekt
    przekazuje `None`); eksporty w `kartograf/__init__.py`.
  - Test RED (`tests/test_errors.py`): `test_validation_hint_has_flag_and_example_from_the_catalog`
    (`error_report(ValidationError(..., option="vertical_crs", allowed=("EVRF2007", "KRON86")),
    command="elevation download").hint` = `Dozwolone wartosci --vertical-crs: EVRF2007, KRON86.
    Przyklad: kartograf elevation download ...`; bez `command` flaga = nazwa opcji, bez przykladu
    z innej komendy); implementacja: wpiecie `catalog.hints.example_for` (import leniwy wewnatrz
    funkcji) w skladniku (a) i (b) hintu w `error_report.py`.
  - Weryfikacja: `$PY -m pytest tests/test_commands_layer.py tests/test_errors.py tests/test_project_*.py
    -q`; brama kroku.
  Commit: `feat(api): parse_command, validate_command, format_command, run_command i check_command (KB-2..KB-5)`
  oraz `feat(errors): podpowiedz bledu z flaga i przykladem z katalogu (spec 6.3)`
- [x] **Step 3: komenda `kartograf catalog` (handler).**
  - Test RED (`tests/test_cli_handlers.py`, test jednostkowy handlera z `argparse.Namespace`; RED:
    `ModuleNotFoundError: kartograf.cli.catalog_cmd`): `test_catalog_text_lists_groups_commands_summaries`
    (jedna linia na komende: id, rodzaj, podsumowanie; grupy z produktami); `test_catalog_group_and_command_views`
    (`GRUPA` -> komendy grupy; `GRUPA KOMENDA` -> opis, tabela parametrow: flaga, argument API, rodzaj,
    wymagany, dozwolone wartosci, opis, przyklady); `test_catalog_params_flag_adds_params_to_group_view`;
    `test_catalog_json_is_the_library_document` (`--json`: `get_catalog(...).to_json()` bajtowo);
    `test_catalog_unknown_group_is_a_validation_error`.
  - Implementacja: `cli/catalog_cmd.py` (`cmd_catalog`; tekst z dokumentu, spec 7.4; komenda jest
    zapytaniem: bez sieci i zapisu).
  Commit: `feat(cli): kartograf catalog [GRUPA [KOMENDA]] [--params] [--json]`
- [x] **Step 4: przelaczenie `create_parser()` na parser z katalogu (D7, stage 2).**
  - Test RED (`tests/test_cli_handlers.py`): `test_every_catalog_cli_command_has_a_handler` (37 lisci:
    36 dzisiejszych i `catalog`; kazde `_command_id` ma wpis w `HANDLERS`) i
    `test_no_handler_without_a_catalog_command`. RED: `ModuleNotFoundError: kartograf.cli._handlers`.
  - Implementacja: `cli/_handlers.py` (`HANDLERS`: id komendy -> funkcja; warianty grup przez
    `functools.partial`: `cmd_download(products=...)`, `cmd_collection_download(group=...)`);
    `cli/_parser.py` zostaje cienka fasada: `create_parser()` (= `build_parser(...)` z
    `catalog.commands.declared()`), `parse_command_line`, `removed_command_error`, `_subparsers`
    reeksportowane z `catalog.cliparser` (stare cialo parsera znika z `_parser.py`);
    `cli/commands.py::_dispatch` wybiera handler po `_command_id` (jedna sciezka dla `parse`, `cache`,
    grup); `cli/groups/**` przestaja byc uzywane (usuwa je Step 9).
  - Testy przejsciowe porownujace ze STARYM parserem traca sens (`create_parser()` zwraca juz nowy):
    usun w tym samym commicie `test_new_parser_equals_old_parser`, `test_group_help_equals_old`,
    `test_removed_command_and_unknown_flag_texts_equal_the_old_parser` i `test_every_old_leaf_command_is_declared`;
    role przejmuje zrzut przed/po (ponizej) i nowy test staly (spec 12.5 a):
    `test_real_parser_matches_the_catalog` (dla kazdej komendy flagi, `dest`, `type`, `choices`,
    `default`, `nargs`, wykluczanie; kazda flaga prawdziwego parsera jest w katalogu i odwrotnie).
  - Weryfikacja: **caly `pytest` (siec bezpieczenstwa 5339 testow CLI)** i zrzut:
    `$PY <...>/baseline_dump.py <...>/after --drop-json && diff -r <...>/before <...>/after` - dozwolone
    roznice WYLACZNIE: `help/root.txt` i wpis `(root)` w `actions.json` (nowa komenda `catalog`) oraz
    pliki `catalog`; reszta (36 helpow lisci, helpy grup, akcje, 33 przebiegi tekstowe) bajtowo
    identyczna. Wynik `diff` do opisu commita.
  Commit: `refactor(cli): create_parser() z katalogu komend; handlery wybierane po id komendy (D7, stage 2)`
- [x] **Step 5: `main()` - dokument bledu, kody wyjscia, tryb JSON (D4, D5, O2).**
  - Test RED (`tests/test_cli_errors.py`, `main([...])` z przechwyceniem stdout/stderr):
    `test_input_error_exits_2_in_text_mode` (brak `--output`: `Error: --output wymagane...` na stderr,
    kod 2); `test_source_failure_exits_1` (`DownloadError`); `test_ok_false_exits_1`;
    `test_json_input_error_is_an_error_document` (`--json` + brak `--output`: stdout = `kartograf-error/1`,
    `code == "invalid_input"`, `exit_code == 2`, `details.option == "output_dir"`, `hint` z dozwolonymi
    wartosciami i przykladem komendy, `stderr == ""`); `test_json_argparse_error_is_usage_error` (nieznana
    flaga z `--json`: `usage_error`, kod 2, stdout dokument, stderr pusty);
    `test_text_usage_error_is_unchanged` (`usage:` + komunikat na stderr, kod 2);
    `test_json_parse_error_uses_invalid_sheet_code`; `test_keyboard_interrupt_is_130`
    (JSON: `interrupted`; tekst: `Error: przerwano (Ctrl-C)`); `test_oserror_is_io_error_in_json_mode`;
    `test_internal_error_in_json_mode_and_debug_reraises` (`KARTOGRAF_DEBUG=1` ponawia wyjatek);
    `test_json_flag_before_the_command_is_a_usage_error` (`kartograf --json elevation ...`);
    `test_json_mode_sets_utf8_stdout`; `test_http_retry_lines_stay_on_stderr` (D6: logger
    `kartograf.transport.http` poza kontraktem).
  - Implementacja wg "Decyzje implementacyjne" 8: `cli/_json.py` (`json_mode(argv)`, `emit_document`,
    kod wyjscia z `ok`), `main()` buduje parser z `usage_errors=True` w trybie JSON,
    `KartografError` -> `error_report(e, command=<id>)` i `e.exit_code`, `KeyboardInterrupt` -> 130,
    `OSError` -> `io_error`, inny `Exception` -> `internal_error`; w trybie tekstowym teksty `Error:`
    jak dotad, kod `e.exit_code` (2 dla `ValidationError`, `ParseError`, `UsageError`). `--plan` bez trybu
    -> `ValidationError(option="plan")`. Flaga `--json` jest w kazdej komendzie-lisciu z katalogu (shared
    param).
  - Weryfikacja: `$PY -m pytest tests/test_cli_errors.py -q`; **testy dotychczasowe z `== 1` dla
    bledow wejscia beda czerwone do Step 6** - nie commituj tego kroku osobno: Step 5 i Step 6 to
    jeden commit zielony (patrz Step 6).
- [x] **Step 6: handlery nie drukuja wlasnych `Error:` za bledy wejscia (O2).** W `kartograf/cli/*.py` jest
  ok. 40 wystapien `Error:` i 20 `return 1` (`download_cmd.py` 12/7, `cache_cmd.py` 5/3,
  `parse_cmd.py` 4/4, `soil_cmd.py` 4/2, `landcover_cmd.py` 3/2, `availability_cmd.py`,
  `collection_cmd.py`, `project_cmd.py`; `_args.py` i `commands.py` zglaszaja juz wyjatki): kazdy blad
  wejscia (brak `--output`, `--product`, zly plik planu, zle godlo, brak sciezki katalogu planu)
  zamien na `raise ValidationError(..., option=...)` (tekst bez zmian), awarie zrodla i zapisu planu
  na wyjatki bibliotek (`OSError` -> `io_error`).
  - Klasyfikacja testow (23 asercje `main([...]) == 1` i ok. 156 asercji `rc`/`code`/`exit_code`/`result == 1`,
    liczone regexem; `test_cli.py` ok. 127, `test_project_cli.py` 9, `test_cli_help.py` 4,
    `test_cli_translation.py` 6): uruchom pelny `pytest`,
    dla kazdej czerwonej asercji zdecyduj: blad wejscia (`ValidationError`, `ParseError`,
    `UsageError`) -> oczekiwany kod 2; awaria zrodla, `ok: false`, blad zapisu -> zostaje 1. Liczby
    (ile zmieniono na 2, ile zostalo 1) do opisu commita.
  Commit (Step 5 + 6 razem): `feat(cli)!: dokument kartograf-error/1 i kody wyjscia 0/1/2/130; bledy wejscia koncza CLI kodem 2` z trescia
  `BREAKING: bledy wejscia (ValidationError, ParseError, UsageError) koncza CLI kodem 2 (dzis 1);
  skrypty sprawdzajace == 1: testuj != 0 (2 = popraw dane, 1 = awaria albo ok: false)`
- [x] **Step 7: `--json` w komendach danych.**
  - Test RED (`tests/test_cli_json.py`; wspolne fixtury z `tests/test_parity*.py`):
    scenariusze zgodnosci CLI `--json` == API `to_dict()` przy zamrozonym zegarze, po normalizacji
    katalogow magazynow (`run_both`): `test_json_pl_sheet` (arkusz PL), `test_json_pl_area` (bbox),
    `test_json_collection`, `test_json_landcover`, `test_json_soil`, `test_json_hsg_with_summary`
    (`soil hsg --json --summary`: `summary` w dokumencie, bez `hsg_statistics` w CLI),
    `test_json_check_updates_plan` (`kartograf-plan/1`; `--plan PLIK` zapisuje ten sam dokument,
    linia `Info: zapisano plan` nie jest drukowana), `test_json_availability_bytes_equal_to_json`
    (bajtowo `check_availability(...).to_json()`); wlasnosci trybu: `test_json_mode_has_no_progress_and_no_notice_lines`
    (stdout = dokument, stderr pusty, komunikaty w `notices`), `test_json_ok_false_exits_1_with_the_report`
    (dokument wyniku z `ok: false`, kod 1), `test_quiet_with_json_is_allowed_and_has_no_effect`.
  - Implementacja: handlery `cmd_download`, `cmd_collection_download`, `cmd_landcover_download`,
    `cmd_soil_download`, `cmd_soil_hsg`, `cmd_availability` w trybie JSON: bez paska postepu, bez
    `on_progress`/`on_notice`, bez linii statusu; `emit_document(report_albo_plan)`; kod z `ok`;
    `calculate_hsg(..., summary=args.summary)` zamiast `hsg_statistics` w CLI (tekst: statystyki z
    `report.summary`); cykl pliku planu bez zmian poza brakiem linii `Info:` w trybie JSON.
  Commit: `feat(cli): --json w komendach danych i availability (kartograf-download/1, -plan/1, -availability/1)`
- [x] **Step 8: `--json` w komendach zapytan i zarzadzania; tekst renderowany z dokumentow.**
  - Test RED (`tests/test_cli_json.py`): test na kazda komende-lisc, ktora da sie uruchomic offline
    (parametryzowany po katalogu: `list-sources` x11, `list-layers` x2, `parse`, `cache stats|path|clear`,
    `catalog`, `project init|add|remove|status|verify|download` na projekcie w `tmp_path` z atrapa
    providera): `main([...komenda, "--json"])` -> stdout to JEDEN dokument (`json.loads` calosci),
    `schema` nalezy do `SCHEMAS`, `stderr == ""`, kod 0 (albo wg `ok`); `test_project_add_uses_parse_command`
    (`project add` odrzuca `--json`, `--workers`, `--summary`, `--check-updates` itd. jako opcje
    uruchomienia z `ValidationError`; bez `_workers_given`).
  - Implementacja: handlery `cmd_parse` (z `describe_sheet`), `cmd_list_sources` (z `list_sources`; tabela
    WYBOR/KRAJ/DOSTAWCA/KATALOG/KLUCZ/NAZWA renderowana z dokumentu; `select` skladany we flagi),
    `cmd_list_layers` (z `list_layers`), `cmd_cache` (z `get_cache_info`/`clear_cache`),
    `cmd_project_*` (z dokumentow projektu), `project add` przez `parse_command`; usun zdublowana
    logike z `cli/parse_cmd.py`, `cache_cmd.py`, `landcover_cmd.py`, `soil_cmd.py`; zaktualizuj
    `tests/test_cli.py` (odwolania do `format_sheet_info` 12, `cmd_parse` 10) i
    `tests/test_metadata_cache.py` (`cmd_cache` 5) na nowe punkty (asercje o zachowaniu bez zmian);
    usun test przejsciowy `test_describe_matches_the_cli_text_facts` (role przejmuje zrzut przed/po).
  - Weryfikacja: pelny `pytest`; zrzut `after`: `diff -r <...>/before/text <...>/after/text` PUSTY
    (tabele `list-sources`, `list-layers`, `parse`, `cache` bajtowo jak dzis).
  Commit: `feat(cli): --json w parse, list-sources, list-layers, cache i komendach projektu; tekst z dokumentow biblioteki`
- [x] **Step 9: opcje `COMMANDS` z katalogu i usuniecie starego kodu (D7, stage 3).**
  - `project/commands.py`: `TaskCommand.options` = `{p.name: p.kind for p in command.params if p.task}` z
    katalogu (kolejnosc nowych manifestow: `country` zaraz po `product` - zmiana kosmetyczna, testy
    kolejnosci aktualizowane); usun `*_task_arguments` (`download_cmd.py`, `landcover_cmd.py`
    `area_task_arguments`, `soil_cmd.py`, `collection_cmd.py`) i `_workers_given`; usun
    `kartograf/cli/groups/**` (14 plikow), flagowe helpery `cli/_args.py` (zostaje tylko to, co uzywaja
    handlery), kopie parserow wartosci i logiki `cli/_parser.py` (zostaje fasada).
  - Testy: usun test przejsciowy `test_kinds_parse_like_the_cli_helpers` (kopie w `cli/_args.py`
    znikaja) i dodaj `test_task_options_come_from_the_catalog` (`COMMANDS[...].options == {p.name: p.kind
    for p in params if p.task}` na prawdziwym `COMMANDS`). Zaktualizuj 12.10:
    `test_cli_translation.py::test_cli_imports_no_data_logic` (dozwolony import `kartograf.catalog` i
    `kartograf.serialization`, nadal zakaz `providers`, `transport` i doboru arkuszy),
    `test_public_api.py`, `test_cli_help.py` (przyklady `--help` z katalogu), `test_cli_language.py`
    (ASCII calego parsera), 12.11 (`test_parity*.py`, `test_project_*`, `test_availability.py`: tylko
    importy wnetrznosci i kod wyjscia bledow wejscia).
  - Weryfikacja: pelny `pytest`; `git grep -n "kartograf.cli.groups\|_task_arguments\|_workers_given" --
    kartograf tests` puste.
  Commit: `refactor(cli)!: parser i opcje projektu z katalogu; usuniete kartograf/cli/groups, flagi w _args.py i *_task_arguments (D7, stage 3)`
  z trescia `BREAKING: kod i testy importujace wnetrznosci CLI (cli.groups, download_task_arguments,
  _download_arguments) uzywaja parse_command(...).options albo create_parser()`
- [x] **Step 10: zamkniecie T5.** Eksporty `kartograf/__init__.py`: `CommandCall`, `parse_command`,
  `validate_command`, `format_command`, `run_command`, `check_command`; `tests/test_public_api.py`
  (nowe nazwy, argumenty tylko nazwane); zrzut `after` ostatni raz (jak Step 4: dozwolone tylko
  `--json` we wszystkich komendach-lisciach poza `availability` i komenda `catalog`: uruchom bez
  `--drop-json` i potwierdz, ze roznice to wylacznie linie `--json` i `catalog`); **brama zadania**
  (`scripts/gate.sh`). Raport: hashe, liczby bramy, wynik zrzutow, liczba asercji `== 1` -> `== 2`.
  Commit: `feat(api): eksporty warstwy komend KB-2..KB-5`

---

## Fala 3: T6 (serwer MCP) i T7 (`llms.txt`) - rownolegle, rozlaczne pliki

Po T5 koordynator tworzy dwa worktree z `feat/agent-interface`: `../agent-interface-mcp`
(`feat/agent-interface-mcp`, T6) i `../agent-interface-llms` (`feat/agent-interface-llms`, T7).
Kontrakt K3 (T5 -> T6, T7) w sekcji "Organizacja wykonania". Scala koordynator; konflikty:
oczekiwany brak (T6 dotyka `pyproject.toml`, T7 `MANIFEST.in`).

### Task T6: `catalog/tools.py` i `kartograf/mcp_server.py` (D11-D16, spec 9)

**Files:**
- Create: `kartograf/catalog/tools.py`, `kartograf/mcp_server.py`, `tests/test_mcp_tools.py`,
  `tests/test_mcp_server.py`
- Modify: `pyproject.toml` (extra `mcp`, `dev`, skrypt `kartograf-mcp`, ewentualny override mypy)

- [x] **Step 0: instalacja `mcp` w `.venv` (O7) i sprawdzenie API (bez commita).**
  ```
  $PY -m pip install --dry-run "mcp>=2.3.0,<3"   # 2026-10-18: 21 nowych pakietow, zero aktualizacji
  $PY -m pip install "mcp>=2.3.0,<3"
  ```
  Dry-run z aktualizacja istniejacego pakietu = zatrzymaj sie i zglos koordynatorowi (O7 dopuszcza
  tylko instalacje addytywna). Potem introspekcja zgodna ze specem 9.1-9.7:
  `inspect.signature(mcp.server.Server.__init__)` ma `version`, `instructions`, `on_list_tools`,
  `on_call_tool`; `mcp.server.session.ServerSession.report_progress(progress, total, message)`;
  `mcp.Client` przyjmuje `Server` i `raise_exceptions`; `mcp_types.CallToolResult` ma
  `structured_content`, `is_error`; `mcp.shared.exceptions.MCPError`. Roznica wzgledem specu =
  zatrzymaj sie i opisz koordynatorowi (nie dostosowuj po cichu).
- [x] **Step 1: `catalog/tools.py` (czyste dane, bez `mcp`; spec 9.3-9.4).**
  - Test RED (`tests/test_mcp_tools.py`; `jsonschema` przez `pytest.importorskip`; RED:
    `ModuleNotFoundError: kartograf.catalog.tools`): `test_tool_names_are_unique_snake_case`;
    `test_there_are_29_tools_in_six_families` (5 `discovery`, 1 `availability`, 12 `data`, 1 `check`,
    7 `project`, 3 `store`); `test_every_catalog_tool_name_has_a_spec_and_only_check_updates_has_no_command`
    (nazwy `CommandInfo.tool` <-> `ToolSpec.name`); `test_check_updates_enum_is_the_twelve_data_tools`
    (kolejnosc `COMMANDS`) i `test_check_arguments_schema_drops_update_plan_workers`
    (`check_arguments_schema(tool)` = schemat narzedzia danych bez tych trzech wlasciwosci,
    `additionalProperties: false`); `test_input_schemas_are_valid_draft_2020_12`
    (`Draft202012Validator.check_schema` dla wszystkich); `test_schemas_follow_catalog_params`
    (wystawione tylko parametry z `argument`; `required` = `required` z `argument` plus `output_dir`
    narzedzi danych; `enum` = `allowed`; `bbox`: tablica 4 liczb i `dependentRequired {"bbox":
    ["bbox_crs"]}`; `path` z opisem sciezki bezwzglednej; `per_country`: `anyOf` napis albo obiekt
    `{pl, cz}`; `plan`: `object`; `workers`: `minimum` 1; nieobecne: `quiet`, `json`, `check_updates`,
    `upgrade`, `force`; `update`: `enum` `upgrade`, `force`); `test_shared_tools_require_group`
    (`list_sources`, `list_layers`: `group` wymagany `enum`; `product` opcjonalny);
    `test_project_add_has_command_and_options`; `test_annotations_follow_kind_and_effects` (narzedzia
    danych: `read_only_hint=False`, `destructive_hint=False` jawnie, `idempotent_hint`,
    `open_world_hint`; `project_remove`: `destructive_hint=True`; odczyt: `read_only_hint=True`;
    `check_updates` i `project_check_updates`: RO + OW); `test_descriptions_are_ascii_and_titles_are_summaries`;
    `test_family_filter` (`tool_specs(families=("discovery", "data"))`; nieznana rodzina = `ValueError`).
  - Implementacja wg "Decyzje implementacyjne" 9 i spec 9.3-9.4 (`ToolSpec`, `tool_specs`,
    `check_arguments_schema`, `FAMILIES`; narzedzie `check_updates` zbudowane z jawnej specyfikacji, nie
    z komendy; wartosci wylacznie z `get_catalog(params=True)`).
  - Pomiar kontekstu: `len(json.dumps([<narzedzie jak na drucie>...]))` i szacunek `/4` tokenow - do
    commita i raportu T9 (spec 15: pomiar zastepuje szacunek 20-25 tys. dla 40 narzedzi).
  - Weryfikacja: `$PY -m pytest tests/test_mcp_tools.py -q`; brama kroku.
  Commit: `feat(mcp): specyfikacje narzedzi z katalogu (29 narzedzi, schematy wejscia, adnotacje)`
- [x] **Step 2: szkielet serwera, `ImportError`, `instructions`, `pyproject.toml`.**
  - Rozstrzygniecie sprzecznosci specu 9.2 (modul rzuca `ImportError` przy imporcie vs `main()`
    drukuje komunikat i konczy kodem 1): `kartograf.mcp_server` importuje sie BEZ `mcp` (importy SDK
    leniwie, w `create_server`; typy tylko pod `TYPE_CHECKING`); `create_server` rzuca
    `ImportError('Brak pakietu mcp: pip install "kartograf[mcp]"')`, a `main()` lapie go, drukuje na
    stderr i zwraca 1 - skrypt `kartograf-mcp` i `python -m kartograf.mcp_server` daja komunikat zamiast
    `ModuleNotFoundError`. (Spec 9.2 poprawiony wraz z tym planem.)
  - Test RED (`tests/test_mcp_server.py`): `test_instructions_are_ascii_and_at_most_8_lines`;
    `test_main_without_mcp_prints_the_install_hint_and_exits_1` (podproces z `sys.modules["mcp"] =
    None`; stderr zawiera `pip install "kartograf[mcp]"`, kod 1; ten test nie ma `importorskip`);
    `test_import_kartograf_does_not_import_mcp` (czysty proces: `import kartograf`; `"mcp" not in
    sys.modules`).
  - Implementacja: `kartograf/mcp_server.py` (`INSTRUCTIONS` z spec 9.9, `create_server(*, families,
    cache, allow_dirs)`, `main(argv=None) -> int`); `pyproject.toml`: `mcp = ["mcp>=2.3.0,<3"]`,
    `dev` + `"mcp>=2.3.0,<3"`, `kartograf-mcp = "kartograf.mcp_server:main"`.
  Commit: `build(mcp): extra mcp, skrypt kartograf-mcp i mcp w dev; szkielet kartograf/mcp_server.py`
- [x] **Step 3: obsluga wywolan, wyniki, bledy, postep, sciezki (spec 9.4-9.7).**
  - Test RED (`tests/test_mcp_server.py`, `pytest.importorskip("mcp")`, `Client(server,
    raise_exceptions=True)` w pamieci; fixtury jak w `tests/test_parity.py`):
    `test_list_tools_equals_tool_specs`; `test_discovery_tools_return_library_documents` (`get_catalog`,
    `parse_sheet`, `list_sources`, `list_layers`, `find_sheets`: `structured_content == doc.to_dict()`,
    tekst == `to_json(indent=None)`, `is_error` falsz); `test_data_tool_result_equals_cli_json_document`
    (dokument = ten sam co `--json` CLI przy zamrozonym zegarze; `is_error` = kod wyjscia != 0);
    `test_ok_false_is_an_error_result_carrying_the_report`; `test_check_updates_equals_check_command`
    (`kartograf-plan/1`); `test_check_updates_input_errors` (`tool` spoza `enum` -> `option="tool"`;
    `arguments` z `update`, `plan` albo `workers` oraz bez `output_dir` -> `invalid_input` z
    `details.option`; `command` bledu = komenda wskazana przez `tool`);
    `test_input_errors_are_error_documents` (sciezka wzgledna z `hint` "Podaj sciezke bezwzgledna",
    nieznany klucz, zly `enum`, `bbox` bez `bbox_crs` -> `kartograf-error/1`, `details.option`);
    `test_oserror_is_io_error` (`store_overview` na nieistniejacym `output_dir`);
    `test_foreign_exception_is_internal_error` (funkcja podmieniona na rzucajaca `KeyError`);
    `test_unknown_tool_is_a_protocol_error` (`MCPError`, `INVALID_PARAMS`);
    `test_progress_is_strictly_increasing` (atrapa pobrania wola `on_progress` ze zdarzeniami o
    powtarzajacym sie `current`; `progress_callback` dostaje 1, 2, 3...);
    `test_allow_dir_rejects_paths_outside_after_resolve`; `test_at_most_four_calls_run_at_once`
    (blokada `CapacityLimiter(4)`); `test_library_does_not_write_to_stdout_during_calls`.
  - Implementacja wg spec 9.4-9.7: kolejnosc walidacji (nieznane narzedzie -> `INVALID_PARAMS`;
    `jsonschema.Draft202012Validator` na `input_schema`; `check_updates`: `arguments` wobec
    `check_arguments_schema(tool)`; regula sciezek bezwzglednych i `--allow-dir`; `validate_command`;
    wykonanie w watku), wynik `CallToolResult(content=[TextContent(...)], structured_content=...,
    is_error=...)`, bledy przez `error_report(exc, command=<id komendy>)`, postep przez
    `ctx.session.report_progress`, brak `output_schema`.
  - Weryfikacja: `$PY -m pytest tests/test_mcp_server.py -q`; brama kroku.
  Commit: `feat(mcp): obsluga wywolan narzedzi - wyniki jak --json, bledy kartograf-error/1, postep, sciezki`
- [x] **Step 4: argumenty serwera i test stdio.**
  - Test RED: `test_tools_flag_selects_families` (`--tools discovery,availability,data,check` = 19
    narzedzi); `test_unknown_family_is_a_usage_error` (kod 2); `test_default_cache_file_is_in_the_user_cache_dir`
    (`XDG_CACHE_HOME`; plik `kartograf/metadata.db` powstaje przy pierwszym uzyciu; nie
    `<cwd>/.kartograf_cache.db`); `test_no_cache_flag`; `test_version_flag`;
    `test_stdio_server_lists_tools_and_parses_a_sheet` (`StdioServerParameters(command=sys.executable,
    args=["-m", "kartograf.mcp_server"], cwd=<korzen repo>)`, 29 narzedzi, wywolanie `parse_sheet`,
    stdout zawiera wylacznie ramki protokolu, bez sieci).
  - Implementacja: `main(argv)` z `--tools`, `--cache-file`/`--no-cache` (wzajemnie wykluczajace),
    `--allow-dir` (powtarzalne), `--version`; `anyio.run` + `stdio_server()` + `server.run(...)`.
  Commit: `feat(mcp): kartograf-mcp --tools, --cache-file, --no-cache, --allow-dir i transport stdio`
- [x] **Step 5: brama zadania.** `scripts/gate.sh` (z `mcp` w `.venv`: `mypy` widzi SDK; jesli brakuje
  stubow `jsonschema`, dodaj `jsonschema.*` do `[[tool.mypy.overrides]]` z `ignore_missing_imports`).
  Raport: hashe, liczby bramy, wynik pomiaru kontekstu narzedzi, wersja zainstalowanego `mcp`.

### Task T7: `llms.txt` (D18, spec 10.2)

**Files:** Create: `llms.txt`, `tests/test_llms_txt.py`; Modify: `MANIFEST.in` (`include llms.txt`)

- [x] **Step 1: Test RED** (`tests/test_llms_txt.py`; RED: brak pliku): `test_file_is_ascii_and_short` (ASCII,
  < 150 linii); `test_starts_with_title_and_quote` (`# Kartograf`, potem cytat `>`);
  `test_every_cli_example_parses_with_the_real_parser` (kazda linia bloku kodu zaczynajaca sie od
  `kartograf ` i bez `...` i `<` parsuje sie `parse_command_line`/`create_parser()`; polecenia z
  `--json` zawieraja flage); `test_every_link_points_to_an_existing_file` (`https://github.com/Daldek/Kartograf/blob/main/<sciezka>`
  -> plik lokalny istnieje; linki bezwzgledne); `test_error_codes_are_the_catalog_codes` (kody z sekcji
  "Kody bledow" naleza do `get_catalog().errors`, a kazdy kod katalogu z kodem wyjscia jest wymieniony);
  `test_sections_follow_llmstxt_format` (sekcje `##`, listy `- [tytul](url): opis`, sekcja `## Optional`).
- [x] **Step 2: tresc.** Projekt tresci ze specu 10.2 (czym jest Kartograf; zasady dla agentow: katalog
  `kartograf catalog --json`, `--json`, `kartograf elevation availability`, `--output` bezwzgledne poza
  repo i `/tmp`, kody wyjscia 0/1/2/130; instalacja z `kartograf[mcp]`; typowe zadania CLI z prawdziwymi
  poleceniami (availability, NMT arkusza, bbox z `--bbox-crs`, land cover, `soil hsg --summary`,
  `project add|download|status`, `parse`, `list-sources`); biblioteka (`download_data`/`check_data`,
  `check_availability`, `to_dict()`/`to_json()`, `get_catalog`, `error_report`); serwer MCP (konfiguracja,
  rodziny, `check_updates`, postep, `is_error`); kody bledow z tabeli 6.2; linki do dokumentacji).
  Polecenia sprawdz recznie na prawdziwym parserze przed commitem.
- [x] **Step 3: pakowanie i brama.** `MANIFEST.in`: `include llms.txt`; `python -m build --sdist` (jak T0
  Step 2) zawiera `llms.txt`; brama kroku i zadania.
  Commit: `docs(agents): llms.txt (llmstxt.org) i test zgodnosci polecen z parserem`

---

## Fala 4: T8 - dokumentacja

### Task T8: dokumentacja, CHANGELOG, PROGRESS, errata ADR-046 (spec 10.4, 10.5, 11)

**Files:** `docs/USAGE.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`, `docs/SCOPE.md`,
`docs/PRD.md`, `docs/CHANGELOG.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md` (CRLF), `README.md`,
`CLAUDE.md`, `kartograf/__init__.py` (docstring), `tests/test_docs_tables.py`

- [x] **Step 1: test RED** (`tests/test_docs_tables.py`): `test_usage_error_and_exit_code_tables_equal_the_catalog`
  (tabele kodow bledow i kodow wyjscia w `docs/USAGE.md` - jedyne w dokumentacji - maja te same kody,
  wyjatki i kody wyjscia co `get_catalog().errors` i `exit_codes`); `test_claude_md_has_the_agent_rule_and_no_agents_md`
  (sekcja "Agenci z innych repozytoriow" wymienia `scripts/gate.sh` i `llms.txt`; brak `AGENTS.md`).
- [x] **Step 2: `docs/USAGE.md`** - nowa sekcja "Interfejs dla agentow": `--json` per komenda (tabela
  specu 7.2), jedna tabela kodow wyjscia (6.5) i bledow (6.2), `kartograf catalog`, serwer MCP i konfiguracja
  klientow (9.8, `claude mcp add kartograf -- kartograf-mcp`), `llms.txt`; poprawka opisu `--json` raportu
  dostepnosci (`schema` pierwszym kluczem, `notices` bez echa na stderr). Przyklady z prawdziwych wydrukow
  (offline: `kartograf catalog --json`, `parse`, `list-sources`; availability z T9 jesli jest).
- [x] **Step 3: `docs/ARCHITECTURE.md`** - sekcja 2 (graf: `serialization`, `error_report`, `sheet_info`,
  `source_info`, `cache_info`, `store_documents`, `catalog`, `commands`, `mcp_server`; krawedzie `cli -> catalog`,
  `project -> catalog`, `mcp_server -> catalog, commands, kartograf`; `catalog -> sources, download, landcover,
  hydrology`), drzewo modulow, 3.6 "Dokumenty JSON `kartograf-*/1`" (lista schematow z `SCHEMAS`), 4.11
  "Interfejs dla agentow" (katalog, tabele, MCP), poprawka opisu `AvailabilityReport` (3017: bez pola
  `schema`), reguly Z1 i rejestr komend.
- [x] **Step 4: `docs/DEVELOPMENT_STANDARDS.md`** - 7.3: Z8 (CLI i MCP drukuja `to_json()`/`to_dict()`), Z9
  (nowa komenda = deklaracja w `catalog/commands/`, nie flagi w `cli/`), Z10 (wyjatek ma `code`/`exit_code`,
  walidator ustawia `option`), Z11 (schematy `/1` addytywne; nowy dokument = `Document` + test kluczy);
  6.3: `scripts/gate.sh`; 11.1: kody bledow; 17.2: przepis na nowa komende przez katalog (zastepuje wpis
  `COMMANDS` i `*_task_arguments`).
- [x] **Step 5: `docs/SCOPE.md`, `docs/PRD.md`, `README.md`, `CLAUDE.md`** - zakres 0.8.0 i poza zakresem
  (HTTP MCP, KC, KH); README: sekcja "Dla agentow AI"; `CLAUDE.md` wg specu 10.4 (punkt bramy ->
  `scripts/gate.sh`; sekcja "Agenci z innych repozytoriow": galaz od `develop`, bez merge/push/tagow, bez
  wpisow wydania bez zgody, obowiazkowy przeglad przed tagiem, `llms.txt`, `kartograf catalog --json`,
  serwer `kartograf-mcp`; wiersze mapy dokumentacji; NIE tworzyc `AGENTS.md`).
- [x] **Step 6: `docs/CHANGELOG.md` `[0.8.0]`** wg specu 11.1: w "Dodane" - `--json` w kazdej komendzie i
  dokumenty `kartograf-*/1`, katalog komend (`kartograf catalog`, `get_catalog`), warstwa komend KB-2..KB-5,
  kody bledow z `hint`, serwer MCP (`kartograf[mcp]`, 29 narzedzi), `py.typed`, `llms.txt`,
  `scripts/gate.sh`, `python -m kartograf`; w "Zmiany lamiace (BREAKING)" - pozycje 1-4 z kolumna "Co
  zrobic" (kod wyjscia 2; `schema` pierwszym kluczem i pole `schema` -> `ClassVar`; `--json` wycisza
  `Info:`/`Warning:`; parser z katalogu: usuniete `cli.groups`, `*_task_arguments`); w "Zmienione" -
  pozycje 5-8 (`calculate_hsg(summary=)`, `TaskDownload.plan`, opcje `COMMANDS` z katalogu); nowy kod
  `io_error`.
- [x] **Step 7: `docs/DECISIONS.md` (CRLF) i `docs/PROGRESS.md`.** ADR-046: errata 1 (wyniki T9, pomiar
  kontekstu narzedzi, rozstrzygniecie importu `mcp_server`, nazwy modulow); sprawdz relacje po obu
  stronach w ADR-037, ADR-039, ADR-040, ADR-045 (indeks i status). `docs/PROGRESS.md`: wpis konca sesji
  wg STANDARDS 15 (struktury PROGRESS nie ruszac). Po edycji: `file docs/DECISIONS.md` i zliczenie CRLF
  (liczba `\r\n` = liczbie `\n`).
- [x] **Step 8: brama zadania** (`scripts/gate.sh`, w tym `tests/test_docs_tables.py`).
  Commity (osobne): `docs(usage): sekcja Interfejs dla agentow, tabela kodow bledow i wyjscia`,
  `docs(architecture): dokumenty JSON, katalog komend i serwer MCP`, `docs(standards): reguly Z8-Z11,
  scripts/gate.sh, przepis na nowa komende przez katalog`, `docs(agents): CLAUDE.md, README i zakres
  0.8.0`, `docs(changelog): wpis 0.8.0 - interfejs dla agentow`, `docs(decisions): errata ADR-046 i
  PROGRESS`.

---

## Fala 5: T9 - brama pelna, smoke, wheel

### Task T9: weryfikacja koncowa (swiadomie, z siecia tam, gdzie wskazano)

Dane live wylacznie do `<katalog-danych>/kartograf/agent-interface-e2e/` (jawne `--output`), cache
metadanych w korzeniu worktree; raport `docs/research/2026-10-xx-agent-interface-e2e/raport.md` bez
sciezki katalogu danych.

- [x] **Brama:** `scripts/gate.sh` (pelny `pytest`, `ruff`, `ruff format --check`, `mypy`) - liczby do raportu.
- [x] **E2E-1 katalog i JSON offline:** `kartograf catalog --json | $PY -m json.tool`;
  `kartograf catalog elevation download --json` ma 30 parametrow (29 z flaga CLI, w tym `--json`, oraz `update`) i przyklady; po jednym wywolaniu z
  `--json` dla kazdej grupy (`list-sources` x11, `list-layers` x2, `parse`, `cache path`, `cache stats`,
  `project init|add|status` w projekcie w katalogu danych): stdout = jeden dokument, stderr pusty, kod 0
  (wyjatek: `project status` przed pierwszym pobraniem to `ok: false`, kod 1, spec 6.5; po `project download` 0).
  Blad: `kartograf elevation download --product nmt --json` -> `kartograf-error/1`, kod 2,
  `details.options` = `sheet, bbox, geometry` (brak obszaru jest zglaszany przed `output_dir`); z obszarem i
  bez `-o` `details.option == "output_dir"`.
- [x] **E2E-2 availability na zywo:** `kartograf elevation availability --product nmt --country pl --bbox
  565000,242000,569000,246000 --json` (Krakow) i Pomorze (E 339000-343000, N 744800-747000): dokument
  rowny `check_availability(...).to_json()` z tego samego cache (poza `checked_at`); wyniki zgodne z
  planem A (kompletne kombinacje Krakowa; Pomorze: 2025 0.5m niekompletna) albo opisz nowe fakty GUGiK.
- [x] **E2E-3 jedno male pobranie i sprawdzenie:** `kartograf elevation download --product nmt --sheet
  M-34-64-D-d-1-2 --resolution 5m --vertical-crs EVRF2007 -o <katalog-danych>/... --json`
  (arkusz Krakowa; `N-34-130-D-d-2-4` ma NMT tylko 1 m, wiec 5 m daje `ok: false`; status `new`, `ok: true`),
  ponownie (`local`), potem `--check-updates --json` (`kartograf-plan/1`,
  pozycje `current`).
- [x] **E2E-4 serwer MCP przez stdio:** skrypt z SDK (`StdioServerParameters`, `kartograf-mcp --allow-dir
  <katalog-danych>`): `list_tools` = 29 narzedzi; `parse_sheet` offline; `elevation_availability` na zywo
  (dokument jak E2E-2); `check_updates` z `tool: elevation_download` na magazynie z E2E-3 (`current`);
  `store_overview` i `store_entries` na tym magazynie (`truncated` falsz); wywolanie z bledem
  (wzgledna sciezka) -> `is_error: true` i `kartograf-error/1`.
- [x] **E2E-5 wheel z `py.typed`:** `$PY -m build --wheel --outdir <katalog-danych>/.../dist .`;
  `$PY -m zipfile -l <wheel>` zawiera `kartograf/py.typed`; czyste venv (`python -m venv`), instalacja
  wheel, skrypt konsumenta `from kartograf import download_data, get_catalog` z `reveal_type(download_data)`
  sprawdzony `mypy`: brak `import-untyped`, sygnatura zamiast `Any`.
- [x] **E2E-6 parzystosc trzech drog:** to samo zadanie (arkusz z E2E-3, `--check-updates`) przez CLI
  `--json`, biblioteke `check_data(...).to_dict()` i narzedzie MCP `check_updates`: identyczne dokumenty
  poza `checked_at`.
- [x] **Raport i commit:** `docs(research): E2E interfejsu dla agentow (JSON, katalog, MCP)`; raport
  koncowy do koordynatora (hashe wszystkich fal, liczby bram, wyniki E2E, otwarte kwestie).

## Review Focus

1. **Jeden dokument, trzy drogi:** CLI `--json`, `to_dict()` i narzedzie MCP daja te same klucze, wartosci i
   kolejnosc kluczy (testy zgodnosci T5 Step 7 i T6 Step 3; E2E-6); roznia sie tylko `checked_at`, etykieta
   `downloaded` i sciezki magazynu.
2. **Katalog = parser = `COMMANDS` = sygnatury API:** testy kontraktowe (T4b-T4d, T5 Step 0 i Step 9)
   sprawdzaja flagi w obie strony, `task` wobec `COMMANDS`, `function` wobec `__all__`, przyklady przez
   `validate_command` i okrazenie `parse_command(format_command(...))`.
3. **Tekst CLI bez zmian:** zrzut przed/po (Dodatek A) po T5 Step 4, 8 i 10: 36 helpow lisci, helpy grup,
   akcje i 33 przebiegi tekstowe bajtowo identyczne; roznice dozwolone tylko: nowa komenda `catalog`, flaga
   `--json`, przyklady w liniach `Przyklady` brane z katalogu (kolejnosc flag, dodatkowy przyklad CZ w
   `boundaries download`, spec 7.5), opis `landcover download` w pomocy grupy (spec 16.3 pkt 5), dluzszy opis
   `cache path` (spec 16.4) i kod wyjscia 2 dla `parse` z blednym albo brakujacym godlem (O2); zrzut akcji
   parsera rozni sie wylacznie komenda `catalog` (E2E U6).
4. **Kody wyjscia i `ok`:** bledy wejscia -> 2, awarie i `ok: false` -> 1, Ctrl-C -> 130; dokument bledu
   zawsze na stdout w trybie JSON, stderr pusty (poza wierszami ponowien HTTP); `OSError` -> `io_error`.
5. **Rozlacznosc torow:** zaden plik nie jest edytowany przez dwa tory fali 1; `git diff --stat` kazdego
   toru sprawdzany przez koordynatora wzgledem tabeli "Pliki na wlasnosc"; scalenie bez konfliktow.
6. **`mcp` opcjonalny:** `import kartograf` i CLI dzialaja bez `mcp` (test czystego procesu); jedyny modul
   kontaktujacy sie z SDK to `kartograf/mcp_server.py`; testy in-memory i stdio offline.
7. **Brak cichych wartosci domyslnych w MCP:** `output_dir` zawsze jawny i bezwzgledny, `bbox` zawsze z
   `bbox_crs`, schematy wejscia z katalogu bez recznych kopii (`tools.py` nie powtarza list wartosci).

## Kryteria zamkniecia

Odpowiadaja kryteriom akceptacji specu (sekcja 14):

1. `py.typed` w drzewie i w wheel; `mypy` konsumenta bez `import-untyped` (T0, T9 E2E-5).
2. Kazda komenda-lisc CLI (36 + `catalog`) przyjmuje `--json` i drukuje jeden dokument znanego schematu;
   stderr pusty; kod wg tabeli (T5 Step 7-8, T9 E2E-1).
3. CLI `--json` == API `to_dict()` dla scenariuszy z T5 Step 7; raport dostepnosci bajtowo == `to_json()`.
4. Kazdy `KartografError` ma stabilny `code`; tabele 6.2 i 6.5 jedyne w USAGE i rowne katalogowi (T2,
   T8 `test_docs_tables.py`).
5. Bledy wejscia z walidatorow wspolnych niosa `option`/`allowed`; w trybie JSON `kartograf-error/1` z
   `hint` (dozwolone wartosci + przyklad) (T2 Step 2-6, T5 Step 2 i 5).
6. `get_catalog()` = `kartograf catalog --json` = narzedzie `get_catalog`; kazda flaga kazdej komendy w
   katalogu i odwrotnie; `COMMANDS` i sygnatury zgodne; `data_commands()` zwraca 12 komend (T4, T5 Step 0, 9).
7. Parser zbudowany z deklaracji; `kartograf/cli/groups/*` usuniete; `--help` i tabele `list-sources` bez
   zmian tresci (zrzut przed/po, T5 Step 4, 8, 10).
8. `parse_command`, `validate_command`, `format_command`, `run_command`, `check_command` wg 8.7; przyklady
   katalogu zgodne w obie strony (T5 Step 2).
9. `kartograf-mcp` wystawia 29 narzedzi (`--tools` zaweza), w tym `check_updates`; schematy wejscia zgodne z
   katalogiem; wynik == `to_dict()`; `is_error` == kod CLI != 0; postep rosnie scisle; testy in-memory i
   stdio zielone offline; `import kartograf` bez `mcp` (T6).
10. `llms.txt` (< 150 linii, polecenia prawdziwe) i `scripts/gate.sh` w repozytorium; `CLAUDE.md` z regula dla
    agentow z innych repozytoriow i wskazaniem obu; brak `AGENTS.md` (T0, T7, T8).
11. Brama pelna zielona (`scripts/gate.sh`); dokumentacja z 10.5, CHANGELOG `[0.8.0]` i PROGRESS
    zaktualizowane (T8, T9).
12. Smoke na zywo (poza repo i poza `/tmp`): availability `--json`, `kartograf-mcp` przez stdio z
    `elevation_availability` i `parse_sheet` (T9 E2E-2, E2E-4).

## Dodatek A: skrypt zrzutu odniesienia (poza repo)

Uruchamiany z korzenia worktree interpreterem `PY`: `$PY baseline_dump.py <katalog-wynikowy> [--drop-json]`.
Sprawdzony 2026-10-18 na kodzie `8c65f4e`: wydruk `leaf commands: 36; parsers: 50; text runs: 33`,
dwa uruchomienia daja identyczne katalogi, `COLUMNS` nie wplywa na wynik, siec zablokowana w skrypcie.
`--drop-json` (po przelaczeniu parsera, T5 Step 4) usuwa `--json` z kazdej komendy-liscia oprocz
`elevation availability` (ktora miala te flage wczesniej), zeby zrzut "po" dalo sie porownac ze zrzutem
"przed" przez `diff -r`.

```python
"""One-off reference dump of the CLI (run BEFORE the catalog migration, outside the repo).

Usage (cwd = worktree root, python of the shared .venv):
    python baseline_dump.py <output-directory> [--drop-json]

Writes <out>/help/*.txt (format_help of root, groups and leaf commands),
<out>/actions.json (every argparse action of every command) and
<out>/text/*.json (stdout, stderr and exit code of read-only commands).
Network is blocked: a command that needs it records the failure.
"""

import argparse
import contextlib
import io
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

os.environ["COLUMNS"] = "100"  # argparse wraps help at the terminal width

from kartograf.cli._parser import create_parser
from kartograf.cli.commands import main


def _block_network() -> None:
    def refuse(*args, **kwargs):
        raise RuntimeError("network blocked during the baseline dump")

    socket.socket.connect = refuse  # type: ignore[assignment]
    socket.create_connection = refuse  # type: ignore[assignment]


def _sub_actions(parser):
    return [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]


def _walk(parser, path=()):
    """Every parser of the tree with its command path (root = ())."""
    yield path, parser
    for action in _sub_actions(parser):
        for name, sub in action.choices.items():
            yield from _walk(sub, (*path, name))


def _drop_option(parser, flag: str) -> None:
    action = parser._option_string_actions.get(flag)
    if action is None:
        return
    parser._remove_action(action)
    for group in (*parser._action_groups, *parser._mutually_exclusive_groups):
        if action in group._group_actions:
            group._group_actions.remove(action)
    for option in action.option_strings:
        parser._option_string_actions.pop(option, None)


def _type_name(action) -> str | None:
    kind = action.type
    if kind is None:
        return None
    return getattr(kind, "__qualname__", None) or repr(kind)


def _row(action, titles, mutex) -> dict:
    return {
        "option_strings": list(action.option_strings),
        "dest": action.dest,
        "kind": type(action).__name__,
        "type": _type_name(action),
        "choices": None if action.choices is None else list(action.choices),
        "default": repr(action.default),
        "nargs": action.nargs,
        "required": action.required,
        "const": repr(action.const),
        "metavar": action.metavar,
        "help": action.help,
        "section": titles.get(id(action)),
        "exclusive": mutex.get(id(action)),
    }


def _dump_parser(path, parser) -> list[dict]:
    titles = {}
    for group in parser._action_groups:
        for action in group._group_actions:
            titles[id(action)] = group.title
    mutex = {}
    for index, group in enumerate(parser._mutually_exclusive_groups):
        for action in group._group_actions:
            mutex[id(action)] = index
    return [
        _row(a, titles, mutex)
        for a in parser._actions
        if not isinstance(a, argparse._SubParsersAction)
    ]


def _run(argv, cwd) -> dict:
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(list(argv))
            except SystemExit as exc:
                code = exc.code
            except Exception as exc:  # recorded, not fatal
                code = f"EXC {type(exc).__name__}: {exc}"
    finally:
        os.chdir(old)
    shown = str(Path(cwd).resolve())  # the working directory differs per run
    return {
        "argv": list(argv),
        "code": code,
        "stdout": out.getvalue().replace(shown, "<cwd>"),
        "stderr": err.getvalue().replace(shown, "<cwd>"),
    }


SAMPLE_SHEETS = [
    "N-34", "N-34-130", "N-34-130-D", "N-34-130-D-d", "N-34-130-D-d-2",
    "N-34-130-D-d-2-4", "6.179.12.20", "CTES96", "302_5550", "N-34-130-D-d-2-4-1",
    "ABC", "",
]
GROUPS = [
    "elevation", "imagery", "landcover", "soil", "boundaries", "cadastre",
    "models3d", "hydro", "names", "maps", "geodesy",
]


def main_dump(out_dir: Path, drop_json: bool = False) -> None:
    _block_network()
    parser = create_parser()
    if drop_json:
        for path, sub in _walk(parser):
            if path and not _sub_actions(sub) and path != ("elevation", "availability"):
                _drop_option(sub, "--json")
    help_dir = out_dir / "help"
    text_dir = out_dir / "text"
    help_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    actions: dict[str, list[dict]] = {}
    leaves = 0
    for path, sub in _walk(parser):
        name = " ".join(path) or "(root)"
        (help_dir / (("_".join(path) or "root") + ".txt")).write_text(
            sub.format_help(), encoding="utf-8"
        )
        actions[name] = _dump_parser(path, sub)
        if not _sub_actions(sub) and path:
            leaves += 1
    (out_dir / "actions.json").write_text(
        json.dumps(actions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    runs = []
    with tempfile.TemporaryDirectory() as tmp:
        for group in GROUPS:
            runs.append(_run([group, "list-sources"], tmp))
        runs.append(_run(["elevation", "list-sources", "--product", "nmt"], tmp))
        runs.append(_run(["landcover", "list-layers", "--product", "bdot10k"], tmp))
        runs.append(_run(["landcover", "list-layers", "--product", "corine"], tmp))
        runs.append(_run(["soil", "list-layers"], tmp))
        for sheet in SAMPLE_SHEETS:
            runs.append(_run(["parse", sheet], tmp))
        runs.append(_run(["parse", "N-34-130-D-d-2-4", "--hierarchy"], tmp))
        runs.append(_run(["parse", "N-34-130-D", "--children"], tmp))
        runs.append(_run(["parse", "N-34-130-D", "--descendants", "1:10000"], tmp))
        runs.append(_run(["cache", "path"], tmp))
        runs.append(_run(["cache", "stats"], tmp))
        runs.append(_run(["--version"], tmp))
    for index, run in enumerate(runs):
        slug = "_".join(run["argv"]).replace("/", "-").replace(":", "-") or "empty"
        (text_dir / f"{index:03d}_{slug}.json").write_text(
            json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"leaf commands: {leaves}; parsers: {len(actions)}; text runs: {len(runs)}")


if __name__ == "__main__":
    main_dump(Path(sys.argv[1]), drop_json="--drop-json" in sys.argv[2:])
```

## Dodatek B: `scripts/gate.sh` (implementacja referencyjna T0 Step 3)

Sprawdzona 2026-10-18 w worktree: `bash -n`, zielony przebieg (`GATE OK (7 s)` z `-x -k test_version`),
zepsuty plik (kod 1 po `== ruff check`), inny checkout (kod 2).

```bash
#!/usr/bin/env bash
# Jedna komenda bramy Kartografa (STANDARDS 6.3, 8.3, 18): ruff check, ruff format
# --check, mypy i pytest offline; pierwszy kod != 0 konczy skrypt tym kodem.
# Argumenty trafiaja do pytest, np.: scripts/gate.sh -x -k parity
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

find_python() {
  if [[ -n "${KARTOGRAF_PYTHON:-}" ]]; then
    printf '%s\n' "$KARTOGRAF_PYTHON"
    return
  fi
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT/.venv/bin/python"
    return
  fi
  # worktree bez wlasnego .venv: srodowisko glownego checkoutu
  local common main
  if common="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"; then
    main="$(dirname "$common")"
    if [[ -x "$main/.venv/bin/python" ]]; then
      printf '%s\n' "$main/.venv/bin/python"
      return
    fi
  fi
  return 1
}

if ! PY="$(find_python)"; then
  echo "gate: brak Pythona - ustaw KARTOGRAF_PYTHON albo utworz .venv (STANDARDS 6.1)" >&2
  exit 2
fi

# Kontrola 0: kod testowany to kod tego checkoutu (instalacja edytowalna wskazuje
# glowny checkout, a worktree ma sprawdzac wlasne zrodla - dlatego kazdy krok idzie
# przez "$PY" -m ... z cwd = korzen).
package="$("$PY" -c 'import kartograf; print(kartograf.__file__)')"
case "$package" in
  "$ROOT"/*) ;;
  *)
    echo "gate: brama sprawdza inny checkout ($package), a nie $ROOT" >&2
    exit 2
    ;;
esac

started=$SECONDS
echo "== ruff check"
"$PY" -m ruff check .
echo "== ruff format --check"
"$PY" -m ruff format --check .
echo "== mypy"
"$PY" -m mypy kartograf/ tests/
echo "== pytest (offline)"
"$PY" -m pytest tests/ -m "not live" -q "$@"
echo "GATE OK ($((SECONDS - started)) s)"
```
