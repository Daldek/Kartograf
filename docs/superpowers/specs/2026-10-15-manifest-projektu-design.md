# Spec: Manifest projektu (podprojekt 2 roadmapy v1.0.0)

**Data:** 2026-10-15
**Status:** projekt do implementacji; architektura z wolnej reki uzytkownika
(2026-10-15), decyzje: ADR-040
**Wersja docelowa:** 0.8.0
**Warunek wstepny:** magazyn wersjonowany (ADR-036), CLI = API (ADR-037),
grupy komend CLI wg typu danych (ADR-039) scalone do `develop`
**Plan:** `docs/superpowers/plans/2026-10-15-manifest-projektu.md`
**Dokumenty zrodlowe:**
- `docs/SCOPE.md` 3.3 (cel 3 "Manager danych"; zasady: sidecar niezmienny,
  manifest = powiazanie projekt -> dane, magazyn na udziale bez blokad,
  zadnej bazy SQLite na udziale, angielskie klucze)
- `docs/ARCHITECTURE.md` 3.2 (sidecar `kartograf-meta/1`), 3.3 (uklad
  `data/`, `versions/`), 3.4 (`extra.parent_request`)
- `docs/USAGE.md` 4.3 (tryby `--check-updates`, `--upgrade`, `--force`)
- spec podprojektu 3 `2026-10-13-katalog-produktow-design.md` (grupy 6.1,
  raport dostepnosci 4) i plany A-E z 2026-10-15

---

## 1. Cel i granice

Magazyn (ADR-036) trzyma kazdy pobrany plik jako niezmienna wersje
z sidecarem, a sciezka standardowa wskazuje najnowsza lokalna wersje.
Z magazynu korzysta wiele projektow (analiz, modeli, raportow). Brakuje
zapisu, ktorych danych uzyl konkretny projekt: gdy ktos pobierze nowsza
wersje, sciezka standardowa przeskoczy na nia, a projekt nie wie, czego
uzyl wczesniej.

Manifest projektu odpowiada na piec pytan:

1. **Jakie dane projekt zamowil?** Zadania: komenda grupy (np.
   `elevation download`) z opcjami wyboru danych.
2. **Ktorych dokladnie plikow uzyl?** Przypiecia: wersje plikow
   z magazynu z pelna suma SHA-256.
3. **Czy te pliki sa na miejscu i nienaruszone?** `status` (szybko, bez
   czytania danych) i `verify` (sumy SHA-256).
4. **Czy u zrodla sa nowsze dane?** `download --check-updates` - bez
   pobierania; przejscie na nowsze dane tylko jawnie (`download --upgrade`).
5. **Jak odtworzyc dane gdzie indziej?** `download` na nowym magazynie
   pobiera zadania ponownie i przyjmuje plik tylko przy tej samej sumie
   SHA-256 co przypieta.

Wiele projektow korzysta z jednego magazynu; projekt nie kopiuje danych
do swojego katalogu. Nie obiecujemy, ze zrodlo zachowa stare dane:
jesli je zmienilo albo wycofalo, odtworzenie tych samych bajtow wymaga
kopii magazynu - Kartograf zglasza to bledem, nie podmienia danych po
cichu.

**Poza zakresem 0.8.0:** indeks "ktore projekty uzywaja pliku" (SCOPE
3.3: budowany lokalnie z manifestow, np. przez GUI webowe); usuwanie
wersji z magazynu (Kartograf niczego nie usuwa); kopiowanie albo eksport
danych projektu do innego katalogu; baza projektow i blokady
dlugotrwale; laczenie projektow.

## 2. Decyzje i odrzucone warianty

| # | Decyzja | Odrzucone warianty i powod |
|---|---|---|
| M1 | Jeden plik `kartograf-project.json` w katalogu projektu: JSON UTF-8, wciecie 2 spacje, stala kolejnosc kluczy, schema `kartograf-project/1`, scisla walidacja (nieznany klucz = blad) | SQLite w projekcie albo w magazynie: udzial sieciowy bez blokad zakresow bajtow, plik nieczytelny dla czlowieka (SCOPE 3.3); YAML/TOML: nowa zaleznosc do zapisu; wpisy projektow w sidecarach: sidecar jest niezmienny, a jeden plik sluzy wielu projektom; plik na zadanie: trudniej przegladac i przenosic |
| M2 | Zadanie = `command` (komenda grupy) + `options` (argumenty funkcji biblioteki tej komendy) + przypiete pliki (`path`, `version`, `label`, `sha256`, `size_bytes`, `role`, `unit`) | Sama lista plikow: nie odtworzy zadania; sama komenda: nie mowi, jakie bajty przyjeto; kopia sidecara w manifescie: dubel pochodzenia, ktore jest w magazynie; suma bajtow sidecara: kazde odtworzenie na nowym magazynie zapisuje nowy sidecar (`downloaded_at`), wiec dawaloby falszywe alarmy bez zmiany danych |
| M3 | Jeden magazyn na projekt, jawnie z `init --output`; sciezka podana wzglednie zapisana wzglednie do katalogu projektu, bezwzgledna - bezwzglednie; przypiecia zawsze wzgledne do magazynu | Magazyn per zadanie: trudniej przenosic i weryfikowac; kopia danych w projekcie: miejsce i rozjazd wersji; tylko sciezki bezwzgledne: projekt nieprzenosny; domyslny `./data`: wartosc domyslna wplywajaca na dane |
| M4 | `project add NAZWA <grupa> <komenda> [opcje]`: po nazwie zadania dokladnie ta komenda, ktora wpisuje sie po `kartograf` (ADR-039), parsowana tym samym parserem | Osobne flagi `project add --product ...`: druga gramatyka rozjezdzajaca sie z grupami; zapis surowej linii polecenia: biblioteka nie parsuje CLI (ADR-037); `kartograf elevation download ... --project P`: zmiana kazdej grupy zamiast jednego modulu grupy `project`; obowiazkowy separator `--`: zbedny (dozwolony) |
| M5 | Komendy `init`, `add`, `remove`, `download`, `status`, `verify`; tryby aktualizacji jak w grupach: `download --check-updates`, `--upgrade`, `--force`; `--project KATALOG` domyslnie biezacy katalog; zadania podawane pozycyjnie | Osobne `check-updates`/`update`: drugie slownictwo dla trybow ADR-036 znanych z grup (USAGE 4.3); `--name ID`: dluzsze niz pozycyjna nazwa; obowiazkowe `--project`: kazde polecenie dluzsze, a typowa praca odbywa sie w katalogu projektu |
| M6 | Pierwsze pobranie przypina wszystkie pliki zadania naraz, tylko po pelnym sukcesie; `download` bez trybu nigdy nie zmienia przypiec, a brakujace przypiete pliki odtwarza wylacznie przy identycznej sumie; przepiecie tylko `--upgrade`/`--force`, zawsze calego zadania | Przypinanie czesci zadania: stan "pol zadania" trudny do zrozumienia i ponowienia; automatyczna aktualizacja przy `download`: niszczy odtwarzalnosc; przepiecie na najnowsza lokalna wersje przy odtwarzaniu: cicha zmiana danych |
| M7 | `verify` = pelny SHA-256 kazdego przypietego pliku i zgodnosc z sidecarem wersji; `status` = istnienie i rozmiar, bez sieci i bez czytania danych | Zaufanie nazwie katalogu `<etykieta>_<sha8>` albo dowiazaniu: 8 znakow to nie dowod; `status` z siecia: wolny i zawodny offline |
| M8 | `check_project` wywoluje `check_*` komendy (plan `UpdatePlan`) i porownuje go z przypieciem przez `PlanItem.local_sha256` | Ponowna interpretacja sygnalow (ETag, wydanie, skorowidz) w projekcie: dubel ADR-036; uzycie `PlanItem.status` wprost: dotyczy najnowszej wersji lokalnej, nie przypietej; zapis planu w manifescie: plan to chwilowa sonda |
| M9 | Brak komendy `project availability`: raport dostepnosci (plan A/B) sluzy wyborowi wariantu PRZED `project add`; wybrany wariant zostaje opcja zadania | `project availability NAZWA`: dubel komendy grupy dla jednego obszaru, uzaleznienie manifestu od planu A/B, mylenie dostepnosci ze swiezoscia; przypinanie raportu jak pliku: raport nie jest danymi |
| M10 | Zapis atomowy (plik tymczasowy w katalogu projektu + `os.replace`) pod krotka blokada katalogowa `mkdir` tylko na czas odczyt-scalenie-zapis; scalanie per zadanie; zapis po kazdym zadaniu | SQLite i blokady zakresow bajtow: udzialy sieciowe; `os.replace` bez blokady: zgubione rownolegle dopisy; blokada na czas calego pobrania: godziny blokady dla zespolu; automatyczne przejmowanie starej blokady: ryzyko nadpisania aktywnego procesu |
| M11 | Jedna pozycja na komende danych CLI w `kartograf/project/commands.py` (funkcja pobrania, `check_*`, rodzina wyniku) i `_task` w parserze komendy; nowy produkt w istniejacej komendzie nie zmienia projektu | Skaner katalogow magazynu per produkt; adapter per produkt; wyprowadzanie wynikow z nazw sciezek |
| M12 | Operacje projektu domyslnie bez cache metadanych (`cache=False`); API przyjmuje lokalny `MetadataCache` | Domyslny `.kartograf_cache.db` w biezacym katalogu: katalog projektu bywa na udziale, a SQLite na udziale jest wykluczone (SCOPE 3.3) |

