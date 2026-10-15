# Spec: Manifest projektu (podprojekt 2, Kartograf 0.8.0)

**Data:** 2026-10-15  
**Status:** projekt do implementacji; decyzje architektoniczne ADR-040  
**Zaleznosci:** magazyn wersjonowany ADR-036, spojnosc CLI/API ADR-037,
grupy CLI ADR-039. Produkty z planow A-E podprojektu 3 wchodza do 0.8.0.

## 1. Cel i granice

Projekt pamieta, **jakie zadanie** uzytkownik zlecil i **ktore dokladnie pliki**
z magazynu przyjal. Ten sam magazyn sluzy wielu projektom; drugi projekt
wykorzystuje lokalne wersje, nie kopiuje rastra do swojego katalogu. Po
pojawieniu sie nowej wersji w magazynie lub u zrodla projekt zachowuje
przypiete wersje, dopoki uzytkownik jawnie go nie zaktualizuje.

Przyklad: zespol moze odtworzyc liste wejsciowych NMT/SoilGrids/HSG dla
analizy sprzed miesiaca, zweryfikowac sumy SHA-256 i odtworzyc **zadanie
pobrania** na nowym magazynie. Nie obiecujemy, ze odlegla usluga zachowa
stara wersje danych; odtworzenie **tych samych bajtow** wymaga zachowania
pliku wersji w magazynie lub jego kopii. Brak automatycznego czyszczenia
wersji przypietych przez manifesty.

Nie jest to katalog wszystkich danych na udziale, indeks projektow ani
funkcja `availability`. Te ostatnie raportuje zrodlo (sekcja 7); raport
nie jest plikiem danych i nie trafia do listy przypietych plikow.

## 2. Decyzje i odrzucone warianty

| # | Decyzja | Odrzucone warianty i powod |
|---|---|---|
| M1 | `kartograf-project.json`, UTF-8, czytelny JSON z wcieciem 2 spacji, schema `kartograf-project/1` | SQLite w projekcie/magazynie: udzial moze nie obslugiwac blokad bajtow; YAML: nowa zaleznosc i niejednoznaczne typy; plik planu `kartograf-plan/1`: to przemijajaca kontrola zrodla, nie przypiecie |
| M2 | Projekt ma zadania z jawnym wyborem produktu/obszaru oraz wpisy konkretnych wersji z pelnym SHA-256, rozmiarem i sidecarem | Sama lista sciezek: nie odtworzy zadania; same komendy tekstowe: nie okreslaja przyjetych bajtow |
| M3 | `--output` podane jawnie przy `project init` okresla jeden wspolny magazyn; pliki danych wskazuja **wylacznie** sciezki wzgledne do tego magazynu, nigdy sciezki standardowe | Kopia danych per projekt: zuzycie miejsca, rozjazd wersji; zapisywanie tylko sciezek bezwzglednych: nieprzenosne |
| M4 | `project add --name ID -- <grupa> download <wybor>` (albo `soil hsg`) zapisuje wybory danych, nie uruchamia pobrania; `project download` pierwszy raz przypina wynik; `project update` jedyny sposob zamiany przypiec | Druga lista flag per produkt w `project add`: rozjezdza sie z grupami ADR-039; automatyczna aktualizacja przy `download`: niszczy odtwarzalnosc |
| M5 | `verify` liczy SHA-256 pliku i sidecara wersji; `status` tylko lokalna kontrola istnienia i rozmiaru; `check-updates` osobno odpytuje sygnal zrodla bez pobrania | Status z ukryta siecia; ufanie nazwie katalogu `_sha8` lub hardlinkowi zamiast pelnej sumie |
| M6 | Jeden adapter wyniku `VersionedFile`/sidecara i kilka istniejacych rodzin wywolan API, bez logiki dla kazdego produktu | Reczne czytanie ukladu katalogow per produkt; dopisywanie projektow do sidecara wersji (narusza jego niezmiennosc) |
| M7 | Manifest i sidecary sa zrodlem prawdy; zapis manifestu przez atomowa podmiane pod blokada katalogowa `mkdir`, bez SQLite i bez byte-range locks na udziale | `os.replace` bez serializacji: zgubienie jednego z dwoch rownoleglych dopisow; automatyczne przejmowanie starej blokady: mozliwa utrata zmian aktywnego procesu |
| M8 | `availability` to oddzielne, nieutrwalane zapytanie dla zadania obszarowego, jesli dana grupa je obsluguje | Traktowanie kompletnosci arkuszy jako gwarancji aktualnosci plikow lub jako warunku `project download` |

