# Research — klaster CLI / wycinek / storage (S2, S3, S5, N4, N5, N8, N9)

Data: 2026-09-29, galaz `develop`, drzewo czyste. Faza: wylacznie research
przyczyn i projekt naprawy — zadnych zmian w `kartograf/`, `tests/`, `docs/`
poza tym raportem. Zero zapytan sieciowych: dowody z kodu (linie wg HEAD),
testow offline, raportow `docs/research/2026-09-29-live-e2e-i-audyt-docs/`
(L1-L7, D1, `hydrograf-uwagi-migracyjne.md`) i lokalnych artefaktow
`e2e-data/2026-09-29-live/` (gitignored). Kazda "reprodukcja offline" nizej
zostala faktycznie uruchomiona w tej sesji (atrapa providera, bez gniazd).

Decyzje wiazace: `decisions.md` — D2 (S2), D3 (S5), D5 (sidecar addytywnie),
D6 (pelny zakres). Interfejs wspolny z klastrem skorowidz
(`manager.py::_write_sidecar`, `sources/sidecar.py`) — sekcja 8.

Skrot wynikow:

| ID | Hipoteza backlogu | Werdykt | Naprawa (jedno zdanie) |
|---|---|---|---|
| S2 | petla sekwencyjna / `raise` w puli | potwierdzona 1:1 (repro offline) | `_download_godlo_list` -> `DownloadManager.download_sheets`; wspolne podsumowanie R5 dla listy i hierarchii godla |
| S3 | ciche przyciecie w `_country_bbox` | potwierdzona (110/38/82 m poszerzenia odtworzone) | `Info:` w `_dispatch_area` (przyciecie per kraj + obszar poza wszystkimi prostokatami); PL: nietkniete krawedzie zostaja dokladne |
| S5 | `merge` przy zrodlach poza siatka | potwierdzona + mechanizm (`win_align`) | off-grid = `GridMismatchError(ValidationError)` PRZED mozaika; warp: kompozycja per arkusz (pytanie otwarte) |
| N4 | skip przed sidecarem; `skipped` bez `missing_sheets` | potwierdzona | skip dopisuje `extra.parent_requests` do istniejacego sidecara; `skipped=True` czyta `extra.missing_sheets` z sidecara |
| N5 | testy live tylko HTTP 200 na martwej warstwie | potwierdzona | nowa klasa testow live: GetCapabilities == `WMS_LAYERS`, R5 na morzu, `LayerNotDefined`, geometria rekordu vs `Parser2000` |
| N8 | `horizontal_crs` z kanalu deskryptora | potwierdzona | `build_metadata(horizontal_crs=)` + `pl_horizontal_crs(path, godlo)` (strefa godla, kontrola x >= 1e6); LAZ: `LazTile.horizontal_crs` |
| N9 | podwojny `estimate_pl_cutout_bytes` | potwierdzona, ale przyczyna kosztu lezy glebiej | cache `Transformer.from_crs` w `core/sheet_parser.py` (8,98 s -> 0,11 s dla 1221 arkuszy) — bez zmiany API |

---

## 1. S2 — tryb listy arkuszy bez tolerancji R5 (D2)

### 1.1 Przyczyna potwierdzona na kodzie

Hipoteza z `PROGRESS.md:1138-1149` potwierdzona w calosci; dodatkowo
potwierdzony wariant BUG-1b z L6 (gubienie sygnalu "niepewny").

**Przeplyw dzis** (`kartograf/cli/download_cmd.py`):

1. `_download_pl_bbox` `:1115` (`find_sheets_for_bbox`) i `_download_pl_geometry`
   `:1761` (`find_sheets_for_geometry`) daja liste godel; oba wolaja
   `_download_godlo_list(manager, godlo_list, skip_existing, on_progress, workers)`
   (`:1151-1153`, `:1813-1815`).
2. `_download_godlo_list` `:861-863`: `expands = any(_expands_to_hierarchy(g))`;
   `if max_workers <= 1 or expands:` -> **petla sekwencyjna** `:868-884`:
   `manager.download_sheet(godlo, ...)` per godlo. Dla arkusza 1:10000
   `download_sheet` (`download/manager.py:335`) wola `self._provider.download`
   BEZ `try` — `NoCoverageError`/`DownloadError` wylatuje i przerywa petle;
   `failed` `:866` zbiera wylacznie `summary.failed` z rozwinietych hierarchii
   (`:879-884`). Zmierzone offline (atrapa providera: `-1` -> `NoCoverageError`,
   `-3` -> `DownloadError`, `-2`/`-4` OK, `--workers 1`): **1 wywolanie providera,
   0 plikow**, stderr `Error: No NMT 5m data available for N-34-130-D-d-2-1`,
   rc 1 — dokladnie L3 B3 / L4 BUG-L4-3.
3. `max_workers > 1` bez rozwiniec -> **pula** `:908-919`: `as_completed`,
   `except (DownloadError, ValidationError): raise` `:918-919` — pierwszy
   wyjatek wg kolejnosci UKONCZENIA przerywa petle; `with ThreadPoolExecutor`
   czeka na reszte futures (pliki powstaja), ale ich wyjatki i sciezki przepadaja
   (`all_paths` nie jest zwracane — wyjatek leci dalej). Zmierzone offline
   (`--workers 2`): 4 wywolania, 2 pliki na dysku, stderr TYLKO
   `No NMT 5m data available for ...-2-1` — `DownloadError` z `-3` (sygnal
   "ponow") **zgubiony** (BUG-1b potwierdzony).
4. `_download_pl_bbox:1159-1161` (`except DownloadError -> "\nError: {e}" -> 1`),
   analogicznie `_download_pl_geometry:1821-1823`; przy `failed_sheets` (tylko
   hierarchie) `:1168-1169` -> 1.
5. `_dispatch_area:540-550`: pod `auto` z sukcesem drugiego kraju komunikat
   budowany WYLACZNIE z kodu wyjscia: `Warning: nie pobrano danych z
   {failed} ...` — falszywy, gdy PL pobral czesc arkuszy (L5 B2, L4 BUG-L4-3).

`DownloadManager` MA juz gotowy tolerancyjny tor: `download_sheets`
(`manager.py:453-490`) -> `_download_hierarchy_sequential`/`_parallel`, ktore
lapia `NoCoverageError` (`:590-605`, `:523-525`) i `DownloadError` (`:607-620`,
`:527-529`) per arkusz, wypelniaja `DownloadResult.failed` + `no_coverage`
(`:83-86`) i NIE rzucaja. Wycinek juz z tego korzysta (`download/cutout.py:591-598`).
Tryb listy po prostu tego nie uzywa — docstring `:857-859` sam nazywa to S2.

### 1.2 Proponowana naprawa (D2)

**Biblioteka — bez zmian kontraktu.** `download_sheet`/`download_sheets`/
`last_result` zostaja jak sa (Hydrograf od 0.7.0 uzywa `download_sheets` +
`last_result.failed`/`no_coverage` — `hydrograf-uwagi-migracyjne.md` B4; nie
polega na kodzie wyjscia CLI ani na wyjatku z petli `download_sheet`). Jedyny
dodatek, addytywny: `DownloadResult.hard_failures` (property) =
`[g for g in failed if g not in no_coverage]` — dzis liczone recznie w
`cutout.py:597` i potrzebne po raz drugi w CLI.

**CLI — `kartograf/cli/download_cmd.py`:**

- `_download_godlo_list` -> jedno wywolanie
  `manager.download_sheets(godlo_list, skip_existing=..., on_progress=...)`
  (rownoleglosc: `max_workers` managera; `expand_sheets` rozwija grubsze godla,
  wiec znika rozroznienie "expands" i zwielokrotnienie watkow). Zwrot:
  `tuple[list[Path], DownloadResult]`. `_expands_to_hierarchy` i
  `_report_failed_sheets` — usunac (martwe).
