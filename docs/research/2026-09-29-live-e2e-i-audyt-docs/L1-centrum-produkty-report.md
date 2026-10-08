# L1 — centrum, produkty (Spytkowice k. Krakowa) — raport z testow na zywych danych GUGiK

- Data: 2026-09-29, 09:25-09:58 CEST. Galaz `develop`, HEAD `152c31e` (bez zmian; `git status` czysty
  przed i po). `kartograf 0.7.0-dev`, `.venv` repo.
- Katalog roboczy: `e2e-data/2026-09-29-live/L1-centrum-produkty/` (wszystkie polecenia z niego; `-o ./data`).
- Pobrano lacznie ok. 300 MB (`data/` 286 MB, `ref/` 11 MB, `data-lazcheck/` 1,7 MB), `--workers 2`.
- Dowod "bez sieci": przebiegi oznaczone `nonet` uruchamiane w `unshare -rn` (osobna przestrzen
  sieciowa, tylko petla `lo` w stanie DOWN, DNS nie dziala) — kontrola A4d pokazuje, ze kazda proba
  wyjscia w siec konczy sie tam bledem.

**Wynik: 8 PASS, 5 UWAGA, 7 FAIL** (w tym 1 FAIL poza zakresem L1 — wycinek, przekazany do L2/(f)).

Najwazniejsze:
1. **KRYTYCZNE — LAZ pobiera kafle z miejsca o zamienionych osiach** (426 km od zadanego bboxa;
   dowod: godlo kafla, wspolrzedne punktow, zgodnosc gruntu z NMT w miejscu transponowanym co do
   0,000 m, test A/B na WFS).
2. `--product orto` pobiera **CIR** (podczerwien w barwach umownych) zamiast RGB; w warstwie
   "Starsze" wybiera **najstarsze** zdjecie (2003 cz-b).
3. Godla PL-2000 (NMT i orto) dostaja **po cichu inny arkusz PL-1992**; tryb listy `--system 2000`:
   pliki pokrywaja **0,0 %** zadanego bboxa, exit 0.
4. Przejsciowe bledy GUGiK (dzis ok. 50 % zerwanych polaczen) po cichu zmieniaja wynik: starsza
   kampania zamiast nowszej (NMT/NMPT/orto), pominiety rocznik (LAZ); NMPT z listy wpisanej na sztywno
   w ogole nie da sie pobrac.
5. Sidecary arkuszy pominietych (juz na dysku) nie dostaja `extra.parent_request` (4 z 9 w C1).

---

## Zakres

| Obszar / obiekt | Wartosc | Dlaczego |
|---|---|---|
| Arkusz glowny | `M-34-76-A-a-1-1` (Kartograf "1:10000"; GUGiK: modul 1:5000), 19,500-19,531°E / 49,979-50,000°N, EPSG:2180 `535822.7,234772.6,538078.1,237103.6` — Spytkowice, ok. 30 km WSW od Krakowa | propozycja kontrolera (`M-34-76-A-a-1` to w nomenklaturze Kartografu 1:25000 — wzialem jego arkusz NW 1:10000); ok. 46 km na E od prostokata CZ (18,86°E) -> `--country auto` = tylko PL |
| Pokrycie (sprawdzone na WMS przed pobraniem, `logs/00_*`, `03_*`) | NMT 1 m EVRF2007: 2024 (+2023iStarsze); NMT 1 m KRON86: 2012; NMT 5 m: 2022; NMPT EVRF2007: 2023, KRON86: 2017iStarsze; orto: 2024 (CIR+RGB) + 10 wpisow w "Starsze" | wszystkie produkty dostepne -> kazda porazka to blad, nie brak danych |
| Godla grubsze | `M-34-76-A-a-1` (1:25000 -> 4 arkusze), `M-34-76-A-a` (1:50000 -> 16 arkuszy), 5 m | rozwijanie hierarchii 1- i 2-poziomowe |
| PL-2000 | `7.124.7.4` (1:5000, EPSG:2178, 4000 x 2500 m; srodek w `M-34-76-A-a-1-1`); lista `--system 2000` -> `7.123.7, 7.123.8, 7.124.7, 7.124.8`; orto `7.124.07.24` (1:2000 — GUGiK ma dla niego prawdziwy arkusz orto PL-2000) | uklad data/ `pl_2000_*` |
| Tryb listy bbox | `536000,233000,541000,238000` (5 x 5 km, 9 arkuszy, przecina granice `M-34-64`/`M-34-76`); brak pokrycia 5 m: Bialystok `N-34-130-D-d-2-4` (bbox 200 x 200 m) | pkt (c) |
| LAZ | bbox `536400,235100,536600,235300` (200 x 200 m, 1 kafel); sondy discovery (bez pobierania): Spytkowice, Wadowice (zasieg NMT 2026), Krakow Rynek, okolice `6.162.34.02` | pkt (b); szukanie kafli w obu ukladach |

## Stan uslugi GUGiK (wazne dla interpretacji)

Do ok. 09:33 bez bledow. Od ok. 09:35 GUGiK (mapy.geoportal.gov.pl: WMS skorowidzow i WFS LIDAR)
zrywa mniej wiecej co drugie swieze polaczenie: `RemoteDisconnected('Remote end closed connection
without response')`, raz `ConnectionResetError 104`, raz `Read timed out (30 s)`. Miara:
`pytest -m live` 4 z 8 zapytan zerwanych; w przebiegach CLI 1-8 zerwanych zapytan warstw na
przebieg. Pelna lista z godzinami: `logs/service_incidents.log`. Zgodnie z zasadami ponawialem raz
(C5 -> C5b, zapytania diagnostyczne). Byc moze to obciazenie od kilku agentow naraz — dla uzytkownika
bez znaczenia: Kartograf musi to znosic, a dzis nie znosi (BUG-L1-5).

## Wyniki per scenariusz

