# Szew danych wysokosciowych PL/CZ — Cieszyn / Cesky Tesin

Analiza diagnostyczna etapu 1 (CUZK obok GUGiK), 2026-08-11.
Galaz `feature/etap1-cz-dmr`, wersja `0.7.0-dev`. **Zadnych zmian w kodzie ani commitow.**

Katalog roboczy: `/tmp/claude-1001/-home-claude-agent-workspace-Kartograf/f27c5cce-cd98-44b3-80e9-a90c445a283f/scratchpad/seam`

> **Errata (2026-08-22):** opisany tu blad zostal naprawiony w 0.7.0 (ADR-024):
> serwer CUZK dostaje zadania wylacznie w natywnym EPSG:5514, reprojekcja tresci
> jest lokalna przypieta operacja, a sidecar niesie transform.horizontal =
> "pinned: <opis> (<dokladnosc> m)" zamiast "server:EPSG:2180". Wnioski 7.1
> (reprojekcja lokalna) i 7.2 (dokladnosc w sidecarze) sa zrealizowane
> (kartograf/cli/download_cmd.py, tests/test_cuzk_dmr.py::
> TestHorizontalReprojection). Dokument zachowany jako diagnoza.

---

## 0. Wniosek nadrzedny (czytaj najpierw)

**`--target-crs EPSG:2180` dla zrodel CZ zwraca raster przesuniety poziomo o ~135 m.**
Nie jest to blad transformacji Kartografa i nie widac go w zadnym sidecarze — reprojekcje
pikseli wykonuje serwer ArcGIS CUZK (`exportImage&imageSR=2180`) i robi to **bez
transformacji datum** (S-JTSK/Bessel traktowany jak ETRS89). Kartograf ten wynik przyjmuje
bez weryfikacji i opisuje w sidecarze jako `transform.horizontal="server:EPSG:2180"`,
bez pola dokladnosci.

Ironia architektoniczna: `kartograf/transform/crs.py` **zakazuje** operacji ballpark
(`allow_ballpark=False`, odrzut `accuracy < 0`) i ten zakaz dziala — obwiednia bboxa
policzona lokalnie przez `bbox_to_crs()` zgadza sie z pyproj do **0,07 m**. Ale sama tresc
rastra idzie sciezka serwerowa, ktora ten sam blad ballparku wprowadza z powrotem.
Dokladnie pulapka "cichy ballpark" znana juz z notatek o danych niemieckich.

Liczby ponizej podaje wiec **dwukrotnie**: dla produktu z `--target-crs` (przesunietego)
i dla danych natywnych EPSG:5514 zreprojektowanych lokalnie przez pyproj/GDAL (poprawnych).
Wszystkie wnioski merytoryczne o szwie opieram na tych drugich.

---

## 1. Pobrania (komendy 1:1)

Uruchamiane z katalogu roboczego (baza `.kartograf_cache.db` powstaje w cwd, poza repo).

```bash
K=/home/claude-agent/workspace/Kartograf/.venv/bin/kartograf

# (1) CZ w ukladzie porownywalnym z PL — reprojekcja SERWEROWA
$K download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 \
   --country cz --target-crs EPSG:2180 --vertical-crs EVRF2007 -o seam-cz
# -> Downloading CZ bbox (2m, EPSG:2180)...
# -> Downloaded to seam-cz/cz_dmr5g_471194.6628_209462.3009_474803.6146_211258.6264.tif

# (2) PL — arkusze natywne
$K download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 \
   --country pl --vertical-crs EVRF2007 -o seam-pl
# -> Found 2 sheets at 1:10000 for bbox (resolution: 1m)
# ->   Sheets: M-34-74-C-a-4-4, M-34-74-C-b-3-3
# -> Downloaded 2 files to seam-pl

# (3) kontrola — CZ natywnie w EPSG:5514 (bez --target-crs)
$K download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 \
   --country cz --vertical-crs EVRF2007 -o seam-cz-native
# -> Downloading CZ bbox (2m, EPSG:5514)...
# -> Downloaded to seam-cz-native/cz_dmr5g_-448602.0516_-1113021.556_-444867.0516_-1110955.981.tif
```

Wszystkie trzy `exit 0`. Czas: CZ ~5 s, PL ~50 s (2 arkusze, ~71 MB).

### Wlasnosci plikow

