# E2E interfejsu dla agentow AI (2026-10-18): wheel z `py.typed`, `--json`, katalog, serwer MCP przez stdio, Claude Code

Galaz `feat/agent-interface-e2e` (od `1a300b7d`, pelna implementacja po scaleniu torow), jedna
poprawka znaleziona w E2E: `a7ba1336`. Plan: `docs/superpowers/plans/2026-10-18-agent-interface.md`
(T9), spec: `docs/superpowers/specs/2026-10-18-agent-interface-design.md` (sekcje 14 i 16).

Metoda. Wheel i sdist zbudowane `python -m build` z `git archive HEAD` poza repo (sdist, potem wheel
z sdist), zainstalowane w czystych venv (`python3.13 -m venv`; powtorzenie offline i drutu MCP na
Pythonie 3.12.15). CLI to skrypt `kartograf` z zainstalowanego wheel (nie kod z drzewa), cwd = korzen
worktree (cache metadanych `.kartograf_cache.db` zostaje lokalnie, STANDARDS 6.4), serwer
`kartograf-mcp` z tego samego wheel, klient: prawdziwy SDK `mcp` 2.3.0 (`Client`,
`StdioServerParameters`) oraz reczny klient JSON-RPC (pomiary na drucie). Dane na zywo wylacznie w
`<katalog-danych>/kartograf-live/agent-interface/` (jawne `-o`/`output_dir`, ok. 80 MB), venv, wheel i
skrypty jednorazowe w `<katalog-danych>/kartograf/agent-interface/e2e/` (poza repo i poza `/tmp`).
Wszystkie kroki ponowiono na wheel z `a7ba1336` (liczby ponizej pochodza z tego przebiegu; pierwszy
przebieg na `1a300b7d` dal te same wyniki produktu poza bledem B1).

## Werdykt

**Kod gotowy do wydania 0.8.0, bez blokerow.** E2E znalazlo jeden blad (B1: serwer MCP konczyl sie
tracebackiem, gdy nie mozna utworzyc katalogu cache) - naprawiony i objety testem (`a7ba1336`). Reszta
uwag to odchylenia planu T9 od rzeczywistego zachowania uslug i drobne pozycje do decyzji (sekcja
"Uwagi"), zadna nie blokuje wydania.

**Dokumentacja (T8) nie jest scalona na tej galezi**: `docs/*.md`, `README.md` i `CLAUDE.md` nie
wspominaja `kartograf-mcp`, `py.typed`, `llms.txt`, `catalog --json` ani `scripts/gate.sh`, nie ma
`tests/test_docs_tables.py`. Kryteria 4 (tabela w USAGE), 10 (regula w `CLAUDE.md`) i 11 (dokumentacja,
CHANGELOG `[0.8.0]`, PROGRESS) czekaja na T8; wydanie po jego scaleniu i po ponownej bramie.

## Kryteria akceptacji speku (sekcja 14)

| # | Kryterium | Wynik | Dowod |
|---|---|---|---|
| 1 | `py.typed` w drzewie i wheel; `mypy` konsumenta bez `import-untyped` | tak | E2E-5 |
| 2 | kazda komenda-lisc (36 + `catalog`) przyjmuje `--json`, jeden dokument, stderr pusty, kod wg tabeli | tak | E2E-1, E2E-7, E2E-12 |
| 3 | CLI `--json` == API `to_dict()`; raport dostepnosci bajtowo == `to_json()` | tak | E2E-2, E2E-6 |
| 4 | stabilne unikalne kody bledow; tabele w USAGE rowne katalogowi | kody tak; tabela w USAGE czeka na T8 | E2E-1, kontrola z tabelami |
| 5 | bledy wejscia niosa `option`/`allowed`, w `--json` `kartograf-error/1` z `hint` | tak | E2E-1, E2E-4, E2E-9 |
| 6 | `get_catalog()` = `catalog --json` = narzedzie `get_catalog`; `data_commands()` = 12 | tak | E2E-4, E2E-12 |
| 7 | parser z deklaracji, `cli/groups/*` usuniete, `--help` bez zmian tresci | tak, z odchyleniami przykladow (U6) | zrzut `--help`, E2E-12 |
| 8 | warstwa komend KB-2..KB-5 | tak | E2E-12 |
| 9 | `kartograf-mcp`: 29 narzedzi, schematy z katalogu, wynik == `to_dict()`, `is_error` == kod CLI != 0, postep rosnie scisle, `import kartograf` bez `mcp` | tak | E2E-4, E2E-8, E2E-12 |
| 10 | `llms.txt` (< 150 linii), `scripts/gate.sh`, `CLAUDE.md` z regula, brak `AGENTS.md` | `llms.txt` (145 linii), `gate.sh` (zielony, kod != 0 przy bledzie), brak `AGENTS.md` tak; regula w `CLAUDE.md` czeka na T8 | brama, E2E-12 |
| 11 | brama pelna; dokumentacja 10.5, CHANGELOG, PROGRESS | brama tak; dokumentacja czeka na T8 | brama |
| 12 | smoke na zywo: `availability --json`, `kartograf-mcp` z `elevation_availability` i `parse_sheet` | tak | E2E-2, E2E-4 |

