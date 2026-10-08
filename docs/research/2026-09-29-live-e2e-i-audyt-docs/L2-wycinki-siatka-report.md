# L2-wycinki-siatka — wycinek NMT PL `--target-crs` na zywych danych GUGiK (2026-09-29)

**Status: mechanika wycinka DZIALA, tresc NIE jest wiarygodna.** Siatka, crop, warp, sidecar,
"Skipped", `--force` i API biblioteki zachowuja sie zgodnie z ARCHITECTURE 4.3 na realnych arkuszach
1 m i 5 m (12 wycinkow zweryfikowanych piksel po pikselu). Wyboru PLIKU arkusza w
`GugikProvider._get_opendata_url` nie da sie jednak obronic: na zywo dostarcza on po cichu
starsze kampanie (przy chwilowych bledach GUGiK), pliki 0,5 m w miejsce 1 m (wycinek "1m" w 0,5 m,
w skrajnym przypadku 100 % nodata z kodem 0) oraz arkusz-dziecko PL-2000 w miejsce zadanego.

Liczniki: **PASS 21, FAIL 6, UWAGA 5** (32 scenariusze). HEAD 152c31e, repo nietkniete
(`git status` czysty). Pobrano ok. 0,85 GB (limit 3 GB), `--workers 2`.

---

## 1. Zakres

| Obszar | Bbox / godla | Dlaczego |
|---|---|---|
| **1 m** — arkusz `N-34-130-D-d-2` (22,94-23,00°E, 52,375-52,42°N; w praktyce okolice Siemiatycz/Drohiczyna, ok. 70 km na S od Bialegostoku) | calkowity `768900,509730,770900,511730` (EPSG:2180, 2 x 2 km, na styku 4 arkuszy `-2-1..-2-4`); ulamkowy `22.955,52.388,22.985,52.405` (EPSG:4326 -> 2143,3 x 2001,3 m) | WMS (sprawdzony przed pobraniem, `wms_samples/probe_areas.json`): EVRF2007 1 m = 2025 (praca 82710) + 2024 + 2022; KRON86 1 m = 2013 (praca 4042); 5 m brak. Styk 4 arkuszy = szwy w kazdym wycinku |
| **5 m** — `N-34-141-A-a` (22,00-22,125°E, 52,25-52,33°N; okolice Wegrowa/Liwu, ok. 65 km na E od Warszawy) | calkowity `703000,491000,713000,501000` (10 x 10 km; 36 arkuszy dla 2180, 42 dla 5514/3045); ulamkowy `21.99,52.255,22.13,52.345` (EPSG:4326 -> 9963,5 x 10407,5 m; 30/42/36 arkuszy) | WMS: 5 m z kampanii 2024 i 2025 (sasiednie arkusze z roznych kampanii), 1 m EVRF2007 brak |
| (f) probka kraju | 12 punktow: Szczecin, Gdansk, Olsztyn, Suwalki, Poznan, Warszawa, Lublin, Wroclaw, Katowice, Rzeszow, Zielona Gora, Lodz — wszystkie rekordy skorowidza 1 m EVRF2007 (4 warstwy) i KRON86 (3 warstwy) + naglowki 92 plikow ASC (strumien przerywany po 6 liniach) | faza siatki dla wszystkich kampanii i obu ukladow wysokosci; czestosc rekordow PL-2000 |
| (g) przypadki znalezione w probce | Zielona Gora `M-33-8-A-a-3-1` (KRON86, bbox `260000,458600,261200,459800`); Szczecin `N-33-90-C-c-2-2` (bbox `207700,624000,208800,625300`), `-c-2-4` (`207500,621500,208500,622500`), `-c-2-4`+`C-d-1-3` (`209000,622000,209800,622800`) | jedyny arkusz probki z fallbackiem PL-2000; jedyny z plikiem 0,5 m wybieranym zamiast 1 m |

Metoda weryfikacji tresci (skrypty w katalogu roboczym):
- **EPSG:2180** (`verify_2180.py`): zasieg wobec zadania, faza siatki arkuszy i wycinka, dla KAZDEGO
  piksela wartosc = wartosc pierwszego (w kolejnosci posortowanych sciezek) arkusza z wazna wartoscia
  w srodku piksela; osobno liczone zakladki arkuszy i piksele bez danych.
- **EPSG:5514/3045** (`verify_warp.py`, `verify_warp2.py`): (1) niezalezna obwiednia celu (401 punktow
  na krawedz) -> naroznik NW i liczba pikseli; (2) punktowo — 62 000 srodkow pikseli -> EPSG:2180
  odwrotnoscia operacji przypietej (`build_pinned_transform`, ta sama polityka) -> WLASNY bilinear na
  WLASNEJ mozaice numpy; (3) niezalezny warp GDAL kazdego arkusza z ta sama operacja
  (`COORDINATE_OPERATION`); (4) warp calej wlasnej mozaiki z opcjami domyslnymi, z `XSCALE=YSCALE=1`,
  z `tolerance=0` i z obiema — rozklad roznicy na przyczyny.

## 2. Wyniki per scenariusz