| plik | CRS | shape | res [m] | nodata | wazne |
|---|---|---|---|---|---|
| `seam-cz/cz_dmr5g_471194…tif` | 2180 | 898 x 1804 | 2,000528 | -9999 | 35,1 % |
| `seam-cz-native/cz_dmr5g_-448602…tif` | 5514 | 1033 x 1867 | 2,000536 | -9999 | 32,8 % |
| `seam-pl/…/M-34-74-C-a-4-4.asc` | brak w pliku | 2328 x 2263 | 1,0 | -9999 | 51,5 % |
| `seam-pl/…/M-34-74-C-b-3-3.asc` | brak w pliku | 2327 x 2262 | 1,0 | -9999 | 99,0 % |

ASC GUGiK nie niesie CRS w pliku — jedynym zrodlem prawdy jest sidecar (`EPSG:2180`).
Dla konsumenta zewnetrznego to istotne: `rasterio.open(...).crs` zwraca `None`.

### Sidecary (fragmenty)

`seam-cz/…tif.meta.json` — reprojekcja serwerowa:

```json
{"dataset": "cz.cuzk.dmr5g", "country": "CZ", "provider": "CUZK",
 "horizontal_crs": "EPSG:2180", "vertical_crs": "EPSG:5621",
 "vertical_source": "native", "resolution": "2m", "nodata": -9999.0,
 "request": {"bbox": [471194.6628001905, 209462.30092557054,
                      474803.6146034533, 211258.62638225872],
             "bbox_crs": "EPSG:2180"},
 "transform": {"horizontal": "server:EPSG:2180",
               "vertical": "pinned: Baltic 1957 height to EVRF2007 height (1) (0.1 m)"},
 "extra": {"parent_request": {"bbox": [18.6, 49.752, 18.65, 49.768],
                              "bbox_crs": "EPSG:4326", "countries": ["CZ"]}},
 "license": {"id": "CC-BY-4.0", "attribution": "Podklad: Cesky urad zememericky a katastralni (CUZK), CC BY 4.0"},
 "schema": "kartograf-meta/1"}
```

`seam-pl/…/M-34-74-C-a-4-4.asc.meta.json`:

```json
{"dataset": "pl.gugik.nmt_1m", "country": "PL", "provider": "GUGiK",
 "horizontal_crs": "EPSG:2180", "vertical_crs": "EPSG:9651",
 "vertical_source": "native", "resolution": "1m", "nodata": -9999.0,
 "request": {"godlo": "M-34-74-C-a-4-4"}, "transform": null,
 "extra": {"parent_request": {"bbox": [18.6, 49.752, 18.65, 49.768],
                              "bbox_crs": "EPSG:4326", "countries": ["PL"]}},
 "license": {"id": "PL-PGiK-40a", …}, "schema": "kartograf-meta/1"}
```

Drugi arkusz PL identycznie (`request.godlo` = `M-34-74-C-b-3-3`).

Uwagi do sidecarow:

- `parent_request` obecny po obu stronach takze przy **jawnym** `--country` — zgodnie z decyzja
  z konsultacji. Przy `--country pl`/`cz` pole `countries` niesie tylko ten jeden kraj, wiec
  **z pojedynczego sidecara nie da sie odtworzyc, ze zadanie mialo drugiego partnera**; dopiero
  tryb `auto` daje `countries: ["CZ","PL"]`. Dla scalania transgranicznego (Hydrograf) to roznica
  istotna — patrz sekcja 7.
- `vertical_source: "native"` przy jednoczesnym `transform.vertical: "pinned: Baltic 1957 …"`
  wyglada sprzecznie, ale **nie jest bledem**: `vertical_source` to statyczna cecha *kanalu*
  z deskryptora (`native` vs `ellipsoidal`), a nie opis tego, co zrobiono z danymi. Warto miec
  swiadomosc, ze naiwny odczyt "native + EPSG:5621" sugeruje, ze serwer wydal EVRF2007 wprost.
- Brakuje pola dokladnosci przy `transform.horizontal` — patrz sekcja 3.

---

## 2. Metoda analizy

Siatka analizy: **2 m, EPSG:2180, wyrownana do siatki PL** (origin 470742,5 / 211576,5).

- **PL 1 m -> 2 m: dokladna srednia blokowa 2x2** (numpy, bez interpolacji i bez GDAL).
  Kazda komorka 2 m pokrywa sie dokladnie z 4 komorkami 1 m, wiec agregacja nie wnosi
  przesuniecia fazowego. Nodata nie wchodzi do sredniej; osobno liczona jest frakcja waznosci.
