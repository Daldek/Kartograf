# E2E-A: NMT i NMPT, przypadki brzegowe (C1-C11, C16)

- **Data:** 2026-10-06, commit `ead24c2` (develop), CLI `0.7.0-dev`
- **katalog danych:** `<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/a/` (dane razem 352 MB)
  - `raw/recon/<godlo>/<endpoint>__<warstwa>.body` — surowe odpowiedzi GetFeatureInfo; `raw/caps/*.xml` — GetCapabilities 5 endpointow; `raw/C6/*.head` — naglowki plikow z GUGiK (Range)
  - `out/<Cx>/` — pobrane pliki i sidecary; `out/oracle.txt|json` — wyrocznia; `out/verify.json` — wyniki F4
  - `logs/<Cx>.{meta,stdout,stderr}` — komenda, kod, czas, komunikaty; `scripts/` — oracle.py (wyrocznia niezalezna od kodu: reguly ADR-028 stosowane na surowych .body), recon.py, verify.py, w8.py, c7.py, uklad.py
- **Rozpoznanie:** 211 arkuszy 1:10000 (PL-1992) sprawdzonych w skorowidzu: 51 wybranych (miasta, wybrzeze, granice, pas zmian stref 5/6/7/8) x 5 endpointow, 110 losowych (seed 20261006) x 3 endpointy EVRF, 49 sasiadow arkusza M-33-31-D-c-4-2 x 1 endpoint. Okolo 2430 zapytan GFI, 4 watki, bez bledow. CLI: 38 uruchomien, `--workers 1`, `--force`.
- **Uwaga metodyczna:** wyrocznia dla C16d byla bledna (patrz nizej): sasiedzi z trzeciego skanu mieli odpytany tylko endpoint NMT 1 m EVRF, wiec "brak NMPT" byl brakiem danych w moich surowych plikach, nie w GUGiK. Poprawiona po dopytaniu. Wszystkie pozostale wyrocznie powstaly przed uruchomieniem CLI (`out/oracle.txt`); C6h (7.173.21.01) dopisany bez wpisu w oracle.txt, ale z rekordow zebranych wczesniej (`raw/recon/N-34-139-A-c-1-1/nmt1_evr__SkorowidzeNMT2023iStarsze.body`).

## Tabela zbiorcza

Kolumna "oczekiwane" = wyrocznia z surowych rekordow (warstwa, aktualnosc, plik). "Faktyczne" = sidecar `extra.source` + naglowek pliku; W1/W2 (URL, aktualnosc, dt_pzgik zgodne z wyrocznia) spelnione dla WSZYSTKICH pobranych plikow.

