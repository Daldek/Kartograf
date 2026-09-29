# L6 — inne granice (PL-SK, PL-UA, PL-BY, PL-LT, PL-RU) — raport z testow na zywych danych GUGiK

Data: 2026-09-29. Galaz `develop`, HEAD 6985765 (repo TYLKO DO ODCZYTU — zero zmian w
kodzie/testach/dokumentacji, `git status` czysty przez cala sesje). Katalog roboczy:
`/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L6-inne-granice/`
(gitignored). Laczny rozmiar pobranych danych: **120 MB** (budzet <= ~3 GB, `--workers 2`
przez caly czas).

## Zakres

Po jednym malym bboxie (4 arkusze 1:10000 kazdy, w docelowym przedziale 2-6) na kazdej
z 5 granic spoza rejestru krajow Kartografu (SK, UA, BY, LT, RU — `sources/registry.py`
zna wylacznie `PL` i `CZ`). Wspolrzedne przejsc granicznych zweryfikowane WebSearch tam,
gdzie moja pierwsza probka byla niepewna (PL-LT, PL-RU) — patrz "Bledy metodologiczne
po drodze" nizej; dla PL-SK/PL-UA/PL-BY pierwsza probka trafila we wlasciwe miejsce.

| Granica | bbox (EPSG:4326) | Rozdzielczosc | Arkusze 1:10000 |
|---|---|---|---|
| PL-SK Lysa Polana (Tatry) | 20.078,49.222,20.103,49.240 | 5 m | M-34-101-A-c-2-{1,2,3,4} |
| PL-UA Medyka | 22.985,49.802,23.010,49.818 | 5 m | M-34-82-D-b-2-{2,4}, M-34-83-C-a-1-{1,3} |
| PL-BY Terespol | 23.605,52.068,23.630,52.084 | 5 m | N-34-144-C-{a-4-4,b-3-3,c-2-2,d-1-1} |
| PL-LT Budzisko (koryg.) | 23.108,54.301,23.132,54.317 | **1 m** (5 m: brak pokrycia regionalnie, patrz nizej) | N-34-71-A-a-2-{2,4}, N-34-71-A-b-1-{1,3} |
| PL-RU Mierzeja Wislana / Piaski (+ woda) | 19.588,54.428,19.618,54.448 | 5 m | N-34-52-C-a-4-{1,2,3,4} |

Kazda granica: (a) `--country auto` bez `--target-crs` (tryb listy arkuszy), (b)
`--country auto --target-crs EPSG:2180` (wycinek). Dobor bboxow zweryfikowany OFFLINE
przed jakimkolwiek zapytaniem sieciowym: `find_sheets_for_bbox` (czysta matematyka) na
liczbe arkuszy (2-6) i `_countries_for_bbox` (rowniez czysta matematyka wobec
`CountryProfile.extent_wgs84`) na to, ze auto-dispatch da wylacznie `('PL',)` — zaden
z 5 bboxow nie przecina prostokata CZ (12,09-18,86°E / 48,55-51,06°N), wiec CUZK mial
zerowa szanse zostac odpytany (potwierdzone tez empirycznie, patrz checklista nizej).

## Wyniki per scenariusz

### PL-SK Lysa Polana — PASS (z wazna uwaga architektoniczna)

- **Lista arkuszy** (`log-pl-sk-list.std{out,err}`): exit **0**. Wszystkie 4 arkusze
  pobrane poprawnie — GUGiK publikuje je mimo ze granica przebiega przez ich srodek.
  Nodata WEWNATRZ arkuszy (nie `missing_sheets`, bo zaden arkusz nie jest w calosci
  bez pokrycia): `M-34-101-A-c-2-1`=3,0%, `-2-3`=3,5% (zachodnie, wewnatrz PL — to
  zwykly szum tla), `-2-2`=71,1%, `-2-4`=81,6% (wschodnie, w strone Slowacji;
  kwadranty prawe = 100% nodata). Polozenie jednoznacznie po stronie slowackiej.