### (d) wycinki

| # | Scenariusz | Wynik | Dowod |
|---|---|---|---|
| S1 | 1 m, bbox calk., `EPSG:2180` | **PASS** | exit 0, ~35 s (4 arkusze, 151 MB). 2001 x 2001 px, bounds `768899.5..770900.5 x 509729.5..511730.5` = zadanie + 0,5 m z kazdej strony; faza arkuszy i wycinka 0,5 px; nodata 0; **0 z 4 004 001** pikseli rozbieznych z arkuszem zawierajacym srodek piksela. Plik arkusza `-2-4` bajt w bajt = niezalezne pobranie `curl` z URL skorowidza (`wms_samples/indep_*`) |
| S2 | 1 m, bbox calk., `EPSG:5514` | **UWAGA** (poprawny; opcje domyslne GDAL — sekcja 4 pkt 3) | 2157 x 2157 px; naroznik NW = niezalezna obwiednia (co do 0,1 mm), krawedz E/S -0,10 m; nodata 0. Warp wlasnej mozaiki z ta sama operacja = wycinek **bit w bit (4 652 649/4 652 649)**; z `XSCALE=YSCALE=1`+`tolerance=0` = wlasny bilinear co do 0,01 mm. Wycinek vs dokladny bilinear: srednio 2,78 mm, p99 15,3 mm, maks. 0,236 m (opcje domyslne GDAL, sekcja 4 pkt 3); vs warp per arkusz: srednio 1,77 mm, maks. 0,133 m dalej niz 1 px od szwu. Kontrola czulosci: przesuniecie zrodla o 1 px = 48 mm srednio |
| S3 | 1 m, bbox calk., `EPSG:3045` | **PASS** | 2114 x 2114 px, krawedz E/S -0,29 m, nodata 0, mozaika+warp bit w bit; punktowo srednio 0,13 mm, maks. 3,3 mm (tylko `tolerance`, sekcja 4 pkt 3) |
| S4 | 1 m, bbox `EPSG:4326`, `EPSG:2180` | **PASS** | nazwa `768920.5449_509812.5422_771063.8243_511813.8636.tif`; 2144 x 2002 px; rozszerzenie W/S/E/N = 0,045 / 0,042 / 0,676 / 0,636 m (< 1 px, >= 0); 0 z 4 292 288 rozbieznych, nodata 0 |
| S5 | 1 m, bbox `EPSG:4326`, `EPSG:5514` | **PASS** | 2300 x 2170 px, E -0,42 m / S +0,25 m, nodata 0; punktowo srednio 2,84 mm, maks. 71 mm; warp per arkusz srednio 1,69 mm |
| S6 | 1 m, bbox `EPSG:4326`, `EPSG:3045` | **UWAGA** (poprawny; wygladzanie zalezne od bboxa) | 2258 x 2124 px, nodata 0, mozaika+warp bit w bit. Punktowo srednio 1,49 mm, maks. 43 mm — ten sam uklad i obszar co S3 (0,13 mm), ale GDAL dobral tu `XSCALE<1` (wygladzanie): wynik zalezy od bboxa |
| S7 | 5 m, bbox calk., `EPSG:2180` | **PASS** (po 1 ponowieniu) | 1. przebieg: exit 1 po 44,7 s — 7 zerwanych zapytan warstw, `N-34-129-C-c-3-4`: "3 z 4 warstw nie odpowiedzialo ... brak pokrycia niepewny" -> `Error: 1 z 36 arkuszy nie pobrano (blad pobrania, nie brak danych) ... wycinek nie powstal; ponow pobranie` (R5 poprawnie). Ponowienie: exit 0, 10,9 s (35 z cache). 2001 x 2001 px po 5 m, +2,5 m z kazdej strony, faza 0,5 px (narozniki 5k+2,5), nodata 0, **0 z 4 004 001** rozbieznych. Zakladki: 10 471 px z danymi w >= 2 arkuszach, 884 z ROZNA wartoscia (rozne kampanie; wygrywa arkusz pierwszy w sortowaniu). Arkusz `N-34-128-D-d-4-4` trafil jednak jako kampania 2024 zamiast 2025 (BUG-L2-1) |
| S8 | 5 m, bbox calk., `EPSG:5514` | **PASS** | 2156 x 2156 px, E/S +2,09 m (0,42 px), nodata 0, bit w bit; punktowo srednio 3,21 mm, maks. 95 mm |
| S9 | 5 m, bbox calk., `EPSG:3045` | **PASS** | 2113 x 2113 px, E/S -0,84 m, nodata 0, bit w bit; punktowo srednio 0,73 mm, maks. 28 mm |
| S10 | 5 m, bbox `EPSG:4326`, `EPSG:2180` | **PASS** | 1993 x 2082 px, rozszerzenie 1,41 / 1,62 / 0,05 / 0,88 m, 0 z 4 149 426 rozbieznych, nodata 0 |
| S11 | 5 m, bbox `EPSG:4326`, `EPSG:5514` | **PASS** | 2155 x 2237 px, E +1,45 / S +2,35 m, nodata 0, bit w bit; punktowo srednio 3,24 mm |
| S12 | 5 m, bbox `EPSG:4326`, `EPSG:3045` | **PASS** | 2110 x 2194 px, E -2,08 / S -1,86 m, nodata 0, bit w bit; punktowo srednio 1,44 mm |
| S13 | Sidecary wszystkich wycinkow | **PASS** | `horizontal_crs` = uklad docelowy; `vertical_crs` EPSG:9651 (EVRF2007) / EPSG:9650 (KRON86); `transform` = `null` dla 2180, `pinned: ... Krovak East North (Greenwich) (0.5 m)` dla 5514, `pinned: ... UTM zone 33N + axis order change (2D) (0.0 m)` dla 3045; `request` = `bbox_target` w ukladzie docelowym z `bbox_crs` = cel; `extra.parent_request` = oryginal (bbox, `bbox_crs` EPSG:2180 albo EPSG:4326, `countries: ["PL"]`); brak `missing_sheets` (brak arkuszy bez danych). Tabela: `logs/cutouts_table.txt` |
| S14 | Ponowne uruchomienie bez `--force` (1 m 5514, 5 m 2180) | **PASS** | `Skipped - already exists at ...`, exit 0, 0,4 s, **siec zablokowana** (`HTTPS_PROXY=http://127.0.0.1:9`, sprawdzone, ze blokuje), sha256 i mtime wyniku i arkuszy bez zmian |
| S15 | `--force` (5 m, 2180) — mechanika | **PASS** | 1. przebieg: exit 1 (`N-34-141-A-a-1-1`: "all 4 layer queries failed"), 35 arkuszy pobranych ponownie (mtime), **poprzedni wycinek nietkniety** (`cmp` identyczny), brak plikow tymczasowych, stary arkusz `-a-1-1` zostaje. Ponowienie: exit 0, 27,6 s, 36 arkuszy pobranych ponownie, wycinek przebudowany (nowy mtime), wartosci 1:1 z NOWYMI arkuszami (0 z 4 004 000 rozbieznych) |
| S16 | `--force` (5 m, 2180) — tresc | **FAIL** (BUG-L2-1) | Ten sam bbox, drugi przebieg: **13 z 36 arkuszy zmienilo tresc** (inne kampanie), >= 14 z 36 nie jest najnowsza kampania; wycinek rozni sie w **21,2 % pikseli**; pojawil sie 1 piksel nodata na szwie arkuszy z roznych kampanii (`N-34-140-B-b-4-2` 2025 / `N-34-141-A-a-3-1` starsza) |
| S17 | Biblioteka `download_pl_cutout` z tym samym cache (1 m, `EPSG:3045`, siec zablokowana) | **PASS** | wynik **bajt w bajt = CLI**; ta sama nazwa pliku takze dla bboxa w EPSG:4326 (sprawdzone `prepare_pl_cutout` dla wszystkich 6 wariantow); drugie wywolanie `skipped=True`; sidecar rozni sie tylko `downloaded_at` i `extra` (`{}` zamiast `parent_request`) |
| S18 | Biblioteka w swiezym katalogu (5 m, `EPSG:5514`, `max_workers=2`) | **FAIL** (BUG-L2-1) | 68,3 s, 42 arkusze, 26 zerwanych zapytan warstw. Wynik spojny sam w sobie (bit w bit z warpem wlasnej mozaiki z JEGO arkuszy), ale wobec wyniku CLI dla tego samego bboxa rozni sie w **854 784 z 4 648 336 px (18,4 %)**, maks. 3,71 m — w 100 % w zasiegu 10 arkuszy, ktore oba przebiegi dostaly z roznych kampanii |
| S19 | R5 przy prawdziwych chwilowych bledach GUGiK | **PASS** | 2 z 2 przebiegow z arkuszem bez odpowiedzi: exit 1, `Error: ... (blad pobrania, nie brak danych) ... wycinek nie powstal; ponow pobranie` — brak dziury nodata, brak falszywego `missing_sheets` |