| Przyp. | Arkusz / zadanie | Oczekiwane | Faktyczne | Werdykt |
|---|---|---|---|---|
| C1a | N-34-130-D-d-2-4 nmt 1m EVRF | warstwy 2025/2024/2023iStarsze, wygrywa 2025: 82710_1715397, 2025-04-26 | to samo, rc 0, nodata 9.9% | PASS |
| C1b | M-34-66-B-a-2-1 nmt 1m EVRF | 3 kampanie w 2023iStarsze (2019-02-16, 2022-05-31, 2023-03-29): 77381, 2023-03-29 | to samo | PASS |
| C1c | M-33-57-C-b-4-2 nmt 1m EVRF | 1 m: 2023iStarsze 2023-05-04, mimo nowszego rekordu 0,5 m (2025-09-04) w warstwie 2025 | to samo | PASS |
| C2 | remis aktualnosci | — | nie znaleziono rozstrzygajacego remisu | NIE ZNALEZIONO |
| C3a | N-33-90-C-c-2-4 nmt 1m | 2024: 0,5 m (2024-08-28, NIE) i 1 m (2024-09-03): wygrywa 1 m 80225_ | to samo | PASS |
| C3b | M-34-63-A-a-3-3 nmt 1m | 2025-04-03, 83884 | to samo | PASS |
| C4a | N-34-63-D-d-4-4 nmt 1m EVRF | wygrywa 2023iStarsze 2022-05-18 (76531) | to samo | PASS |
| C4b | M-34-76-A-a-1-1 nmt 5m | 5 m tylko w 2022iStarsze (najstarsza warstwa), 2022-06-03 | to samo, 5.00 m | PASS |
| C4c | N-34-130-D-d-2-4 nmt 1m KRON86 | 2017iStarsze, 2013-10-23 (4042_475813) | to samo, vcrs EPSG:9650 | PASS |
| C5a | N-34-144-C-c-2-2 (Terespol) nmt 1m | 2025-09-22, calyArkusz=NIE, brak starszej alternatywy | to samo; nodata 26.2%, plik pokrywa 21.5% godla | PASS (uwaga: dane w ~16% uzyteczne) |
| C5b | N-34-131-D-a-3-2 nmt 1m | 2025-07-02, NIE, brak alternatywy | to samo; nodata 58.0%, plik pokrywa 50.2% godla | PASS (jw.) |
| C6a | 6.129.30.01.1 (strefa 6) nmt 1m | 1 m 2020-05-08; nowszy 0,5 m (2023-07-08) odfiltrowany | to samo, EPSG:2177, wspolrzedne 6.57e6 | PASS |
| C6b | 7.125.11.19 (strefa 7) nmt 1m | 2023-03-17 (77912) | rekord wybrany poprawnie, ale plik w EPSG:2180, cellsize 0.9993671653521061; Warning, sidecar horizontal_crs=EPSG:2180 | UWAGA (dane) |
| C6h | 7.173.21.01 (strefa 7, 1:2000) nmt 1m | 2021-04-28 (75064) | jw.: plik w EPSG:2180, cellsize 0.999608511470073, Warning | UWAGA (dane) |
| C6c | 8.193.14.01.1 (strefa 8) nmt 1m EVRF | 2024-03-30 (83802) | EPSG:2179, 8.44e6 | PASS |
| C6d | 5.148.24.15.4 (strefa 5) nmt 1m EVRF | 2024-07-06 (81774) | EPSG:2176, 5.53e6 | PASS |
| C6e | 8.193.14.01.1 nmt 1m KRON86 | 2018-11-30 (71305), EPSG:9650 | to samo; naglowek `xllcorner`, cellsize `1`, NODATA `-9999.0` | PASS |
| C6f | 6.129.30 (1:10000 PL-2000) | NoCoverage, rc 1, potomek 6.129.30.13.4 (rekord z 2020-05-08 i 0,5 m z 2023-07-05) | rc 1, "Dostepny potomek 6.129.30.13.4 — uzyj --scale 1:1000; ... PL-1992: M-34-63-A-c-2-1" | PASS |
| C6g | 5.167.25 KRON86 | NoCoverage, potomek 5.167.25.13 (2019-06-03, 1 m) | rc 1, `--scale 1:2000` | PASS |
| C7 | N-34-139-A-c-1-1 KRON86 vs EVRF2007 | KRON86 2018-04-03 (70709) vs EVRF 2025-04-27 (83233): rozne kampanie | sidecary EPSG:9650 / EPSG:9651; ta sama siatka | UWAGA (brak pary z tej samej kampanii) |
| C8a | N-34-141-A-a-1-1 5m | 2024-07-19 (81417) | to samo | PASS |
| C8b | N-34-130-D-d-2-4 5m (1 m jest, 5 m brak) | NoCoverage rc 1 | rc 1 `Error: Brak danych NMT 5m ...` | PASS |
| C8c | N-34-141-A-a-1-1 1m EVRF (5 m jest, 1 m brak) | NoCoverage rc 1 | rc 1 | PASS |
| C8d | N-34-141-A-a-1-1 1m KRON86 | 2011-10-27 (3970) | to samo | PASS |
| C9a | N-33-59-C-a-1-3 KRON86 | rekord z `godlo:"N-33-59-c-a-1-3"` (male c) 2018-04-21 | wybrany, plik `N-33-59-C-a-1-3.asc`, source.godlo znormalizowane | PASS |
| C9b | N-33-115-C-d-2-2 5m | wygrywa 2025-03-20 (nie `.ASC` z 2022iStarsze) | to samo | PASS |
| C10a | Hel N-34-50-B-a-3-4 | 2022-04-20 | to samo, nodata 0.56% | PASS |
| C10b | Leba N-33-48-C-a-3-4 | 2022-04-28 | to samo, 4.1% | PASS |
| C10c | Swinoujscie N-33-77-A-d-2-2 nmt 1m | 2024-09-21 (0,5 m NIE w tej samej warstwie pominiete) | to samo, 11.9% | PASS |
| C10d | Slubice N-33-126-C-c-3-4 | 2024-09-03 | to samo, nodata 75.4% (Odra/Niemcy) | PASS (uwaga: 75% pusty, calyArkusz=TAK) |
| C10e | Przemysl M-34-82-D-a-3-1 | 2025-06-21 | to samo, 9.1% | PASS |
| C10f | N-34-51-D-d-1-1 (Zalew Wislany) | brak w 5 endpointach, NoCoverage rc 1 | rc 1 | PASS |
| C10g | N-33-77-A-d-2-2 nmpt 1m | tylko 0,5 m: NoCoverage z podpowiedzia | rc 1 "GUGiK ma ten arkusz w 0.5 m — Kartograf pobiera dokladnie 1 m" | PASS |
| C11 | naglowki ASC | patrz sekcja | nodata sidecara zgodny we wszystkich plikach | PASS |
| C16a | M-34-6-B-c-4-2 nmpt 1m | NMPT 2023iStarsze 2019-04-19, gdy NMT ma 2025-04-26 | to samo | UWAGA (zalegosc NMPT 6 lat) |
| C16b | N-34-130-D-d-2-4 nmpt EVRF | 2025-04-26 (82709) | to samo | PASS |
| C16c | N-34-130-D-d-2-4 nmpt KRON86 | 2013-10-23 (3152) | to samo, EPSG:9650 | PASS |
| C16d | M-33-31-D-a-3-3 nmpt EVRF | (skorygowana) 1 m 2021-09-04 w 2023iStarsze; nowsze 0,5 m odfiltrowane | to samo | PASS |
| C16e | M-34-106-C-a-4-4 nmpt EVRF | 2023-04-28, NIE | to samo, nodata 31.4% | PASS |
| W12 | rerun C1a bez `--force` | skip | rc 0, 395 ms, mtime pliku i sidecara bez zmian | PASS |