- **Wycinek `--target-crs EPSG:2180`** (`log-pl-sk-cutout.std{out,err}`): exit **0**,
  **brak** `extra.missing_sheets` (bo brak jest wewnatrz-arkuszowy, nie
  per-arkuszowy) — sidecar nie niesie zadnego sladu, ze wycinek dotyka granicy.
  Realny plik: `2,87%` nodata, skoncentrowane w rogu NE (kolumny 342-369/370,
  wiersze 0-254/406) — geometrycznie spojne z pozycja Slowacji.
- Dowod: `data/pl-sk/nmt/pl_1992_5m_evrf2007/.../*.asc` (4 pliki + sidecary),
  `data/pl-sk/nmt/pl_1992_5m_evrf2007/bbox/578443.8777_151057.6907_580292.2134_153084.3226.tif(.meta.json)`.

### PL-UA Medyka — PASS (R5 poprawny; ujawnia BUG-1, patrz "Bledy")

- **Lista arkuszy** (`log-pl-ua-list.std{out,err}`): exit **1**. Na dysku tylko 2/4
  arkuszy (`M-34-82-D-b-2-2`, `-2-4`); `M-34-83-C-a-1-1` i `-1-3` NIE maja pokrycia
  (zweryfikowane tez niezaleznie pojedynczym pobraniem `-1-3`, `log-pl-ua-verify-sheet.*`
  — ten sam `NoCoverageError`). Stderr wymienia **tylko jeden** z dwoch brakujacych
  arkuszy (`-1-1`) — patrz BUG-1.
- **Wycinek** (`log-pl-ua-cutout.std{out,err}`): exit **0**,
  `Warning: GUGiK nie ma danych dla 2 arkuszy wycinka (M-34-83-C-a-1-1, M-34-83-C-a-1-3)`
  — tym razem OBA poprawnie wymienione (kontrast z lista arkuszy, patrz BUG-1).
  Wynikowy plik: **100% nodata** — sprawdzone niezaleznie (`rasterio.merge.merge` na
  2 udanych arkuszach przycietych do tego samego bboxa: rowniez 0 pikseli z danymi),
  bo maly bbox padl dokladnie w naroznik arkuszy `M-34-82-D-b-2-*`, ktory sam GUGiK
  juz oznaczyl jako nodata (71-100% nodata w tych arkuszach, kwadrant SE). Nie blad —
  potwierdza, ze crop na siatce arkuszy dziala 1:1 (`transform: null`).
- Dowod: `data/pl-ua/...`, `data/pl-ua-verify/...`.

### PL-BY Terespol — PASS (R5 poprawny; ponownie BUG-1, mocniej)

- **Lista arkuszy** (`log-pl-by-list.std{out,err}`): exit **1**. Na dysku tylko 1/4
  (`N-34-144-C-a-4-4`); 3 arkusze bez pokrycia, stderr wymienia **tylko jeden**
  (`-b-3-3`) z trzech.
- **Wycinek** (`log-pl-by-cutout.std{out,err}`): exit **0**,
  `Warning: ... dla 3 arkuszy wycinka (N-34-144-C-b-3-3, N-34-144-C-c-2-2, N-34-144-C-d-1-1)`
  — wszystkie 3 poprawnie wymienione. Wynik: 94,4% nodata, realne dane tylko w
  kwadrancie NW (16,5%) — spojne z 1 na 4 udanymi arkuszami.
- Dowod: `data/pl-by/...`.

### PL-LT Budzisko — UWAGA (lista: PASS; wycinek: FAIL dwukrotnie, ale poprawnie —
  zywa niestabilnosc WMS, nie blad Kartografu)

- Pierwsza probka (23.180,54.348,23.205,54.364 wg mojego wstepnego szacowania
  polozenia przejscia) dala **0/4** arkuszy w ogole, przy 5 m I przy 1 m — zobacz
  "Bledy metodologiczne po drodze". WebSearch skorygowal wspolrzedne przejscia
  Budzisko-Kalvarija na 54°18'30"N 23°07'10"E; nowy bbox (23.108,54.301,23.132,54.317)
  dal sensowny wynik mieszany.