## 3. Projekt na dysku

### 3.1 Katalog projektu i magazyn

- Projekt to katalog z plikiem `kartograf-project.json`. Reszta katalogu
  nalezy do uzytkownika (skrypty, wyniki, geometrie obszarow).
- `output_dir` to magazyn: ten sam katalog, ktory komendy grup dostaja
  przez `--output`. Projekt ma dokladnie jeden magazyn; wszystkie
  zadania pobieraja do niego.
- Dwa typowe uklady:
  - wspolny magazyn zespolu: `kartograf project init --output /srv/dane/kartograf`,
  - magazyn w projekcie: `kartograf project init --output data`
    (katalog `data/` obok manifestu).
- `init` tworzy katalog projektu i katalog magazynu, jesli ich nie ma.
  Pozostale komendy wymagaja istniejacego katalogu magazynu - chroni to
  przed pobraniem gigabajtow do pustego punktu montowania, gdy udzial
  nie jest podlaczony.

### 3.2 Sciezki i przenoszenie

Jedna regula dla `output_dir` i dla pliku geometrii zadania
(`options.geometry`): sciezka podana wzglednie jest zapisywana wzglednie,
przeliczona na wzgledna do katalogu projektu; podana bezwzglednie -
bezwzglednie. Przy odczycie sciezka wzgledna jest rozstrzygana wzgledem
katalogu projektu, nie biezacego katalogu. Separator zawsze `/`.
Przypiecia (`path`, `version`) sa zawsze wzgledne do magazynu.

| Sytuacja | Co zrobic |
|---|---|
| Przenosze projekt i magazyn razem, z zachowaniem ich wzajemnego polozenia (wzgledny `output_dir`) | nic |
| Przenosze sam projekt, magazyn zostaje (bezwzgledny `output_dir`) | nic |
| Przenosze sam projekt przy wzglednym `output_dir` | popraw `output_dir` w `kartograf-project.json` |
| Przenosze albo kopiuje magazyn | kopiuj z sidecarami i dowiazaniami twardymi (`rsync -aH`), popraw `output_dir`, potwierdz `kartograf project verify` |
| Kolega otwiera projekt z pustym magazynem | utworz katalog magazynu (albo popraw `output_dir` na wlasny magazyn), potem `kartograf project download` odtwarza pliki z zadan (tylko identyczne sumy SHA-256) |

Zalecenie: plik geometrii obszaru trzymaj w katalogu projektu (sciezka
wzgledna) - przenosi sie razem z projektem.

### 3.3 Format pliku `kartograf-project/1`

Przyklad: zadanie `teren` pobrane i przypiete, zadanie `pokrycie` dodane,
jeszcze niepobrane.

```json
{
  "schema": "kartograf-project/1",
  "output_dir": "/srv/dane/kartograf",
  "tasks": [
    {
      "name": "teren",
      "command": "elevation download",
      "options": {
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": "1m",
        "vertical_crs": "EVRF2007"
      },
      "pinned_at": "2026-10-20T08:15:02+00:00",
      "kartograf_version": "0.8.0",
      "files": [
        {
          "role": "output",
          "unit": "N-34-130-D-d-2-4",
          "path": "nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc",
          "version": "nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_10be475e/N-34-130-D-d-2-4.asc",
          "label": "2022-05-10_83233",
          "sha256": "10be475e6b5c43d54b8dc832ab9816367e3dad4c1bd59bbba25c2b296a2824c6",
          "size_bytes": 41029733
        }
      ]
    },
    {
      "name": "pokrycie",
      "command": "landcover download",
      "options": {
        "product": "bdot10k",
        "teryt": "1465"
      },
      "pinned_at": null,
      "kartograf_version": null,
      "files": []
    }
  ]
}
```