- **CZ -> siatka analizy: jedna reprojekcja bilinear** (`rasterio.warp.reproject`,
  transformacja datum z PROJ) z rastra **natywnego 5514**. Maska waznosci warpowana osobno,
  dane zamaskowane jako `NaN` przed interpolacja — nodata nie wycieka do wynikow.

Uzasadnienie wyboru: CZ i tak musi przejsc przez jedno przeprobkowanie (zmiana odwzorowania
jest nieunikniona), natomiast PL nie musi przez zadne — agregacja 2x2 to operacja dokladna.
Odwrotny wariant (CZ 2 m -> 1 m bilinear) dokladalby CZ interpolacje *w gore* rozdzielczosci,
czyli wymyslal detal, ktorego w zrodle nie ma. Wariant "oba na siatke 2,0005 m CZ w 2180"
przeprobkowywalby oba zbiory. Wybrany wariant ma **minimalna laczna liczbe interpolacji**.

Rozroznienie masek:

- **footprint (luzny)** — jakikolwiek wklad danych zrodlowych; uzywany do geometrii pokrycia.
- **strict** — komorka w 100 % zbudowana z waznych pikseli zrodlowych (PL: 4/4 piksele 1 m;
  CZ: maska po warpie == 1,0); uzywany do statystyk roznic. Odrzuca to komorki brzegowe,
  w ktorych srednia mieszalaby dane z pustka.

Kontrola pozioma: dopasowanie przez minimalizacje RMS roznic **wokol mediany** (odporne na
offset pionowy) przy probkowaniu bilinear obu zbiorow w przesunietych pozycjach.

---

## 3. Rejestracja pozioma — sedno sprawy

### Produkt z `--target-crs EPSG:2180` (serwerowy)

Test przesuniec na tym rastrze **nie ma minimum w (0,0)** — minimum lezy daleko poza
oczekiwanym zakresem:

| wielkosc | wartosc |
|---|---|
| RMS roznic przy (0, 0) | **5,361 m** |
| minimum RMS | **0,266 m** przy **dx = −119 m, dy = −65 m** |
| korelacja wysokosci CZ~PL przy (0,0) | **0,4986** |
| mediana roznic przy (0,0) | +1,369 m (mean +2,286, std 5,246, zakres −18,0 … +25,7) |

Korelacja 0,50 miedzy dwoma NMT tego samego terenu jest fizycznie nieakceptowalna
(poprawnie zestawione modele daja >0,99) — to sygnatura grubej dezregistacji, nie szumu.

### Skad 135 m

Roznica miedzy operacja poprawna a **ballpark** (pominiety datum shift Bessel -> ETRS89)
dla srodka sceny, policzona w pyproj:

```
ballpark − poprawna:  dE = 116,37 m,  dN = 68,28 m,  |d| = 134,92 m
zaobserwowane przesuniecie rastra:  dE ≈ 119 m, dN ≈ 65 m,  |d| = 135,6 m
```

Zgodnosc co do kilku metrow. **Serwer CUZK reprojektuje bez transformacji datum.**

Dowod rozstrzygajacy — ten sam obszar pobrany natywnie (EPSG:5514) i zreprojektowany
lokalnie przez pyproj/GDAL, po czym ten sam test:

| wielkosc | wartosc |
|---|---|
| minimum RMS | **0,284 m przy dx = 0, dy = 0** |
| mediana roznic | **−0,084 m** |

Te same bajty zrodlowe, inna droga reprojekcji, zero przesuniecia. Wina lezy jednoznacznie
po stronie reprojekcji serwerowej, nie danych.

### Test drobnych przesuniec ±2 m (na danych poprawnych)

RMS roznic wokol mediany [m], siatka 0,5 m:

```
   dx:     -2.0    -1.5    -1.0    -0.5     0.0     0.5     1.0     1.5     2.0
 dy -2.0  0.498   0.460   0.419   0.391   0.364   0.353   0.346   0.356   0.371
 dy -1.0  0.441   0.402   0.361   0.334   0.308   0.302   0.302   0.322   0.344
 dy +0.0  0.398   0.360   0.319   0.295  [0.275]  0.276   0.284   0.312   0.342
 dy +0.5  0.385   0.349   0.310   0.289   0.272   0.278   0.289   0.321   0.352
 dy +1.0  0.373   0.338   0.302   0.284   0.272   0.282   0.297   0.330   0.365
 dy +2.0  0.369   0.341   0.314   0.305   0.302   0.318   0.338   0.374   0.409
```