## Brama (`scripts/gate.sh`)

| Stan | ruff check | ruff format --check | mypy | pytest (offline) | czas |
|---|---|---|---|---|---|
| `1a300b7d` | czysto | 305 plikow bez zmian | 0 bledow w 303 plikach | 7069 passed, 18 deselected, 147,80 s | 166 s |
| `a7ba1336` | czysto | 305 plikow bez zmian | 0 bledow w 303 plikach | 7070 passed, 18 deselected, 153,72 s | 156 s |

`mypy` wypisuje 75 notatek `annotation-unchecked` (nie bledy; 20 w `tests/test_serialization.py`).
Testow `live` repo (`-m live`, 18 odznaczonych) nie uruchamiano: plan T9 ich nie wymaga (E2E ponizej
wykonuje zapytania na zywo przez CLI i serwer MCP).

## Wyniki

### E2E-1 katalog i `--json` offline (zainstalowany wheel)

- 34 wywolania: `catalog --json` (7 629 znakow, 13 grup, 41 komend, widok `overview`), `catalog
  elevation download --json` (29 717 znakow, 30 parametrow, 4 przyklady), `list-sources` x11,
  `list-layers` x2 (`landcover --product corine`, `soil`), `parse` PL i CZ, `cache path`, `cache stats`,
  `project init`, `add`, `status`, `verify` i 10 bledow. 34/34: stdout to jeden dokument (`json.loads`
  calosci, `\n` na koncu), znany `schema` jako pierwszy klucz, stderr pusty, kod wg tabeli; kazde
  wywolanie 0,6-0,7 s. `--help` wszystkich 37 komend-lisci zawiera `--json`. Powtorzone na Pythonie
  3.12.15: 34/34, dokumenty bajtowo identyczne.
- Bledy (w trybie `--json`: `kartograf-error/1` na stdout, stderr pusty):
  - `elevation download --product nmt --json`: kod 2, `invalid_input`, `details.options` =
    `sheet, bbox, geometry`, `hint: null` (U2); z `--sheet`, bez `-o`: kod 2, `details.option ==
    "output_dir"`, w `hint` przyklad komendy;
  - `elevation download --product foo --json`: kod 2, `usage_error`, `command: "elevation download"`,
    `hint`: `Parametry komendy: kartograf catalog elevation download. Przyklad: ...`; `frobnicate`: kod 2,
    `usage_error`, `command: null`; `parse ZZZ`: kod 2, `invalid_sheet_code` z formatami godel w `hint`;
  - `project add ... --json` po nazwie zadania: kod 2, `option: json`, komunikat podaje poprawne miejsce
    flagi; `project status` i `verify` przed pobraniem: kod 1, `ok: false`, `not_downloaded: ["arkusz"]`
    (U3); `project status` bez manifestu: kod 2;
  - poprawny arkusz do `-o /dev/null/...`: kod 1, `io_error`, `details.errno: ENOTDIR`, `hint` ze sciezka;
    `project init` pod plikiem: kod 2, `invalid_input`;
  - Ctrl-C (SIGINT po 3 s zapytania sieciowego): kod 130; `--json`: `interrupted` z `command`, stderr pusty;
    tekst: `Error: przerwano (Ctrl-C)`; `KARTOGRAF_DEBUG=1`: traceback, kod 1; tekst bez `--json`:
    `Error:` na stderr, kod 2, stdout pusty.