| Pole | Znaczenie |
|---|---|
| `schema` | `"kartograf-project/1"`; inna wartosc = blad z prosba o aktualizacje Kartografa |
| `output_dir` | magazyn (3.1, 3.2) |
| `tasks[]` | zadania w kolejnosci dodania |
| `tasks[].name` | nazwa zadania, unikalna: male litery, cyfry, `-`, `_`, zaczyna sie litera albo cyfra, do 64 znakow |
| `tasks[].command` | komenda danych grupy (sekcja 5): `elevation download`, `imagery download`, `landcover download`, `soil download`, `soil hsg` oraz komendy `download` nowych grup |
| `tasks[].options` | wybor danych: argumenty funkcji biblioteki tej komendy (nazwy = flagi CLI w `snake_case`, ADR-037) w postaci JSON - `bbox` jako lista 4 liczb plus `bbox_crs`, sciezki jako napisy, wartosci per kraj jako obiekt (`{"pl": "1m", "cz": "2m"}`), listy (np. `layers`) jako tablice. Tylko wartosci wybrane (bez `null` i `false`). Nigdy: `output_dir`, tryby aktualizacji, `plan`, `workers`, `cache`, `timeout`, wywolania zwrotne |
| `tasks[].pinned_at` | chwila ostatniej zmiany przypiec (UTC, ISO 8601) albo `null` dla zadania niepobranego |
| `tasks[].kartograf_version` | wersja Kartografa, ktora przypiela pliki, albo `null` |
| `tasks[].geometry_sha256` | tylko przy `options.geometry`, od pierwszego przypiecia: `{nazwa pliku: sha256}` plikow geometrii (GPKG: jeden plik; SHP: obecne z `.shp`, `.shx`, `.dbf`, `.prj`) |
| `tasks[].files[]` | przypiete pliki; puste przed pierwszym pobraniem |
| `files[].role` | `output` (wynik zadania), `raw` (oryginalna paczka, np. ZIP BDOT10k z `keep_raw`), `input` (wejscie pochodnej: clay/sand/silt dla HSG) |
| `files[].unit` | jednostka wyniku (godlo, kafel LAZ, TERYT, wycinek) - do komunikatow |
| `files[].path` | sciezka standardowa pliku (`VersionedFile.path`) wzgledem magazynu: KTORY plik |
| `files[].version` | sciezka przypietej wersji (`VersionedFile.version_path`) wzgledem magazynu: KTORE bajty |
| `files[].label` | etykieta wersji (`VersionedFile.label`) |
| `files[].sha256` | pelny SHA-256 danych (64 male znaki hex) |
| `files[].size_bytes` | rozmiar danych w bajtach (z sidecara wersji) |

Zasady pliku:

- Kartograf zapisuje plik zawsze w tej samej postaci (kolejnosc kluczy jak
  w tabeli, zadania w kolejnosci dodania, `files` w kolejnosci wyniku
  biblioteki bez powtorzen `version`, znak nowej linii na koncu), wiec
  zmiany dobrze widac w systemie kontroli wersji.
- Reczna edycja jest dozwolona (np. `output_dir` po przeniesieniu
  magazynu, `options` zadania). Kazdy odczyt waliduje cala strukture:
  zly JSON, nieznany albo brakujacy klucz, zly typ, powtorzona nazwa
  zadania, nieznana komenda, sciezka przypiecia poza magazynem albo poza
  `versions/` - `ValidationError` ze wskazaniem miejsca.
- Zmiana `options` recznie nie zmienia przypiec: `download --check-updates`
  pokaze roznice, a `download --upgrade` przepnie zadanie wedlug nowych
  opcji.
- Manifest zapisuje wybor uzytkownika, nie dopelnia domyslnych wartosci
  biblioteki. Wartosci domyslne zmieniajace dane sa wykluczone zasadami
  projektu, a gdyby jedna sie zmienila, odtworzenie wykryje inna sume
  (blad, nie cicha podmiana).

Czego manifest nie zawiera: pochodzenia pliku (zrodlo, `request`,
`extra.parent_request`, licencja) - jest w niezmiennym sidecarze wersji
w magazynie; raportu dostepnosci, planu aktualizacji ani cache. Sidecar
mowi, jak plik POWSTAL (zadanie, ktore go pobralo, moglo nalezec do
innego projektu); manifest mowi, ktore zadanie projektu go WYBRALO.

## 4. Komendy CLI i API

### 4.1 Przeglad

Grupa `kartograf project` (ADR-039: jeden modul grupy). Kazda komenda
tlumaczy argumenty na jedna funkcje biblioteki (ADR-037). Wszystkie
przyjmuja `--project KATALOG` (domyslnie biezacy katalog); nazwy zadan
podaje sie pozycyjnie, bez nazw = wszystkie zadania w kolejnosci
z manifestu.

| CLI | API | Co robi | Siec | Manifest |
|---|---|---|---|---|
| `init --output KATALOG` | `init_project` | tworzy manifest (i katalog magazynu) | nie | tworzy |
| `add NAZWA <grupa> <komenda> [opcje]` | `add_project_task` | dodaje zadanie po walidacji bez sieci | nie | dopisuje |
| `remove NAZWA` | `remove_project_task` | usuwa zadanie; pliki zostaja w magazynie | nie | usuwa |
| `download [NAZWA...]` | `download_project` | pobiera i przypina niepobrane zadania; odtwarza brakujace przypiete pliki | tylko gdy trzeba | przypina niepobrane zadania; przy odtwarzaniu aktualizuje `version`/`label` (ta sama suma) |
| `download --check-updates [NAZWA...]` | `check_project` | porownuje przypiecia ze zrodlem, niczego nie pobiera | tak | nie |
| `download --upgrade [NAZWA...]` | `download_project(update="upgrade")` | pobiera nowsze dane wskazane sygnalem zrodla i przepina zadania | tak | przepina |
| `download --force [NAZWA...]` | `download_project(update="force")` | pobiera wszystko ponownie; inna tresc = nowe przypiecie | tak | przepina |
| `status [NAZWA...]` | `get_project_status` | zadania, przypiecia, istnienie i rozmiar plikow | nie | nie |
| `verify [NAZWA...]` | `verify_project` | sumy SHA-256 i zgodnosc z sidecarem wersji | nie | nie |
| - | `open_project` | odczyt i walidacja manifestu (dla nakladek: QGIS, GUI) | nie | nie |

`download`, `status` i `verify` maja tez `--quiet`/`-q` jak komendy grup
(bez paska postepu i linii statusu na stdout; `Info:`, `Warning:`
i `Error:` na stderr zostaja).