| ID | Polecenie (z katalogu roboczego; `K=kartograf`) | Exit | Czas | Werdykt |
|---|---|---|---|---|
| A1 | `K download M-34-76-A-a-1-1 --resolution 1m --vertical-crs EVRF2007 -o ./data --workers 2` | 0 | 15,1 s | PASS |
| A2 | `... --resolution 1m --vertical-crs KRON86 ...` | 0 | 17,4 s | PASS |
| A3 | `... --resolution 5m ...` | 0 | 2,6 s | PASS |
| A4 | A1-A3 ponownie w `unshare -rn` (+ kontrola A4d: brakujacy arkusz bez sieci) | 0/0/0 (A4d: 1) | 0,36-0,40 s | PASS (UWAGA: komunikat) |
| A5 | `K download M-34-76-A-a-1 --resolution 5m ...` | 0 | 4,6 s | PASS |
| A6 | `K download 7.124.7.4 --resolution 1m --vertical-crs EVRF2007 ...` | 0 | 14,7 s | **FAIL** (BUG-L1-4) |
| A7 | `K download M-34-76-A-a --resolution 5m ...` | 0 | 32,0 s | UWAGA (BUG-L1-5) |
| B1 | `K download M-34-76-A-a-1-1 --product nmpt ...` | 0 | 26,7 s | UWAGA (BUG-L1-9, -5) |
| B2 | `K download M-34-76-A-a-1-1 --product orto ...` | 0 | 15,0 s | **FAIL** (BUG-L1-2) |
| B3 | `K download --bbox 536400,235100,536600,235300 --product laz ...` | 0 | 24,7 s | **FAIL** (BUG-L1-1) |
| B3b | B3 ponownie w `unshare -rn` | 1 | 0,38 s | UWAGA (BUG-L1-8) |
| B4 | `K download 7.124.07.24 --product orto ...` | 0 | 14,8 s | **FAIL** (BUG-L1-4) |
| B5 | orto "Starsze": `GugikOrtoProvider._get_opendata_url` na realnej odpowiedzi, lista warstw zawezona do `Starsze` (symulacja arkusza z najnowszym zdjeciem <= 2023) | — | — | **FAIL** (BUG-L1-3) |
| C1 | `K download --bbox 536000,233000,541000,238000 --resolution 5m ...` | 0 | 14,4 s | UWAGA (BUG-L1-6) |
| C2 | C1 ponownie w `unshare -rn` | 0 | 0,39 s | PASS |
| C4 | C1 + `--bbox-crs EPSG:2180 --system 2000` | 0 | 5,5 s | **FAIL** (BUG-L1-4) |
| C5 | `K download --bbox 770937,509535,771137,509735 --resolution 5m ...` (Bialystok, brak 5 m) | 1 / 1 (C5b) | 1,2 s | PASS |
| D1 | `.venv/bin/python -m pytest <repo>/tests -m live -q -p no:cacheprovider -rA` | 0 | 3,1 s | UWAGA (BUG-L1-10) |
| E1-E8 | ponowne NMPT/orto bez sieci, walidacje flag (patrz nizej) | zgodnie z oczekiwaniem | ~0,36 s | PASS |
| F1 | `unshare -rn K download --bbox 536000,233000,541000,238000 --resolution 5m --target-crs EPSG:2180 ...` | 0 | 0,59 s | **FAIL** — poza zakresem L1 (BUG-L1-7, dla L2/(f)) |

### A1-A3 — godlo 1:10000: 1 m EVRF2007, 1 m KRON86, 5 m — PASS

- Sciezki: `data/nmt/pl_1992_1m_evrf2007/M-34/76/A/a/1/1/M-34-76-A-a-1-1.asc`,
  `data/nmt/pl_1992_1m_kron86/...`, `data/nmt/pl_1992_5m_evrf2007/...` — zgodne z CLAUDE.md
  "Uklad data/" i ARCHITECTURE 3.3 (segment + hierarchia `path_parts`). Sidecar obok kazdego pliku.
- Sidecary: `dataset` `pl.gugik.nmt_1m` / `nmt_1m` / `nmt_5m`; `horizontal_crs` `EPSG:2180`;
  `vertical_crs` `EPSG:9651` / `EPSG:9650` / `EPSG:9651`; `resolution` 1m/1m/5m; `nodata` -9999.0
  (z naglowka ASC); `request {"godlo": ...}`; `transform: null`; `extra: {}` (tryb godlowy — bez
  `parent_request`, zgodnie z 3.4). Wszystkie pola schematu 3.2 obecne.
- Tresc (`logs/A1_inspect.log`, `A2_A3_inspect.log`, `A1_A2_A3_compare.log`):
  - 1 m: 2256 x 2331 px, piksel 1 m, zasieg `(535822.5, 234772.5, 538078.5, 237103.5)` — od obwiedni
    arkusza rozni sie o < 0,5 m; nodata 1,38 % w trojkatach przy krawedziach (arkusz to czworokat
    w 2180) + 0,19 % wewnatrz. KRON86 na tej samej siatce co EVRF2007.
  - wysokosci 217-297 m (dolina Wisly ~218 m) — wiarygodne; **EVRF2007 - KRON86 = mediana +0,21 m**
    (p25 +0,17, p75 +0,26) — pion w sidecarach zgadza sie z trescia;
  - 5 m: 451 x 466 px; **5 m (2022) - 1 m (2024) = mediana -0,03 m**.
- ASC GUGiK nie niesie CRS (`rasterio crs=None`) — jedynym nosnikiem CRS jest sidecar.

### A4 — drugie uruchomienie = pominiecie bez sieci — PASS (UWAGA: komunikat)

A1-A3 powtorzone w `unshare -rn`: exit 0, 0,36-0,40 s, `stat` (mtime, rozmiar) wszystkich plikow
identyczny przed i po (`logs/A4_before.stat`, `A4_after.stat`). Kontrola A4d (arkusz, ktorego nie ma
na dysku, w tej samej przestrzeni bez sieci) -> exit 1 `GUGiK WMS skorowidz unavailable ... all 4
layer queries failed` — izolacja dziala, wiec brak bledu w A4a-c dowodzi braku ruchu sieciowego.
UWAGA: pominiety arkusz 1:10000 raportowany jako `Downloaded to data/...` (nie ma sladu, ze to skip).