### E2E-2 availability na zywo

- Krakow `--bbox 565000,242000,569000,246000`, Pomorze `339000,744800,343000,747000` (`--force`, z cache,
  z `--bbox-crs`), Cieszyn `--country auto`: `CLI --json` == `check_availability(...).to_json()` bajtowo
  poza `checked_at` (ten sam cache); `--force` == z cache == z `--bbox-crs EPSG:2180`; stderr pusty.
- Krakow: 20 kombinacji (17 kompletnych): 2025, 2024, 2023, 2022, 2019 PL-1992 1m (6/0), 2023 i 2021
  PL-2000 1m (15/0), 2019 5m ASC i ASCII-NMT (6/0), 2018 XYZ/TBD niekompletne - zgodnie z planem A.
- Pomorze: lad 86,38 ha, 15 kombinacji (5 kompletnych): NMT 2025 0.5m 0/4 niekompletna, 2022 1m 3/0
  niekompletna (8 782 m2 bez arkuszy), najnowsza kompletna to 2010 TBD 25m KRON86 - zgodnie z planem A.
- Cieszyn: obszary PL 1,77 km2 i CZ 3,49 km2 (jak plan B), `notices` z `cz_service_only` w dokumencie,
  nie na stderr.
- Czasy: Krakow 5,84 s (siec), 2,34 s (CLI z cache), 1,81 s (biblioteka); Pomorze 5,28 / 1,50 / 0,88 s;
  dokumenty 20 833 i 16 513 znakow.

### E2E-3 pobranie, ponowienie, sprawdzenie

- `elevation download --product nmt --sheet M-34-64-D-d-1-2 --resolution 5m --vertical-crs EVRF2007 -o
  <magazyn> --json` (arkusz Krakowa, U1): `new` (1,53 s); plik 1 680 683 B, sha256 `23d160d0...` rowny
  sidecarowi, siatka 469 x 454, 5 m, wysokosci 197,4-225,3 m, 97,3% waznych; ponowny przebieg `local`
  (0,60 s); `--check-updates --json`: `kartograf-plan/1`, pozycja `current` (1,17 s).
- Projekt: `init`, `add`, `status` przed pobraniem (kod 1), `project download` -> `kartograf-project-report/1`,
  `pinned` (4,1 s), `status` i `verify` kod 0 `ok: true`, `project download --check-updates` -> `current`.

### E2E-4 serwer MCP przez stdio

SDK (`kartograf-mcp --allow-dir <katalog-danych> --cache-file <cache>`), 72 sprawdzenia, 72/72:

- `initialize`: `serverInfo` `kartograf` 0.8.0, protokol `2026-07-28`, `instructions` 1 447 znakow ==
  `INSTRUCTIONS`; `list_tools` = 29 narzedzi (nazwy == katalog + `check_updates` + `project_check_updates`),
  bez `title`, schematy poprawne wg Draft 2020-12; `--tools discovery,availability` zaweza do 6 narzedzi.
- `parse_sheet`, `get_catalog` (przeglad i `command`), `list_sources`, `list_layers`: dokument == dokument
  CLI (wartosci i kolejnosc kluczy), tekst wyniku == zwarty JSON z `structured_content`; `find_sheets`: 6
  arkuszy Krakowa; `elevation_availability` Krakow i Pomorze == dokument CLI.
- `elevation_download` arkusz: `new`, plik o tym samym sha256 co pobranie CLI, jedno zdarzenie postepu
  `start M-34-64-D-d-1-2 (0/1): rozdzielczosc: 5m` (`total` = `None`); drugi raz `local`. Obszar 6
  arkuszy 5m (10 104 115 B): 6 zdarzen `completed <arkusz> (n/6)`, `progress` 1..6 scisle rosnaco.
