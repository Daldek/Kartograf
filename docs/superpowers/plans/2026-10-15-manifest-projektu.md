# Manifest projektu — Implementation Plan (0.8.0)

> **For agentic workers:** zadania ponizej wykonuj w kolejnosci; najpierw
> test zachowania, potem kod, potem wskazane testy. Checklist `- [ ]` sledzi
> postep. Nie zalatwiaj brakujacego sygnalu pozornym statusem "aktualne".

**Data:** 2026-10-15  
**Goal:** Manifest projektu zapisuje powtarzalne zadania i przypiete wersje
konkretnych plikow w jednym wspolnym magazynie; CLI `project` korzysta
wylacznie z publicznego API, bez dodatkowej logiki danych.  
**Spec:** `docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`
(sekcje 1-8), ADR-040; kontrakty magazynu ADR-036, CLI/API ADR-037,
grupy CLI ADR-039.  
**Zaleznosci wdrozeniowe:** plany A-E podprojektu 3 moga powstawac
rownolegle; kazdy produkt musi zwracac `VersionedFile` i miec wersyjny
sidecar. Plan A dostarcza `check_availability` do `project availability`.
**Galaz implementacyjna:** krotkotrwala galaz z aktualnego `develop`
**po scaleniu ADR-039**. Nie opieraj sie na starych nazwach CLI ze stanu
2026-10-15 przed migracja.

## Zasady globalne

- Python z `.venv/bin/python` (lub wspoldzielonego `.venv` z korzenia
  worktree). Testy offline `-m "not live"`; `live` tylko swiadomie;
  pobrane dane wyłącznie poza repo i `/tmp`, z jawnym `--output` przy
  `project init`; w docs/logach `<katalog-danych>`. Brama po integracji:
  `python -m pytest tests/ -m "not live" -q`, `python -m ruff check .`,
  `python -m ruff format --check .`, `python -m mypy kartograf/ tests/`.
- Angielskie nazwy API/kluczy, docstringi po angielsku; teksty `Notice` i
  wyjatkow po polsku ASCII. Bledy wejscia `ValidationError`, zrodla
  `DownloadError`, cache `CacheError` (STANDARDS 7.3, 11).
- `kartograf-project/1` i `kartograf-meta/1` sa odrebne kontrakty; nie
  dopisuj `parent_requests` ani projektu do sidecara. JSON manifestu
  wolno aktualizowac, plik wersji i sidecar pozostaja niezmienne.
- Jedyny rejestr wyborow danych = grupy ADR-039 i ich publiczne API;
  zadnych dodatkowych list produktow w CLI `project` ani duplikacji
  formatowania sciezek magazynu. Adapter wyniku musi obejmowac
  `VersionedFile` z wielu jednostek, takze `raw` i wejscia HSG.
- Testy offline symuluja sygnal i trwale pliki, nie kopiuja mock-echo
  wywolan; sprawdzaja piny, bajty, bledy i brak pobran. Testy starych
  dokladnych tekstow/wiring przepisz albo usun, nie przywiazuj
  implementacji do nich. Zweryfikuj rezultat przez uruchomienie
  rzeczywistej komendy `project` na malym magazynie lokalnym po zmianie.

## Stan i interfejsy do sprawdzenia PRZED pierwsza zmiana

Na bazowym `develop` 2026-10-15 obecne: `kartograf/download/fetch.py::VersionedFile`
(`path`, `status`, `label`, `sha256`, `version_path`, `newer`, `unverified`),
`download/data.py::download_data/check_data`, `DataReport.files: tuple[UnitFile]`
(z `.file`), `download/manager.py::DownloadResult.files: dict[str,
tuple[VersionedFile,...]]`, `landcover/manager.py::LandCoverAreaResult.files`
(z `.file` i `.raw`), `hydrology/hsg.py::HsgResult.file/.inputs`,
`download/plan.py::UpdatePlan.items: tuple[PlanItem]` z
`available_label`, `available_signal`, `status` i tozsamoscia slotu.
Sidecary z `sources/sidecar.py` maja `sha256`, `size_bytes`, `dataset`,
`request`, `extra.parent_request` i `extra.version`; lokalne wersje
`download/versions.py::read_version`/`list_versions` sa tylko wewnetrzne.
CLI 2026-10-15: `cli/_parser.py::create_parser`,
`cli/commands.py::_dispatch` i `kartograf/__init__.py::__all__`.
Po ADR-039 otworz ich aktualne odpowiedniki i podlacz grupe `project`
**jednym** modułem `cli/project_cmd.py`, w sposob przyjety dla innych
grup (bez drugiego rejestru komend). W planach A-E nowe grupy
`boundaries`, `cadastre`, `models3d`, `names`, `maps` i dalsze
otrzymuja adapter z publicznego wyniku, nie osobne skanery katalogu.

