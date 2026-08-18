# Weryfikacja E2E bugfixu reprojekcji CZ — punkty 1 i 4 z kontrola TRESCI

Galaz `feature/etap1-cz-dmr` @ `2dd8dae`, 2026-08-11, dane **zywe** (serwery CUZK + GUGiK).
Katalog roboczy: `/tmp/claude-1001/-home-claude-agent-workspace-Kartograf/f27c5cce-cd98-44b3-80e9-a90c445a283f/scratchpad/seam/verify`
**Zadnych zmian w kodzie, zadnej zmiany galezi** (`git status` czysty przez cala sesje).

---

## 0. Werdykt

| punkt | zakres | werdykt | liczba rozstrzygajaca |
|---|---|---|---|
| **1** | godlo TM33 `302_5550` -> EPSG:3045 | **PASS** | minimum RMS **dokladnie (0,00; 0,00)**, RMS(0,0) = **0,0163 m** (prog 0,1) |
| **4** | bbox + `--target-crs EPSG:2180` | **PASS** | minimum RMS **dokladnie (0,00; 0,00)**, RMS(0,0) = **0,0310 m** (prog 0,1) |
| **4b** | CZ vs NMT PL w pasie nakladki (szew Olzy) | **PASS** | mediana CZ−PL = **−0,0862 m** (prog 0,3; seam-report: −0,083 m) |

Fix dziala na zywych danych. Obie sciezki rastrowe trafiaja w tresc referencyjna
**w zerze**, z rezyduum na poziomie szumu probkowania. Kontrole negatywne (ponizej)
potwierdzaja, ze metoda wykrywa bledy tej klasy — wiec zerowy wynik nie jest
artefaktem nieczulosci.

---

## 1. Metoda kontroli tresci

Metodologia 1:1 z `bugfix-report.md` (sekcja diagnozy), z jedna roznica: referencja
natywna jest pobierana **bezposrednim** `GET .../exportImage` (biblioteka `requests`,
z pominieciem `CuzkClient`), zeby produkt i referencja nie dzielily kodu transportu.

1. Produkt wydany przez Kartografa czytany z dysku (siatka + wartosci).
2. Obwiednia produktu (400 punktow po brzegu) przeliczona do EPSG:5514 **przypieta
   operacja** (`build_pinned_transform("EPSG:5514", <cel>, _HORIZONTAL_POLICY)`,
   kierunek INVERSE) + margines 60 m -> `exportImage?bboxSR=5514&imageSR=5514`,
   `pixelType=F32`, `noData=-9999`, piksel 2 m.
3. Test przesuniec: srodek kazdego waznego piksela produktu przesuniety o (dx, dy),
   przeliczony ta sama przypieta operacja do 5514, referencja probkowana **bilinear**
   (czysty numpy), liczone RMS roznic **wokol mediany** (odporne na offset pionowy).
4. Skan drobny **±2 m co 0,25 m** (17 x 17 = 289 ocen).
5. Kontrola czulosci: ten sam pipeline PROJ **bez krokow datum** (`push/pop v_3`,
   `cart`, `molobadekas`) daje wektor ballparku; liczone RMS w tej pozycji.

Skrypt: `shift_test.py` (wynik: `shift_p1.json`, `shift_p4.json`, `surf_*.npy`).
Porownanie z PL: `cz_vs_pl.py`. Pomiar skutku fixu: `old_vs_new.py`.

Kryteria z zadania: **minimum RMS w (0,0) ±0,5 m** oraz **RMS(0,0) < 0,1 m**.

---

## 2. Punkt 1 — godlo TM33

```bash
cd .../scratchpad/seam/verify
/home/claude-agent/workspace/Kartograf/.venv/bin/kartograf download 302_5550 --country cz -o v1
# -> Downloading 302_5550 (CZ, resolution: 2m)...
# -> Downloaded to v1/cz_dmr5g/302/5550/302_5550.tif
# exit 0, real 1,300 s
```

### Geometria i plik

| cecha | wartosc | oczekiwanie | ocena |
|---|---|---|---|
| sciezka | `v1/cz_dmr5g/302/5550/302_5550.tif` | podkatalog deskryptora + rozbicie godla | OK |
| CRS | **EPSG:3045** | 3045 | OK |
| res | **(2.0, 2.0)** | (2, 2) | OK |
| bounds | **(302000.0, 5550000.0, 304000.0, 5552000.0)** | dokladnie tyle | OK (co do bitu) |
| shape / typ | 1000 x 1000, float32, nodata −9999.0 | 1 km²/4 -> 1000 px | OK |
| rozmiar | 4 003 384 B | — | patrz Zastrzezenie 1 |
| dane | wazne 6,61 % (66 078 px), 446,23–476,34 m | kafel przy zachodniej granicy CZ | OK, zgodne z E2E (5a: 64 722 px) |