### (f) siatka pikseli

| # | Scenariusz | Wynik | Dowod |
|---|---|---|---|
| S20 | Faza arkuszy 1 m w moim obszarze | **PASS** | EVRF2007 2025 (4) i KRON86 2013 (4): naglowki `xllcenter` calkowite -> narozniki na k + 0,5 m. Kampanie roznia sie zasiegiem o 1 px (np. `-2-1`: 767661 vs 767660), nie faza |
| S21 | Faza 1 m w probce kraju | **PASS** | 76 unikalnych plikow PL-1992 1 m (EVRF2007 2019-2025, KRON86 2011-2018; 74 x `xllcenter`, 2 x `xllcorner` = ,5) — **jedna faza: narozniki k + 0,5 m**. Inne fazy maja tylko pliki innego typu w tych samych skorowidzach: PL-1992 0,5 m (4, narozniki k*0,5 + 0,25) i PL-2000 (12; faza 0, jeden z `cellsize 0.4997775943`) — `logs/phase_summary_1m.txt` |
| S22 | Wycinek KRON86 1 m (bbox calk., 2180) | **PASS** | 36,1 s; 2001 x 2001 px, ta sama siatka co EVRF2007 (S1), 0 z 4 004 001 rozbieznych, sidecar `EPSG:9650`; EVRF2007(2025) - KRON86(2013): mediana +0,180 m |
| S23 | Ostrzezenie "poza siatka pikseli wiekszosci" na zywo | **PASS** (nie wystapilo) | 0 wystapien we wszystkich przebiegach (1 m i 5 m w moich obszarach; 5 m: 48 arkuszy z kampanii 2022/2024/2025, wszystkie 5k + 2,5) |
| S24 | Semantyka ostrzezenia (symulacja offline na realnych arkuszach 1 m: naglowek `-2-2` przesuniety) | **UWAGA** (m4) | Ostrzezenie jest logowane. Przesuniecie +0,30/+0,45 px w x oraz +/-0,30 px w y: tresc = najblizszy piksel (0 roznic). Przesuniecie **-0,30 / -0,45 px w x: uzyty piksel oddalony o 0,70 / 0,55 px (NIE najblizszy, wbrew tekstowi ostrzezenia) + 996 pikseli nodata (kolumna na szwie)**. Potwierdza mechanizm BUG-L1-7 z raportu L1 (5 m, Krakow) |

