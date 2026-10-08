# L3-morze — NMT PL w pasie morskim na zywych danych GUGiK (2026-09-29)

Galaz `develop`, HEAD 152c31e, repo nietkniete (`git status` czysty). Katalog roboczy:
`e2e-data/2026-09-29-live/L3-morze/` (dalej `WD/`). Wszystkie polecenia z `WD/`
(`cd WD && kartograf ...`), dane `-o ./data`, `--workers 2` (dwa razy `1`).

**Status: tresc i logika R5 przy morzu — PASS; odpornosc CLI przy morzu — FAIL.**
Arkusze czysto morskie trafiaja do `extra.missing_sheets` + `Warning:` + kod 0,
nodata lezy wylacznie nad woda, wartosci 1:1 z arkuszy (0 rozbieznych pikseli na
14,3 mln), straz "raport wyjatku OGC = blad warstwy" dziala na realnych odpowiedziach
w obie strony. Ale: (B1) wycinek z wieloma arkuszami morskimi przez CLI praktycznie
nie przechodzi, gdy GUGiK zrywa czesc NOWYCH polaczen (Hel: 4 z 4 prob kod 1) — ta
sama biblioteka na jednej sesji keep-alive z ponawianiem: 72/72 zapytan bez bledu;
(B2) blad chwilowy najnowszej warstwy skorowidza = cicho pobrana STARSZA kampania
(tu roznice wysokosci do 5,2 m na wydmach); (B3) tryb listy arkuszy przy morzu
zawsze konczy sie kodem 1, a z `--workers 1` nie pobiera nic.

Scenariusze: **PASS 7, FAIL 3, UWAGA 4** (tabela nizej).

## Zakres

| ID | Obszar | Zadanie (EPSG:2180) | Arkusze 1:10000 | Dlaczego |
|---|---|---|---|---|
| A | Leba (brzeg otwartego morza, port, jeziora Lebsko/Sarbsko) | `404000,765000,410000,772000` | 16 (5 morskich) | linia brzegowa W-E przez srodek bboxa, pelny rzad arkuszy morskich na N; jeziora sprawdzaja "nodata nad ladem" |
| A1 | Leba, 1 m | `406000,767500,408500,771500` | 6 (2 morskie) | pokrycie 1 m istnieje (kampania 2022); ~25 MB/arkusz |
| As | Leba, cel EPSG:5514 | `405000,766000,409000,771000` | 12 (4 morskie) | wszystkie arkusze ladowe juz w cache (minimum zapytan) |
| B | Polwysep Helski (Jastarnia/Jurata) | `475000,755000,483000,763000` | 25 (14 morskich) | wazka mierzeja, morze po OBU stronach (Baltyk + Zatoka Pucka); >10 arkuszy morskich |
| D | Baltyk na N od Leby | `404000,771000,407000,772500` | 2 (oba morskie) | bbox w calosci nad morzem |
| C | Rozewie, bbox przez 54,90°N (offline) | `455000,773000,459000,784000` | 18 / 15 | polnocna krawedz prostokata PL biegnie przez Baltyk |

Dostepnosc danych sprawdzona skorowidzem (GetFeatureInfo, parametry z
`GugikProvider._get_opendata_url`) przed wnioskami: arkusze morskie — pusta
odpowiedz na wszystkich 4 warstwach (5 m i 1 m); ladowe — URL. Kampanie 5 m:
Leba 2025-05-20 (warstwa `SkorowidzeNMT2025`), Hel 2023-04-23 (`SkorowidzeNMT2023`,
najnowsza dla Helu — 2025/2024 nie maja tych arkuszy); 1 m Leba 2022-04-28.

Obciazenie: ~210 MB pobran lacznie, ~500 zapytan GetFeatureInfo, 1 GetMap orto.

## Wyniki per scenariusz

