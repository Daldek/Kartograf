# L7 — duzy wycinek NMT PL (>= 1000 arkuszy): czas, pamiec, deskryptory — raport OFFLINE

Data: 2026-09-29. Galaz `develop`, HEAD 6985765 (repo Kartograf TYLKO DO ODCZYTU —
zero zmian w kodzie/testach/dokumentacji, `git status` czysty przez cala sesje).
Katalog roboczy: `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L7-duzy-wycinek/`
(gitignored). **Zadanie jest OFFLINE** — siec zablokowana w skrypcie pomiarowym
straznikiem na `socket.socket.connect` (dowod: `network_attempts_blocked: []` w kazdym
z 4 raportow JSON), zasady "kultury wobec uslug publicznych" z `LIVE-COMMON.md` (workers
2, budzet 3 GB) NIE dotycza tego zadania — uzyto `--workers 4` i lacznie ok. 6 GB na
dysku roboczym (dane lokalne, cache Hydrografu tylko do odczytu, zero ruchu sieciowego).

## Zakres

**Zrodlo danych:** `/home/claude-agent/workspace/Hydrograf/cache/nmt/` (TYLKO DO
ODCZYTU, nic tam nie zmieniono). `nmt_5m/` = 1454 arkusze .asc, `nmt_1m/` = 523 pliki
(TEZ 5 m — `cellsize 5.00` potwierdzone naglowkiem ASC; katalog ma mylaca nazwe).
Wszystkie 1977 plikow maja tez `.prj` (sprawdzone: `find ... -name '*.prj' | wc -l`
rowne liczbie `.asc` w obu katalogach) — w tym cache NIE ma naturalnego przypadku
"arkusz bez .prj", wiec ta konkretna sciezka mieszanego cache nie zostala tu dodatkowo
przetestowana (jest juz pokryta osobnym E2E z fali review max, `docs/research/2026-09-28-fala-review-max/e2e/e2e_pl_cutout.py`).

**Analiza pokrycia (offline, bez pobierania):** zindeksowano 1652 unikalne godla
(suma `nmt_5m` + `nmt_1m`, przeciecie 325 identycznych plikow bit w bit — zweryfikowane
`filecmp`) i zgrupowano po jednostce nadrzednej godla (3-czlonowy prefiks, np.
`N-33-119`; w tym rejestrze kartografu to poziom z 256 potomkami 1:10000 — 4 poziomy
podzialu x4). Cache jest **rozproszony w 4 niespojnych ze soba klastrach geograficznych**
(prawdopodobnie osobne zlewnie z wczesniejszych sesji Hydrografu): okolica
N-33-118/119/120/130/131/132 (zachodnio-centralna PL, x~330-433 tys., y~497-573 tys.
w EPSG:2180), N-34-126/127/138/139 (okolice Bialegostoku/Lomzy), M-33-44/46/57/58/59/69/70/71
(Sudety/Dolny Slask) i M-34-61/76/77/88/89 (Malopolska). **Zaden pojedynczy klaster nie
osiaga 1000 arkuszy z realnymi danymi** — najgestszy (N-33, blok 3x3 jednostek
118/119/120/130/131/132/106/107/108) ma **732** arkusze z danymi na 1652 w calym cache.

**Wybrany obszar** (spojny prostokat, jednostki N-33-118/119/120/130/131/132, "dolne"
2 wiersze x 3 kolumny siatki jednostek nadrzednych): bbox EPSG:2180
`329716, 496844, 432911, 573431` (103,2 x 76,6 km). Uzasadnienie wyboru: to
najgestszy dostepny **spojny** blok, dajacy oficjalna (wymagana przez API) liczbe
arkuszy wyraznie powyzej progu 1000 przy najlepszym stosunku arkuszy-z-danymi do
wymaganych sposrod sprawdzonych kandydatow (zob. tabela nizej) — **>= 1000 arkuszy
odnosi sie do liczby arkuszy WYMAGANYCH przez selekcje API (`select_pl_cutout_sheets`),
NIE do liczby arkuszy z realnymi danymi w cache** (zgodnie z trescia zadania: nodata
tam, gdzie brak arkuszy, jest oczekiwanym, sprawdzanym zachowaniem, nie usterka).
Arkuszy z realnymi danymi w tym cache zabraklo do 1000 w jednym spojnym obszarze —
**uzyto tylu, ile bylo (688 dla EPSG:2180 / 732 dla EPSG:5514)**, zgodnie z
dopuszczeniem w tresci zadania.