## Mapa plikow

| Plik | Cel |
|---|---|
| `kartograf/project/manifest.py` (nowy), `kartograf/project/__init__.py` (nowy) | schemat, serializacja i walidacja sciezek, zapis bez zgubienia cudzych zmian |
| `kartograf/project/operations.py` (nowy) | API `init_project`, `add_project_task`, `download_project`, `verify_project`, `status_project`; normalizacja zadania i wynikow |
| `kartograf/project/freshness.py` (nowy) | `check_project_updates`, `update_project`, `project_availability` i porownanie z przypietymi wersjami |
| `kartograf/cli/project_cmd.py` (nowy), `kartograf/cli/_parser.py`, `kartograf/cli/commands.py` (po ADR-039: odpowiedniki) | rejestracja grupy, tlumaczenie argumentow i wydruk `ProjectReport`/`Notice` |
| `kartograf/__init__.py` | nowe publiczne API i `__all__` |
| `tests/test_project_manifest.py`, `tests/test_project_download.py`, `tests/test_project_freshness.py`, `tests/test_project_cli.py` (nowe) | zachowanie, wyjatki, transakcje, CLI = API |
| `docs/USAGE.md`, `docs/ARCHITECTURE.md`, `README.md`, `docs/CHANGELOG.md`, `docs/PROGRESS.md` | przyklady, kontrakt, wydanie i stan sesji |

## Task 1: Schemat, sciezki i transakcyjny zapis

**Files:** `kartograf/project/manifest.py`, `kartograf/project/__init__.py`,
`tests/test_project_manifest.py`.

- [ ] **Step 1 (testy):** pusty manifest po `init_project` ma `schema`,
  `store.path`, `tasks: []`, prawidlowy JSON; drugie `init` nie zmienia
  bajtow istniejącego pliku; sciezka wzgledna magazynu jest wzgledem
  projektu, bezwzgledna zostaje bezwzgledna; po przeniesieniu obu
  katalogow z zachowaniem relacji dostep do magazynu dziala. Nieznany
  schemat, nieznany klucz w strukturze zadania, dubel nazwy, `../` lub
  absolutna sciezka pliku, `versions/.incoming`, symlink uciekajacy poza
  magazyn daja `ValidationError` przed odczytem pliku poza magazynem.
- [ ] **Step 2 (testy):** dwie niezalezne instancje manifestu probuja
  dopisac dwa zadania: drugi zapis po pierwszym otrzymuje konflikt z
  czytelnym komunikatem, pierwszy nie ginie; blokada `mkdir` zajeta:
  brak nadpisania; wyjatki podczas zapisu/zabicie przed `os.replace`
  zostawia czytelny stary manifest i usuwa wlasny plik tymczasowy.
- [ ] **Step 3 (kod):** dataclasses/parsowanie `ProjectManifest`,
  `ProjectTask`, `ProjectFile`; `read_manifest`, `write_manifest` z
  `os.mkdir` wykluczajacym, ponownym odczytem pod blokada i porownaniem
  pierwotnego hasha, plikiem tymczasowym w projekcie,
  `flush`/`fsync`/`os.replace`/sync katalogu, porzadek stabilny. Brak
  automatycznego przejmowania osieroconej blokady. Zadnej SQLite na
  udziale; `cache=False` domyslnie w API projektu.
- [ ] **Step 4:** `python -m pytest tests/test_project_manifest.py -m "not live" -q`.

## Task 2: `add`, typowane wybory i rozdzielenie zadan

**Files:** `kartograf/project/operations.py`, `kartograf/project/manifest.py`,
`kartograf/__init__.py`, `tests/test_project_manifest.py`.

- [ ] **Step 1 (testy):** NMT arkusz z `resolution`/`vertical_crs`,
  bbox z CRS i `--country auto`, `landcover` z `year` lub `layers`,
  `soil hsg` z `depth`: zadania zachowuja jawne wybory i typy (bbox
  coords, rok, bool), a ponowne dodanie `name` daje blad bez zmiany
  manifestu. `add` bez wyboru wymaganego przez grupe, z `--output`,
  `--force`, `--check-updates` lub z obca opcja daje `ValidationError`
  PRZED siecia; `add` nie tworzy pliku danych. Wariant `geometry`:
  zmiana GPKG lub plikow SHP/.shx/.dbf/.prj blokuje wykonanie.
- [ ] **Step 2 (kod):** jedna biblioteczna normalizacja wyboru grupy
  (wywolania rodzin `download_data`, `LandCoverManager`,
  `HSGCalculator` i grup A-E), analogiczna do walidacji w istniejacych
  `download/options.py` i managerach, bez sondowania sieci podczas
  `add`. Zapisuj jawne opcje ksztaltujace dane, nie transport czy
  prezentacje. Nie wywoluj CLI z biblioteki; nowe API eksportuj przez
  `kartograf/__init__.py::__all__`.