Minimum: **dx = 0,0, dy = +0,5 m (RMS 0,2721)** wobec **0,2746 w (0,0)** — roznica **0,9 %**,
przy komorce 2 m i zaokragleniach probkowania. Praktycznie: **siatki sa zgodne poziomo**,
rezydualne przesuniecie ponizej 0,5 m, czyli ponizej wielkosci piksela CZ. Misa RMS jest przy
tym plaska i lekko wydluzona wzdluz osi N-S (teren rzeczny o slabej fakturze poprzecznej),
wiec +0,5 m nie jest wiarygodnie odroznialne od zera.

---

## 4. Geometria szwu — nakladka czy dziura?

Ekstent analizy: obwiednia footprintu CZ, **2110 x 2086 m**.

| kategoria | piksele 2 m | udzial | powierzchnia |
|---|---|---|---|
| **nakladka** (oba zrodla wazne) | 262 559 | 23,9 % | **1,050 km²** |
| tylko PL (GUGiK NMT 1 m) | 421 264 | 38,3 % | 1,685 km² |
| tylko CZ (CUZK DMR 5G 2 m) | 366 265 | 33,3 % | 1,465 km² |
| brak po obu stronach | 50 277 | 4,6 % | 0,201 km² |

**Odpowiedz: istnieje NAKLADKA, nie ma dziury.**

Szerokosc ciaglego pasa nakladki mierzona per wiersz (transekt E-W, granica biegnie ~N-S):

| statystyka | wartosc |
|---|---|
| minimum | 8 m |
| p25 | 432 m |
| **mediana** | **454 m** |
| p75 | 474 m |
| maksimum | 1036 m |
| srednia | 511 m |

Nakladka jest **ciagla**: w 1028 z 1043 wierszy wystepuje, mediana liczby fragmentow na wiersz
= 1 (maks. 2). Krance zasiegow: wschodni kraniec CZ mediana X = 472 290 m, zachodni kraniec PL
mediana X = 471 836 m — dane polskie zaczynaja sie ~454 m **na zachod** od miejsca, gdzie koncza
sie czeskie, czyli oba panstwa nalatuja LIDAR-em kilkaset metrow za granice. Granica panstwowa
(Olza) lezy wewnatrz tego pasa, ale **z samych masek nie da sie jej wyznaczyc** — maski pokazuja
zasiegi nalotow, nie granice polityczna.

Klasyfikacja pikseli "brak danych po obu stronach" (0,201 km²):

- **96,8 %** — przy krawedzi ekstentu: naroza obrocone go czworokata, ktory prostokat CZ
  z ukladu 5514 tworzy po reprojekcji do 2180. **Artefakt kadru analizy**, nie dziura w danych.
- **3,2 %** (0,0064 km², 11 wierszy) — przy poludniowej krawedzi sceny (y ≈ 209 248–209 268),
  czyli na dolnym brzegu mozaiki PL. Rowniez efekt brzegowy sceny.
- **0,0 %** — dziur wewnetrznych, otoczonych danymi z obu stron, **nie ma ani jednego piksela**.
  W szczegolnosci koryto Olzy nie jest nodata w obu zbiorach naraz.

Czyli: **w pasie przygranicznym nie ma zadnej luki**; przy scalaniu problemem bedzie nadmiar
danych (ktore zrodlo wybrac w pasie 450 m), a nie ich brak.

---

## 5. Roznice wysokosci CZ − PL w nakladce

Oba zbiory nominalnie w EVRF2007: PL to realizacja **EPSG:9651**, CZ to **EPSG:5621**
uzyskane przez przypieta operacje `Baltic 1957 height to EVRF2007 height (1)` o deklarowanej
dokladnosci **0,10 m**.

n = 261 005 pikseli 2 m (1,044 km²), maska strict.

| statystyka | wartosc [m] |
|---|---|
| **mediana** | **−0,083** |
| srednia | −0,068 |
| **std** | **0,276** |
| std wokol mediany | 0,276 |
| **NMAD** (1,4826 x MAD) | **0,109** |
| p0,1 / p1 / p5 | −2,227 / −0,798 / −0,394 |
| p25 / p75 | −0,163 / −0,015 |
| p95 / p99 / p99,9 | +0,435 / +0,726 / +1,644 |
| min / max | −5,660 / +5,051 |

Udzialy: **|d| < 0,10 m — 43,7 %**, |d| < 0,25 m — 78,8 %, **|d| < 0,50 m — 93,4 %**,
|d| < 1,0 m — 99,1 %, |d| > 2 m — 0,20 %, |d| > 5 m — 0,001 %.