## 3. Format i model

Plik: `<katalog-projektu>/kartograf-project.json`. `project init --project
<katalog-projektu> --output <katalog-danych>` tworzy tylko katalog projektu
i manifest (bez pobierania). Katalog moze zawierac pozostale pliki analizy.
`schema` pozwoli odrzucic nieznana przyszla wersje bez cichej migracji.
Przyklad po dodaniu zadania, przed pierwszym pobraniem (`files` jest puste):

```json
{
  "schema": "kartograf-project/1",
  "store": {"path": "../data"},
  "tasks": [
    {
      "name": "teren",
      "group": "elevation",
      "action": "download",
      "selection": {
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": "1m",
        "vertical_crs": "EVRF2007"
      },
      "files": []
    }
  ]
}
```

Po pobraniu Kartograf dopisuje pola `files` z **rzeczywistych** wynikow
wersji; sum kontrolnych i rozmiarow nie wpisuje sie na oko. Przy `init`
sciezka `--output` wzgledna jest rozstrzygana wzgledem biezacego katalogu
CLI i zapisywana **wzgledem projektu** (np. `--project ./projekt
--output ./data` daje `store.path: "../data"`); bezwzgledna pozostaje
bezwzgledna. Przy odczycie manifestu `store.path` wzgledna jest
rozstrzygana wzgledem katalogu projektu. Przeniesienie razem
`projekt/` i `data/` z zachowaniem ich relacji nie wymaga zmian; przeniesienie
samego projektu przy wzglednym magazynie wymaga korekty `store.path` w JSON.
Przeniesienie samego projektu przy bezwzglednym magazynie nie wymaga zmiany.
Po przeniesieniu magazynu poprawia sie tylko `store.path`, nie kazdy plik;
`verify` sprawdza kopie magazynu. Kopiuj magazyn razem z sidecarami
(`rsync -aH` zachowuje dowiazania twarde). Zadna operacja nie zaklada,
ze katalog projektu i magazyn sa na tym samym systemie plikow.

Kazde zadanie ma unikalne `name` (`[a-z0-9][a-z0-9_-]*`), `group` z grup
CLI 0.8.0 (`elevation`, `imagery`, `landcover`, `soil`, `boundaries`,
`cadastre`, `models3d`, `names`, `maps` oraz nowe grupy z planu E),
`action="download"` (dla `soil hsg`: `action="hsg"`), `selection` =
**kanoniczne typowane opcje danych** bez `--output`, `--quiet`, `--workers`,
`--check-updates`, `--upgrade`, `--force`, `--plan` i `--cache`. Przy zapisie
dopelnij jawne wartosci majace wplyw na bajty, jesli dany tor ma dopuszczalne
wartosci domyslne (np. format BDOT10k): zmiana domyslnych w kolejnej
wersji programu nie zmieni odtwarzanego wyboru. Jawne wybory wymagane
przez grupe dalej sa wymagane; `project add` niczego nie zgaduje. BBox ma postac
`{"coords":[min_x,min_y,max_x,max_y],"crs":"EPSG:2180"}`; wartosci
`pl=...,cz=...` sa mapami, rok liczba, wartosci logiczne boolean. `geometry`
(wraz z `layer` gdy potrzeba) ma sciezke wzgledna do projektu i SHA-256
pliku; dla SHP takze sumy wymaganych `.shp/.shx/.dbf/.prj`, tak by zmiana
wejscia wymagalo jawnego poprawienia zadania. Biblioteka odmawia wykonania
zadania po zmianie geometrycznych danych wejsciowych; nie przelicza obszaru
po cichu. Zalecany sposob przenoszenia: geometria wewnatrz projektu.