| Kandydat (jednostki nadrzedne) | Oficjalnie wymagane (1:10000) | Realne w cache | Gestosc |
|---|---|---|---|
| `col10_only` (107/119/131, pasek 1x3) | 1000 | 662 | 66% |
| **wybrany: `118/119/120/130/131/132` (2x3)** | **1836 (2180) / 2394 (5514)** | **688 / 732** | **37,5% / 30,6%** |
| `full_3x3` (+106/107/108, 3x3) | 2652 | 732 | 28% |

(`col10_only` ma najlepsza gestosc i tez >=1000, ale mniejszy zapas nad progiem i
mniejsza siatke wyniku; wybrano wiekszy wariant 2x3 dla solidniejszego zapasu >=1000
przy wciaz dobrej gestosci i rozsadnym zuzyciu pamieci, zob. wyniki nizej.)

**Metoda:** arkusze skopiowane (TYLKO kopia, `setup_copy.py`) do wlasnego drzewa pod
sciezki `FileStorage(<dir>/data, resolution="5m", vertical_crs="EVRF2007").get_path(godlo, ".asc")`
(732 pliki, unia realnych arkuszy potrzebnych dla obu ukladow docelowych, 923 MB,
6,3 s). Pomiar: `build_one.py`, jeden proces Python na przebieg, wywoluje
`prepare_pl_cutout -> select_pl_cutout_sheets -> run_pl_cutout` z providerem
`RaisingProvider`, ktory **RZUCA `NoCoverageError` na kazdej probie pobrania**
(zaden arkusz nie jest faktycznie pobierany — arkusze realne pochodza WYLACZNIE ze
skopiowanego cache przez `skip_existing`). Siec zablokowana straznikiem na
`socket.socket.connect` (jak w szablonie `docs/research/2026-09-28-fala-review-max/e2e/e2e_pl_cutout.py`).
Pomiary: czas per etap (`time.perf_counter`), szczytowy RSS (`resource.getrusage(RUSAGE_SELF).ru_maxrss`,
Linux — biezacy "high water mark" jadra dla calego procesu, przechwycony PRZED
diagnostyka poprawnosci zeby jej wlasne alokacje nie zafalszowaly wyniku), maks. liczba
otwartych deskryptorow (watek-demon probkujacy `len(os.listdir("/proc/self/fd"))` co
10 ms przez caly pomiar). Limit 256 deskryptorow: `resource.setrlimit(RLIMIT_NOFILE, (256, hard))`
na starcie procesu (`--fd-limit 256`), osobny katalog wyjsciowy
`data_fd256/` (arkusze dolinkowane twardo z `data/` przez `cp -al` — 0 dodatkowej
kopii danych, 4 MB narzutu), zeby wymusic PELNA (nie "juz istnieje, pomin") budowe
takze pod limitem.

4 przebiegi: {EPSG:2180, EPSG:5514} x {domyslny limit deskryptorow (524288 miekki/twardy
na tej maszynie), 256}.

## Wyniki per scenariusz

### Wszystkie 4 przebiegi — PASS (exit 0, wynik poprawny, limit 256 przechodzi)

| Etykieta | Cel | Limit fd | Oficjalne/realne/brak | Czas calk. [s] | RSS szczyt [MiB] | Maks. otw. fd | Rozmiar wyniku |
|---|---|---:|---|---:|---:|---:|---:|
| `normal_2180` | EPSG:2180 | 524288 | 1836 / 688 / 1148 | 36,4 | 1037,3 | 9 | 1206,1 MiB |
| `fd256_2180`  | EPSG:2180 | **256** | 1836 / 688 / 1148 | 42,2 | 1037,3 | 9 | 1206,1 MiB |
| `normal_5514` | EPSG:5514 | 524288 | 2394 / 732 / 1662 | 108,7 | 1038,2 | 9 | 1398,3 MiB |
| `fd256_5514`  | EPSG:5514 | **256** | 2394 / 732 / 1662 | 107,0 | 1038,9 | 8 | 1398,3 MiB |