Katalog wyjsciowy zawiera **wylacznie** `302_5550.tif` + `302_5550.tif.meta.json`
(brak pozostalosci po pliku natywnym — sprzatanie dziala).

### Sidecar (`302_5550.tif.meta.json`)

```json
{"dataset": "cz.cuzk.dmr5g", "country": "CZ", "product": "nmt", "provider": "CUZK",
 "horizontal_crs": "EPSG:3045", "vertical_crs": "EPSG:8357", "vertical_source": "native",
 "resolution": "2m", "nodata": -9999.0, "request": {"godlo": "302_5550"},
 "license": {"id": "CC-BY-4.0", ...},
 "transform": {
   "horizontal": "pinned: Inverse of Krovak East North (Greenwich) + S-JTSK to ETRS89 (3) + UTM zone 33N + axis order change (2D) (0.5 m)"
 },
 "extra": {}, "schema": "kartograf-meta/1"}
```

- `transform.horizontal` w formacie `"pinned: <opis> (<acc> m)"` — **jest** (przed fixem
  na tej sciezce bylo `transform: null`, patrz E2E krok 1).
- `transform.vertical` slusznie **nieobecny** — pobranie natywne Bpv (`EPSG:8357`),
  bez `--vertical-crs`.
- `extra` puste — tryb godlowy nie ma `parent_request` (zgodne ze specem).

### Kontrola TRESCI

Referencja: `exportImage` 5514 na obwiednie kafla (−897 988,6 / −1 021 707,2 /
−895 628,2 / −1 019 346,7), 1180 x 1180 px, wazne 9,7 %.

| wielkosc | wartosc |
|---|---|
| **RMS(0,0)** | **0,0163 m** (n = 65 732) |
| mediana roznic w (0,0) | +0,0000 m (brak transformacji pionowej — zgodnie z oczekiwaniem) |
| **minimum RMS (skan ±2 m / 0,25 m)** | **0,0163 m przy (dx = +0,00, dy = +0,00)** |
| RMS w narozach skanu (±2 m) | 0,337 / 0,348 / 0,347 / 0,336 |
| ballpark wg pyproj | dE +63,96, dN +94,38, \|d\| **114,01 m** |
| RMS, gdyby tresc byla przesunieta o ballpark | **5,4448 m** |

RMS [m], wiersze dy, kolumny dx (co 0,5 m):

```
        -2.00  -1.50  -1.00  -0.50   0.00   0.50   1.00   1.50   2.00
 -2.00  0.337  0.314  0.296  0.285  0.282  0.288  0.302  0.322  0.348
 -1.50  0.285  0.256  0.232  0.217  0.213  0.220  0.238  0.263  0.294
 -1.00  0.240  0.204  0.172  0.150  0.143  0.153  0.177  0.210  0.248
 -0.50  0.209  0.165  0.123  0.088  0.073  0.090  0.126  0.169  0.214
 +0.00  0.199  0.151  0.102  0.053 [0.016] 0.053  0.102  0.150  0.199
 +0.50  0.213  0.169  0.126  0.090  0.073  0.087  0.122  0.164  0.209
 +1.00  0.247  0.210  0.177  0.153  0.143  0.150  0.171  0.203  0.240
 +1.50  0.294  0.263  0.237  0.220  0.212  0.217  0.231  0.255  0.284
 +2.00  0.347  0.321  0.301  0.287  0.281  0.284  0.295  0.312  0.336
```

Misa jest **symetryczna i ostra**, minimum dokladnie w zerze, wartosc w zerze o rzad
wielkosci nizsza niz w sasiedztwie 0,5 m. Dawne przesuniecie serwerowe (+1,25 m wg
bugfix-report) dalo by RMS ~0,15 m, czyli 9x wieksze — bylo by widoczne natychmiast.

**PUNKT 1: PASS** (minimum w (0,0), 0,0163 m < 0,1 m).

### Dodatkowo: bezposredni pomiar skutku fixu na tym samym kaflu

Plik sprzed fixu z E2E (`/tmp/kartograf-e2e-etap1/cz_dmr5g/302/5550/302_5550.tif`,
19:39, `imageSR=3045`) przetrwal. Porownanie stary~nowy (`old_vs_new.py`, skan ±30 m):