- **5 m nie ma pokrycia w calym tym rejonie** (potwierdzone kontrolnym pojedynczym
  pobraniem punktu ok. 15 km w gleb Polski, `N-34-71-A-a-3-3`, Sejny —
  `log-pl-lt-probe.*`: `NoCoverageError` przy 5 m), wiec test przeprowadzony na
  **1 m** (kontrolny punkt: `log-pl-lt-probe-1m.*` — 1 m dziala, plik 36 MB).
- **Lista arkuszy** (`log-pl-lt2-list.*`, powtorzone `log-pl-lt2-list-retry.*` po
  przejsciowych bledach sieci): exit **1** stabilnie w obu probach. Na dysku 2/4
  (`N-34-71-A-b-1-1`, `-1-3`, oba ~10,3% nodata rownomiernie — tlo, NIE granica);
  `N-34-71-A-a-2-2` i `-2-4` bez pokrycia (Litwa). Stderr znow tylko 1 z 2.
- **Wycinek** (`log-pl-lt2-cutout.*` i powtorka `log-pl-lt2-cutout-retry.*`): exit
  **1** w OBU probach — ale z DOBREGO powodu: `N-34-71-A-a-2-4` to czysty
  `NoCoverageError` (nodata, jak oczekiwano), ale `N-34-71-A-a-2-2` dwukrotnie trafil
  na przejsciowy `ConnectionResetError`/`RemoteDisconnected` akurat na najnowszej
  warstwie `SkorowidzeNMT2026`, co GUGiK-provider poprawnie klasyfikuje jako
  **"brak pokrycia niepewny"** (`DownloadError`, NIE `NoCoverageError` —
  `kartograf/providers/pl/gugik.py:632-641`) — a taki blad **NIE** jest dla R5
  "brakiem danych": `_download_pl_cutout` konczy caly wycinek kodem 1,
  `Error: 1 z 4 arkuszy nie pobrano (blad pobrania, nie brak danych):
  N-34-71-A-a-2-2 — wycinek nie powstal; ponow pobranie`, **zaden** plik `.tif` nie
  powstaje (sprawdzone: `find data/pl-lt2 -path "*bbox*"` puste po obu probach —
  brak polfabrykatu). To jest DOKLADNIE zamierzone zachowanie z docstringa
  `NoCoverageError` (`kartograf/exceptions.py:73-82`) zaobserwowane na zywo pod
  prawdziwa niestabilnoscia sieci — czysty PASS dla logiki R5, ale scenariusz
  "PL-LT wycinek: sukces z nodata" pozostaje niepotwierdzony w tej sesji (budzet
  "odczekaj i ponow raz" z LIVE-COMMON wykorzystany — 2 proby, obie ten sam wynik).
- Dowod: `data/pl-lt/` (pierwsza, bledna probka — 0 plikow, zachowana jako dowod
  regionalnego braku 5 m), `data/pl-lt-probe-inland/` (kontrola 1 m/5 m w Sejnach),
  `data/pl-lt2/` (docelowa probka).

### PL-RU Mierzeja Wislana / Piaski (z woda) — PASS

- Wspolrzedne przejscia (parking przy przystani w Piaskach, granica lądowa konczy sie
  po 850 m i biegnie dalej przez wode Zalewu Wislanego/Zatoki Gdanskiej) potwierdzone
  WebSearch: 54.438223, 19.602655 — moja pierwsza probka (dalej na poludnie) NIE
  zostala uzyta do pobrania, poprawiona przed pierwszym zywym zapytaniem.
- **Lista arkuszy** (`log-pl-ru-list.*`): exit **1**. 3/4 arkusze na dysku
  (`-a-4-2/-4-3/-4-4`), tylko `N-34-52-C-a-4-1` bez pokrycia — tu akurat lista jest
  1:1 poprawna (tylko jeden brak, wiec nie ma czego zgubic — kontrastuje z BUG-1
  na innych granicach, gdzie bylo >=2 brakow naraz).
  Nodata w udanych arkuszach: `-4-2`=53,8% (kwadrant NW=100%, w strone
  wody/Rosji), `-4-3`=21,9% (kwadrant NW podwyzszony), `-4-4`=1,6% (tlo) — spojna
  gradacja z polnocy (woda+granica) na poludnie (ladem, w gleb Polski).