### 4.2 Przyklad pracy z projektem

Nowy projekt we wspolnym magazynie zespolu:

```bash
cd ~/projekty/wisla
kartograf project init --output /srv/dane/kartograf
kartograf project add teren elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007
kartograf project add pokrycie landcover download --source bdot10k --teryt 1465
kartograf project add gleby soil hsg --sheet N-34-130-D --depth 0-5cm
kartograf project download
kartograf project verify
```

Miesiac pozniej - czy sa nowsze dane i swiadome przejscie na nie dla
jednego zadania:

```bash
kartograf project download --check-updates
kartograf project download --upgrade teren
```

Kolega odtwarza projekt na swoim komputerze: manifest z repozytorium
projektu, wlasny magazyn wpisany w `output_dir` (reczna edycja jednej
linii; katalog magazynu musi istniec):

```bash
cd ~/projekty/wisla
kartograf project status
kartograf project download
kartograf project verify
```

Ze skryptu, bez zmiany katalogu:

```bash
kartograf project verify --project ~/projekty/wisla
```

Przykladowe wydruki (tekst ilustracyjny; ostateczny ustala implementacja,
slownictwo jak w USAGE 4.3):

```text
$ kartograf project download
teren: N-34-130-D-d-2-4: przypieto 2022-05-10_83233 (nowa wersja)
pokrycie: 1465: przypieto 2026-10-20 (nowa wersja)
gleby: przypieto 4 pliki (HSG N-34-130-D i wejscia clay, sand, silt 2.0)
Projekt: przypiete 3, bez zmian 0, bledy 0

$ kartograf project status
Projekt: /home/ola/projekty/wisla
Magazyn: /srv/dane/kartograf
teren     elevation download  1 plik   przypiete 2026-10-20
pokrycie  landcover download  1 plik   przypiete 2026-10-20
gleby     soil hsg            4 pliki  przypiete 2026-10-20

$ kartograf project download --check-updates
teren: N-34-130-D-d-2-4: nowsza: 2025-04-02_99887 (przypieta 2022-05-10_83233)
pokrycie: 1465: nie da sie sprawdzic bez pobrania (--force)
gleby: aktualne (4 pliki)
Aktualizacja: kartograf project download --upgrade [ZADANIE...]

$ kartograf project download --upgrade teren
teren: N-34-130-D-d-2-4: przypieto 2025-04-02_99887 (bylo 2022-05-10_83233)
```

### 4.3 API

```python
def init_project(project_dir: str | Path, *, output_dir: str | Path) -> Project
def open_project(project_dir: str | Path) -> Project
def add_project_task(project_dir: str | Path, *, name: str, command: str,
                     options: Mapping[str, object]) -> Project
def remove_project_task(project_dir: str | Path, *, name: str) -> Project
def download_project(project_dir: str | Path, *, tasks: Sequence[str] | None = None,
                     update: UpdateMode | None = None,
                     cache: MetadataCache | bool = False,
                     on_progress: Callable[[DownloadProgress], None] | None = None,
                     on_notice: Callable[[Notice], None] | None = None) -> ProjectReport
def check_project(project_dir: str | Path, *, tasks: Sequence[str] | None = None,
                  cache: MetadataCache | bool = False,
                  on_notice: Callable[[Notice], None] | None = None) -> ProjectCheck
def get_project_status(project_dir: str | Path, *,
                       tasks: Sequence[str] | None = None) -> ProjectCheck
def verify_project(project_dir: str | Path, *,
                   tasks: Sequence[str] | None = None) -> ProjectCheck
```

Typy wyniku (zamrozone dataclassy, eksport w `kartograf/__init__.py`):

```python
PinRole = Literal["output", "raw", "input"]

class PinnedFile:      # jeden wpis files[]
    role: PinRole; unit: str; path: str; version: str
    label: str; sha256: str; size_bytes: int

class ProjectTask:     # jedno zadanie
    name: str; command: str; options: Mapping[str, object]   # postac JSON
    pinned_at: str | None; kartograf_version: str | None
    geometry_sha256: Mapping[str, str] | None
    files: tuple[PinnedFile, ...]

class Project:
    directory: Path          # katalog projektu (rozstrzygniety)
    output_dir: Path         # magazyn (rozstrzygniety)
    tasks: tuple[ProjectTask, ...]

TaskOutcome = Literal["pinned", "unchanged", "restored", "updated", "failed"]

class TaskResult:
    name: str; outcome: TaskOutcome
    pinned: tuple[PinnedFile, ...]      # nowe przypiecia (pinned/restored/updated)
    unpinned: tuple[PinnedFile, ...]    # przypiecia zastapione albo odpiete
    errors: tuple[str, ...]             # przyczyny failed

class ProjectReport:   # download_project
    project: Project                    # stan manifestu po operacji
    tasks: tuple[TaskResult, ...]
    notices: tuple[Notice, ...]
    ok: bool                            # zadne wybrane zadanie nie zakonczylo sie failed

PinStatus = Literal["ok", "missing", "corrupt",                  # status, verify
                    "current", "newer", "added", "removed",      # check_project
                    "unverifiable", "check_failed"]

class FileCheck:
    task: str; unit: str; path: str; status: PinStatus
    pinned_label: str | None; available_label: str | None; detail: str | None

class ProjectCheck:    # get_project_status, verify_project, check_project
    project: Project
    files: tuple[FileCheck, ...]
    not_downloaded: tuple[str, ...]     # zadania bez przypiec
    notices: tuple[Notice, ...]
    ok: bool
```

Zasady API:

- `options` w `add_project_task` w postaci argumentow biblioteki (`BBox`,
  `Path`, napisy, liczby, `bool`, mapa per kraj, sekwencja); zapis do
  postaci JSON i odczyt z niej robi biblioteka. Nieznana nazwa opcji albo
  opcja innej komendy = `ValidationError` (manifest bywa edytowany
  recznie, wiec blad wejscia, nie programu).
- `ok` w `ProjectCheck`: `get_project_status`/`verify_project` - kazde wybrane
  zadanie przypiete i kazdy plik `ok`; `check_project` - zaden plik
  `check_failed` i zadne zadanie nie zakonczylo sie bledem.
- Nieznana nazwa zadania w `tasks` = `ValidationError` przed jakimkolwiek
  dostepem do sieci.
- `cache=False` domyslnie (M12); `True` tworzy cache w biezacym
  katalogu - tylko gdy ten katalog jest lokalny.
- Komunikaty bibliotek wywolanych dla zadania przechodza przez
  `on_notice` z tym samym `code` i tekstem poprzedzonym nazwa zadania
  (`teren: ...`).

### 4.4 `project init` i `project remove`