- Nowy wspolny finisz `_finish_pl_sheets(result: DownloadResult, paths, *,
  output_dir, quiet) -> int` uzywany przez `_download_pl_bbox`,
  `_download_pl_geometry` **i tryb godla z hierarchia** w `cmd_download`
  (`:743-748` + `:782-789` — ta sama semantyka "wiele plikow", te same arkusze
  morskie pod godlem 1:50000 na wybrzezu; patrz pytanie 1.4.a):

  | Wynik | stderr | kod |
  |---|---|---|
  | wszystko `succeeded`/`skipped` | — | 0 |
  | >= 1 plik (succeeded+skipped), reszta `no_coverage` | `Warning: GUGiK nie ma danych dla K z M arkuszy ({do 10 godel}{ ...}) — pominiete (morze, obszar za granica); pobrano N` | 0 |
  | >= 1 `hard_failures` (niezaleznie od reszty) | `Error: K z M arkuszy nie pobrano (blad pobrania, nie brak danych): {PELNA lista} — ponow pobranie` (+ `Warning:` jw., gdy sa tez `no_coverage`) | 1 |
  | 0 plikow, wszystkie `no_coverage` | `Error: GUGiK nie ma danych dla zadnego z M arkuszy obszaru` | 1 |

  Ostatni wiersz to propozycja na pytanie "co gdy WSZYSTKIE bez danych":
  spojnie z wycinkiem (`cutout.py:609-613` -> `ValidationError`, kod 1) i z
  regula D2 "0 gdy >= 1 plik" (zero plikow = nie-zero). Pod `--country auto`
  z sukcesem CZ `_dispatch_area` i tak daje 0 + `Warning:` (ADR-023 pkt 4-5).
- Podsumowanie stdout (nie `-q`): `Downloaded {succeeded} files to {dir}
  ({skipped} already existed)` — dzis `Downloaded N files` liczy pominiete
  (L1 "Drobne UX"). `Found N sheets ...` bez zmian.
- `_dispatch_area:543-549`: przeredagowac komunikat, bo po D2 rc=1 kraju PL
  oznacza "blad pobrania albo zero danych", niekoniecznie brak plikow:
  `Warning: czesc {failed} zadania zakonczyla sie bledem (patrz Error wyzej) —
  pobrano {ok}; kod 0 (prostokatne obwiednie krajow, ADR-023 pkt 4-5)`.
  Alternatywa (bogatszy zwrot workera zamiast `int`) odrzucona — jeden
  komunikat prawdziwy w obu przypadkach wystarcza.
- Efekt uboczny na plus: `download_sheets` wola `on_progress` per arkusz, wiec
  lista 1:10000 z `--workers > 1` dostaje pasek postepu (dzis cisza 14-30 s,
  L1 "Drobne UX").

**Kontrakt dla wolajacych:** CLI: kod 0 z `Warning:` tam, gdzie dotad 1;
kod 1 nadal przy kazdej porazce nie-R5. `download_pl_cutout`/Hydrograf: bez
zmian. Sidecar: bez zmian (arkusze bez danych nie maja pliku ani sidecara;
lista brakujacych w trybie listy zyje tylko w stderr — patrz pytanie 1.4.c).

### 1.3 Testy offline

- `tests/test_cli.py::TestAreaModeHierarchyExitCode` (`:1370-1517`) — mocki
  `download_sheet` z `side_effect` ustawiajacym `last_result` to testy
  implementacji petli; do PRZEPISANIA na `download_sheets` + `last_result`
  (nie re-pinowac petli). Nowe przypadki (failing-before/passing-after), na
  atrapie providera jak w reprodukcji z 1.1 (patch
  `_create_provider_and_storage` + `find_sheets_for_bbox`, prawdziwy
  `DownloadManager` i `FileStorage` w `tmp_path`):
  - `--workers 1`, `[-1 NoCoverage, -2 ok, -3 DownloadError, -4 ok]` -> provider
    wolany 4 razy (dzis 1), 2 pliki, rc 1, stderr wymienia `-3` w `Error:`
    i `-1` w `Warning:`;
  - `--workers 2`, `[-1 NoCoverage, -3 DownloadError, ...]` -> stderr zawiera OBA
    (dzis tylko pierwszy wg wyscigu);
  - tylko `NoCoverage` + >= 1 ok -> rc 0, `Warning:` z lista, brak `Error:`;
  - wszystkie `NoCoverage` -> rc 1, `Error: ... zadnego z M`;
  - `auto` + CZ ok (mock `_cmd_download_cz` -> 0) + PL czesciowo bez danych
    -> rc 0 i BRAK `Warning: nie pobrano danych z PL` (dzis jest — L5 B2).
- `tests/test_pl_cutout.py::test_without_target_crs_behaviour_unchanged`
  (`:898-922`) patchuje `_download_godlo_list` z krotka `(sheets, [])` —
  dostosowac do nowego zwrotu `(paths, DownloadResult)`.
- `tests/test_cli.py::TestCmdDownload` `:654-720` ("4 of 4 sheets failed") —
  jesli hierarchia godla wejdzie pod wspolny finisz (1.4.a), tresc komunikatu
  sie zmieni; te testy pinuja kod wyjscia, nie tresc — zaktualizowac asercje
  tekstu.
- `tests/test_download_manager.py::test_no_coverage_is_subset_of_failed`
  (`:506-512`) — wzorzec atrapy providera do reuzycia; dopisac test property
  `hard_failures` tylko jesli wejdzie (proste, ale to kontrakt publiczny).

### 1.4 Ryzyka i pytania projektowe