- [ ] **Step 3:** `python -m pytest tests/test_project_manifest.py -m "not live" -q`.

## Task 3: Pinowanie wszystkich plikow i offline `verify`/`status`

**Files:** `kartograf/project/operations.py`, `tests/test_project_download.py`,
`kartograf/project/manifest.py`.

- [ ] **Step 1 (testy):** na malym magazynie testowym z wersjami i
  sidecarami `kartograf-meta/1`: `DataReport` PL+CZ, dwa kafle LAZ,
  `LandCoverAreaResult` z dwoma powiatami i `raw`, `HsgResult` z
  `file` oraz trzema `inputs` przypinaja kazdy rzeczywisty
  `VersionedFile.version_path` bez duplikatow. Dowiazanie standardowe
  wskazuje na nowsza wersje: `verify` starego pinu dalej przechodzi.
  Pojedynczy zmieniony bajt pliku, usuniety plik, podmieniony sidecar,
  roznica `size_bytes`/`dataset`/`extra.version.label` daja osobne
  `missing`/`corrupt` i kod `ok=False`; `status` nie czyta zawartosci
  ani nie odpytuje zrodla.
- [ ] **Step 2 (testy):** zadanie w polowie zakonczone sukcesem w jednej
  jednostce i `failed` w drugiej zachowuje udany pin i zwraca `ok=False`;
  ponowienie dopelnia brakujaca jednostke, nie podmienia starej.
  Gdy producent zwroci inna wersje juz przypietej jednostki,
  `download_project` nie zmienia jej; brakujaca przypieta wersja
  wymaga przywrocenia kopii, nie automatycznego przepisania pinu.
- [ ] **Step 3 (kod):** jeden kolektor rodzin wynikow oparty na
  `VersionedFile` i obowiazkowym sidecarze wersji; role
  `output`/`input`/`raw`; pelny SHA-256, rozmiar, etykieta i sumy
  sidecarow. Normalizuj sciezki wzgledem korzenia magazynu, odrzucaj
  wyjscie poza korzen. Dla `verify` strumieniowe liczenie sum,
  `status` tylko stat; brak odczytu SQLite. Wynik projektu sklada
  `Notice` i bledy bez maskowania czesciowego sukcesu.
- [ ] **Step 4:** `python -m pytest tests/test_project_download.py -m "not live" -q`.

## Task 4: Swiezosc od przypietej wersji i jawny `update`

**Files:** `kartograf/project/freshness.py`, `kartograf/project/operations.py`,
`tests/test_project_freshness.py`.

- [ ] **Step 1 (testy):** magazyn ma wersje B, projekt przypina A,
  zrodlo ma B: `check_project_updates` daje `newer` od A nawet jezeli
  `check_data` zwroci `PlanItem.status="current"` dla B;
  `check_project_updates` nie pobiera payloadu i nie zmienia zadnego
  bajtu manifestu. Sygnaly `index`, `metadata`, `http` (odrzuc
  `Content-Length` jako dowod swiezosci), `none`, awaria sieci,
  etykieta nieporownywalna: rozroznione statusy. HSG z nowym
  wydaniem clay i starymi sand/silt wykrywa roznice wejsc.
- [ ] **Step 2 (testy):** `update_project` najpierw weryfikuje
  stare piny; tylko po sukcesie jednostki i sprawdzeniu nowego
  sidecara zmienia jej pin; brak sygnalu bez `force` nie pobiera;
  `force` przy identycznym SHA zostawia pin, przy nowych bajtach
  zmienia pin, innego zadania nie rusza. Awaria jednego powiatu,
  wymiana sygnalu miedzy sonda a pobraniem, brak potrzebnego
  wejscia HSG i konflikt zapisu nie nadpisuja starych pinow
  porazonych jednostek; manifest pozostaje poprawnym JSON.
- [ ] **Step 3 (kod):** wywoluj istniejace publiczne `check_*` i
  `download(..., update="upgrade"/"force")`, nie implementuj nowego
  odkrywania zrodel. `UpdatePlan` to tylko tymczasowy wynik sprawdzenia,
  a `PlanItem.status` jest wzgledem magazynu: porownuj
  `available_label`/`available_signal` i sidecar **pinu**. Tam gdzie
  sygnal nie pozwala ustalic porzadku, nie twierdz ze jest nowszy;
  pokaz `unverifiable` lub `check_failed`. Nie zapisuj planu ani
  dostepnosci do manifestu.
- [ ] **Step 4:** `python -m pytest tests/test_project_freshness.py -m "not live" -q`.

## Task 5: Grupa CLI `project` i `availability`

**Files:** `kartograf/cli/project_cmd.py`, aktualne po ADR-039
`kartograf/cli/_parser.py` i `kartograf/cli/commands.py`,
`kartograf/project/freshness.py`, `tests/test_project_cli.py`,
`kartograf/__init__.py`.