- `kartograf project init --output KATALOG [--project KATALOG]`:
  `--output` wymagane (brak wartosci domyslnej - M3). Istniejacy
  `kartograf-project.json` = blad ("projekt juz istnieje"), plik nie jest
  nadpisywany. Wydruk: sciezka manifestu i magazynu oraz podpowiedz
  `kartograf project add NAZWA <grupa> download ...`.
- `kartograf project remove NAZWA`: usuwa zadanie z manifestu razem z jego
  przypieciami; pliki zostaja w magazynie (moga je przypinac inne
  projekty). Zmiana zadania = `remove` + `add` albo reczna edycja
  `options` i `download --upgrade`.

### 4.5 `project add`

Gramatyka: `kartograf project add [--project KATALOG] NAZWA <grupa>
<komenda> [opcje komendy]`. Po nazwie zadania nastepuje dokladnie to,
co wpisuje sie po `kartograf` w komendzie grupy; parsuje to ten sam
parser (pomoc `--help` komendy dziala, blad flagi wyglada jak w grupie).
Dopuszczalny, ale zbedny separator `--` po nazwie.

- Dozwolone tylko komendy danych (zapisujace pliki w magazynie,
  sekcja 5). Inne (`list-sources`, `list-layers`, `availability`,
  `parse`, `cache`) - blad z lista dozwolonych komend.
- Walidacja bez sieci, ta sama co w bibliotece przed pierwszym
  zapytaniem: np. brak `--vertical-crs` daje ten sam `Error:` co
  `kartograf elevation download`. `add` niczego nie zgaduje i niczego
  nie pobiera.
- `--output`/`-o` mozna pominac; jesli jest (np. komenda wklejona
  z historii), musi wskazywac magazyn projektu - inaczej blad
  "zadanie pobiera do magazynu projektu (...); usun --output".
- `--check-updates`, `--upgrade`, `--force`, `--plan` - blad: tryby
  dotycza uruchomienia, nie zadania (`kartograf project download
  --upgrade NAZWA`).
- `--workers`, `--quiet`, `--summary` (`soil hsg`) - opcje jednego
  uruchomienia; nie sa zapisywane.
- Opcje podane po nazwie zadania naleza do komendy grupy; `--project`
  podane po nazwie = blad z podpowiedzia, by podac je przed nazwa.
- Plik geometrii musi istniec; sciezka zapisana wg 3.2.
- Wydruk: `Dodano zadanie teren (elevation download); pobierz: kartograf
  project download teren`.

### 4.6 `project download` (bez trybu)

Dla kazdego wybranego zadania, po kolei; manifest zapisywany po kazdym
zadaniu (przerwanie nie gubi zadan juz przypietych):

1. **Zadanie niepobrane:** wywolanie funkcji biblioteki komendy z
   `update=None` (ADR-036: wersje lokalne sa uzywane, brakujace
   pobierane). Pelny sukces -> przypiecie wszystkich plikow wyniku naraz
   (`pinned_at`, `kartograf_version`, `geometry_sha256`). Brak pelnego
   sukcesu -> nic nie jest przypinane, zadanie `failed`; pobrane pliki
   zostaja w magazynie i ponowienie wezmie je bez ponownego pobierania.
2. **Zadanie przypiete, wszystkie przypiete wersje sa w magazynie**
   (plik danych i sidecar, rozmiar zgodny): nic do zrobienia, bez sieci
   (`unchanged`). Swiezosc sprawdza `--check-updates`.
3. **Zadanie przypiete, brakuje czesci przypietych wersji** (np. nowy
   magazyn): odtworzenie - wywolanie biblioteki jak w 1 (geometria musi
   miec sumy z `geometry_sha256`). Brakujace przypiecie jest odtworzone,
   gdy wynik zawiera plik o tej samej sciezce standardowej i tej samej
   sumie SHA-256; `version` i `label` moga sie zmienic (wycinek bez
   sygnalu dostaje date pobrania), tresc przypiecia nie (`restored`).
   Inna suma -> zadanie `failed`, przypiecie bez zmian, nowy plik zostaje
   w magazynie nieprzypiety; komunikat wskazuje obie etykiety i dwie
   drogi: przywrocenie kopii magazynu albo `download --upgrade NAZWA`.
   Jesli w magazynie jest inna wersja tego pliku (przypieta zostala
   usunieta recznie), biblioteka zwraca ja bez pobierania i zachodzi ten
   sam przypadek. Odtworzone przypiecia sa zapisywane takze wtedy, gdy
   inne pliki zadania sie nie odtworzyly (tresc przypiec sie nie
   zmienia); zadanie jest `restored` tylko wtedy, gdy odtworzylo sie
   wszystko, inaczej `failed`.

**Pelny sukces** zadania wg rodziny wyniku (sekcja 5): `DataReport` -
`ok` i puste `failed` (zadanie `--country auto` z jednym krajem
nieudanym nie jest pelnym sukcesem projektu, choc komenda grupy konczy
sie kodem 0: projekt nie przypina polowy zadania); `LandCoverAreaResult` -
`ok` i plik w kazdej pozycji; `HsgResult` - `ok`, plik HSG i trzy
wejscia z plikami; wynik kolekcji planu C - `ok` i puste `failed`.
Kazdy plik wyniku musi miec sidecar wersji (inaczej `failed`). Wyjatek
biblioteki (`ValidationError`, `DownloadError`, `NoCoverageError`,
`TransformError`, `ParseError`) konczy tylko to zadanie (`failed`);
pozostale zadania wykonuja sie dalej.

**Odtwarzalnosc a "najnowszy".** Zadanie bez jawnego wariantu (np.
NMT PL bez `--year`) oznacza "najnowszy lot w chwili pobrania". Po
publikacji nowszego lotu odtworzenie na pustym magazynie pobierze nowszy
lot i skonczy sie bledem "inna tresc" (dane sa bezpieczne, ale trzeba
kopii magazynu albo `--upgrade`). Kto chce odtwarzac bez kopii magazynu,
zapisuje wariant w zadaniu (`--year`, w razie potrzeby rozdzielczosc
i uklad) - dokumentacja (USAGE) podaje to jako zalecenie. Projekt nie ma
wiedzy o lotach poszczegolnych produktow i nie zgaduje roku za
uzytkownika.

### 4.7 `project download --upgrade` i `--force`

- Wywolanie biblioteki z `update="upgrade"` albo `"force"` (ADR-036,
  USAGE 4.3): `--upgrade` pobiera tylko tam, gdzie sygnal zrodla wskazuje
  nowsza tresc (tor bez sygnalu zostaje przy wersji lokalnej z `Info:`
  o `--force`); `--force` pobiera wszystko ponownie (ta sama tresc =
  bez nowej wersji).