- **Wycinek** (`log-pl-ru-cutout.*`): exit **0**,
  `Warning: ... dla 1 arkuszy wycinka (N-34-52-C-a-4-1)`. Wynik: 22,55% nodata,
  skoncentrowane w kwadrancie NW (77,8%) — spojne z polozeniem wody/granicy na
  polnocy.
- Dowod: `data/pl-ru/...`.

## Bledy

### BUG-1 — tryb listy arkuszy (bez `--target-crs`) gubi wszystkie oprocz PIERWSZEJ
  rownoleglej porazki arkusza

**Reprodukcja:** `kartograf download --bbox 23.605,52.068,23.630,52.084 --bbox-crs
EPSG:4326 --country auto --resolution 5m --workers 2 -o <dir>` (PL-BY Terespol; ten
sam ksztalt na PL-UA i PL-LT). Oczekiwane: stderr informuje o WSZYSTKICH arkuszach
bez pokrycia (jak w trybie wycinka). Rzeczywiste: exit 1, ale stderr wymienia
**tylko jeden** arkusz (`N-34-144-C-b-3-3`), mimo ze na dysku brakuje TRZECH
(`-b-3-3`, `-c-2-2`, `-d-1-1` — zweryfikowane przez `find data/pl-by -name "*.asc"`,
tylko 1 plik). Powtorzone identycznie na PL-UA (2 braki, 1 zgloszony) i PL-LT
(2 braki, 1 zgloszony) — ksztalt identyczny za kazdym razem.

**Hipoteza (plik:linia):** `kartograf/cli/download_cmd.py:894-907` — galaz
rownolegla `_download_godlo_list` (uzywana gdy `max_workers > 1` i zaden godlo nie
rozwija sie hierarchicznie, czyli dokladnie przypadek bbox 1:10000).
`for future in concurrent.futures.as_completed(...): ... except (DownloadError,
ValidationError): raise` (linie 898-905) podnosi wyjatek na PIERWSZYM napotkanym
niepowodzeniu i konczy petle — `ThreadPoolExecutor.__exit__` czeka az wszystkie
watki dokoncza (wiec pliki DLA UDANYCH arkuszy sa zapisane poprawnie — nie ma utraty
danych), ale wyjatki z pozostalych, rowniez nieudanych futures nigdzie nie trafiaja:
nie sa zbierane, nie sa drukowane, nie wchodza do `failed_sheets`. Kontrast: galaz
sekwencyjna/hierarchiczna tej samej funkcji (linie 847-873) zbiera wszystkie porazki
do listy `failed` i drukuje je wszystkie przez `_report_failed_sheets` (linie
910-917); `run_pl_cutout` (tor `--target-crs`, uzywany w `_download_pl_cutout`,
linie 948-1059) rowniez poprawnie agreguje wszystkie braki do `missing_sheets`
(potwierdzone na zywo: PL-BY 3/3, PL-UA 2/2 poprawnie wymienione w Warning).
Naprawa najpewniej wymaga zbierania `(godlo, exception)` z KAZDEGO future w petli
`as_completed` zamiast `raise` na pierwszym, analogicznie do galezi sekwencyjnej.

**Dotkniete:** wylacznie tryb bbox/geometry BEZ `--target-crs`, z arkuszami
1:10000 (a wiec normalny maly-bbox use case), `--workers` > 1 (domyslne 4, w tej
sesji 2). Prawdopodobnie NIE dotyczy godel pojedynczych/hierarchicznych (galaz
sekwencyjna) ani trybu `--target-crs` (wlasny, poprawny mechanizm agregacji).

**Waga:** umiarkowana — kod wyjscia (1) i integralnosc danych (pliki nieudanych
arkuszy po prostu nie istnieja, zadnej korupcji) sa poprawne; problem to WYLACZNIE
niedoszacowana diagnostyka na stderr. Dla uzytkownika pogranicza: latwo pomyslec
"jeden arkusz bez danych" podczas gdy w rzeczywistosci jest ich wiecej — trzeba
recznie porownac zadana liste arkuszy z zawartoscia `data/`.