- [ ] **Step 1 (testy):** `project init|add|download|status|verify|
  check-updates|update|availability --help`; parser `add -- ...`
  odrzuca ukryte `-o` i tryby aktualizacji, akceptuje
  `elevation download`, `landcover download`, `soil hsg` oraz
  produkt nowej grupy; CLI po jednorazowym wywolaniu publicznego
  API raportuje te same zadania, piny, komunikaty `Notice` i
  blad co wywolanie API. Dla `availability` wybor obszarowy z
  zapisanej `selection` daje ten sam `AvailabilityReport` co
  `check_availability`, a `--name` zadania bez takiej sondy
  daje zrozumialy blad. `--quiet` nie ukrywa warningow.
- [ ] **Step 2 (kod):** tylko jeden modul `cli/project_cmd.py`
  z rejestracja grupy w miejscu ustalonym ADR-039. CLI konwertuje
  tekst argumentow na slownik typowany, czyta/drukuje wyniki;
  walidacja wyboru, parsowanie sidecara, decyzja co pobrac, status
  i teksty `Notice` pozostaja w `kartograf/project/`.
  Dla planu A/B przeprowadz `project_availability` przez
  publiczne `check_availability` (bez pobrania i zapisu).
- [ ] **Step 3:** `python -m pytest tests/test_project_cli.py -m "not live" -q`.

## Task 6: Integracja kazdej rodziny produktow i dokumentacja

**Files:** testy reprezentatywne dla grup w `tests/test_project_download.py`
/ `tests/test_project_freshness.py`; `README.md`, `docs/USAGE.md`,
`docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/PROGRESS.md`.

- [ ] **Step 1 (testy):** dla nowo scalonych produktow A-E z wynikiem
  `VersionedFile` sprawdz co najmniej po jednym zadaniu na nowa
  rodzine wyniku, kazda z nowymi grupami CLI; nie mnoz testow
  jednoargumentowego przekazania przez parser. Przypadek CZ z
  plikami towarzyszacymi (np. orto JPG+JGW) przypina wszystkie
  rzeczywiste pliki wersji z sidecarami; nie przypina plikow
  tymczasowych ani raportu `availability`.
- [ ] **Step 2 (docs):** opis schematu i drogi pliku w
  ARCHITECTURE 3 (po sidecarach), przyklady 8 polecen z rozdzialu 4
  specu w USAGE i krotki link w README. CHANGELOG `[0.8.0] -
  Unreleased`: nowa funkcja i API (bez oglaszania jako gotowe przed
  zaimplementowaniem). PROGRESS koniec sesji, datowane wyniki.
  `docs/DECISIONS.md` zachowuje CRLF. Nazwy starych grup z daty
  przed ADR-039 nie moga wystepowac w nowych przykladach.
- [ ] **Step 3 (smoke):** uruchom rzeczywiste CLI `project init`,
  `add`, `download` na malym lokalnym magazynie z fixture wersji
  (albo z jawnym magazynem live), `verify`, `status`,
  `check-updates`, `update`. Zobacz na dysku JSON oraz pin po
  podstawieniu nowszej wersji; nie opieraj sie tylko na testach.

## Integracja i E2E na zywo

- [ ] Po scaleniu wszystkich Task: brama offline z zasad globalnych;
  brak plikow tymczasowych/SQLite w udziale; uruchom `kartograf project
  --help` i `--version` z worktree. Popraw docstring/publiczny `__all__`.
- [ ] GUGiK: maly arkusz z magazynu poza repo, `project init
  --project <katalog-projektu> --output <katalog-danych>`, `add`
  `elevation download`, `download`, `verify`, `check-updates`;
  drugi projekt uzywa tej samej lokalnej wersji. Zapisz
  etykiete, `sha256`, liczbe plikow i czy drugi projekt zmienil
  pin pierwszego. Projekt moze lezec na udziale pozbawionym
  byte-range locks; cache SQLite nie trafia na ten udzial.
- [ ] PL obszar: `project availability` -> tabelka kombinacji
  identyczna jak `elevation availability`, zadne pliki nie
  pobrane; `project download` dopiero po wyborze wariantu.
  CZ/SoilGrids `check-updates` dla dostepnego sygnalu i wycinek
  PL (`none`) dla stanu `unverifiable`; CLMS z credentials pomijamy.
- [ ] Na kopii magazynu poza repo zmien `store.path` (albo zachowaj
  relacje sciezek wzglednych), uruchom `verify`. Raport live:
  `docs/research/` zgodnie z lokalna konwencja, bez adresu
  fizycznej sciezki danych. Commit(y) Conventional Commits po
  polsku, autor `Daldek <git@debever.pl>` bez stopki.