### A5, A7 — godla grubsze — PASS / UWAGA

- A5 `M-34-76-A-a-1` (1:25000): 4 arkusze, pasek postepu `○` (skip) dla `-1-1` z A3, `✓` dla 3
  nowych; exit 0; 4 sidecary z `request.godlo` = godlo LISCIA.
- A7 `M-34-76-A-a` (1:50000): 16 arkuszy (6 skip, 10 nowych), 16 sidecarow, exit 0; zasiegi zgodne
  z arkuszami (`logs/A7_inspect.log`). UWAGA: w trakcie 8 zapytan warstw 2025/2024/2023 zerwanych
  (7 x RemoteDisconnected, 1 x ReadTimeout 30 s) — provider po cichu przeszedl do 2022iStarsze
  (tu wynik ten sam, bo nowsze warstwy sa tu puste; ogolnie — BUG-L1-5).
- `Downloaded 4 files` / `Downloaded 16 files` liczy tez pominiete.

### A6 — godlo PL-2000 `7.124.7.4`, 1 m EVRF2007 — FAIL (BUG-L1-4)

Sciezka `data/nmt/pl_2000_1m_evrf2007/7/124/7/4/7.124.7.4.asc` zgodna z ADR-026 (podzial po
kropkach), ale tresc to arkusz PL-1992 `M-34-76-A-a-1-1` (md5 `fbbab3d8...` identyczne z A1);
pokrywa 33,5 % zadanego arkusza PL-2000. Szczegoly w BUG-L1-4.

### B1 — NMPT 1 m — UWAGA (tresc PASS)

`data/nmpt/pl_1992_1m_evrf2007/M-34/76/A/a/1/1/M-34-76-A-a-1-1.asc` + sidecar (`pl.gugik.nmpt`,
2180, 9651, 1m). Tresc: ta sama siatka co NMT 1 m; NMPT(2023) - NMT(2024): mediana 0,00 m, p95
+7,4 m, 11,5 % pikseli > 2 m nad terenem — wiarygodny NMPT. UWAGA: stderr za kazdym razem
`WMS GetCapabilities returned different layers than hardcoded ... Consider updating WMS_LAYERS`
(BUG-L1-9) i zerwane zapytanie warstwy 2026 (BUG-L1-5).

### B2 — orto godlo — FAIL (BUG-L1-2)

`data/orto/pl_1992/M-34/76/A/a/1/1/M-34-76-A-a-1-1.tif` (+ sidecar: 2180, `vertical_crs null`,
`resolution null`, `nodata null`) — GeoTIFF EPSG:2180, 0,25 m, 9023 x 9326, poczatek `535822.5,
237103.75` — geometrycznie zgodny z arkuszem, ale to zdjecie **CIR**. stdout: `Downloading
M-34-76-A-a-1-1 (resolution: 1m)...` — rozdzielczosc NMT w komunikacie orto.

### B3 — LAZ bbox — FAIL (BUG-L1-1)

exit 0, 1 kafel: `data/laz/pl_1992_evrf2007/N-33/127/A/a/2/3/4/74957_1079797_N-33-127-A-a-2-3-4.laz`
(43 MB) + sidecar (`pl.gugik.laz`, 2180, 9651, `request.bbox` = zadanie, `extra` =
`godlo_kafla`/`rok` 2021/`gestosc` 4/`url`; bez `parent_request` — zgodnie z 3.4). Segment
`pl_1992` poprawnie z `uklad_xy` kafla (`PL-1992`). Ale kafel lezy 426 km od zadanego obszaru.

### B3b — LAZ ponownie bez sieci — UWAGA (BUG-L1-8)

exit 1 `Error: No LAZ tiles found for the given area.` — przyczyna to 9 nieudanych zapytan WFS,
nie brak kafli. LAZ zawsze najpierw odpytuje WFS, wiec pominiecie "bez sieci" (jak NMT) tu nie
istnieje — do udokumentowania.

### B4 — orto godlo PL-2000 `7.124.07.24` — FAIL (BUG-L1-4)

exit 0, **pusty stderr**; `data/orto/pl_2000/7/124/07/24/7.124.07.24.tif` ma md5 `3d196a08...` =
arkusz PL-1992 CIR z B2 — mimo ze GUGiK publikuje prawdziwy arkusz PL-2000 `7.124.07.24`.

### C1-C5 — tryb listy arkuszy `--bbox` bez `--target-crs`

- C1 (UWAGA): `Found 9 sheets at 1:10000 for bbox (resolution: 5m)`, lista 9 godel, po 14 s
  `Downloaded 9 files to data` (4 z nich pominiete — komunikat tego nie odroznia; w trybie
  listy 1:10000 z `--workers > 1` brak postepu per arkusz). exit 0. 9 arkuszy + 9 sidecarow, zasiegi
  i wysokosci wiarygodne (`logs/C1_inspect.log`), bbox pokryty w 100 %. **Tylko 5 z 9 sidecarow ma
  `extra.parent_request`** `{"bbox": [536000.0, 233000.0, 541000.0, 238000.0], "bbox_crs":
  "EPSG:2180", "countries": ["PL"]}` — 4 pominiete zachowaly stare sidecary z A3/A5 bez rodzica
  (`logs/C1_sidecars.log`; BUG-L1-6).
- C2 (PASS): C1 w `unshare -rn` — exit 0, 0,39 s.
- C4 (FAIL): `--system 2000` — 4 godla PL-2000, 4 ostrzezenia "URL innego arkusza", exit 0,
  pliki pokrywaja 0,0 % bboxa (BUG-L1-4).