`files` to **jeden wpis per rzeczywisty `VersionedFile`**, bez duplikatow
tej samej sciezki (arkusze, LAZ, powiaty, raster, surowy ZIP BDOT10k z
`keep_raw`, wynik HSG i jego trzy wejscia). `role` = `output`, `raw` lub
`input`; `unit` = jednostka wyniku (godlo, kafel, TERYT lub bbox), `country`
moze byc `null` dla danych globalnych. `path` jest sciezka pliku
w `versions/` **wzgledem katalogu magazynu**, z `VersionedFile.version_path`,
nie `VersionedFile.path` (sciezka standardowa wskazuje najnowsza lokalna
wersje i moze sie zmienic). Z wersji i jej obowiazkowego
`<nazwa>.meta.json` pochodza pelny `sha256`, `size_bytes`, `dataset`,
`extra.version.label` i SHA-256 sidecara; musza sie zgadzac z wynikiem API.

| Pole `files[]` | Typ i pochodzenie |
|---|---|
| `role`, `unit`, `country` | rola (`output`/`raw`/`input`), jednostka wyniku, kod kraju albo `null` |
| `path` | napis z `VersionedFile.version_path`, wzgledny do `store.path` |
| `sha256`, `size_bytes` | pelny SHA-256 (64 male znaki hex) i liczba bajtow z sidecara wersji, potwierdzone wynikiem API |
| `sidecar_sha256` | pelny SHA-256 bajtow niezmiennego sidecara `<plik>.meta.json` |
| `dataset`, `label` | `sidecar.dataset`, `sidecar.extra.version.label` |

Zrodlo i pierwotne `request`/`extra.parent_request` pozostaja w
**niezmiennym** sidecarze wersji: to opis zadania, ktore WYTWORZYLO plik,
nie zawsze tozsamy z aktualnym zadaniem, ktore uzylo lokalnej wersji.
`selection` manifestu opisuje z kolei zadanie, ktore wybralo te wersje.
Dla HSG `extra.source_files[]` laczy pochodna z wersjami wejsciowymi;
manifest przypina rowniez te wejscia, nawet jesli inny projekt zapisze
nowszy HSG. Pliki dokumentacji, raport `availability` i cache nie sa wpisami.

## 4. Publiczne API i polecenia

Jedna grupa `kartograf project` zarejestrowana w parserze/dispatcherze
po scaleniu ADR-039. API eksportowane przez `kartograf/__init__.py`:

```python
init_project(project_dir: str | Path, *, output_dir: str | Path) -> ProjectManifest
add_project_task(project_dir: str | Path, *, name: str, group: str,
                 selection: Mapping[str, object],
                 action: Literal["download", "hsg"] = "download") -> ProjectManifest
download_project(project_dir: str | Path, *, tasks: Sequence[str] | None = None,
                 cache: MetadataCache | bool = False,
                 on_notice: Callable[[Notice], None] | None = None) -> ProjectReport
verify_project(project_dir: str | Path, *, tasks: Sequence[str] | None = None) -> ProjectReport
status_project(project_dir: str | Path, *, tasks: Sequence[str] | None = None) -> ProjectReport
check_project_updates(project_dir: str | Path, *, tasks: Sequence[str] | None = None,
                      cache: MetadataCache | bool = False,
                      on_notice: Callable[[Notice], None] | None = None) -> ProjectReport
update_project(project_dir: str | Path, *, tasks: Sequence[str] | None = None,
               force: bool = False, cache: MetadataCache | bool = False,
               on_notice: Callable[[Notice], None] | None = None) -> ProjectReport
project_availability(project_dir: str | Path, *, name: str,
                     cache: MetadataCache | bool = False) -> AvailabilityReport
```