| wielkosc | wartosc |
|---|---|
| RMS(0,0) stary vs nowy | 0,5128 m (n = 64 036) |
| minimum RMS | **0,0416 m przy (dx +4,50, dy +2,00)** |
| tresc starego lezala wzgledem poprawnej o | **(−4,50; −2,00) m, \|d\| = 4,92 m** |

Rezyduum w minimum (0,04 m) pokazuje, ze roznica byla **czystym przesunieciem**, nie
szumem. Uwaga istotna: to **4,92 m, nie 1,25 m** — blad serwerowej sciezki 3045 jest
**zmienny przestrzennie** (1,25 m kolo Cieszyna, ~4,9 m w zachodnich Czechach). Patrz
Zastrzezenie 3.

---

## 3. Punkt 4 — bbox z `--target-crs EPSG:2180`

```bash
/home/claude-agent/workspace/Kartograf/.venv/bin/kartograf download \
  --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz \
  --target-crs EPSG:2180 --vertical-crs EVRF2007 -o v4
# -> Downloading CZ bbox (2m, EPSG:2180)...
# -> Downloaded to v4/cz_dmr5g_467492.8465_192586.3211_471134.299_198163.8958.tif
# exit 0, real 8,327 s
```

### Geometria i plik

| cecha | wartosc | ocena |
|---|---|---|
| CRS | **EPSG:2180** | OK |
| res | **(2.0, 2.0)** — dokladnie | OK (przed fixem: 1,99985 — siatke liczy teraz Kartograf) |
| shape | 2789 x 1821 px (identycznie jak w E2E sprzed fixu) | OK |
| bounds | (467492,8465; 192585,8958; 471134,8465; 198163,8958) | OK, patrz nizej |
| nodata / pokrycie | −9999,0 / **100 %** waznych | OK |
| rozmiar | 20 332 190 B (2789·1821·4 + naglowek) | OK |

Zadany bbox to (467492,8465; 192586,3211; 471134,2990; 198163,8958). Wynik wychodzi
poza niego o **0,43 m na poludniu i 0,55 m na wschodzie** — mniej niz ½ piksela,
dokladnie jak opisuje ADR-024 (zasieg przyklejony do wielokrotnosci `pixel_size`).
Katalog zawiera tylko TIF + sidecar.

### Sidecar — cytat

```json
"transform": {
  "horizontal": "pinned: Inverse of Krovak East North (Greenwich) + S-JTSK to ETRS89 (3) + Inverse of ETRF2000-PL to ETRS89 (1) + Poland CS92 + axis order change (2D) (0.5 m)",
  "vertical": "pinned: Baltic 1957 height to EVRF2007 height (1) (0.1 m)"
},
"horizontal_crs": "EPSG:2180", "vertical_crs": "EPSG:5621", "vertical_source": "native",
"request": {"bbox": [467492.8465420702, 192586.321124183, 471134.2989923145, 198163.89578754455],
            "bbox_crs": "EPSG:2180"},
"extra": {"parent_request": {"bbox": [18.55, 49.6, 18.6, 49.65],
                             "bbox_crs": "EPSG:4326", "countries": ["CZ"]}}
```

- `transform.horizontal` w wymaganym formacie `"pinned: ... (... m)"` — **OK**
  (przed fixem: `"server:EPSG:2180"`, bez dokladnosci).
- `transform.vertical` **obecny** — OK.
- `extra.parent_request` obecny mimo jawnego `--country cz` — zgodnie z decyzja z konsultacji.

### Kontrola TRESCI

Referencja: `exportImage` 5514, bbox (−453 641,1; −1 129 643,4; −449 462,8; −1 123 680,7),
2089 x 2981 px, wazne 100 %. Punkty testowe: co 4. piksel produktu (318 288 pkt).

| wielkosc | wartosc |
|---|---|
| **RMS(0,0)** | **0,0310 m** (n = 318 288) |
| mediana roznic w (0,0) | **+0,1262 m** = zastosowany shift pionowy Bpv->EVRF2007 (E2E 5a: +0,13237 m na innym kaflu) |
| **minimum RMS (skan ±2 m / 0,25 m)** | **0,0310 m przy (dx = +0,00, dy = +0,00)** |
| RMS w narozach skanu | 0,904 / 0,815 / 0,815 / 0,904 |
| ballpark wg pyproj | dE +118,11, dN +63,19, \|d\| **133,95 m** |
| RMS, gdyby tresc byla przesunieta o ballpark | **37,5191 m** |