Liczby (wierszy tabeli): UWAGA 4 (C6b, C6h, C7, C16a), NIE ZNALEZIONO 1 (C2), FAIL 0, BLOKADA 0, reszta PASS (w tym C5a/C5b i C10d z notami o niepelnych danych).

## Przypadki z dowodami

### C1 (wiele kampanii)
- C1a: surowe body `raw/recon/N-34-130-D-d-2-4/nmt1_evr__SkorowidzeNMT2025.body` (82710, 2025-04-26, dt_pzgik 2025-09-24), `...2024.body` (81449, 2024-05-27), `...2023iStarsze.body` (76748, 2022-07-21). Sidecar `out/C1a/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc.meta.json`: `layer SkorowidzeNMT2025`, `aktualnosc 2025-04-26`, `dt_pzgik 2025-09-24`, `vertical_crs EPSG:9651`, `nodata -9999.0`, `numer_zgloszenia GK-FOTO.6201.11.2025`.
- C1b: 3 rekordy w jednej warstwie, wygrywa max aktualnosci; C1c: patrz C3.
- W9: `request` w sidecarze zawiera tylko `{"godlo": ...}`; rozdzielczosc i pion sa na poziomie glownym (`resolution`, `vertical_crs`), wiec zgodne z faktycznym plikiem. Obserwacja, nie blad.

### C2 (remis aktualnosci)
Nie znaleziono rozstrzygajacego remisu w 211 arkuszach (~850 rekordow wlasnych). Jedyne remisy (aktualnosc 2021-10-01, dt_pzgik 2021-12-28 vs 2022-02-18) wystepuja w sasiedztwie M-33-31-D-c-* w warstwie 2023iStarsze, ale trzeci rekord (2023-06-03) jest nowszy, a ponadto nad ta warstwa lezy 2025. Tie-break `dt_pzgik`/URL nie byl wiec wywolany na zywo. Dowod: `raw/recon/M-33-31-D-c-4-2/nmt1_evr__SkorowidzeNMT2023iStarsze.body`.

### C3 (rozdzielczosci)
Wzorzec dla fixtury: M-33-57-C-b-4-2: `nmt1_evr__SkorowidzeNMT2025.body` zawiera 0,5 m z 2025-09-04, a `...2023iStarsze.body` 1 m z 2023-05-04 — wygrywa 1 m 2023 (filtr rozdzielczosci przechodzi przez warstwe z tylko nieodpowiednimi rekordami, bez bledu). Szczecinski wzorzec z K4 (0,5 m starsze o 6 dni od 1 m w tej samej warstwie) powtorzony na N-33-90-C-c-2-4 i N-33-90-C-a-3-4.