- Pelny sukces -> przypiecia zadania zastapione wynikiem w calosci: nowe
  wersje przypiete, pliki spoza wyniku odpiete, nowe pliki (np. nowy
  kafel LAZ) dopisane, nowe `pinned_at`, `kartograf_version`,
  `geometry_sha256` (przyjecie zmienionej geometrii). Gdy nic sie nie
  zmienilo: `unchanged`, manifest bez zmian.
- Brak pelnego sukcesu -> przypiecia zadania bez zmian (nigdy pol
  zadania), zadanie `failed`.
- `--upgrade` moze przepiac na nowsza wersje, ktora juz jest w magazynie
  (pobral ja inny projekt) - bez pobierania.
- Stare wersje zostaja w magazynie: moga je przypinac inne projekty.
- Zadanie niepobrane z trybem: pierwsze przypiecie jak w 4.6 punkt 1, tylko
  z podanym trybem.

### 4.8 `project download --check-updates`

Dla kazdego przypietego zadania wywolanie funkcji `check_*` jego komendy
(`check_data`, `LandCoverManager.check`, `HSGCalculator.check_hsg`,
`check_collection` z planu C) z opcjami zadania. Wynik (`UpdatePlan`) to
chwilowa sonda: nie jest zapisywany, a manifest sie nie zmienia.
Zadanie niepobrane: `nie pobrane`, bez sieci. Zmieniona geometria:
`Warning:` (plan dotyczy obecnego pliku geometrii).

Porownanie dotyczy przypiecia, nie najnowszej wersji lokalnej.
`PlanItem.local_sha256` to suma najnowszej wersji lokalnej, wzgledem
ktorej `check_*` liczy `status`; projekt laczy pozycje planu z
przypieciem po sciezce standardowej (`segment/hierarchy/name` pozycji
= `path` przypiecia; przy kilku przypieciach tego samego pliku, np.
`all_campaigns`, takze po etykiecie):

| Status | Wydruk CLI | Kiedy | Co zrobi `--upgrade` |
|---|---|---|---|
| `current` | `aktualne` | najnowsza lokalna = przypieta, a `check_*` daje `current` | nic |
| `newer` | `nowsza: <etykieta> (przypieta <etykieta>)` | najnowsza lokalna rozna od przypietej (nowsza wersja juz w magazynie) albo rowna, ale `check_*` daje `newer` lub `missing` (np. HSG z nowym wydaniem wejsc) | przepnie |
| `added` | `nowy plik w wyniku zadania` | pozycja planu bez przypiecia (np. nowy kafel LAZ, nowa kampania przy `all_campaigns`) | dopisze |
| `removed` | `poza wynikiem zadania` | przypiecie bez pozycji planu | odepnie (plik zostaje w magazynie) |
| `unverifiable` | `nie da sie sprawdzic bez pobrania (--force)` | najnowsza lokalna = przypieta, tor bez taniego sygnalu (wycinki, TM33, BDOT10k, podglad CORINE) | nic; `--force` pobierze i porowna sumy |
| `check_failed` | `blad sprawdzenia: <przyczyna>` | sygnalu nie udalo sie odczytac albo `check_*` zglosil blad | - |
| `missing` | `brak przypietego pliku w magazynie` | przypieta wersja nie istnieje lokalnie | `download` sprobuje odtworzyc |

Kod wyjscia: 1 przy `check_failed` albo bledzie zadania, inaczej 0 (jak
`--check-updates` grup). Projekt nie interpretuje sam sygnalow (ETag,
wydanie, rekord skorowidza) - robi to `check_*` wg ADR-036.

Zadanie z jawnym wyborem roku (`year`) jest `aktualne`, nawet gdy
istnieje nowszy rocznik: wybor jest czescia zadania. O innych wariantach
obszaru mowi raport dostepnosci (4.10).

### 4.9 `project status` i `project verify`

- `status`: bez sieci i bez czytania danych. Dla kazdego zadania: stan
  (`nie pobrane` / przypiete z data), liczba plikow; dla plikow -
  istnienie wersji i sidecara oraz zgodnosc rozmiaru (`ok`, `missing`,
  `corrupt` = inny rozmiar). Kod 0, gdy kazde wybrane zadanie jest
  przypiete i kazdy plik `ok`; inaczej 1 (nadaje sie do skryptow:
  `kartograf project status -q || kartograf project download`).
- `verify`: jak `status`, a dodatkowo dla kazdego przypietego pliku:
  poprawnosc sciezki (wzgledna, wewnatrz magazynu takze po rozwinieciu
  dowiazan symbolicznych, pod `versions/`, bez `.incoming`), pelny
  SHA-256 liczony strumieniowo, sidecar wersji `<plik>.meta.json`
  czytelny i zgodny z przypieciem (`sha256`, `size_bytes`,
  `extra.version.label`). Kod 0 tylko gdy wszystko zgodne i kazde zadanie
  przypiete.
- Ani `status`, ani `verify` niczego nie zmieniaja.
- Podpowiedzi: `missing` - `kartograf project download NAZWA` (odtworzy,
  jesli zrodlo ma te sama tresc) albo kopia magazynu; `corrupt` -
  przywroc katalog wersji z kopii albo usun uszkodzony katalog wersji
  i uruchom `kartograf project download NAZWA` (magazyn nie nadpisuje
  istniejacej wersji innymi bajtami).

### 4.10 Raport dostepnosci (`availability`)

`availability` (plan A: `elevation availability` dla PL, plan B: CZ) to
sonda zrodla dla obszaru przed wyborem wariantu: lata, uklady,
rozdzielczosci z kompletem pelnych arkuszy. Nie pobiera danych i nie
jest plikiem danych, wiec nie trafia do `files[]` i nie ma komendy
`project availability` (M9). Wybor dokonany na podstawie raportu
(np. `--year`, `--resolution`) staje sie opcja zadania:

```bash
kartograf elevation availability --product nmt --country pl --bbox 566000,243000,569000,246000
kartograf project add krakow-nmt elevation download --product nmt --country pl --bbox 566000,243000,569000,246000 --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --year 2025
```

Stopka raportu (`download_hint`: gotowe flagi `kartograf elevation
download`) wklejona po `kartograf project add NAZWA` daje zadanie w tym
wariancie; `--output` w podpowiedzi jest dozwolone, jesli wskazuje
magazyn projektu (4.5).

`download --check-updates` i `availability` odpowiadaja na rozne
pytania: pierwsze - czy przypiete pliki sa najnowsze dla wybranego
wariantu; drugie - jakie kompletne warianty ma obszar. Kompletny
wariant w raporcie nie oznacza, ze przypiety plik jest aktualny,
i odwrotnie.