- `check_updates` z `tool: elevation_download` na magazynie z E2E-3: `current`. `store_overview` (==
  biblioteka, tekst w UTF-8 bez ucieczek `\u00b7`), `store_entries` (3 wpisy: `link`, `full_sheet`,
  `version`; `truncated: false`), `store_sidecar` (sha256 == plik).
- 9 bledow jako `kartograf-error/1` z `is_error: true` (8 wejscia i 1 `io_error`: sciezka wzgledna, poza
  `--allow-dir`, `bbox` bez `bbox_crs`, `product: foo`, nieznany argument, `update` w `check_updates`, zly
  `tool`, zle godlo, brak katalogu magazynu); nieznane narzedzie to blad protokolu `-32602`; `ok: false`
  (arkusz bez 5 m) daje `is_error: true` z raportem `kartograf-download/1` rownym dokumentowi CLI (kod 1).
- Narzedzia projektu: `project_init`, `add`, `status` (`is_error: true`, `ok: false`), `download` z
  postepem, `status`, `verify`, `check_updates` (`ok: true`), `remove`.
- Domyslny cache: `$XDG_CACHE_HOME/kartograf/metadata.db` (3,5 MB), nie w cwd serwera.

Na drucie (E2E-4b, reczny JSON-RPC, protokol 2025-06-18), 17/17, powtorzone na 3.12: `tools/list` 28 641
znakow ramki i 28 597 znakow tablicy `tools` (budzet 30 000; spec 16.3 podaje 28 607); klucze camelCase
(`inputSchema`, `readOnlyHint`, `isError`, `structuredContent`), bez `title`, `outputSchema`, `$ref`;
`get_catalog`: ramka 15 524 znakow (tekst 7 315 + `structuredContent` 7 315 + koperta);
`notifications/progress` powtarza `progressToken`, bez tokenu brak notyfikacji; kazda linia stdout to
ramka JSON-RPC, stderr pusty, kod 0 po zamknieciu stdin.

### E2E-5 wheel z `py.typed`

- `python -m build` (5,6 s): `kartograf-0.8.0-py3-none-any.whl` 741 767 B, 153 pliki, `kartograf/py.typed`
  (0 B), skrypty `kartograf` i `kartograf-mcp`, bez `kartograf/cli/groups/` i `tests/`; sdist 3 699 370 B,
  1285 plikow, z `kartograf/py.typed` i `llms.txt`; METADATA: `Typing :: Typed`, extra `mcp` =
  `mcp<3,>=2.3.0`, `Requires-Python >=3.12`.
- Czyste venv + wheel, `mypy` 2.4.0 na `consumer.py` (`from kartograf import BBox, download_data,
  get_catalog`, 8 x `reveal_type`): `Success: no issues found`, brak `import-untyped`. `download_data` to
  `def (*, product: str | None, output_dir: str | Path | None, sheet: str | None =, ...) -> DataReport`,
  `get_catalog` -> `Catalog`, `to_json()` -> `str`; `--strict` czysto. `consumer_bad.py` (`product=123`,
  argument pozycyjny, `group=5`) daje 3 bledy (`arg-type`, `call-arg`, `arg-type`), wiec sygnatury nie sa
  `Any`. Kontrola negatywna: po zdjeciu `py.typed` `mypy` zglasza `import-untyped` i `Revealed type is
  "Any"`.
- Instalacja bez extra `[mcp]` (osobne venv): `kartograf --version`, `catalog --json`, `parse --json`
  dzialaja; `import kartograf` nie laduje `mcp` ani `kartograf.cli`; `kartograf-mcp --version` kod 0,
  `kartograf-mcp` kod 1 z jednym wierszem `Brak pakietu mcp: pip install "kartograf[mcp]"` na stderr,
  stdout pusty; `mypy` konsumenta tak samo czysto.

### E2E-6 parzystosc trzech drog

- `check` arkusza z E2E-3: CLI `--check-updates --json`, `check_data(...).to_dict()` i narzedzie
  `check_updates`: identyczne dokumenty poza `checked_at` (wartosci i kolejnosc kluczy); stdout CLI ==
  `to_json()` bajtowo, tekst MCP == `to_json(indent=None)`.