### C4 / C8 (warstwy zbiorcze, 5 m)
Rozklad warstw wygrywajacych (czesc probki): NMT 1 m EVRF: 2025 x103, 2024 x30, 2023iStarsze x36; NMT 5 m: 2025 x40, 2024 x30, 2023 x14, 2022iStarsze x21; NMPT EVRF 2023iStarsze x57. Nie odnotowano bledu przejscia przez warstwy. 1 m bez 5 m (20 arkuszy) i 5 m bez 1 m EVRF (4: N-34-101-C-b-2-3, N-34-141-A-a-1-1, N-34-141-C-c-2-2, N-34-80-A-b-2-1) wystepuja; oba kierunki daja `Error: Brak danych ...`, rc 1, bez podpowiedzi (inny endpoint, wiec Kartograf nie ma o czym podpowiedziec — poprawne wg ADR-028).

### C5 (niepelny najnowszy arkusz)
Nie znaleziono arkusza, w ktorym nowsza kampania NIE jest pelna, a starsza TAK (zadnego z 13 arkuszy z wygrywajacym `calyArkusz...=NIE` nie ma innego rekordu 1 m w zadnej warstwie). Skutek reguly "najnowsza niezaleznie od pelnosci" nie wystapil w tej probce. Granicznie: Terespol (`out/C5a/.../N-34-144-C-c-2-2.asc`: 548 x 2197 komorek, plik pokrywa 21.5% godla, w nim 26.2% nodata) i N-34-131-D-a-3-2 (1264 x 2192, 50.2% godla, 58.0% nodata). Pliki sa mniejsze niz arkusz (zasieg `xllcenter`/ncols), a sidecar ma `full_sheet: false`. Dowod: `out/verify.json`, `logs/w8.txt`.

### C6 (PL-2000)
- Strefy 5, 6, 8 (C6a, C6c, C6d, C6e): wspolrzedne zgodne ze strefa (EPSG:2176 x ~5.53e6, 2177 x ~6.57e6, 2179 x ~8.44e6), sidecar zgodny, godlo pokryte w 100%, sciezka `nmt/pl_2000_1m_*`.
- **Strefa 7 (C6b, C6h) — nowy wzorzec danych.** Rekord: `ukladWspolrzednychPoziomych:"PL-2000:S7"`, a plik (naglowek z GUGiK, `raw/C6/77912_1384976_7.125.11.19.head`, `75172_...head`, `75064_...head`): `xllcenter 567975.95 yllcenter 242449.35 cellsize 0.9993671653521061` — wspolrzedne EPSG:2180 (po PL-2000 byloby ~7.5e6), cellsize niecalkowite. Kartograf wykrywa: stderr `Sidecar ...: godlo 7.125.11.19 wskazuje EPSG:2178, ale wspolrzedne pliku (x = 567976) sa w EPSG:2180 — zapisano uklad pliku`, rc 0; sidecar `horizontal_crs: EPSG:2180` (zgodny z plikiem), natomiast `extra.source.uklad: "PL-2000:S7"` (deklaracja rekordu) i sciezka `nmt/pl_2000_1m_evrf2007/7/125/11/19/` (uklad z godla, ADR-026). Starszy rekord 7.125.11.19 (2021-10-05, 75172) ma identyczny naglowek. Pozostale 4 godla PL-2000 strefy 7 w danych (7.173.21.01.2, 7.135.34.06 KRON86) nie byly pobierane — nie wiem, czy wszystkie strefy 7 maja ten defekt (2 z 2 pobranych maja).
- Skale: w danych sa tylko godla 1:1000 (np. 6.129.30.01.1, 6.224.25.11.4) i 1:2000 (5.167.25.13, 7.173.21.01); 1:5000 i 1:500 PL-2000 NIE znaleziono w 211 arkuszach (modulArchiwizacji: tylko "1:5000" (PL-1992), "1:2000", "1:1000").
- 1:10000 PL-2000 bez wlasnego pliku (C6f, C6g): komunikat zgodny z oczekiwaniem; hint wskazuje pierwszego potomka z rekordow GFI (nie wszystkich) — zgodne z surowym body `raw/recon/6.129.30/nmt1_evr__SkorowidzeNMT2023iStarsze.body`.
- Granica stref: 6.148.12.02.2 (strefa 6) i 5.148.24.15.4 (strefa 5) w tym samym pasie 148 po obu stronach 16,5E — oba rekordy obecne; pobrano strefe 5 (C6d), poprawna.