```
        -2.00  -1.50  -1.00  -0.50   0.00   0.50   1.00   1.50   2.00
 -2.00  0.904  0.792  0.698  0.628  0.593  0.598  0.642  0.717  0.815
 -1.00  0.721  0.583  0.455  0.352  0.299  0.323  0.412  0.532  0.667
 -0.50  0.660  0.510  0.363  0.230  0.152  0.208  0.336  0.481  0.631
 +0.00  0.629  0.473  0.317  0.161 [0.031] 0.161  0.317  0.473  0.629
 +0.50  0.631  0.482  0.337  0.209  0.152  0.230  0.363  0.510  0.660
 +1.00  0.667  0.532  0.412  0.324  0.299  0.351  0.455  0.583  0.721
 +2.00  0.815  0.717  0.641  0.597  0.592  0.628  0.698  0.792  0.904
```

Misa idealnie symetryczna wzgledem (0,0). Stosunek RMS przy ballparku do RMS w zerze
wynosi **1210x** — metoda jest bezdyskusyjnie czula na blad, ktory naprawiano.
Mediana +0,126 m jest przy okazji **niezaleznym potwierdzeniem**, ze transformacja
pionowa zostala wykonana (referencja natywna jest w Bpv, produkt w EVRF2007).

**PUNKT 4: PASS** (minimum w (0,0), 0,0310 m < 0,1 m).

---

## 4. Punkt 4b — porownanie z NMT PL w pasie nakladki (szew Olzy)

Bbox punktu 4 (18,55–18,60 E; 49,60–49,65 N) lezy w glebi Czech — nie ma tam danych PL.
Porownanie transgraniczne wykonano wiec na **bboxie z seam-report** (te same arkusze PL,
ktore nadal leza w `../seam-pl/`), komenda identyczna jak w punkcie 4:

```bash
/home/claude-agent/workspace/Kartograf/.venv/bin/kartograf download \
  --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country cz \
  --target-crs EPSG:2180 --vertical-crs EVRF2007 -o v4s
# -> Downloaded to v4s/cz_dmr5g_471194.6628_209462.3009_474803.6146_211258.6264.tif
# exit 0, real 2,750 s; 6 485 736 B, 898 x 1804, EPSG:2180, res (2.0, 2.0)
```

Sidecar `v4s` niesie te same dwie przypiete operacje co punkt 4
(`horizontal: "pinned: ... Poland CS92 + axis order change (2D) (0.5 m)"`,
`vertical: "pinned: Baltic 1957 height to EVRF2007 height (1) (0.1 m)"`).

Metoda (`cz_vs_pl.py`): siatka porownania = siatka produktu CZ (2180, 2 m); arkusze PL
1 m probkowane **bilinear** w srodkach pikseli CZ (oba zbiory sa juz w 2180 — zadnej
transformacji ukladu, samo probkowanie); maska strict = piksel CZ wazny **i** wszystkie
4 sasiednie piksele PL wazne.

| wielkosc | **po fixie** (`v4s`) | **przed fixem** (`../seam-cz`, kontrola negatywna) | seam-report (reprojekcja lokalna) |
|---|---|---|---|
| n (strict) | 216 319 px = 0,865 km² | 285 214 px | 261 005 px |
| **mediana CZ−PL** | **−0,0862 m** | **+1,3681 m** | −0,083 m |
| mediana \|CZ−PL\| | 0,1204 m | — | — |
| srednia / std | −0,0647 / 0,2761 m | — / 5,2456 m | −0,068 / 0,276 |
| NMAD | 0,1111 m | — | 0,109 |
| **korelacja CZ~PL** | **0,99796** | **0,4987** | 0,99862 |
| \|d\| < 0,1 m / < 0,5 m | 42,2 % / 93,9 % | — | 43,7 % / 93,4 % |
| p1 / p99 | −0,758 / +0,726 m | — | −0,798 / +0,726 |

**Mediana −0,0862 m < 0,3 m — PASS.** Wynik odtwarza seam-report (−0,083 m) co do
3 mm mimo innego schematu przeprobkowania, a rozklad (NMAD, percentyle, udzialy)
zgadza sie na 2. miejscu po przecinku.

Kontrola negatywna jest tu kluczowa: **ten sam skrypt na pliku sprzed fixu** daje
medianę +1,368 m i korelacje 0,4987 — czyli dokladnie liczby z seam-report (+1,369 /
0,4986). Test nie jest slepy; gdyby fix nie dzialal, zobaczylbym to natychmiast.

Dla sciezki bboxowej (punkt 4) osobny pomiar "stary vs nowy" na plikach E2E jest wiec
**zbedny** — kontrola negatywna wyzej dotyczy dokladnie tej samej sciezki kodu
(`--target-crs EPSG:2180`) i odtwarza zmierzone wczesniej 135 m (mediana +1,37 m,
korelacja 0,50 to sygnatura dezregistacji o tej skali).