Korelacja wysokosci CZ~PL: **0,99862** (relief w nakladce: 254,8–297,6 m, std 5,25 m).

### Rozklad systematyki, szumu i artefaktow

- **Systematyka: mediana −0,083 m.** Miesci sie w deklarowanej dokladnosci 0,10 m przypietej
  operacji Bpv -> EVRF2007. To roznica *realizacji pionowych*, a nie blad Kartografa: taki
  offset jest oczekiwany i **na tym poziomie transformacja pionowa etapu 1 dziala poprawnie**.
  (Dla porzadku: znak jest ujemny, czyli CZ po transformacji lezy ~8 cm **nizej** niz PL.)
- **Szum: NMAD 0,109 m.** To laczny budzet: dokladnosc pionowa obu NMT (deklarowane
  ~0,10–0,18 m dla ALS), roznica epok nalotu, roznica rozdzielczosci (2 m vs 1 m zagregowane)
  i jedna interpolacja bilinear po stronie CZ. Rozklad ma ostry pik — nie ma w nim
  dodatkowej skladowej sugerujacej blad przetwarzania.
- **Artefakty/outliery: |d| > 2 m to tylko 0,20 % (515 px)** i sa silnie zwiazane z nachyleniem:
  mediana nachylenia terenu w outlierach **15,4°** wobec **2,0°** w calej nakladce. Stoki > 10°
  zajmuja 14,4 % powierzchni, ale skupiaja **64,3 %** outlierow (> 20°: 5,9 % powierzchni,
  41,2 % outlierow). Korelacja |d| z nachyleniem 0,31. To klasyczny efekt przeprobkowania na
  skarpach — na stoku 20° przesuniecie 0,3 m daje 0,11 m roznicy wysokosci — plus realne
  roznice na brzegach koryta i skarpach miedzy epokami nalotu.
- **Struktura przestrzenna** (`seam_diff.png`): tlo jest niemal biale (roznice < 0,1 m) na
  calej zabudowie i polach; wyrazna **czerwona wstega biegnie dokladnie korytem Olzy**
  (CZ wyzej o 0,3–0,8 m) — to nie jest blad rejestracji, tylko **rozne traktowanie lustra
  wody**: inny stan wody w dniu nalotu i inna metoda wypelniania powierzchni wodnych w DMR 5G
  i NMT. W histogramie odpowiada temu drugi, plaski garb przy +0,35…+0,45 m. Lokalne niebieskie
  platy (CZ nizej) skupiaja sie na kilku obiektach — zbiorniki/wyrobiska i miejsca zmian terenu
  miedzy epokami. Wzdluz samego szwu **nie widac zadnej krawedzi ani schodka** — co potwierdza,
  ze po poprawnej reprojekcji zbiory schodza sie plynnie.

---

## 6. Co jest cecha danych, a co artefaktem Kartografa

| zjawisko | wielkosc | zrodlo |
|---|---|---|
| przesuniecie poziome ~135 m przy `--target-crs` | 119 m E / 65 m N | **Kartograf/CUZK** — serwerowy `imageSR` bez datum shift, przyjety bez weryfikacji |
| offset pionowy −0,083 m | mediana | **dane** — roznica realizacji EVRF2007 (9651 vs 5621 z Bpv), w granicach 0,10 m operacji |
| szum 0,109 m NMAD | rozklad | **dane** + ~jedna interpolacja; nie da sie tego przypisac Kartografowi |
| czerwona wstega w korycie Olzy | +0,3…+0,8 m | **dane** — rozne lustro wody / epoki nalotu |
| outliery na skarpach | 0,20 % pikseli | **mieszane** — przeprobkowanie na stromiznach + realne zmiany terenu |
| nakladka 454 m | geometria | **dane** — oba panstwa nalatuja za granice |
| "dziura" 0,201 km² | 96,8 % kadr | **artefakt kadru analizy**, nie danych |
| ASC PL bez CRS w pliku | — | **dane GUGiK**; sidecar jest jedynym nosnikiem CRS |

Poza sciezka `--target-crs` **nie znalazlem sladu, zeby Kartograf cokolwiek psul**:
transformacja pionowa trafia w deklarowana dokladnosc, obwiednie licza sie do 0,07 m,
nodata nie wycieka, mozaikowanie arkuszy PL jest geometrycznie spojne (siatki obu arkuszy
wyrownane co do metra, 12 m zakladki bez uskoku).