### C7 (KRON86 vs EVRF2007)
Ta sama siatka (N-34-139-A-c-1-1, 2197 x 2376, te same granice i maska nodata, 4 944 148 wspolnych komorek). Roznica EVRF2007 (2025-04-27) minus KRON86 (2018-04-03): srednia 0.156 m, mediana 0.210 m, std 0.597 m, p5 -1.25, p95 0.54, min -8.01, max 11.93; tylko 1.1% komorek ma |roznica| < 5 cm. Sidecary: `vertical_crs EPSG:9650` vs `EPSG:9651`, pola zgodne z `ukladWspolrzednychPionowych` rekordow (PL-KRON86-NH / PL-EVRF2007-NH — 120 / 407 wystapien w probce). **Wniosek ograniczony:** w 49 arkuszach, gdzie istnieja oba piony, NIGDY nie sa to ta sama kampania (KRON86 maks. 2018-2019, EVRF2007 >= 2022 w wygrywajacych warstwach; `out/..` lista w logu analizy), wiec roznicy datum nie da sie wydzielic z realnych zmian terenu (mediana 0.21 m jest zgodna z oczekiwana skala "kilkanascie cm" tylko luzno). Nie wiem, czy starsze rekordy EVRF2007 (np. 2019-2021 w 2023iStarsze) sa konwersja tych samych pomiarow KRON86; Kartograf ich nie wybiera.

### C9 (nietypowe pliki)
Rozszerzenia URL w 527 rekordach NMT/NMPT: `.asc` 524, `.ASC` 2 (5 m 2022iStarsze: N-33-115-C-d-2-2, N-33-126-C-c-3-4), `.xyz` 1 (`_N-33-69-A-d-3-2.xyz`, 1 m 2019-04-29, 2023iStarsze, format "ARC/INFO ASCII GRID"). Wszystkie trzy przegrywaja z nowszym rekordem w wyzszej warstwie, wiec **nigdy nie wygrywaja** — nie znaleziono wygrywajacego `.ASC`/`.xyz`/`.zip`/`.tif`. Pole `format` ma jedyna wartosc "ARC/INFO ASCII GRID". Nazwa pliku != godlo: nie znaleziono, ale jest wariant wielkosci liter w polu godlo (C9a: `N-33-59-c-a-1-3`, rekord 2018 KRON86) — Kartograf normalizuje. Dowody: `raw/recon/N-33-59-C-a-1-3/nmt1_krn__SkorowidzeNMT2018.body`, `raw/recon/N-33-69-A-d-3-2/nmt1_evr__SkorowidzeNMT2023iStarsze.body`.

### C10 (morze, granica)
Slubice 75% nodata (`out/C10d`), Terespol 26-58%, Przemysl 9%; Zalew Wislany i Mierzeja (N-34-51-D-d-1-1, N-34-51-C-d-2-3) bez rekordow w zadnym z 5 endpointow: rc 1, `Error: Brak danych NMT 1m ...`. Swinoujscie/Kolobrzeg: NMPT nie ma 1 m (tylko 0,5 m) — podpowiedz o 0,5 m (C10g).

### C11 (naglowki ASC)
Zaobserwowane w pobranych plikach (`out/verify.json`):
- `xllcenter` w 37 plikach, `xllcorner` tylko w C6e (KRON86, PL-2000 1:1000, 2018: `xllcorner 8444000`, `cellsize 1`, `NODATA_value -9999.0`).
- `cellsize` niecalkowite: C6b/C6h (0.99937..., 0.99960...); 5 m z fazami `xllcenter 535825.200`, `704335.00`, `244780.00`; `cellsize 1.0` w C9a.
- `NODATA_value`: `-9999` (36 plikow), `-9999.0` (C6e). Sidecar `nodata: -9999.0` zgodny z kazdym (W6). Liczba komorek = ncols x nrows we wszystkich plikach.
- Nie znaleziono innej wartosci NODATA niz -9999.