- C5 (PASS): Bialystok, brak 5 m. Pierwszy przebieg: 2 z 4 warstw zerwane -> `Error: GUGiK WMS
  skorowidz: 2 z 4 warstw nie odpowiedzialo dla N-34-130-D-d-2-4, pozostale nie maja arkusza — brak
  pokrycia niepewny ...` exit 1 (straz R5 zadzialala poprawnie — chwilowy blad nie udaje braku
  danych). Ponowienie C5b: `Error: No NMT 5m data available for N-34-130-D-d-2-4
  (vertical_crs=EVRF2007). This area may not have 5m coverage in GUGiK. ...` exit 1 — czytelne.
  Po porazce zostaje pusty katalog `data/nmt/pl_1992_5m_evrf2007/N-34/130/D/d/2/4/` (tak samo w A4d).

### D1 — `pytest -m live` — UWAGA (BUG-L1-10)

`4 passed, 4 skipped, 1861 deselected in 2.55s`, exit 0; 4 skipy = `WMS not reachable:
RemoteDisconnected`. Testy nie mowia nic o pobieraniu: odpytuja nieistniejaca warstwe i sprawdzaja
tylko HTTP 200.

### E1-E8 — PASS

| ID | Przypadek | Wynik |
|---|---|---|
| E1/E2 | NMPT / orto ponownie w `unshare -rn` | exit 0, 0,36 s |
| E3 | `--resolution 5m --vertical-crs KRON86` (godlo) | exit 0; stderr `Resolution 5m only supports EVRF2007, changing vertical_crs from 'KRON86' to 'EVRF2007'`; segment `pl_1992_5m_evrf2007` |
| E4 | `--bbox 536000,233000,541000` | exit 1 `Error: Invalid bbox format: BBOX must have 4 values` (stderr) + `Expected: ...` (stdout) |
| E5 | `--product nmpt --resolution 5m` | exit 1 `Error: --product nmpt jest dostepny tylko w rozdzielczosci 1m (podano 5m)` |
| E6 | `--product orto --vertical-crs KRON86` | exit 1 `Error: --vertical-crs nie dotyczy --product orto ...` |
| E7 | godlo + `--target-crs EPSG:2180` | exit 1 `Error: --target-crs dziala tylko z --bbox/--geometry; ...` |
| E8 | `M-34-76-A-a-1 --scale 1:10000 --resolution 5m` w `unshare -rn` | exit 0, `Downloading 4 sheets ...`, 4 x `○` |

### F1 — wycinek EPSG:2180 z arkuszy 5 m o roznych fazach — FAIL (poza zakresem L1; BUG-L1-7)

Uruchomiony, bo moje 9 arkuszy 5 m okazaly sie miec 9 roznych faz siatki; bez sieci (arkusze
z cache). Szczegoly — BUG-L1-7.

---

## Bledy

### BUG-L1-1 (KRYTYCZNY) — LAZ: discovery WFS z zamienionymi osiami — kafle z innego miejsca Polski

**Reprodukcja:** `kartograf download --bbox 536400,235100,536600,235300 --product laz -o ./data`
(bbox 200 x 200 m pod Spytkowicami, 19,509°E 49,983°N). **Wynik:** exit 0, kafel
`N-33-127-A-a-2-3-4` (2021, 4 p/m2). **Oczekiwane:** kafel(e) pokrywajace bbox — WFS zapytany
z poprawna kolejnoscia osi zwraca `M-34-76-A-a-1-1-3` (2023, 4 p/m2,
`77518_1352498_M-34-76-A-a-1-1-3.laz`, 19,508°E 49,984°N; ta sama kampania co NMT/NMPT 77519/77520).

**Dowody (cztery niezalezne):**
1. Godlo kafla `N-33-127-A-a-2-3-4` -> arkusz `N-33-127-A-a-2-3` = 15,06-15,09°E / 52,625-52,646°N
   (Lubuskie, okolice Skwierzyny) — a nie okolice Krakowa.
2. Punkty w pliku (standard LAS: X = wschod, Y = polnoc; `laspy`): E 234661-235780, N 535970-537185
   -> 15,086°E 52,630°N — **426,3 km** od zadanego bboxa; wszystkie wewnatrz arkusza z pkt 1.
3. Punkty gruntu (klasa 2, 5,39 mln) maja Z 13,7-17,9 m; NMT w zadanym miejscu ma 231-297 m. NMT 5 m
   pobrany dla `N-33-127-A-a-2-3` (miejsce transponowane): **LAZ grunt - NMT = mediana 0,000 m**
   (p5 -0,08, p95 +0,08; 26 946 punktow) — kafel jest poprawny, tylko z innego miejsca.
4. Test A/B na WFS (`logs/B3_wfs_axis_test.log`): `BBOX=235100,536400,235300,536600,urn:ogc:def:crs:EPSG::2180`
   (N,E) -> w roku 2023 `M-34-76-A-a-1-1-3` (Spytkowice); to, co wysyla Kartograf,
   `BBOX=536400,235100,536600,235300,urn:...` (E,N) -> `N-33-127-A-a-2-3-4` z
   `lowerCorner '535970.42 234660.93'`, co w kolejnosci (N,E) daje wlasnie 15,086°E 52,630°N.

