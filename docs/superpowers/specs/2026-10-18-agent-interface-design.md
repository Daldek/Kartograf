# Spec: Interfejs dla agentow AI - dokumenty JSON, kody bledow, katalog komend i serwer MCP (0.8.0)

**Data:** 2026-10-18
**Status:** zaakceptowana przez koordynatora 2026-10-18: zakres (pozycje 1-8 sekcji 0),
decyzje szczegolowe D1-D21 (sekcja 4) i rozstrzygniecia O1-O9 (sekcja 16); wdrozenie wg
planu `docs/superpowers/plans/2026-10-18-agent-interface.md` (zadania T0-T9, sekcja 13)
**Galaz:** `feat/agent-interface` (z `feat/archiwista-store-api`; zawiera poprawki
przegladu API odczytu magazynu, merge `8c65f4e`)
**Wersja docelowa:** 0.8.0 (wydanie jeszcze nietagowane: zmiany lamiace API
i CLI dozwolone, wszystko w jednym wydaniu; sekcja 11)
**Warunek wstepny:** API odczytu magazynu (ADR-045, po przegladzie z merge `8c65f4e`),
grupy komend CLI (ADR-039, ADR-044), manifest projektu (ADR-040), raport dostepnosci
(ADR-041) i `Notice` (ADR-037) sa juz w 0.8.0-dev na galezi bazowej
**Dokumenty zrodlowe:**
- decyzje koordynatora 2026-10-18 (pozycje 1-8 sekcji 0; poza zakresem:
  archiwizacja dziennika `docs/PROGRESS.md`, `AGENTS.md`, szacunek rozmiaru
  pobrania - KH, anulowanie - KC)
- ADR-037 (CLI tylko tlumaczy; Z1-Z7), ADR-039 (grupy komend), ADR-040
  (manifest, `project/commands.py::COMMANDS`), ADR-041 (`kartograf-availability/1`),
  ADR-044 (funkcje poziomu komend, raporty), ADR-045 (odczyt magazynu),
  ADR-031 i `docs/DEVELOPMENT_STANDARDS.md` 9.4 (jezyk), 11.1 (wyjatki)
- Archiwista `docs/SPEC.md` 12.2 (KB-1..KB-7), 5.6 (protokol zadan w tle:
  `progress`/`notice`/`result`/`error`), 7.3 (narzedzia asystenta), 9 (API HTTP)
  - tylko odczyt, nazwy z tej specyfikacji sa ostateczne (sekcja 8.6)
- SDK MCP: `mcp` 2.3.0 (PyPI 2026-10-02), dokumentacja
  https://py.sdk.modelcontextprotocol.io (low-level `Server`, postep, bledy,
  testowanie); zrodla wheel `mcp` i `mcp-types` 2.3.0 przeczytane 2026-10-18

---

## 0. Zakres w skrocie

| # | Pozycja | Co powstaje | Sekcja |
|---|---|---|---|
| 1 | `py.typed` | plik znacznikowy PEP 561 w paczce, `package-data`, `MANIFEST.in`, klasyfikator | 10.1 |
| 2 | `--json` w kazdej komendzie CLI | dokumenty `kartograf-<rodzaj>/1` z biblioteki (`to_dict()`/`to_json()`), CLI tylko drukuje; blad = `kartograf-error/1` | 5, 6, 7 |
| 3 | Stabilne kody bledow | `code`, `hint`, `exit_code` na wyjatkach, jedna tabela kodow bledow i wyjscia | 6 |
| 4 | Katalog komend | `get_catalog()` (`kartograf-catalog/1`), `kartograf catalog`, pokrycie KB-1 i warstwa komend KB-2..KB-5; parser CLI budowany z katalogu | 8 |
| 5 | Serwer MCP | `kartograf[mcp]`, `kartograf-mcp`, `kartograf/mcp_server.py`, 29 narzedzi z katalogu | 9 |
| 6 | `llms.txt` | spis tresci dla agentow (llmstxt.org), po polsku, < 150 linii | 10.2 |
| 7 | `scripts/gate.sh` | jedna komenda bramy (ruff, ruff format, mypy, pytest), dziala z worktree | 10.3 |
| 8 | `CLAUDE.md` | regula dla agentow z innych repozytoriow + wskazanie `scripts/gate.sh` i `llms.txt` | 10.4 |

Poza zakresem tej specyfikacji (decyzja koordynatora): archiwizacja dziennika
`docs/PROGRESS.md` (struktury PROGRESS nie ruszamy), `AGENTS.md` (nie tworzyc),
KH (szacunek rozmiaru pobrania), KC (anulowanie i jednolity `on_progress`),
KB-6 (`command_for_file`) i KB-7 (`find_admin_units`), transport HTTP serwera MCP
(tylko stdio), strumieniowy postep na stderr w trybie CLI `--json`.

## 1. Cel i kryterium akceptacji

Agent AI (Claude Code, asystent Archiwisty, skrypt, inny serwer) uzywa
Kartografa trzema drogami - CLI, biblioteka Pythona i serwer MCP - i na kazdej
musi umiec: (1) **odkryc**, co Kartograf potrafi i jakie wartosci sa dozwolone,
bez czytania kodu i bez parsowania `--help`; (2) **wywolac** komende z jawnymi
parametrami i dostac wynik w postaci maszynowej; (3) po bledzie **wiedziec, co
poprawic**, bez parsowania polskiego tekstu.

Kryterium (kontroluja je testy z sekcji 12, kryteria numerowane w sekcji 14):

- to samo zadanie przez CLI `--json`, API (`to_dict()`) i MCP daje ten sam
  dokument: te same klucze, wartosci i kolejnosc kluczy. Roznia sie tylko pola
  zalezne od chwili wykonania (`checked_at`, etykieta wersji `downloaded`) i
  sciezki magazynu - jak w kryterium ADR-037; testy zgodnosci zamrazaja zegar;
- katalog (`get_catalog()` = `kartograf catalog --json` = narzedzie MCP
  `get_catalog`) opisuje kazda komende CLI i kazdy jej parametr; jego zgodnosc
  z argparse, z sygnaturami funkcji API i z `COMMANDS` projektu jest
  wymuszona testami (kazda flaga kazdej komendy jest w katalogu i odwrotnie);
- kazdy blad ma stabilny `code`, kod wyjscia z jednej tabeli i - gdy sie da -
  `hint` z dozwolonymi wartosciami i przykladem poprawnej komendy;
- `import kartograf` nie wymaga `mcp`; konsument z mypy widzi typy (`py.typed`);
- serwer MCP przechodzi test offline przez klienta SDK (in-memory) i przez
  stdio (podproces) bez dostepu do sieci.

## 2. Stan wyjsciowy (badanie kodu 2026-10-18)

- `--json` ma tylko `elevation availability` (`cli/availability_cmd.py`:
  `report.to_json()`); pozostale komendy drukuja tekst: tabele, linie statusu,
  pasek postepu na stdout, `Info:`/`Warning:`/`Error:` na stderr.
- Serializacja: `AvailabilityReport.to_json()` i `UpdatePlan.to_json()` to dwie
  osobne implementacje `dataclasses.asdict`; `schema` jest ostatnim kluczem.
  Raporty komend (`DataReport`, `CollectionReport`, `LandCoverReport`,
  `SoilReport`, `HsgReport`) oraz `Project`, `ProjectReport`, `ProjectCheck`
  nie maja serializacji; `parse`, `list-sources`, `list-layers` i `cache` nie
  maja typu wyniku (CLI drukuje tekst zlozony w `cli/`, a logika wyboru flag
  per grupa, odczyt providerow i `MetadataCache` siedzi w modulach CLI -
  poza regula Z1).
- `Notice` ma pola `level`, `code`, `text` (ASCII); `asdict` daje te same
  klucze w `kartograf-availability/1`; Archiwista (SPEC 5.6, 7.9, przyklad SSE
  w 9.3) i `on_notice` uzywaja nazwy `text`.
- Wyjatki: osiem klas w `kartograf/exceptions.py` (`KartografError`,
  `ValidationError`, `ParseError`, `DownloadError`, `NoCoverageError`,
  `YearRangeError`, `CacheError`, `InvalidSidecarError`) i dwie w
  `transform/crs.py` (`TransformError`, `TransformUnavailableError` z polem
  `remedy`); bez `code` i `hint`; informacje dla wywolujacego maja tylko czesc
  klas (`DownloadError.sheet`/`status_code`, `NoCoverageError.hints`,
  `YearRangeError.sheets`/`hints`, `InvalidSidecarError.path`).
- Odczyt magazynu (ADR-045, stan po przegladzie `8c65f4e`): `list_segments`,
  `iter_store`, `read_sidecar`, `describe_segment`, `file_footprint`, `link_target` i
  typy `Sidecar`, `StoreEntry`, `SegmentInfo` (`Sidecar` i `StoreEntry` niehashowalne:
  pola `dict`). Brak albo niedostepny `output_dir` to `OSError` (nie pusty magazyn);
  bledne argumenty (segment, jednostka: nazwa zarezerwowana `versions`/`full_sheet`/
  `kampanie` albo dluzsza niz 255 bajtow, `units` bez `segment`) to `ValidationError`
  od razu przy wywolaniu; `read_sidecar` zglasza `InvalidSidecarError` (brak pliku, zly
  JSON, inny schemat; sidecar bez pola `schema` tylko w ksztalcie `emit_sidecar`).
  `Sidecar.unit` pliku krajowego z motywem to nazwa pliku slotu (`pl_miejscowosci`) i
  jest wartoscia przyjmowana przez `iter_store(units=...)` tego segmentu;
  `Sidecar.schema` jest zawsze `kartograf-meta/1`.
- Kody wyjscia (`cli/commands.py::main`): 0, 1 (`KartografError`, wyjatek
  spoza hierarchii, `ok == false`), 2 (argparse), 130 (Ctrl-C). Nigdzie nie sa
  spisane w jednej tabeli.
- Parser: 36 komend-lisci (`create_parser()`), flagi dodawane recznie w 14
  plikach `kartograf/cli/groups/` (1925 linii razem) i `cli/_args.py`; teksty
  `--help` ok. 38 tys. znakow, z wartosciami z rejestru zrodel i wariantow
  (`download/options.py`, `landcover/manager.py`, `download/collections.py`);
  przyklady w `epilog` (test `tests/test_cli_help.py` sprawdza je przez
  `project add`).
- Te same nazwy i rodzaje opcji powtorzone w `project/commands.py::COMMANDS`
  (12 komend danych; rodzaje `str`, `int`, `flag`, `bbox`, `bbox_crs`, `path`,
  `per_country`, `str_list`) i w pieciu funkcjach `*_task_arguments` CLI.
- Brak katalogu komend: Archiwista (SPEC 12.2 KB-1..KB-5) i jego asystent
  czekaja na `data_commands()`, `validate_command`, `format_command`,
  `run_command`/`check_command`.
- Brak `kartograf/py.typed`, `llms.txt`, `scripts/`, `kartograf/__main__.py`;
  `CLAUDE.md` nie ma regul dla agentow z innych repozytoriow.
- SDK MCP: `mcp` 2.3.0 (2026-10-02, `requires-python >= 3.10`; linia 1.x
  nadal wydawana: 1.30.0). v2 przebudowal serwer: `FastMCP` -> `MCPServer`,
  niskopoziomowy `Server` bierze handlery w konstruktorze i nie waliduje
  argumentow, wyjatek w handlerze to blad protokolu (`-32603`), a blad widoczny
  dla modelu to `CallToolResult(is_error=True)` budowany recznie; klient
  testowy `Client(server)` laczy sie w pamieci. Zaleznosci `mcp`: `anyio`,
  `httpx2`, `jsonschema`, `mcp-types`, `opentelemetry-api`, `pydantic>=2.12`,
  `pyjwt[crypto]`, `python-multipart`, `sse-starlette`, `starlette`,
  `uvicorn`, `typing-extensions`, `typing-inspection` (+ `pywin32` na Windows);
  `starlette` i `uvicorn` sa zaleznosciami twardymi takze dla stdio.
- Konsumenci (badanie repozytoriow siostrzanych): Hydrograf uzywa biblioteki
  (nie CLI): `SheetParser`, `BBox`, `find_sheets_for_bbox`, `DownloadManager`,
  `GugikProvider`, `MetadataCache`, `Bdot10kProvider`, lapie `ValueError`,
  `ValidationError`, `ParseError`; Archiwista uzywa wylacznie nazw z
  `kartograf.__all__` (`iter_store`, `read_sidecar`, `open_project`,
  `get_project_status`, ...) i lapie `KartografError`, `InvalidSidecarError`.
  Zaden konsument nie wywoluje CLI przez podproces ani nie parsuje jego tekstu.

## 3. Zasady (staja sie regulami Z8-Z11 w STANDARDS 7.3)

**A1. Jedna serializacja, w bibliotece.** Wynik komendy to dokument:
dataclass z `to_dict()`/`to_json()` z jednego mixinu (`kartograf/serialization.py`).
CLI drukuje `to_json()`, MCP zwraca `to_dict()`; zaden inny modul nie zamienia
wynikow na JSON (rozszerzenie Z1: CLI i MCP nie formatuja danych).

**A2. Kontrakt `--json`.** stdout = dokladnie jeden dokument JSON (UTF-8,
wciecie 2 spacje, znak nowej linii na koncu); pole `schema` = `kartograf-<rodzaj>/<n>`;
klucze po angielsku w `snake_case`; sciezki jako napisy bezwzgledne z `/`;
brak paska postepu, linii statusu i `Info:`/`Warning:` (komunikaty sa w
`notices`); blad = `kartograf-error/1` na stdout i kod wyjscia z tabeli 6.5.

**A3. Wersjonowanie.** W obrebie `/1` tylko zmiany addytywne (nowe klucze, nowe
wartosci wyliczen); konsument ignoruje nieznane klucze. Usuniecie klucza albo
zmiana typu to `/2` (jak IMGW-13 w SPEC Archiwisty).

**A4. Blad jest danymi.** Kazdy wyjatek z hierarchii `KartografError` ma stabilny
`code` (`snake_case`), `exit_code` i opcjonalny `hint`; informacje dla
wywolujacego sa atrybutami wyjatku (STANDARDS 11.1), nigdy czescia komunikatu do
parsowania.

**A5. Katalog jest jedynym zrodlem prawdy o komendach.** Deklaracje komend i
parametrow (nazwa flagi, nazwa argumentu API, rodzaj, wymagalnosc, dozwolone
wartosci, opis, przyklady) zyja w `kartograf/catalog/`. Rzutami katalogu sa:
parser CLI (argparse budowany z deklaracji), nazwy i rodzaje opcji w
`project/commands.py::COMMANDS`, schematy wejscia narzedzi MCP i `llms.txt`.
Rozjazd wyklucza budowa, a testy kontraktowe (sekcja 12) sprawdzaja reszte.

**A6. Warstwy.** Biblioteka (w tym `catalog`) nie importuje `kartograf.cli` ani
`mcp`. `cli` i `mcp_server` importuja katalog i funkcje komend. `mcp` jest
zaleznoscia opcjonalna (extra), importowana wylacznie w `kartograf/mcp_server.py`.

**A7. MCP jest cienki.** Narzedzie = jedna komenda katalogu = jedna funkcja
biblioteki (przez `run_command`/`check_command` albo wprost); jedyny wyjatek to
`check_updates`: jedno narzedzie sprawdzajace dla komend danych (argument `tool`
wybiera komende, wywolanie to `check_command`). Wynik narzedzia = ten sam dict co
`--json`; zadna logika danych, walidacja ani formatowanie nie powstaje w serwerze.

**A8. Bez cichych wartosci domyslnych wplywajacych na dane.** Narzedzia MCP
nie dodaja wartosci domyslnych: `output_dir` jest zawsze jawny, kazda sciezka
bezwzgledna, `bbox` zawsze z `bbox_crs` (domyslne `EPSG:2180` zostaje tylko flaga
CLI `--bbox-crs`; w API `BBox.crs` jest obowiazkowe).

**A9. Jezyk.** Klucze, nazwy schematow, kody bledow, nazwy narzedzi i wartosci
wyliczen - angielskie, `snake_case` (ADR-031). Teksty dla czlowieka (`message`,
`hint`, `text` komunikatu, opisy katalogu i narzedzi) - po polsku, ASCII (Z5).

**A10. Powtarzalnosc.** Kolejnosc kluczy i elementow tablic jest stala (kolejnosc
pol dataclass, kolejnosc wyniku biblioteki); przy zamrozonym zegarze
`to_json()` jest bajtowo powtarzalne.

## 4. Decyzje i odrzucone warianty