- Tak samo: `parse` (CLI, biblioteka, MCP), `availability` (3 drogi), pobranie obszaru 6 arkuszy (CLI,
  biblioteka, MCP: jeden dokument po normalizacji sciezki magazynu i etykiety statusu), `store_*`
  (biblioteka == MCP).

### Dodatkowe scenariusze

- **E2E-7 rodziny danych na zywo** (po jednym malym pobraniu `--json`, ponowny przebieg i
  `--check-updates`): 7/7 kod 0, `ok: true`, pliki istnieja pod sciezkami bezwzglednymi: `soil download`
  (639 B), `soil hsg --summary` (1 100 B, ponowny przebieg `reused`), CORINE bez poswiadczen (PNG 20 x 20
  px, notice `corine_preview`), `boundaries admin` gmina (241 664 B), `names geographic` (106 496 B;
  zrodlo PRNG: `notices` `slow_source`, na stderr wiersze ponowien HTTP dopuszczone przez spec, 332 s),
  ortofotomapa wycinek (481 135 B), NMT wycinek WCS (262 902 B). Ponowny przebieg `local`;
  `--check-updates`: `current` dla gleb, `unverifiable` dla pozostalych.
- **E2E-8 plan, wspolbieznosc, `--allow-dir`** (13/13): plik `--check-updates --plan PLIK` rowny
  dokumentowi na stdout bajtowo, bez wiersza `Info:`; `--upgrade --plan` wykonuje plan (sama pozycja
  `current`: brak pobran); ten sam plan jako obiekt w MCP (`update: upgrade`, `plan`) dziala; plan innego
  magazynu, nieznany schemat i brak pliku to kod 2; `store_entries` `limit: 1` -> `truncated: true`;
  `--allow-dir` odrzuca `..`, dowiazanie symboliczne poza katalog, jego potomka i sasiada o wspolnym
  prefiksie, przyjmuje `./x/../x`; 8 rownoleglych `elevation_availability` (4 z `force`) przez jedno
  polaczenie i wspolny cache: wszystkie poprawne i rowne wynikom sekwencyjnym, 10,8 s wobec 23,7 s
  jedno po drugim.
- **E2E-9 brzegi** (30/30): cykl `cache` przez CLI (`path` bez bazy `exists: false`, po `availability`
  `exists: true` i `size_bytes`, `stats` z `entries` wg rodzaju, `clear` -> `cleared: true`); baza
  nieczytelna: `cache path` dziala (nie otwiera bazy), `cache stats` kod 1 `cache_error` z `hint`,
  `cache clear` -> `removed_unreadable: true`; `parse ... -q` (komenda bez `-q`) kod 2 `usage_error`;
  `--json -q` na pobraniu daje ten sam dokument; `kartograf --json parse ...` kod 2 `usage_error`;
  `catalog <zla grupa>` kod 2 z `allowed`; 10 bledow wejscia MCP z `details.option` (brak `sheet`, `bbox`
  jako napis, 3 liczby, zly `bbox_crs`, `limit: "5"`, `workers: 0`, nieznana komenda katalogu, nieznana
  opcja w `project_add`, brak `output_dir` w `check_updates`, zly `scale`); wywolanie bez obiektu
  `arguments` dziala; `year: "2019"` to `invalid_input`; `store_overview` z `LC_ALL=C PYTHONUTF8=0
  PYTHONIOENCODING=ascii` zwraca `\u00b7` poprawnie.
- **E2E-10 tekst i `--workers`**: pobranie obszaru bez `--json`: pasek postepu i podsumowanie `Nowe: 6,
  ...` jak dotad, kod 0; `--workers 3 --json`: `ok`, `files` posortowane, dokument == sekwencyjny.
- **E2E-11 srodowisko bez zapisu** (po poprawce B1): `HOME=/proc/nohome` albo `--cache-file` pod zwyklym
  plikiem: serwer startuje, `parse_sheet` i `elevation_availability` dzialaja, na stderr jedno ostrzezenie
  o katalogu cache i komunikat cache biblioteki, bez tracebacku, kod 0 po zamknieciu.