---

## 7. Wnioski dla scalania transgranicznego (Hydrograf)

1. **`--target-crs` dla CZ nie nadaje sie obecnie do scalania.** Do czasu naprawy jedyna
   poprawna droga to pobranie natywne (EPSG:5514) i reprojekcja lokalna przez PROJ. Ta sama
   watpliwosc dotyczy kazdego innego `image_sr` != natywny na serwerach ArcGIS CUZK,
   a przez analogie takze przyszlych zrodel DE/SK sterowanych serwerowa reprojekcja.
   Sugerowany kierunek naprawy (poza zakresem tej analizy): albo reprojekcja lokalna zamiast
   `imageSR`, albo test kontrolny punktow (serwer vs `PinnedTransform`) z twardym bledem przy
   rozjezdzie > tolerancji, albo — minimum minimorum — zapis dokladnosci/ostrzezenia
   w `transform.horizontal` zamiast golego `server:EPSG:2180`.
2. **Sidecar musi niesc dokladnosc transformacji poziomej**, tak jak juz niesie ja pionowa
   (`pinned: … (0.1 m)`). Konsument nie ma dzis zadnego sygnalu, ze `server:EPSG:2180` moze
   znaczyc "blad 135 m".
3. **W pasie ~450 m trzeba rozstrzygac konflikt, nie laty.** Skoro dziur nie ma, scalanie
   sprowadza sie do reguly wyboru: sensowne jest priorytetowanie zrodla o wyzszej
   rozdzielczosci (PL 1 m) tam, gdzie jest wazne, i uzycie CZ poza jego zasiegiem, z waskim
   feather/blend w strefie przejscia. Uskok do zamaskowania ma mediane 0,083 m — jedno
   przesuniecie stale zdejmuje wiekszosc rozjazdu.
4. **Piony sprowadzac jawnie do jednej realizacji.** Roznica 9651 vs 5621 jest mala, ale
   niezerowa i systematyczna; przy laczeniu z danymi hydrologicznymi (spadki, objetosci)
   warto ja odejmowac swiadomie, a nie zostawiac jako "szum".
5. **Koryta rzek graniczne traktowac osobno.** Najwiekszy spojny rozjazd (0,3–0,8 m) lezy
   dokladnie tam, gdzie hydrologia jest najwrazliwsza. Zadna transformacja tego nie usunie —
   to roznica stanu wody i metody; przy modelowaniu przeplywu wybor jednego zrodla dla calego
   koryta jest bezpieczniejszy niz mozaika.
6. **`parent_request` przy jawnym `--country` niesie tylko jeden kraj** (`countries: ["CZ"]`
   wzgl. `["PL"]`), wiec nie zwiaze dwoch pobran wykonanych osobno. Do scalania Hydrograf
   powinien albo uzywac trybu `auto` (wtedy `countries: ["CZ","PL"]` i identyczny
   `parent_request` we wszystkich sidecarach), albo dopasowywac po polu `request.bbox`
   rodzica. Warto to w specu dopowiedziec.

---

## 8. Rysunki

| plik | tresc |
|---|---|
| `seam_masks.png` | mapa waznosci: nakladka / tylko PL / tylko CZ / brak; krance zasiegow, osie w metrach 2180 |
| `seam_diff.png` | mapa roznic CZ − PL, paleta rozbiezna wycentrowana na 0, skala ucieta na p1/p99 (±0,80 m), szary = poza nakladka |
| `seam_hist.png` | histogram roznic z mediana, p5/p95 i pasmem deklarowanej dokladnosci 0,10 m |

Wszystkie 170 dpi. Palety: kategoryczna blue/orange/aqua (trojka udokumentowana jako
przechodzaca walidacje all-pairs CVD) + achromatyczny szary dla klasy "brak danych";
rozbiezna blue–szary–red z neutralnym srodkiem.

## 9. Odtwarzalnosc

`analyse.py` (siatka, maski, geometria szwu, statystyki) i `plots.py` (rysunki) leza w katalogu
roboczym. Posrednie tablice: `pl_mosaic.npy`, `F_cat.npy`, `F_diff.npy`, `F_cz.npy`, `F_pl.npy`,
`F_meta.json`, `F_shift.json`. matplotlib/scipy zainstalowane do lokalnego `./pylibs`
(`PYTHONPATH=./pylibs`), **`.venv` projektu nietkniete**; `git status` czysty przez cala sesje.