| # | Decyzja | Odrzucone warianty i powod |
|---|---|---|
| D1 | Mixin `Document` w `kartograf/serialization.py`: generyczny koder dataclass (`Path` -> sciezka bezwzgledna, `tuple` -> lista, `Decimal` -> napis, `BBox` -> `{"bbox", "crs"}`, `Notice` -> `{level, code, text}`), `schema` zawsze pierwszym kluczem, rejestr `SCHEMAS`; `AvailabilityReport` i `UpdatePlan` przechodza na ten sam koder | `to_dict` per klasa: dubel i rozjazd kluczy; `pydantic` w rdzeniu: nowa ciezka zaleznosc; `asdict` bez kontekstu: sciezki wzgledne pinow projektu, `Decimal`/`Path` niekodowalne |
| D2 | Jeden schemat `kartograf-download/1` dla `DataReport`, `CollectionReport`, `LandCoverReport`, `SoilReport`, `HsgReport` ze stalym zestawem kluczy (`raw`, `inputs`, `superseded`, `summary` puste, gdy klasa ich nie ma) | schemat na klase (piec schematow o ok. 90% wspolnych pol); rozne klucze pod jednym schematem (lamie A3) |
| D3 | Pole komunikatu zostaje `text` (`Notice.text`, JSON `text`), blad ma `message` | `message` w notice'ach (brief): zlamie `Notice.text` (publiczne), SPEC Archiwisty 5.6/7.9 i `kartograf-availability/1`; patrz O1 |
| D4 | Kody wyjscia 0, 1, 2, 130; `ValidationError`/`ParseError`/uzycie -> 2 (jak argparse), reszta bledow i `ok == false` -> 1 | wszystkie bledy 1: skrypt nie odroznia blednego wejscia od awarii zrodla; osobny kod per klasa (3, 4, 5...): agent i tak czyta `code`; patrz O2 |
| D5 | W trybie `--json` blad (takze bledy argparse) to dokument `kartograf-error/1` na stdout, stderr pusty | tekst na stderr: agent musi parsowac; dwa kanaly bledu |
| D6 | `--json` wycisza `Info:`/`Warning:` (sa w `notices`); logi ponowien transportu HTTP zostaja na stderr jako diagnostyka spoza kontraktu | notice'y na stderr i w dokumencie: dubel; calkowite wyciszenie stderr: gubi diagnostyke sieci |
| D7 | Deklaracje komend w bibliotece (`kartograf/catalog/`), argparse budowany z deklaracji (`kartograf/catalog/cliparser.py`), test kontraktowy jako dodatkowa bariera; migracja etapami z porownaniem `--help` przed/po (sekcja 13) | sam test kontraktowy: kazdy tekst `--help` w dwoch miejscach; introspekcja argparse w `get_catalog()`: biblioteka importowalaby `kartograf.cli`; katalog w `cli/`: MCP i Archiwista importowalyby CLI |
| D8 | Jeden model komendy dla CLI i API: komenda tylko-API (`find_sheets`, `store_*`) to wpis z `cli: null` | dwa katalogi (CLI, API): rozjazd i dwa formaty |
| D9 | `get_catalog()` zwraca przeglad (`view: "overview"`: grupy z nazwami produktow, komendy: id, podsumowanie, narzedzie, `supports_check`; ok. 7 tys. znakow); reszta na zadanie: `group=`, `command=`, `params=True`, `tables=True` (D22) | zawsze pelny: ok. 25-30 tys. tokenow (szacunek) na kazde wywolanie przez model; widok skrocony 0.8.0-dev (kazda komenda z opisem i polami, grupy ze zrodlami produktow, tabele kodow): zmierzone 47 807 znakow (62 389 w CLI), czyli nadal ok. 12 tys. tokenow |
| D10 | Warstwa komend w bibliotece: `parse_command` (KB-2), `validate_command` (KB-3), `format_command` (KB-4), `run_command`/`check_command` (KB-5); `data_commands()` = filtr katalogu (KB-1) | tylko katalog: MCP i Archiwista pisza wlasny dispatch po 12 funkcjach; patrz O5 |
| D11 | MCP na niskopoziomowym `mcp.server.Server` z jawnymi schematami z katalogu; wynik `CallToolResult(content, structured_content, is_error)` budowany przez serwer | `MCPServer`: schemat z sygnatur Pythona (artefakty pydantic, `title`), do modelu dociera tylko tresc `ToolError`, brak `structured_content` przy bledzie; `mcp run`/`mcp dev` dzialaja tylko z `MCPServer` (nieistotne: skrypt `kartograf-mcp`) |
| D12 | Narzedzie na komende katalogu (`elevation_download`, `boundaries_download`, ...) plus jedno narzedzie `check_updates` (tylko odczyt; parametry `tool` = nazwa narzedzia danych i `arguments` = jego argumenty) zamiast blizniaka per komenda; nazwy narzedzi z katalogu (`CommandInfo.tool`) | narzedzie na funkcje API (`download_data` dla elevation i imagery, `download_collection` dla 7 grup): 5 narzedzi danych zamiast 12, ale `collection` to zargon biblioteki, schemat to suma 17 parametrow roznych produktow; 12 blizniakow `<narzedzie>_check_updates`: 12 dodatkowych narzedzi (kontekst, gorszy wybor narzedzia przez agenta); jedno narzedzie danych z trybem `check`: `readOnlyHint` nie moze zalezec od argumentu; patrz O4 |
| D13 | `is_error` narzedzia MCP = kod wyjscia komendy CLI != 0 (takze `ok: false`); dokument jest zawsze w `content` i `structured_content` | `is_error` tylko dla wyjatkow: agent musi pamietac o sprawdzaniu `ok`; patrz O3 |
| D14 | Sciezki w argumentach narzedzi MCP musza byc bezwzgledne | wzgledne: zaleza od cwd serwera uruchomionego przez klienta |
| D15 | Postep MCP: `report_progress(n, None, tekst)` z licznikiem zdarzen `n` | `DownloadProgress.current` jako `progress`: nie rosnie scisle (status `downloading` i `completed` tej samej jednostki), a protokol wymaga wzrostu |
| D16 | `mcp` jako extra `kartograf[mcp]` (`mcp>=2.3.0,<3`), skrypt `kartograf-mcp`, rdzen bez zmian zaleznosci | `mcp` w zaleznosciach rdzenia: pydantic, starlette, uvicorn dla kazdego uzytkownika; linia 1.x: inne API serwera (dekoratory, walidacja argumentow) - dwa kody |
| D17 | `kartograf/py.typed` + `[tool.setuptools.package-data]` + `MANIFEST.in` + klasyfikator `Typing :: Typed` | sam plik: setuptools nie dolaczy go do wheel bez `package-data` |
| D18 | `llms.txt` w korzeniu repo (llmstxt.org), tekst po polsku, linki bezwzgledne do GitHub (`main`), zgodnosc polecen z katalogiem sprawdza test | linki wzgledne: nie dzialaja poza repozytorium; kopia opisu CLI: dubel katalogu |
| D19 | `scripts/gate.sh`: ruff check, ruff format --check, mypy, pytest `-m "not live"`; Python z `.venv` repozytorium albo glownego checkoutu (worktree) | `make`/`nox`: nowa zaleznosc; skrypt w Pythonie: potrzebuje Pythona do znalezienia Pythona |
| D20 | `kartograf/__main__.py` (`python -m kartograf`) wola `kartograf.cli.commands.main` | tylko skrypt `kartograf`: agent w srodowisku bez `PATH` skryptow (worktree, `uvx`) nie uruchomi CLI z kodu worktree |
| D21 | `OSError` (brak, uprawnienia, odlaczony udzial; kontrakt odczytu magazynu ADR-045 mowi o `OSError`, nie o pustym magazynie) = kod bledu `io_error`, kod wyjscia 1; budowany przez `error_report` obok `interrupted` i `internal_error`, bez nowej klasy w hierarchii `KartografError` | `internal_error` dla `OSError`: model dostaje "blad programu" za literowke w `output_dir`; klasa `StoreError(KartografError)` opakowujaca `OSError`: `OSError` leci tez z zapisu pobran, cache i projektu, wiec kazde miejsce wymagaloby opakowania; `ValidationError(option="output_dir")` tylko w nowych funkcjach: gubi odlaczony udzial (zawsze `invalid_input`, kod 2) |
| D22 | Budzet kontekstu agenta (decyzja koordynatora): `tools/list` <= 30 000 znakow (bylo 65 883), `get_catalog()` i `kartograf catalog --json` bez argumentow <= 8 000 (bylo 47 807 i 62 389). Opisy narzedzi i argumentow pisane dla wywolania (tabela `_BRIEF` w `tools.py`: kilka slow, bez flag CLI i bez powtarzania `enum`), wspolne znaczenia argumentow (obszar, sciezki, `update`, `plan`) raz w `instructions` serwera, dlugi opis (tekst `--help`) w `get_catalog(command=)`; narzedzie bez `title`; `$ref` nie jest uzywane; przeglad katalogu zapisywany jako rekord na linie (9.4, 8.1) | `$defs`/`$ref` dla powtarzanych struktur (`bbox`, `bbox_crs`, obszar): klienty nie rozwiazuja `$ref` jednolicie (Claude Code anthropics/claude-code#18260: parametr z `$ref` trafia do serwera jako napis; Codex openai/codex#3152, #13746: model widzi napis zamiast schematu) - ryzyko wiekszego kosztu niz zysk (ok. 4-6 tys. znakow); opisy z katalogu (tekst `--help`): 35 tys. znakow samych opisow parametrow; `title` obok `description`: 1,6 tys. znakow dubla pierwszego zdania; zawezanie rodzin narzedzi zamiast skracania (`--tools`): zostaje jako dodatkowe, nie zastepuje skracania |

## 5. Serializacja i dokumenty JSON

### 5.1 Mixin `Document` i koder (`kartograf/serialization.py`)

Nowy modul bez importow z reszty pakietu poza `exceptions` (typy wyniku
importuja go, nie odwrotnie). Eksportuje mixin klas `@dataclass(frozen=True)`:

```python
class Document:
    SCHEMA: ClassVar[str]                           # "kartograf-download/1"
    JSON_KEYS: ClassVar[tuple[str, ...] | None] = None   # kolejnosc kluczy po `schema`
    JSON_FILL: ClassVar[Mapping[str, object]] = {}       # wartosci kluczy bez pola i bez wlasciwosci

    @property
    def schema(self) -> str: ...                    # = SCHEMA (zachowuje atrybut report.schema)
    def to_dict(self) -> dict[str, object]: ...
    def to_json(self, *, indent: int | None = 2) -> str: ...
```

`to_dict()` zwraca obiekt: pierwszy klucz `schema`, potem klucze z `JSON_KEYS`
(`None`: pola dataclass w kolejnosci deklaracji). Wartosc klucza to pole
dataclass; gdy klasa nie ma pola - wlasciwosc o tej nazwie (np. `UpdatePlan.ok`);
gdy nie ma i jej - `JSON_FILL[klucz]` (stala lista kluczy rodziny schematu, D2).
`to_json()` = `json.dumps(to_dict(), ensure_ascii=False, indent=indent,
allow_nan=False)` i `"\n"` na koncu (dla `indent=None` separatory `(",", ":")` i
bez nowej linii - postac MCP, 9.5). Pole dataclass `schema` (dzis w
`AvailabilityReport` i `UpdatePlan`) zastepuje `ClassVar SCHEMA` i wlasciwosc
`schema`.

Reguly kodera:

| Typ w Pythonie | JSON |
|---|---|
| dataclass (kazda) | obiekt: pola w kolejnosci deklaracji; pole z `metadata={"json": False}` pominiete |
| `Document` najwyzszego poziomu | j.w. + pierwszy klucz `schema` |
| `Document` zagniezdzony | j.w., bez klucza `schema` |
| `Path` | napis `Path.absolute().as_posix()` (bez `resolve()`: nie dotyka dowiazan ani systemu plikow) |
| `tuple`, `list`, `frozenset` | tablica (zbior: posortowana) |
| `Mapping` | obiekt (klucze `str`, kolejnosc wstawiania) |
| `Decimal` | napis (`"0.5"`) |
| `datetime` | napis ISO 8601 w UTC z przesunieciem `+00:00`, do sekund |
| `BBox` | `{"bbox": [min_x, min_y, max_x, max_y], "crs": "EPSG:2180"}` (`BBoxValue`) |
| `Notice` | `{"level", "code", "text"}` (dataclass) |
| `Enum` | wartosc |
| `float` | liczba skonczona; `NaN`/`Infinity` = `ValueError` (blad programu) |
| `None`, `bool`, `int`, `str` | bez zmian |
| inny typ | `TypeError` (nigdy `str(obj)` po cichu) |

Hak `__json__(self, ctx) -> object` pozwala typowi podac wlasna reprezentacje.
Uzywaja go `PinnedFile` i `FileCheck`: w manifescie `path` i `version` sa
wzgledne do magazynu, a dokument ma sciezki bezwzgledne, wiec `Project`,
`ProjectReport` i `ProjectCheck` ustawiaja `ctx.store` (= `project.output_dir`)
przed zakodowaniem potomkow.

Kontekst kodera niesie tez `ctx.omit` (zbior par `(klasa, pole)` pomijanych w kodowaniu
dataclass): `StoreEntries` ustawia `{("Sidecar", "raw")}` (5.4.10), `StoreSidecar` nie.
`Sidecar` i `StoreEntry` sa niehashowalne (pola `dict`): koder nigdy nie opiera sie na
hashowaniu wartosci.

Rejestr `SCHEMAS: dict[str, tuple[type[Document], ...]]` wypelnia
`__init_subclass__`. Test: kazda nazwa pasuje do `^kartograf-[a-z][a-z0-9-]*/[1-9][0-9]*$`,
klasy jednego schematu maja identyczny zestaw i kolejnosc kluczy, a kazdy
`result_schema` i `check_result_schema` katalogu jest w rejestrze. Schematy
plikow (`kartograf-meta/1` sidecara, `kartograf-project/1` manifestu) nie sa
dokumentami wyniku i nie wchodza do rejestru; nazwy dokumentow ich nie powtarzaja
(dokument projektu to `kartograf-project-state/1`).

### 5.2 Reguly wspolne dokumentow

1. Dokument to obiekt JSON; pierwszy klucz `schema`; kolejnosc kluczy wg
   tabel ponizej; klucz jest zawsze obecny (brak wartosci = `null`, brak
   elementow = `[]`, nigdy pominiecie).
2. Teksty: UTF-8, `ensure_ascii=False`; teksty biblioteki (`text`, `message`,
   `hint`, opisy) sa ASCII (Z5); `text` komunikatu moze zawierac `\n`.
3. Sciezki (`path`, `version_path`, `store`, `directory`, `output_dir`...):
   napisy bezwzgledne z `/`. Wyjatki wyliczone: `request.geometry` raportu
   dostepnosci (jak podano) i `tasks[].options` projektu (postac manifestu:
   wartosci jak zapisane, sciezki wzgledem katalogu projektu, 5.4.8).
4. Czas: ISO 8601 UTC `YYYY-MM-DDTHH:MM:SS+00:00`; daty danych `YYYY-MM-DD`.
5. `bbox`: `[min_x, min_y, max_x, max_y]` (liczby) obok osobnego klucza z ukladem
   (`bbox_crs` w `request`, `crs` w obiekcie `BBoxValue`).
6. Wyliczenia (statusy, rodzaje) - male litery, `snake_case` albo wartosci
   rejestru (`pl`, `EVRF2007`, `PL-1992`); nowe wartosci sa zmiana addytywna (A3).
7. `ok` (bool) wystepuje w dokumentach z wynikiem do oceny (`kartograf-download/1`,
   `-plan/1`, `-availability/1`, `-project-report/1`, `-project-check/1`); kod
   wyjscia CLI = 0 gdy `ok` jest `true` albo dokument nie ma pola `ok`, inaczej 1
   (tabela 6.5). Dokumenty zapytan (`-sheet`, `-sheets`, `-sources`, `-layers`,
   `-project-state`, `-cache`, `-catalog`, `-store-*`) sa zawsze sukcesem.
8. Listy nigdy nie sa ucinane po cichu; gdzie jest limit
   (`kartograf-store-entries/1`) dokument niesie `limit` i `truncated`.
9. `notices` (tablica `Notice`) maja dokumenty raportow; komunikaty sa jedynym
   miejscem `Info`/`Warning` w trybie JSON (A2).
10. Nazwy kluczy sie nie tlumacza; dokument nie zalezy od jezyka konsumenta.

### 5.3 Typy zagniezdzone

| Typ | Pola (w kolejnosci) |
|---|---|
| `Notice` | `level` (`info`, `warning`), `code` (kod z `kartograf/notices.py`, np. `sheet_list`, `newer_available`), `text` (string ASCII) |
| `VersionedFile` | `path` (sciezka standardowa), `status` (`new`, `unchanged`, `relabeled`, `local`, `reused`), `label`, `sha256` (64 znaki), `version_path` (plik niezmiennej wersji), `newer` (string albo `null`), `unverified` (`"unchecked"`, `"none"`, `"check_failed: <blad>"` albo `null`), `same_as` (etykieta albo `null`) |
| `UnitFile` | `unit` (godlo, kafel, TERYT, `<wsp>` wycinka...), `country` (`PL`, `CZ`, `EU`, `GLOBAL`), `file` (`VersionedFile`) |
| `UnitFailure` | `unit`, `country`, `error` (tekst), `kind` (`no_coverage`, `download`, `country`) |
| `PlanItem` | `track` (`pl_sheet`, `laz_tile`, `cz_sheet`, `cz_laz`, `pl_cutout`, `cz_cutout`, `landcover`, `hsg`, `collection`, `cz_orto`), `segment`, `hierarchy`, `name`, `unit`, `local_label`, `local_sha256`, `available_label`, `available_signal` (obiekt albo `null`), `status` (`current`, `newer`, `missing`, `unverifiable`, `check_failed`), `error` |
| `LazTile` | `sheet`, `url`, `year`, `density`, `crs`, `min_x`, `min_y`, `max_x`, `max_y`, `footprint` (tablica par albo `null`), `date`, `full_sheet` |
| `PinnedFile` | `role` (`output`, `raw`, `input`), `unit`, `path` i `version` (bezwzgledne: `output_dir` + wartosc manifestu), `label`, `sha256`, `size_bytes` |
| `FileCheck` | `task`, `unit`, `path` (bezwzgledna), `status` (`ok`, `missing`, `corrupt`, `current`, `newer`, `added`, `removed`, `unverifiable`, `check_failed`), `pinned_label`, `available_label`, `detail` |
| `BBoxValue` | `bbox` (4 liczby), `crs` |

### 5.4 Dokumenty

Przyklady sa skrocone do jednego elementu; wartosci ilustracyjne.

#### 5.4.1 `kartograf-download/1` - wynik komend danych

Typy: `DataReport` (`elevation download`, `imagery download`), `CollectionReport`
(7 grup kolekcji), `LandCoverReport`, `SoilReport`, `HsgReport` (`soil hsg`).
Funkcje: `download_data`, `download_collection`, `download_landcover`,
`download_soil`, `calculate_hsg`. `JSON_KEYS` rodziny: `files`, `raw`, `inputs`,
`failed`, `stale`, `superseded`, `summary`, `notices`, `ok`.

| Klucz | Typ | Znaczenie |
|---|---|---|
| `schema` | string | `kartograf-download/1` |
| `files` | `UnitFile[]` | pliki wyniku (jedna wersja kazdego) |
| `raw` | `UnitFile[]` | oryginalne paczki (`keep_raw`, land cover) |
| `inputs` | `UnitFile[]` | wejscia pochodnej: clay, sand, silt dla HSG |
| `failed` | `UnitFailure[]` | jednostki, ktore sie nie powiodly |
| `stale` | `PlanItem[]` | pozycje zmienione od planu (`--upgrade --plan`) |
| `superseded` | `{tile, covered_by}[]` | kafle LAZ PL zastapione nowszymi (`tile`: `LazTile`, `covered_by`: `LazTile[]`) |
| `summary` | obiekt albo `null` | statystyki HSG (`calculate_hsg(summary=True)`, CLI `--summary`): klucze `A`, `B`, `C`, `D`, `nodata`, kazdy `{count, area_m2, area_ha, percent, description}` (wynik `hsg_statistics`) |
| `notices` | `Notice[]` | komunikaty o danych |
| `ok` | bool | brak `failed` i brak `stale` |

Klucze, ktorych klasa nie ma (wartosc z `JSON_FILL`: `[]`, a dla `summary` `null`):

| Klasa | Ma pola | Klucze z `JSON_FILL` |
|---|---|---|
| `DataReport` | `files`, `failed`, `stale`, `superseded`, `notices`, `ok` | `raw`, `inputs`, `summary` |
| `CollectionReport` | `files`, `failed`, `stale`, `notices`, `ok` | `raw`, `inputs`, `superseded`, `summary` |
| `LandCoverReport` | `files`, `raw`, `failed`, `stale`, `notices`, `ok` | `inputs`, `superseded`, `summary` |
| `SoilReport` | `files`, `failed`, `stale`, `notices`, `ok` | `raw`, `inputs`, `superseded`, `summary` |
| `HsgReport` | `files`, `inputs`, `failed`, `stale`, `notices`, `ok`, `summary` (nowe) | `raw`, `superseded` |

```json
{
  "schema": "kartograf-download/1",
  "files": [
    {
      "unit": "N-34-130-D-d-2-4",
      "country": "PL",
      "file": {
        "path": "/data/kartograf/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc",
        "status": "new",
        "label": "2022-05-10_83233",
        "sha256": "10be475e6b5c43d54b8dc832ab9816367e3dad4c1bd59bbba25c2b296a2824c6",
        "version_path": "/data/kartograf/nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_10be475e/N-34-130-D-d-2-4.asc",
        "newer": null,
        "unverified": null,
        "same_as": null
      }
    }
  ],
  "raw": [],
  "inputs": [],
  "failed": [],
  "stale": [],
  "superseded": [],
  "summary": null,
  "notices": [
    {
      "level": "info",
      "code": "sheet_list",
      "text": "Znaleziono arkuszy wg godla: 1 dla N-34-130-D-d-2-4 (NMT 1 m)\n  Arkusze: N-34-130-D-d-2-4"
    }
  ],
  "ok": true
}
```

#### 5.4.2 `kartograf-plan/1` - plan aktualizacji (`--check-updates`, `check_*`)

Typ `UpdatePlan` (istnieje; plik `--plan`). Zmiany: `schema` pierwszym kluczem;
nowe pole `notices` (komunikaty emitowane w trakcie sprawdzenia; `()` domyslnie;
`UpdatePlan.merge` laczy je bez powtorzen) i wlasciwosc `ok` (brak pozycji
`check_failed`; `JSON_KEYS` zawiera `ok`); nowa metoda `UpdatePlan.from_dict(dict)`
(`from_json` wola ja). Czytnik planu toleruje brak `notices` i `ok` (plany z
0.8.0-dev) i ignoruje `ok` (wyliczane). `JSON_KEYS`: `store`, `checked_at`,
`kartograf_version`, `items`, `notices`, `ok`.

| Klucz | Typ | Znaczenie |
|---|---|---|
| `schema` | string | `kartograf-plan/1` |
| `store` | string | katalog magazynu (bezwzgledny) |
| `checked_at` | string | chwila sprawdzenia (UTC) |
| `kartograf_version` | string | wersja Kartografa, ktora zbudowala plan |
| `items` | `PlanItem[]` | pozycje planu |
| `notices` | `Notice[]` | komunikaty sprawdzenia |
| `ok` | bool | zadna pozycja nie ma statusu `check_failed` |

```json
{
  "schema": "kartograf-plan/1",
  "store": "/data/kartograf",
  "checked_at": "2026-10-18T10:15:02+00:00",
  "kartograf_version": "0.8.0",
  "items": [
    {
      "track": "pl_sheet",
      "segment": "nmt/pl_1992_1m_evrf2007",
      "hierarchy": "N-34/130/D/d/2/4",
      "name": "N-34-130-D-d-2-4.asc",
      "unit": "N-34-130-D-d-2-4",
      "local_label": "2022-05-10_83233",
      "local_sha256": "10be475e6b5c43d54b8dc832ab9816367e3dad4c1bd59bbba25c2b296a2824c6",
      "available_label": "2025-04-02_99887",
      "available_signal": {"url": "https://opendata.geoportal.gov.pl/.../N-34-130-D-d-2-4.asc", "date": "2025-04-02"},
      "status": "newer",
      "error": null
    }
  ],
  "notices": [],
  "ok": true
}
```

#### 5.4.3 `kartograf-availability/1` - raport dostepnosci (`elevation availability`)

Typ `AvailabilityReport` (ADR-041; USAGE 2, ARCHITECTURE 4.9). Bez zmian poza
(a) `schema` pierwszym kluczem, (b) wspolnym koderem (`to_json()` wola
`Document.to_json`; tekst identyczny z dzisiejszym poza kolejnoscia klucza
`schema`). Klucze: `schema`, `request` (`product`, `country`, `sheet` albo `bbox`
+ `bbox_crs` albo `geometry` + `layer`, `min_year`, `max_year`), `checked_at`,
`areas` (`AvailabilityArea`: `country`, `crs`, `bounds` [4 liczby], `area_m2`,
`land_m2`), `combinations` (`AvailabilityCombination`: `country`, `product`,
`source`, `year`, `acquisition_dates`, `published`, `campaigns`, `horizontal`,
`resolution`, `vertical_crs`, `format`, `densities`, `complete`, `sheets_full`,
`sheets_partial`, `sheets_missing`, `uncovered`, `uncovered_m2`, `size_bytes`,
`download_hint`), `notices`, `ok`. `download_hint` to komendy po `kartograf ` albo
`kartograf project add NAZWA ` bez `--output`, np. `elevation download --product nmt
--country pl --bbox 565000,242000,569000,246000 --sheet-system 1992 --resolution 1m
--vertical-crs EVRF2007 --year 2025`.

#### 5.4.4 `kartograf-sheet/1` - opis godla (`parse`)

Nowy typ `SheetInfo`; funkcja `describe_sheet(sheet, *, hierarchy=False,
children=False, descendants=None) -> SheetInfo` (logika dzis w `cli/parse_cmd.py`:
`format_cz_sheet`, `SheetParser`, hierarchia, potomkowie; modul `kartograf/sheet_info.py`,
T4d: pole `commands` wylicza sie z deklaracji katalogu, wiec funkcja powstaje w torze
katalogu). Bez sieci. Bledy: `ParseError` (godlo spoza nomenklatur), `ValidationError` z
`option` (`hierarchy`, `children`, `descendants` dla godla CZ; nieznana skala).

| Klucz | Typ | Znaczenie |
|---|---|---|
| `schema` | string | `kartograf-sheet/1` |
| `sheet` | string | godlo w postaci kanonicznej (`SheetParser.sheet`; CZ: z rejestru) |
| `system` | string | `pl1992`, `pl2000`, `cz_sm5`, `cz_tm33` (id z `SYSTEMS` w `core/parser_registry.py`) albo `cz_ztm` (arkusz mapy topograficznej, rozpoznaje `ztm_sheet_system`) |
| `country` | string | `PL` albo `CZ` |
| `sheet_system` | string albo `null` | wartosc opcji `sheet_system`: `1992`, `2000` (PL), `sjtsk`, `etrs89` (ZTM); `null` dla SM5 i TM33 |
| `scale` | string albo `null` | `1:10000`...; `null` dla CZ |
| `components` | obiekt albo `null` | czlony godla PL w kolejnosci (`pas`, `slup`, `arkusz_200k`...; PL-2000: `strefa`, `pas`, `slup`, `ark_2k`); `null` dla CZ |
| `zone` | int albo `null` | strefa PL-2000 (5-8) |
| `crs` | string | natywny uklad arkusza (`EPSG:2180`, `EPSG:2176`..`EPSG:2179`, `EPSG:5514`, `EPSG:3045`) |
| `bounds` | `BBoxValue` albo `null` | obwiednia w `crs`; `null` dla SM5 i ZTM (rama z indeksu CUZK, wymaga sieci) |
| `commands` | string[] | id komend katalogu, ktore przyjmuja to godlo w `--sheet` (z deklaracji `ParamInfo.accepts`, 8.3) |
| `hierarchy` | `{sheet, scale}[]` albo `null` | od arkusza do 1:1000000 (`hierarchy=True`, tylko PL) |
| `children` | `{sheet, scale}[]` albo `null` | bezposredni potomkowie (`children=True`, tylko PL) |
| `descendants` | obiekt albo `null` | `{"scale", "count", "sheets"}` do skali docelowej (`descendants="1:10000"`, tylko PL; bez ucinania) |

```json
{
  "schema": "kartograf-sheet/1",
  "sheet": "N-34-130-D-d-2-4",
  "system": "pl1992",
  "country": "PL",
  "sheet_system": "1992",
  "scale": "1:10000",
  "components": {"pas": "N", "slup": "34", "arkusz_200k": "130", "arkusz_100k": "D", "arkusz_50k": "d", "arkusz_25k": "2", "arkusz_10k": "4"},
  "zone": null,
  "crs": "EPSG:2180",
  "bounds": {"bbox": [769911.0902514459, 508419.16283969115, 772163.7346478042, 510851.5730979936], "crs": "EPSG:2180"},
  "commands": ["elevation download", "elevation availability", "imagery download", "landcover download", "soil download", "soil hsg", "boundaries download", "cadastre download", "models3d download", "names download", "maps download", "geodesy download"],
  "hierarchy": null,
  "children": null,
  "descendants": null
}
```

#### 5.4.5 `kartograf-sheets/1` - godla obszaru (API i MCP: `find_sheets`)

Nowy typ `SheetList`; funkcja `find_sheets(*, bbox=None, geometry=None,
layer=None, scale, sheet_system) -> SheetList` wola `find_sheets_for_bbox` /
`find_sheets_for_geometry` (dokladnie jeden z `bbox`, `geometry`; `scale` i
`sheet_system` wymagane - bez wartosci domyslnych; wyniki tych funkcji i ich
kolejnosc bez zmian). Komenda katalogu z `cli: null` (brak komendy CLI: `elevation
download --bbox` rozwija obszar sam).

| Klucz | Typ | Znaczenie |
|---|---|---|
| `schema` | string | `kartograf-sheets/1` |
| `request` | obiekt | `scale`, `sheet_system`, `bbox` + `bbox_crs` albo `geometry` + `layer` (reszta `null`) |
| `sheets` | string[] | godla w kolejnosci biblioteki |
| `count` | int | `len(sheets)` |

#### 5.4.6 `kartograf-sources/1` - zrodla grupy (`<grupa> list-sources`, MCP `list_sources`)

Nowy typ `SourceList`; funkcja `list_sources(*, group, product=None) -> SourceList`
(rejestr zrodel, bez sieci). Logika wyboru flag per grupa (dzis `_source_choice` w
`cli/groups/*.py`) przechodzi do `kartograf/source_info.py` (T3; modul biblioteki poza
`catalog/`: katalog korzysta z rejestru, nie odwrotnie); tabela CLI
(WYBOR, KRAJ, DOSTAWCA, KATALOG, KLUCZ, NAZWA) jest renderowana z tego dokumentu
i musi dawac ten sam tekst co dzis (kontrola jednorazowa przed/po, sekcja 13).
`group`: jedna z 11 grup z `list-sources` (`elevation`, `imagery`, `landcover`,
`soil`, `boundaries`, `cadastre`, `models3d`, `hydro`, `names`, `maps`, `geodesy`).

| Klucz | Typ | Znaczenie |
|---|---|---|
| `schema` | string | `kartograf-sources/1` |
| `group` | string | grupa |
| `products` | string[] | produkty grupy (wartosci `--product`) |
| `sources` | `SourceInfo[]` | zrodla w kolejnosci rejestru |

`SourceInfo`: `key` (klucz deskryptora = pole `dataset` sidecara), `name`, `country`
(`PL`, `CZ`, `EU`, `GLOBAL`), `provider`, `product` (wartosc `--product` wybierajaca
zrodlo), `directory` (segment pod `output_dir` z `<uklad>`, `<uklad-wys>`), `select`
(obiekt: opcja -> wartosc | lista wartosci | `null` = wolny wybor z wartosci
`list-layers`; wszystkie opcje wymagane do wyboru tego zrodla, w kolejnosci flag),
`license` (`id`, `attribution`, `url`), `auth` (`none`, `clms_oauth`),
`update_signals` (suma sygnalow swiezosci kanalow: `index`, `metadata`, `http`,
`none`).

```json
{
  "schema": "kartograf-sources/1",
  "group": "elevation",
  "products": ["nmt", "nmpt", "laz", "contours"],
  "sources": [
    {
      "key": "pl.gugik.nmt_1m",
      "name": "Numeryczny Model Terenu 1 m (siatka ASC)",
      "country": "PL",
      "provider": "GUGiK",
      "product": "nmt",
      "directory": "nmt/pl_<uklad>_1m_<uklad-wys>",
      "select": {"product": "nmt", "country": "pl", "resolution": "1m", "vertical_crs": ["EVRF2007", "KRON86"]},
      "license": {"id": "PL-PGiK-40a", "attribution": "(tekst atrybucji z rejestru)", "url": ""},
      "auth": "none",
      "update_signals": ["index"]
    }
  ]
}
```

#### 5.4.7 `kartograf-layers/1` - warstwy produktu (`landcover|soil list-layers`, MCP `list_layers`)

Nowy typ `LayerList`; funkcja `list_layers(*, group, product=None) -> LayerList`
(`landcover`: `product` wymagany; `soil`: bez `product`). Bez sieci i bez zapisu;
logika dzis w `cli/landcover_cmd.py` i `cli/soil_cmd.py` (provider przez
`LandCoverManager`) przechodzi do `kartograf/source_info.py` (obok `list_sources`).

| Klucz | Typ | Znaczenie |
|---|---|---|
| `schema` | string | `kartograf-layers/1` |
| `group` | string | `landcover` albo `soil` |
| `product` | string albo `null` | `bdot10k`, `bdoo`, `corine`, `zabaged`, `data50`, `data250`; `null` dla `soil` |
| `source` | string | nazwa zrodla (naglowek "Warstwy zrodla ...") |
| `layers` | `{code, description}[]` | warstwy (BDOT10k: kod + opis; ZABAGED/Data50/Data250: nazwa uslugi, `description` `null`); `[]` dla pozostalych |
| `classes` | obiekt albo `null` | BDOO: rocznik (string) -> lista kodow klas |
| `years` | `{year, data, description}[]` albo `null` | CORINE: `data` = `clms` (dane CLMS, bez poswiadczen podglad WMS) albo `wms` (tylko podglad) |
| `properties` | `{code, description}[]` albo `null` | SoilGrids: wlasciwosci |
| `depths` | string[] albo `null` | SoilGrids: przedzialy glebokosci |
| `statistics` | `{code, description}[]` albo `null` | SoilGrids: statystyki |

#### 5.4.8 Dokumenty projektu

Typy istnieja (`Project`, `ProjectReport`, `ProjectCheck`), dostaja `Document`.
Sciezki plikow pinow sa bezwzgledne (hak `__json__`, 5.1); `tasks[].options` to
postac manifestu (ADR-040): `bbox` jako 4 liczby + `bbox_crs`, sciezki jak zapisane,
wartosc per kraj jako napis albo `{"pl", "cz"}`, listy jako tablice, bez `null`/`false`.

`kartograf-project-state/1` (`Project`; `init_project`, `add_project_task`,
`remove_project_task`, `open_project`): `schema`, `directory`, `output_dir`,
`tasks[]` = `{name, command, options, pinned_at, kartograf_version,
geometry_sha256 (obiekt albo null), files: PinnedFile[]}`.

`kartograf-project-report/1` (`ProjectReport`; `download_project`): `schema`,
`project` (jak `project-state` bez klucza `schema`), `tasks[]` = `{name, outcome
(pinned, unchanged, restored, updated, failed), pinned: PinnedFile[], unpinned:
PinnedFile[], errors: string[]}`, `notices`, `ok`.

`kartograf-project-check/1` (`ProjectCheck`; `get_project_status`, `verify_project`,
`check_project`): `schema`, `project` (jak wyzej), `files: FileCheck[]`,
`not_downloaded: string[]`, `notices`, `ok`.

```json
{
  "schema": "kartograf-project-check/1",
  "project": {
    "directory": "/home/ola/projekty/wisla",
    "output_dir": "/srv/dane/kartograf",
    "tasks": [
      {
        "name": "teren",
        "command": "elevation download",
        "options": {"product": "nmt", "sheet": "N-34-130-D-d-2-4", "resolution": "1m", "vertical_crs": "EVRF2007"},
        "pinned_at": "2026-10-20T08:15:02+00:00",
        "kartograf_version": "0.8.0",
        "geometry_sha256": null,
        "files": [
          {
            "role": "output",
            "unit": "N-34-130-D-d-2-4",
            "path": "/srv/dane/kartograf/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc",
            "version": "/srv/dane/kartograf/nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_10be475e/N-34-130-D-d-2-4.asc",
            "label": "2022-05-10_83233",
            "sha256": "10be475e6b5c43d54b8dc832ab9816367e3dad4c1bd59bbba25c2b296a2824c6",
            "size_bytes": 41029733
          }
        ]
      }
    ]
  },
  "files": [
    {
      "task": "teren",
      "unit": "N-34-130-D-d-2-4",
      "path": "/srv/dane/kartograf/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc",
      "status": "ok",
      "pinned_label": "2022-05-10_83233",
      "available_label": null,
      "detail": null
    }
  ],
  "not_downloaded": [],
  "notices": [],
  "ok": true
}
```

#### 5.4.9 `kartograf-cache/1` - cache metadanych (`cache stats|path|clear`)

Nowy typ `CacheInfo`; funkcje `get_cache_info() -> CacheInfo` (`stats` i `path`: ta
sama funkcja; nie tworzy brakujacej bazy) i `clear_cache() -> CacheInfo` (logika dzis
w `cli/cache_cmd.py`; baze nieczytelna usuwa razem z `-wal` i `-shm`; baze zablokowana
przez inny proces zglasza jako `CacheError`, nigdy jej nie usuwa). Cache to
`<cwd>/.kartograf_cache.db` (Z6).

| Klucz | Typ | Znaczenie |
|---|---|---|
| `schema` | string | `kartograf-cache/1` |
| `action` | string | `info` albo `clear` |
| `path` | string | bezwzgledna sciezka pliku bazy |
| `exists` | bool | czy plik istnieje |
| `size_bytes` | int albo `null` | rozmiar bazy; `null` bez pliku |
| `entries` | obiekt albo `null` | `records`, `campaigns`, `teryt`, `sheets`, `index_areas`, `atom_feeds` (liczby wpisow); `null` dla `clear` i bez pliku |
| `cleared` | bool albo `null` | `true` po `clear`; `null` dla `info` |
| `removed_unreadable` | bool albo `null` | `clear`: usunieto nieczytelny plik; `null` dla `info` |

#### 5.4.10 Dokumenty odczytu magazynu (API i MCP; ADR-045)

Nowe typy opakowuja istniejace obiekty odczytu w dokumenty (A1: serializacja w
bibliotece; strumieniowe `list_segments`, `iter_store`, `read_sidecar` bez zmian).
Kontrakt odczytu po przegladzie (ADR-045, ARCHITECTURE 3.3.1) zostaje: bledne argumenty
to `ValidationError` (z `option`, 6.1), brak albo niedostepny `output_dir` to `OSError`
(`io_error`, 6.2), brak albo nieczytelny sidecar to `InvalidSidecarError`:

- `kartograf-store-overview/1`: `describe_store(output_dir) -> StoreOverview` =
  `list_segments` + `describe_segment` dla kazdego segmentu. Klucze: `schema`,
  `output_dir`, `segments[]` = `SegmentInfo` (`segment`, `product`, `country`,
  `dataset_key`, `name`, `known`).
- `kartograf-store-entries/1`: `list_store_entries(output_dir, *, segment,
  units=None, limit) -> StoreEntries` = pierwsze `limit` wpisow `iter_store(segment=,
  units=)`. Klucze: `schema`, `output_dir`, `segment`, `units` (tablica albo `null`),
  `limit`, `truncated` (byly dalsze wpisy), `entries[]` = `StoreEntry` (`kind`,
  `segment`, `hierarchy`, `name`, `path`, `version_path`, `label`, `sha8`, `sidecar`,
  `problem`, `skipped`; `sidecar` = pola `Sidecar` bez `raw`). `segment` i `limit`
  (liczba >= 1) sa wymagane: pelny skan magazynu z 80 tys. wersji nie jest
  odpowiedzia dla modelu. `units` to nazwy jednostek jak w `iter_store(units=)` (nie
  prefiksy); `sidecar.unit` wpisu jest wartoscia przyjmowana przez `units` tego samego
  segmentu (plik krajowy z motywem: `pl_miejscowosci`), wiec agent odswieza jedna
  jednostke bez zgadywania nazwy; nazwy zarezerwowane (`versions`, `full_sheet`,
  `kampanie`) i dluzsze niz 255 bajtow to `invalid_input` z `details.option` = `units`.
  `skip_versions` nie jest wystawione (dokument nie ma wlasnego indeksu).
- `kartograf-store-sidecar/1`: `read_store_sidecar(path) -> StoreSidecar`. Klucze:
  `schema`, `path`, `sidecar` (wszystkie pola `Sidecar`, z `raw`; zagniezdzone pole
  `schema` jest zawsze `kartograf-meta/1`, takze gdy `raw` nie ma pola `schema`:
  sidecar w ksztalcie `emit_sidecar`). `InvalidSidecarError` -> `kartograf-error/1`
  (`invalid_sidecar`, `details.path`).

### 5.5 Typy -> dokumenty -> funkcje

| Typ (`kartograf.__all__`) | Schemat | Funkcje biblioteki | Komenda CLI |
|---|---|---|---|
| `DataReport`, `CollectionReport`, `LandCoverReport`, `SoilReport`, `HsgReport` | `kartograf-download/1` | `download_data`, `download_collection`, `download_landcover`, `download_soil`, `calculate_hsg` | `<grupa> download`, `soil hsg` |
| `UpdatePlan` | `kartograf-plan/1` | `check_data`, `check_collection`, `check_landcover`, `check_soil`, `check_hsg`, `check_command` | `... --check-updates` |
| `AvailabilityReport` | `kartograf-availability/1` | `check_availability` | `elevation availability` |
| `SheetInfo` (nowy) | `kartograf-sheet/1` | `describe_sheet` | `parse` |
| `SheetList` (nowy) | `kartograf-sheets/1` | `find_sheets` | - |
| `SourceList` (nowy) | `kartograf-sources/1` | `list_sources` | `<grupa> list-sources` |
| `LayerList` (nowy) | `kartograf-layers/1` | `list_layers` | `landcover list-layers`, `soil list-layers` |
| `Project` | `kartograf-project-state/1` | `init_project`, `add_project_task`, `remove_project_task`, `open_project` | `project init`, `add`, `remove` |
| `ProjectReport` | `kartograf-project-report/1` | `download_project` | `project download` |
| `ProjectCheck` | `kartograf-project-check/1` | `get_project_status`, `verify_project`, `check_project` | `project status`, `verify`, `download --check-updates` |
| `CacheInfo` (nowy) | `kartograf-cache/1` | `get_cache_info`, `clear_cache` | `cache stats`, `path`, `clear` |
| `Catalog` (nowy) | `kartograf-catalog/1` | `get_catalog` | `catalog` |
| `ErrorReport` (nowy) | `kartograf-error/1` | `error_report` | kazda komenda przy bledzie |
| `StoreOverview`, `StoreEntries`, `StoreSidecar` (nowe) | `kartograf-store-overview/1`, `-store-entries/1`, `-store-sidecar/1` | `describe_store`, `list_store_entries`, `read_store_sidecar` | - |

Wszystkie nowe nazwy dochodza do `kartograf.__all__`. Nowe funkcje maja argumenty
tylko nazwane (`*` na poczatku, jak `download_data`), z jednym wyjatkiem: argument
identyfikujacy obiekt jest pozycyjny, jak w `read_sidecar(path)`,
`list_segments(output_dir)` i `open_project(project_dir)` - `describe_sheet(sheet,
*, ...)`, `describe_store(output_dir)`, `list_store_entries(output_dir, *, ...)`,
`read_store_sidecar(path)`; reszta (`find_sheets`, `list_sources`, `list_layers`,
`get_catalog`, `get_cache_info`, `clear_cache`) jest w calosci nazwana.

## 6. Bledy: kody, podpowiedzi, kody wyjscia

### 6.1 Atrybuty wyjatkow (`kartograf/exceptions.py`, `transform/crs.py`)

Zmiany sa addytywne (konstruktory dostaja opcjonalne argumenty nazwane; kazde
dotychczasowe wywolanie dziala):

| Atrybut | Rodzaj | Znaczenie |
|---|---|---|
| `code` | `ClassVar[str]`, `snake_case` | stabilny kod bledu; **zdefiniowany w `__dict__` kazdej klasy** (nie dziedziczony po cichu); test sprawdza unikalnosc i wzorzec `^[a-z][a-z0-9_]*$` |
| `exit_code` | `ClassVar[int]` | kod wyjscia CLI dla tego bledu (6.5) |
| `hint` | atrybut instancji (`str` albo `None`), argument `hint=` konstruktora | podpowiedz ustawiona w miejscu zgloszenia (ASCII, jedna linia) |
| `DETAIL_FIELDS` | `ClassVar[tuple[str, ...]]` | nazwy atrybutow, ktore trafiaja do `details` dokumentu bledu |
| `details()` | metoda | `{pole: wartosc}` z `DETAIL_FIELDS` (tylko niepuste; kodowane koderem 5.1) |
| `DEFAULT_HINT` | `ClassVar[str]` albo `None` | podpowiedz klasy, gdy instancja jej nie ma |

`ValidationError(message, *, option=None, options=None, allowed=None, hint=None)`:
`option` = nazwa argumentu API, ktorego dotyczy blad (np. `vertical_crs`; nazwa z
katalogu, nie flaga), `options` = grupa argumentow w konflikcie (`("sheet", "bbox")`),
`allowed` = dozwolone wartosci (`tuple[str, ...]`); `DETAIL_FIELDS = ("option",
"options", "allowed")`. To realizuje KB-3 ("`ValidationError` z nazwa opcji") i
pozwala modelowi poprawic dokladnie jeden argument.

Nowa klasa `UsageError(ValidationError)`: bledne uzycie komendy (nieznana flaga albo
komenda, brak argumentu pozycyjnego, wartosc spoza `choices` parsera). Zglasza ja
parser katalogu (`parse_command`, CLI w trybie `--json`); `code = "usage_error"`.

Pozostale klasy: `DownloadError.DETAIL_FIELDS = ("sheet", "status_code")`;
`NoCoverageError`: `+ "hints"`; `YearRangeError`: `("sheets", "min_year",
"max_year", "hints")`; `InvalidSidecarError`: `("path",)` i `DEFAULT_HINT = "Podaj
sciezke pliku danych magazynu albo jego sidecara <plik>.meta.json (kartograf-meta/1)"`;
`TransformUnavailableError`: `("rejected", "remedy")`; `CacheError.DEFAULT_HINT =
"Wyczysc cache: kartograf cache clear"`.

Obowiazkowe miejsca ustawiania `option`/`allowed` (test sprawdza kazdy scenariusz):
wspolne walidatory (`download/options.py`: `require_product`, wybor `resolution`,
`vertical_crs`, `format`, `model`, `scale`, `sheet_system`, `country`, lata;
`download/collections.py`: `require_collection_product`, `validate_collection_request`;
`landcover/manager.py`: `require_landcover_product`, `validate_landcover_request`,
`validate_soil_request`; `hydrology/hsg.py`: `validate_hsg_request`; `output_required`;
`validate_request_bbox`/`parse_bbox_arg`; zgloszenia "wymagane" i "niedozwolone"
opcji), argumenty projektu (`name`, `command`) oraz walidatory odczytu magazynu
(`store.py`: nieprawidlowy segment -> `option="segment"`, nieprawidlowa jednostka albo
`units` bez `segment` -> `option="units"`) i nowych funkcji biblioteki (`limit`,
`group` i `product` w `list_sources`/`list_layers`, `scale` i `sheet_system` w
`find_sheets`, `hierarchy`/`children`/`descendants` w `describe_sheet`). Pozostale
`ValidationError` bez `option` sa dozwolone (`option: null`); regula STANDARDS 11.1
zostaje: informacje dla wywolujacego sa atrybutami, nigdy wyciagnietymi z tekstu.

### 6.2 Taksonomia: wyjatek -> kod -> kod wyjscia -> podpowiedz

| Wyjatek | `code` | `exit_code` | Kiedy | `hint` (zrodlo) |
|---|---|---|---|---|
| `KartografError` (sama klasa bazowa) | `kartograf_error` | 1 | blad pakietu bez dokladniejszej klasy | - |
| `ValidationError` | `invalid_input` | 2 | bledna wartosc albo kombinacja argumentow, brak wymaganego argumentu, bledny plik wejsciowy (plan, manifest, geometria) | `exc.hint`; inaczej z `option`/`allowed` i katalogu: `Dozwolone wartosci --<flaga>: a, b, c. Przyklad: kartograf <komenda> ...` |
| `UsageError` (nowa, `ValidationError`) | `usage_error` | 2 | nieznana komenda/flaga, brak argumentu pozycyjnego, wartosc spoza `choices` | `kartograf catalog <grupa> <komenda> --params` |
| `ParseError` (`ValidationError`) | `invalid_sheet_code` | 2 | godlo nie jest godlem PL ani CZ albo jest poza nomenklatura | formaty godel: PL-1992 `N-34-130-D-d-2-4`, PL-2000 `6.179.12.20`, SM5 `CTES96`, TM33 `302_5550`; `kartograf parse --help` |
| `DownloadError` | `download_failed` | 1 | siec, HTTP, timeout, odpowiedz zrodla | `exc.hint`; inaczej - |
| `NoCoverageError` (`DownloadError`) | `no_coverage` | 1 | zrodlo nie ma danych dla arkusza (stan danych, ponowienie nie pomoze) | `hints` wyjatku (te same teksty co po kropce w komunikacie) |
| `YearRangeError` (`DownloadError`) | `year_out_of_range` | 1 | dane sa, ale poza przedzialem lat (przed pobraniem) | `hints` wyjatku (propozycje flag) |
| `CacheError` | `cache_error` | 1 | cache SQLite niedostepny (`strict`), zablokowany albo nieczytelny | `Wyczysc cache: kartograf cache clear` |
| `InvalidSidecarError` | `invalid_sidecar` | 1 | sidecar `kartograf-meta/1` nie istnieje, jest nieczytelny, nie jest obiektem JSON albo ma inny schemat (`read_sidecar`, `read_store_sidecar`; brak pola `schema` przyjmowany tylko w ksztalcie `emit_sidecar`); skan `iter_store` go nie zglasza (wpis `problem`) | `DEFAULT_HINT` (`details.path`) |
| `TransformError` | `transform_failed` | 1 | blad przeliczenia wspolrzednych (np. wynik nieskonczony) | - |
| `TransformUnavailableError` (`TransformError`) | `transform_unavailable` | 1 | brak bezpiecznej operacji dla pary ukladow | `remedy` |
| `OSError` (`FileNotFoundError`, `PermissionError`...) | `io_error` | 1 | katalog albo plik niedostepny: brak, uprawnienia, brak miejsca, odlaczony udzial; m.in. `describe_store` i `list_store_entries` na nieistniejacym `output_dir` (kontrakt ADR-045: brak magazynu to `OSError`, nie pusty magazyn) | `Sprawdz sciezke i uprawnienia: <exc.filename>` |
| `KeyboardInterrupt` (CLI, serwer) | `interrupted` | 130 | Ctrl-C / SIGINT | - |
| kazdy inny `Exception` poza `OSError` (`KeyError`, `ValueError` niezmiennika, `RuntimeError`, `TypeError`) | `internal_error` | 1 | blad programu | `Zglos blad z komenda i wersja; KARTOGRAF_DEBUG=1 pokazuje traceback` |

`KeyboardInterrupt`, `OSError` i wyjatki spoza hierarchii nie maja klas `code`: kody
`interrupted`, `io_error` i `internal_error` buduje `error_report` (6.3). Kolejne kody
wolno dodawac (A3); zmiana albo usuniecie istniejacego to zmiana lamiaca.

### 6.3 Dokument `kartograf-error/1` (`ErrorReport`, `error_report`)

Nowy modul `kartograf/error_report.py` (importuje `exceptions` i `serialization`;
katalog dociaga leniwie): dataclass `ErrorReport(Document)` i funkcja
`error_report(exc, *, command=None) -> ErrorReport`.

| Klucz | Typ | Znaczenie |
|---|---|---|
| `schema` | string | `kartograf-error/1` |
| `code` | string | kod z 6.2 |
| `message` | string | tekst bledu (ASCII) - dokladnie to, co CLI wypisuje po `Error: ` |
| `hint` | string albo `null` | podpowiedz (wynik algorytmu ponizej) |
| `exception` | string | nazwa klasy wyjatku (`type(exc).__name__`) |
| `exit_code` | int | kod wyjscia z 6.5 |
| `command` | string albo `null` | id komendy katalogu, w ktorej wystapil blad (CLI i MCP znaja ja z kontekstu; biblioteka bez kontekstu: `null`) |
| `details` | obiekt | `exc.details()`; `{}` gdy brak atrybutow; dla `OSError` `{"errno": "ENOENT", "path": "<exc.filename>"}` (tylko niepuste pola; `errno` jako nazwa symboliczna) |

Algorytm `hint` (deterministyczny, jedna linia ASCII, najwyzej 400 znakow):

1. `exc.hint`, gdy ustawiony;
2. `DEFAULT_HINT` klasy, a dla `NoCoverageError`/`YearRangeError` - `hints` wyjatku
   polaczone `"; "`, dla `TransformUnavailableError` - `remedy`, dla `OSError` - `Sprawdz
   sciezke i uprawnienia: <exc.filename>` (bez nazwy pliku: `Sprawdz sciezki i
   uprawnienia katalogow z argumentow`);
3. dla `ValidationError` z `option`: skladniki (a) `Dozwolone wartosci <flaga>: a, b,
   c.` (z `allowed`, najwyzej 40 wartosci i `...`; flaga z katalogu, gdy `command` znana
   i parametr istnieje, inaczej nazwa `option`), (b) `Przyklad: <command_line>` -
   pierwszy przyklad komendy z katalogu, ktory uzywa tej opcji, a gdy zaden nie
   uzywa, pierwszy przyklad komendy; (a) i (b) laczone spacja;
4. w przeciwnym razie `null`.

```json
{
  "schema": "kartograf-error/1",
  "code": "invalid_input",
  "message": "--vertical-crs wymagane: EVRF2007 (...), KRON86 (...)",
  "hint": "Dozwolone wartosci --vertical-crs: EVRF2007, KRON86. Przyklad: kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 -o ./data",
  "exception": "ValidationError",
  "exit_code": 2,
  "command": "elevation download",
  "details": {"option": "vertical_crs", "allowed": ["EVRF2007", "KRON86"]}
}
```

### 6.4 Raport z `ok: false` nie jest bledem

Czesciowa porazka (jednostki w `failed`, `stale`, `check_failed` w planie, projekt
niepelny) to **wynik**: komenda zwraca dokument wyniku z `ok: false` i kod 1. Blad
(`kartograf-error/1`) oznacza, ze wyniku nie udalo sie zbudowac. Agent odroznia
je po `schema`; `ok` jest rozstrzygajace tylko w dokumentach wyniku.

### 6.5 Jedna tabela kodow wyjscia

Trafia do `docs/USAGE.md` (razem z tabela 6.2) i do katalogu (`exit_codes`):

| Kod | Nazwa | Znaczenie | Stdout w trybie `--json` |
|---|---|---|---|
| 0 | `ok` | komenda wykonana; dokument wyniku z `ok: true` albo dokument bez pola `ok` | dokument wyniku |
| 1 | `failed` | brak kompletnego wyniku: blad zrodla, sieci, cache, magazynu, blad programu, albo `ok: false` | dokument wyniku (`ok: false`) albo `kartograf-error/1` |
| 2 | `usage` | bledne uzycie albo bledne dane wejsciowe: argparse, `ValidationError`, `ParseError`, `UsageError` | `kartograf-error/1` |
| 130 | `interrupted` | przerwane przez uzytkownika (128 + SIGINT); wersje zatwierdzane atomowo, brak polowicznych plikow | `kartograf-error/1` |

Zmiana wzgledem 0.8.0-dev: bledy wejscia (`ValidationError`, `ParseError`) koncza
sie kodem 2, nie 1 (D4, O2); argparse konczyl sie 2 juz wczesniej.

### 6.6 Zachowanie warstw

- **Biblioteka**: bez zmian kontraktu Z4; wyjatki jak dotad, nowe atrybuty;
  `error_report(exc, command=None)` jest narzedziem dla CLI, MCP i konsumentow.
- **CLI** (`main`): wykrywa tryb JSON przed parsowaniem (`--json` wsrod tokenow
  argumentow) i ustawia go na parserze; potem:
  - `UsageError`/argparse w trybie JSON: dokument na stdout, kod 2, stderr pusty
    (bez trybu JSON: dotychczasowy tekst `usage:` + komunikat na stderr, kod 2);
  - `KartografError`: tryb JSON - `error_report(e, command=<id>)` na stdout, kod
    `e.exit_code`; bez JSON - `Error: <message>` na stderr jak dotad (podpowiedz
    nie jest drukowana drugi raz: teksty `hints` sa juz w komunikacie), kod `e.exit_code`;
  - `KeyboardInterrupt`: kod 130 (JSON: `interrupted`; bez JSON: `Error: przerwano (Ctrl-C)`);
  - `OSError`: kod 1 (JSON: `io_error`; bez JSON jak inny `Exception`);
  - inny `Exception`: kod 1 (JSON: `internal_error`; bez JSON: `Error: <Typ>: <tekst>` + linia
    o `KARTOGRAF_DEBUG`, jak dotad);
  - `KARTOGRAF_DEBUG=1`: wyjatek jest podnoszony ponownie (takze w trybie JSON).
  Handlery `cmd_*` nie drukuja juz wlasnych `Error:` ani nie zwracaja 1 za bledy
  wejscia (np. brak `--output`, brak `--product`): zglaszaja `ValidationError` z
  `option`, a `main` je tlumaczy (jedna sciezka bledow, kod 2).
- **MCP**: kazdy wyjatek handlera narzedzia -> `error_report` -> wynik z
  `is_error=True` (9.5); `KeyboardInterrupt` nie dotyczy serwera (zamkniecie strumienia
  konczy proces).

## 7. CLI: `--json` w kazdej komendzie

### 7.1 Kontrakt trybu `--json`

Flaga `--json` (bez skrotu) jest w kazdej komendzie-lisciu CLI (36 dzisiejszych i
`catalog`); deklaruje sie ja raz jako parametr wspolny katalogu (`json`: rodzaj
`flag`, tylko CLI, `argument: null`). Pozycja: za komenda
(`kartograf elevation availability --json ...`); `kartograf --json ...` nie istnieje.

1. **stdout** = dokladnie jeden dokument JSON (`to_json()`: wciecie 2 spacje,
   `\n` na koncu; wyjatek: przeglad katalogu, 8.1 - rekord grupy i komendy w jednej
   linii), nic wiecej: ani pasek postepu, ani linie statusu, ani naglowek
   `SHEET_LIST` (jest w `notices`). CLI ustawia kodowanie stdout na UTF-8
   (`sys.stdout.reconfigure(encoding="utf-8")`), niezaleznie od lokalizacji.
2. **stderr** jest pusty z dwoma wyjatkami spoza kontraktu: linie ponowien
   transportu HTTP (`Warning:` z loggera `kartograf.transport.http`, D6) i traceback
   przy `KARTOGRAF_DEBUG=1`. CLI nie przekazuje `on_notice` ani `on_progress`
   (komunikaty sa w `notices`, postepu w tym trybie nie ma).
3. **Kod wyjscia** wg 6.5 i reguly R7 (5.2): 0, gdy dokument nie ma `ok` albo
   `ok: true`; 1, gdy `ok: false` (dokument i tak jest wydrukowany); 2/1/130 dla
   bledow (`kartograf-error/1`).
4. `--quiet`/`-q` w trybie JSON dozwolone i bez efektu. `--plan PLIK` dziala jak
   dotad (odczyt przy `--upgrade`, zapis przy `--check-updates`); linia `Info:
   zapisano plan aktualizacji` nie jest drukowana (plik to ten sam dokument co
   stdout). `soil hsg --json --summary` zwraca `summary` w dokumencie.
5. `--json` nie jest czescia zadania projektu: `project add ... --json` jest
   odrzucone `ValidationError` (jak `--workers`, `--summary`); `project add` parsuje
   komende przez `parse_command` (8.7) i widzi `--json` w `CommandCall.run`.
6. Bez `--json` zachowanie jest bez zmian (tekst), z wyjatkami: kod 2 dla bledow
   wejscia (6.5), tabele `list-sources`/`list-layers` i `parse` renderowane z
   dokumentu biblioteki (ten sam tekst co dzis - kontrola jednorazowa przed/po,
   sekcja 13), `cache`/`parse` przez nowe funkcje biblioteki.

### 7.2 Komendy, funkcje i dokumenty

| Komenda CLI | Funkcja biblioteki | Dokument (stdout `--json`) | Kod 1, gdy |
|---|---|---|---|
| `elevation download`, `imagery download` | `download_data` | `kartograf-download/1` | `ok: false` |
| `boundaries`, `cadastre`, `models3d`, `hydro`, `names`, `maps`, `geodesy download` | `download_collection` | `kartograf-download/1` | `ok: false` |
| `landcover download` | `download_landcover` | `kartograf-download/1` | `ok: false` |
| `soil download` | `download_soil` | `kartograf-download/1` | `ok: false` |
| `soil hsg` (`--summary`) | `calculate_hsg(summary=)` | `kartograf-download/1` | `ok: false` |
| kazda z powyzszych z `--check-updates` | `check_data`, `check_collection`, `check_landcover`, `check_soil`, `check_hsg` | `kartograf-plan/1` | pozycja `check_failed` |
| `elevation availability` | `check_availability` | `kartograf-availability/1` | `ok: false` |
| `<grupa> list-sources` (11 grup) | `list_sources(group=)` | `kartograf-sources/1` | - |
| `landcover list-layers`, `soil list-layers` | `list_layers` | `kartograf-layers/1` | - |
| `parse` | `describe_sheet` | `kartograf-sheet/1` | - |
| `project init`, `add`, `remove` | `init_project`, `add_project_task`, `remove_project_task` | `kartograf-project-state/1` | - |
| `project download` | `download_project` | `kartograf-project-report/1` | `ok: false` |
| `project download --check-updates` | `check_project` | `kartograf-project-check/1` | `ok: false` |
| `project status`, `project verify` | `get_project_status`, `verify_project` | `kartograf-project-check/1` | `ok: false` |
| `cache stats`, `cache path` | `get_cache_info` | `kartograf-cache/1` | - |
| `cache clear` | `clear_cache` | `kartograf-cache/1` | - |
| `catalog` | `get_catalog` | `kartograf-catalog/1` | - |

`soil hsg --summary` bez `--json` drukuje statystyki z `report.summary` (dzis CLI
wola `hsg_statistics` po obliczeniu - logika poza biblioteka); `hsg_statistics` zostaje
funkcja publiczna.

### 7.3 Logika przenoszona z CLI do biblioteki (Z1)

`--json` wymaga, by wynik kazdej komendy byl typem biblioteki. Dzis poza regula Z1
sa i przechodza do biblioteki: opis godla (`describe_sheet`: `format_cz_sheet`,
hierarchia, potomkowie), tabele zrodel i wybor flag per grupa (`list_sources`:
`_source_choice`, `_product_flag` z `cli/groups/*.py`), warstwy produktow
(`list_layers`: provider przez `LandCoverManager`), obsluga cache (`get_cache_info`,
`clear_cache`), statystyki HSG po obliczeniu (parametr `summary`). W `cli/` zostaje:
parsowanie flag, odczyt/zapis pliku planu, wyliczenie kodu wyjscia, renderowanie
tekstu z dokumentow (tabele, linie statusu, pasek postepu) i wybor trybu JSON.
`tests/test_cli_translation.py::test_cli_imports_no_data_logic` dopuszcza import
`kartograf.catalog` i `kartograf.serialization`; nadal zabrania `providers`,
`transport` i doboru arkuszy.

### 7.4 Komenda `catalog`

`kartograf catalog [GRUPA [KOMENDA]] [--params] [--json]` = `get_catalog(group=,
command=, params=)` (8.5). Bez `--json` drukuje tekst: grupy z produktami i
komendami (jedna linia na komende: id, rodzaj, podsumowanie); z `GRUPA` komendy
grupy; z `GRUPA KOMENDA` opis i parametry (tabela: flaga, argument API, rodzaj,
wymagany, dozwolone wartosci, opis) i przyklady; `--params` dodaje parametry do widoku
grupy i calosci. Z `--json` bez `GRUPY` i `KOMENDY`: przeglad (`view: "overview"`,
do 8000 znakow; D9, D22); z `GRUPA`, `KOMENDA` albo `--params`: widok pelny (8.1).
Tabele kodow (`tables=True`) ma `get_catalog` w API i MCP oraz caly katalog z
parametrami (`--params --json` bez `GRUPY`); osobnej flagi `--tables` CLI nie ma
(mozliwe rozszerzenie: parametr `tables` bez `flag=None`, a w `cmd_catalog`
`tables=True if args.tables else None`). Komenda jest zapytaniem (bez sieci, bez
zapisu), nie komenda danych projektu (bez `_task`).

### 7.5 Pozostale zmiany CLI

- `kartograf/__main__.py` (3 linie): `python -m kartograf ...` = `kartograf ...`
  (D20). `python -m kartograf.cli.commands` dziala nadal.
- `--version`, `--help` bez zmian i bez trybu JSON.
- Przyklady w `--help` (`epilog`) pochodza z przykladow katalogu (8.4).

## 8. Katalog komend

### 8.1 Model dokumentu `kartograf-catalog/1`

Typy (`kartograf/catalog/model.py`, `Document`): `Catalog`, `GroupInfo`,
`ProductInfo`, `CommandInfo`, `ParamInfo`, `ConstraintInfo`, `ExampleInfo`,
`ExitCodeInfo`, `ErrorCodeInfo`, `SchemaInfo`. Wszystkie teksty po polsku, ASCII.

`Catalog` - klucze: `schema` (`kartograf-catalog/1`), `view` (`overview` albo `full`),
`kartograf_version`, `language` (`pl`), `groups` (`GroupInfo[]`), `commands`
(`CommandInfo[]`), `exit_codes` (`{code, name, meaning}[]`, tabela 6.5), `errors`
(`{code, exception, exit_code, meaning}[]`, tabela 6.2), `schemas` (`{schema,
description, produced_by}[]`; `produced_by` = id komend, kolejnosc jak w `SCHEMAS`).
Zestaw kluczy jest ten sam w kazdym widoku (5.2 punkt 1); tabele `exit_codes`,
`errors`, `schemas` sa `null`, dopoki nie zostana zazadane (`tables=True`, 8.5).

**Widoki** (`Catalog.view`; D9, D22). Przeglad (`overview`) to to, co agent czyta
najpierw, wiec jego dokument jest krotkim rzutem tych samych obiektow (do 8000 znakow;
bylo 47 807):

- `groups[]`: `{name, summary, products}`, gdzie `products` to tablica nazw produktow
  (nie `ProductInfo`);
- `commands[]`: `{id, summary, tool, supports_check}` (`tool`: `null`, gdy komenda nie
  jest narzedziem MCP);
- pozostale pola `GroupInfo`, `ProductInfo` i `CommandInfo` oraz parametry, ograniczenia,
  przyklady i tabele sa pod zapytaniem szczegolowym: `group=` (opis grupy, produkty z
  `summary`, `countries`, `sources`, komendy grupy z opisem i polami), `command=`
  (komenda z `params`, `constraints`, `examples`), `params=True`, `tables=True`.

Widok pelny (`full`: wybrano grupe albo komende albo `params=True`) ma kazde pole
obiektow. Obiekty w pamieci (`get_catalog().groups[0].description`) maja ZAWSZE
wszystkie pola - rzut dotyczy tylko dokumentu (`to_dict()`, `to_json()`), wiec
wywolujacy biblioteke nie pyta drugi raz, a tekst CLI (`kartograf catalog`) drukuje
z tych samych obiektow. `to_json()` przegladu zapisuje rekord grupy i komendy w jednej
linii (wciecie 2 spacje poziomu listy; `to_json(indent=None)` jak zawsze zwarty): ten
sam dokument, ok. jedna czwarta krocej niz wciecie kazdego klucza (CLI: 7 629 znakow,
z wcieciem 9 870).

`GroupInfo`: `name` (`elevation`...), `summary`, `description`, `products`
(`ProductInfo[]`), `commands` (id komend grupy). `GroupInfo` istnieje tylko dla grup
CLI, w kolejnosci dzisiejszego `kartograf --help`: `boundaries`, `cadastre`,
`elevation`, `geodesy`, `hydro`, `imagery`, `landcover`, `maps`, `models3d`, `names`,
`project`, `soil`, `cache` (13 grup). Komendy bez grupy CLI - `parse`, `catalog` oraz
tylko-API `find_sheets`, `store_overview`, `store_entries`, `store_sidecar` - maja
`group: null` i nie naleza do zadnego `GroupInfo`.

`ProductInfo`: `name` (wartosc `--product`), `summary` (opis z `_PRODUCT_TEXT` i
tekstow kolekcji, np. `Numeryczny Model Terenu; PL i CZ`), `countries` (`pl`, `cz`),
`sources` (klucze deskryptorow; szczegoly: `list_sources`).

`CommandInfo`:

| Klucz | Typ | Znaczenie |
|---|---|---|
| `id` | string | `elevation download`, `parse`, `catalog`, `find_sheets` (komenda tylko-API: nazwa funkcji); to samo co klucz `COMMANDS` i `tasks[].command` |
| `group` | string albo `null` | grupa (`elevation`...) |
| `name` | string | ostatnie slowo `id` |
| `summary` | string | jedna linia, najwyzej 120 znakow (`help` komendy w `--help`) |
| `description` | string | pelny opis (`description` komendy w `--help`) |
| `kind` | string | `data` (zapisuje do magazynu), `query` (tylko odczyt), `manage` (zmienia projekt albo cache) |
| `effects` | string[] | podzbior: `network`, `store_write`, `project_write`, `cache_write`, `cache_delete` |
| `idempotent` | bool | powtorzenie z tymi samymi argumentami nie zmienia skutku |
| `destructive` | bool | usuwa informacje (`project remove`, `cache clear`) |
| `project_task` | bool | komenda danych projektu (jest w `COMMANDS`, ma `_task`) - to jest "komenda danych" KB-1 |
| `function` | string | nazwa funkcji w `kartograf.__all__` (`download_data`) |
| `check_function` | string albo `null` | blizniak `check_*` (`check_data`) |
| `result_schema` | string | schemat wyniku (`kartograf-download/1`) |
| `check_result_schema` | string albo `null` | schemat wyniku blizniaka (`kartograf-plan/1`) |
| `supports_check` | bool | komenda ma sprawdzenie aktualnosci bez pobierania: `true` <=> `check_function` i `check_result_schema` sa ustawione (CLI: `--check-updates`; MCP: dla komend danych narzedzie `check_updates`, dla `project download` narzedzie `project_check_updates`) |
| `cli` | string albo `null` | slowa po `kartograf` (`elevation download`); `null` = tylko API |
| `tool` | string albo `null` | nazwa narzedzia MCP (9.3); komenda z `supports_check`, bedaca komenda danych, jest sprawdzana narzedziem `check_updates` z `tool` = ta nazwa |
| `params` | `ParamInfo[]` albo `null` | parametry; tylko na zadanie (8.5) |
| `constraints` | `ConstraintInfo[]` albo `null` | ograniczenia (j.w.) |
| `examples` | `ExampleInfo[]` albo `null` | przyklady (j.w.) |

`ParamInfo`:

| Klucz | Typ | Znaczenie |
|---|---|---|
| `name` | string | unikalna w komendzie; klucz opcji zadania i - gdy `argument` niepusty - nazwa argumentu API |
| `argument` | string albo `null` | nazwa argumentu funkcji API (`output_dir` dla `--output`); `null` = tylko CLI (`quiet`, `json`, `check_updates`, `upgrade`, `force`) |
| `flag` | string albo `null` | flaga CLI (`--vertical-crs`); `null` = tylko API (`update`) |
| `short` | string albo `null` | skrot (`-o`, `-r`, `-w`, `-q`, `-p`, `-d`, `-f`) |
| `positional` | bool | argument pozycyjny (`sheet` w `parse`, `name`, `tasks`) |
| `kind` | string | `str`, `int`, `flag`, `bbox`, `bbox_crs`, `path`, `per_country`, `str_list` (jak `OptionKind` projektu, KB-1) oraz `plan`, `options` (9.4) |
| `required` | bool | wymagany przez komende (walidacja w bibliotece; argparse nie ustawia `required`) |
| `task` | bool | opcja zadania projektu (wchodzi do `tasks[].options`) |
| `allowed` | string[] albo `null` | dozwolone wartosci z rejestru i wariantow (suma po krajach i produktach); `null` = wartosc dowolna |
| `default` | wartosc albo `null` | wartosc, ktorej uzywa funkcja API, gdy argument pominieto (`null` = brak) |
| `cli_default` | wartosc albo `null` | wartosc domyslna flagi CLI, gdy rozni sie od API (`--bbox-crs`: `EPSG:2180`); `null` = taka sama |
| `accepts` | string[] albo `null` | tylko `sheet`: systemy godel (`pl1992`, `pl2000`, `cz_sm5`, `cz_tm33`, `cz_ztm`) |
| `section` | string albo `null` | tytul sekcji `--help` (`Produkt i obszar`, `Parametry produktu`, `Wynik i aktualizacja`) |
| `description` | string | opis (ten sam tekst co flaga w `--help`) |

`ConstraintInfo`: `type` (`one_of`, `any_of`, `requires`, `excludes`, `applies_to`,
`required_when`), `param` (string albo `null`), `params` (string[]), `when`
(obiekt albo `null`: `{"<param>": true}` = podany, `{"<param>": ["a", "b"]}` =
wartosc z listy; kilka kluczy = AND), `message` (tekst). Znaczenie: `one_of` -
dokladnie jeden z `params`; `any_of` - co najmniej jeden; `requires` - gdy podano
`param`, wymagane wszystkie `params` (np. `cutout` -> `horizontal_crs`); `excludes` -
gdy podano `param`, zaden z `params`; `applies_to` - `param` tylko gdy `when`;
`required_when` - `param` wymagany gdy `when`. Rodzaj `bbox` zawsze wymaga
`bbox_crs` w API i MCP (regula wbudowana, nie ograniczenie).

`ExampleInfo`: `title` (string albo `null`), `options` (opcje zadania, postac
manifestu), `command_line` (`kartograf ... -o ./data`, wyliczona z `options` przez
`format_command`).

Przyklad (skrocony do 5 z 28 parametrow `elevation download`):

```json
{
  "id": "elevation download",
  "group": "elevation",
  "name": "download",
  "summary": "Pobierz NMT, NMPT, LAZ albo warstwice (arkusze, kafle albo wycinek)",
  "description": "Pobierz NMT, NMPT i chmury punktow LAZ z GUGiK (PL) albo CUZK (CZ) do magazynu wersji. ...",
  "kind": "data",
  "effects": ["network", "store_write"],
  "idempotent": true,
  "destructive": false,
  "project_task": true,
  "function": "download_data",
  "check_function": "check_data",
  "result_schema": "kartograf-download/1",
  "check_result_schema": "kartograf-plan/1",
  "supports_check": true,
  "cli": "elevation download",
  "tool": "elevation_download",
  "params": [
    {"name": "product", "argument": "product", "flag": "--product", "short": null, "positional": false, "kind": "str", "required": true, "task": true, "allowed": ["nmt", "nmpt", "laz", "contours"], "default": null, "cli_default": null, "accepts": null, "section": "Produkt i obszar", "description": "Produkt (wymagany): nmt (Numeryczny Model Terenu; PL i CZ), ..."},
    {"name": "bbox", "argument": "bbox", "flag": "--bbox", "short": null, "positional": false, "kind": "bbox", "required": false, "task": true, "allowed": null, "default": null, "cli_default": null, "accepts": null, "section": "Produkt i obszar", "description": "Prostokat obszaru: min_x,min_y,max_x,max_y ..."},
    {"name": "bbox_crs", "argument": "bbox_crs", "flag": "--bbox-crs", "short": null, "positional": false, "kind": "bbox_crs", "required": false, "task": true, "allowed": ["EPSG:2180", "EPSG:4326", "EPSG:2176", "EPSG:2177", "EPSG:2178", "EPSG:2179", "EPSG:5514", "EPSG:3045"], "default": null, "cli_default": "EPSG:2180", "accepts": null, "section": "Produkt i obszar", "description": "Uklad wspolrzednych --bbox (domyslnie EPSG:2180)"},
    {"name": "output_dir", "argument": "output_dir", "flag": "--output", "short": "-o", "positional": false, "kind": "path", "required": true, "task": false, "allowed": null, "default": null, "cli_default": null, "accepts": null, "section": "Wynik i aktualizacja", "description": "Katalog magazynu (wymagany): ..."},
    {"name": "upgrade", "argument": null, "flag": "--upgrade", "short": null, "positional": false, "kind": "flag", "required": false, "task": false, "allowed": null, "default": null, "cli_default": null, "accepts": null, "section": "Wynik i aktualizacja", "description": "Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje ..."}
  ],
  "constraints": [
    {"type": "one_of", "param": null, "params": ["sheet", "bbox", "geometry"], "when": null, "message": "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry"},
    {"type": "requires", "param": "cutout", "params": ["horizontal_crs"], "when": null, "message": "--cutout wymaga --horizontal-crs"}
  ],
  "examples": [
    {"title": null, "options": {"product": "nmt", "sheet": "N-34-130-D-d-2-4", "resolution": "1m", "vertical_crs": "EVRF2007"}, "command_line": "kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 -o ./data"}
  ]
}
```

Przyklad przegladu (`get_catalog()`; skrocony do dwoch grup i trzech komend z 13 grup i
41 komend; w pliku rekordy sa po jednym w linii):

```json
{
  "schema": "kartograf-catalog/1",
  "view": "overview",
  "kartograf_version": "0.8.0",
  "language": "pl",
  "groups": [
    {"name":"elevation","summary":"Wysokosci: NMT, NMPT i chmury LAZ (PL i CZ), warstwice (CZ)","products":["nmt","nmpt","laz","contours"]},
    {"name":"soil","summary":"Gleby: SoilGrids i grupy hydrologiczne HSG","products":["soil"]}
  ],
  "commands": [
    {"id":"elevation download","summary":"Pobierz NMT, NMPT, LAZ albo warstwice (arkusze, kafle albo wycinek)","tool":"elevation_download","supports_check":true},
    {"id":"elevation list-sources","summary":"Wypisz zrodla danych grupy (rejestr zrodel, bez sieci)","tool":"list_sources","supports_check":false},
    {"id":"cache stats","summary":"Pokaz statystyki cache (liczby wpisow, rozmiar bazy)","tool":null,"supports_check":false}
  ],
  "exit_codes": null,
  "errors": null,
  "schemas": null
}
```

Komendy `parse`, `catalog` i tylko-API (`find_sheets`, `store_*`) maja `group:
null`; komendy tylko-API maja `cli: null` i nie dodaja flag ani parsera.

### 8.2 Zrodlo prawdy: deklaracje w bibliotece, argparse z deklaracji (D7)

```
kartograf/catalog/
    spec.py         # typy deklaracji: Param, Command, Group (frozen); allowed i description moga byc dostawcami
    shared.py       # parametry wspolne: obszar (sheet, bbox, bbox_crs, geometry, layer), product, country,
                    #   output_dir, workers, quiet, json, check_updates/upgrade/force, plan, update
    kinds.py        # rodzaje parametrow: parsery wartosci CLI (bbox, per_country, layers) i konwersja opcji
                    #   zadania <-> argumenty biblioteki (options_from_json/_to_json, check_options_json)
    commands/       # jeden modul na grupe: elevation.py, imagery.py, landcover.py, soil.py, boundaries.py,
                    #   cadastre.py, models3d.py, hydro.py, names.py, maps.py, geodesy.py, project.py,
                    #   misc.py (parse, catalog, cache, tylko-API)
    model.py        # dokument katalogu (8.1)
    build.py        # get_catalog(): rozstrzyga dostawcow, waliduje deklaracje, buduje Catalog
    cliparser.py    # argparse z deklaracji (tylko stdlib); UsageError zamiast SystemExit
    formatting.py   # format_command_line: kanoniczna linia komendy (8.7); ExampleInfo.command_line i format_command
    hints.py        # example_for(command, option): skladnik (b) podpowiedzi bledow (6.3)
    tools.py        # specyfikacje narzedzi MCP (czyste dane, 9.3-9.4)
    __init__.py     # get_catalog, data_commands
kartograf/commands.py  # warstwa komend KB-2..KB-5 (8.7): importuje catalog i project.commands
```

Moduly biblioteki dodane poza `catalog/` (katalog korzysta z rejestru i funkcji
biblioteki, nie odwrotnie; A6): w T3 `kartograf/source_info.py` (`list_sources`,
`list_layers`: rejestr zrodel i wybor flag per grupa, przeniesione z `cli/groups`),
`kartograf/cache_info.py` (`get_cache_info`, `clear_cache`) i
`kartograf/store_documents.py` (`describe_store`, `list_store_entries`,
`read_store_sidecar`); w T4d `kartograf/sheet_info.py` (`describe_sheet`, `find_sheets`).

Przeplyw (jedno zrodlo, cztery rzuty):

1. deklaracje -> `build.get_catalog()` -> `Catalog` (`kartograf catalog`, narzedzie
   `get_catalog`, `data_commands()`);
2. deklaracje -> `cliparser.build_parser()` -> parser CLI. `cli/_parser.py::create_parser()`
   sklada korzen (`--version`, `parse`, grupy, `cache`, `catalog`) wylacznie z
   deklaracji; `parse_command` (8.7) uzywa tego samego parsera;
3. deklaracje -> `project/commands.py`: `TaskCommand.options = {p.name: p.kind for p in
   command.params if p.task}` (kolejnosc deklaracji = kolejnosc manifestu); w projekcie
   zostaja walidacje, wywolania `download`/`check` i adaptery wyniku - zachowanie, nie
   nazwy i rodzaje; funkcje `*_task_arguments` CLI znikaja (zastepuje je
   `parse_command(...).options`);
4. deklaracje -> `tools.py` -> narzedzia MCP; przyklady -> `epilog` CLI, testy i `llms.txt`.

Zasady budowy parsera (zachowanie CLI bez zmian):

- argparse **nigdy nie ustawia `required=True`** dla flag - brak wartosci zglasza
  biblioteka (Z1; tresc bledow po polsku jak dzis); wyjatek: argumenty pozycyjne
  (`parse GODLO`, `project add NAZWA`);
- `dest` flagi = `Param.dest` (domyslnie `name`; `--output` ma `dest="output"`, wiec
  handlery i testy dalej czytaja `args.output`); `normalize` -> `type` argparse
  (`str.lower`, `str.upper`, `str.strip`); `kind` -> `type`/`action` (`int`, `store_true`,
  parsery `--bbox`, `pl=..,cz=..`, `--layers` z biblioteki - przeniesione z
  `cli/_args.py`); `allowed` -> `choices` tylko tam, gdzie dzis jest `choices`
  (flaga ma `choices: true`; reszta jest walidowana w bibliotece);
- `--check-updates`, `--upgrade`, `--force` w jednej wzajemnie wykluczajacej sie grupie;
  sekcje `--help` z `section`; `epilog` = przyklady komendy;
- niezmienione: `_Parser` bez skracania flag, `_HelpFormatter`, `_LazyVersionAction`,
  komunikaty o usunietych komendach 0.8.0 (`removed_command_error`), podpowiedzi o
  nieznanych flagach (`_unknown_text`, `_UNKNOWN_HINTS`), sklejanie `--bbox -447000,...`
  - cala ta logika wraz z `parse_command_line` przechodzi do `cliparser.py` (uzywa jej
  `parse_command`); `cli/_parser.py` zostaje cienka fasada (`create_parser`,
  `parse_command_line`, `removed_command_error`, `_subparsers`), bo testy z niej
  importuja;
- komenda tylko-API nie ma parsera CLI i nie dodaje flag.

Dlaczego nie sam test kontraktowy (odrzucone w D7): kazdy z kilkuset opisow flag
(38 tys. znakow) mialby dwie kopie, a test sprawdzalby ich identycznosc - zmiana
opisu wymagalaby dwoch edycji. Dlaczego nie introspekcja argparse w `get_catalog()`:
biblioteka (i MCP) importowalaby `kartograf.cli`, wbrew A6. Test kontraktowy (12)
zostaje jako druga bariera: parser zbudowany z deklaracji porownywany z katalogiem,
z sygnaturami funkcji API i z `COMMANDS`.

Migracja etapami (sekcja 13): (1) model i deklaracje obok starego parsera, test
rownowaznosci stary parser <-> katalog (flagi, `dest`, `type`, `choices`, `default`,
`nargs`, wzajemne wykluczanie) oraz jednorazowe porownanie `--help` kazdej
komendy; (2) przelaczenie `create_parser()` na `cliparser`; (3) usuniecie
`cli/groups/*.py` i `*_task_arguments`. Pomiar odniesienia (obecny parser) zdejmuje
sie PRZED etapem 2 skryptem (`format_help()` i zrzut akcji kazdej komendy), poza
repozytorium.

### 8.3 Deklaracje

`Param` (`catalog/spec.py`, frozen) ma pola z tabeli `ParamInfo` oraz pola tylko
CLI, ktore nie trafiaja do JSON: `dest` (domyslnie `name`), `metavar` (po polsku:
`KATALOG`, `GODLO`, `ROK`, `BBOX`, `PLIK`, `KOD`...), `normalize` (`lower`,
`upper`, `strip`, `None`), `exclusive` (id grupy wzajemnego wykluczania),
`choices` (bool: `allowed` jest tez `choices` argparse), `nargs` (`*` dla `tasks`,
`REMAINDER` dla `arguments`). Reguly:

1. `flag` domyslnie `"--" + name.replace("_", "-")`; `argument` domyslnie `name`;
   `None` w obu polach wylacza odpowiednio CLI albo API;
2. `allowed` i `description` moga byc dostawcami (funkcjami bez argumentow
   zwracajacymi liste / tekst): wartosci z rejestru (`download/options.py`,
   `landcover/manager.py`, `download/collections.py`, `sources/variants.py`) sa
   rozstrzygane w `get_catalog()` i przy budowie parsera, nigdy przy imporcie
   modulu; kopia listy w deklaracji jest zabroniona (test: `allowed` rowne wynikowi
   dostawcy);
3. opisy komend i flag przenosi sie z dzisiejszych modulow `cli/groups/*.py` bez
   zmiany tresci (Z5: polski, ASCII); `summary` komendy <= 120 znakow;
4. parametr wspolny (`shared.py`) deklaruje sie raz; komenda go wlacza i moze
   nadpisac `description`, `allowed`, `required` (`dataclasses.replace`);
5. `required: true` tylko dla argumentow, ktore biblioteka odrzuca przy braku
   (`product`, `output_dir` komend danych, `sheet` w `parse`, `group` w `list_sources`);
   `task: true` dla opcji, ktore dzis sa kluczami `COMMANDS[...].options`; `output_dir`,
   `workers`, `plan`, `update`, `summary` i flagi CLI nie sa `task`;
6. komenda deklaruje `function` i `check_function` jako nazwy z `kartograf.__all__`
   (test sprawdza sygnature: kazdy `argument` jest parametrem funkcji, kazdy
   parametr bez wartosci domyslnej jest `required`, funkcja ma argumenty tylko
   nazwane);
7. kolejnosc `params` = kolejnosc flag w `--help` (sekcje po kolei); kolejnosc
   kluczy opcji w manifescie wynika z niej (dzis `COMMANDS` ma wlasna kolejnosc, np.
   `country` po obszarze; po zmianie nowe manifesty maja `country` zaraz po
   `product` - zmiana kosmetyczna: odczyt manifestu nie zalezy od kolejnosci kluczy,
   testy kolejnosci sie aktualizuje).

### 8.4 Ograniczenia i przyklady

- **Ograniczenia** to dokumentacja glownych regul walidatora (zrodlem zachowania
  zostaje biblioteka): kazda komenda deklaruje co najmniej `one_of` obszaru
  (`sheet`/`bbox`/`geometry`, `teryt` i `ku` tam, gdzie wybieraja jednostke), regule
  `requires` dla kazdego "X wymaga Y" z `--help` (np. `cutout` -> `horizontal_crs`) oraz
  `applies_to` dla opcji ograniczonych do produktow (`model`, `min_density`,
  `coverage`, `direction`, `keep_raw`, `layers`...). Test naruszenia wyprowadza
  wywolanie niepoprawne z przykladu: dla `one_of` usuwa wszystkie `params` i dodaje
  dwa, dla `requires` usuwa wymagane, dla `excludes` dodaje wykluczone, dla
  `applies_to` dodaje opcje przy produkcie spoza `when`; oczekiwany wynik:
  `validate_command` rzuca `ValidationError`, a `option`/`options` wskazuje opcje
  ograniczenia. `required_when` jest dokumentacja (bez generowanego testu).
- **Przyklady** deklaruje sie jako opcje zadania (`options`); `command_line` wylicza
  `format_command`. Kazda komenda danych ma co najmniej jeden przyklad PL i, gdy
  produkt ma CZ, jeden CZ; przyklady dzisiejszych `epilog` przechodza bez zmian.
  Testy: kazdy przyklad przechodzi `validate_command`, `parse_command(command_line)` daje te
  same `options` (zaokraglenie w obie strony), a `kartograf <command_line>` parsuje sie
  prawdziwym parserem.

### 8.5 API: `get_catalog`, `data_commands`

```python
def get_catalog(*, group: str | None = None, command: str | None = None,
                params: bool | None = None, tables: bool | None = None) -> Catalog
def data_commands() -> tuple[CommandInfo, ...]    # KB-1: komendy z project_task=True, z parametrami
```

- bez argumentow: przeglad (`view: "overview"`, 8.1, D9): grupy z nazwami produktow i
  komendy (id, podsumowanie, narzedzie, `supports_check`); `params`, `constraints`,
  `examples` obiektow sa `None`, tabele `None`;
- `group`: tylko ta grupa i jej komendy, z produktami i ich zrodlami (widok `full`;
  nieznana: `ValidationError`, `option="group"`, `allowed` = grupy); `command`: tylko ta
  komenda, z `params`, `constraints` i `examples` (`params=None` oznacza wtedy `True`);
  nieznana: `ValidationError`, `option="command"`;
- `params=True`: parametry, ograniczenia i przyklady wszystkich wybranych komend (bez
  `group` i `command`: caly katalog, ok. 200 tys. znakow); `params=False`: nigdy;
  `None`: tylko gdy podano `command`;
- `tables`: `True` dodaje `exit_codes`, `errors` i `schemas` do kazdego widoku (przeglad
  z tabelami zostaje przegladem); `False`: nigdy; `None`: tylko dla calego katalogu
  (`params=True` bez `group` i `command`: jak przed zmiana D22);
- `view` jest `overview`, gdy nic nie wybrano i nie zazadano parametrow, inaczej `full`;
  wynik pelnego katalogu jest budowany raz na proces i niemutowalny, widoki sa jego
  filtrami (ten sam obiekt dla tych samych argumentow);
- `data_commands()` zwraca `CommandInfo` z wypelnionymi `params` komend z
  `project_task: true` (12 komend; kolejnosc `COMMANDS`); parametry zawieraja zarowno
  opcje zadania (`task: true`), jak i flagi uruchomienia (`output_dir`, `workers`,
  `update`, `plan`...).

### 8.6 Mapowanie wymagania KB Archiwisty (SPEC 12.2)

| ID | Wymaganie Archiwisty | Realizacja w Kartografie 0.8.0 | Zakres |
|---|---|---|---|
| KB-1 | `data_commands() -> tuple[CommandInfo, ...]`: nazwa, rodzaj (`str`, `int`, `flag`, `bbox`, `path`, `per_country`, `str_list`), dozwolone wartosci z rejestru i wariantow, wymagalnosc i zaleznosci (np. `cutout` wymaga `horizontal_crs`), flaga CLI, opis po polsku z `--help` | `data_commands()` i `get_catalog()`: `CommandInfo.id`, `ParamInfo.kind` (rodzaje `OptionKind` + `bbox_crs`), `allowed`, `required` + `constraints`, `flag`, `description` | w zakresie |
| KB-2 | `parse_command(argv) -> CommandCall` (ten sam parser co `project add`) | `kartograf.parse_command` (8.7); parser z deklaracji | w zakresie |
| KB-3 | `validate_command(command, options)`; `ValidationError` z nazwa opcji | `kartograf.validate_command`; `ValidationError.option`/`options`/`allowed` (6.1) | w zakresie |
| KB-4 | `format_command(command, options) -> str` | `kartograf.format_command`; ten sam formater wylicza `ExampleInfo.command_line` | w zakresie |
| KB-5 | `run_command(...)` i `check_command(...) -> UpdatePlan` z `on_progress`, `on_notice`, `cancel` | `kartograf.run_command`, `kartograf.check_command` bez `cancel` (KC poza zakresem); MCP uzywa tych funkcji | w zakresie (bez `cancel`) |
| KB-6 | `command_for_file(sidecar)` | - | poza zakresem (v1.1 Archiwisty) |
| KB-7 | `find_admin_units(query, ...)` | - | poza zakresem (osobna decyzja) |

Nazwy w tabeli sa ostateczne (zastepuja "propozycje" SPEC 12.2); SPEC Archiwisty
powinien je przejac. Roznice: KB-1 dostaje `ParamInfo.kind` rozszerzone o `bbox_crs`
(juz w `OptionKind`) oraz `plan`, `options` (tylko API); `CommandCall` ma dodatkowe
pole `run` (8.7).

### 8.7 Warstwa komend (`kartograf/commands.py`, KB-2..KB-5)

```python
@dataclass(frozen=True)
class CommandCall:
    command: str                      # "elevation download"
    options: dict[str, object]        # opcje zadania, postac JSON manifestu (tylko podane)
    run: dict[str, object]            # pozostale flagi komendy, klucze = Param.name (tylko podane)

def parse_command(argv: Sequence[str] | str) -> CommandCall
def validate_command(command: str, options: Mapping[str, object], *,
                     output_dir: str | Path | None = None) -> None
def format_command(command: str, options: Mapping[str, object], *,
                   run: Mapping[str, object] | None = None) -> str
def run_command(command: str, options: Mapping[str, object], *, output_dir: str | Path,
                update: UpdateMode | None = None, plan: UpdatePlan | None = None,
                workers: int | None = None, cache: MetadataCache | bool = True,
                on_progress: Callable[[DownloadProgress], None] | None = None,
                on_notice: Callable[[Notice], None] | None = None) -> Document
def check_command(command: str, options: Mapping[str, object], *, output_dir: str | Path,
                  cache: MetadataCache | bool = True,
                  on_notice: Callable[[Notice], None] | None = None) -> UpdatePlan
```

- `options` we wszystkich funkcjach to **postac JSON opcji zadania** (ADR-040:
  `bbox` jako 4 liczby + `bbox_crs`, sciezki jako napisy, wartosc per kraj jako napis
  albo `{"pl", "cz"}`, listy jako tablice, bez `null`/`false`); konwerter do
  argumentow biblioteki to istniejace `options_from_json` (przechodzi z
  `project/commands.py` do `catalog` jako wspolna funkcja rodzajow; projekt i MCP
  uzywaja jednej implementacji);
- `parse_command(argv)`: `argv` bez nazwy programu (tokeny po `kartograf`; napis jest
  dzielony `shlex.split`); parser jest parserem z 8.2; `options` zawiera tylko
  opcje zadania podane jawnie (`bbox` zawsze z `bbox_crs`, takze z domyslnym
  `EPSG:2180` flagi CLI), `run` - pozostale podane flagi (`output_dir`, `upgrade`,
  `force`, `check_updates`, `plan`, `workers`, `quiet`, `json`, `summary`); komenda
  spoza `COMMANDS` (np. `parse`, `elevation availability`) to `ValidationError`
  z lista komend danych (jak `project add`); blad skladni to `UsageError`. To usuwa
  obejscie `_workers_given` w `project add` (parser odroznia flage podana od domyslnej);
- `validate_command`: ta sama walidacja bez sieci i bez zapisu co `add_project_task`
  (`TaskCommand.validate`); `output_dir=None` podstawia `Path(".")` (walidatory nie
  otwieraja katalogu; plik `geometry` jest czytany jak dotad); `ValidationError` z
  `option`;
- `format_command`: kanoniczna linia `kartograf <grupa> <komenda> ...`: flagi w
  kolejnosci deklaracji; `flag` -> sama flaga; `bbox` -> `--bbox a,b,c,d`, a
  `--bbox-crs X` pomijane, gdy `X == cli_default`; `per_country` -> `v` albo
  `pl=v,cz=w`; `str_list` -> po przecinku; `path` -> cytowanie `shlex.quote`;
  `run` dopisuje flagi uruchomienia (`output_dir` jako `-o`); `parse_command(
  format_command(c, o, run=r)[len("kartograf "):])` zwraca `(c, o, r)` dla kazdego
  przykladu katalogu (test);
- `run_command` = `COMMANDS[command].download(...)` z nowym argumentem `plan`
  (`TaskDownload.__call__` dostaje `plan: UpdatePlan | None`; projekt przekazuje
  `None`) i `update`; zwraca raport rodziny komendy (`Document` schematu
  `result_schema`); `check_command` = `COMMANDS[command].check(...)`. Obie najpierw
  wolaja `validate_command`. Brak `cancel` (KC);
- nieznana `command`: `ValidationError(option="command", allowed=<komendy danych>)`.

## 9. Serwer MCP

### 9.1 Zalozenia

- Serwer Model Context Protocol przez **stdio** (jedyny transport w 0.8.0), modul
  `kartograf/mcp_server.py`, skrypt `kartograf-mcp`. Narzedzia generuja sie z katalogu
  (`kartograf/catalog/tools.py`, czyste dane bez `mcp`); serwer tylko je wystawia i
  wola funkcje biblioteki (A7).
- Narzedzie = komenda katalogu z `tool` albo wspolne narzedzie `check_updates` (29
  narzedzi, 9.3); nazwa narzedzia jest stabilna jak kod bledu (A3). Wynik narzedzia =
  dokument `kartograf-*/1` identyczny z `--json` (9.5). Brak wartosci domyslnych
  wplywajacych na dane (A8, D14).
- `mcp` importuje tylko `kartograf/mcp_server.py`; `import kartograf` i CLI dzialaja bez
  niego (A6). Niskopoziomowy `mcp.server.Server` (D11): schematy wejscia sa dokladnie
  tymi z katalogu (bez artefaktow pydantic), a wynik budujemy recznie, bo wyjatek w
  handlerze niskiego poziomu to blad protokolu `-32603` bez tresci (model nie zobaczylby
  komunikatu), a `MCPServer` przekazuje modelowi wylacznie tresc `ToolError` i nie
  zwraca `structured_content` przy bledzie.

### 9.2 Zaleznosc, wersja, uruchomienie

`pyproject.toml`:

```toml
[project.optional-dependencies]
mcp = ["mcp>=2.3.0,<3"]
dev = ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.8", "mypy>=1.13", "mcp>=2.3.0,<3"]

[project.scripts]
kartograf = "kartograf.cli.commands:main"
kartograf-mcp = "kartograf.mcp_server:main"
```

- Wersja: **`mcp>=2.3.0,<3`** - 2.3.0 to najnowsze wydanie stabilne (PyPI 2026-10-02;
  linia 2.x co 2-4 tygodnie: 2.1.0 2026-08-24, 2.2.0 2026-09-07, 2.3.0 2026-10-02); linia
  1.x (1.30.0) ma inne API serwera (dekoratory `@server.call_tool()`, walidacja
  argumentow przez SDK) i nie jest wspierana. Gorna granica `<3` chroni przed zmiana
  glowna; kontakt z SDK ogranicza sie do jednego modulu i testow w pamieci (9.10), wiec
  zmiany podwersji lapie brama.
- `kartograf.mcp_server` importuje sie BEZ `mcp` (importy SDK leniwie, w `create_server`; typy
  tylko pod `TYPE_CHECKING`): `create_server` bez `mcp` rzuca `ImportError` z napisem `Brak
  pakietu mcp: pip install "kartograf[mcp]"`, a `main()` lapie go, drukuje na stderr i konczy
  kodem 1. Skrypt `kartograf-mcp` jest instalowany zawsze (komunikat zamiast
  `ModuleNotFoundError`).
- Rdzen nie zyskuje zaleznosci. `kartograf[mcp]` dolacza m.in. `pydantic>=2.12`,
  `starlette`, `uvicorn` (twarde zaleznosci SDK, takze dla stdio), `httpx2`,
  `jsonschema`, `sse-starlette`, `anyio`, `opentelemetry-api`, `mcp-types==2.3.0`.
  `jsonschema` uzywa tez serwer do walidacji argumentow (9.4).
- `kartograf-mcp [--tools RODZINY] [--cache-file PLIK | --no-cache] [--allow-dir KATALOG]...
  [--version]`; uruchomienie: `kartograf-mcp` albo `python -m kartograf.mcp_server`. Serwer:
  `Server("kartograf", version=kartograf.__version__, instructions=<9.9>, on_list_tools=...,
  on_call_tool=...)`; petla: `anyio.run` z `mcp.server.stdio.stdio_server()` i
  `server.run(read, write, server.create_initialization_options())`.
  - `--tools`: rodziny po przecinku z `discovery`, `availability`, `data`, `check`,
    `project`, `store` (domyslnie wszystkie 29 narzedzi; klienty z limitem liczby narzedzi
    zawezaja np. do `discovery,availability,data,check`); nieznana rodzina = blad uruchomienia;
  - `--cache-file`: plik cache metadanych; domyslnie `<katalog cache>/kartograf/metadata.db`
    (`$XDG_CACHE_HOME` albo `~/.cache`; Windows `%LOCALAPPDATA%`), tworzony przy
    pierwszym uzyciu; `--no-cache` = `cache=False`. Domyslny cache serwera NIE jest
    `<cwd>/.kartograf_cache.db`: cwd serwera wybiera klient MCP (Z6 zostaje dla CLI i
    biblioteki);
  - `--allow-dir`: wielokrotne; gdy podano, kazda sciezka argumentu (`output_dir`,
    `geometry`, `project_dir`, `path`) po `Path.resolve()` musi lezec w ktoryms z
    katalogow, inaczej `invalid_input` z `option` i `hint` (9.7).

### 9.3 Narzedzia

Adnotacje (`ToolAnnotations`, wylacznie wskazowki): `RO` = `read_only_hint`, `D` =
`destructive_hint`, `I` = `idempotent_hint`, `OW` = `open_world_hint`. Wyliczane z
`kind`/`effects`/`idempotent`/`destructive` komendy; **`destructive_hint=false`
ustawiane jawnie dla narzedzi zapisujacych** (domyslna wartosc protokolu to `true`):
magazyn jest niezmienny, nic nie jest nadpisywane (ADR-036). Narzedzie nie ma `title`:
pierwsze zdanie `description` to `summary` komendy (D22).

| Rodzina | Narzedzie | Komenda katalogu | Funkcja (przez) | Dokument | Adnotacje |
|---|---|---|---|---|---|
| `discovery` | `get_catalog` | `catalog` | `get_catalog` | `kartograf-catalog/1` | RO |
| `discovery` | `parse_sheet` | `parse` | `describe_sheet` | `kartograf-sheet/1` | RO |
| `discovery` | `find_sheets` | `find_sheets` | `find_sheets` | `kartograf-sheets/1` | RO |
| `discovery` | `list_sources` | `<grupa> list-sources` (11 komend: jedno narzedzie z parametrem `group`) | `list_sources` | `kartograf-sources/1` | RO |
| `discovery` | `list_layers` | `landcover list-layers`, `soil list-layers` (parametr `group`) | `list_layers` | `kartograf-layers/1` | RO |
| `availability` | `elevation_availability` | `elevation availability` | `check_availability` | `kartograf-availability/1` | RO, OW |
| `data` | `elevation_download`, `imagery_download` | `elevation download`, `imagery download` | `download_data` (`run_command`) | `kartograf-download/1` | D=false, I, OW |
| `data` | `landcover_download` | `landcover download` | `download_landcover` (`run_command`) | `kartograf-download/1` | D=false, I, OW |
| `data` | `soil_download` | `soil download` | `download_soil` (`run_command`) | `kartograf-download/1` | D=false, I, OW |
| `data` | `soil_hsg` | `soil hsg` | `calculate_hsg` (`run_command`) | `kartograf-download/1` | D=false, I, OW |
| `data` | `boundaries_download`, `cadastre_download`, `models3d_download`, `hydro_download`, `names_download`, `maps_download`, `geodesy_download` | `<grupa> download` | `download_collection` (`run_command`) | `kartograf-download/1` | D=false, I, OW |
| `check` | `check_updates` (jedno narzedzie dla 12 komend danych; parametry `tool` i `arguments`, 9.4) | 12 komend danych z `supports_check` | `check_data`, `check_landcover`, `check_soil`, `check_hsg`, `check_collection` (`check_command`) | `kartograf-plan/1` | RO, OW |
| `project` | `project_init` | `project init` | `init_project` | `kartograf-project-state/1` | D=false, I |
| `project` | `project_add` | `project add` | `add_project_task` | `kartograf-project-state/1` | D=false |
| `project` | `project_remove` | `project remove` | `remove_project_task` | `kartograf-project-state/1` | D=true |
| `project` | `project_download` | `project download` | `download_project` | `kartograf-project-report/1` | D=false, I, OW |
| `project` | `project_check_updates` | `project download --check-updates` | `check_project` | `kartograf-project-check/1` | RO, OW |
| `project` | `project_status` | `project status` | `get_project_status` | `kartograf-project-check/1` | RO |
| `project` | `project_verify` | `project verify` | `verify_project` | `kartograf-project-check/1` | RO |
| `store` | `store_overview` | `store_overview` | `describe_store` | `kartograf-store-overview/1` | RO |
| `store` | `store_entries` | `store_entries` | `list_store_entries` | `kartograf-store-entries/1` | RO |
| `store` | `store_sidecar` | `store_sidecar` | `read_store_sidecar` | `kartograf-store-sidecar/1` | RO |

Razem 5 + 1 + 12 + 1 + 7 + 3 = 29. Poza MCP: `cache *` (cache serwera to jego
wewnetrzna sprawa: `update="force"` odswieza wpisy), `project_open` (stan projektu
zwracaja `project_status` i pozostale). Nazwy narzedzi sa polem katalogu
(`CommandInfo.tool`), nie wyprowadza sie ich w locie; wyjatek: `check_updates` nie ma
wlasnej komendy (O4), a jego `tool` wskazuje komende przez jej `tool`.

`check_updates` (O4) zastepuje 12 blizniakow `<narzedzie>_check_updates`: mniej
narzedzi to mniej kontekstu i latwiejszy wybor narzedzia przez agenta. Parametry:
`tool` (wymagany; `enum` = `tool` komend z `project_task` i `supports_check`, 12 nazw) i
`arguments` (wymagany `object`: argumenty narzedzia z `tool` bez `update`, `plan` i
`workers` - sprawdzenie niczego nie pobiera, nie przyjmuje planu i nie ma liczby
watkow; ich podanie to `invalid_input`; `output_dir` wymagany jak w narzedziu danych).
Serwer rozwiazuje `tool` -> komenda, waliduje `arguments` schematem narzedzia danych
bez tych trzech wlasciwosci (`check_arguments_schema`, 9.4) i `validate_command`, po czym
wola `check_command`. Adnotacje RO, OW (`readOnlyHint` nie zalezy od argumentu: dlatego
sprawdzenie nie jest trybem narzedzi danych); wynik `kartograf-plan/1`, `ok: false` =
czesc pozycji `check_failed`. Sprawdzenie projektu zostaje osobnym narzedziem
`project_check_updates` (`project_dir`, `check_project`, `kartograf-project-check/1`).

### 9.4 Schematy wejscia z katalogu

`tools.py` buduje `input_schema` (JSON Schema 2020-12, dokladnie to, co trafia na
drut; klucze protokolu w drucie sa camelCase: `inputSchema`, `readOnlyHint`):

1. korzen `{"type": "object", "properties": ..., "required": [...],
   "additionalProperties": false}`; `required` = parametry z `required: true`,
   ktore maja `argument`, plus `output_dir` narzedzi danych (w `check_updates` wymagany w `arguments`);
2. rodzaj -> wlasciwosc: `str` -> `string` (+ `enum` z `allowed`), `int` -> `integer`,
   `flag` -> `boolean`, `bbox` -> tablica 4 `number` (`minItems`=`maxItems`=4) i
   `dependentRequired: {"bbox": ["bbox_crs"]}`, `bbox_crs` -> `string` z `enum`, `path`
   -> `string` (opis: sciezka bezwzgledna), `per_country` -> `anyOf` (`string` albo obiekt
   `{pl, cz}` o wartosciach `string`, `additionalProperties: false`), `str_list` ->
   tablica `string`, `plan` -> `object` (dokument `kartograf-plan/1`), `options` ->
   `object` (opcje zadania projektu, 8.1);
3. wystawiane sa tylko parametry z `argument` (bez flag CLI `quiet`, `json`,
   `check_updates`, `upgrade`, `force`), a z flag uruchomienia: `update` (`enum`
   `upgrade`, `force`), `plan`, `workers` (`integer`, `minimum` 1); bez `cache`,
   `on_progress`, `on_notice`;
4. opisy (D22): `description` narzedzia = `summary` komendy (bez `title`: dublowalby
   pierwsze zdanie) + odeslanie do `get_catalog(command="<id>")` dla narzedzi danych
   (`project_add`: `command=<command>`) + `Wynik: <dokument>.` (bez zdania o `ok` i bez
   dokumentu dla narzedzi danych: to jest w `instructions`, 9.9). `description`
   wlasciwosci to NIE `ParamInfo.description` (tekst `--help`: flagi, kazda dozwolona
   wartosc), tylko kilka slow z tabel `_BRIEF` i `_BRIEF_FOR` w `tools.py` (`None` =
   sama nazwa, typ i `enum`; znaczenia wspolne dla wielu narzedzi - obszar, sciezki,
   `update`, `plan` - sa w `instructions`). Kazdy argument kazdego narzedzia ma wpis:
   nowy parametr katalogu nie zbuduje narzedzi, dopoki go nie dostanie. Test pilnuje: brak
   flag CLI, najwyzej jedna wartosc `enum` w opisie, najwyzej 80 znakow, brak
   przestarzalych wpisow. `get_catalog` ma `group`, `command` (bez `enum`: 41 id jest w
   przegladzie), `params` i `tables`; `check_updates` ma tylko dwie wlasciwosci (`tool`,
   `arguments`) - parametry zadania daje `get_catalog` z `command=`;
5. narzedzia wspoldzielone (`list_sources`, `list_layers`) maja dodatkowy wymagany
   parametr `group` (`enum` grup komend, ktore dziela narzedzie), `product` - opcjonalny
   napis (wartosci zaleza od grupy: nieznana wartosc to blad biblioteki z lista
   `allowed`); `project_add` ma `command` (`enum` 12 komend danych) i `options`
   (`object`); `check_updates` ma `tool` (`enum` 12 narzedzi danych) i `arguments`
   (`object`; schemat korzenia nie zawiera schematow 12 narzedzi - serwer wybiera
   schemat po `tool`);
6. ograniczenia katalogu (8.4) nie sa kodowane w schemacie (poza `dependentRequired`
   dla `bbox` i `required`): wykonuje je `validate_command` i zwraca `option`;
7. bez `$ref` i `$defs` (D22): klienty nie rozwiazuja ich jednolicie, a powtarzane
   struktury (`bbox`, `bbox_crs`) sa male po skroceniu opisow;
8. budzet kontekstu (D22): `tools/list` z 29 narzedziami ma najwyzej 30 000 znakow
   (zmierzone 28 607, bylo 65 893), czyli ok. 7 tys. tokenow zamiast 16,5 tys.; pilnuja
   go `test_tools_list_is_small` (specyfikacje) i test na prawdziwym kliencie SDK (drut).

Skrocony przyklad (`elevation_download`):

```json
{
  "name": "elevation_download",
  "description": "Pobierz NMT, NMPT, LAZ albo warstwice (arkusze, kafle albo wycinek). Parametry: get_catalog(command=\"elevation download\").",
  "inputSchema": {
    "type": "object",
    "properties": {
      "product": {"type": "string", "enum": ["nmt", "nmpt", "laz", "contours"]},
      "sheet": {"type": "string"},
      "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4, "description": "[min_x, min_y, max_x, max_y]"},
      "bbox_crs": {"type": "string", "enum": ["EPSG:2180", "EPSG:4326", "EPSG:2176", "EPSG:2177", "EPSG:2178", "EPSG:2179", "EPSG:5514", "EPSG:3045"]},
      "resolution": {"anyOf": [{"type": "string"}, {"type": "object", "properties": {"pl": {"type": "string"}, "cz": {"type": "string"}}, "additionalProperties": false}], "description": "Rozdzielczosc siatki, np. 1m; wartosci zaleza od produktu i kraju"},
      "output_dir": {"type": "string"},
      "update": {"type": "string", "enum": ["upgrade", "force"]},
      "workers": {"type": "integer", "minimum": 1}
    },
    "required": ["product", "output_dir"],
    "dependentRequired": {"bbox": ["bbox_crs"]},
    "additionalProperties": false
  },
  "annotations": {"readOnlyHint": false, "destructiveHint": false, "idempotentHint": true, "openWorldHint": true}
}
```

(w przykladzie pominieto 17 pozostalych wlasciwosci `elevation download`).

Schemat `check_updates` (caly; `enum` w kolejnosci `COMMANDS`):

```json
{
  "name": "check_updates",
  "description": "Porownaj magazyn z sygnalami zrodel dla zadania narzedzia danych (tool) i jego argumentow (arguments: te same, bez update, plan, workers i summary; output_dir wymagany). Nic nie jest pobierane. Wynik: kartograf-plan/1.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "tool": {"type": "string", "enum": ["elevation_download", "imagery_download", "landcover_download", "soil_download", "soil_hsg", "boundaries_download", "cadastre_download", "models3d_download", "hydro_download", "names_download", "maps_download", "geodesy_download"], "description": "Narzedzie danych, ktorego zadanie sprawdzasz"},
      "arguments": {"type": "object", "description": "Argumenty tego narzedzia danych, z output_dir"}
    },
    "required": ["tool", "arguments"],
    "additionalProperties": false
  },
  "annotations": {"readOnlyHint": true, "openWorldHint": true}
}
```

`check_arguments_schema(tool)` (`catalog/tools.py`) zwraca schemat wejscia narzedzia
danych `tool` bez wlasciwosci `update`, `plan`, `workers` i `summary`.

Kolejnosc walidacji wywolania: (1) nieznana nazwa narzedzia -> blad protokolu
`INVALID_PARAMS` (jedyny przypadek bledu protokolu); (2) argumenty wobec
`input_schema` (`jsonschema.Draft202012Validator`): pierwszy blad -> `invalid_input`
z `details.option` = nazwa wlasciwosci, `message` po polsku z opisem naruszenia; dla
`check_updates` dodatkowo `arguments` wobec `check_arguments_schema(tool)` (`option` =
nazwa wlasciwosci wewnatrz `arguments`; `tool` spoza `enum` = `option="tool"`);
(3) regula sciezek (9.7); (4) dla narzedzi danych i `check_updates` `validate_command`
(`ValidationError` z `option`); (5) wykonanie w watku roboczym.

### 9.5 Wynik i bledy

- Sukces i `ok: false`: `CallToolResult(content=[TextContent(text=<JSON zwarty>)],
  structured_content=<dict>, is_error=<kod wyjscia != 0>)`, gdzie `dict` =
  `report.to_dict()`, a tekst = `report.to_json(indent=None)` (`separators=(",", ":")`,
  `ensure_ascii=False`). `is_error` jest `true` dokladnie wtedy, gdy ten sam dokument
  dalby kod wyjscia CLI != 0 (6.5; D13): `ok: false` (w tym `project_status` z
  niepobranym zadaniem) i kazdy blad.
- Blad: `error_report(exc, command=<id komendy narzedzia>)` (dla `check_updates` - id komendy
  wskazanej przez `tool`), `is_error=True`, ten sam ksztalt (`content` +
  `structured_content`); `OSError` -> `io_error`, inny wyjatek spoza hierarchii ->
  `internal_error` (komunikat `Typ: tekst`; pelny traceback tylko w logu stderr serwera).
- Nie deklarujemy `output_schema` (D11): wynik jest rodzina dokumentow (wynik albo
  `kartograf-error/1`), a `Client` SDK waliduje `structured_content` wobec zadeklarowanego
  schematu - niezgodny wynik bledu wywalalby `RuntimeError` po stronie klienta.
  Kontrakt dokumentow opisuje sekcja 5, katalog (`schemas`) i testy. Generowanie
  `output_schema` z adnotacji dataclass jest mozliwym rozszerzeniem (addytywnym).
- Zawartosc dokumentu nie jest ucinana poza tym, co zapowiedziano (`store_entries`:
  `limit`/`truncated`; `get_catalog`: przeglad, 8.5). Tekst wyniku (`content`) jest
  zwartym JSON (bez wciec), a `structured_content` niesie ten sam dokument: klient, ktory
  podaje modelowi oba, placi dwa razy (przeglad: 2 x 7 315 znakow).

### 9.6 Postep

Narzedzia, ktorych funkcja przyjmuje `on_progress` (`download_data`, `download_collection`,
`download_landcover`, `download_project` - narzedzia `elevation_download`,
`imagery_download`, `landcover_download`, 7 narzedzi grup kolekcji i `project_download`),
raportuja postep notyfikacjami MCP:

- handler jest `async`; praca idzie w watku roboczym (`anyio.to_thread.run_sync`), a
  `on_progress(DownloadProgress)` (wolany z watkow roboczych) przekazuje zdarzenie przez
  `anyio.from_thread.run(ctx.session.report_progress, n, None, tekst)`;
- `n` to licznik zdarzen (1, 2, 3...; rosnie scisle pod blokada, D15), `total` = `None`
  (liczba jednostek bywa nieznana, a protokol zabrania wymyslania sumy), `tekst` =
  `"<status> <jednostka> (<current>/<total>): <message>"` (ASCII, bez pustych skladnikow);
- `report_progress` jest no-op, gdy klient nie przekazal `progressToken` (SDK) - serwer
  raportuje bezwarunkowo;
- bez postepu (brak `on_progress` w API): `soil_download`, `soil_hsg`, `check_updates`,
  `project_check_updates`, narzedzia odczytu; KC-2 (jednolity postep) poza zakresem.

### 9.7 Wspolbieznosc, anulowanie, sciezki

- Wywolania moga isc rownolegle (watek na wywolanie; `MetadataCache` serwera jest
  bezpieczny watkowo); jednoczesnych wywolan narzedzi danych i sprawdzajacych jest
  najwyzej 4 (`anyio.CapacityLimiter(4)`), reszta czeka - nie zalewamy GUGiK i CUZK
  rownoleglymi zadaniami z kilku rozmow.
- Anulowanie przez klienta (`notifications/cancelled`, timeout) nie przerywa trwajacego
  pobrania (KC poza zakresem): watek konczy prace, wersje sa zatwierdzane atomowo (brak
  polowicznych plikow), wynik jest odrzucany. Zamkniecie stdio konczy proces serwera.
- Sciezki w argumentach (`output_dir`, `geometry`, `project_dir`, `path`; `plan` w MCP to
  obiekt dokumentu, nie plik) musza byc **bezwzgledne** (D14): wzgledna = `invalid_input`
  z `option` i `hint` (`Podaj sciezke bezwzgledna, np. /home/ola/dane/kartograf`).
  `--allow-dir` (9.2) zaweza je dodatkowo. Serwer nie czyta ani nie zapisuje niczego
  poza sciezkami z argumentow i swoim plikiem cache.

### 9.8 Konfiguracja klientow

Instalacja: `pip install "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git"`
(po wydaniu: tag `v0.8.0`). Claude Code: `claude mcp add kartograf -- kartograf-mcp`.
Inni klienci (`mcpServers`):

```json
{
  "mcpServers": {
    "kartograf": {
      "command": "kartograf-mcp",
      "args": ["--allow-dir", "/home/ola/dane", "--tools", "discovery,availability,data,check"]
    }
  }
}
```

### 9.9 Instrukcje serwera (`instructions`)

Tekst konstruktora `Server(..., instructions=...)` (polski, ASCII, cztery akapity, do
2000 znakow; Claude Code laduje go na poczatku kazdej sesji i ucina po 4096 znakach).
Narzedzia nie powtarzaja tego, co jest wspolne dla wielu z nich (obszar, sciezki,
tryb aktualizacji, dokument wyniku): mowi o tym `instructions`, raz (D22):

```text
Kartograf pobiera dane przestrzenne Polski i Czech (GUGiK, CUZK, Copernicus, ISRIC) do magazynu wersji w katalogu output_dir. Zacznij od get_catalog (przeglad: grupy, produkty, komendy); parametry komendy: get_catalog(command="elevation download"); kody wyjscia, kody bledow i schematy dokumentow: get_catalog(tables=true). Jakie lata i uklady ma obszar: elevation_availability.
Wspolne argumenty. Sciezki (output_dir, geometry, project_dir, path) podawaj bezwzglednie. Obszar: sheet (godlo arkusza, np. N-34-130-D-d-2-4), bbox ([min_x, min_y, max_x, max_y] w ukladzie bbox_crs, ktory jest wymagany: bez wartosci domyslnej) albo geometry (plik SHP albo GPKG, obwiednia obiektow; layer: warstwa GPKG) - dokladnie jeden; czesc komend ma tez teryt, ku albo whole_country. country: pl, cz albo auto (wymagany z bbox i geometry, z sheet wynika z godla).
Dane wybierasz jawnie (product, resolution, vertical_crs...): Kartograf nie zgaduje; wartosc per kraj to tekst albo {pl, cz}. update: pominiety - tylko brakujace wersje, upgrade - nowsza tresc wg zrodla, force - od nowa; pobranie nie nadpisuje danych. check_updates (tool, arguments) sprawdza aktualnosc bez pobierania; jego plan (kartograf-plan/1) wykonasz z update=upgrade i plan.
Wynik to dokument kartograf-*/1 z polem ok (narzedzia danych: kartograf-download/1); ok=false: czesc jednostek sie nie powiodla (is_error=true, lista failed). Blad to kartograf-error/1 z code, hint i details.option.
```

### 9.10 Testy serwera

Opisane w sekcji 12 (wiersze 12.7-12.8): kontrakt `tools.py` bez `mcp`; klient SDK w pamieci
(`Client(server, raise_exceptions=True)`) z `progress_callback`; test stdio przez
`StdioServerParameters` i podproces `python -m kartograf.mcp_server` (lista narzedzi i
`parse_sheet`, bez sieci); test czystosci stdout (biblioteka nie drukuje; w trybie
serwera wszystko, co trafi na stdout poza protokolem, SDK przekierowuje na stderr).

## 10. Pliki towarzyszace: `py.typed`, `llms.txt`, `scripts/gate.sh`, `CLAUDE.md`

### 10.1 `py.typed` (PEP 561; D17)

- Pusty plik `kartograf/py.typed`.
- `pyproject.toml`: `[tool.setuptools.package-data]` z `kartograf = ["py.typed"]` (bez
  tego wheel go nie zawiera, mimo `packages.find`) oraz klasyfikator `"Typing :: Typed"`;
  `MANIFEST.in`: `include kartograf/py.typed` (sdist).
- Weryfikacja (jednorazowa, kryterium 1 w sekcji 14): zbuduj wheel (np. `python -m build`) i
  `unzip -l dist/*.whl | grep kartograf/py.typed`; w czystym venv z zainstalowanym wheel
  skrypt `from kartograf import download_data` sprawdzony `mypy` nie daje
  `import-untyped`, a `reveal_type(download_data)` pokazuje sygnature, nie `Any`.
  Test w repozytorium nie dowodzi pakowania (plik jest w drzewie zrodel), wiec go nie
  ma.

### 10.2 `llms.txt` (llmstxt.org; D18)

Plik w korzeniu repozytorium (+ `include llms.txt` w `MANIFEST.in`), tekst po polsku
ASCII, **< 150 linii**, linki bezwzgledne `https://github.com/Daldek/Kartograf/blob/main/...`
(plik czyta agent poza repozytorium). Format: `# Kartograf`, cytat z opisem, akapity,
sekcje `##` z listami `- [tytul](url): opis`, sekcja `## Optional`. Projekt tresci:

```text
# Kartograf

> Pobieranie danych przestrzennych Polski i Czech (GUGiK, CUZK, Copernicus, ISRIC) do
> magazynu wersji: NMT/NMPT, LAZ, ortofotomapa, BDOT10k, CORINE, SoilGrids, HSG i inne.
> Trzy interfejsy, ten sam wynik: CLI `kartograf`, biblioteka Pythona, serwer MCP `kartograf-mcp`.

Kazdy plik trafia do katalogu `output_dir` jako niezmienna wersja z sidecarem
`kartograf-meta/1`; nic nie jest nadpisywane. Dane wybierasz jawnie (produkt,
rozdzielczosc, uklad wysokosci, obszar) - Kartograf nie ma cichych wartosci domyslnych.

## Zasady dla agentow
- Zacznij od katalogu: `kartograf catalog --json`; parametry komendy:
  `kartograf catalog elevation download --json`.
- Dodawaj `--json`: stdout to jeden dokument `kartograf-<rodzaj>/1`; blad to
  `kartograf-error/1` z `code`, `hint` i `details`.
- Przed pobraniem sprawdz dostepnosc obszaru: `kartograf elevation availability`.
- Zawsze podawaj `--output` (sciezka bezwzgledna poza repozytorium i poza /tmp) i przy
  `--bbox` uklad `--bbox-crs`.
- Kod wyjscia 0 = ok; 1 = brak kompletnego wyniku (zobacz `ok`, `failed`); 2 = bledne
  dane wejsciowe (popraw wg `hint`); 130 = przerwane.

## Instalacja
- `pip install "kartograf @ git+https://github.com/Daldek/Kartograf.git"` (Python >= 3.12);
  z serwerem MCP: `pip install "kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git"`.

## Typowe zadania (CLI)
[kilka blokow `kartograf ...` z --json: availability, download NMT arkusza, bbox, landcover,
 soil hsg --summary, project add/download/status, parse, list-sources]

## Biblioteka Pythona
[download_data / check_data, check_availability, to_dict()/to_json(), get_catalog, error_report]

## Serwer MCP
[konfiguracja `kartograf-mcp`, rodziny narzedzi, postep, is_error]

## Kody bledow
[tabela 6.2 w skrocie: invalid_input 2, usage_error 2, invalid_sheet_code 2, download_failed 1,
 no_coverage 1, year_out_of_range 1, cache_error 1, invalid_sidecar 1, transform_failed 1,
 transform_unavailable 1, io_error 1, interrupted 130, internal_error 1]

## Dokumentacja
- [Uzycie](.../docs/USAGE.md): przyklady CLI i biblioteki, kody wyjscia i bledow
- [Architektura](.../docs/ARCHITECTURE.md), [Zakres](.../docs/SCOPE.md), [Standardy](.../docs/DEVELOPMENT_STANDARDS.md)
- [Decyzje](.../docs/DECISIONS.md): ADR-037, ADR-045, ADR-046

## Optional
- [Changelog](.../docs/CHANGELOG.md), [Specyfikacja interfejsu dla agentow](.../specs/2026-10-18-agent-interface-design.md)
```

Tresc sekcji w nawiasach kwadratowych jest do napisania (przyklady polecen musza byc
prawdziwe). Test `tests/test_llms_txt.py`: plik jest ASCII i ma < 150 linii; zaczyna sie
od `# Kartograf` i cytatu; kazda linia bloku kodu zaczynajaca sie od `kartograf ` bez
`...` i `<` parsuje sie prawdziwym parserem (`parse_command_line`); kazdy link wskazuje
sciezke istniejaca w repozytorium (`.../blob/main/<sciezka>` -> plik lokalny); wszystkie
kody bledow z tabeli sa w `get_catalog().errors`.

### 10.3 `scripts/gate.sh` (D19)

Jedna komenda bramy, ktora agent uruchamia przed zgloszeniem gotowosci:
`scripts/gate.sh [argumenty pytest]` (argumenty trafiaja do pytest, np. `scripts/gate.sh
-x -k parity`). Plik wykonywalny, konce linii LF, `#!/usr/bin/env bash`,
`set -euo pipefail`.

1. Korzen = katalog nadrzedny skryptu (`cd "$(dirname "${BASH_SOURCE[0]}")/.."`), czyli
   biezacy checkout albo worktree.
2. Python: `$KARTOGRAF_PYTHON`; inaczej `<korzen>/.venv/bin/python`; inaczej `.venv`
   glownego checkoutu (rodzic katalogu z `git rev-parse --git-common-dir`, tam gdzie
   worktree nie ma wlasnego `.venv`); brak = komunikat i kod 2.
3. Kontrola 0: `python -c` (cwd na `sys.path`) sprawdza, ze `kartograf.__file__` lezy
   pod korzeniem; inaczej kod 2 z komunikatem "brama sprawdza inny checkout" (instalacja
   edytowalna wskazuje glowny checkout, a worktree musi testowac wlasny kod - dlatego
   kazdy krok idzie przez `"$PY" -m ...` z cwd = korzen).
4. Kroki, kazdy po naglowku `== <nazwa>`; pierwszy kod != 0 konczy skrypt tym kodem:
   `ruff check .`, `ruff format --check .`, `mypy kartograf/ tests/`, `pytest tests/ -m
   "not live" -q "$@"` (najpierw tanie kroki - szybka porazka).
5. Na koncu `GATE OK (<N> s)`; kod 0.

Nie instaluje zaleznosci (brak `mcp` w venv = testy MCP maja `importorskip`, a `mypy`
zglosi brak modulu - dlatego `dev` zawiera `mcp`, 9.2). Weryfikacja: zielony przebieg w
worktree oraz przebieg z celowo zepsutym plikiem (kod != 0 na odpowiednim kroku).

### 10.4 `CLAUDE.md` (pozycja 8; bez `AGENTS.md`)

Zmiany:

1. W "Zasady pracy (krytyczne)" punkt bramy zastepuje: `scripts/gate.sh` (ruff check,
   ruff format --check, mypy, pytest offline; z worktree tez) - STANDARDS 6.3, 8.3, 18.
2. Nowa sekcja **"Agenci z innych repozytoriow"** (Hydrograf, Archiwista, IMGWTools i
   inne repozytoria, ktorych agenci edytuja Kartografa):
   - zmiany wylacznie na galezi odchodzacej od `develop` (`feat/<temat>`,
     `fix/<temat>`); nigdy na `develop` ani `main`;
   - bez merge do `develop`/`main`, bez push do nich i bez tagow;
   - bez wpisow wydania (nowy naglowek `## [x.y.z] - data` w `docs/CHANGELOG.md`,
     zmiana `__version__`, tag) bez zgody uzytkownika; zmiane opisuje sie w sekcji
     nadchodzacego wydania (`## [Unreleased]`, gdy ostatnie wydanie jest otagowane)
     i w commicie;
   - **przed tagiem obowiazkowy przeglad**: `git log develop..<galaz>`, przeglad diffu
     przez uzytkownika, `scripts/gate.sh` zielony; tag dopiero po jawnej zgodzie;
   - interfejs maszynowy: `llms.txt`, `kartograf catalog --json`, `--json` w kazdej
     komendzie, serwer `kartograf-mcp` (docs/USAGE.md, sekcja "Interfejs dla agentow");
   - nie tworzyc `AGENTS.md`.
3. "Mapa dokumentacji": wiersze o `llms.txt` i interfejsie dla agentow (USAGE, ADR-046,
   ta specyfikacja) oraz o `scripts/gate.sh`.

### 10.5 Pozostala dokumentacja do aktualizacji

| Plik | Zmiana |
|---|---|
| `docs/DECISIONS.md` (CRLF) | ADR-046; relacje po obu stronach w ADR-037, ADR-039, ADR-040 i ADR-045 (status i indeks) |
| `docs/USAGE.md` | nowa sekcja "Interfejs dla agentow": `--json` per komenda (tabela 7.2), **jedna tabela kodow wyjscia i bledow** (6.2, 6.5), katalog, serwer MCP i konfiguracja klientow, `llms.txt`; poprawka opisu `--json` raportu dostepnosci (`schema` pierwszym kluczem, `notices` bez echa na stderr) |
| `docs/ARCHITECTURE.md` | sekcja 2: graf (`serialization`, `error_report`, `sheet_info`, `source_info`, `cache_info`, `store_documents`, `catalog`, `commands`, `mcp_server`; krawedzie `cli -> catalog`, `project -> catalog`, `mcp_server -> catalog, commands, kartograf`; `catalog -> sources, download, landcover, hydrology`), drzewo modulow, nowa 3.6 "Dokumenty JSON `kartograf-*/1`" (lista schematow), nowa 4.11 "Interfejs dla agentow"; reguly Z1 (3) i rejestr komend |
| `docs/DEVELOPMENT_STANDARDS.md` | 7.3: Z8 (CLI i MCP drukuja `to_json()`/`to_dict()`), Z9 (nowa komenda = deklaracja w `catalog/commands/`, nie flagi w `cli/`), Z10 (wyjatek ma `code`/`exit_code`, walidator ustawia `option`), Z11 (schematy `/1` addytywne; nowy dokument = `Document` + test kluczy); 6.3: `scripts/gate.sh`; 11.1: kody bledow; 17.2: przepis na nowa komende przez katalog |
| `docs/SCOPE.md`, `docs/PRD.md` | interfejs dla agentow w zakresie 0.8.0; poza zakresem: HTTP MCP, KC, KH |
| `README.md` | sekcja "Dla agentow AI" (kilka zdan, linki do `llms.txt`, USAGE, serwera MCP) |
| `docs/CHANGELOG.md` | wpis `[0.8.0]` wg sekcji 11 |
| `docs/PROGRESS.md` | wpis konca sesji wg STANDARDS 15 (struktury PROGRESS nie ruszac) |
| `CLAUDE.md` | 10.4 |

## 11. Zmiany lamiace, migracja i wplyw na konsumentow

### 11.1 Zmiany wzgledem 0.8.0-dev (wydanie nietagowane; wpis CHANGELOG `[0.8.0]` do napisania w T8)

| # | Zmiana | Kogo dotyczy | Co zrobic |
|---|---|---|---|
| 1 | Bledy wejscia (`ValidationError`, `ParseError`, `UsageError`) koncza CLI kodem 2 (dzis 1); handlery nie drukuja wlasnych `Error:` za brak `--output`/`--product`, tylko zglaszaja `ValidationError` (D4) | skrypty sprawdzajace `== 1` | testuj `!= 0`; 2 = popraw dane wejsciowe, 1 = awaria/`ok: false` |
| 2 | `AvailabilityReport.to_json()` i `UpdatePlan.to_json()`: `schema` pierwszym kluczem; pole dataclass `schema` zastapione `ClassVar` i wlasciwoscia; `UpdatePlan` dostaje `notices` i `ok` (plan `kartograf-plan/1` ma 2 nowe klucze); `UpdatePlan.from_dict` | czytniki JSON (kolejnosc kluczy), kod budujacy `AvailabilityReport(schema=...)` | czytaj po kluczach; plany 0.8.0-dev nadal sie wczytuja |
| 3 | `--json` wycisza `Info:`/`Warning:` na stderr (sa w `notices`); `elevation availability --json` przestaje je powielac | agenci czytajacy stderr | czytaj `notices` z dokumentu |
| 4 | Parser CLI budowany z katalogu; `kartograf/cli/groups/*.py`, `cli/_args.py` (flagi), `*_task_arguments` znikaja; `create_parser`, `main`, `parse_command_line`, `removed_command_error`, `_subparsers` zostaja jako fasada | testy i kod importujacy wnetrznosci CLI (`cli.groups`, `download_task_arguments`, `_download_arguments`) | uzyc `parse_command(...).options` albo `create_parser()`; testy w repozytorium przepisac (T5) |
| 5 | `calculate_hsg(..., summary=False)`, `HsgReport.summary`; `--summary` wola API zamiast `hsg_statistics` w CLI | Hydrograf (`HSGCalculator` wewnetrznie) - brak wplywu | - |
| 6 | Wyjatki: nowe atrybuty (`code`, `exit_code`, `hint`, `DETAIL_FIELDS`, `ValidationError.option`/`options`/`allowed`), nowa klasa `UsageError`; konstruktory przyjmuja opcjonalne argumenty nazwane | konsumenci biblioteki | addytywne; `except ValidationError` lapie tez `UsageError` |
| 7 | Nowe funkcje i typy w `kartograf.__all__`: `get_catalog`, `data_commands`, `Catalog`, `CommandInfo`, `ParamInfo`, `parse_command`, `validate_command`, `format_command`, `run_command`, `check_command`, `CommandCall`, `describe_sheet`, `SheetInfo`, `find_sheets`, `SheetList`, `list_sources`, `SourceList`, `list_layers`, `LayerList`, `get_cache_info`, `clear_cache`, `CacheInfo`, `describe_store`, `list_store_entries`, `read_store_sidecar`, `StoreOverview`, `StoreEntries`, `StoreSidecar`, `ErrorReport`, `error_report`, `UsageError` | - | addytywne |
| 8 | `TaskDownload.__call__` (`project/commands.py`) dostaje `plan`; `TaskCommand.options` pochodzi z katalogu (kolejnosc kluczy opcji nowych manifestow: `country` zaraz po `product`) | kod rozszerzajacy `COMMANDS` | dodac deklaracje katalogu (STANDARDS 17.2 po zmianie) |
| 9 | `python -m kartograf`; skrypt `kartograf-mcp`; extra `mcp`; `dev` zawiera `mcp` | srodowiska deweloperskie | `pip install -e ".[dev]"` |

Planowany wpis `[0.8.0]` (`docs/CHANGELOG.md`): w "Dodane" - `--json` w kazdej komendzie i
dokumenty `kartograf-*/1`, katalog komend (`kartograf catalog`, `get_catalog`),
warstwa komend KB-2..KB-5, kody bledow z `hint`, serwer MCP (`kartograf[mcp]`),
`py.typed`, `llms.txt`, `scripts/gate.sh`, `python -m kartograf`; w "Zmiany lamiace
(BREAKING)" - pozycje 1-4 z "Co zrobic"; w "Zmienione" - pozycje 5-8.

### 11.2 Wplyw na konsumentow (badanie repozytoriow 2026-10-18)

- **Hydrograf** (`kartograf@v0.7.0`; biblioteka, nie CLI): brak wplywu funkcjonalnego -
  `SheetParser`, `BBox`, `find_sheets_for_bbox`, `DownloadManager`, `GugikProvider`,
  `MetadataCache`, `Bdot10kProvider` bez zmian; `except ValidationError`/`ParseError`
  nadal lapie bledy (nowe atrybuty addytywne); zmiana kodu wyjscia i `--json` go nie
  dotykaja. Migracja 0.7.x -> 0.8.0 jest osobnym tematem (CHANGELOG [0.8.0]).
- **Archiwista** (uzywa tylko nazw z `__all__`: `iter_store`, `read_sidecar`,
  `file_footprint`, `open_project`, `get_project_status`...): `Notice` bez zmian
  (`level`, `code`, `text` - protokol zadan 5.6 i SSE 9.3 pozostaja poprawne); KB-1..KB-5
  dostarczone pod nazwami z 8.6 (SPEC 12.2 do aktualizacji; `cancel` dochodzi z KC);
  `ValidationError.option` pokrywa KB-3; dokumenty JSON moga byc przekazywane przez
  protokol zadan jako `result`. Brak zmian lamiacych po stronie adaptera.
- **Hydrolog, IMGWTools**: brak importow `kartograf` (IMGWTools: tylko wzorzec formatu).

## 12. Strategia testow

Wszystkie offline (`-m "not live"`); frozen clock jak w `tests/parity.py`; testy MCP z
`pytest.importorskip("mcp")` (srodowisko dev ma `mcp`, brama go wymaga).

| # | Plik | Co dowodzi (konsument zobaczy blad) |
|---|---|---|
| 12.1 | `tests/test_serialization.py` | koder: `Path` bezwzgledna, `BBox` -> `{bbox, crs}`, `Decimal`, `tuple`, `NaN` odrzucone, `schema` pierwszy, `JSON_KEYS`/`JSON_FILL` (staly zestaw i kolejnosc kluczy rodziny `kartograf-download/1` dla 5 klas), rejestr `SCHEMAS` (wzorzec nazwy, unikalnosc); `to_json()` bajtowo powtarzalne; hak `__json__` w projekcie (sciezki pinow bezwzgledne); kontekst kodera: `Sidecar.raw` pominiete w `StoreEntries`, obecne w `StoreSidecar` |
| 12.2 | `tests/test_json_contract.py` | tabela schemat -> **dokladna lista kluczy w kolejnosci** dla kazdego dokumentu z sekcji 5 (zmiana klucza = blad) na raportach zbudowanych z fixtur; dokumenty tolerowane przez `from_dict` planu |
| 12.3 | `tests/test_cli_json.py` | kazda komenda-lisc: `main([... , "--json"])` -> stdout to jeden dokument (`json.loads` calosci), znany `schema`, stderr pusty, kod wyjscia wg 6.5; parzystosc CLI `--json` == `api_result.to_dict()` (po normalizacji katalogow magazynow) przez `run_both` dla scenariuszy: arkusz PL, obszar PL, kolekcja, land cover, soil, HSG (`--summary`), `--check-updates`, availability (bajtowo `to_json()`), project init/add/download/status/verify; blad wejscia -> `kartograf-error/1`, kod 2, stderr pusty; blad argparse w trybie JSON -> `usage_error`; tryb tekstowy bez zmian (`Error:` na stderr, kod 2) |
| 12.4 | `tests/test_errors.py` | kazda klasa `KartografError` z pakietu (przeglad modulow) ma wlasny `code` w `__dict__`, kody unikalne i zgodne ze wzorcem, tabela 6.2 (literal w tescie) = `ERROR_CODES`; `error_report`: hint z `hints`/`remedy`/`allowed` + przyklad z katalogu, `details`; scenariusze `option`/`allowed` z 6.1 (brak `product`, zly `product`, brak `output_dir`, brak i zly `vertical_crs`, zla `resolution`, brak obszaru, `bbox` bez `bbox_crs` w MCP, zle godlo, zly `segment` i `units` odczytu magazynu...); `io_error` dla `OSError` (nieistniejacy `output_dir`: `details.path`, `errno`); `invalid_sidecar` takze dla braku pliku sidecara; `internal_error` dla `KeyError`; `interrupted` |
| 12.5 | `tests/test_catalog.py` | (a) parser z deklaracji == katalog: dla kazdej komendy flagi, `dest`, `type`, `choices`, `default`, `nargs`, wykluczanie; kazda flaga parsera jest w katalogu i odwrotnie; (b) `COMMANDS[...].options == {p.name: p.kind}` dla parametrow z `task: true`; (c) `function`/`check_function` istnieja w `__all__`, `argument` komendy to parametr funkcji, parametry bez wartosci domyslnej sa `required`, argumenty tylko nazwane; (d) `allowed` = wynik dostawcy z rejestru; (e) przyklady: `validate_command`, `parse_command(format_command(...)) == (command, options, run)`, `kartograf <command_line>` parsuje prawdziwy parser; (f) ograniczenia: test naruszenia wyprowadzony z przykladu (8.4); (g) `result_schema` w `SCHEMAS`; (h) teksty ASCII, `summary` <= 120; (i) filtry `get_catalog` i bledy (`option="group"`/`"command"`); (j) KB-1: `data_commands()` = 12 komend w kolejnosci `COMMANDS` |
| 12.6 | `tests/test_commands_layer.py` | `parse_command`: opcje podane jawnie, `bbox` z `bbox_crs`, `run` osobno, blad skladni -> `UsageError`, komenda spoza `COMMANDS` -> `ValidationError` z lista; `validate_command` bez sieci (atrapa transportu odrzuca kazde zapytanie); `run_command`/`check_command` = funkcje komend (parzystosc z `download_data`/`check_data`) z `plan` i `update` |
| 12.7 | `tests/test_mcp_tools.py` (bez `mcp`) | `tools.py`: nazwy unikalne i zgodne z `^[a-z][a-z0-9_]*$`; 29 narzedzi; kazda nazwa `CommandInfo.tool` ma narzedzie, a kazde narzedzie poza `check_updates` ma komende; `enum` `check_updates.tool` = narzedzia komend z `project_task` i `supports_check` (12), `check_arguments_schema(tool)` = schemat narzedzia danych bez `update`, `plan`, `workers`; schemat wejscia poprawny wg `Draft202012Validator.check_schema` i zgodny z parametrami katalogu (`argument`, `required`, `enum` = `allowed`, `dependentRequired` dla `bbox`); adnotacje wg `kind`/`effects` (`destructive_hint=false` dla zapisujacych; `check_updates`: RO, OW); opisy ASCII; rodziny `--tools` |
| 12.8 | `tests/test_mcp_server.py` | `Client(server, raise_exceptions=True)`: `list_tools` == `tools.py`; `get_catalog`, `parse_sheet`, `list_sources`, `find_sheets` offline: `structured_content == doc.to_dict()` i tekst == `to_json(indent=None)`; narzedzie danych na fixturach (jak w `test_parity.py`) -> dokument i `is_error` = (kod != 0); `check_updates` na fixturach -> `kartograf-plan/1` rowny `check_command`; `tool` spoza `enum`, `arguments` z `update`/`plan`/`workers` albo bez `output_dir` -> `invalid_input` z `details.option`, `command` bledu = komenda wskazana przez `tool`; `ok: false` -> `is_error=True` z dokumentem raportu; blad wejscia (wzgledna sciezka, nieznany klucz, zly `enum`, `bbox` bez `bbox_crs`) -> `kartograf-error/1`, `details.option`; `OSError` (`store_overview` na nieistniejacym `output_dir`) -> `io_error`; wyjatek spoza hierarchii -> `internal_error`; `progress_callback` dostaje rosnace `progress` z `on_progress` podrobionego pobrania; `--allow-dir`; nieznane narzedzie -> `MCPError`; test stdio: `StdioServerParameters` + podproces `python -m kartograf.mcp_server`, lista narzedzi i `parse_sheet`, stdout zawiera wylacznie ramki protokolu |
| 12.9 | `tests/test_llms_txt.py` | wg 10.2 |
| 12.10 | `tests/test_cli_translation.py`, `tests/test_public_api.py`, `tests/test_cli_help.py`, `tests/test_cli_language.py` | aktualizacja: dozwolony import `kartograf.catalog`/`serialization`; nowe funkcje w `__all__` i ich sygnatury (argumenty nazwane); przyklady `--help` z katalogu; ASCII calego parsera |
| 12.11 | zachowane | `tests/test_parity*.py`, `test_project_*`, `test_availability.py`, `test_cli*.py` przechodza po przepisaniu parsera bez zmiany asercji o zachowaniu (zmieniaja sie tylko importy wnetrznosci i kod wyjscia bledow wejscia) |
| 12.12 | `tests/test_sheet_info.py` (T4d), `tests/test_source_info.py`, `tests/test_cache_info.py`, `tests/test_store_documents.py` (T3) | nowe funkcje biblioteki: `describe_sheet`, `list_sources` i `list_layers` daja te same informacje co dzisiejszy tekst CLI (tabela, hierarchia, potomkowie; kontrola jednorazowa przed/po + testy na fixturach), `SheetInfo.commands` zgodne z `accepts` katalogu, bledy z `option`, brak sieci (atrapa transportu odrzuca kazde zapytanie) i brak zapisu poza `clear_cache`; odczyt magazynu: `limit`/`truncated`, `sidecar.unit` -> `units` (plik krajowy z motywem), zarezerwowana jednostka -> `ValidationError` z `option="units"`, nieistniejacy `output_dir` -> `OSError`, `read_store_sidecar` (`raw` obecne; w `StoreEntries` pominiete), `InvalidSidecarError` dla braku pliku |
| 12.13 | `tests/test_catalog.py`, `tests/test_mcp_tools.py`, `tests/test_mcp_server.py` | budzet kontekstu (D22): przeglad `get_catalog()` <= 8000 znakow zwarty i z wcieciem (CLI), kazda grupa, produkt i komenda w przegladzie, reszta pod `group=`/`command=`/`tables=True`; ten sam zestaw kluczy w kazdym widoku, rzut przegladu, rekord w linii, `view`; `tools/list` <= 30 000 znakow (specyfikacje i drut prawdziwego klienta SDK); kazdy argument ma wpis w `_BRIEF`/`_BRIEF_FOR`, brak przestarzalych wpisow, opisy bez flag CLI i bez powtorzonych wartosci `enum`, najwyzej 80 znakow; narzedzie bez `title`; `instructions` <= 2000 znakow z glosariuszem wspolnych argumentow |

Poza testami stalymi (skrypty jednorazowe, poza repozytorium): zrzut `format_help()` i akcji
argparse kazdej komendy PRZED etapem 2 migracji i porownanie PO (8.2); tekst `list-sources`
kazdej grupy przed/po; wheel z `py.typed` (10.1); przebieg `scripts/gate.sh` w worktree.

## 13. Kolejnosc prac (zadania planu)

| # | Zadanie | Zalezy od | Tor i fala (plan wdrozenia) |
|---|---|---|---|
| T0 | `py.typed` + `pyproject`/`MANIFEST.in`; `scripts/gate.sh`; `kartograf/__main__.py`; zrzut odniesienia (poza repo): `format_help()` i akcje parsera kazdej komendy, `list-sources`, `list-layers`, `parse`, `cache` | - | Tor A, fala 1 |
| T1 | `serialization.py` (`Document`, koder, `SCHEMAS`), migracja `AvailabilityReport`/`UpdatePlan` (schema pierwszy, `notices`, `ok`, `from_dict`), `to_dict()` dla `DataReport`, `CollectionReport`, `LandCoverReport`, `SoilReport`, `HsgReport` (+ `calculate_hsg(summary=)`), `Project`, `ProjectReport`, `ProjectCheck`; testy 12.1-12.2 | - | Tor A, fala 1 |
| T2 | wyjatki (`code`, `exit_code`, `hint`, `DETAIL_FIELDS`, `option`/`allowed`, `UsageError`), `ErrorReport`/`error_report` (bez skladnika (b) hintu z katalogu; `OSError` -> `io_error`), `option`/`allowed` w walidatorach; testy 12.4 | - | Tor A, fala 1 |
| T3 | nowe funkcje biblioteki z przeniesieniem logiki z CLI (moduly poza `catalog/`: `source_info.py`, `cache_info.py`, `store_documents.py`): `list_sources`, `list_layers`, `get_cache_info`, `clear_cache`, `describe_store`, `list_store_entries`, `read_store_sidecar`; testy 12.12 | T1, T2 (kontrakt K1) | Tor A, fala 1 |
| T4a | katalog: `spec.py`, `model.py`, `shared.py`, `kinds.py`, `formatting.py`, `build.py`, `cliparser.py` (parser z deklaracji, przeniesiona logika `_parser.py`), `get_catalog`; zrzut rownowaznosci stary parser <-> katalog | kontrakt K1 (`Document`, `ValidationError.option`/`allowed`, `UsageError` z T1 i T2) | Tor B, fala 1 |
| T4b | deklaracje: `elevation`, `imagery`, availability (+ przyklady, ograniczenia) | T4a | Tor B, fala 1 |
| T4c | deklaracje: `landcover`, `soil`, `hsg`, 7 grup kolekcji | T4a | Tor B, fala 1 |
| T4d | deklaracje: `project`, `cache`, `parse`, `catalog`, tylko-API; `sheet_info.py` (`describe_sheet`, `find_sheets`: `SheetInfo.commands` z `accepts` katalogu); `catalog/hints.py` (`example_for`) | T4a, T3 (nazwy funkcji w `kartograf.__all__`) | Tor B, fala 1 |
| T5 | CLI na katalogu: `create_parser()` z `cliparser`, usuniecie `cli/groups/*` i `*_task_arguments`, handlery z `--json` (dokument albo tekst), `main()` z blednym dokumentem i kodami, komenda `catalog`; `project/commands.py` z opcjami z katalogu i `plan`; `commands.py` (KB-2..KB-5); wpiecie `example_for` w `error_report` (skladnik (b) hintu); testy 12.3, 12.5, 12.6, 12.10-12.11 | T1-T4 | fala 2 (jeden wlasciciel) |
| T6 | `catalog/tools.py` + `mcp_server.py` + testy 12.7-12.8; `mcp` w venv deweloperskim i w `dev` | T4, T5 | fala 3 (z T7) |
| T7 | `llms.txt` + test 12.9 (po T5: polecenia musza byc prawdziwe) | T5 | fala 3 (z T6) |
| T8 | dokumentacja 10.5 (USAGE, ARCHITECTURE, STANDARDS, SCOPE, PRD, README, CLAUDE.md), ADR-046 (jest), CHANGELOG, PROGRESS | T5-T7 | fala 4 |
| T9 | brama pelna (`scripts/gate.sh`), smoke: `kartograf catalog --json`, `--json` kazdej grupy, `kartograf-mcp` przez stdio (lista narzedzi, `parse_sheet`, `elevation_availability` na zywo w katalogu danych poza repo i poza /tmp), wheel z `py.typed` | wszystko | fala 5 |

Wykonanie (plan wdrozenia `docs/superpowers/plans/2026-10-18-agent-interface.md`, sekcja
"Organizacja wykonania"): fala 1 to dwa tory rownolegle w osobnych worktree z rozlacznymi
zbiorami plikow - Tor A (T0-T3: biblioteka, serializacja, wyjatki, raporty) i Tor B
(T4a-T4d: katalog i deklaracje) - z kontraktem K1 (sygnatury `Document`,
`ValidationError.option`/`allowed`, `UsageError`) udostepnionym przez Tor A jako pierwsze
commity; potem sekwencyjnie T5 (jeden wlasciciel: parser i `main` to jeden modul), T6 i
T7 rownolegle, T8, T9.

## 14. Kryteria akceptacji

1. `kartograf/py.typed` w drzewie i w wheel (`unzip -l`); `mypy` na skrypcie konsumenta
   z zainstalowanym wheel nie zglasza `import-untyped`.
2. Kazda komenda-lisc CLI (36 + `catalog`) przyjmuje `--json` i drukuje jeden dokument
   znanego schematu; stderr pusty (poza wyjatkami 7.1); kod wyjscia wg 6.5.
3. Dla scenariuszy 12.3: CLI `--json` == API `to_dict()` (po normalizacji katalogow
   magazynow, przy zamrozonym zegarze); raport dostepnosci bajtowo == `to_json()`.
4. Kazdy wyjatek `KartografError` pakietu ma stabilny `code`, kody sa unikalne; tabela 6.2
   i 6.5 jest jedyna w dokumentacji (USAGE) i jest rowna katalogowi (`errors`, `exit_codes`).
5. Bledy wejscia z walidatorow wspolnych niosa `option` (i `allowed`, gdy znane);
   w trybie `--json` blad to `kartograf-error/1` z `hint` zawierajacym dozwolone wartosci
   i przyklad komendy (scenariusze 12.4).
6. `get_catalog()` = `kartograf catalog --json` = narzedzie `get_catalog`; kazda flaga
   kazdej komendy jest w katalogu i odwrotnie; `COMMANDS[...].options` i sygnatury API
   zgodne z katalogiem (12.5); `data_commands()` zwraca 12 komend (KB-1).
7. Parser CLI jest zbudowany z deklaracji; `kartograf/cli/groups/*` usuniete; `--help`
   kazdej komendy i tabele `list-sources` bez zmian tresci wzgledem odniesienia (poza
   nowa flaga `--json`).
8. `parse_command`, `validate_command`, `format_command`, `run_command`, `check_command`
   dzialaja wg 8.7; przyklady katalogu sa w obie strony zgodne.
9. `kartograf-mcp` wystawia 29 narzedzi (`--tools` zaweza), w tym jedno `check_updates` dla
   12 komend danych; schematy wejscia zgodne z katalogiem; wynik narzedzia == `to_dict()`
   dokumentu; `is_error` == kod CLI != 0; postep rosnie scisle; testy in-memory i stdio
   zielone offline; `import kartograf` dziala bez `mcp`.
10. `llms.txt` (< 150 linii, polecenia prawdziwe) i `scripts/gate.sh` (zielony w worktree,
    != 0 przy bledzie) w repozytorium; `CLAUDE.md` zawiera regule dla agentow z innych
    repozytoriow i wskazuje oba; brak `AGENTS.md`.
11. Brama pelna zielona: `scripts/gate.sh` (ruff, ruff format, mypy, pytest offline);
    dokumentacja z 10.5 i CHANGELOG `[0.8.0]` zaktualizowane.
12. Smoke na zywo (poza repo i poza /tmp): `kartograf elevation availability ... --json`,
    `kartograf-mcp` przez stdio z `elevation_availability` i `parse_sheet`.

## 15. Ryzyka

| Ryzyko | Skutek | Ograniczenie |
|---|---|---|
| Przepisanie parsera (T5) psuje `--help` albo zachowanie flag (10 tys. linii `test_cli.py`) | regresje CLI tuz przed wydaniem | etapy z porownaniem `format_help()` i zrzutu akcji przed/po; stary parser zostaje do zielonych testow rownowaznosci; `choices` i brak `required` odtwarzane wprost |
| SDK `mcp` 2.x zmienia API podwersjami (3 wydania w 6 tygodni) | zlamany serwer po aktualizacji | pin `<3`, kontakt z SDK w jednym module, testy in-memory i stdio w bramie |
| 29 narzedzi = koszt kontekstu: 65 893 znakow `tools/list` (ok. 16,5 tys. tokenow) i 47 807 znakow `get_catalog()` w pierwszej wersji; 12 blizniakow `_check_updates` zastapionych jednym narzedziem `check_updates` (O4), potem skrocenie opisow i widok przegladowy (D22: 28 607 i 7 315 znakow); limity klientow | gorsza selekcja narzedzi, droga pierwsza rozmowa | `--tools`, `get_catalog` jako przeglad (8.1), opisy na wywolanie (9.4), wspolne znaczenia w `instructions` (9.9); budzety w testach: 30 000, 8 000 |
| Kod wyjscia 2 dla bledow wejscia (D4) zaskakuje skrypty | falszywe alarmy | jawny wpis BREAKING z "Co zrobic"; O2 |
| Rozjazd katalogu z walidatorami biblioteki (ograniczenia) | agent dostaje bledna wiedze | testy naruszen z przykladow (8.4); zrodlem zachowania jest biblioteka |
| Biblioteka drukuje na stdout w trakcie wywolania | psuje ramki MCP / dokument `--json` | test czystosci stdout w obu trybach; SDK przekierowuje zrzuty na stderr, ale to ostatnia linia obrony |
| Dlugie pobrania blokuja watki; brak anulowania (KC) | zawieszone rozmowy | limit 4 wywolan, `workers`, dokumentacja; KC osobno |
| Narzedzia pisza po dowolnym `output_dir` i czytaja dowolna `geometry` | niezamierzony zapis/odczyt poza projektem | sciezki bezwzgledne, `--allow-dir`, adnotacje, zatwierdzanie wywolan przez klienta |
| Windows: sciezki i kodowanie stdout | rozne dokumenty | `as_posix()`, wymuszone UTF-8; `pywin32` w zaleznosciach `mcp` |
| Brak `mcp` w `.venv` (brama: mypy, testy) | brama niezielona | `dev` zawiera `mcp`; instalacja w `.venv` glownego checkoutu za zgoda koordynatora, addytywnie (O7) |

## 16. Rozstrzygniecia kwestii O1-O9 (decyzje koordynatora 2026-10-18)

Kwestie otwarte z projektu specyfikacji rozstrzygnal koordynator; tresc specyfikacji jest
z nimi zgodna (kolumna "Skutek").

| # | Kwestia | Rozstrzygniecie | Skutek w specyfikacji |
|---|---|---|---|
| O1 | Klucz tekstu komunikatu w JSON: brief mowi `message`, kod, Archiwista (SPEC 5.6, 7.9, SSE 9.3) i `kartograf-availability/1` maja `text` | `text` (zgodnie z rekomendacja); blad ma `message` | D3, 5.3 |
| O2 | Kod wyjscia dla bledow wejscia | 2 dla `ValidationError`/`ParseError`/`UsageError`; wpis BREAKING w CHANGELOG `[0.8.0]` | D4, 6.5, 11.1 poz. 1 |
| O3 | `is_error` w MCP dla `ok: false` | tak: `is_error` = kod wyjscia CLI != 0 | D13, 9.5 |
| O4 | Granularnosc narzedzi MCP | narzedzie na komende katalogu, ale bez 12 blizniakow `_check_updates`: jedno narzedzie `check_updates` z parametrami `tool` (`enum` nazw narzedzi danych) i `arguments` (obiekt walidowany schematem wskazanego narzedzia danych przez `validate_command`); adnotacje RO, OW; dokument `kartograf-plan/1`; razem 29 narzedzi (mniej narzedzi = mniej kontekstu i lepszy wybor narzedzia przez agenta); pole katalogu `CommandInfo.check_tool` usuniete (zbedne), w katalogu zostaje `supports_check: bool` | D12, 8.1, 9.3-9.6, 9.9, 12.7-12.8, 14.9, 15 |
| O5 | Zakres KB-2..KB-5 w 0.8.0 | w zakresie: `parse_command`, `validate_command`, `format_command`, `run_command`, `check_command` | D10, 8.6, 8.7 |
| O6 | Parser CLI z deklaracji (D7) kosztem przepisania 14 plikow `cli/groups` | tak; migracja grup z porownaniem zrzutu `--help` i parsowania przed i po (zrzut poza repo) | D7, 8.2, 13 |
| O7 | Instalacja `mcp>=2.3.0,<3` w `.venv` (i w `dev`) | zgoda: instalacja w `.venv` glownego checkoutu (addytywnie) i wpis w extra `dev` | 9.2, 15 |
| O8 | Cache serwera MCP | jak w 9.2: domyslnie plik w katalogu cache uzytkownika, `--allow-dir` opcjonalne | 9.2 |
| O9 | Status ADR-046 | `Przyjeta` | ADR-046 |

### 16.1 Uzgodnienia ze zmianami na galezi bazowej (przeglad API odczytu magazynu, merge `8c65f4e`)

Sprawdzenie specyfikacji wzgledem kodu galezi po poprawkach przegladu (ADR-045; commity
`f33f037`, `a189f25`):

| Zmiana w kodzie i dokumentacji galezi bazowej | Poprawka w specyfikacji |
|---|---|
| `Sidecar.unit` pliku krajowego z motywem to nazwa pliku slotu (`pl_miejscowosci`), przyjmowana przez `iter_store(units=...)` | 2, 5.4.10: `sidecar.unit` -> `units` zamyka petle odswiezania jednostki |
| `InvalidSidecarError` obejmuje brak pliku sidecara; sidecar bez pola `schema` jest przyjmowany w ksztalcie `emit_sidecar`; `Sidecar.schema` jest zawsze `kartograf-meta/1` | 2, 5.4.10, 6.1 (`DEFAULT_HINT`), 6.2 |
| `iter_store`: bledne argumenty (segment, zarezerwowana jednostka, nazwa dluzsza niz 255 bajtow, `units` bez `segment`) to `ValidationError` od razu przy wywolaniu | 6.1: wymagane `option` (`segment`, `units`) w walidatorach magazynu |
| Brak albo niedostepny `output_dir` to `OSError`, nie pusty magazyn | D21, 6.2-6.3, 6.6, 9.5: kod `io_error` (kod wyjscia 1) zamiast `internal_error` |
| `StoreEntry` i `Sidecar` jawnie niehashowalne (pola `dict`) | 5.1: koder nie opiera sie na hashowaniu; `ctx.omit` pomija `Sidecar.raw` w `StoreEntries` |

### 16.2 Zmiany strukturalne wynikajace z planu wdrozenia

Plan (`docs/superpowers/plans/2026-10-18-agent-interface.md`) rozdziela prace na dwa rownolegle
tory o rozlacznych zbiorach plikow; to wymusilo cztery korekty tej specyfikacji (tresc wyzej jest
juz zgodna z nimi):

| Korekta | Powod | Miejsce |
|---|---|---|
| `list_sources` i `list_layers` w `kartograf/source_info.py` (nie `catalog/sources.py`) | tor biblioteki nie tworzy plikow w pakiecie toru katalogu; katalog korzysta z rejestru, nie z tych funkcji (A6) | 5.4.6, 5.4.7, 8.2 |
| `describe_sheet` i `find_sheets` w `kartograf/sheet_info.py`, zadanie T4d | `SheetInfo.commands` wylicza sie z `ParamInfo.accepts` katalogu | 5.4.4, 8.2, 13 |
| nowe moduly katalogu `kinds.py`, `formatting.py`, `hints.py`; skladnik (b) hintu bledu wpina T5 | wspolny kod parsera, `format_command` i `ExampleInfo.command_line` bez cyklu `catalog` <-> `commands`; `error_report.py` ma jednego wlasciciela na raz | 8.2, 6.3, 13 |
| `kartograf.mcp_server` importuje sie bez `mcp`; `create_server` rzuca `ImportError`, `main()` drukuje komunikat | poprzednie sformulowanie ("import rzuca `ImportError`" i "`main()` go drukuje") bylo sprzeczne | 9.2 |

### 16.3 Koszt kontekstu agenta (D22; pomiar 2026-10-18)

Pomiar na prawdziwej sesji stdio (`initialize`, `tools/list`, `tools/call`; dlugosc w
znakach, JSON zwarty), przed = `0bb7702e`, po = `86168139`:

| Wielkosc | przed | po |
|---|---|---|
| `tools/list` (29 narzedzi) | 65 893 | 28 607 |
| `instructions` serwera | 686 | 1 447 |
| `get_catalog()` (tekst wyniku; `structured_content` ma tyle samo) | 47 807 | 7 315 |
| `get_catalog(group="elevation")` | 10 761 | 4 796 |
| `get_catalog(command="elevation download")` | 26 312 | 20 347 |
| `get_catalog(tables=True)` | (tabele w kazdym widoku) | 13 294 |
| `kartograf catalog --json` | 62 389 | 7 629 |
| `kartograf catalog elevation download --json` | 37 546 | 29 717 |

Zmiany kontraktu wzgledem wersji narzedzi i katalogu z T6 (wydanie 0.8.0 jest
nietagowane, wiec to nie sa zmiany lamiace wzgledem 0.7.x; trafiaja do dokumentacji T8):

1. `kartograf-catalog/1`: nowy klucz `view` (drugi), tabele `exit_codes`, `errors`,
   `schemas` sa `null` dopoki nie zazadano (`tables=True`; caly katalog z parametrami ma je
   nadal); dokument przegladu ma rekordy `{name, summary, products[]}` i `{id, summary,
   tool, supports_check}` (8.1).
2. `get_catalog(*, group, command, params, tables)`: domyslny widok to przeglad (8.5);
   `kartograf catalog --json` bez grupy ma 7,6 tys. znakow, tabele daje `--params --json`
   (bez `GRUPY`) - osobnej flagi `--tables` nie ma (8.4, 7.4).
3. Narzedzia MCP: te same 29 nazw; bez `title`; opisy skrocone (9.4); `get_catalog` ma
   argumenty `group`, `command`, `params`, `tables`; `command` w `get_catalog` oraz
   `product` w `list_sources` i `list_layers` bez `enum`; narzedzia danych odsylaja do
   `get_catalog(command="...")`.
4. `instructions` serwera: cztery akapity (<= 2000 znakow) z glosariuszem wspolnych
   argumentow i znaczeniem `ok=false` (9.9).
5. Podsumowanie komendy `landcover download` bez flagi CLI (`Pobierz dane wybranego
   produktu pokrycia terenu`).
6. Do sprawdzenia przy scalaniu z torem CLI: `_FOOTER` w `cli/catalog_cmd.py` (mowi, ze
   tabele daje `kartograf catalog --json`; teraz `kartograf catalog --params --json`).