- **(a) Czy hierarchia godla (`kartograf download N-34-130-D --scale 1:10000`)
  tez dostaje R5?** D2 mowi o "trybie listy" (bbox/geometry). Opcje: (1) tylko
  bbox/geometry — litera D2, godlo z arkuszem morskim nadal kod 1 ("N of M
  sheets failed"); (2) takze hierarchia godla — ten sam finisz, ta sama
  semantyka "wiele plikow". **Rekomendacja: (2)** — arkusz 1:50000 na wybrzezu
  ma te same arkusze morskie, a dwa rozne kody wyjscia dla tej samej sytuacji
  to pulapka; pojedynczy arkusz 1:10000/PL-2000 bez danych zostaje bledem
  (nic do pobrania = kod 1, jak wiersz 4 tabeli).
- **(b) Status postepu dla arkusza bez danych.** Dzis manager raportuje
  `no_coverage` jako `status="failed"` (`manager.py:602`, `:718`), a pasek
  drukuje `✗` (L3: "oczekiwany stan wyglada jak blad"). Opcje: (1) zostawic;
  (2) nowy status `"no_coverage"` w `DownloadProgress` + ikona `∅`/`-` w CLI.
  **Rekomendacja: (2)**, addytywne (konsument dopasowujacy `"failed"` pominie
  te linie — nieszkodliwe), ale to kontrakt `on_progress` biblioteki — do
  potwierdzenia.
- **(c) Slad listy brakujacych arkuszy poza stderr.** W trybie listy nie ma
  pliku zbiorczego, wiec `Warning:` jest jedynym sladem. Opcje: (1) tylko
  stderr — rekomendacja (brak naturalnego nosnika; sidecar arkusza istnieje
  tylko dla pobranych); (2) manifest zadania `<segment>/requests/<hash>.json`
  — nowy artefakt, poza zakresem fali.
- **(d) Haly `logger.warning("No data for ...")` per arkusz** (`manager.py:594`)
  ida na stderr przez `logging.lastResort` przed jednym `Warning:` (L3, L5 UX).
  Opcje: (1) zostawic (jedyny sygnal dla uzytkownika biblioteki, ktory nie
  czyta `last_result`); (2) zdegradowac do INFO (jak zbiorczy log wycinka
  `cutout.py:617`). **Rekomendacja: (1)** w tej fali; to UX, nie blad.

### 1.5 Zakres

`cli/download_cmd.py` (`_download_godlo_list`, `_download_pl_bbox`,
`_download_pl_geometry`, `cmd_download` tryb hierarchii, `_dispatch_area`),
`download/manager.py` (property `hard_failures`, opcjonalnie status
`no_coverage`), testy `test_cli.py`, `test_pl_cutout.py`, `test_download_manager.py`;
dokumentacja: CLAUDE.md (akapit "Tryb listy arkuszy ... nie ma tolerancji R5"),
README `:230-233`, SCOPE `:396-400`, ARCHITECTURE 4.2, DECISIONS — addendum do
ADR-027 ("R5 obejmuje tryb listy", errata ADR-023 pkt 7), CHANGELOG. Kontrakt
publiczny: CLI (kody wyjscia — zmiana zamierzona), biblioteka addytywnie.

---

## 2. S3 — ciche przyciecie bboxa do prostokata kraju pod `auto`

### 2.1 Przyczyna potwierdzona na kodzie

`_country_bbox` (`cli/download_cmd.py:284-347`): pod `auto` bbox idzie do WGS84
(`_bbox_to_wgs84` `:320`, obwiednia z 4 naroznikow — `core/geometry.py:449-465`),
jest przecinany z `extent_wgs84` kraju (`:322-327`) i **caly** przyciety
prostokat wraca do ukladu zadania (`:340-347`, znowu obwiednia z naroznikow).
Dwa skutki, oba odtworzone offline na bboxie z L3 (Rozewie
`455000,773000,459000,784000` EPSG:2180): (1) czesc na N od 54,90°N znika
(1936,5 m), (2) krawedzie NIETKNIETE przez przyciecie sa poszerzone
o W 110,26 / S 38,19 / E 82,21 m — dokladnie liczby z L3 B5 (poludnik zadania
nie jest linia prosta w EPSG:2180, a obwiednia bierze skrajny naroznik).
`_dispatch_area:515-517` wola to bez slowa; `parent_request` niesie oryginal
(`_build_parent_request:363-367`), ale nazwa pliku i `request.bbox` — czesc
przycieta (wycinek: `prepare_pl_cutout` liczy `coords` z `bbox_target`
`cutout.py:216-224`; CZ: `_cz_download_bbox:1535-1543`). Osinow (L5 B4):
`_country_bbox(BBox(14.03,52.835,14.16,52.85,"EPSG:4326"),"PL",auto=True)` ->
`14.07..14.16` — potwierdzone. Docstring `:294-296` sam nazywa to S3.

Przyciecie jako takie jest zamierzone (ADR-023 pkt 4: CZ nie powinien dostawac
czesci polskiej — mniejszy raster nodata, mniej ruchu; K6 limit pikseli) —
wada jest cichosc i poszerzanie.

### 2.2 Proponowana naprawa

**(a) `Info:` w `_dispatch_area`** (stderr, `-q` nie tlumi — konwencja
`Info:`/`Warning:`). `_country_bbox` zwraca `CountryPart(bbox: BBox,
clipped: tuple[str, ...])` z krawedziami WGS84 faktycznie przycietymi
(`"W"`, `"S"`, `"E"`, `"N"`) — dzis to `BBox`; jedyny wolajacy to
`_dispatch_area:517`. Dwa komunikaty, oba tylko pod `auto`:

1. Per kraj z niepustym `clipped`:
   `Info: --country auto: czesc {code} przycieta do obwiedni kraju
   ({N: 54,90°N}); plik i request.bbox niosa zasieg przyciety, oryginal
   w extra.parent_request.bbox`.
2. Gdy czesc zadania lezy poza WSZYSTKIMI prostokatami krajow z `countries`
   (prawdziwa utrata): `Info: --country auto: obszar {lon1}-{lon2}°E x
   {lat1}-{lat2}°N ({X km / Y % powierzchni}) lezy poza zasiegiem PL/CZ
   i zostal pominiety; caly bbox pobiera jawne --country pl (za granica:
   arkusze bez danych / nodata)`. Obliczenie dokladne i tanie: podzial bboxa
   WGS84 na komorki wszystkimi krawedziami prostokatow (cuts x/y), komorka
   niepokryta przez zaden prostokat = utrata; obwiednia komorek utraconych do
   komunikatu. Nie wystarczy test per krawedz (bbox 13-15°E x 53-55°N: W
   krawedz lezy wewnatrz zakresu lon CZ, ale CZ konczy sie na 51,06°N — test
   krawedziowy nie widzi utraty; podzial na komorki widzi).

**Kiedy:** komunikat 1 zawsze, gdy plik bedzie mial inny zasieg niz zadanie
(takze gdy odcieta czesc jest po prostu w drugim kraju — uzytkownik szuka
pliku po wspolrzednych); komunikat 2 tylko przy realnej utracie. Brak
przyciecia = brak komunikatow (bbox wewnatrz obu prostokatow — dzis wiekszosc
zadan przygranicznych PL-CZ). Jawny `--country` i rozstrzygniecie flagami
PL-only (`auto=False`) — bez zmian, bez przycinania, bez `Info:`.

**(b) Koniec poszerzania nietknietych krawedzi (PL).** Dla PL uklad wyniku ==
uklad zadania (`target = bbox.crs` `:333`), wiec po transformacji przycietego
prostokata krawedzie z `clipped` biora wartosc z transformacji (konserwatywna
na zewnatrz — obwiednia zakrzywionej krawedzi kraju), a pozostale **wartosc
oryginalu 1:1**. Rozewie po zmianie: `(455000, 773000, 459000, 782063.5)`.
Dla CZ czesc jest z definicji w innym ukladzie (`cz_crs`, przypieta
`bbox_to_crs` z probkowaniem krawedzi) — poszerzenie jest tam nieuniknione
i uczciwe (plik nazwany w swoim ukladzie); bez zmian. Odrzucona alternatywa:
przecinanie w ukladzie zadania z obwiednia prostokata kraju w tym ukladzie —
obwiednia rownoleznika 54,9°N w EPSG:2180 na 14,07°E lezy ~11 km dalej na N
niz na 18,4°E (zbieznosc TM), wiec przyciecie bylo by o kilometry za luzne.

**(c) Nazwa pliku i `request.bbox`: zasieg PRZYCIETY (status quo).** Opcje:
(1) przyciety = to, co plik naprawde pokrywa; oryginal w `parent_request`
(juz jest) — **rekomendacja**; (2) nazwa/`request.bbox` z oryginalu — nazwa
klamie o zasiegu, a ten sam plik pod `auto` i `--country pl` mialby te sama
nazwe przy roznej tresci (kolizja cache) — odrzucone; (3) brak przycinania
pod `auto` — CZ dostawalby czesc polska (wiekszy raster nodata, limit K6), PL
odpytywalby skorowidz o arkusze czeskie (4 zapytania GFI na arkusz, S1) —
odrzucone. Nowe pole sidecara nie jest potrzebne (`request.bbox` vs
`parent_request.bbox` juz niesie te informacje) — patrz pytanie 2.4.b.

### 2.3 Testy offline

`tests/test_cli.py::TestAutoSplitBBox` (`:3829-4515`, wzorzec
`test_auto_clips_cz_part_to_country_extent` `:4033-4065` z mockami
`_cmd_download_cz`, `find_sheets_for_bbox`, `DownloadManager`):

- Rozewie (`455000,773000,459000,784000` EPSG:2180, `--country auto`): bbox
  przekazany do PL ma `min_x == 455000`, `min_y == 773000`, `max_x == 459000`
  DOKLADNIE i `max_y < 784000` (dzis: 454889.74/772961.81/459082.21 — failing
  before); stderr zawiera `Info:` z `54,90` i `poza zasiegiem`.
- Osinow (`14.03,52.835,14.16,52.85` EPSG:4326): `Info:` z `14,07`;
  `parent_request.bbox == [14.03, ...]` (bez zmian).
- Bogatynia (`15.0,50.9,15.3,51.2` EPSG:4326, kraje CZ+PL): jeden `Info:` dla
  CZ (`51,06`), ZERO `poza zasiegiem` (odcieta czesc jest w PL); PL bez `Info:`.
- Pas PL-CZ wewnatrz obu prostokatow (`18.4,49.55,18.8,49.75` — istniejacy
  test) -> stderr bez `Info:` (regresja cichosci dla przypadku bez przyciecia).
- Bbox 13-15°E x 53-55°N (utrata w narozniku, oba testy krawedziowe slepe) ->
  `Info:` z utrata; test jednostkowy funkcji podzialu na komorki (czysta
  matematyka, bez CLI).
- `TestAutoSplitGeometry` (`:4516+`): `--geometry` pod `auto` dostaje ten sam
  `part` — jeden test, ze `Info:` pojawia sie takze tam.

### 2.4 Ryzyka i pytania projektowe

- **(a) Poziom komunikatu.** `Info:` (jak rozstrzygniecie flagami PL-only) czy
  `Warning:` dla utraty? Opcje: (1) oba `Info:`; (2) utrata jako `Warning:`.
  **Rekomendacja: (1)** — to zamierzone dzialanie `auto`, nie awaria;
  `Warning:` w `_dispatch_area` zarezerwowane dla porazki kraju.
- **(b) Pole w sidecarze** (`extra.clipped_to_country_extent: true`)? Opcje:
  (1) bez pola — konsument porowna `request.bbox` z `parent_request.bbox`
  (rozne uklady: trzeba transformowac) — **rekomendacja** (D5 tylko addytywnie,
  ale kazde pole to kontrakt); (2) dodac flage. Do potwierdzenia.
- **(c) Poludniowa krawedz przez poludnik osiowy 19°E.** Obwiednia z 4
  naroznikow (`_transform_bbox`) dla rownoleznika przecinajacego 19°E daje
  `min_y` za wysoko o metry (minimum lezy w srodku krawedzi) — istniejace,
  marginalne ograniczenie, nie ruszamy (dotyczy tylko bboxow przycietych na S
  do 49,00°N).

### 2.5 Zakres

`cli/download_cmd.py` (`_country_bbox` -> `CountryPart`, `_dispatch_area`,
nowa funkcja utraty pokrycia), testy `test_cli.py`; docs: CLAUDE.md pkt (4)
"znany blad S3", README `:62-63`, SCOPE `:421-428`, DECISIONS ADR-023 pkt 7
(errata), ARCHITECTURE 4.6, CHANGELOG. Kontrakt publiczny: tylko CLI (nowe
linie `Info:` na stderr; nazwy plikow PL pod `auto` zmienia sie o metry — te
same co pod `--country pl` na nietknietych krawedziach). Kolizja: klaster CZ
(N2 w `_cz_download_bbox`, komunikat `:1643-1644`) edytuje ten sam plik.

---

## 3. S5 — wycinek EPSG:2180 z arkuszy o roznych fazach siatki (D3)

### 3.1 Przyczyna potwierdzona na kodzie i danych

**Dane.** `e2e-data/2026-09-29-live/L1-centrum-produkty/data/nmt/pl_1992_5m_evrf2007/M-34/`
(19 arkuszy 5 m, kampania 2022, rasterio offline): naglowki `xllcenter`
z 2 miejscami po przecinku, fazy `(t.c/5) % 1` = 0,444 / 0,032 / 0,620 /
0,540 / 0,322 / 0,636 / 0,612 / 0,104 / 0,884 / 0,586 / 0,560 / 0,732 /
0,900 / 0,824 / 0,186 / 0,068 / 0,236 / 0,548 / 0,910 — **19 roznych faz**
(kotwiczenie we wlasnym narozniku SW, jak w L1 BUG-L1-7). W tym samym
katalogu `7.123.8.asc` ma naglowek identyczny z `M-34-76-A-a-2-4.asc`
(542560.300/232508.630) — to K4 (godlo PL-2000 -> plik PL-1992), zbiezne z N8.

**Mechanizm.** `_snap_outward` (`transport/mosaic.py:93-139`) wyznacza siatke
WIEKSZOSCI (`Counter(keys).most_common`) i zwraca zrodla spoza niej; wolajacy
`mosaic_and_crop:257-271` tylko **loguje ostrzezenie** i puszcza je do
`merge` (`:324-330`). `rasterio.merge.merge` 1.5.0 (kod zrodlowy przejrzany:
`cw = win_align(cw)` — zaokraglenie offsetow i dlugosci okna DOCELOWEGO,
odczyt zrodla z okna ulamkowego `sw` w `out_shape` okna zaokraglonego) —
czyli przeprobkowanie zrodla do siatki wyniku "przez okno", nie po srodkach
pikseli. Reprodukcja syntetyczna (dwie kafle 1 m, druga przesunieta o -0,3 px
w x): piksel wyniku x=10,5 dostal wartosc z piksela zrodla o srodku 11,2
(0,7 px dalej) zamiast 10,2 (0,3 px — najblizszy), a ostatnia kolumna wyniku
(x=17,5, pokryta przez zrodlo do 19,7) jest **nodata** — 1:1 z L1 BUG-L1-7
(przesuniecie 0,59-0,88 px, prawa kolumna/dolny wiersz nodata, szwy) i L2 S24.
Komunikat `:266-270` ("przepisana najblizszym sasiadem") jest falszywy.
Hipoteza backlogu potwierdzona; dodatkowo: dla warpu (`pinned is not None`)
mozaika posrednia `tmp` (`cutout.py:384-394`) niesie te same znieksztalcenia
PRZED bilinearem, wiec dzisiejszy warp 5514/3045 z takich arkuszy tez jest
zly — wazne dla tresci podpowiedzi z D3 (pytanie 3.4.a).

**Tolerancja porownania faz.** `_GRID_TOL_PX = 1e-6` (`:31`), fazy kubelkowane
`round(p / 1e-6)` (`:81-90`). Szum zmiennoprzecinkowy dla wspolrzednych
~5e5..7e5 m to ~1e-10 m -> 2e-11 px (5 m); realne rozjazdy w plikach GUGiK
sa >= 0,01 m (naglowki z 2-3 miejscami) -> 2e-3 px (5 m) / 1e-2 px (1 m).
1e-6 px lezy 5 rzedow nad szumem i 3 rzedy pod najmniejszym realnym
rozjazdem — zostaje. Jedna korekta: porownywac `|faza - faza_ref| <= tol`
(z owinieciem przez 1), nie rownosc kubelkow — dwa szumy po dwu stronach
granicy kubelka nie moga dac falszywego bledu twardego.

**1 m i `--geometry`.** 84 arkusze 1 m na zywo: jedna faza `k + 0,5` (L2) —
1 m nietkniete. `--geometry` idzie przez ten sam `build_pl_cutout` -> ta sama
regula, bez osobnego kodu.

### 3.2 Proponowana naprawa (D3)

1. **`transport/mosaic.py`:** wydzielic detekcje z `_snap_outward` do
   publicznego `check_source_grid(paths) -> SourceGrid(reference: Affine,
   off_grid: tuple[OffGridSource(path, dx_px, dy_px), ...])` (metadane czytane
   raz — dzis `mosaic_and_crop` juz je czyta po jednym pliku `:203-216`; do
   wspolnego uzytku z `build_pl_cutout` wystarczy, ze `mosaic_and_crop`
   przyjmie gotowe `SourceGrid` albo policzy sam). `mosaic_and_crop(...,
   snap_to_source_grid=True)` przy `off_grid` **rzuca**
   `GridMismatchError(ValidationError)` z atrybutem `off_grid` i komunikatem
   `"{n} z {m} zrodel lezy na innej siatce pikseli niz pozostale (maks.
   przesuniecie {worst:.3f} px): {do 10 nazw}"`. Galaz `logger.warning`
   `:263-271` i akapity docstringa o "najblizszym sasiedzie" `:107-111`,
   `:169-173` — usunac. Jedyny wolajacy ze `snap_to_source_grid=True` to
   `build_pl_cutout` (tor CZ nie uzywa flagi — bez zmian).
2. **`download/cutout.py::build_pl_cutout`:** przed mozaika
   `grid = check_source_grid(sheet_paths)` (obok `_reject_pl2000_sheets`):
   - `pinned is None` (EPSG:2180) i `grid.off_grid` -> `GridMismatchError`
     z podpowiedzia CLI: `"{n} z {m} arkuszy lezy na innej siatce pikseli
     (maks. {worst:.2f} px): {lista} — wycinek EPSG:2180 wymaga wspolnej
     siatki (wartosci 1:1, R1). Zadaj wycinek w ukladzie z pelnym warpem
     (--target-crs EPSG:5514 albo EPSG:3045) albo pobierz obszar jako arkusze
     (bez --target-crs). Arkusze zostaja w cache."` CLI lapie `Exception`
     wokol `run_pl_cutout` (`download_cmd.py:1054-1056`) -> `Error:` + kod 1
     (pod `auto` z sukcesem CZ: 0 + `Warning:`, ADR-023). Blad pada PO
     pobraniu arkuszy (fazy znamy dopiero z plikow) — nie da sie go
     przesunac przed siec; koszt to arkusze w cache, ktore posluza
     natychmiast wycinkowi z warpem.
   - `pinned is not None` (5514/3045) i `grid.off_grid` -> **kompozycja per
     arkusz** (W1, pytanie 3.4.a): `transform/raster.py::warp_to_grid`
     przyjmuje `list[Path]` i wola `reproject` dla kazdego zrodla do TEGO
     SAMEGO pasma docelowego (pierwsze z `init_dest_nodata=True`, kolejne
     `False`; kolejnosc odwrotna do sortowania sciezek, zeby — jak w `merge`
     — pierwsze w sortowaniu wygrywalo w zakladce; do zweryfikowania smoke
     testem przy wdrozeniu, bo GDAL nadpisuje wazne piksele kolejnym zrodlem).
     Kazdy arkusz jest wtedy przeprobkowany RAZ, ze swojej siatki na siatke
     wyniku — bez `merge` i bez pliku `tmp`. Bez `off_grid` — dotychczasowa
     sciezka (mozaika 1:1 + warp, zweryfikowana na zywo bit w bit) bez zmian.
     Sidecar wycinka (addytywnie, D5): `extra.off_grid_sheets = [...]` tylko
     na tej sciezce — konsument widzi, ze szwy powstaly z niezaleznych warpow.
3. Komunikaty/dokumenty z "najblizszym sasiadem" i "znany blad S5" — usunac
   (`mosaic.py`, `cutout.py:335-340`, CLAUDE.md, README `:255`, SCOPE `:63-64`,
   ARCHITECTURE 4.3 krok 5, ADR-027 uzupelnienie 2026-09-29).

**Kontrakt:** `download_pl_cutout`/`run_pl_cutout` rzucaja nowy
`GridMismatchError(ValidationError)` (eksport w `kartograf.exceptions`;
`except ValidationError` Hydrografu dalej dziala; nowy typ pozwala wybrac
programowo inny `target_crs` bez parsowania tekstu). CLI: kod 1 + `Error:`
z podpowiedzia. Sidecar: bez zmian dla 2180; `extra.off_grid_sheets` przy W1.

### 3.3 Testy offline

- `tests/test_transport_mosaic.py::test_snap_uses_majority_grid_and_warns`
  (`:253-269`) pinuje ostrzezenie — **do usuniecia**, zastapic:
  `test_snap_rejects_off_grid_source` (`_write_lattice_tile(..., x0=0.75)` ->
  `pytest.raises(GridMismatchError)`, w komunikacie `odd.tif` i `0.250`),
  `test_snap_tolerates_float_noise` (dwa kafle z `x0=0.0` i `x0=1e-9` -> bez
  bledu, jedna siatka), istniejace `test_snap_copies_source_pixels_exactly`
  i `test_snap_keeps_bbox_already_on_grid` bez zmian.
- `tests/test_pl_cutout.py` (harness `TestDownloadPlBboxCutout._run` `:650-676`
  i `TestLibraryApi` `:1590+`): dwa ASC 5 m o naglowkach jak w L1
  (`xllcorner 535807.22`/`538045.16`, `cellsize 5`) -> `EPSG:2180`:
  `GridMismatchError`, tekst z `--target-crs EPSG:5514`, plik wyniku NIE
  istnieje, `prune_empty_dirs` sprzatnal `bbox/`; przez CLI: rc 1, `Error:`
  z podpowiedzia. Dla W1: te same arkusze o stalych wartosciach 100/200 ->
  `EPSG:5514`: wynik ma oba poziomy, zero nodata wewnatrz obszaru wspolnego
  i brak kolumny nodata na szwie (dzis: kolumna nodata + przesuniecie —
  failing before). Arkusze na jednej fazie -> sciezka bez zmian
  (`test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe` `:959+` zostaje).
- Dane realne w `e2e-data/` sa gitignorowane — testy syntetyczne (rasterio),
  a L1 (`unshare -rn kartograf download --bbox 536000,233000,541000,238000
  --resolution 5m --target-crs EPSG:2180 -o e2e-data/.../L1-centrum-produkty/data`)
  jako smoke bez sieci przy wdrozeniu: oczekiwane `Error:` z lista 18 z 19.

### 3.4 Ryzyka i pytania projektowe

- **(a) Warp z arkuszy o roznych fazach — czy naprawiac w tej fali?** D3 kaze
  podpowiadac "inny --target-crs (pelny warp)", ale dzisiejszy warp z takich
  arkuszy jest tak samo zly (mozaika posrednia przez `merge`). Opcje: (1) W1
  tylko dla zestawow z `off_grid` (rekomendacja: sciezka zweryfikowana na
  zywo zostaje, nowa sciezka tylko tam, gdzie dzis jest blad); (2) W1 zawsze
  dla warpu — prostszy kod (bez `tmp`, kompresji, BIGTIFF), ale zmienia wynik
  na szwach (bilinear bez sasiada zza szwu) w torze potwierdzonym bit w bit;
  (3) bez W1 — wtedy podpowiedz z D3 musi brzmiec "wycinek z takich arkuszy
  w innym ukladzie to etap 2" (pobierz jako arkusze). **Rekomendacja: (1)**;
  jesli uzytkownik odrzuci W1 — (3) z poprawiona podpowiedzia.
- **(b) Typ wyjatku.** (1) `ValidationError` z tekstem; (2) `GridMismatchError
  (ValidationError)` z `.off_grid` — **rekomendacja (2)** (Hydrograf wybiera
  programowo warp; addytywne). Nazwa do akceptacji.
- **(c) Zakladka arkuszy 5 m w W1** (~1 wiersz/kolumna): pierwsze w sortowaniu
  wygrywa jak dotad; wartosci z dwu kampanii roznia sie do 9 cm (L2) — bez
  zmiany polityki.
- **(d) Tolerancja.** 1e-6 px zostaje (uzasadnienie 3.1); alternatywa 1e-3 px
  (1 mm przy 1 m) tez bezpieczna — bez znaczenia na realnych danych.

### 3.5 Zakres

`transport/mosaic.py` (`check_source_grid`, `GridMismatchError`, usuniecie
ostrzezenia), `exceptions.py` (nowy typ), `download/cutout.py`
(`build_pl_cutout`, sidecar `extra.off_grid_sheets`), `transform/raster.py`
(`warp_to_grid(list[Path])` — tor PL, nie lustro CZ), testy
`test_transport_mosaic.py`, `test_pl_cutout.py`; docs: CLAUDE.md, README,
SCOPE, ARCHITECTURE 4.3 krok 5-6, ADR-027 (addendum D3), CHANGELOG. Kontrakt
publiczny: nowy wyjatek (podklasa), CLI kod 1 tam, gdzie dotad 0 z zla
trescia.

---

## 4. N4 — `parent_request` arkuszy pominietych; `missing_sheets` przy pominietym wycinku

### 4.1 Przyczyna potwierdzona na kodzie

- Arkusze: trzy sciezki skip wracaja PRZED `_write_sidecar` —
  `download_sheet` `manager.py:329-331`, `_download_single_sheet_task`
  `:516-517`, `_download_hierarchy_sequential` `:548-562`. Sidecar zostaje
  stary (albo nie ma go wcale — cache 0.6.1, `hydrograf-uwagi-migracyjne.md`
  A1). Kontrakt ARCHITECTURE 3.4 ("klucz grupowania plikow jednego zadania")
  jest przez to niespelnialny dla arkuszy z cache (L1 BUG-L1-6: 4 z 9).
- Wycinek: `run_pl_cutout` `cutout.py:567-568` i `download_pl_cutout`
  `:713-714` zwracaja `PlCutoutResult(path, skipped=True)` — `missing_sheets`
  domyslnie `()` (`:113`), choc sidecar ma `extra.missing_sheets`
  (`write_pl_cutout_sidecar:435-437`); CLI `_download_pl_cutout:1004-1007`
  pomija wycinek jeszcze przed biblioteka i nie drukuje `Warning:` (D1 ID 5).
  Test `test_skip_existing_writes_no_sidecar` (`test_download_manager.py:937`)
  pinuje, ze skip NIE TWORZY sidecara — zostaje w mocy.

### 4.2 Proponowana naprawa

**(a) Arkusze — dopisanie rodzica do ISTNIEJACEGO sidecara (addytywnie, D5).**
Nowa metoda `DownloadManager._note_reuse(target_path)` wolana w trzech
sciezkach skip: jesli `self._sidecar_extra` ma `parent_request` i obok pliku
JEST `.meta.json`: wczytaj, jesli `extra.parent_request != nowy` i nowy nie
jest jeszcze w `extra.parent_requests` — dopisz do listy `extra.parent_requests`
i zapisz (best-effort, jak `_write_sidecar`: kazdy blad = `logger.warning`).
`extra.parent_request` = zadanie, ktore plik POBRALO (bez zmian, `downloaded_at`
prawdziwe); `extra.parent_requests` = kolejne zadania, ktore go uzyly.
Konsument szuka `parent_request == R or R in parent_requests`. Bez sidecara
(cache 0.6.1) — nic (tworzenie sidecara z niepewna data i bez `extra.source`
byloby zmyslaniem). Odrzucone: (C) nadpisanie `parent_request` (gubi historie),
(B) sama dokumentacja (D6: N4 w zakresie). Pokrywa tez arkusze reuzyte przez
wycinek (`run_pl_cutout` przekazuje `sidecar_extra`).

**(b) Wycinek — `skipped=True` z lista z sidecara.** `sources/sidecar.py::
read_sidecar(data_path) -> dict | None` (JSON, `None` przy braku/bledzie) +
`download/cutout.py::skipped_pl_cutout(cutout) -> PlCutoutResult` budujacy
`PlCutoutResult(path, skipped=True, missing_sheets=tuple(sidecar.extra.
missing_sheets or ()))`; uzywane w `run_pl_cutout`, `download_pl_cutout`
i w CLI (`_download_pl_cutout` zamiast wlasnego `exists()` — CLI drukuje wtedy
ten sam `Warning:` co przy budowie, z dopiskiem "(z sidecara istniejacego
wycinka)"). `sheet_paths` przy skipie zostaje `()` (udokumentowac).

### 4.3 Testy offline

- `tests/test_download_manager.py::TestSidecarWritten` (`:902+`, fixture
  `_mock_provider`): pobranie z `sidecar_extra={"parent_request": A}`, potem
  drugi manager z `B` i `skip_existing=True` -> sidecar ma `parent_request == A`
  i `parent_requests == [B]`; trzecie uzycie z `B` nie dubluje; brak sidecara
  -> nic nie powstaje (istniejacy test); `skip_existing` w `download_sheets`
  (obie galezie `max_workers` 1/4) — to samo.
- `tests/test_pl_cutout.py::TestLibraryApi` (`:1590+`): po
  `test_no_coverage_sheet_becomes_nodata_with_record` drugi przebieg bez
  `force` -> `skipped is True` i `missing_sheets == ("N-34-130-D-d-2-4",)`
  (dzis `()` — failing before), provider nie wolany; sidecar usuniety ->
  `missing_sheets == ()`. CLI (`TestDownloadPlBboxCutout`): istniejacy wycinek
  z `extra.missing_sheets` -> stdout `Skipped`, stderr `Warning:` z lista.

### 4.4 Ryzyka i pytania projektowe

- **Ksztalt pola:** (1) `extra.parent_requests` (lista, `parent_request`
  niezmienne) — rekomendacja; (2) `parent_request` -> najnowsze, historia
  w `parent_requests`. (1) nie zmienia znaczenia istniejacego pola.
- **Zapis nieatomowy** `write_sidecar` (`write_text`) przy rownoleglym
  dopisywaniu przez dwa procesy — ryzyko marginalne (ten sam plik w dwu
  zadaniach naraz); ewentualnie `os.replace` przez plik tymczasowy, jak
  wycinek. Rekomendacja: `os.replace` (5 linii) w `write_sidecar` dla
  wszystkich wolajacych.

### 4.5 Zakres

`download/manager.py` (3 sciezki skip + `_note_reuse`), `sources/sidecar.py`
(`read_sidecar`, atomowy zapis), `download/cutout.py` (`skipped_pl_cutout`),
`cli/download_cmd.py` (`_download_pl_cutout` skip), testy jw.; docs:
ARCHITECTURE 3.4/4.3, README tabela `extra.parent_request` i `:149-151`,
CLAUDE.md, SCOPE `:386-389`, CHANGELOG. Kontrakt publiczny: addytywny
(`extra.parent_requests`, `missing_sheets` wypelnione przy `skipped=True`).
Kolizja: `manager.py` (klaster skorowidz: `_write_sidecar`/`extra.source`,
N6) — moje zmiany nie dotykaja `_write_sidecar` (sekcja 8).

---

## 5. N5 — testy `live` nic nie sprawdzaja

### 5.1 Przyczyna potwierdzona na kodzie

`tests/test_pl2000_verification.py:404-482` (`TestPL2000LiveWMS`): 8 zapytan
GetFeatureInfo na endpoint 1 m EVRF2007 (`:405-407`) z `LAYERS=
SkorowidzeNMT2022iStarsze` (`:456-457`) — warstwy nie ma w
`GugikProvider.WMS_LAYERS["1m"]["EVRF2007"]` (`gugik.py:134-139`: 2026, 2025,
2024, 2023iStarsze; potwierdzone przez GetCapabilities w `gfi/index.json`
`caps.1m`). Serwer odpowiada HTTP 200 `text/xml` z `ServiceException
code="LayerNotDefined"` (probka `gfi/15_bogus1m_...body`, 554 B), a test
asertuje tylko `status_code == 200` (`:474`); kazdy blad sieci = `skip`
(`:477-482`). Wynik "4 passed, 4 skipped" (L1 D1) nie mowi nic o pobieraniu.

### 5.2 Proponowana naprawa

Zastapic `TestPL2000LiveWMS` klasa `TestLiveGugikIndex` (marker `live`
**i** `real_wms_layers` — inaczej autouse `_offline_wms_layers`
`conftest.py:125-174` podmieni GetCapabilities; timeout 15 s, `skip` tylko
na `ConnectionError`/`Timeout`, NIE na `RequestException` ogolnie):

1. `test_getcapabilities_matches_hardcoded_layers` — parametryzacja po
   `(GugikProvider|GugikNmptProvider, resolution, vertical_crs)`:
   `provider._fetch_wms_layers(endpoint) == WMS_LAYERS[...]`. To jedyny test,
   ktory wylapalby S4 (NMPT: 2025..2022iStarsze vs 2026..2023iStarsze)
   i coroczna rotacje `iStarsze`.
2. `test_land_sheet_resolves_to_matching_asc` — `provider._get_opendata_url
   ("N-33-48-C-a-3-4")` (5 m EVRF2007; rekord 2025 w `gfi/05_land5m_...body`)
   zwraca URL `https://opendata.geoportal.gov.pl/.../..._N-33-48-C-a-3-4.asc`
   z godlem jako CALYM tokenem (`_{godlo}.asc`) — po D4 sprawdza filtr twardy
   na zywej odpowiedzi; bez pobierania pliku.
3. `test_sea_sheet_is_no_coverage` — `_get_opendata_url("N-33-48-C-a-1-3")`
   (morze, L3: wszystkie 4 warstwy puste, szablon MapServera 7721 B bez
   znacznikow OGC, `gfi/01-04_sea5m_*`) -> `pytest.raises(NoCoverageError)`.
   Straz R5 na realnej odpowiedzi.
4. `test_unknown_layer_is_service_exception_not_no_coverage` — zapytanie
   z warstwa `SkorowidzeNMT1999NieIstnieje` (probki `gfi/14-16`) -> body
   zawiera `ServiceException`, a `_get_opendata_url` z lista warstw zawezona
   do niej rzuca `DownloadError` nie bedacy `NoCoverageError` (straz I-2).
5. Zachowac intencje pliku (weryfikacja PL-2000): dla 8 godel z
   `LIVE_WMS_SHEETS` zapytanie w srodku arkusza na WSZYSTKICH warstwach
   z `_get_validated_layers("1m","EVRF2007")`; asercje: brak
   `ServiceException`, >= 1 rekord `skor_NMT_wg_akt.push({...godlo:"X"...})`
   w sumie po warstwach, a bbox arkusza `SheetParser(X).get_bbox("EPSG:2180")`
   (PL-1992 albo PL-2000) ZAWIERA punkt zapytania — to sprawdza geometrie
   `Parser2000`/`SheetParser` wzgledem poligonow skorowidza GUGiK, czego
   dzisiejszy test udaje. Jesli ktoras z 8 lokalizacji nie ma rekordu 1 m,
   naprawa to wybor innego godla (interior PL) — nie oslabianie asercji.

Parser rekordow `push({...})` do tych asercji bierze sie z modulu skorowidza
klastra K3/K4 (`providers/pl/skorowidz.py` wg `research-orto-laz.md`) — testy
N5 sa jego konsumentem, nie definiuja wlasnego regexu.

### 5.3 Testy offline

Nie dotyczy (to sa testy live). Offline: liczba testow `live` w CLAUDE.md
("8 testow sieciowych") i SCOPE 6.2 do aktualizacji; `pyproject.toml`
markery bez zmian (`live`, `real_wms_layers` juz istnieja).

### 5.4 Ryzyka i pytania projektowe

- **Stabilnosc danych zywych:** morze pod `N-33-48-C-a-1-3` nie dostanie
  danych 5 m; rekord `N-33-48-C-a-3-4` moze zmienic kampanie, ale zawsze
  bedzie MIAL rekord (asercja na token godla, nie na numer kampanii).
- **Kiedy uruchamiac:** tylko swiadomie (`-m live`), jak dotad; przy zrywanych
  polaczeniach (S1) test 2-5 moze dac `DownloadError` — po naprawie S1
  (ponowienia w sesji) ryzyko maleje; do tego czasu `skip` na
  `ConnectionError`/`Timeout` jest akceptowalny, na `DownloadError` NIE.

### 5.5 Zakres

`tests/test_pl2000_verification.py` (klasa `:400-482`), CLAUDE.md, SCOPE.
Zaleznosc: modul skorowidza (K3/K4). Kontrakt publiczny: brak.

---

## 6. N8 — sidecar pliku PL-2000 deklaruje `horizontal_crs` EPSG:2180

### 6.1 Przyczyna potwierdzona na kodzie

`build_metadata` (`sources/sidecar.py:107-127`) bierze
`horizontal_crs=channel.horizontal_crs` (`:112`), a kanaly PL w rejestrze maja
na sztywno `EPSG:2180` (`registry.py:77`, `:83`, `:108`, `:129`, `:148`,
`:167`) — slusznie dla PL-1992, falszywie dla arkuszy PL-2000 (strefy 5-8 =
EPSG:2176-2179, `core/parser_2000.py:36-41` `ZONE_EPSG`) i kafli LAZ
`uklad_xy: PL-2000:S6`. `DownloadManager._write_sidecar` (`manager.py:852-870`)
nic nie nadpisuje; segment `pl_2000_...` (`storage.py:176-198`) jest juz
poprawny, sidecar nie. Plik `.asc` nie niesie CRS (rasterio `crs=None`), orto
TIF PL-2000 ma WKT bez EPSG (L1 BUG-L1-11) — z pliku odczytamy tylko
WSPOLRZEDNE (x >= 1e6 = strefa `x // 1e6`, jak `_reject_pl2000_sheets`
`cutout.py:284-301`). Dzis blad jest latentny, bo K4 podstawia plik PL-1992
(`7.123.8.asc` == `M-34-76-A-a-2-4.asc` w `e2e-data` L1); po D4 (filtr
twardy ukladu wg godla) plik PL-2000 bedzie prawdziwie PL-2000 i sidecar
z `EPSG:2180` stanie sie jawnie falszywy.

### 6.2 Proponowana naprawa

- `sources/sidecar.py`: kwarg `build_metadata(..., horizontal_crs: str | None
  = None)` — nadpisuje `channel.horizontal_crs` (addytywny, keyword-only);
  zastepuje dzisiejsze post-przypisania `meta.horizontal_crs = ...`
  w `write_pl_cutout_sidecar` (`cutout.py:449`) i `_write_cz_sidecar`
  (`download_cmd.py:1431`).
- `sources/sidecar.py::pl_horizontal_crs(data_path: Path, godlo: str | None)
  -> str`: (1) z godla: `SheetParser(godlo).uklad == "2000"` -> `ZONE_EPSG
  [zone]` (nowa property `SheetParser.native_crs`: `"EPSG:2180"` dla 1992,
  `self._pl2000.native_crs` dla 2000 — `sheet_parser.py:149-154` juz trzyma
  `Parser2000`); (2) kontrola z PLIKU: `.asc` -> `xllcorner`/`xllcenter`
  z naglowka (obok `read_asc_nodata` `:46-56`), `.tif` -> `rasterio` bounds
  (import lokalny); `x >= 1e6` -> strefa z cyfry milionow, inaczej 2180;
  rozjazd godlo vs plik -> `logger.warning` i **CRS z pliku** (sidecar opisuje
  plik; przed D4 to sciezka K4, po D4 nie wystapi); plik nieczytelny -> godlo.
- `manager.py::_write_sidecar` (wlasciciel: klaster skorowidz — sekcja 8):
  jedna linia `horizontal_crs=pl_horizontal_crs(data_path, request.get("godlo"))`.
- LAZ: `LazTile.horizontal_crs` (property obok `uklad`, `gugik_laz.py:96-118`):
  `PL-2000:S{z}` -> `ZONE_EPSG[z]`, `PL-1992*` -> `EPSG:2180`, inaczej `None`
  (kanal); `_write_laz_sidecar` (`download_cmd.py:1236-1249`) przekazuje
  `horizontal_crs=tile.horizontal_crs`.

Kontrakt: `horizontal_crs` = uklad FAKTYCZNY pliku (juz tak jest dla CZ
i wycinkow); dla PL-1992 bez zmian. Konsument (Hydrograf) czytajacy
`horizontal_crs` dla plikow `pl_2000_*` zobaczy 2176-2179 — zmiana
znaczeniowa na plus, bez zmiany schematu.

### 6.3 Testy offline

- `tests/test_sidecar.py`: `build_metadata(..., horizontal_crs="EPSG:2177")`
  nadpisuje kanal; `pl_horizontal_crs` na ASC z `xllcorner 6500000` + godlo
  `6.179.12.20` -> `EPSG:2177`; ASC `xllcorner 542560.30` + godlo PL-2000
  (przypadek K4) -> `EPSG:2180` + warning; brak pliku -> z godla.
- `tests/test_download_manager.py::TestSidecarWritten`: `download_sheet
  ("6.179.12.20")` z atrapa piszaca ASC o `xllcorner 6500000` -> sidecar
  `horizontal_crs == "EPSG:2177"` (dzis `EPSG:2180` — failing before);
  `N-34-130-D-d-2-4` -> `EPSG:2180` (regresja, istniejacy test `:924-935`).
- `tests/test_gugik_laz.py::TestLazTileUklad` (`:187+`): `horizontal_crs` dla
  `PL-2000:S6` -> `EPSG:2177`, `PL-1992` -> `EPSG:2180`, nieznany -> `None`;
  `tests/test_cli.py::TestCmdDownloadLaz` (`:2474+`, kafle z `PL-2000:S6`):
  sidecar kafla `horizontal_crs == "EPSG:2177"`.
- `tests/test_pl_cutout.py:449` post-przypisanie -> asercje sidecara wycinka
  bez zmian (`EPSG:5514`/`EPSG:2180` juz testowane `:698`, `:721`).

### 6.4 Ryzyka i pytania projektowe

- **Zrodlo prawdy: godlo czy plik?** (1) godlo (po D4 wystarczajace);
  (2) plik z godlem jako fallback; (3) oba z kontrola — **rekomendacja (3)**
  (koszt: odczyt naglowka ASC, ktory `build_metadata` i tak robi dla nodata;
  chroni sidecar takze wobec plikow z cache sprzed D4).
- **`horizontal_crs` dla NMT 5 m PL-2000?** 5 m nie istnieje w PL-2000 (godla
  5 m sa PL-1992) — helper i tak dziala.
- Kolejnosc wdrozenia: N8 razem z D4 albo po nim (przed D4 helper zglaszalby
  warning o rozjezdzie na kazdym pliku K4 — to poprawne zachowanie, nie blad).

### 6.5 Zakres

`sources/sidecar.py`, `core/sheet_parser.py` (`native_crs`),
`providers/pl/gugik_laz.py` (`LazTile.horizontal_crs`), `cli/download_cmd.py`
(`_write_laz_sidecar`, `_write_cz_sidecar` na kwarg), `download/cutout.py`
(`write_pl_cutout_sidecar` na kwarg), `download/manager.py::_write_sidecar`
(1 linia, wlasciciel skorowidz); testy jw.; docs: README tabela
`horizontal_crs` `:183`, ARCHITECTURE 3.2, CHANGELOG. Kontrakt publiczny:
addytywny kwarg; wartosc pola dla plikow PL-2000 zmienia sie na prawdziwa.

---

## 7. N9 — podwojne `estimate_pl_cutout_bytes`

### 7.1 Przyczyna potwierdzona na kodzie i profilem

`estimate_pl_cutout_bytes` (`cutout.py:482-512`) dla kazdego arkusza
nieobecnego w cache wola `SheetParser(leaf).get_bbox("EPSG:2180")` (`:505`);
`get_bbox` (`sheet_parser.py:660`) tworzy **nowy** `Transformer.from_crs
("EPSG:4326","EPSG:2180")` przy kazdym wywolaniu, a pyproj 3.7.2 nie cache'uje
`from_crs` (sprawdzone w zrodle: brak `lru_cache` w `pyproj/transformer.py`).
Profil offline: `Transformer.from_crs` 6,95 ms; `SheetParser()` 0,013 ms;
`SheetParser().get_bbox()` 8,87 ms; jeden `transform()` na gotowym
transformerze 0,003 ms. Czyli ~7 ms/arkusz z L7 to w >99 % budowa
transformera, nie parser. `run_pl_cutout:581` wola `check_pl_cutout_disk_space`
-> ta sama estymacja; wolajacy liczacy ja wczesniej (skrypt L7) placi dwa razy
(CLI nie — `download_cmd.py:1034` uzywa `cutout.estimated_bytes`). Hipoteza
backlogu ("podwojne wywolanie") jest prawdziwa, ale to symptom: sam jeden
przebieg to 7,7-11,5 s.

Pomiar na wycinku 75 x 75 km 5 m (1221 arkuszy, zero w cache):
`select_pl_cutout_sheets` 0,05 s; `estimate_pl_cutout_bytes` **8,98 s**;
z transformerem cache'owanym (monkeypatch w tej sesji) **0,114 s**, identyczny
wynik w bajtach.

### 7.2 Proponowana naprawa

**Opcja A (rekomendacja): cache transformerow w `core/sheet_parser.py`** —
`@functools.lru_cache def _transformer(src: str, dst: str) -> Transformer`
(module-level; `Transformer` pyproj >= 3.1 jest bezpieczny miedzy watkami —
`TransformerLocal(threading.local)` w `pyproj/transformer.py:300-360`),
uzyty w `get_bbox` (`:660`) i `_transform_bbox_to_wgs84` (`:957`); te same
3 miejsca w `parser_2000.py` (`:602`, `:707`, `:745`) i `core/geometry.
_transform_bbox` (`:449`, klucz `to_wkt()` dla obiektow `CRS`). Zero zmian
API; podwojne wywolanie kosztuje potem ~0,2 s i nie wymaga leczenia.
Przy okazji przyspiesza `find_sheets_for_bbox` dla PL-2000 i wszystkie
hierarchie.
**Opcja B: `run_pl_cutout(..., check_disk_space: bool = True)`** — kwarg
pozwalajacy wolajacemu pominac kontrole, gdy sam ja wykonal. Odrzucona:
dodatkowy przelacznik bezpieczenstwa w publicznym API dla problemu, ktory
znika po A.
**Opcja C: memoizacja wyniku na `PlCutoutSheets`** — zle: wynik zalezy od
stanu dysku (`pending`), nie tylko od selekcji.

### 7.3 Testy offline

Brak nowych testow trwalych (wydajnosc = smoke): `tests/test_sheet_parser.py`,
`tests/test_parser_2000.py`, `tests/test_pl_cutout.py::TestCutoutSize::
test_estimate_counts_only_pending_sheets` (`:940-957`) jako regresja
poprawnosci; dowod wdrozenia: skrypt jednorazowy jak wyzej (1221 arkuszy,
< 0,5 s, `need` identyczne z wersja bez cache). Dokumentacja: `L7` pkt 1
"Zachowanie do udokumentowania" staje sie nieaktualne — CHANGELOG (perf),
ARCHITECTURE 4.3 krok 1 (kontrola dysku "tania").

### 7.4 Ryzyka i pytania projektowe

- `lru_cache` bez limitu: klucze to pary etykiet CRS (kilkanascie) — bez
  ryzyka pamieciowego; `maxsize=64` dla porzadku.
- Transformer wspoldzielony miedzy watkami `DownloadManager` (pool
  `--workers`): bezpieczny od pyproj 3.1 (pyproject wymaga `>= 3.6.0`).

### 7.5 Zakres

`core/sheet_parser.py`, `core/parser_2000.py`, `core/geometry.py` (opcjonalnie),
CHANGELOG. Kontrakt publiczny: brak zmian.

---

## 8. Kolizje miedzy klastrami i lista plikow `kartograf/`

| Plik | Ten klaster | Inni |
|---|---|---|
| `cli/download_cmd.py` | S2 (`_download_godlo_list`, finisz listy, `_dispatch_area`, hierarchia godla), S3 (`_country_bbox` -> `CountryPart`, `Info:`), N4 (`_download_pl_cutout` skip), N8 (`_write_laz_sidecar`, `_write_cz_sidecar` kwarg) | CZ: N2 (`_cz_download_bbox`), komunikat `:1643-1644` (K2); orto-laz: N7 (`_cmd_download_laz`), `:756` |
| `download/manager.py` | S2 (`DownloadResult.hard_failures`, opcjonalnie status `no_coverage`), N4 (3 sciezki skip + `_note_reuse`) | skorowidz: `_write_sidecar` (`extra.source`, D5), N6 (cache) — **N8 = 1 linia w ich funkcji** (interfejs: `build_metadata(horizontal_crs=)` + `pl_horizontal_crs`) |
| `download/cutout.py` | S5 (`build_pl_cutout`: `check_source_grid`, W1, `extra.off_grid_sheets`), N4 (`skipped_pl_cutout`), N8 (kwarg w `write_pl_cutout_sidecar`) | skorowidz: N6 (`:572`, `:705` fabryka providera z cache), K4 komunikat `_reject_pl2000_sheets:306-311` |
| `transport/mosaic.py` | S5 (`check_source_grid`, `GridMismatchError`, usuniecie ostrzezenia) | — |
| `transform/raster.py` | S5 W1 (`warp_to_grid(list[Path])`, tor PL) | CZ: K2 dotyczy `transform/crs.py`, nie `raster.py` |
| `exceptions.py` | S5 (`GridMismatchError(ValidationError)`) | — |
| `sources/sidecar.py` | N8 (`build_metadata(horizontal_crs=)`, `pl_horizontal_crs`), N4 (`read_sidecar`, atomowy `write_sidecar`) | skorowidz: D5 `extra.source` (tylko tresc `extra`; brak kolizji w sygnaturze, uzgodnic kolejnosc mergu) |
| `core/sheet_parser.py` | N9 (cache transformerow), N8 (`native_crs`) | — |
| `core/parser_2000.py`, `core/geometry.py` | N9 (cache transformerow, opcjonalnie) | — |
| `providers/pl/gugik_laz.py` | N8 (`LazTile.horizontal_crs`) | orto-laz: K1/N7 (discovery WFS) — inny fragment pliku |
| `tests/test_pl2000_verification.py` | N5 | zaleznosc od parsera rekordow skorowidza (K3/K4) |

Poza `kartograf/`: `tests/test_cli.py`, `tests/test_pl_cutout.py`,
`tests/test_transport_mosaic.py`, `tests/test_download_manager.py`,
`tests/test_sidecar.py`, `tests/test_gugik_laz.py`; docs: CLAUDE.md, README,
SCOPE, ARCHITECTURE (3.2, 3.4, 4.2, 4.3, 4.6), DECISIONS (addenda ADR-027 D2/D3,
errata ADR-023 pkt 7), CHANGELOG, PROGRESS.

## 9. Pytania otwarte do rozstrzygniecia (zbiorczo)

1. S2: R5 takze dla hierarchii godla (`--scale`)? — rekomendacja TAK (1.4.a).
2. S2: nowy status `no_coverage` w `DownloadProgress` (ikona zamiast `✗`)? — rekomendacja TAK, addytywne (1.4.b).
3. S3: `Info:` dla kazdego przyciecia per kraj + osobny dla utraty; bez nowego pola sidecara — do potwierdzenia (2.2, 2.4.b).
4. S5: kompozycja per arkusz (W1) dla warpu z arkuszy o roznych fazach — bez niej podpowiedz z D3 wskazuje na wynik rownie zly; rekomendacja W1 tylko dla zestawow `off_grid` (3.4.a); nazwa `GridMismatchError` (3.4.b).
5. N4: `extra.parent_requests` (lista) dla arkuszy reuzytych; sidecar nie jest tworzony, gdy go nie ma (4.4).
6. N8: uklad z godla z kontrola wspolrzednych pliku; rozjazd = CRS pliku + warning (6.4).
7. N9: cache transformerow zamiast kwargu API (7.2) — brak zmiany kontraktu.