---

## 5. Zastrzezenia (nic z tego nie zmienia werdyktow)

1. **Pliki wynikowe stracily "rzadki" uklad TIFF serwera.** Kafel `302_5550` (93 % nodata)
   wazyl przed fixem **527 034 B** (serwerowy TIFF tiled, puste kafle pominiete), teraz
   **4 003 384 B** — 7,6x wiecej; lokalny zapis jest striped i gesty (`compress=None`,
   `tiled=False`). Dla punktu 4 (0 % nodata) roznicy praktycznie nie ma (21,6 -> 20,3 MB).
   Skutek wylacznie dyskowy, ale przy masowym pobieraniu kafli brzegowych rosnie
   kilkukrotnie. Warto rozwazyc `tiled=True` + kompresje w profilu zapisu warpu.
2. **Zasieg waznych pikseli rosnie o ~1 px na krawedzi nodata.** Produkt punktu 1 ma
   66 078 waznych pikseli, ale dla 346 z nich (0,5 %) referencja natywna jest juz nodata
   — to halo interpolatora bilinear (GDAL renormalizuje wagi, gdy czesc sasiadow jest
   maskowana). Wartosci pozostaja poprawne (test "pole plaskie" w suite to pokrywa),
   ale maska waznosci produktu moze siegac ~1 piksel poza faktyczny zasieg danych
   zrodlowych. Konsument liczacy powierzchnie pokrycia powinien o tym wiedziec.
3. **Liczba "1,25 m" w bugfix-report/ADR-024 zaniza dawny blad sciezki godlowej.**
   Pomiar na `302_5550` (zachodnie Czechy) daje **4,92 m** przesuniecia produktu sprzed
   fixu — prawie 4x wiecej niz zmierzone kolo Cieszyna. Blad serwerowy 3045 jest wiec
   **zmienny przestrzennie** (najpewniej inna realizacja S-JTSK->ETRS89 po stronie
   serwera, nie staly offset). Dla decyzji o zakresie fixu to argument wzmacniajacy,
   ale dokumentacja czyta sie dzis tak, jakby 1,25 m bylo stala globalna — warto
   dopisac jedno zdanie.
4. **Zmiana siatki wzgledem macierzy E2E sprzed fixu.** Punkt 4 mial `res ≈ 1,99985`
   i bounds = zadany bbox; teraz `res = 2,0` dokladnie, a zasieg jest zaokraglony do
   wielokrotnosci piksela (≤ ½ px poza zadanie). To zamierzone (ADR-024) i lepsze
   (siatka bez ulamkowego piksela), ale liczby w `docs/research/2026-08-11-etap1-e2e.md`
   dla punktow 1 i 4 sa juz nieaktualne — dokument warto odswiezyc o wyniki tej
   weryfikacji, bo obecnie opisuje stan sprzed fixu.
5. **Referencja i produkt korzystaja z tej samej przypietej operacji** (z definicji
   zadania: sprawdzamy, czy tresc trafia tam, gdzie mowi `PinnedTransform`). Poprawnosc
   samej operacji nie jest przedmiotem tego testu — potwierdza ja niezaleznie punkt 4b
   (zgodnosc z danymi GUGiK na 8 cm) oraz zakaz ballparku w `transform/crs.py`.
6. Referencja natywna jest pobierana z tego samego serwera co produkt, tyle ze w ukladzie
   natywnym — test wykrywa bledy reprojekcji, ale nie wykryl by bledu samego zrodla
   (gdyby CUZK wydawal zla tresc w 5514). To ograniczenie metody, nie fixu.

## 6. Pliki i odtwarzalnosc

| plik | tresc |
|---|---|
| `shift_test.py` | referencja natywna + test przesuniec (uzycie: `shift_test.py <tag> <produkt> <EPSG> [stride]`) |
| `cz_vs_pl.py` | porownanie CZ z arkuszami NMT PL w nakladce |
| `old_vs_new.py` | pomiar przesuniecia produktu sprzed fixu wzgledem produktu po fixie |
| `shift_p1.json`, `shift_p4.json`, `surf_p1.npy`, `surf_p4.npy` | wyniki skanow |
| `czpl_v4s.json`, `oldnew_p1w.json` | statystyki CZ−PL i pomiar starego przesuniecia |
| `native_p1.tif`, `native_p4.tif` | referencje natywne 5514 (bezposredni `exportImage`) |
| `v1/`, `v4/`, `v4s/` | produkty Kartografa (TIF + sidecar) |