Nazwy (`snake_case`) i `ProjectManifest`/`ProjectReport` to nowy publiczny
kontrakt; zadna z tych funkcji nie istnieje jeszcze w kodzie `develop`.
`ProjectReport`: deterministycznie ulozone `tasks` (nazwa, przypiete pliki,
stan lokalny i stan zrodla jesli sprawdzono), `failed` (zadanie, jednostka,
tekst, rodzaj), `notices: tuple[Notice,...]`, `ok: bool` (CLI 0 gdy
wszystkie zadane operacje zakonczone pomyslnie). Raport rozroznia `pending`,
`missing`, `corrupt`, `current`, `newer`, `unverifiable`, `check_failed`;
`check_failed` NIE jest `current`. Z API poziomu grup/torow pochodzi
`DataReport(files: tuple[UnitFile,...], failed, stale, notices, ok)`, w
`UnitFile.file` jest `VersionedFile(path,status,label,sha256,version_path)`;
arkusze PL: `DownloadResult.files`, land cover:
`LandCoverAreaResult.files[].file` i `.raw`, HSG: `HsgResult.file` i
`.inputs[].file`. Adapter wyniku obejmuje te **rodziny wyniku**, a nie
liste nazw produktow. Nastepny produkt planow A-E uzywa istniejacej
rodziny lub wprowadza wspolny wynik z `VersionedFile` (wymagane przy
jego wprowadzeniu); bez wyniku i sidecara nie moze byc przypiety.

| CLI | Znaczenie |
|---|---|
| `project init --project KATALOG --output KATALOG` | Zapisuje magazyn i pusty manifest; istniejacego manifestu nie nadpisuje. To jawne `--output` dla calego projektu. |
| `project add --project KATALOG --name ID -- <grupa> download <wybor>` (lub `soil hsg`) | Wspolny parser grup i biblioteczna walidacja opcji; nie pobiera, nie przyjmuje `-o` w zagniezdzonej komendzie. |
| `project download --project KATALOG [--name ID]` | Pierwsze pobranie lub dopelnienie nieprzypietego zadania z magazynu; nigdy nie zastapi istniejacego przypiecia. |
| `project status --project KATALOG [--name ID]` | Lokalnie: lista przypiec, brakow i rozmiarow bez sieci i bez liczenia SHA. Nie mylic z weryfikacja. |
| `project verify --project KATALOG [--name ID]` | Offline SHA-256 plikow i sidecarow wersji; kod 1 przy braku, naruszeniu lub uszkodzeniu. |
| `project check-updates --project KATALOG [--name ID]` | Bez pobierania danych: dostepnosc swiezszych wersji u zrodla i stan niesprawdzony. |
| `project update --project KATALOG [--name ID] [--force]` | Jawne pobranie nowszych danych i atomowa zmiana przypiec po sukcesie; `--force` ponownie pobiera wszystkie wybrane jednostki, takze bez sygnalu (moze byc kosztowne). |
| `project availability --project KATALOG --name ID` | Raport `AvailabilityReport` z `check_availability` dla obszarowego zadania grupy oferujacej `availability`, bez zmian manifestu. |

Opcja `--name ID` poza `add` i `availability` wybiera jedno zadanie;
bez niej przetwarzane sa wszystkie w kolejnosci z manifestu. Przyklad
pierwszego uzycia (projekt i magazyn to odrebne katalogi):

```bash
kartograf project init --project ./projekt-wisla --output <katalog-danych>
kartograf project add --project ./projekt-wisla --name teren -- elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007
kartograf project add --project ./projekt-wisla --name pokrycie -- landcover download --source bdot10k --teryt 1465
kartograf project download --project ./projekt-wisla
kartograf project verify --project ./projekt-wisla
kartograf project check-updates --project ./projekt-wisla
kartograf project update --project ./projekt-wisla --name teren
```

`availability` nie jest aliasem `check-updates`: np. dla obszaru:

```bash
kartograf project add --project ./projekt-wisla --name nmt-obszar -- elevation download --product nmt --country pl --bbox 566000,243000,569000,246000 --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992
kartograf project availability --project ./projekt-wisla --name nmt-obszar
```