### C16 (NMPT)
Zalegosc NMPT wzgledem NMT (z probki 110 + 51 arkuszy): np. M-34-6-B-c-4-2 NMT 2025-04-26, NMPT 2019-04-19; 57 wygrywajacych NMPT w 2023iStarsze wobec 13 w 2025. NMPT nie ma 1 m w wielu arkuszach, gdzie NMT ma (czesto tylko 0,5 m). Mieszanie NMT (2025) z NMPT (2019) daje rozne kampanie (np. nDSM) — Kartograf jest zgodny z deklaracja, ale uzytkownik nie dostaje ostrzezenia. Warstwy NMPT 2026 sa w GetCapabilities, ale w probce nie wygral zaden rekord z 2026 (NMT tez nie: 2026 pusty w probce).

## E11: wartosci pola ukladu poziomego (repr z surowych rekordow)

Pole `ukladWspolrzednychPoziomych` wystapilo w 1131 rekordach z 2430 body (211 arkuszy x endpointy; fallback `ukladWspolrzednych` w zadnym nie byl potrzebny). Skrypt: `scripts/uklad.py`. "Zaakceptowany" = zgodny z `PL-1992` lub `^PL-2000:S[5-8]$` (regula z `skorowidz._horizontal_crs`, powtorzona niezaleznie).

| repr() | liczba | zaakceptowany | `horizontal_crs` sidecara |
|---|---|---|---|
| `'PL-1992'` | 1080 | tak | EPSG:2180 |
| `'PL-2000:S5'` | 11 | tak | EPSG:2176 |
| `'PL-2000:S6'` | 24 | tak | EPSG:2177 |
| `'PL-2000:S7'` | 10 | tak | EPSG:2180 (nie 2178: plik jest w 1992, patrz C6b/C6h) |
| `'PL-2000:S8'` | 6 | tak | EPSG:2179 |

Nie znaleziono: wariantow bez strefy (`'PL-2000'`), bialych znakow, malych liter ani innych wartosci w tej probce. Zmienne wartosci wystepuja za to w polu `godlo` (male litery: `N-33-59-c-a-1-3`). Wnioski dla review-1 D3 ograniczone do tej probki: realne dane maja tylko 5 wartosci, wszystkie scisle.

## Nie znaleziono w danych (liczba sprawdzonych arkuszy)
- C2 rozstrzygajacy remis aktualnosci: nie znaleziono w 211 arkuszach (remis tylko w przegrywajacych rekordach).
- C5 nowsza niepelna + starsza pelna: nie znaleziono (13 arkuszy z wygrywajacym `calyArkusz=NIE`, zero z alternatywa).
- C9 wygrywajacy `.ASC`/`.xyz`/`.zip`/`.tif`, nazwa pliku inna niz godlo: nie znaleziono (527 rekordow; `.ASC` x2 i `.xyz` x1 tylko przegrywajace).
- PL-2000 1:5000 i 1:500: nie znaleziono (211 arkuszy; tylko 1:2000 i 1:1000).
- Inny NODATA niz -9999: nie znaleziono (38 plikow).
- KRON86 i EVRF2007 z tej samej kampanii: nie znaleziono (49 arkuszy z obiema warstwami).
- Rekord z innym wariantem pola ukladu (E11): nie znaleziono.
- Remis wygrywajacy na `dt_pzgik` albo URL: nie ma dowodu na zywo.

## Propozycje dla rejestru wymagan i testow offline

Zadnych FAIL. Propozycje dla UWAG i nowych wzorcow (surowe body juz leza w katalogu danych, kopiowac do `tests/fixtures/gugik_skorowidz/`):