**Wariant ostrzejszy (BUG-1b, zaobserwowany posrednio na PL-LT):** to nie tylko
zliczanie — moze zgubic INNY GATUNEK bledu. Na PL-LT w trybie wycinka (ktory NIE ma
tego problemu — wlasna, poprawna agregacja) zlapalem live dwa rozne typy porazki w
jednym zadaniu: czysty `NoCoverageError` (`N-34-71-A-a-2-4`) obok przejsciowego
`DownloadError` "brak pokrycia niepewny" (`N-34-71-A-a-2-2`, patrz sekcja PL-LT
wyzej). W trybie LISTY te dwa typy trafiaja do tej samej rownoleglej petli
`as_completed` — ktorykolwiek future dojrzeje pierwszy, ten wygrywa i jedyny trafia
na stderr. Nie zdolalem wymusic live akurat tej kolejnosci (bledy sieciowe sa
niedeterministyczne), ale kod na to pozwala: gdyby "niepewny" (wart ponowienia)
przegral wyscig z czystym "brak danych" (nie wart ponowienia), uzytkownik zobaczy
tylko to drugie i straci sygnal "sprobuj jeszcze raz" — a to rozroznienie jest
dokladnie tym, co reszta kodu (`gugik.py:542-649`, `exceptions.py:73-82`) celowo
stara sie zachowac.

## Bledy metodologiczne po drodze (nie blad Kartografu — notatka do przyszlych testow)

Moje wstepne (z pamieci, bez weryfikacji) wspolrzedne przejscia Budzisko-Kalvarija
(PL-LT) byly przesuniete o ok. 5 km na polnocny-wschod od realnego przejscia —
skutek: pierwszy bbox dal 0/4 arkuszy (i przy 5 m, i przy 1 m), co bez dodatkowej
kontroli latwo bledne odczytac jako "Kartograf nie dziela dobrze tej granicy",
podczas gdy w rzeczywistosci caly bbox lezal po litewskiej stronie. WebSearch
(`54°18'30"N 23°07'10"E`) naprowadzil na poprawna lokalizacje, ktora dala oczekiwany
mieszany wynik. Podobnie dla PL-RU: moja pierwsza probka (dalej na poludnie od
Piask) nie zostala w ogole uzyta do zywego zapytania — WebSearch dal wspolrzedne
(54.438223, 19.602655) przed pierwszym pobraniem. Wniosek dla przyszlych testow
pogranicza: warto zweryfikowac wspolrzedne przejscia PRZED zuzyciem live-budzetu,
zwlaszcza dla mniej oczywistych granic (Tatry, Mierzeja) gdzie linia graniczna nie
jest prosta.

Osobno: w tym samym rejonie (Sejny/Suwalszczyzna) 5 m NMT nie ma pokrycia w ogole
(potwierdzone punktem kontrolnym ~15 km w gleb Polski) — to pokrywa sie z
udokumentowanym w CLAUDE.md/MEMORY faktem "pokrycie 1 m i 5 m sie nie pokrywa", ale
warto to explicite odnotowac przy tej granicy: "brak danych" blisko granicy PL-LT
przy 5 m NIE mozna od razu przypisac granicy bez kontroli inland.

## Zachowanie do udokumentowania

1. **Nodata z powodu granicy ma DWA ksztalty, a tylko jeden jest widoczny w
   metadanych.** Gdy maly bbox przecina realna granice PL (nie prostokatna
   obwiednie kraju), GUGiK albo (a) w ogole nie publikuje arkusza —
   `NoCoverageError` -> `missing_sheets` + `Warning:` w trybie wycinka, w pelni
   udokumentowane i dziala poprawnie (PL-UA, PL-BY, PL-RU, czesciowo PL-LT); albo
   (b) publikuje arkusz normalnie, ale z nodata JUZ wewnatrz pliku po stronie
   obcej (PL-SK: wszystkie 4 arkusze "sukces", 0 wpisow w `missing_sheets`, a mimo
   to do 81,6% powierzchni pojedynczego arkusza to nodata). (b) jest niewidoczne
   na poziomie sidecara/CLI — trzeba otworzyc raster. Warto dopisac to explicite
   przy R5/ADR-027 w ARCHITECTURE.md 4.3 albo CLAUDE.md "Ograniczenia", bo dzisiejszy
   opis R5 ("arkusz bez danych GUGiK = nodata + Warning + missing_sheets") sugeruje,
   ze `missing_sheets` jest pelnym obrazem nodata przy granicy — nie jest.