Analogicznie API: `init_project("projekt-wisla", output_dir="<katalog-danych>")`,
`add_project_task("projekt-wisla", name="teren", group="elevation",
selection={"product": "nmt", "sheet": "N-34-130-D-d-2-4",
"resolution": "1m", "vertical_crs": "EVRF2007"})`,
`download_project("projekt-wisla")`. `--` oddziela opcje projektu od
istniejacej gramatyki komendy pobierania; `project` nie wywoluje
`cli.main()` i nie przechwytuje tekstowego stdout. `project add` konwertuje
flagi do typowanych opcji; cala walidacja wyboru danych i wykonanie
pozostaja w bibliotece (ADR-037). Opcje zalezne od wersji programu
(transport, cache, prezentacja) nie sa czescia zadania. Wybor w
`project add` nie przyjmuje `availability` jako akcji zapisu pliku.

## 5. Pobranie, przypiecie i weryfikacja

Pierwsze `download_project` wywoluje publiczne funkcje poziomu grup z
`output_dir` manifestu. Domyslnie wykorzystuje prawidlowe lokalne wersje
(ADR-036). `DataReport.ok=False`, pozycje `failed` lub `stale`,
`LandCoverAreaResult.ok=False` i blad HSG nie sa sukcesem zadania:
udane **jednostki** mozna zapisac jako przypiete wraz z jawnym raportem
niepowodzenia; ponowienie dopelnia tylko nieprzypiete jednostki. Przy
kazdym konflikcie tej samej jednostki ze starym przypieciem operacja
zwraca blad, zamiast zamienic stare przypiecie. Raz przypiete poprawne
zadanie `project download` zostawia w spokoju; uszkodzone/przeniesione
pliki przypiete wymagaja przywrocenia wersji z kopii i `verify` (nie
zastapienia przez obecna sciezke standardowa). `update_project` przed
zmiana przypiec wymaga poprawnego `verify` wybranych zadan: uszkodzonych
bajtow nie wolno przykryc aktualizacja.

`verify` rozstrzyga sciezke pod katalogiem magazynu po kanonicznej
walidacji (`versions/`, bez `..`, bez sciezek bezwzglednych i bez
symlinkow wychodzacych poza magazyn), sprawdza istnienie i rozmiar,
liczy pelny SHA-256 strumieniowo raz na plik; odczytuje wersyjny sidecar,
sprawdza `schema="kartograf-meta/1"`, `dataset`, `sha256`,
`size_bytes`, `extra.version.label` oraz SHA-256 bajtow sidecara.
Przy uszkodzeniu sidecara nie modyfikuje ani pliku ani manifestu. Sama
sciezka standardowa, etykieta lub `samefile` nie sa dowodem tozsamosci.
Zwykla kontrola `status` jest szybka, ale NIE zastępuje `verify`.

Projektowe funkcje domyslnie uzywaja `cache=False`, aby nawet start
z katalogu projektu na udziale sieciowym nie tworzyl tam domyslnej
`<cwd>/.kartograf_cache.db`. Wywolujacy API moze podac **lokalna**
instancje `MetadataCache` lub `True` tylko z lokalnego cwd; CLI `project`
nie ma flagi tworzacej cache na udziale. W zadnej galezi nie powstaje
wspolna baza SQLite. Sidecary wersji nigdy nie sa aktualizowane
informacja o projektach; odwrotny indeks "ktore projekty uzywaja pliku"
mozna zbudowac lokalnie z manifestow, lecz nie jest on zrodlem prawdy
ani czescia tej implementacji.

## 6. Swiezosc i jawna aktualizacja

`check_project_updates` uzywa `check_data`, `LandCoverManager.check`,
`HSGCalculator.check_hsg` i analogicznych publicznych `check_*` nowych
grup; kazde zwraca `UpdatePlan` (`kartograf-plan/1`, `PlanItem.status`,
`available_label`, `available_signal`, `track`, `segment`, `hierarchy`,
`name`, `unit`). Plan to **sonda**, nie nowy manifest; nie zapisujemy
go w projekcie. Porownanie odbywa sie wzgledem **przypietej wersji** i
sygnalu z jej sidecara, nie wzgledem najnowszego pliku w magazynie ani
samego `PlanItem.status` (ten dotyczy najnowszej wersji lokalnej).
Identyfikacja jednostki wykorzystuje `track/segment/hierarchy/name`
plus wynik `VersionedFile.version_path`; nie porownuje plikow z roznych
torow po samej nazwie. Porownania korzystaja z zasad toru ADR-036:

| Sygnal toru | `check-updates` |
|---|---|
| `index` (arkusze PL, LAZ, nowe skorowidze A-E) | Porownanie wybranego rekordu/etykiety z przypietym lotem; nowy kafel LAZ/nowa jednostka to dodatkowa pozycja, nie podmiana istniejacego wpisu. |
| `metadata` (SoilGrids, CORINE CLMS, ATOM A-E) | Porownanie wydania z przypietym `extra.version`/`extra.edition`, nie z kopia `*_preview`. |
| `http` (SM5, pliki CUZK A-E z naglowkami) | Porownanie `ETag`/`Last-Modified` z `extra.http`; `Content-Length` samo nie jest sygnalem. |
| `none` (WCS PL, ImageServer CZ, BDOT10k, podglad CORINE i inne bez sygnalu) | `unverifiable`, bez wniosku o aktualnosci; dopiero `update --force` pobiera do porownania sum. |
| HSG | Porownanie zestawu SHA-256 przypietych clay/sand/silt z aktualnymi wydaniami/wersjami wejsc; `HsgResult.inputs` i `extra.source_files` wskazuja faktyczne wejscia. |

Brak sygnalu lub awaria uslugi daje `unverifiable`/`check_failed`, nie
"aktualne"; `--force` to **pobranie**, nigdy tryb `check-updates`.
`availability` z planu A/B pyta o kompletnosc i warianty obszaru (PL:
pelne arkusze wg skorowidza i PRG; CZ: dane katalogowe). Nawet kompletna
kombinacja nie dowodzi, ze przypiety plik jest najnowszy; `project
availability` nie zapisuje wyniku ani nie zmienia przypiec.

`project update` bez `--force` uzywa `update="upgrade"` istniejacych
torow: pobiera tylko nowy porownywalny sygnal, przypina nowe wersje i
pozostawia stare w magazynie. Gdy tor jest `unverifiable`, pozostawia
pin bez zmian i wypisuje `Warning:` z podpowiedzia `project update
--force`. `project update --force` daje torom `update="force"` i porownuje
SHA; identyczna zawartosc nie zmienia przypiecia, inna tworzy nowa
wersje. Sukces dla zadania wymaga kompletu zwroconych wymaganych
plikow, ich sidecarow i poprawnego `verify` **nowych** pinow przed
atomowa podmiana manifestu. Awaria jednej jednostki nie zmienia pinow
tej jednostki (zadanie moze byc czesciowo zaktualizowane tylko z jawnym
raportem, nigdy ukryty sukces). Zaden tryb nie usuwa starych wersji.
Jesli celem jest historyczna kampania nieobecna u zrodla i w magazynie,
aktualizacja nie odtworzy jej bajtow: nalezy przywrocic kopie magazynu.

## 7. Bledy, komunikaty, wspolbieznosc

- Uszkodzony JSON, nieznane schema, powtorzona nazwa, nieznana grupa/opcja,
  wybor spoza skladni grupy, sciezka poza magazynem, zmieniona geometria:
  `ValidationError` z porada; niesprawne zrodlo: `DownloadError` albo
  `failed` w `ProjectReport`; blad odczytu lokalnego pliku: raport `missing`/
  `corrupt`, bez maskowania przez pobranie.
- Przyklad bledu: `Error: zadanie teren: plik wersji nie istnieje;
  przywroc magazyn i uruchom kartograf project verify --project
  ./projekt-wisla`. Przyklad informacji: `Info: teren: dostepna nowsza
  wersja; przypieta wersja bez zmian (kartograf project update --project
  ./projekt-wisla --name teren)`. Przyklad niesprawdzalnosci:
  `Warning: teren: zrodlo bez taniego sygnalu; wersja przypieta bez zmian
  (kartograf project update --project ./projekt-wisla --name teren
  --force)`. Komunikaty tworzy biblioteka jako `Notice(level, code, text)`,
  po polsku ASCII; CLI tylko renderuje `Info:`/`Warning:` takze z `-q`.