### 4.11 Bledy, komunikaty, kody wyjscia

Teksty po polsku w ASCII (Z5), tworzy je biblioteka; CLI wypisuje
`Error:`/`Warning:`/`Info:` jak komendy grup. Bledy wejscia i manifestu:
`ValidationError` (STANDARDS 11), kod 1 i nic nie jest pobierane ani
zapisywane. Bledy zadan: w `ProjectReport`/`ProjectCheck`, kod 1, pozostale
zadania wykonane. Blad skladni argumentow: argparse, kod 2.

| Sytuacja | Komunikat (przyklad) |
|---|---|
| Brak manifestu | `Error: brak projektu w /home/ola/x (kartograf-project.json); utworz: kartograf project init --output KATALOG albo wskaz --project KATALOG` |
| Manifest juz istnieje (`init`) | `Error: projekt juz istnieje: /home/ola/projekty/wisla/kartograf-project.json` |
| Nieznany schemat | `Error: kartograf-project.json: nieznany schemat 'kartograf-project/2' (ten Kartograf zna kartograf-project/1); zaktualizuj Kartografa` |
| Nieznany klucz (np. literowka) | `Error: kartograf-project.json: zadanie teren: nieznany klucz 'optons'` |
| Nieznane zadanie | `Error: nieznane zadanie 'terne'; zadania projektu: teren, pokrycie, gleby` |
| Powtorzona nazwa (`add`) | `Error: zadanie teren juz istnieje; usun je (kartograf project remove teren) albo wybierz inna nazwe` |
| Komenda bez danych (`add`) | `Error: do projektu mozna dodac komendy zapisujace dane: elevation download, imagery download, landcover download, soil download, soil hsg` |
| Tryb w zadaniu (`add`) | `Error: --upgrade nie jest czescia zadania; aktualizacja projektu: kartograf project download --upgrade teren` |
| Inny magazyn w zadaniu (`add`) | `Error: zadanie pobiera do magazynu projektu (/srv/dane/kartograf), a --output wskazuje /tmp/x; usun --output` |
| Brak katalogu magazynu | `Error: magazyn projektu nie istnieje: /srv/dane/kartograf; podlacz udzial albo popraw output_dir w kartograf-project.json` |
| Inna tresc przy odtwarzaniu | `Error: teren: N-34-130-D-d-2-4: zrodlo ma inna tresc niz przypieta (przypieta 2022-05-10_83233, pobrana 2025-04-02_99887); przypiecie bez zmian - przywroc magazyn z kopii albo przyjmij nowa wersje: kartograf project download --upgrade teren` |
| Zmieniona geometria przy odtwarzaniu | `Error: teren: plik geometrii obszar/zlewnia.gpkg zmienil sie od przypiecia; przywroc go albo przyjmij nowy obszar: kartograf project download --upgrade teren` |
| Zadanie zmienione rownolegle | `Error: teren: zadanie zmienione w tym czasie przez inny proces; nic nie zapisano - ponow polecenie` |
| Blokada zajeta | `Error: projekt zablokowany przez inny proces (.kartograf-project.lock: host lab-3, pid 4121, od 2026-10-20T08:15:02+00:00); jesli zaden kartograf nie pracuje na tym projekcie, usun katalog .kartograf-project.lock` |
| Uszkodzony plik (`verify`) | `Error: pokrycie: 1465: suma SHA-256 inna niz przypieta - przywroc wersje z kopii magazynu` |

Nowe kody `Notice` projektu (np. zmieniona geometria przy
`--check-updates`) trafiaja do `kartograf/notices.py` jak pozostale.

### 4.12 Wspolbieznosc i trwalosc zapisu

- Zapis manifestu: plik tymczasowy w katalogu projektu, `flush` +
  `fsync`, `os.replace` na `kartograf-project.json`, synchronizacja
  katalogu (gdy system plikow ja wspiera). Przerwanie w dowolnej chwili
  zostawia stary albo nowy manifest, nigdy polowe.
- Blokada: katalog `.kartograf-project.lock` tworzony atomowo (`mkdir`)
  wylacznie na czas odczyt-scalenie-zapis (milisekundy), z informacja
  o wlascicielu (host, pid, czas). Zajeta blokada: krotkie ponawianie,
  potem blad z instrukcja (4.11). Brak automatycznego przejmowania.
- Scalanie per zadanie: operacja pamieta stan zadan z chwili swojego
  odczytu; pod blokada czyta manifest ponownie i zapisuje tylko zadania,
  ktorych nikt w tym czasie nie zmienil. Rownolegle `download` roznych
  zadan nie koliduja; to samo zadanie zmienione rownolegle konczy sie
  bledem tego zadania, bez nadpisania (pobrane pliki zostaja w magazynie,
  ponowienie ich uzyje).
- System plikow projektu musi wspierac atomowe `mkdir` i `rename`
  (lokalne dyski, NFS, SMB je wspieraja); zadnej bazy SQLite ani blokad
  zakresow bajtow na udziale. Magazyn nadal wymaga dowiazan twardych
  (ADR-036 D22).

## 5. Integracja z komendami danych (istniejace i plany A-E)

Projekt nie ma logiki per produkt: zna komendy danych i rodziny wyniku
(listy produktow i zrodel komend bierze z biblioteki - te same, z ktorych
korzysta CLI). Jedna pozycja na komende danych CLI w
`kartograf/project/commands.py`:

| `command` | Funkcja biblioteki | Sonda | Rodzina wyniku -> przypiecia |
|---|---|---|---|
| `elevation download`, `imagery download` | `download_data` | `check_data` | `DataReport.files[].file` (`output`) |
| `landcover download` | `LandCoverManager(output_dir, source).download` | `.check` | `LandCoverAreaResult.files[].file` (`output`), `.raw` (`raw`) |
| `soil download` | `LandCoverManager(output_dir, "soilgrids").download` | `.check` | jak wyzej |
| `soil hsg` | `HSGCalculator(output_dir).calculate_hsg` | `.check_hsg` | `HsgResult.file` (`output`), `.inputs[].file` (`input`) |
| `download` nowych grup planow C-E | `download_collection` (plan C) | `check_collection` | `CollectionReport.files[].file` (`output`) |