2. **`--country auto` na tych 5 granicach zachowuje sie jak niejawne `--country
   pl`, bez zadnego komunikatu.** `_countries_for_bbox` zna tylko PL/CZ
   (`sources/registry.py`), wiec dla SK/UA/BY/LT/RU zawsze wraca `('PL',)` —
   jeden kraj w `results`, warunek `len(results) > 1` w `_dispatch_area`
   (`download_cmd.py:534`) nigdy nie trafia, wiec nie ma ani `Info:`, ani
   `Warning:` o rozstrzygnieciu kraju (w odroznieniu od pogranicza PL-CZ, gdzie
   uzytkownik dostaje jawny komunikat). Zachowanie jest poprawne (nie ma czego
   sygnalizowac — nie ma dwoch kandydatow), ale dokumentacja opisuje dzis `auto`
   prawie wylacznie w kontekscie PL-CZ; warto dopisac zdanie, ze na pozostalych
   granicach `auto` == `pl`, cicho.
3. **Rozne kody wyjscia dla identycznego braku pokrycia miedzy trybami — celowe i
   jednolite na wszystkich 5 granicach, ale warte jednego zdania w komunikacie
   bledu.** Tryb listy: KAZDY brakujacy arkusz = `Error:` + exit 1 (nawet gdy
   3 z 4 sie udalo, jak PL-RU). Tryb wycinka: te same braki = `Warning:` + exit 0
   (R5). Sprawdzone identycznie na wszystkich 5 granicach — zero rozbieznosci
   miedzy granicami, to czysto tryb decyduje. Z perspektywy uzytkownika bez
   znajomosci ADR-027 kontrast "Error/exit 1" kontra "Warning/exit 0" dla tego
   samego geograficznie zadania moze wygladac jak niespojnosc silnika, a nie
   swiadomy kontrakt — jedno zdanie w komunikacie bledu trybu listy
   ("dla czesciowego pokrycia rozwaz --target-crs") mogloby to zamknac.
4. **Zywa niestabilnosc WMS GUGiK w tej sesji** (kilkukrotne `Connection
   aborted`/`ConnectionResetError`/`RemoteDisconnected`, raz nieudany
   `GetCapabilities` z fallbackiem na `WMS_LAYERS` z kodu) — zgodnie z
   LIVE-COMMON ("kilku agentow rownolegle na tych samych uslugach"). System
   poprawnie odroznial to od faktycznego braku pokrycia (`transport_errors`
   w `gugik.py`) we WSZYSTKICH przypadkach, ktore udalo sie zaobserwowac — jedyny
   koszt to PL-LT wycinek, ktory nie zdazyl "przebic sie" w ramach budzetu
   "ponow raz" z LIVE-COMMON.

## Odpowiedzi na pozycje checklisty (z briefu zadania)

- **Arkusze po stronie obcej w `extra.missing_sheets` + `Warning:` (wycinek):**
  tak, dziala poprawnie na PL-UA (2), PL-BY (3), PL-RU (1); PL-LT nie zdolal
  dokonczyc live (patrz wyzej, powod: zywa niestabilnosc sieci, nie logika).
  PL-SK to swiadomy wyjatek — patrz punkt 1 w "Zachowanie do udokumentowania".
- **Polozenie nodata w rastrze:** sprawdzone rasterio (nodata_count + rozklad po
  kwadrantach) na kazdej granicy — zawsze skoncentrowane po stronie sasiada (a na
  PL-RU takze nad woda), geometrycznie spojne z kierunkiem granicy w kazdym
  przypadku.