- Zapis projektu: plik tymczasowy w katalogu projektu, `fsync`,
  `os.replace` i synchronizacja katalogu, pod wykluczajaca blokada
  katalogowa tworzona atomowo (`.kartograf-project.lock/`). Po uzyskaniu
  blokady jeszcze raz odczytaj manifest i sprawdz oczekiwana wersje/zmiane
  (hash bajtow): brak nadpisania cudzych zmian. Blokady nie przejmuj
  automatycznie po czasie: po przerwanym procesie komunikat wskazuje jak
  bezpiecznie sprawdzic wlasciciela i usunac osierocony katalog. Przy
  konkurencyjnych uruchomieniach jedno konczy sie `ValidationError`
  "projekt zmienil sie w trakcie operacji; ponow polecenie", nie utrata
  danych. Filesystem bez atomowego tworzenia katalogu/podmiany pliku
  nie nadaje sie na wspoldzielony projekt; nie stosujemy SQLite ani
  byte-range locks na udziale.
- Pobrane pliki sa w niezmiennym magazynie; przerwanie przed zapisem
  manifestu moze zostawic tam NIEPRZYPIETA wersje, ale nie uszkodzony
  manifest. `project verify`, `status` i `check-updates` nic nie zapisują.

## 8. Kryteria akceptacji i scenariusze na zywo

1. `init` zapisuje pusty czytelny manifest; `add` odrzuca bledne i
   zagniezdzone `--output` przed siecia; dwie osoby moga pobierac do
   wspolnego magazynu, ale nie moga zgubic nawzajem zmian manifestu.
2. Offline na fiksturach z prawdziwych odpowiedzi: NMT PL `--sheet` z
   dwoma kampaniami; `download` przypina konkretna wersje, kolejne
   pobranie innego projektu nie zmienia pinu; `verify` wykrywa zmiane
   jednego bajtu i podmieniony sidecar.
3. `--country auto` PL+CZ, LAZ (wiele kafli), BDOT10k (wiele powiatow),
   SoilGrids, CORINE podglad i HSG (wynik + wejscia): wszystkie zwrocone
   wersje trafiaja do jednego zadania; porazka czesci nie ukrywa sukcesow,
   ponowienie nie nadpisuje przypiec.
4. Raport `check-updates` odroznia od przypietej wersji: nowe loty, zmiane
   wydania/ETag, brak sygnalu, awarie; nie pobiera danych i nie zmienia
   manifestu, rowniez gdy magazyn ma juz nowsza lokalna wersje.
5. `project availability` dla obszaru PL daje kombinacje pelnych arkuszy
   jak `elevation availability`, a `project download` nadal pobiera tylko
   zadany wariant i nie myli dostepnosci ze swiezoscia.
6. `update --name` zmienia tylko wskazane zadanie, `--force` dla toru
   `none` porownuje SHA; brak zmiany bajtow nie zmienia pinu. `verify`
   przed i po przeprowadzce magazynu z zachowaniem sidecarow przechodzi.
7. W planach A-E kazda nowa grupa i produkt sa objete bez specjalnego
   skanera katalogu: z publicznego wyniku `VersionedFile` oraz sidecara;
   raport `availability` tylko tam, gdzie grupa udostepnia API sondy.

**Live przed wydaniem:** na malej jednostce GUGiK utworz projekt i jawny
magazyn poza repo (`project init ... --output <katalog-danych>`), dodaj
NMT PL, pobierz, sprawdz `verify` i `check-updates`; ten sam magazyn
wykorzystaj z drugim projektem bez zmiany pinu pierwszego. Dla malego
bbox sprawdz `project availability` i porownaj z bezposrednim `elevation
availability`. Dla jednego produktu CZ/SoilGrids z dostepnym sygnalem
sprawdz odczyt bez pobierania danych; dla `none` komunikat o braku
sygnalu, nie wymuszaj duzego pobrania. Zweryfikuj sumy po skopiowaniu
magazynu poza repo; zadnych danych w repo ani w `/tmp`, CLMS bez
credentials pomijamy. Raport live podaje dokladne komendy, wynik i
ograniczenia sygnalow (bez tajnej sciezki danych).