- **E2E-12 komendy, warstwa komend, pakowanie** (20 sprawdzen): kazda z 37 komend-lisci z samym `--json`
  (katalog scratch) daje jeden dokument znanego schematu, `schema` pierwszy, stderr pusty: 16 wynikow
  (kod 0: `list-sources` x11, `soil list-layers`, `catalog`, `cache stats`, `clear`, `path`) i 21 bledow
  `kartograf-error/1` (kod 2, `command` = id komendy). `data_commands()` = 12; `parse_command` ->
  `format_command` -> `parse_command` (po obcieciu prefiksu `kartograf `, O2) zwraca to samo; `run_command` == `download_data` i
  `check_command` == `check_data` (dokumenty rowne); biblioteka nie importuje `kartograf.cli` ani `mcp`;
  `scripts/gate.sh` na kopii z dopisanym nieuzywanym importem konczy sie kodem 1 na `ruff check`, bez
  dojscia do kolejnych krokow. Dwa sprawdzenia skryptu, ktore zalozyly `option` dla bledu braku obszaru,
  byly bledne (U2/O1), nie kodu.

### Claude Code (model `haiku`)

- `claude mcp add kartograf -- kartograf-mcp ...` (zakres lokalny, katalog scratch): `claude mcp list` i
  `get` -> `Connected`; serwer usuniety po tescie (w zakresie projektu `.mcp.json` serwer czeka na
  zatwierdzenie w sesji interaktywnej).
- Przebieg: `claude -p --model haiku --mcp-config ... --strict-mcp-config --tools "" --allowedTools
  mcp__kartograf --permission-mode dontAsk --no-session-persistence` w katalogu poza repo; model
  `claude-haiku-5-5`, serwer `connected`, 29 narzedzi MCP i zadne wbudowane.

| Zadanie | Wywolania | Tury | Czas | Koszt | Wynik |
|---|---|---|---|---|---|
| A: "sprawdz dostepnosc NMT dla arkusza M-34-64-D-d-1-2 i pobierz go (5 m, EVRF2007)" | `get_catalog(command, params)`, `elevation_availability(product, sheet)`, `elevation_download(..., year: 2019)` | 4 | 15,3 s | 0,0052 USD | pobrany, status `new`, sha256 `23d160d0...` (= pobranie CLI i MCP), odpowiedz z latami i rozdzielczosciami |
| B: 5 m dla `N-34-130-D-d-2-4` (ma tylko 1 m), "jesli nie istnieje, pobierz najblizszy" | `get_catalog`, `availability`, `download 5m` = `is_error: true`, `ok: false`, `download 1m` | 5 | 32,3 s | 0,0058 USD | agent wyjasnil brak 5 m na podstawie komunikatu z podpowiedzia i pobral 1 m (2025, ok. 37 MB), podal sciezke i sha256 |
| A na wheel z `1a300b7d` | `elevation_availability`, `elevation_download` | 3 | 15,6 s | 0,0067 USD | pobrany |

### Zrzut `--help` (wheel vs zrzut odniesienia T0, `baseline_dump.py --drop-json`)

`leaf commands: 37; parsers: 51; text runs: 33`; roznice opisane w U6.

### Pomiar kontekstu i kontrola z tabelami katalogu

- Pomiar kontekstu (spec 16.3, ponowiony na wheel): `instructions` 1 447, `get_catalog()` 7 315,
  `get_catalog(group="elevation")` 4 796, `get_catalog(command="elevation download")` 20 347,
  `get_catalog(tables=True)` 13 294 (tabele: 4 kody wyjscia, 14 kodow bledow, 16 schematow), `catalog
  --json` 7 629, `catalog elevation download --json` 29 717, `catalog --params --json` 298 151 (zwarte
  200 032) znakow - zgodnie ze spec; `tools/list` 28 597 wobec 28 607 w spec (roznica 10 znakow).