### (g) arkusze PL-2000 pod godlem PL-1992 i pokrewne

| # | Scenariusz | Wynik | Dowod |
|---|---|---|---|
| S25 | Moje obszary | **PASS** | 0 ostrzezen "URL innego arkusza", 0 plikow z x >= 1 000 000 (1 m: 8 arkuszy, 5 m: 48 arkuszy, wielokrotnie pobieranych) |
| S26 | Czestosc (probka 12 punktow x 2 uklady wysokosci, wybor providera w pierwszej niepustej warstwie) | **UWAGA** | EVRF2007: 0/12 fallbackow PL-2000 (1/12 plik 0,5 m — S29); **KRON86: 1/12 (Zielona Gora: warstwa 2019 zawiera TYLKO arkusze PL-2000:S5)**. Rekordy PL-2000 sa w skorowidzach 1 m w **8 z 12** lokalizacji (glownie starsze warstwy, we Wroclawiu takze 2025 obok PL-1992; w Lodzi warstwa 2024 ma tylko PL-2000 0,5 m) — fallback staje sie realny, gdy nowsza warstwa chwilowo nie odpowie (BUG-L2-1) |
| S27 | Wycinek na arkuszu z fallbackiem PL-2000 (Zielona Gora, KRON86, 2180) | **PASS** | exit 1, 23,1 s; stderr: `M-33-8-A-a-3-1: skorowidz zwrocil URL innego arkusza (.../72980_898837_5.167.25.13.asc) — plik moze byc innym arkuszem, np. w ukladzie PL-2000` i `Error: 1 arkusz(y) ma wspolrzedne PL-2000 zamiast PL-1992: M-33-8-A-a-3-1.asc (strefa 5, EPSG:2176) — ... pobierz obszar jako arkusze (bez --target-crs), np. z --system 2000.` Brak pliku wycinka, brak pustych katalogow. UWAGA: plik PL-2000 (1600 x 1000 px, `xllcorner 5535200`) zostaje w `pl_1992_1m_kron86/M-33/8/A/a/3/1/` z sidecarem `horizontal_crs: EPSG:2180`; kazdy kolejny wycinek dotykajacy arkusza konczy sie tym samym bledem (bez sieci), `--force` pobierze to samo |
| S28 | Remedium z komunikatu: `--system 2000` (bez `--target-crs`) | **FAIL** (BUG-L2-3) | exit 0, 6,1 s, bez ostrzezen: godlo `5.167.25` (8 x 5 km) dostaje plik `5.167.25.13` (1:2000, 1,6 x 1,0 km = 4 % arkusza), pokrywajacy ok. 45 % zadanego bboxa; sidecar `horizontal_crs: EPSG:2180` dla danych w EPSG:2176 |
| S29 | Szczecin 1 m -> plik 0,5 m (`N-33-90-C-c-2-2`, 2180) | **FAIL** (BUG-L2-2) | exit 0, 40,2 s: arkusz w segmencie `pl_1992_1m_evrf2007` ma `cellsize 0.50` (114,6 MB), wycinek 2201 x 2601 px **po 0,5 m**, sidecar `resolution: 1m`; 3,4 % nodata tam, gdzie GUGiK ma pelny arkusz 1 m. Bez ostrzezenia |
| S30 | Szczecin `N-33-90-C-c-2-4` -> wycinek w calosci nodata | **FAIL** (BUG-L2-2) | exit 0, `Downloaded to ...`: plik 0,5 m dla `-c-2-4` to pasek 786 x 219 px (95,6 % nodata; rekord `calyArkuszWypelnionyTrescia: NIE`), wycinek 2001 x 2001 px = **100 % nodata**, bez `Warning:` i bez `missing_sheets`, choc GUGiK ma dla arkusza pelny plik 1 m (`TAK`) |
| S31 | Szczecin `-c-2-4` (0,5 m) + `C-d-1-3` (1 m) | **FAIL** (BUG-L2-2) | exit 1: `Error: mosaic_and_crop: niezgodne rozdzielczosci wejsc: [(0.5, 0.5), (1.0, 1.0)]` — trwale (arkusze w cache), komunikat bez godel i bez przyczyny |
| S32 | Ukladowa operacja 2180 -> 5514 (offline, TransformerGroup) | **UWAGA** (BUG-L2-4) | wybrana "S-JTSK to ETRS89 (3)" (0,5 m) ma obszar uzycia 16,84-22,56°E / 49,0-49,61°N (Slowacja/pogranicze PL-SK); od czeskiej "(1)" rozni sie o 1,96 m pod Klodzkiem i 1,15 m pod Cieszynem; w moich obszarach (52,4°N) obie operacje sa poza obszarem uzycia, a sidecar i tak deklaruje `(0.5 m)` |