- **Kod wyjscia i komunikaty w trybie listy arkuszy:** exit 0 tylko gdy WSZYSTKIE
  arkusze OK (PL-SK); exit 1 gdy cokolwiek brakuje (PL-UA/BY/LT/RU) — ale stderr
  **niedoszacowuje** liczbe/tozsamosc brakow przy >=2 rownoczesnych porazkach
  (BUG-1/BUG-1b powyzej).
- **Czy nic nie idzie do CUZK:** potwierdzone podwojnie — (1) statycznie,
  `_countries_for_bbox` zwraca kody wylacznie z `all_countries()` (PL, CZ), zaden
  z 5 bboxow nie przecina prostokata CZ; (2) empirycznie, `grep` po wszystkich 14
  logach zywych polecen (stdout+stderr) na `cuzk|arcgis|dmr5g|dmr4g|exportImage|
  Krovak|EPSG:5514|EPSG:3045` — zero trafien; zaden segment `cz_*` nie powstal
  nigdzie w `data/`.
- **Czy wynik/komunikaty sa zrozumiale:** w wiekszosci tak — komunikat R5
  (`Warning: GUGiK nie ma danych dla N arkuszy wycinka (...) — w tych miejscach
  wycinek ma nodata (lista w sidecarze: extra.missing_sheets)`) jest jasny i
  wskazuje gdzie szukac pelnej listy; rozroznienie "brak danych" kontra "blad
  pobrania, nie brak danych — ponow pobranie" (zobaczone live na PL-LT) jest
  dobrze zaprojektowane i faktycznie uzyteczne. Najwiekszy minus to BUG-1: przy
  wielu rownoczesnych brakach w trybie listy user dostaje wrazenie "jeden arkusz
  bez danych", a moze ich byc kilka.
- **Porownanie miedzy granicami — czy jednolite:** tak, w pelni jednolite.
  `_countries_for_bbox` -> `('PL',)` na kazdej z 5 granic; tryb listy: exit
  zalezny wylacznie od "czy cokolwiek nie wyszlo"; tryb wycinka: R5 identycznie
  zastosowany wszedzie, gdzie udalo sie dokonczyc pobranie. Jedyne roznice miedzy
  granicami to geografia GUGiK (ktory arkusz ma pelne/czesciowe/zerowe pokrycie) i
  zywa kondycja sieci w danym momencie (PL-LT) — zero roznic wynikajacych z ktorego
  kraju-sasiada dotyczy zadanie (co jest oczekiwane: kod nie zna SK/UA/BY/LT/RU
  z nazwy, traktuje je identycznie jako "poza rejestrem").

## Surowe artefakty

Wszystko w `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L6-inne-granice/`:

- `probe.py` — offline sanity (sheet count + `_countries_for_bbox`) przed kazdym
  live zapytaniem.
- `check_nodata.py` — rasterio: procent/rozklad nodata po kwadrantach dla
  dowolnych plikow ASC/TIF podanych w argv.
- `log-pl-sk-{list,cutout}.std{out,err}`
- `log-pl-ua-{list,cutout}.std{out,err}`, `log-pl-ua-verify-sheet.std{out,err}`
  (niezalezna weryfikacja drugiego brakujacego arkusza)
- `log-pl-by-{list,cutout}.std{out,err}`
- `log-pl-lt-{list,list-1m,probe,probe-1m}.std{out,err}` (pierwsza, bledna
  probka wspolrzednych + kontrola inland), `log-pl-lt2-{list,list-retry,cutout,
  cutout-retry}.std{out,err}` (docelowa probka, po korekcie WebSearch)
- `log-pl-ru-{list,cutout}.std{out,err}`
- `data/pl-sk/`, `data/pl-ua/`, `data/pl-ua-verify/`, `data/pl-by/`, `data/pl-lt/`,
  `data/pl-lt-probe-inland/`, `data/pl-lt2/`, `data/pl-ru/` — pelne drzewa
  `nmt/pl_1992_{1m,5m}_evrf2007/...` z plikami `.asc`/`.tif` + sidecary
  `.meta.json` z kazdego udanego pobrania.