- Kontrola z tabelami katalogu: 61 dokumentow CLI z E2E-1, 2, 3 i 7 oraz kody bledow z MCP - kazdy ma
  znany `schema` (pierwszym kluczem), kazdy `kartograf-error/1` ma `code` i `exit_code` z tabeli `errors`
  katalogu; widziane kody: `invalid_input`, `usage_error`, `invalid_sheet_code`, `io_error` (oraz
  `interrupted` w E2E-1 i `cache_error` w E2E-9, tez zgodne z tabela); wszystkie 16 schematow z tabeli
  `schemas` pojawilo sie w E2E.

## Blad znaleziony i naprawiony

**B1 (`a7ba1336`, sredni): `kartograf-mcp` konczyl sie tracebackiem przy starcie, gdy nie mozna utworzyc
katalogu cache.** Powtorzenie: `HOME=/proc/nohome XDG_CACHE_HOME= kartograf-mcp` albo `kartograf-mcp
--cache-file <plik>/sub/m.db`, gdzie `<plik>` to zwykly plik: `Path.mkdir` w `_open_cache` rzucal
`FileNotFoundError`, `PermissionError` albo `NotADirectoryError`, kod 1, traceback na stderr. CLI i
biblioteka w tej samej sytuacji ostrzegaja i pracuja bez cache (`cache_disabled` w `notices`); serwer w
piaskownicy z `HOME` tylko do odczytu byl bezuzyteczny. Poprawka: `_open_cache` lapie `OSError`, loguje
jedno ostrzezenie (`Cache metadanych: nie mozna utworzyc katalogu ...: ... - praca bez cache
(--cache-file z zapisywalnej sciezki albo --no-cache)`), a `MetadataCache` biblioteki zglasza brak bazy
przy pierwszym uzyciu jak zawsze. Test regresji
`tests/test_mcp_server.py::test_a_cache_directory_that_cannot_be_made_does_not_stop_the_server` (czerwony
przed poprawka: `NotADirectoryError`). Potwierdzenie na wheel: E2E-11.

## Uwagi (odchylenia planu od rzeczywistosci i drobne pozycje do decyzji; zadna nie blokuje)

**Odchylenia planu T9 (kod zachowuje sie zgodnie ze speckiem):**

- U1. Arkusz `N-34-130-D-d-2-4` nie ma NMT 5 m (tylko 1 m EVRF2007 i KRON86): `--resolution 5m` daje
  `ok: false` z komunikatem `Brak danych NMT 5m ... uzyj --resolution 1m`, kod 1 (to samo w MCP:
  `is_error: true`). E2E-3, E2E-4 i E2E-6 uzyly arkusza Krakowa `M-34-64-D-d-1-2` (5 m, 2019). Przyklady
  w katalogu i `llms.txt` uzywaja tego arkusza z `--resolution 1m`, wiec dokumentacja jest poprawna.
- U2. `elevation download --product nmt --json` (bez obszaru i bez `-o`) zglasza najpierw brak obszaru
  (`details.options` = `sheet, bbox, geometry`), nie `output_dir`; `details.option == "output_dir"`
  wychodzi, gdy obszar jest podany (E2E-1).
- U3. Status ponownego przebiegu to `local` (nie `unchanged`); `soil hsg` daje `reused`. `project status`
  przed pobraniem to `ok: false`, kod 1 (spec 6.5: niepobrane zadanie), dopiero po `project download` 0.
- U4. `catalog elevation download` ma 30 parametrow (29 z flaga CLI, w tym `--json`, oraz `update`); spec
  8.1 i plan mowia o 28 - liczba do poprawy w T8.
- U5. `--upgrade --plan` z planem innego arkusza w tym samym magazynie to bezszumowe `ok: true` bez pobran
  (plan jest filtrem, zgodnie z ARCHITECTURE: odrzucany jest tylko inny magazyn i nieznany schemat).