## 3. Bledy (reprodukcje, hipotezy — NIE naprawiane)

### BUG-L2-1 (WYSOKI) — chwilowy blad GUGiK po cichu podmienia kampanie arkusza; wycinek niepowtarzalny

**Reprodukcja (zywa):** `cd e2e-data/2026-09-29-live/L2-wycinki-siatka; kartograf download --bbox
703000,491000,713000,501000 --target-crs EPSG:2180 --resolution 5m -o ./data --workers 2 --force`
dwa razy pod rzad (przy obciazonym GUGiK: 22 i 27 linii `WMS query failed for layer ...`).
**Wynik:** exit 0; 13 z 36 arkuszy zmienia tresc miedzy przebiegami; po drugim >= 14 z 36 nie jest
najnowsza kampania (np. `N-34-140-B-b-2-2`, `-b-2-4`, `-b-4-2`, `-b-4-4`, `N-34-141-A-a-1-4`,
`-a-3-4`: 2025 -> 2024; `N-34-141-A-a-2-2`, `-a-4-4`, `-b-3-3`: 2024 -> 2022; dopasowanie przez
rozmiar pliku vs `Content-Length` URL-i z kazdej warstwy, `logs/campaigns_5m_*`). Wycinek rozni sie
w 21,2 % pikseli, biblioteka w swiezym katalogu vs CLI — 18,4 %. Roznice kampanii: |d| srednio
8-14 mm, p99 4-8 cm, lokalnie do 3,78 m i 4,21 m (`logs/campaign_diff_magnitude.txt`).
Jedyny slad: surowe `WMS query failed for layer SkorowidzeNMT2025: ...` — bez godla.
**Oczekiwane:** najnowsza kampania albo blad (jak w R5: "chwilowy blad nie moze zostawic trwalej
dziury" — tu zostawia trwale starsze dane w cache `skip_existing`).
**Reprodukcja minimalna (offline):** `.venv/bin/python repro_silent_downgrade.py` (sesja zrywajaca
tylko warstwe 2025) -> `ZWROCONY URL: .../81417_1626552_N-34-140-B-b-2-2.asc` (2024), bez wyjatku.
**Hipoteza:** `kartograf/providers/pl/gugik.py:618-622` (`except requests.RequestException:
transport_errors += 1; continue` — przejscie do starszej warstwy, zadnych ponowien zapytania
GetFeatureInfo; plik ma 3 proby, skorowidz 1) + `:582-588` (pierwszy URL wygrywa). `transport_errors`
wplywa na wynik tylko, gdy ZADNA warstwa nie ma URL-a (`:624-642`). Pokrewne: L1 BUG-L1-5.

### BUG-L2-2 (WYSOKI) — rekord arkusza wybierany wg kolejnosci HTML: pliki 0,5 m zamiast 1 m, najstarsza kampania w warstwie zbiorczej

**Fakty (skorowidz na zywo):** warstwa zwraca rekordy w kolejnosci ROSNACEJ po dacie (JS strony
sortuje dopiero do wyswietlenia), a jeden punkt/godlo moze miec kilka rekordow: 0,5 m i 1 m
(Szczecin 2024: `84007_...` 0,50 m `calyArkuszWypelnionyTrescia: NIE` przed `80225_...` 1,00 m `TAK`,
dla 7 z 9 arkuszy wokol `N-33-90-C-c-2-2`), kilka kampanii w `SkorowidzeNMT2023iStarsze` (12 z 12
lokalizacji probki, zawsze od najstarszej).
**Reprodukcje (zywe):**
1. `kartograf download --bbox 207700,624000,208800,625300 --target-crs EPSG:2180 -o ./data` -> exit 0,
   wycinek 0,5 m (2201 x 2601 px) w `pl_1992_1m_evrf2007/bbox/`, sidecar `resolution: 1m`, 3,4 % nodata.
2. `kartograf download --bbox 207500,621500,208500,622500 --target-crs EPSG:2180 -o ./data` -> exit 0,
   **100 % nodata**, bez ostrzezenia i `missing_sheets`.
3. `kartograf download --bbox 209000,622000,209800,622800 --target-crs EPSG:2180 -o ./data` -> exit 1,
   `mosaic_and_crop: niezgodne rozdzielczosci wejsc: [(0.5, 0.5), (1.0, 1.0)]`.
4. `GugikProvider._get_opendata_url` na zywo z lista warstw zawezona do `SkorowidzeNMT2023iStarsze`
   (sytuacja arkusza bez danych 2024+ albo po BUG-L2-1): `N-34-139-A-c-1-1` -> `73021_914857`
   (2019-04-18) zamiast `78047_1404533` (2023-09-05); `M-33-35-C-a-3-1` -> 2019 zamiast 2023
   (`logs/oldest_in_aggregated_layer.txt`).
**Oczekiwane:** plik o rozdzielczosci zadania, pelny arkusz, najnowszy; wycinek "1m" w 1 m; nodata
tylko tam, gdzie GUGiK nie ma danych.
**Hipoteza:** `kartograf/providers/pl/gugik.py:576-588` — regex po `url:"..."` i pierwszy URL
zawierajacy godlo; pola rekordu `charakterystykaPrzestrzenna`, `calyArkuszWypelnionyTrescia`,
`aktualnosc` sa w odpowiedzi, ale nie sa czytane. Wycinek nie ma strazy rozdzielczosci arkusza
(`download/cutout.py` — `_reject_pl2000_sheets` sprawdza tylko x >= 1e6). Pokrewne: L1 BUG-L1-3
(orto "Starsze" — ten sam wzorzec).

### BUG-L2-3 (SREDNI) — remedium z bledu PL-2000 daje arkusz-dziecko; sidecar PL-2000 z EPSG:2180

**Reprodukcja:** po S27: `kartograf download --bbox 260000,458600,261200,459800 --vertical-crs KRON86
--system 2000 -o ./data --workers 2` -> exit 0, bez ostrzezen, `pl_2000_1m_kron86/5/167/25/5.167.25.asc`
= plik `5.167.25.13` (1600 x 1000 px, 1:2000), ok. 45 % bboxa; sidecar `horizontal_crs: EPSG:2180`,
`request.godlo: 5.167.25`. **Oczekiwane:** arkusz(e) pokrywajace zadanie albo blad/ostrzezenie;
`horizontal_crs` = EPSG:2176 dla pliku strefy 5.
**Hipoteza:** `gugik.py:584` — `if godlo in found_url` dopasowuje podciag (`5.167.25` w
`..._5.167.25.13.asc`), wiec arkusz-dziecko przechodzi jako "ten" arkusz; `sources/registry.py:76`
(kanal NMT PL z `horizontal_crs="EPSG:2180"` na sztywno) + `sources/sidecar.py:111`. Tresc
komunikatu `download/cutout.py:306-312` poleca te droge. Pokrewne: L1 BUG-L1-4, BUG-L1-11.

### BUG-L2-4 (NISKI-SREDNI, decyzja do rewizji) — operacja 2180 -> 5514 spoza obszaru uzycia, deklarowana dokladnosc 0,5 m

`build_pinned_transform` (`transform/crs.py:236`) wybiera min(accuracy) sposrod operacji, ktore
przeszly probe (tylko `isfinite`). Dla 2180 -> 5514 to zawsze "S-JTSK to ETRS89 (3)" (Helmert
slowacki, obszar 16,84-22,56°E / 49,0-49,61°N). Pomiar (`logs/op_5514_candidates.txt`): wobec
czeskiej "(1)" (obszar CZ) — 1,96 m (Klodzko), 1,15 m (Cieszyn; zgodne z researchem 2026-08-10:
~1,1 m). Sidecar wycinka pisze `(0.5 m)`. To swiadomy wybor z `docs/research/2026-08-10-czechy-dmr-zabaged.md`
(tabela 7.1), ale research sam oznaczyl brak kontroli `area_of_use` jako "DO ZMIANY"
(`2026-08-11-etap1-rekonesans.md` 7c). Istotne dla R6 (styk wycinkow PL i CZ w 5514) — do L4.

### Drobne (UX)
- m1: `WMS query failed for layer X: ...` nie podaje godla — uzytkownik nie wie, ktory arkusz moze
  byc starsza kampania (`gugik.py:615, 621`).
- m2: po nieudanym `--force` komunikat "wycinek nie powstal" — poprzedni plik wyniku jednak istnieje
  i jest nietkniety (S15); warto to powiedziec.
- m3: `niezgodne rozdzielczosci wejsc` bez nazw arkuszy i bez wskazowki (S31).
- m4: tekst ostrzezenia "tresc przepisana najblizszym sasiadem" nieprawdziwy dla przesuniec
  w strone W (S24, L1 BUG-L1-7).
- m5: biblioteka z wlaczonym logowaniem: przy kazdym wycinku EPSG:2180 `WARNING rasterio._env:
  CPLE_IllegalArg ... BLOCKXSIZE can only be used with TILED=YES` (profil VRT + `tiled=False`,
  `transport/mosaic.py:281-286`); nieszkodliwe. W CLI niewidoczne (rasterio ma NullHandler).
- m6: przy zerwanym GetCapabilities ostrzezenie drukuje kazdy watek (2x przy `--workers 2`).

## 4. Zachowanie do udokumentowania

1. **Siatka 1 m (odpowiedz na "siatka 1 m — checklista live" w 4.3 krok 5):** wszystkie pliki
   PL-1992 1 m maja narozniki pikseli na k + 0,5 m (84 pliki: EVRF2007 2019-2025, KRON86 2011-2018,
   12 lokalizacji + moj obszar); kampanie tego samego arkusza roznia sie zasiegiem o 1 px, nie faza.
   5 m w moim obszarze: 5k + 2,5 (48 arkuszy, kampanie 2022/2024/2025) — ALE L1 zmierzyl pod
   Krakowem arkusze 5 m (2022) kotwiczone we wlasnym narozniku (fazy dowolne): regula 5k + 2,5 nie
   jest uniwersalna.
2. **Skorowidz "1 m" nie jest wylacznie 1 m ani PL-1992:** te same warstwy zawieraja rekordy 0,5 m
   (PL-1992 i PL-2000) i arkusze PL-2000 (1 m i 0,5 m) — PL-2000 w 8 z 12 lokalizacji probki.
3. **Opcje domyslne warpu GDAL** (4.3 krok 6 opisuje tylko `XSCALE/YSCALE`): `rasterio.warp.reproject`
   uzywa tez transformatora PRZYBLIZONEGO (`tolerance=0.125` px zrodla). Rozklad roznicy wobec
   dokladnego bilineara (1 m, 5514): tylko `XSCALE`: srednio 2,76 mm / maks. 0,25 m; tylko
   `tolerance`: 0,31-0,33 mm / 18 mm; obie wylaczone: 0,004 mm / 0,01 mm. Dla 5 m `tolerance` daje
   do 0,13 m (5514). Obrot siatek wzgledem 2180 na 22-23°E: Krovak +4,5°, UTM 33N -3,2°, skala
   1,0026-1,0030. To samo pole i uklad moga dac rozne wygladzenie zaleznie od bboxa (S3 vs S6).
4. **Uklad docelowy spoza obszaru uzycia** (5514/3045 w NE Polsce) jest przyjmowany bez uwag;
   dokladnosc w `transform` sidecara jest nominalna (BUG-L2-4).
5. **Zakladki arkuszy 5 m:** sasiednie arkusze nachodza na siebie ~1 wiersz/kolumne (10-13 tys. px
   na wycinek 10 x 10 km); w zakladce wygrywa arkusz pierwszy w sortowaniu sciezek, nie najnowszy —
   miedzy kampaniami to do 9 cm roznicy (`logs/overlap_5m.txt`).
6. **Szwy miedzy kampaniami** moga zostawic 1 px nodata (S16) — "nodata tylko tam, gdzie nie siega
   zaden pobrany arkusz" formalnie prawdziwe, ale wynika z mieszania kampanii.
7. **Sidecar arkusza nie zapisuje URL-a ani daty kampanii** (`request` = samo godlo) — nie da sie
   sprawdzic, ktora kampanie dostal uzytkownik; tor LAZ zapisuje `extra.url`.
8. **Plik PL-2000 pobrany fallbackiem zostaje w segmencie PL-1992** (z sidecarem EPSG:2180) i blokuje
   kazdy kolejny wycinek na tym arkuszu, az uzytkownik usunie go recznie — warto napisac to w
   komunikacie bledu (sciezka pliku).
9. `PlCutoutResult.sheet_paths` ma kolejnosc ukonczenia pobran (nie posortowana); sidecar wycinka
   z biblioteki bez `parent_request` ma `"extra": {}`.
10. Pod obciazeniem (kilku agentow rownolegle) GUGiK zrywa 1-27 zapytan warstw na przebieg
    (`RemoteDisconnected`, `Connection reset by peer`, raz `Read timed out` 30 s) — zwykly uzytkownik
    z `--workers 4` (domyslne CLI) tez to zobaczy.
11. Nazewnictwo w pamieci projektu: `N-34-130-D-d-2` to okolice Siemiatycz (nie Bialystok),
    `N-34-141-A-a-1` okolice Wegrowa (nie Warszawa).

## 5. Odpowiedzi na pozycje checklisty

**(d) wycinki 2180/5514/3045, bbox calkowity i ulamkowy, 1 m i 5 m, na zywych danych — mechanika TAK.**
2180: siatka arkuszy (faza 0,5 px), zasieg = zadanie rozszerzone na zewnatrz o 0,04-0,68 m (1 m)
i 0,05-2,5 m (5 m), wartosci 1:1 (0 rozbieznych w 5 wycinkach, ~20 mln pikseli). 5514/3045: siatka
wyniku zgodna z niezalezna obwiednia, krawedz E/S w granicy 0,5 px, wynik bit w bit rowny warpowi
wlasnej mozaiki z ta sama operacja; wobec dokladnego bilineara 0,13-3,3 mm srednio (opcje domyslne
GDAL); nodata 0 wszedzie, gdzie arkusze maja dane. Sidecar zgodny z 3.2. "Skipped" bez sieci — TAK.
`--force` pobiera arkusze ponownie i przebudowuje plik, nieudany zostawia stary — TAK. Biblioteka =
CLI bajt w bajt przy tych samych arkuszach — TAK. **Ale** tresc zalezy od tego, ktora kampanie
provider dostanie (BUG-L2-1, BUG-L2-2): powtorzenie tego samego polecenia daje inny wynik (21 % pikseli).

**(f) siatka 1 m EVRF2007 i KRON86 — jedna faza (narozniki k + 0,5 m) dla wszystkich kampanii
i obu ukladow wysokosci** (84 pliki). Fazy mieszane w 1 m PL-1992 nie wystepuja, wiec ostrzezenie
"poza siatka pikseli wiekszosci" nie pojawilo sie ani razu na zywo; backlog `extra.off_grid_sheets`
dla 1 m jest zbedny. Pilniejsza jest straz ROZDZIELCZOSCI (pliki 0,5 m w skorowidzu 1 m, BUG-L2-2).
Gdyby fazy byly mieszane (symulacja, S24): ostrzezenie jest logowane, tresc arkusza spoza siatki
jest przepisywana bez interpolacji, ale dla przesuniec w strone W bierze piksel oddalony o 0,55-0,70 px
(nie najblizszy) i zostawia kolumne nodata na szwie — zgodnie z BUG-L1-7 (5 m, Krakow, fazy
dowolne na zywo).

**(g) arkusze 1 m PL-2000 pod godlem PL-1992 — rzadkie w wyborze domyslnym, ale realne:** 0 w moich
obszarach; w probce 12 lokalizacji 1/12 dla KRON86 (Zielona Gora, warstwa 2019 w calosci PL-2000),
0/12 dla EVRF2007 w pierwszej niepustej warstwie — rekordy PL-2000 sa jednak w skorowidzach 8/12
lokalizacji, wiec chwilowy blad nowszej warstwy (BUG-L2-1) potrafi do nich zepchnac (Lodz: warstwa
2024 ma tylko PL-2000 0,5 m). **Zachowanie wycinka: poprawne — glosny blad z opisem, kod 1, bez
dziury** (S27). Slabosci wokol: plik PL-2000 zostaje w cache PL-1992 z blednym sidecarem, a
remedium z komunikatu (`--system 2000`) daje po cichu arkusz 1:2000 zamiast 1:10000 (BUG-L2-3).
Znana luka "URL innego arkusza tego samego ukladu" (4.3 krok 4) ma groznego kuzyna, ktorego
ostrzezenie nie obejmuje: URL Z godlem, ale innej rozdzielczosci/niepelny (BUG-L2-2, 100 % nodata
z kodem 0).

## 6. Surowe artefakty

Katalog roboczy: `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L2-wycinki-siatka/`
- `logs/runs.txt` — polecenia, kody, czasy; `logs/<tag>.stdout|.stderr` — pelne wyjscia (tagi jak w
  tabelach: `d*`, `f_*`, `g_*`).
- Weryfikacje: `logs/verify_*.txt`, `logs/verify2_*.txt`, `logs/cutouts_table.txt`,
  `logs/overlap_5m.txt`, `logs/lib_call_1m.txt`, `logs/lib_call_5m_run1.txt`, `logs/lib_vs_cli_5m.txt`,
  `logs/lib_logging_warnings.txt`.
- Kampanie: `logs/campaigns_5m_after_run1.{txt,json}`, `logs/campaigns_5m_after_force.{txt,json}`,
  `logs/campaigns_5m_after_force2_offline.txt`, `logs/campaign_diff_magnitude.txt`,
  `logs/force*_sha.txt`, `logs/force_*_stat.txt`, `cut_5m_int_2180_before_force.tif`.
- Skorowidze i fazy: `wms_samples/probe_areas.json`, `wms_samples/sample_country_1m.json`,
  `logs/sample_country_1m.txt`, `logs/phase_summary_1m.txt`, `logs/szczecin_*.txt`,
  `logs/oldest_in_aggregated_layer.txt`, `wms_samples/N-34-130-D-d-2-4_EVRF2007_2025.html` (surowa
  odpowiedz GetFeatureInfo), `wms_samples/indep_82710_1715397_N-34-130-D-d-2-4.asc` (niezalezne pobranie).
- Symulacje/reprodukcje: `repro_silent_downgrade.py`, `logs/sim_offgrid*.txt`, `sim_offgrid/`,
  `logs/op_5514_candidates.txt`.
- Skrypty: `run.sh`, `probe_wms.py`, `verify_2180.py`, `verify_warp.py`, `verify_warp2.py`,
  `campaign_check.py`, `sample_country.py`, `overlap_stats.py`, `lib_call_1m.py`, `lib_call_5m.py`.
- Dane: `data/nmt/pl_1992_{1m_evrf2007,1m_kron86,5m_evrf2007}/`, `data/nmt/pl_2000_1m_kron86/`
  (remedium), `data_lib/` (biblioteka, swiezy katalog), `cli_copies/` (wynik CLI przed wywolaniem
  bibliotecznym).