Z kazdego `VersionedFile` powstaje `PinnedFile`: `path` z
`VersionedFile.path`, `version` z `VersionedFile.version_path` (obie
wzgledne do magazynu), `label`, `sha256`, a `size_bytes` z sidecara
wersji, ktory musi istniec. Kazda pozycja ma tez walidacje wyboru bez
sieci (`project add`): te sama funkcje, ktora funkcja pobrania wywoluje
przed pierwszym zapytaniem (dzis: `validate_request` dla `download_data`,
kontrola opcji i wyboru `LandCoverManager`, wybor `HSGCalculator`),
oraz zbior dozwolonych opcji rowny flagom danych komendy w CLI.

- **Nowy produkt w istniejacej komendzie** (plany A, B, E: np. NMT 0,5 m,
  NMT 100 m, orto prawdziwa w `elevation`/`imagery`): zero zmian
  w projekcie - nowe wartosci opcji przechodza przez te sama pozycje.
- **Nowa grupa** (plany C, D, E: `boundaries`, `cadastre`, `models3d`,
  `names`, `maps`, `geodesy`, ...) musi: (1) miec funkcje biblioteki
  poziomu komendy z `output_dir`, wyborem, `update`, `cache`,
  `on_notice` i wynikiem z `VersionedFile` na plik oraz `ok`/`failed`,
  a obok blizniaka `check_*` zwracajacego `UpdatePlan` (plan C:
  `download_collection`/`check_collection`) i walidacje wyboru bez sieci
  wspolna z funkcja pobrania; (2) dodac pozycje
  w `kartograf/project/commands.py`; (3) w parserze komendy ustawic
  `_task` (nizej); (4) dodac test jednego zadania projektu dla nowej
  rodziny wyniku. Kolejnosc scalania z planami C-E jest dowolna: kto
  scala sie pozniej, dopisuje pozycje.
- **CLI (uzupelnienie ADR-039):** parser kazdej komendy danych ustawia,
  obok `_handler`, `_task`: funkcje `argparse.Namespace -> dict`
  zwracajaca argumenty biblioteki tej komendy bez `output_dir`, trybow
  i opcji uruchomienia - to samo tlumaczenie, ktorego uzywa `_handler`
  (jedno miejsce). `project add` parsuje komende parserem glownym,
  bierze `_task` i nazwe komendy z przestrzeni nazw argparse.
- Plik bez sidecara wersji nie moze byc przypiety (`verify` opiera sie na
  nim); zasada magazynu ADR-036 to gwarantuje.

## 6. Kryteria akceptacji

1. `init` tworzy czytelny manifest (3.3) i katalog magazynu; ponowny
   `init` nie zmienia ani bajtu; sciezka magazynu wzgledna/bezwzgledna
   zapisana wg 3.2; przeniesienie projektu z magazynem (wzgledny
   `output_dir`) dziala bez zmian.
2. `add` dla `elevation download`, `imagery download`, `landcover
   download`, `soil download` i `soil hsg` zapisuje opcje identyczne
   z argumentami, ktore komenda grupy przekazalaby bibliotece; bledny
   albo niepelny wybor daje ten sam blad co komenda grupy, przed siecia
   i bez zmiany manifestu; `--upgrade`/obcy `--output` w zadaniu = blad.
3. Na magazynie offline (fixtury z prawdziwych odpowiedzi): pierwsze
   `download` przypina wszystkie pliki zadan arkusza PL, `--country auto`,
   LAZ (kilka kafli), BDOT10k (kilka powiatow i `keep_raw`), SoilGrids,
   CORINE i HSG (wynik + 3 wejscia); niepowodzenie jednej jednostki = nic
   nie przypiete, a ponowienie konczy przypieciem bez ponownego
   pobierania udanych jednostek.
4. Drugi projekt pobierajacy nowsza wersje do tego samego magazynu nie
   zmienia przypiec pierwszego; `verify` pierwszego przechodzi, choc
   sciezka standardowa wskazuje nowsza wersje.
5. `verify` wykrywa zmiane jednego bajtu, brak pliku, podmieniony albo
   niezgodny sidecar i przypiecie spoza magazynu; `status` wykrywa brak
   i inny rozmiar bez czytania danych.
6. `download --check-updates` rozroznia statusy z 4.8 wzgledem
   przypiecia (takze gdy magazyn ma juz nowsza wersje, a `check_*` daje
   `current`), niczego nie pobiera i nie zmienia manifestu.
7. `download --upgrade NAZWA` przepina tylko to zadanie, w calosci, po
   pelnym sukcesie; `--force` dla toru bez sygnalu z ta sama trescia nie
   zmienia przypiecia, z inna - przepina; porazka = przypiecia bez zmian.
8. Odtwarzanie na pustym magazynie: ta sama tresc u zrodla - przypiecia
   odtworzone (`restored`); inna tresc - blad z podpowiedzia, przypiecie
   bez zmian.
9. Dwa procesy `download` roznych zadan tego samego projektu nie gubia
   swoich przypiec; tego samego zadania - jeden konczy sie bledem bez
   nadpisania; przerwanie przy zapisie zostawia poprawny manifest.
10. CLI = API (ADR-037): `project` z kazda komenda daje te same
    przypiecia, statusy, `Notice` i bledy co funkcje biblioteki; operacje
    projektu nie tworza `.kartograf_cache.db` w katalogu projektu.
11. Kazda nowa grupa planow C-E przed scaleniem ma pozycje w
    `kartograf/project/commands.py`, `_task` i test zadania projektu
    (sekcja 5).

## 7. Scenariusze na zywo (przed wydaniem)

Dane wylacznie w katalogu poza repo i poza `/tmp` (`<katalog-danych>`),
CLMS bez credentials pomijamy.

1. Projekt A w `<katalog-danych>/projekty/a` z magazynem
   `<katalog-danych>/magazyn`: zadania NMT PL (jeden arkusz), BDOT10k
   (jeden powiat), SoilGrids + HSG (maly arkusz) i jedno zadanie CZ
   (arkusz SM5 - sygnal `http`); `download`, `status`, `verify`.
2. Projekt B na tym samym magazynie: to samo zadanie NMT; pliki wziete
   z magazynu bez pobierania, te same przypiecia.
3. `download --check-updates` w A: statusy zgodne z sygnalami torow
   (NMT `index`, SM5 `http`, SoilGrids `metadata`, BDOT10k `unverifiable`);
   brak pobran (licznik zapytan albo czas, rozmiar magazynu bez zmian).
4. Kopia magazynu (`rsync -aH`) w nowe miejsce, zmiana `output_dir`,
   `verify` zgodny; drugi projekt z pustym magazynem: `download`
   odtwarza przypiecia (`restored`) przy niezmienionym zrodle.
5. Raport w `docs/research/` z dokladnymi poleceniami (sciezki jako
   `<katalog-danych>`), statusami, liczbami plikow i ograniczeniami
   sygnalow.