**Hipoteza (plik:linia):** `kartograf/providers/pl/gugik_laz.py:363-369` — `BBOX` sklejany jako
`min_x,min_y,max_x,max_y` (E,N) z CRS `urn:ogc:def:crs:EPSG::2180`, dla ktorego serwer stosuje
kolejnosc osi EPSG (polnoc, wschod); `:464-465` czyta `gml:Envelope` (N,E) jako (x,y). Zamiana
w obie strony jest spojna, wiec filtr `_intersects` (`:482-497`, "safety net against WFS axis-order
quirks") i komentarz "Verified live" (`:363-365`) jej nie widza. Obserwacja z pamieci projektu
(`M-34-27-B-b-2-1` -> kafle `N-33-131-B-a-1-*`) byla objawem tego bledu.

**Zasieg:** wszystkie tryby LAZ (godlo/`--bbox`/`--geometry` sprowadzane do bboxa 2180 E,N).
Przyklady z dokumentacji (`CLAUDE.md:160`, `docs/PRD.md:225`, docstring `gugik_laz.py:29`) szukaja
kafli ok. 209 km od podanego obszaru (17,29°E 52,64°N zamiast 19,45°E 51,32°N). Gdy obszar
transponowany wypada poza Polska — mylace `No LAZ tiles found`.

### BUG-L1-2 (WYSOKI) — orto: CIR zamiast RGB

**Reprodukcja:** `kartograf download M-34-76-A-a-1-1 --product orto -o ./data`. **Wynik:** plik
38 655 130 B = `Content-Length` URL-a `81422_1368112_M-34-76-A-a-1-1.tif`, ktory skorowidz opisuje
`kolor:"CIR"` (RGB `81423_1371958_...` ma 43 766 986 B); srednie pasm (161,6; 83,0; 94,3), pasmo 1 >
pasmo 2 + 20 na 93,4 % pikseli (bliska podczerwien w kanale czerwonym). **Oczekiwane:** RGB
(zdjecie lotnicze w barwach naturalnych). **Systematyczne:** wybor providera dla `M-34-64-D-a-3-4`
(2024) i `M-34-74-D-d-2-2` (2025) tez = CIR — w obu kampaniach wpis CIR poprzedza RGB (numery prac
81422 < 81423, 83854 < 83855) (`logs/08_orto_pick_1.log`).

**Hipoteza:** `kartograf/providers/pl/gugik_orto.py:376-384` — pierwszy URL zawierajacy godlo
w pierwszej warstwie, ktora ma jakikolwiek URL; brak wyboru po `kolor` (RGB) i `aktualnosc`
(skorowidz te pola podaje w `skorDo5cm.push({...})`). Sidecar nie ma koloru ani URL-a — uzytkownik
nie ma jak zauwazyc.

### BUG-L1-3 (WYSOKI) — orto z warstwy "Starsze": najstarsze zdjecie zamiast najnowszego

**Dowod (`logs/02_orto_entries_*.log`, `09_orto_starsze_sim.log`):** warstwa
`SkorowidzeOrtofotomapyStarsze` zwraca wpisy **rosnaco po dacie** (dla `M-34-76-A-a-1-1`: 1997 RGB
arkusz 1:10000 -> 2003 B/W -> 2009 -> 2015 CIR/RGB -> 2015 PL-2000 -> 2018 -> 2019 -> 2022 RGB/CIR).
Provider z lista warstw zawezona do `Starsze` (symulacja arkusza, ktorego najnowsza orto jest
<= 2023; realna odpowiedz serwera, kod providera bez zmian) zwraca `17_21794_M-34-76-A-a-1-1.tif`
= **2003, czarno-biale**; dla `M-34-64-D-a-3-4` `17_37258_...` (2003 B/W) zamiast 2023-09-08 RGB.
**Osiagalnosc:** kazdy arkusz, ktorego najnowsze zdjecie jest z lat <= 2023 (GUGiK skonsolidowal
2018-2023 w "Starsze"); w trzech sondach nie trafilem na taki arkusz (wszedzie byly 2024/2025),
stad symulacja. **Hipoteza:** ta sama petla `gugik_orto.py:376-384` (zaklada kolejnosc
od najnowszego wewnatrz warstwy).

### BUG-L1-4 (WYSOKI) — godla PL-2000: po cichu inny arkusz PL-1992

- **NMT, godlo** (A6): `kartograf download 7.124.7.4 --resolution 1m --vertical-crs EVRF2007` ->
  exit 0, stderr `7.124.7.4: skorowidz zwrocil URL innego arkusza (https://opendata.geoportal.gov.pl/
  NumDaneWys/NMT/81428/81428_1629594_M-34-76-A-a-1-1.asc) — plik moze byc innym arkuszem, np.
  w ukladzie PL-2000`; plik = arkusz PL-1992 `M-34-76-A-a-1-1` (md5 identyczne z A1), pokrywa
  **33,5 %** zadanego arkusza (4000 x 2500 m w EPSG:2178); sidecar `request.godlo 7.124.7.4`,
  `horizontal_crs EPSG:2180`, bez sladu podstawienia.
- **NMT, lista** (C4): `--bbox 536000,233000,541000,238000 --system 2000 --resolution 5m` -> exit 0,
  `Downloaded 4 files`; 4 pliki to arkusze PL-1992 `M-34-75-B-b-2-4`, `M-34-76-A-a-2-4`,
  `M-34-63-D-d-4-4`, `M-34-64-C-c-4-4` (2,26 x 2,33 km, ze srodkow arkuszy PL-2000 8 x 5 km) —
  pokrywaja **0,0 %** zadanego bboxa (`--system 1992`: 100 %; `logs/C4_coverage.log`).
- **Orto, godlo** (B4): `kartograf download 7.124.07.24 --product orto` -> exit 0, **zadnego
  komunikatu**; plik = arkusz PL-1992 CIR z B2 (md5 identyczne), choc GUGiK ma prawdziwy arkusz
  `64878_364829_7.124.07.24.tif` (2015 RGB, w "Starsze"; pobrany do `ref/`: 6400 x 4000 px, 0,25 m,
  poczatek `7392800, 5541000` = strefa 7).
- W badanym obszarze skorowidze NMT 1 m/5 m i NMPT maja wylacznie arkusze PL-1992
  (`ukladWspolrzednychPoziomych: PL-1992` dla 2022/2023/2024); nie znalazlem zadnego arkusza NMT
  w PL-2000 (warstwa 2026: w jej zasiegu pod Wadowicami brak wpisow w sprawdzonych punktach). Segment
  `nmt/pl_2000_*` dostaje tu wiec arkusze PL-1992 pod nazwami PL-2000.

**Hipoteza:** `kartograf/providers/pl/gugik.py:590-599` — fallback "URL innego arkusza" przyjmowany
(`logger.warning` + `return urls[0]`; kod i ARCHITECTURE 4.3 mowia, ze lista arkuszy "przyjmuje go
bez zmian", ale skutek — 0 % pokrycia przy exit 0 — nie jest nigdzie opisany);
`kartograf/providers/pl/gugik_orto.py:382-384` — ten sam fallback na poziomie DEBUG, a petla konczy
sie na pierwszej warstwie z jakimkolwiek URL-em, wiec nie dochodzi do warstwy z pasujacym godlem.
Tresc ostrzezenia NMT ("np. w ukladzie PL-2000") myli, gdy podstawiony jest arkusz PL-1992.

### BUG-L1-5 (SREDNI) — przejsciowe bledy GUGiK po cichu zmieniaja wynik

- NMT/NMPT/orto: zerwane zapytanie nowszej warstwy -> provider idzie do starszych i zwraca
  pierwszy znaleziony URL, exit 0; jedyny slad to surowa linia `WMS query failed for layer ...`.
  Zaobserwowane w A6 (2026+2025), B1 (NMPT 2026), B2 (orto 2026), C4 (2025+2024), A7 (8 zapytan).
  Tu wynik sie nie zmienil (nowsze warstwy dla tych arkuszy sa puste — sprawdzone wczesniej), ale
  tam, gdzie nowsza kampania istnieje, jedno zerwane polaczenie po cichu da starsza. Zapytania
  skorowidza nie maja ponowien (jedna proba na warstwe; `gugik.py:618-622`), plik ma ich 3.
- LAZ: `gugik_laz.py:385-388` — blad transportu -> rocznik pomijany bez bledu (B3: rocznik 2026,
  exit 0; sondy Krakow: 2026 i 2025). `FALLBACK_YEARS` (`:159-160`) konczy sie na 2025, a
  GetCapabilities pokazuje 2026 — gdy GetCapabilities zostanie zerwany (zaobserwowane), rocznik
  2026 nie jest w ogole odpytywany.
- Straz R5 dziala poprawnie (C5: "brak pokrycia niepewny", exit 1).

### BUG-L1-6 (SREDNI) — `extra.parent_request` brak w sidecarach arkuszy pominietych

**Reprodukcja:** A3/A5 (godla) -> C1 (bbox obejmujacy te arkusze). **Wynik:** 4 z 9 sidecarow bez
`parent_request` (stare, z trybu godlowego); 5 nowych z rodzicem. **Oczekiwane (ARCHITECTURE 4.2):**
"Kazdy sidecar dostaje `extra.parent_request`", a 3.4 czyni go kluczem grupowania — konsument
znajdzie 5 z 9 arkuszy zadania. Symetrycznie arkusz wspolny dwoch zadan bbox niesie tylko
pierwszego rodzica. **Hipoteza:** `kartograf/download/manager.py:326-328` (oraz `:513-514`,
`:545-554`) — skip wraca przed `_write_sidecar`. Decyzja projektowa: nadpisac/scalic sidecar przy
pominieciu albo opisac ograniczenie.

### BUG-L1-7 (WYSOKI dla R1; poza zakresem L1 — do L2 / checklisty (f)) — wycinek EPSG:2180 z arkuszy 5 m o roznych fazach

**Reprodukcja (bez sieci, arkusze z mojego cache):** `cd e2e-data/2026-09-29-live/L1-centrum-produkty;
unshare -rn kartograf download --bbox 536000,233000,541000,238000 --resolution 5m --target-crs
EPSG:2180 -o ./data` -> exit 0, stderr `mosaic_and_crop: 8 z 9 zrodel poza siatka pikseli
wiekszosci (maks. przesuniecie 0.412 px) — ich tresc przepisana najblizszym sasiadem: ...`.

**Fakty:**
- Arkusze 5 m (kampania 2022) sa tu kotwiczone we WLASNYM narozniku SW (`xllcorner` = min_x arkusza
  z dokladnoscia 0,01 m), wiec kazdy ma inna faze: x = 2,70 / 1,61 / 3,18 / 3,06 / 2,22 / 0,16 /
  3,10 / 0,52 / 2,93 m. "Siatka wiekszosci" to 1 arkusz z 9. Zalozenie "narozniki 5 m na 5k + 2,5"
  (fakt 1 planu fali) tu nie zachodzi.
- Tresc (3000 losowych pikseli, `logs/F1_cutout_nodata.log`): dla 5 arkuszy wycinek = najblizszy
  piksel zrodla (100 %); dla 4 (`M-34-64-C-c-3-4`, `M-34-76-A-a-1-2`, `-2-1`, `-2-3`) wartosc
  pochodzi z SASIEDNIEGO piksela (przesuniecie o +1 kolumne i/lub wiersz: 100 % zgodnosci,
  przy (0,0) 0,7-6,8 %) — uzyty srodek piksela zrodla lezy 2,94-4,39 m na os (0,59-0,88 px;
  dla `-2-1` 3,30 m w x i 3,89 m w y) od srodka piksela wyniku, podczas gdy najblizszy lezy
  0,61-2,06 m — to NIE jest najblizszy sasiad, wbrew komunikatowi.
- 766 pikseli nodata (0,076 %) tam, gdzie arkusze maja dane: cala prawa kolumna (463), dolny wiersz
  (134), szwy pionowe przy x ~ 538 100 i ~ 540 300 (149 z 170).
- Sidecar bez sladu (`transform: null`, brak listy arkuszy poza siatka).

**Hipoteza:** `kartograf/transport/mosaic.py:317` — `rasterio.merge.merge` dla zrodel poza siatka
zaokragla przesuniecie okien zrodel do calego piksela (wynik zalezy od znaku przesuniecia fazy)
zamiast brac najblizszy piksel, a przy okazji gubi ostatnia kolumne/wiersz stopy zrodla (szwy,
prawa i dolna krawedz); komunikat `:258-263` opisuje zachowanie nieprawdziwie.

### BUG-L1-8 (NISKI) — LAZ: `No LAZ tiles found` przy awarii sieci

B3b: bez sieci wszystkie zapytania WFS padaja, a uzytkownik dostaje `Error: No LAZ tiles found for
the given area.` (`download_cmd.py:1311`). Przy czesciowej awarii — wynik niepelny z exit 0
(BUG-L1-5).

### BUG-L1-9 (SREDNI) — NMPT EVRF2007: przestarzala lista warstw w kodzie

`gugik_nmpt.py:83-86` = `2025, 2024, 2023, 2022iStarsze`; GetCapabilities (dzis) = `2026, 2025,
2024, 2023iStarsze`. Skutki: (1) kazde pobranie NMPT drukuje dlugi warning; (2) gdy GetCapabilities
zostanie zerwany (dzis kilka razy), uzywana jest lista z kodu — dwie warstwy nie istnieja (HTTP 200 +
`LayerNotDefined`) i dla arkusza z danymi w 2023iStarsze (jak `M-34-76-A-a-1-1`) pobranie konczy sie
`DownloadError: ... 2 z 4 warstw nie odpowiedzialo ... brak pokrycia niepewny`
(`logs/B1b_nmpt_hardcoded_layers.log`). Pozostale listy (NMT 1 m obie, NMT 5 m, NMPT KRON86, orto)
zgodne z GetCapabilities.

### BUG-L1-10 (NISKI) — testy `live` nic nie sprawdzaja

`tests/test_pl2000_verification.py:456-457` odpytuje `SkorowidzeNMT2022iStarsze` na endpoincie
1 m EVRF2007 — tej warstwy juz nie ma; serwer odpowiada HTTP 200 `text/xml`
`<ServiceException code="LayerNotDefined">` (zapisane: `logs/D1_layer_missing.*`), a test
sprawdza tylko kod 200 (`:474`); blad sieci = skip (`:482`). "4 passed, 4 skipped" potwierdza
tylko, ze serwer odpowiada.

### BUG-L1-11 (latentny) — `horizontal_crs` sidecara dla plikow PL-2000

`sources/sidecar.py:111` bierze `horizontal_crs` z kanalu deskryptora (`EPSG:2180` dla NMT/NMPT/
orto/LAZ). Prawdziwy plik PL-2000 (np. orto `7.124.07.24`: wspolrzedne strefy 7, wlasny WKT
"Transverse Mercator; WGS84") dostalby `EPSG:2180`. Dzis niewidoczne tylko dlatego, ze BUG-L1-4
podstawia plik PL-1992. To samo dotyczy kafli LAZ z `uklad_xy: PL-2000:*`.

### Drobne (UX)

- `Downloaded to <sciezka>` dla pominietego arkusza (`download_cmd.py:763`); `Downloaded N files`
  liczy pominiete (`:761`, `:1143`, `:1803`).
- orto: `Downloading ... (resolution: 1m)...` (`:750`).
- Tryb listy 1:10000 z `--workers > 1`: brak postepu per arkusz (cisza 14-30 s).
- Ostrzezenia providerow to surowe linie logu bez prefiksu `Warning:`, czesto ~500 znakow
  zakodowanego URL-a (A4d, B3b, C5).
- Po nieudanym pobraniu zostaje pusta galaz katalogow (A4d, C5b) — `mkdir` przed zapytaniem WMS.
- E4: `Expected: ...` na stdout, `Error:` na stderr.

---

## Zachowanie do udokumentowania

1. ASC z GUGiK nie ma CRS (`crs=None`) — jedynym nosnikiem ukladu jest sidecar.
2. Siatki: arkusze 1 m tu (NMT 2024 EVRF2007, NMT 2012 KRON86, NMPT 2023) na tej samej siatce
   (srodki pikseli na liczbach calkowitych); arkusze 5 m (2022) kotwiczone w narozniku SW arkusza —
   faza dowolna, inna dla kazdego arkusza; krawedz E/N rastra 5 m do < 5 m krotsza od obwiedni arkusza;
   nodata ~1,3-1,4 % w trojkatach krawedziowych.
3. Ponowne uruchomienie: NMT/NMPT/orto pomijaja istniejace pliki bez sieci (0,4 s); LAZ zawsze
   najpierw odpytuje WFS (bez sieci -> blad).
4. Pominiety arkusz zachowuje stary sidecar (bez `parent_request` nowego zadania) — do opisania
   w 3.4/4.2 albo do naprawy (BUG-L1-6).
5. Skorowidz orto ma dla arkusza warianty CIR i RGB oraz wiele kampanii; "Starsze" jest od
   najstarszego — dzis Kartograf bierze pierwszy wpis (BUG-L1-2/-3).
6. NMT (co najmniej w okolicy Krakowa) jest w GUGiK tylko w PL-1992; godla PL-2000 i `--system 2000`
   daja arkusze zastepcze (NMT: warning, orto: cisza) — do opisania albo odrzucania.
7. Pliki LAZ GUGiK: LAS 1.2, LASzip, X = wschod / Y = polnoc (standard), pusty VLR GeoKeyDirectory
   (brak CRS w pliku); obok siebie kafle 4 i 12 p/m2 o roznej szczegolowosci godla (7 i 8 czlonow).
   Sidecar LAZ ma `request.bbox` takze przy wejsciu godlem (kod `_write_laz_sidecar`; nie sprawdzane
   na zywo).
8. Rozbieznosc skal (Kartograf "1:10000" = GUGiK "modul archiwizacji 1:5000" — skorowidz podaje to
   wprost dla `M-34-76-A-a-1-1`) jest opisana w ARCHITECTURE:660, ale nie w pomocy `--scale`.
9. Straz R5 (dane do (j)): pusta warstwa = HTTP 200 `text/html`, 7721 B, bez znacznikow OGC
   (`logs/D1_empty_layer.*`); nieistniejaca warstwa = HTTP 200 `text/xml` `ServiceExceptionReport`/
   `LayerNotDefined` (`logs/D1_layer_missing.*`) — straz odroznia oba przypadki poprawnie.
10. Dopoki nie ma ponowien zapytan skorowidza, wynik zalezy od tego, ktore zapytania warstw
    przejda (BUG-L1-5) — warto ostrzec w dokumentacji.

## Odpowiedzi na pozycje checklisty

**Zlecenie L1:**
- (a) Godlo PL-1992 1:10000: 1 m EVRF2007 -> `nmt/pl_1992_1m_evrf2007/`, 1 m KRON86 ->
  `nmt/pl_1992_1m_kron86/`, 5 m -> `nmt/pl_1992_5m_evrf2007/` — **tak**, w hierarchii godel,
  sidecary obok, tresc zweryfikowana; drugie uruchomienie = pominiecie bez sieci — **tak**
  (dowod `unshare -rn`). Godla grubsze (1:25000 -> 4, 1:50000 -> 16, 5 m) — **tak**. Godlo PL-2000
  1 m EVRF2007 -> sciezka `nmt/pl_2000_1m_evrf2007/7/124/7/4/7.124.7.4.asc` **poprawna**, tresc
  **bledna** (arkusz PL-1992; BUG-L1-4).
- (b) `--product nmpt` -> `nmpt/pl_1992_1m_evrf2007/` — **tak** (tresc OK). `--product orto` ->
  `orto/pl_1992/` — sciezka tak, tresc **CIR** (BUG-L1-2). `--product laz` -> segment z `uklad_xy`
  (`laz/pl_1992_evrf2007/N-33/127/A/a/2/3/4/`) i sidecar obok kafla — **tak**, ale kafel z innego
  miejsca (BUG-L1-1). Kafli w obu ukladach **nie znalazlem** (4 obszary, wszystkie kafle PL-1992;
  przy okazji: przez BUG-L1-1 kazda sonda szukala w miejscu transponowanym).
- (c) Lista `--bbox` 5 m, 5 x 5 km: 9 arkuszy, exit 0, komunikaty czytelne, lecz liczba "Downloaded"
  obejmuje pominiete, brak postepu; brak pokrycia -> exit 1 z jasnym komunikatem; niepewne pokrycie
  -> exit 1 ("niepewny"); `--system 2000` -> exit 0 przy 0 % pokrycia (FAIL).
- (d) `pytest -m live`: 4 passed, 4 skipped (zerwane polaczenia), exit 0 — ale testy sa puste
  (BUG-L1-10).
- Zgodnosc z CLAUDE.md "Uklad data/" i ARCHITECTURE 3: wszystkie powstale sciezki zgodne
  (`nmt/pl_1992_{1m_evrf2007,1m_kron86,5m_evrf2007}/`, `nmt/pl_2000_{1m,5m}_evrf2007/`,
  `nmpt/pl_1992_1m_evrf2007/`, `orto/pl_1992/`, `orto/pl_2000/`, `laz/pl_1992_evrf2007/`,
  `nmt/pl_1992_5m_evrf2007/bbox/<coords>.tif`); schemat sidecara 3.2 kompletny. Odstepstwa:
  `parent_request` (4.2 "kazdy sidecar" — BUG-L1-6), latentny `horizontal_crs` PL-2000 (BUG-L1-11).

**PROGRESS "Nastepne kroki" pkt 12:**
- (a) PL-1992 x KRON86/EVRF2007 — OK; PL-2000 — sciezka OK, tresc zastepcza (KRON86 x PL-2000 nie
  uruchamiane — ten sam mechanizm).
- (b) nmpt/orto/laz — sciezki OK; tresc: orto CIR, LAZ zle miejsce; "kafle z obu ukladow" — nie
  wykazane.
- (f) (czesciowo, dla L2) 1 m: jeden arkusz + KRON86 + NMPT na wspolnej siatce; 5 m (2022): faza per
  arkusz — mieszane fazy to tu norma, a nie wyjatek; skutki w wycinku BUG-L1-7 — sam
  `extra.off_grid_sheets` + `Warning:` nie wystarczy, potrzebna naprawa mozaiki.
- (g) Godla PL-1992 w tym obszarze: wszystkie URL-e zawieraly godlo (fallback nie wystapil) dla NMT
  1 m/5 m i NMPT; odwrotny kierunek (godlo PL-2000 -> arkusz PL-1992) jest tu regula (BUG-L1-4).
- (j) (zadanie L3) — przy okazji zapisane probki pustej odpowiedzi i raportu wyjatku (pkt 9 wyzej).

## Surowe artefakty

Katalog: `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L1-centrum-produkty/`
- `logs/<ID>.meta|.out|.err` — polecenie, czas, exit, stdout, stderr kazdego przebiegu (A1-F1).
- `logs/service_incidents.log` — zerwane polaczenia GUGiK z godzinami.
- `logs/00_wms_coverage_*.log`, `02_orto_entries_*.log`, `03_nmt_nmpt_entries_*.log`,
  `05_*`-`16_*` — sprawdzenia pokrycia i wpisy skorowidzy.
- `logs/*_inspect.log`, `A1_A2_A3_compare.log`, `C4_coverage.log`, `F1_cutout_nodata.log` — analizy
  rastrow.
- `logs/B3_*.log`, `B3c_laz_vs_nmt.log`, `B3_ground_sample.npy` — dowody LAZ.
- `logs/B1b_nmpt_hardcoded_layers.log`, `D1_empty_layer.*`, `D1_layer_missing.*`.
- `data/` (NMT/NMPT/orto/LAZ + sidecary + wycinek F1), `data-lazcheck/` (NMT 5m w miejscu
  transponowanym), `ref/64878_364829_7.124.07.24.tif` (prawdziwy arkusz orto PL-2000), `wms/*.png`.
- `scripts/` — `run.sh` (rejestrator przebiegow), `wms_coverage.py`, `featureinfo_entries.py`,
  `inspect_raster.py`, `orto_pick.py`.
- `.lasvenv/` — osobne venv z `laspy`/`lazrs` do odczytu LAZ (poza repo; `.venv` projektu nietkniete).