Czas per etap (s), `normal_2180` / `normal_5514`:
`prepare_pl_cutout` 0,00 / 0,07 — `select_pl_cutout_sheets` 0,05 / 0,06 —
`estimate_pl_cutout_bytes` (wolane osobno, do raportu) 7,69 / 11,47 —
`run_pl_cutout` 28,65 / 97,12 (ten etap woła TA SAMA estymacje disk-space wewnetrznie
jeszcze raz, zob. "Zachowanie do udokumentowania").

**Deskryptory — WYNIK KLUCZOWY:** maks. 8-9 otwartych deskryptorow rownoczesnie w
CALYM pomiarze (probkowanie co 10 ms, 3456-9926 probek na przebieg), **niezaleznie od
limitu** (524288 vs 256) i **niezaleznie od liczby arkuszy w mozaice** (688 vs 732).
Potwierdza to wprost dokumentacje `kartograf/transport/mosaic.py` ("Zrodla otwierane sa
POJEDYNCZO... limit 256 (macOS) — trzymanie wszystkich zrodel otwartych naraz konczylo
sie 'Too many open files'"). Limit 256 dziala **bez zadnej degradacji funkcjonalnej** —
zob. tez dowod bit-w-bit nizej.

**Bit-w-bit identycznosc normal vs fd256** (ten sam bbox/cel, inny limit fd, inny
katalog wyjsciowy): `sha256sum` obu par wynikowych GeoTIFF:
- EPSG:2180: `502c4885c32c5db6a4d953d0a053f870d570d2651b383163a3c0b3c360176951` (oba pliki)
- EPSG:5514: `d7a07810a42a810b52bb47a235db6ea569beca6bd58de804885a2ab78783d3d1` (oba pliki)

Limit deskryptorow nie zmienia ani jednego bajta wyniku.

### Poprawnosc — PASS (z jednym doprecyzowaniem metody pomiaru, nie biblioteki)

**Faza siatki (EPSG:2180):** `x mod 5 = 2.5`, `y mod 5 = 2.5` w obu przebiegach 2180 —
zgodne z dokumentacja (arkusze GUGiK 5 m: "narozniki na 5k + 2,5 m").

**Wartosci punktowo:**
- EPSG:2180 (crop bez warpa, wartosci 1:1): 1500/1500 probek trafionych z roznica
  `< 1 mm` (w praktyce `0.0` — kopia bitowa wartosci arkusza).
- EPSG:5514 (warp bilinear, operacja przypieta `axis order change (2D) + Inverse of
  Poland CS92 + ETRF2000-PL to ETRS89 (1) + Inverse of S-JTSK to ETRS89 (3) + Krovak
  East North (Greenwich)`, dokladnosc 0,5 m): 1500 probek nienodata, roznica srednia
  **5,1 cm**, mediana rzedu kilku cm, p95 **17,0 cm**, maks. **0,88 m** — spodziewane
  dla resamplingu bilinearnego terenu (nie blad; `< 1 mm` trafien tylko 47-48/1500, bo
  scisle rowne wartosci przy interpolacji sa rzadkie). Niezalezna operacja odwrotna
  (`target -> EPSG:2180`) zbudowana osobno przez `build_pinned_transform` (NIE surowy
  `gdal_operation()` — ten koduje kolejnosc osi authority i wymaga wspolrzednych w tej
  kolejnosci, zmierzony roundtrip < 1 mm z osobno zbudowanym `PinnedTransform`).

**Nodata tylko tam, gdzie brak arkuszy** (porownanie z obwiedniami arkuszy):
- EPSG:2180 — test WYCZERPUJACY (kazdy piksel, nie probka): maska pokrycia z
  prostokatow WSZYSTKICH 688 uzytych arkuszy vs maska nodata wyniku.
  `valid_outside_covered_px = 0` w obu przebiegach 2180 (**zero** pikseli z realna
  wartoscia poza obszarem jakiegokolwiek realnego arkusza — najwazniejszy niezmiennik,
  trzyma sie idealnie). `nodata_within_covered_px = 238 268` na `covered_px = 129 013 363`
  (0,18%) — zweryfikowane PUNKTOWO (7+ probek), kazdy taki piksel ma **realny arkusz
  ZE SWOJA WLASNA wewnetrzna dziura nodata w tym miejscu** (np. `N-33-120-C-a-4-1` przy
  x=405170/y=546275 — piksel arkusza = `-9999`, sasiedztwo 5x5 tez `-9999`) — to
  dziedziczona dziura danych GUGiK (np. brak zwrotu LIDAR), NIE artefakt mozaikowania.
  Pozostale 187 150 157 px nodata (99,87% calego nodata) to R5 (arkusz w ogole
  nieobecny) — zgodne z `missing_r5=1148`.
- EPSG:5514 — test PROBKOWANY (8000 pikseli/przebieg, transformacja odwrotna punktu +
  odczyt z arkusza zrodlowego, jak dopuszcza `LIVE-COMMON.md` pkt 3): 4/8000 (`normal_2180`
  miala swoj wlasny odpowiednik na poziomie 2180) i 8/8000 (`normal_5514`/`fd256_5514`)
  "niezgodnosci" — wszystkie zweryfikowane recznie jako TA SAMA przyczyna (wewnetrzna
  dziura zrodla, potwierdzona odczytem sasiedztwa 5x5 arkusza), zero prawdziwych
  niezgodnosci.

**Doprecyzowanie metody (nie blad biblioteki):** pierwsza wersja testu wyczerpujacego
dla EPSG:2180 miala BLAD WE WLASNYM SKRYPCIE diagnostycznym (nie w kartografie) —
zob. "Bledy" nizej. Po poprawce liczby jak wyzej; potwierdzone niezaleznie (te same
liczby wyszly z przeliczenia post-hoc na juz zbudowanym wyniku ORAZ z poprawionego
skryptu na kolejnym przebiegu `fd256_2180`).

### Rozmiary plikow — PASS

| | EPSG:2180 | EPSG:5514 |
|---|---:|---:|
| Wynik (GeoTIFF, bez kompresji, float32) | 1206,1 MiB (15318 x 20640 px) | 1398,3 MiB (16840 x 21765 px) |
| Plik POSREDNI mozaiki (przed warpem, deflate+predyktor3) | — (ten sam plik = wynik, bez warpa) | **244,0 MiB** (odtworzone post-hoc identycznymi parametrami co `build_pl_cutout`, 732 arkuszy) |
| Plik posredni BEZ kompresji (dla porownania) | — | 1605,9 MiB |
| Wspolczynnik kompresji posredniego | — | **6,58x** (wiecej niz orientacyjne 2-3x z docstringu — nasz obszar ma 63% nodata, ktore deflate kompresuje bardzo dobrze) |
| Arkuszy uzytych w mozaice, suma na dysku | 688 arkuszy, 904,6 MB | 732 arkusze, 958,8 MB |

Odtworzenie pliku posredniego (poza pomiarem glownym, ta sama funkcja
`mosaic_and_crop` z identycznymi `dst_kwds` co `build_pl_cutout`): 45,6 s dla samej
mozaiki 732 arkuszy — sensowna dekompozycja czasu `run_pl_cutout` dla 5514 (97,1 s):
~46 s mozaika + ~51 s pozostale (kontrola miejsca na dysku ~11 s + petla
DownloadManager na 2394 zadaniach + warp).

## Bledy (we WLASNYM skrypcie pomiarowym `build_one.py`, NIE w kartografie)

Zadnego bledu w kodzie kartografa nie znaleziono w tym zadaniu. Dwa bledy znalezione i
naprawione we wlasnym skrypcie diagnostycznym (dokumentuje sie je, bo mogly latwo dac
falszywy alarm o bledzie biblioteki):

**B1 — falszywe `nodata_within_covered_px` z ujemnego indeksu slice'a w numpy.**
Pierwsza wersja testu wyczerpujacego liczyla zakres wiersz/kolumna kazdego arkusza
przez `r0=round(...); r1=round(...); r0,r1 = max(0,r0), min(H,r1)`. Dla arkusza CALKOWICIE
poza siatka wyniku od gory (np. `N-33-108-C-c-1-2`, spoza wybranego bbox ale obecny w
kopii cache jako czesc WIEKSZEJ selekcji dla EPSG:5514 — margines `WARP_MARGIN_PX` +
zaokraglenie obwiedni przy reprojekcji siega ok. 7,6 km poza pierwotny bbox), `r1`
wychodzi UJEMNY (np. -998). `min(H, -998)` zwraca -998 (bo -998 < H), a
`tablica[0:-998]` w Pythonie to indeksowanie OD KONCA — zaznaczalo prawie CALA siatke
jako "pokryta", dajac falszywe 16 558 004 "nodata w obszarze pokrycia" zamiast
prawdziwych 238 268. Naprawa: pomin CALKOWICIE arkusz, gdy `r1<=0 or r0>=H or c1<=0 or c0>=W`,
PRZED przycinaniem (`build_one.py`, sekcja "Test WYCZERPUJACY"). Nie ma to zwiazku z
`kartograf/transport/mosaic.py::mosaic_and_crop` (ktory w ogole nie robi takiego
przycinania per-arkusz — dziala na bboxach geograficznych, nie indeksach tablicy).

**B2 — nieograniczony cache otwartych plikow w diagnostyce punktowej zablokowal
pierwszy przebieg `fd256_2180`.** Funkcja pomocnicza `read_sheet_px` (test wartosci
punktowych, uruchamiany PO `run_pl_cutout`) trzymala KAZDY otwarty `rasterio.open()`
w słowniku bez limitu i bez zamykania az do konca 1500 probek. Przy probkowaniu >~250
roznych arkuszy z 688 dostepnych i limicie 256 deskryptorow: `rasterio._err.CPLE_OpenFailedError:
...N-33-131-B-b-3-1.asc: Too many open files`. **Kluczowe: `run_pl_cutout` (mierzony
etap biblioteki) JUZ ZAKONCZYL SIE SUKCESEM** przed tym padem — plik wynikowy
(1 264 655 420 B, identyczny rozmiar jak w przebiegu bez limitu) i sidecar zostaly
zapisane poprawnie; padla wylacznie MOJA diagnostyka post-hoc. Naprawa: cache LRU z
limitem 32 otwartych plikow (`OrderedDict`, `popitem(last=False)` + `close()` przy
przekroczeniu). Po naprawie: przebieg powtorzony, zakonczony sukcesem, wynik bit w bit
identyczny z wersja bez limitu (zob. sha256 wyzej).

## Zachowanie do udokumentowania

1. **`estimate_pl_cutout_bytes`/`check_pl_cutout_disk_space` skaluje sie liniowo z
   liczba arkuszy OCZEKUJACYCH (nie tylko wybranych)** i jest kosztowna dla duzych
   selekcji: 7,7-11,5 s dla 1148-1662 arkuszy nieobecnych w cache (ok. 6,7-6,9 ms na
   arkusz — `SheetParser` + transformacja bboxa do EPSG:2180 w czystym Pythonie/pyproj).
   `run_pl_cutout` WOLA TA SAMA funkcje WEWNETRZNIE jeszcze raz (`check_pl_cutout_disk_space`
   przed `DownloadManager`) — jesli wywolujacy (jak nasz skrypt, w typowym wzorcu
   "oszacuj przed startem, pokaz uzytkownikowi") woła ja TEZ jawnie przed
   `run_pl_cutout`, koszt placi sie DWA RAZY (u nas: ok. 14-22 s z 36-108 s calosci,
   czyli 13-21% czasu). Nie jest to blad — oba wywolania maja legalny, niezalezny cel
   (raportowanie uzytkownikowi vs kontrola bezpieczenstwa przed pobraniem) — ale dla
   duzo wiekszych obszarow (dziesiatki tysiecy arkuszy) ten koszt urosnie liniowo i
   moze byc warty odnotowania w dokumentacji API (`prepare_pl_cutout`/`run_pl_cutout`
   docstring) jako znana cecha wydajnosciowa.
2. **Selekcja arkuszy (`select_pl_cutout_sheets`/`find_sheets_for_bbox`) pobiera
   "grubszym pedzlem" niz scisla geometria wymaga**, do ok. 3,7 km poza brzeg zadania
   po kazdej stronie (obserwowane: 22 z 688 arkuszy EPSG:2180 lezaly CALKOWICIE poza
   finalna siatka wyniku — ich tresc nie trafia do zadnego piksela wyniku). To NIE
   wplywa na poprawnosc (arkusze bez wplywu na wynik sa po prostu ignorowane przez
   `mosaic_and_crop`'s przycinanie do bboxa), ale oznacza nieco wiecej otwarc/sprawdzen
   plikow niz scisle minimum geometryczne (~3% w naszym przypadku) — drobny koszt
   efektywnosci, nie poprawnosci, wynikajacy prawdopodobnie z ziarnistosci
   przycinania/prune w rekurencyjnym algorytmie `find_sheets_for_bbox` (dokumentacja:
   "1:1M (math) -> 1:200k (siatka 12x12, math) -> rekurencyjne children+prune").
3. **Szczytowy RSS jest bliski (86-100%) rozmiaru finalnej siatki wyniku, NIE stala
   mala wartosc** — 1037-1039 MiB niezaleznie od celu (2180: wynik 1206 MiB; 5514:
   wynik 1398 MiB, ale posredni skompresowany tylko 244 MiB) — sugeruje, ze
   `rasterio.merge.merge(..., dst_path=...)` DZIALA kawalkami (jak dokumentuje
   `mosaic.py`: "szczyt 2,63x rozmiaru danych" BEZ `dst_path`, mniej z nim), ale
   pamiec i tak rosnie w przyblizeniu proporcjonalnie do rozmiaru wyniku, nie jest to
   pamiec-stala niezaleznie od skali. Dla planowania pojemnosci: przy tej rozdzielczosci
   (5 m) i tym wzorcu, ok. **1 GiB RSS per ~130-320 Mpx siatki wyniku** — dla
   znaczaco wiekszych wycinkow (np. cale wojewodztwo) warto zaplanowac odpowiedni
   margines RAM (przy 15 GiB fizycznych na tej maszynie i innych agentach dzialajacych
   rownolegle, dostepne bylo 4,5-6,4 GiB w trakcie pomiarow — komfortowy margines dla
   tej skali, ale NIE dla znacznie wiekszej).
4. **Deskryptory: potwierdzona bezpieczna gorna granica ok. 9 rownoczesnie otwartych
   plikow**, niezaleznie od liczby arkuszy (688-732) i ustawionego limitu (256 vs
   524288) — znaczny margines ponizej domyslnego limitu macOS (256). Warto to
   ZAMIENIC w automatyczny test regresyjny (np. z `resource.setrlimit` w markerze
   `live`/osobnym markerze wydajnosciowym), zeby przyszla zmiana w `mosaic_and_crop`
   (np. przejscie na rownolegle otwieranie zrodel) nie zepsula tej wlasciwosci po cichu.

## Odpowiedz na pozycje checklisty (PROGRESS.md pkt 12i: "duzy wycinek (>= 1000 arkuszy): czas, pamiec, deskryptory")

Zweryfikowano offline na realnych danych GUGiK (cache Hydrografu) dla obu obslugiwanych
celow reprojekcji uzywanych w praktyce (EPSG:2180 bez warpu, EPSG:5514 z warpem
przypietym) i dla obu warunkow deskryptorow (domyslny limit, limit 256 "jak na macOS"):

- **Czas:** 36-42 s (EPSG:2180, 1836 wymaganych arkuszy) / 107-109 s (EPSG:5514, 2394
  wymagane arkusze, dodatkowy warp). Limit 256 fd: +16% (2180) / -1,6% (5514) wzgledem
  domyslnego — w granicach szumu pomiarowego (wspoldzielona maszyna, inne agenty
  rownolegle), NIE systematyczna degradacja.
- **Pamiec:** szczytowy RSS 1037-1039 MiB w kazdym z 4 przebiegow — stabilny,
  proporcjonalny do rozmiaru siatki wyniku (patrz "Zachowanie" pkt 3), NIE zalezny od
  limitu deskryptorow.
- **Deskryptory:** maks. 8-9 rownoczesnie otwartych w calym procesie (probkowane co
  10 ms), pod limitem 524288 ORAZ pod limitem 256 — **limit 256 PRZECHODZI** bez
  zadnej zmiany zachowania (wynik bit w bit identyczny, sha256 wyzej). Potwierdza to
  bezposrednio adnotacje w `kartograf/transport/mosaic.py` o poprawce "Too many open
  files" (review max 2026-08-30, zn. 3) na tej skali (688-732 realnych arkuszy,
  1836-2394 oficjalnie zadanych).
- **Uwaga o zakresie:** cache Hydrografu dostepny na tej maszynie NIE mial 1000 arkuszy
  Z REALNYMI DANYMI w jednym spojnym obszarze (max 732 w calym cache, w dowolnym
  klastrze) — uzyto wiec obszaru z >= 1000 arkuszy WYMAGANYMI przez selekcje API
  (1836/2394), z 688/732 realnymi i reszta poprawnie obsluzona jako `missing_sheets`
  (R5, nodata). Jest to zgodne z dopuszczeniem w tresci zadania ("jesli arkuszy jest za
  malo na 1000 w spojnym obszarze — uzyj ile jest i napisz to") — tu formalnie
  arkuszy-do-przetworzenia bylo >= 1000, a arkuszy-z-danymi zabraklo do 1000 i to
  jest jawnie udokumentowane.

## Surowe artefakty (sciezki)

Wszystko w `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L7-duzy-wycinek/`:

- `index_cache.py`, `cache_index.json` — indeksacja 1652 arkuszy cache Hydrografu (bbox, godlo)
- `setup_copy.py`, `setup_copy_report.json`, `wanted_sheets.json` — kopiowanie 732 arkuszy do wlasnego `data/`
- `build_one.py` — skrypt pomiarowy (1 przebieg = 1 proces; argumenty: `--target-crs`, `--output-dir`, `--fd-limit`, `--workers`, `--label`, `--bbox`)
- `report_normal_2180.json`, `report_fd256_2180.json`, `report_normal_5514.json`, `report_fd256_5514.json` — pelne wyniki strukturalne (czas per etap, RSS, fd, poprawnosc, sidecar)
- `run_{normal,fd256}_{2180,5514}.std{out,err}.txt` — surowe logi (w tym linie `No data for ...` z biblioteki, `RLIMIT_NOFILE: ... ->`)
- `diag_intermediate_5514_report.json` — rozmiar/czas odtworzonego pliku posredniego (post-hoc, poza pomiarem glownym)
- `data/nmt/pl_1992_5m_evrf2007/bbox/329716_496844_432911_573431.tif(.meta.json)` — wynik EPSG:2180 (limit domyslny)
- `data/nmt/pl_1992_5m_evrf2007/bbox/-568197.4873_-822913.536_-459370.4099_-738711.528.tif(.meta.json)` — wynik EPSG:5514 (limit domyslny)
- `data_fd256/nmt/pl_1992_5m_evrf2007/bbox/...` — te same dwa wyniki pod limitem 256 (bit w bit identyczne z powyzszymi, zob. sha256)
- `data/nmt/pl_1992_5m_evrf2007/N-33/...` — 732 skopiowane arkusze zrodlowe (+ `.prj`)