1. **PL-2000:S7 z plikiem w EPSG:2180 (C6b/C6h, UWAGA).** Fixture: `<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/a/raw/recon/M-34-64-D-d-2-3/nmt1_evr__SkorowidzeNMT2023iStarsze.body` (dwa rekordy 7.125.11.19: 2021-10-05 i 2023-03-17) oraz naglowek `.../raw/C6/77912_1384976_7.125.11.19.head`. Asercje: wybrany 77912 (max aktualnosc); przy pliku z `xllcenter 567975.95` sidecar ma `horizontal_crs == "EPSG:2180"`, `extra.source.uklad == "PL-2000:S7"`, ostrzezenie o niezgodnosci uklady; plik trafia do segmentu `pl_2000_`. Do rejestru: E-nowe "sidecar ma uklad faktycznego pliku, deklaracje rekordu zachowuje w `extra.source`" oraz decyzja, czy segment sciezki ma niesc uklad pliku (obecnie godla) — dla UZYTKOWNIKA plik w katalogu `pl_2000` ma wspolrzedne 1992 (rozbieznosc W7 vs W4; nie wiem, czy zamierzona — ADR-026 mowi o godle).
2. **0,5 m nowsze niz 1 m w innej warstwie (C3/C1c).** Fixtury: `raw/recon/M-33-57-C-b-4-2/nmt1_evr__SkorowidzeNMT2025.body` + `...2023iStarsze.body`. Test: dla `resolution_m=1.0` wynik = rekord 1 m z 2023iStarsze (2023-05-04, URL 78954_1462161), bez bledu przy przejsciu przez warstwe 2025 zawierajaca tylko 0,5 m. Mutacja: usuniecie filtra rozdzielczosci wybiera 0,5 m z 2025.
3. **Wiele kampanii w jednej warstwie (C1b).** `raw/recon/M-34-66-B-a-2-1/nmt1_evr__SkorowidzeNMT2023iStarsze.body` (2019-02-16, 2022-05-31, 2023-03-29): wygrywa 77381.
4. **Rekord z godlem malymi literami (C9a).** `raw/recon/N-33-59-C-a-1-3/nmt1_krn__SkorowidzeNMT2018.body`: `select_sheet_record` akceptuje, `extra.source.godlo == "N-33-59-C-a-1-3"`.
5. **`.ASC` i `.xyz` w URL (C9).** `raw/recon/N-33-115-C-d-2-2/nmt5_evr__SkorowidzeNMT2022iStarsze.body` (`.ASC`) i `raw/recon/N-33-69-A-d-3-2/nmt1_evr__SkorowidzeNMT2023iStarsze.body` (`.xyz`): asercja, ze rozszerzenie nie wplywa na wybor (wygrywa najnowszy), oraz — brak testu na wygrana wariantu z innym rozszerzeniem: dla pliku zapisanego jako `.asc` trzeba zdecydowac, czy rozszerzenie jest brane z URL (nie wiem; nie przetestowano, bo takie rekordy nie wygrywaja).
6. **Podpowiedz PL-2000 1:10000 (C6f/C6g).** `raw/recon/6.129.30/nmt1_evr__SkorowidzeNMT2023iStarsze.body` i `raw/recon/5.167.25/nmt1_krn__SkorowidzeNMT2019.body`: asercja komunikatu "Dostepny potomek ... --scale 1:1000 / 1:2000" oraz "Skorowidz ma ten obszar w PL-1992: ...". Uwaga: przy wielu potomkach hint wymienia jednego (6.129.30.13.4); do rejestru jako obserwacja.
7. **NMPT tylko 0,5 m (C10g).** `raw/recon/N-33-77-A-d-2-2/nmpt_evr__SkorowidzeNMPT2024.body`: NoCoverageError z "GUGiK ma ten arkusz w 0.5 m".
8. **Arkusz granicy, NIE-pelny (C5).** `raw/recon/N-34-144-C-c-2-2/nmt1_evr__SkorowidzeNMT2025.body`: wybrany rekord ma `full_sheet False`; wymaganie do rejestru: plik niepelny (mniejszy zasieg) NIE jest bledem, a `W8` dla takich plikow wymaga wyjatku "zasieg <= godlo".
9. **Warstwa NMPT starsza niz NMT (C16a).** `raw/recon/M-34-6-B-c-4-2/nmpt_evr__*` vs `nmt1_evr__*`: dokumentacja, ze `nmt` i `nmpt` jednego godla moga pochodzic z kampanii rozniacych sie o lata; brak asercji kodu (kod zgodny), propozycja wymagania: `kartograf` nie scala NMT i NMPT, a wycinek nDSM wymaga sprawdzenia `aktualnosc` z obu sidecarow.
10. **Naglowki ASC (C11).** Plik z `xllcorner` (C6e: `out/C6e/nmt/pl_2000_1m_kron86/8/193/14/01/1/8.193.14.01.1.asc`) i `NODATA_value -9999.0` oraz plik `cellsize 0.9993671653521061`: test `read_asc_nodata` zwraca -9999.0 dla obu zapisow; test warpu/mozaiki na niecalkowitym cellsize (nie testowane tu, bo wycinek poza zakresem E2E-A).