- U6. `--help` wzgledem zrzutu odniesienia (plan, Review Focus 3: dozwolone tylko `catalog` i `--json`):
  zrzut akcji parsera (`actions.json`: 50 -> 51 komend) rozni sie wylacznie dodana komenda `catalog` -
  zadna flaga, typ, `choices`, `default`, `nargs` ani tekst pomocy innej komendy sie nie zmienil. W tekstach
  roznia sie: kolejnosc flag i dodatkowy przyklad w liniach `Przyklady` (`boundaries`, `elevation`,
  `geodesy`, `landcover`, `maps`, `models3d` `download`, `soil hsg`, `project init`: przyklady z katalogu,
  spec 7.5), opis `landcover download` w pomocy grupy (`Pobierz dane wybranego produktu pokrycia terenu`,
  spec 16.3 pkt 5), dluzszy opis `cache path` (spec 16.4), pomoc glowna z `catalog`, kod wyjscia
  `parse ABC` i `parse` bez argumentu 1 -> 2 (BREAKING O2) oraz `[--json]` w wierszu `usage`. Pozostale
  helpy lisci i grup oraz 30 z 33 przebiegow tekstowych sa bajtowo takie same (3 rozne: `elevation
  list-sources --product nmt` - `[--json]` w wierszu `usage`, `parse ABC` i `parse` - kod 2).

**Drobne uwagi (kandydaci do decyzji, nie bledy):**

- O1. `hint` bledow z `options` zamiast `option` (np. brak obszaru) to `null` (spec 6.3 pkt 4): agent dostaje
  alternatywy w `message`, ale nie przyklad. Podobnie `ValidationError` "Plan dotyczy innego magazynu" ma
  `details: {}` i `hint: null` (pozostale bledy planu maja `option: plan`).
- O2. `format_command` zwraca wiersz z poczatkowym `kartograf `, a `parse_command` go odrzuca
  (`UsageError`: `argument command: invalid choice: 'kartograf'`, bez podpowiedzi); zgodnie ze spec 8.7
  trzeba obciac prefiks, ale `parse_command(format_command(...))` jest naturalna pierwsza proba agenta.
- O3. Narzedzie `project_check_updates` nie jest nazwane w katalogu (`project download` ma
  `supports_check: true`, ale `tool: project_download`); agent znajdzie je w `tools/list`.
- O4. Pobranie jednego arkusza przez MCP daje jedno zdarzenie postepu (`start (0/1)`), obszaru - `completed
  n/N`; rosnaca numeracja i `total: None` zgodnie z 9.6.
- O5. `kartograf-mcp --allow-dir` przyjmuje sciezke wzgledna i nieistniejacy katalog bez ostrzezenia
  (rozwiazywane wzgledem cwd serwera wybranego przez klienta).

## Dane dla T8

Pomiary powyzej (kontekst narzedzi i katalogu, rozmiary, czasy) sa pomiarami T9 do errata ADR-046.
Prawdziwe wydruki do przykladow w dokumentacji (zapisane poza repo): `catalog --json`, `parse`,
`list-sources`, `cache path` i `cache stats`, `project *`, `elevation availability --json` (Krakow),
`elevation download --json` (`new` i `local`), `--check-updates --json` (`kartograf-plan/1`),
`kartograf-error/1` z `hint` (`elevation download --product foo --json`, `parse ZZZ --json`, `--sheet`
bez `-o`), wynik narzedzia MCP (`structured_content` == dokument CLI) oraz przebieg Claude Code
(`claude mcp add kartograf -- kartograf-mcp --allow-dir <katalog-danych>`).

## Powtorzenie

Skrypty jednorazowe (poza repo) w `<katalog-danych>/kartograf/agent-interface/e2e/scripts/`:
`rerun_all.sh` (budowa wheel z `git archive HEAD`, reinstalacja w venv 3.13 i 3.12, `mypy` konsumenta,
`e2e1_offline.py`, `e2e2_availability.py`, `e2e3_download.py`, `e2e4_mcp.py`, `e2e4b_wire.py`,
`e2e8_extra.py`, `e2e9_edge.py`, `e2e11_hostile_env.py`, `e2e7_families.py`, powtorzenie offline i drutu
na 3.12, zrzut `--help`), `e2e12_final_checks.py`, `postcheck.py`; przebieg Claude Code: komenda z sekcji
"Claude Code" (katalog roboczy poza repo, `--mcp-config` z `kartograf-mcp --allow-dir
<katalog-danych>/kartograf-live/agent-interface --cache-file <plik>`).