| # | Scenariusz | Wynik | Dowod (skrot) |
|---|---|---|---|
| 1 | A: wycinek 5 m `--target-crs EPSG:2180` (CLI) | **PASS** | rc 0, 11,3 s; `Warning:` z 5 arkuszami; `missing_sheets` = te same 5; 0 z 1 682 601 px rozbieznych; nodata 50,0 % wylacznie nad morzem |
| 2 | A1: wycinek 1 m `--target-crs EPSG:2180` (CLI) | **PASS** | rc 0, 45,5 s; `missing_sheets` 2; 0 z 10 006 501 px rozbieznych; faza siatki 1 m = k+0,5 |
| 3 | As: wycinek 5 m `--target-crs EPSG:5514` | **PASS** (1. proba CLI: kod 1 przez blad chwilowy) | 2. proba CLI rc 0, bit w bit rowny wynikowi biblioteki; niezalezna interpolacja: srednio 2,97 mm, maks. 0,150 m |
| 4 | B: Hel 5 m `--target-crs EPSG:2180` — **tresc** (API biblioteki, sesja z ponawianiem) | **PASS** | `missing_sheets` 14; 0 z 2 563 201 px rozbieznych; mierzeja w calosci wazna, nodata tylko nad woda |
| 5 | B: Hel 5 m przez **CLI** | **FAIL (B1)** | 4 proby (w tym `--workers 1` po 3 min przerwy): kod 1, 4/3/9/6 z 25 arkuszy "brak pokrycia niepewny" |
| 6 | D: bbox w calosci nad morzem (CLI) | **PASS** | rc 1, `Error: GUGiK nie ma danych dla zadnego z 2 arkuszy obszaru — wycinek nie powstal` (1. proba: kod 1 przez blad chwilowy) |
| 7 | Tryb listy arkuszy, A, `--workers 2` | **UWAGA (B3)** | rc 1, jeden arkusz morski w `Error:`, 11 arkuszy ladowych + sidecary na dysku, brak podsumowania |
| 8 | Tryb listy arkuszy, A, `--workers 1` | **FAIL (B3)** | rc 1 po PIERWSZYM arkuszu (morski) — nie pobrano nic z 11 dostepnych |
| 9 | (j) surowe odpowiedzi skorowidza + straz OGC w obie strony | **PASS** | sekcja "Checklista (j)" |
| 10 | Wybor kampanii przy bledzie chwilowym (wyszlo w #7) | **FAIL (B2)** | 5 z 11 arkuszy innej tresci niz w przebiegu bez bledow; md5 -> 2023 zamiast 2025 |
| 11 | Puste katalogi arkuszy morskich | UWAGA (B4) | oba tryby: `N-33/48/C/a/1/3` itd. zostaja puste |
| 12 | C: `--country auto` na N krawedzi prostokata PL (offline) | UWAGA (B5) | bbox przyciety do 54,90°N, pozostale krawedzie rozszerzone, inna nazwa pliku, bez `Info:` |
| 13 | Komunikaty CLI przy arkuszach morskich | UWAGA | per arkusz nieprefiksowane `No data for ... Check https://mapy.geoportal.gov.pl` + `✗` w pasku, potem `Warning:` |
| 14 | Niezalezny wglad: ortofotomapa (WMS GetMap) dla A | **PASS** (weryfikacja #1) | zasieg orto nad morzem pokrywa sie z zasiegiem NMT; nodata NMT = woda |

### 1. A — Leba 5 m, EPSG:2180 (CLI) — PASS

`kartograf download --bbox 404000,765000,410000,772000 --resolution 5m --target-crs EPSG:2180 -o ./data --workers 2`
-> rc 0, 11,3 s, maxrss 111 MB. stdout: `Found 16 sheets ...`, pasek (`✗` dla 5 arkuszy),
`Downloaded to data/nmt/pl_1992_5m_evrf2007/bbox/404000_765000_410000_772000.tif`.
stderr: 5 linii `No data for N-33-48-C-a-...` (logger managera) i
`Warning: GUGiK nie ma danych dla 5 arkuszy wycinka (N-33-48-C-a-1-3, N-33-48-C-a-1-4, N-33-48-C-a-2-3, N-33-48-C-a-2-4, N-33-48-C-a-3-1) — w tych miejscach wycinek ma nodata (lista w sidecarze: extra.missing_sheets)`.

- Sidecar: `horizontal_crs EPSG:2180`, `vertical_crs EPSG:9651`, `transform null`,
  `request.bbox` = zadanie, `extra.parent_request` (countries `["PL"]`),
  `extra.missing_sheets` = 5 godel jak wyzej (posortowane). Wynik 6,7 MB, 1201 x 1401 px.
- Siatka: bounds `(403997.5, 764997.5, 410002.5, 772002.5)` — faza 2,5 m, rozszerzenie
  dokladnie 2,5 m na strone (bbox calkowity) — zgodnie z ARCHITECTURE 4.3 pkt 6.
- Wartosci (`check_2180.py`, niezaleznie od kodu mozaiki: srodek piksela -> ASC):
  **0 z 1 682 601** pikseli rozbieznych.
- Nodata 841 526 px (50,0 %): 447 334 w arkuszach `missing_sheets` (100 % ich pikseli),
  394 192 w pobranych arkuszach przybrzeznych — 358 884 POZA rastrem ASC (kampania 2025
  przycina arkusze przybrzezne do zasiegu danych, np. `N-33-48-C-a-3-2` = 207 x 46 px,
  pas 230 m), 35 308 komorek nodata ASC; 0 poza arkuszami zadania. Cale nodata spojne
  z krawedzia rastra (0 zamknietych dziur), krawedz S bez nodata; wazne piksele
  sasiadujace z nodata maja **-0,12..0,21 m** (lustro wody). Jeziora Lebsko i Sarbsko
  maja wartosci (nie nodata). Obraz: `WD/png/A5_2180.png`; niezalezne orto
  `WD/ortho/A_ortho.jpg` (zasieg orto nad morzem = zasieg NMT, bialy brak orto = arkusze
  z `missing_sheets`).

### 2. A1 — Leba 1 m, EPSG:2180 (CLI) — PASS

`kartograf download --bbox 406000,767500,408500,771500 --resolution 1m --target-crs EPSG:2180 -o ./data --workers 2`
-> rc 0, 45,5 s, 4 arkusze po 24-26 MB; `Warning:` z `N-33-48-C-a-1-4, N-33-48-C-a-2-3`;
sidecar `dataset pl.gugik.nmt_1m`, `missing_sheets` j.w. Wynik 2501 x 4001 px (40 MB).
Siatka: bounds `(405999.5, 767499.5, 408500.5, 771500.5)` — **arkusze 1 m maja naroznik
pikseli na k+0,5 m** (wszystkie 4, kampania 2022, EVRF2007), wiec wycinek rozszerza
bbox calkowity o 0,5 m na strone (dane do checklisty (f)). **0 z 10 006 501** pikseli
rozbieznych. Nodata 19,0 %: 1 899 789 px = dokladnie arkusze `missing_sheets`, 165 px to
komorki nodata ASC na styku z nimi; 0 dziur; wazne przy nodata -0,14..0,25 m.
Uwaga o danych: w 1 m arkusz przybrzezny `N-33-48-C-a-3-2` to PELNY arkusz 2058 x 2360 px
z powierzchnia morza -0,20..0,25 m (w 5 m ten sam arkusz to pas 230 m) — ponad 2 km
otwartego morza ma w wycinku 1 m wartosci ~0 m, nie nodata (`WD/png/A1_2180_small.png`).

### 3. As — Leba 5 m, EPSG:5514 — PASS (z zastrzezeniem B1)

1. proba CLI (`... --bbox 405000,766000,409000,771000 --resolution 5m --target-crs EPSG:5514 ...`,
po 6 min przerwy): rc 1 — `Error: 1 z 12 arkuszy nie pobrano (blad pobrania, nie brak danych):
N-33-48-C-a-2-3 — wycinek nie powstal; ponow pobranie` (arkusz morski, zerwane polaczenie na
warstwie 2025). Te same kroki przez API biblioteki (`lib_cutout_retry.py`, sesja z
ponawianiem) — OK od razu; potem (wynik biblioteki odsuniety do `WD/lib_results/`)
2. proba CLI: rc 0, 2,7 s, `Warning:` z 4 arkuszami, plik
`bbox/-473171.8076_-551725.4553_-468799.1025_-546422.1439.tif` (875 x 1061 px).
- CLI vs biblioteka: piksele **bit w bit** identyczne, transform/CRS rowne, sidecary
  roznia sie tylko `downloaded_at`.
- Sidecar: `horizontal_crs EPSG:5514`, `transform.horizontal = "pinned: axis order change (2D)
  + Inverse of Poland CS92 + ETRF2000-PL to ETRS89 (1) + Inverse of S-JTSK to ETRS89 (3) +
  Krovak East North (Greenwich) (0.5 m)"`, `request.bbox` w 5514 (= `bbox_target`),
  `parent_request` w 2180, `missing_sheets` 4 godla.
- Krawedzie: E +2,30 m, S -1,69 m wobec `bbox_target` (<= 0,5 px — zgodnie z 4.3 pkt 6).
- Niezaleznie (`check_warp.py`: wlasna mozaika ASC, operacja pyproj o tym samym opisie,
  wlasna dwuliniowa 2x2): 465 182 px waznych w obu — |roznica| srednio **2,97 mm**,
  mediana 0,99 mm, p99 34 mm, maks. **0,150 m** (1821 px > 5 cm — wylacznie strome zbocza
  wydm, `WD/png/A5s_5514.png`); 0 px waznych w wyniku bez waznego zrodla; 0 px nodata
  w wyniku przy pelnym waznym 2x2 zrodla; nodata 49,8 % — 462 159 px bez waznego zrodla,
  523 px krawedz danych. Zgodne z E2E offline (2,7 mm / 0,15 m).

### 4-5. B — Hel 5 m, EPSG:2180 — tresc PASS, CLI FAIL (B1)

CLI `kartograf download --bbox 475000,755000,483000,763000 --resolution 5m --target-crs EPSG:2180 -o ./data --workers 2`:

| Proba | Kiedy | rc | Zerwane zapytania GFI | Arkusze "brak pokrycia niepewny" |
|---|---|---|---|---|
| 1 | 09:36 | 1 | 5 (+ GetCapabilities) | 4 z 25 |
| 2 | 09:38 (po 60 s) | 1 | 3 | 3 z 25 |
| 3 | 09:42 (po 3 min, `--workers 1`) | 1 | 13 | 9 z 25 (`d-1-1`, `d-1-2`: 2 z 4 warstw; `d-3-4`: 3 z 4) |
| 4 | 09:56 | 1 | 9 | 6 z 25 (jeden: `all 4 layer queries failed`) |

Za kazdym razem `Error: N z 25 arkuszy nie pobrano (blad pobrania, nie brak danych): ...
— wycinek nie powstal; ponow pobranie`, pliku wyniku brak, arkusze ladowe zostaja jako
cache. Zachowanie R5 jest POPRAWNE (chwilowy blad nie robi trwalej dziury), ale
uzytkownik nie dostanie tego wycinka z CLI — patrz B1.

Tresc przez API biblioteki (`prepare_pl_cutout` -> `select_pl_cutout_sheets` ->
`run_pl_cutout`, wstrzykniety `GugikProvider(session=...)` z jedna sesja keep-alive
i `urllib3.Retry(total=4, backoff_factor=1)`, `max_workers=1`, `force=False`):
OK w 8,1 s, **56 GetFeatureInfo, 0 ponowien**; `missing_sheets` (14):
`N-34-38-C-c-4-2, -c-4-4, -d-1-1, -d-1-2, -d-2-1, -d-2-2, -d-2-3, -d-2-4, -d-3-3, -d-3-4,
N-34-50-A-a-2-2, -A-b-1-1, -A-b-1-2, -A-b-2-1` (wynik: `WD/lib_results/B5_2180_lib.tif`).
- Siatka 1601 x 1601, faza 2,5, rozszerzenie 2,5 m/strone; **0 z 2 563 201** px rozbieznych.
- Nodata 62,1 %; 0 dziur; spojne z krawedziami N/W/E/S (morze po obu stronach mierzei);
  wazne przy nodata -0,36..1,06 m. Mierzeja w calosci wazna (`WD/png/B5_2180.png`).
- 1169 waznych px wewnatrz graticule arkuszy z `missing_sheets` — wszystkie <= 2,6 m
  (pol piksela) od krawedzi arkusza, wartosci 0,00..0,30 m: to piksele brzegowe ASC
  sasiada, ktorych srodek wypada tuz za linia arkusza. Nie defekt.
- Arkusze Helu w cache to kampania 2023 = najnowsza dla tego obszaru (md5 sprawdzone na
  2 z 11 arkuszy, `runlog/vintage_probe_hel.txt`; 2025/2024 nie maja arkuszy Helu, wiec
  zerwana warstwa 2025 niczego tu nie zmienila) — B2 tu nie wystapil.

### 6. D — bbox w calosci nad morzem — PASS

`... --bbox 404000,771000,407000,772500 --resolution 5m --target-crs EPSG:2180 -o ./data_allsea`:
1. proba rc 1 przez blad chwilowy (`1 z 2 arkuszy nie pobrano`); ponowienie po 30 s:
rc 1, `Error: GUGiK nie ma danych dla zadnego z 2 arkuszy obszaru — wycinek nie powstal`
(zgodnie z 4.3 pkt 4). Brak katalogu `bbox/`; zostaja 2 puste katalogi arkuszy (B4).

### 7-8. Tryb listy arkuszy (bez `--target-crs`), bbox A — UWAGA / FAIL (B3)

`--workers 2`, swiezy katalog `-o ./data_list_w2`: rc 1 po 8,8 s. stdout tylko `Found 16
sheets ...` (w trybie listy arkuszy 1:10000 nie ma paska postepu ani podsumowania
`Downloaded N files`). stderr: seria `WMS query failed ...` (bledy chwilowe) i
`Error: No NMT 5m data available for N-33-48-C-a-1-3 (vertical_crs=EVRF2007). This area may
not have 5m coverage in GUGiK. Check https://mapy.geoportal.gov.pl for data availability.` —
JEDEN z 5 arkuszy morskich, reszta bledow zgubiona. Na dysku: 11 arkuszy ladowych
+ 11 sidecarow (z `parent_request`) + 5 pustych katalogow.

`--workers 1`, swiezy `-o ./data_list_w1`: rc 1 po 1,2 s, ten sam `Error:` dla
`N-33-48-C-a-1-3` — pierwszego godla na liscie; **nie pobrano nic** (0 plikow, 1 pusty
katalog). Uzytkownik czyta to jako "brak danych 5 m dla obszaru", a 11 z 16 arkuszy ma
dane.

Ocena uzytkownika: bbox przybrzezny w trybie listy NIGDY nie konczy sie kodem 0
(ponowienie: arkusze z dysku sa pomijane, morskie znow koncza sie bledem); wynik zalezy
od `--workers`; komunikat sugeruje brak pokrycia calego obszaru. R5 (brak danych = nie
blad) dziala tylko w torze wycinka. ARCHITECTURE 4.2 mowi ogolnie "Nieudany arkusz konczy
polska czesc zadania kodem 1" — nie mowi, ze sekwencyjnie przerywa liste, ani ze morze to
"nieudany arkusz".

### 9. Checklista (j) — PASS (szczegoly w sekcji "Checklista (j)")

### 10. Kampania przy bledzie chwilowym — FAIL (B2)

Przebieg #7 (z bledami chwilowymi) pobral 5 z 11 arkuszy o INNEJ tresci niz przebieg #1
(bez bledow): `N-33-48-C-a-3-4, -a-4-2, -a-4-4, -c-2-1, -c-2-2` (md5). Dla dwoch
zweryfikowane pobraniem kazdej kampanii ze skorowidza (`vintage_probe.py`, md5 calego pliku):

| Arkusz | Przebieg bez bledow | Przebieg z bledem chwilowym warstwy 2025 |
|---|---|---|
| `N-33-48-C-a-4-2` | 2025-05-20 (`83885_1835902_...`), 405 x 180 px | 2023-04-20 (`78969_1471904_...`), 412 x 473 px |
| `N-33-48-C-a-3-4` | 2025-05-20 (`83885_1835900_...`), 412 x 468 px | 2023-04-20 (`78969_1471902_...`), 413 x 473 px |

Roznice wysokosci na wspolnych pikselach: mediana |d| 0,05 m, p99 0,67 / 1,44 m,
**maks. 2,98 / 5,20 m** (wydmy/plaza — brzeg morski zmienia sie miedzy nalotami),
plus inny zasieg. Sidecar arkusza ma tylko `request = {godlo}` — nie da sie tego wykryc
po fakcie, a arkusz zostaje w cache i trafia do kolejnych wycinkow. Potwierdza i
zaostrza L5-B5 (tam wartosci byly identyczne).

### 11-14. Pozostale

- **Puste katalogi (B4):** kazdy arkusz morski zostawia pusty katalog w segmencie
  (`data/nmt/pl_1992_5m_evrf2007/N-33/48/C/a/1/3` itd.) — w wycinku, w liscie i przy
  porazce; `bbox/` nie powstaje przy porazce (OK).
- **`--country auto` na polnocy (B5, offline — te same funkcje co CLI: `_country_bbox`,
  `prepare_pl_cutout`):** bbox `455000,773000,459000,784000` (Rozewie, siega 54,918°N):
  czesc PL = `(454889.745, 772961.805, 459082.21, 782063.508)` — N przyciety o 1,94 km
  do 54,90°N, a W/S/E ROZSZERZONE o 110/38/82 m (obwiednia po podrozy przez WGS84);
  plik `454889.7446_772961.8054_459082.2099_782063.5079.tif`, 15 arkuszy; z
  `--country pl`: `455000_773000_459000_784000.tif`, 18 arkuszy. Bez komunikatu `Info:`.
  Dla A (ponizej 54,90°N) auto == pl (bez zmian).
- **Komunikaty:** kazdy arkusz morski daje na stderr nieprefiksowana linie loggera
  (`logging.lastResort`) `No data for ...: ... This area may not have 5m coverage in GUGiK.
  Check https://mapy.geoportal.gov.pl ...`, a pasek postepu pokazuje `✗` — przy Helu byloby
  14 takich linii przed jednym `Warning:`. Oczekiwany stan (morze) wyglada jak blad.
  Bledy chwilowe tez ida nieprefiksowane (`WMS query failed ...`, `Failed to download ...`,
  `Failed to fetch WMS GetCapabilities ...`).
- **Orto:** jedno zapytanie GetMap (600 x 700 px); 1. proba `ConnectionResetError`,
  ponowienie po 20 s OK.

## Bledy

### B1 — zapytania skorowidza bez ponowien i na nowym polaczeniu per arkusz: wycinki przy morzu nie przechodza przez CLI

- **Reprodukcja:** `cd WD && kartograf download --bbox 475000,755000,483000,763000 --resolution 5m --target-crs EPSG:2180 -o ./data --workers 2`
  (dzis 09:36-09:57). **Wynik:** 4/4 proby rc 1, `Error: N z 25 arkuszy nie pobrano (blad
  pobrania, nie brak danych) ...`, N = 3..9. **Oczekiwane:** chwilowe zerwanie polaczenia
  ponawiane jak przy pobieraniu ASC (`_download_with_retry`: 3 proby z backoffem);
  wycinek z kodem 0 i 14 `missing_sheets`.
- **Mechanizm:** arkusz morski wymaga odpowiedzi WSZYSTKICH 4 warstw (ladowy — zwykle
  jednej), wiec podatnosc rosnie z liczba arkuszy morskich/przygranicznych; wynik
  `NoCoverageError` nie jest zapamietywany, wiec rada "ponow pobranie" powtarza caly
  zestaw zapytan z tym samym ryzykiem. Bledy to `RemoteDisconnected('Remote end closed
  connection without response')` / `ConnectionResetError` — prawie zawsze na PIERWSZYM
  zapytaniu nowej sesji (warstwa 2025) i na zapytaniach po bledzie (nowe polaczenie).
- **Dowod roznicowy (ten sam czas, te same arkusze):** biblioteka z jedna
  `requests.Session` (keep-alive) + `urllib3.Retry` — Hel 56 i Leba 16 zapytan, **0 bledow,
  0 ponowien** (09:51); CLI w tych samych minutach (09:50-09:57) — od 0 do ~30 % zapytan
  zerwanych na przebieg (5514 #1: 1/16, lista w2: 12/~40, 5514 #2: 0/16, Hel #4: 9/~56).
  Przejsciowe zrywania zglaszaja tez L5 (B3) i L6.
- **Hipoteza (file:line):** `kartograf/providers/pl/gugik.py:519`
  (`session = self._session or requests.Session()` — nowa sesja, wiec nowe polaczenie
  TCP/TLS, na kazde wywolanie `_get_opendata_url`, czyli na kazdy arkusz), `:572`
  (`session.get(url, timeout=timeout)` bez ponowien), `:618-622` (`RequestException` ->
  `transport_errors += 1; continue`); GetCapabilities `:298` (tez nowa sesja — 4 razy
  dzis `Failed to fetch WMS GetCapabilities ... Using hardcoded WMS_LAYERS`).

### B2 — blad chwilowy nowszej warstwy = cicho starsza kampania

- **Reprodukcja:** dwa przebiegi tego samego zadania do swiezych katalogow; gdy w drugim
  zapytanie warstwy 2025 dla arkusza ladowego zostanie zerwane
  (`WMS query failed for layer SkorowidzeNMT2025: ...`), arkusz przychodzi z 2023
  (tabela w #10). **Oczekiwane:** zerwana nowsza warstwa to "wynik niepewny" (ponowienie
  albo `DownloadError`), jak juz jest dla brakow pokrycia (`gugik.py:632-641`); co najmniej
  URL/kampania w sidecarze arkusza.
- **Hipoteza:** `kartograf/providers/pl/gugik.py:582-588` — pierwszy znaleziony URL jest
  zwracany bez sprawdzenia `transport_errors` z wczesniejszych (nowszych) warstw; zapis do
  `MetadataCache` (`_cache_url`, jesli podany) utrwala go na 7 dni; sidecar arkusza
  (`download/manager.py:333` i `:517`, `request = {"godlo": ...}`) nie niesie URL ani kampanii.

### B3 — tryb listy arkuszy przy morzu: kod 1 zawsze, `--workers 1` nie pobiera nic, gubione bledy

- **Reprodukcja:** `kartograf download --bbox 404000,765000,410000,772000 --resolution 5m -o ./data_list_w1 --workers 1`
  -> rc 1, 0 plikow; z `--workers 2` -> rc 1, 11 plikow, `Error:` tylko dla jednego arkusza.
  **Oczekiwane (propozycja):** jak w R5 — arkusze bez danych jako `Warning:` z lista,
  pozostale pobrane, kod 0; albo przynajmniej pelne pobranie i zbiorczy `Error:` z lista
  (jak `_report_failed_sheets` w sciezce hierarchii).
- **Hipoteza:** `kartograf/cli/download_cmd.py:849-857` (sekwencyjnie
  `manager.download_sheet` rzuca `NoCoverageError` i przerywa petle), `:904-905`
  (`except (DownloadError, ValidationError): raise` w petli `as_completed` — tylko pierwszy
  wyjatek, pula i tak konczy reszte), `:1145-1147` (`\nError: {e}`, kod 1, bez
  podsumowania). Zbiezne z L6 BUG-1/1b.

### B4 (drobny) — puste katalogi po arkuszach bez danych

`kartograf/providers/pl/gugik.py:448` — `output_path.parent.mkdir(...)` przed
`_get_opendata_url`; ani manager, ani `run_pl_cutout` nie sprzata. Przy wycinku przy
morzu/granicy drzewo `data/` rosnie o puste galezie.

### B5 (dokumentacja/UX) — `--country auto` zmienia bbox na N krawedzi prostokata PL

`kartograf/cli/download_cmd.py:282-342` (`_country_bbox`, przyciecie w WGS84 i obwiednia
z powrotem): wynik przy bboxie siegajacym na N od 54,90°N (tylko morze) ma inny zasieg
i inna nazwe pliku niz zadanie, bez komunikatu. Zadnych danych to nie odbiera (tam jest
tylko morze), ale konsument szukajacy pliku po wspolrzednych zadania go nie znajdzie,
a siatka nie pokrywa sie z zadaniem. Propozycja: `Info:` o przycieciu i/lub nieposzerzanie
krawedzi, ktorych przyciecie nie dotyczy.

## Zachowanie do udokumentowania

1. **Skad nodata nad morzem (4.3):** (a) arkusze z `missing_sheets` (brak pliku),
   (b) czesc arkusza przybrzeznego poza jego rastrem — kampania 5 m 2025 przycina rastry do
   zasiegu danych (Leba: `N-33-48-C-a-3-2` = 207 x 46 px), (c) komorki nodata w ASC
   (kampania 2023: pelne arkusze z nodata nad morzem). `missing_sheets` wymienia tylko (a);
   `nodata` wycinka wiec NIE rowna sie `missing_sheets`.
2. **Woda ma wartosci:** przy brzegu NMT ma lustro wody ~0 m (-0,4..+0,3 m) — w 5 m pas
   kilkuset metrow, w 1 m (Leba, 2022) CALY arkusz przybrzezny (>2 km morza). W Zatoce
   Puckiej arkusze przybrzezne maja wode ~0 m, a sasiednie czysto zatokowe — nodata:
   granica nodata/woda biegnie po krawedziach arkuszy, nie po linii brzegowej. Jeziora
   (Lebsko, Sarbsko) maja wartosci.
3. **Skorowidz przy brzegu:** poligony skorowidza to pelne arkusze — zapytanie w srodku
   arkusza przybrzeznego (nad morzem) zwraca arkusz, mimo ze dane leza tylko w pasie przy
   S krawedzi (sprawdzone na `N-33-48-C-a-3-2`). Odpowiedz niesie tez atrybuty nieuzywane
   przez Kartograf: `aktualnosc`, `calyArkuszWypelnionyTrescia` (TAK/NIE), `bladSredniWysokosci`.
4. **Faza siatki 1 m:** k+0,5 m (4 arkusze kampanii 2022, Leba) — wycinek 1 m bboxa
   calkowitego jest szerszy o 0,5 m na strone (5 m: 5k+2,5 m, 2,5 m na strone).
5. **Tryb listy przy morzu/granicy:** kod 1, zaleznosc od `--workers`, brak paska
   postepu i podsumowania dla arkuszy 1:10000 (B3) — dopoki nie poprawione, warto to
   opisac w CLAUDE.md/README (np. "dla obszarow przybrzeznych uzyj `--target-crs`").
6. **`--country auto` przycina do prostokata kraju** takze od strony morza (54,90°N) —
   i poszerza pozostale krawedzie (B5); `--country pl` = bbox 1:1.
7. **Tor CLI PL NMT nie uzywa `MetadataCache`** (`create_nmt_provider(cache=None)`,
   cache tylko w torze CZ, `download_cmd.py:1604-1636`) — `.kartograf_cache.db` nie powstaje
   (LIVE-COMMON zaklada inaczej).
8. **Odpowiedzi skorowidza** (dla przyszlych fixtur/kontroli pozytywnej) — sekcja nizej.

## Checklista (j) — surowe odpowiedzi GetFeatureInfo

Skrypt `WD/gfi_probe.py`: podklasa `requests.Session` zapisujaca kazda odpowiedz,
`GugikProvider(session=...)`, wywolanie `_get_opendata_url` (parametry z kodu); arkusz
morski `N-33-48-C-a-1-4`, ladowy `N-33-48-C-a-3-4`; zla warstwa przez podstawienie
`_validated_layers` = `["SkorowidzeNMT1999NieIstnieje"]`. GetCapabilities (osobna sesja
providera): warstwy 5 m i 1 m = hardcoded `WMS_LAYERS` (bez ostrzezenia).

| Przypadek | HTTP | Content-Type | Body | Znaczniki OGC | Wynik providera |
|---|---|---|---|---|---|
| morze, 5 m (4 warstwy) i 1 m (4 warstwy) | 200 | `text/html` (bez charset; Content-Length 2456 = rozmiar po kompresji transferu) | 7721 B, szablon HTML MapServera bez obiektow; md5 `bd860cc6d75ba4ee1ac5200edb387f55`, identyczny dla OBU endpointow i wszystkich warstw | brak | `NoCoverageError` |
| lad, 5 m (warstwa 2025) | 200 | `text/html` | 8887 B, szablon + `skor_NMT_wg_akt.push({url:"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/83885/83885_1835900_N-33-48-C-a-3-4.asc", ..., aktualnosc:"2025-05-20", ..., calyArkuszWypelnionyTrescia:"TAK", ...})` | brak | URL |
| lad, 1 m (2026/2025/2024 puste, 2023iStarsze z URL) | 200 | `text/html` | 7721 B x3, potem 8911 B (`76625_1257614_...`, 2022-04-28) | brak | URL |
| zla warstwa (5 m i 1 m) | **200** | `text/xml; charset=UTF-8` | 554 B: `<ServiceExceptionReport version="1.3.0" ...><ServiceException code="LayerNotDefined">msWMSLoadGetMapParams(): WMS server error. Invalid layer(s) given in the LAYERS parameter. ...` | `ServiceException`, `ExceptionReport` | `DownloadError: GUGiK WMS skorowidz unavailable ... all 1 layer queries failed (last error: warstwa ...: raport wyjatku OGC w odpowiedzi HTTP 200: msWMSLoadGetMapParams(): ...)` |
| zla + 4 prawdziwe, morze | 200/200 | j.w. | j.w. | tylko w zlej | `DownloadError: ... 1 z 5 warstw nie odpowiedzialo ... brak pokrycia niepewny` (NIE `NoCoverageError`) |
| zla + 4 prawdziwe, lad | 200/200 | j.w. | j.w. | tylko w zlej | URL z warstwy 2025 |

Straz w obie strony: pusta odpowiedz NIE zawiera `ServiceException`/`ExceptionReport`
(R5 dziala — wycinki przy brzegu powstaja), raport wyjatku zawiera oba i przychodzi
z HTTP 200 (bez strazy bylby "brakiem arkusza"). Kandydat na kontrole pozytywna: kazda
poprawna odpowiedz (pusta i z obiektami) zawiera szablon z `function createTable
(skor_NMT_wg_akt)` i `</body>`, obiekty dodaja `skor_NMT_wg_akt.push(` — wymog sygnatury
szablonu odroznilby strone bledu z HTTP 200 bez znacznikow OGC, kosztem zaleznosci od
szablonu GUGiK. Uwaga poboczna: `text/html` bez charset -> `requests` dekoduje UTF-8
jako ISO-8859-1 (polskie znaki znieksztalcone); dla regexu URL i znacznikow (ASCII) bez
znaczenia. Strona czeska (drugi przypadek z (j)) — zakres L4.

## Surowe artefakty (`WD` = `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L3-morze`)

- Logi przebiegow CLI: `WD/runlog/<tag>.{cmd,out,err,rc,time}` — `A5_2180`, `A1_2180`,
  `B5_2180`, `B5_2180_retry`, `B5_2180_retry2_w1`, `B5_2180_cli4`, `A5s_5514`,
  `A5s_5514_cli2`, `D5_allsea`, `D5_allsea_retry`, `A5_list_w1`, `A5_list_w2`;
  weryfikacje: `WD/runlog/*.check`; biblioteka: `WD/runlog/{A5s_5514_lib,B5_2180_lib}.lib.{log,json}`;
  offline B5: `WD/runlog/C_offline_clip.txt`; kampanie: `WD/runlog/vintage_probe{,_hel}.txt`.
- (j): `WD/gfi/NN_<przypadek>_<warstwa>.body` (22 surowe body) + `WD/gfi/index.json`
  (URL, status, Content-Type, dlugosci, znaczniki, wyniki), `WD/gfi_probe.log`.
- Wyniki: `WD/data/nmt/pl_1992_5m_evrf2007/bbox/404000_765000_410000_772000.tif`,
  `WD/data/nmt/pl_1992_1m_evrf2007/bbox/406000_767500_408500_771500.tif`,
  `WD/data/nmt/pl_1992_5m_evrf2007/bbox/-473171.8076_-551725.4553_-468799.1025_-546422.1439.tif`
  (CLI), `WD/lib_results/{B5_2180_lib,A5s_5514_lib}.tif` (+ `.meta.json`); tryb listy:
  `WD/data_list_w1/`, `WD/data_list_w2/`; morze: `WD/data_allsea/`.
- Obrazy: `WD/png/{A5_2180,A1_2180_small,A5s_5514,B5_2180}.png`, `WD/ortho/A_ortho.jpg`.
- Skrypty: `WD/run.py`, `WD/check_2180.py`, `WD/check_warp.py`, `WD/lib_cutout_retry.py`,
  `WD/disk_state.py`, `WD/vintage_probe.py`, `WD/gfi_probe.py`.
