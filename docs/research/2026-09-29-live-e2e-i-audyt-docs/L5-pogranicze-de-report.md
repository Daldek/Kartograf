# L5-pogranicze-de — raport testow na zywych danych (2026-09-29)

Galaz `develop`, HEAD 6985765, repo nietkniete (`git status` czysty). Wszystkie
polecenia z `e2e-data/2026-09-29-live/L5-pogranicze-de/`, dane w `runs/<przebieg>/data`,
`--resolution 5m`, `--workers 2` (jeden przebieg `--workers 1`). Okno: 09:29-09:55 CEST.

Uruchamianie: `kg.py` = dokladne lustro entry pointu `kartograf` (`kartograf.cli.commands:main`)
plus log `urllib3` do pliku (`hosts.log`, lista hostow i zapytan; root logger nietkniety, wiec
stdout/stderr sa identyczne z `.venv/bin/kartograf`). Przebiegi oznaczone **[retry-harness]**
uzywaly `kg_retry.py`: kazda `requests.Session` dostaje urllib3 `Retry` WYLACZNIE na bledy
polaczenia/odczytu (bez ponawiania po kodach HTTP) — obejscie niestabilnosci GUGiK (patrz B3);
logika Kartografa bez zmian. Harness zweryfikowany (autotest: 7 prob na zamknietym porcie).

## 1. Zakres

| ID | Obszar | bbox (EPSG:4326) | Po co |
|---|---|---|---|
| S1 | Slubice / Frankfurt (Oder) | `14.52,52.335,14.60,52.36` (w 2180: 5,6 x 3,1 km) | granica PL-DE na Odrze; poza prostokatem CZ (52,3°N > 51,06°N). Lista: 8 arkuszy `N-33-126-C-c-3-1..4-4`; wycinek: 12 (+`N-33-138-A-a-1-1..2-2`) |
| S2 | Zgorzelec / Görlitz | `14.96,51.14,15.03,51.16` (5,0 x 2,5 km) | granica PL-DE na Nysie, tuz na polnoc od 51,06°N (bez CZ). Lista 6 / wycinek 8 arkuszy `M-33-30-D-b-*`, `M-33-31-C-a-*` |
| S3 | Trojstyk PL-CZ-DE (Zittau / Hradek nad Nisou / Porajow) | `14.79,50.855,14.86,50.89` (5,1 x 4,2 km) | wszystkie trzy kraje; oba prostokaty. Lista 6 / wycinek 9 arkuszy `M-33-42-B-c-*` |
| S3c | Sieniawka / Hirschfelde | `14.86,50.92,14.90,50.94` (2,9 x 2,4 km) | DE+PL wewnatrz prostokata CZ, zero terytorium CZ — co zwraca CUZK |
| S4 | Osinow Dolny / Hohenwutzen | `14.03,52.835,14.16,52.85` (8,9 x 1,7 km) | najdalej na zachod wysuniety punkt PL (~14,12°E); 2,7 km bboxa lezy na zachod od 14,07°E (poza prostokatem PL). Auto: lista 4 / wycinek 8 arkuszy; `--country pl`: 6 / 18 |
| S5 | Berlin | `13.38,52.51,13.40,52.52` | caly bbox poza prostokatami krajow |

Swinoujscie/Uznam nie uruchomione: mechanizm 14,07°E pokazuje juz S4, morze to zakres L3,
a GUGiK byl wtedy niestabilny (B3). Kostrzyn lezy na ~14,65°E, wiec nie siega na zachod od 14,07°E.
Wolumen: 78 pobranych arkuszy ASC, 4 zapytania `exportImage` CUZK, ~520 zapytan WMS GUGiK
w przebiegach CLI i ~60 w probach recznych; lacznie 135 MB na dysku.

## 2. Wyniki per scenariusz

Podsumowanie: **14 scenariuszy — 7 PASS, 2 FAIL, 5 UWAGA.**

| # | Scenariusz | Status | Najwazniejszy dowod |
|---|---|---|---|
| A | S1 lista arkuszy (auto/pl, w2/w1) | UWAGA (B1) | rc=1, `Error:` wymienia 1 z 2 niemieckich arkuszy; w2: 6/6 arkuszy z danymi na dysku; w1: 0 plikow |
| B | S1 wycinek `--target-crs EPSG:2180` (auto/pl) | PASS | rc=0, `missing_sheets` = 3 arkusze niemieckie, nodata tylko za Odra, 1:1, auto == pl bajt w bajt |
| C | S2 lista (auto/pl) | UWAGA (B1) | rc=1, 4/4 arkusze z danymi na dysku |
| D | S2 wycinek 2180 (auto/pl) + ponowienie po bledzie chwilowym | PASS | 1. proba: ConnectionReset -> `Error: 1 z 8 arkuszy nie pobrano (blad pobrania, nie brak danych)` (R5 dziala); ponowienie: rc=0, 6 arkuszy z dysku |
| E | S3 lista, auto | **FAIL (B2)** | rc=0 + `Warning: nie pobrano danych z PL`, choc 4 arkusze PL sa na dysku |
| F | S3 wycinek auto 2180 (PL + CZ) — tresc | PASS | 2 pliki o tej samej nazwie w `pl_1992_5m_evrf2007/bbox/` i `cz_dmr4g_bpv/bbox/`, wspolny `parent_request`, PL 1:1, 5 `missing_sheets` (DE+CZ) |
| G | S3 styk danych PL/CZ (wejscie R6) | PASS (pomiar) | pas zakladki 1,0 km², mediana 350 m N-S; roznica wysokosci mediana 0,17 m po EVRF2007 |
| H | S3c: DE+PL w prostokacie CZ | UWAGA | plik CZ 100 % nodata (1,1 MB) + sidecar, rc=0, zero komunikatu |
| I | S4 auto (lista i wycinek) — czesc na zachod od 14,07°E | UWAGA (B4) | 2,69 km zadania pominiete bez komunikatu; nazwa pliku i `request.bbox` = bbox przyciety |
| J | S4 `--country pl` wycinek | PASS [retry-harness] | pelny zasieg 8,865 km, 10 `missing_sheets`, czesc wspolna z auto: 220 932 px identycznych |
| K | S5 auto | PASS | `Error: obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)`, rc=1, zero sieci |
| L | S5 `--country pl` wycinek | PASS [retry-harness] | `Error: GUGiK nie ma danych dla zadnego z 2 arkuszy obszaru — wycinek nie powstal`, rc=1 |
| M | Odpornosc na chwilowe bledy GUGiK (przekrojowo) | **FAIL (B3)** | trojstyk: 3 z 4 prob bez wycinka PL; Osinow `--country pl`: 0 z 2 prob; z retry-harness od razu |
| N | Wybor kampanii przy bledzie chwilowym (przekrojowo) | UWAGA (B5) | 3 arkusze pobrane z warstwy 2023, choc warstwa 2025 je ma; wartosci identyczne |

Tabela przebiegow (`werr` to ostrzezenia `WMS query failed`/`Failed to fetch WMS GetCapabilities`;
`retr` to ponowienia harnessu; `ok/sk/x` to znaczniki paska postepu: pobrany/pominiety/bez pliku):

```
przebieg                              rc  czas   found ok sk  x werr retr  Error
s1a_slubice_auto_list                  1   7.4 s     8  -  -  -    0    0  No NMT 5m data available for N-33-126-C-c-3-3
s1a2_slubice_auto_list_w1 (--workers 1)1   1.8 s     8  -  -  -    0    0  No NMT 5m data available for N-33-126-C-c-3-1
s1b_slubice_pl_list                    1   4.7 s     8  -  -  -    0    0  No NMT 5m data available for N-33-126-C-c-3-1
s1c_slubice_auto_2180                  0   7.0 s    12  9  0  3    0    0  (Warning: 3 arkusze)
s1d_slubice_pl_2180                    0   7.0 s    12  9  0  3    0    0  (Warning: 3 arkusze)
s2a_zgorzelec_auto_list                1   5.2 s     6  -  -  -    0    0  No NMT 5m data available for M-33-30-D-b-2-1
s2b_zgorzelec_pl_list                  1   6.1 s     6  -  -  -    0    0  (jw.)
s2c_zgorzelec_auto_2180                1   7.7 s     8  6  0  2    1    0  1 z 8 arkuszy nie pobrano (blad pobrania...): M-33-30-D-b-2-3
s2c2_zgorzelec_auto_2180_retry         0   1.4 s     8  0  6  2    0    0  (Warning: 2 arkusze)
s2d_zgorzelec_pl_2180                  0   9.4 s     8  6  0  2    0    0  (Warning: 2 arkusze)
s3a_trojstyk_auto_list                 0  18.9 s     6  -  -  -    2    0  No NMT 5m ... M-33-42-B-c-1-4 + Warning: nie pobrano danych z PL
s3b_trojstyk_auto_2180                 0  19.5 s     9  4  0  5    3    0  1 z 9 arkuszy nie pobrano ...: M-33-42-B-c-1-4 + Warning (PL)
s3b2_..._retry                         0  19.3 s     9  0  4  5    2    0  (jw., M-33-42-B-c-1-4)
s3b3_..._retry2                        0  20.5 s     9  0  4  5    5    0  (jw., M-33-42-B-c-4-4: all 4 layer queries failed)
s3b4_..._RETRYHARNESS                  0   4.4 s     9  0  4  5    0    0  (Warning: 5 arkuszy) — 0 ponowien = jak czyste CLI
s3c_sieniawka_auto_2180                0   4.8 s     4  3  0  1    3    0  (Warning: 1 arkusz)
s3d_trojstyk_auto_2180_evrf            0   5.6 s     -  -  -  -    0    0  (CZ EVRF2007; PL Skipped)
s4a_osinow_auto_list                   1   2.6 s     4  -  -  -    0    0  No NMT 5m data available for N-33-113-A-c-4-3
s4c_osinow_auto_2180                   1   4.9 s     8  6  0  2    4    0  1 z 8 arkuszy nie pobrano ...: N-33-113-A-c-4-3
s4c2_osinow_auto_2180_retry            0   1.7 s     8  0  6  2    1    0  (Warning: 2 arkusze)
s4d_osinow_pl_2180                     1  11.1 s    18  8  0 10    7    0  1 z 18 arkuszy nie pobrano ...: N-33-113-A-c-4-2
s4d2_osinow_pl_2180_retry              1  22.6 s    18  0  8 10    8    0  5 z 18 arkuszy nie pobrano ...
s4d3_osinow_pl_2180_RETRYHARNESS       0   6.6 s    18  0  8 10    0    7  (Warning: 10 arkuszy)
s5a_berlin_auto                        1   0.4 s     -  -  -  -    0    0  obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)
s5b_berlin_pl_2180                     1   1.5 s     2  0  0  2    3    0  1 z 2 arkuszy nie pobrano ...: N-33-123-B-d-3-3
s5b2_berlin_pl_2180_RETRYHARNESS       1  33.9 s     2  0  0  2    0    8  GUGiK nie ma danych dla zadnego z 2 arkuszy obszaru — wycinek nie powstal
```

W trybie listy pasek postepu nie jest rysowany (stad `-`); liczba plikow: patrz A/C/E.

### A. S1 lista arkuszy — UWAGA (B1)
- `kartograf download --bbox 14.52,52.335,14.60,52.36 --bbox-crs EPSG:4326 --resolution 5m --workers 2 -o ./data`
  (auto i `--country pl` daja to samo): rc=1. Na stdout jest `Found 8 sheets...`, ale brak
  podsumowania `Downloaded N files`. Na stderr jest pusta linia i
  `Error: No NMT 5m data available for N-33-126-C-c-3-3 (vertical_crs=EVRF2007). This area may not have 5m coverage in GUGiK. Check https://mapy.geoportal.gov.pl for data availability.`
- Na dysku leza **6/6 arkuszy z danymi** z sidecarami (`parent_request.countries=["PL"]`).
  Drugi arkusz bez danych (`c-3-1`, Niemcy) nie jest nigdzie wymieniony. Ktory arkusz trafia do
  `Error:`, zalezy od kolejnosci konczenia watkow: auto podal `c-3-3`, pl podal `c-3-1`.
- `--workers 1`: rc=1 i **0 plikow**. Petla staje na pierwszym arkuszu listy (`c-3-1`, Niemcy).
- Nic nie poszlo do CUZK (hosts: tylko `mapy.geoportal.gov.pl`, `opendata.geoportal.gov.pl`).
- Dla uzytkownika jest to niezrozumiale: komunikat o "braku pokrycia 5m" nie mowi, ze arkusz
  lezy w Niemczech; nie widac tez, ze reszta sie pobrala.

### B. S1 wycinek EPSG:2180 — PASS
- auto: rc=0, 7,0 s, 12 arkuszy (9 pobranych). Na stderr: 3 linie loggera `No data for <godlo>: ...`
  i `Warning: GUGiK nie ma danych dla 3 arkuszy wycinka (N-33-126-C-c-3-1, N-33-126-C-c-3-3, N-33-138-A-a-1-1) — w tych miejscach wycinek ma nodata (lista w sidecarze: extra.missing_sheets)`.
- Plik `data/nmt/pl_1992_5m_evrf2007/bbox/194916.9831_505674.1335_200531.3726_508786.5679.tif`:
  EPSG:2180, 1124x623 px, 5 m, faza siatki 2,5/2,5 (siatka arkuszy). Rozszerzenie wzgledem
  zadania wynosi W/S/E/N 4,48/1,63/1,13/0,93 m, czyli < 1 px.
- Sidecar ma `transform: null`, `vertical_crs EPSG:9651`, `missing_sheets` z tymi 3 arkuszami
  i `parent_request {bbox [14.52,52.335,14.6,52.36], EPSG:4326, [PL]}`.
- **nodata 40,90 %, w calosci na zachod od krawedzi danych.** W kazdym wierszu jest 0 pikseli
  nodata na wschod od pierwszego waznego piksela. Krawedz danych lezy na 14,548-14,559°E,
  czyli na Odrze.
- Arkusze przygraniczne GUGiK wydaje z nodata po stronie niemieckiej: `c-3-2` ma 59,7 % nodata,
  `c-3-4` 75,4 %, `N-33-138-A-a-1-2` 95,7 %. Arkusze wewnetrzne maja ok. 11 % nodata, bo ramka
  arkusza lezy w obwiedni EPSG:2180.
- 1:1 z arkuszami: 413 872 px, 0 roznic, 0 nodata tam, gdzie arkusz ma dane, 0 danych bez arkusza.
- `--country pl`: TIF identyczny bajt w bajt (`cmp`), sidecar identyczny poza `downloaded_at`.
  Do CUZK nic nie poszlo.
- Skorowidz (proba reczna) zna arkusz przygraniczny takze w punkcie srodka lezacym juz w
  Niemczech. Przyklad: srodek `N-33-113-C-a-2-2` lezy ~820 m na zachod od pasa danych, a warstwa
  2025 i tak zwraca rekord. Poligony skorowidza to wiec pelne ramki arkuszy — zapytanie o srodek
  arkusza jest na granicy bezpieczne.

### C. S2 lista — UWAGA (B1)
To samo co A: rc=1, `Error:` o `M-33-30-D-b-2-1`, drugi niemiecki arkusz (`b-2-3`) nie jest
wymieniony, 4/4 arkusze z danymi leza na dysku.

### D. S2 wycinek EPSG:2180 — PASS
- 1. proba auto: GUGiK zerwal polaczenie (`Connection reset by peer`) na 1 z 4 warstw dla
  `M-33-30-D-b-2-3`. Wynik: `Failed to download ... brak pokrycia niepewny` i
  `Error: 1 z 8 arkuszy nie pobrano (blad pobrania, nie brak danych): M-33-30-D-b-2-3 — wycinek nie powstal; ponow pobranie`, rc=1.
  To poprawne R5 na realnym bledzie chwilowym: brak falszywej dziury nodata.
- Ponowienie z tym samym `-o`: rc=0, 1,4 s. 6 arkuszy wzieto z dysku (`○`), tylko 2 arkusze
  bez danych odpytano ponownie (10 GET).
- Raster 1003x498 px ma nodata 46,65 %. Flood-fill od zachodniej krawedzi obejmuje 100 % nodata,
  wiec nie ma zadnej dziury po stronie PL. Krawedz danych lezy na 14,988-14,998°E (Nysa).
  1:1: 266 460 px, 0 roznic.
- `--country pl` daje wynik identyczny bajt w bajt.

### E. S3 lista, auto — FAIL (B2)
- `kartograf download --bbox 14.79,50.855,14.86,50.89 --bbox-crs EPSG:4326 --resolution 5m --workers 2 -o ./data`: rc=0.
  - CZ: `nmt/cz_dmr4g_bpv/bbox/-705439.9183_-962555.2831_-700045.0331_-958049.9127.tif` (EPSG:5514,
    1079x901 px, nodata 72,43 %). Dane sa tylko na SE, czyli w Czechach: 14,809-14,867°E,
    50,851-50,874°N. Czesc DE (Zittau) i PL jest nodata.
  - PL: pobrano 4 arkusze z sidecarami (`countries ["CZ","PL"]`).
  - stderr: `Error: No NMT 5m data available for M-33-42-B-c-1-4 ...`, a potem
    `Warning: nie pobrano danych z PL dla tego obszaru (brak pokrycia albo awaria zrodla — patrz Error wyzej) — pobrano CZ (prostokatne obwiednie krajow, ADR-023 pkt 4-5)`.
- Komunikat jest **sprzeczny z faktami**: dane PL sa na dysku. Uzytkownik (albo Hydrograf czytajacy
  stderr) uzna, ze po stronie PL nic nie ma.

### F. S3 wycinek auto 2180 — tresc PASS (niezawodnosc: M)
- Trzy pierwsze proby: CZ OK. PL za kazdym razem padlo na `RemoteDisconnected` (B3), co dalo
  rc=0 + `Warning: nie pobrano danych z PL` (zgodnie z ADR-023). Za 3. razem blad brzmial
  `all 4 layer queries failed`.
- 4. proba [retry-harness, **0 ponowien** — przebieg jak czyste CLI]: rc=0, 4,4 s. Powstal
  `nmt/pl_1992_5m_evrf2007/bbox/203809.1627_340177.3007_208950.5503_344344.7449.tif`: 1029x835 px,
  faza 2,5, nodata 62,60 %.
- `missing_sheets` obejmuje 5 arkuszy: `c-1-4` (DE), `c-3-2` (DE/CZ), `c-3-4`, `c-4-3`, `c-4-4` (CZ).
  1:1: 321 345 px, 0 roznic. Dane sa tylko na NE (Porajow).
- Plik CZ ma **te sama nazwe** w `nmt/cz_dmr4g_bpv/bbox/`: 1028x833 px, nodata 72,89 %.
  Sidecar ma `transform.horizontal = "pinned: ... Poland CS92 ... (0.5 m)"`. `exportImage` idzie
  natywnie z `bboxSR=5514&imageSR=5514` (ADR-024 OK).
- Wspolny `parent_request {bbox [14.79,50.855,14.86,50.89], EPSG:4326, [CZ, PL]}`.

### G. Styk danych PL/CZ na trojstyku (wejscie R6) — PASS (pomiar)
- Wspolna siatka 5 m (faza 2,5; maska CZ probkowana najblizszym sasiadem). Wynik: tylko PL
  281 182 px, tylko CZ 191 945 px, **oba 40 163 px = 1,004 km²**, zadne 344 896 px (zachod,
  Niemcy/Zittau: nie ma danych z zadnego zrodla).
- Zakladka to pas wzdluz granicy PL-CZ na wschod od trojstyku, szeroki w kierunku N-S: mediana
  350 m, p90 415 m, max 450 m.
- Roznica wysokosci w zakladce:
  - PL(EVRF2007) - CZ(Bpv): mediana 0,308 m.
  - Po `--vertical-crs EVRF2007` (s3d, CZ w `nmt/cz_dmr4g_evrf2007/bbox/`, `transform.vertical`
    przypiety, 0,1 m): mediana 0,165 m, MAD 0,243, p5/p95 -1,17/+1,04 m.
- Wniosek dla R6: na tym odcinku zrodla **zachodza na siebie**, a nie zostawiaja szczeliny.
  Scalanie musi rozstrzygac pierwszenstwo w zakladce. Ktore zrodlo wychodzi poza granice, bez
  wielokata granicy nie da sie rozstrzygnac (zakres L4).
- Mapa ASCII: `seam_map.py`, dane w `seam_trojstyk_*.npz`.

### H. S3c: DE+PL wewnatrz prostokata CZ — UWAGA
- `kartograf download --bbox 14.86,50.92,14.90,50.94 --bbox-crs EPSG:4326 --resolution 5m --target-crs EPSG:2180 --workers 2 -o ./data`: rc=0.
- CZ: `nmt/cz_dmr4g_bpv/bbox/209137.8022_347242.2978_212070.7426_349621.5679.tif`, 587x476 px,
  **100,00 % nodata**, 1,1 MB, z sidecarem. Nie ma zadnego `Info:`/`Warning:`.
- PL: wycinek z 1 arkuszem `missing_sheets` (`M-33-42-B-a-4-2`, Niemcy); nodata 39,30 %
  (zachod za Nysa); 1:1: 0 roznic.
- Dokumentacja opisuje "raster same-nodata" tylko dla bboxow w calosci w Polsce. Saksonia
  i pas Bogatyni nie sa wymienione.

### I. S4 auto — czesc na zachod od 14,07°E — UWAGA (B4)
- Lista (s4a): `Found 4 sheets` (`A-c-4-3, A-c-4-4, A-d-3-3, A-d-3-4`, bez `A-c-3-3/-3-4` na
  zachod od 14,0625°E). Wynik rc=1 przez niemiecki `A-c-4-3` (B1).
- Wycinek (s4c2, po jednej probie z bledem chwilowym): rc=0. Plik
  `nmt/pl_1992_5m_evrf2007/bbox/168096.3744_563137.9548_174263.978_565216.7676.tif` (1235x416 px).
  Zachodnia krawedz lezy na **14,068-14,070°E**, a zadanie siegalo 14,03°E. **2,69 km zadania
  pominiete bez komunikatu.**
- Nazwa pliku i `request.bbox` niosa bbox przyciety. Oryginal jest tylko w
  `parent_request.bbox = [14.03, 52.835, 14.16, 52.85]`.
- `missing_sheets` = 2, nodata 57,0 %, dane od ~14,117°E (Osinow Dolny). 1:1: 0 roznic.
- Offline (`prepare_pl_cutout`, zero sieci) potwierdza przyczyne: `_country_bbox(auto=True)`
  zwraca `BBox(14.07, 52.835, 14.16, 52.85)`.

### J. S4 `--country pl` — PASS [retry-harness]
- Czyste CLI: 2 proby, rc=1 za kazdym razem. Pierwsza: `1 z 18` (`A-c-4-2`). Druga:
  `5 z 18 arkuszy nie pobrano (blad pobrania, nie brak danych)`.
- [retry-harness] (7 ponowien polaczen): rc=0. Plik
  `165405.2716_563137.9548_174263.978_565402.4785.tif` (1773x453 px, **8,865 km** wobec 6,175 km
  w auto).
- `missing_sheets` = 10 arkuszy niemieckich; `Warning:` wymienia dokladnie 10, bez `...`.
  nodata 70,46 %; 1:1: 0 roznic.
- W czesci wspolnej z wycinkiem auto: 220 932 px waznych, wszystkie identyczne.

### K. S5 auto — PASS
rc=1 po 0,4 s: `Error: obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)`. Zero
zapytan, zero plikow i katalogow.

### L. S5 `--country pl` wycinek — PASS [retry-harness]
- Czyste CLI: rc=1 z bledem chwilowym (`1 z 2 arkuszy nie pobrano ...`).
- [retry-harness] (8 ponowien, 33,9 s): rc=1 z `Error: GUGiK nie ma danych dla zadnego z 2 arkuszy obszaru — wycinek nie powstal`.
  Komunikat jest jasny.
- Zostaja 2 puste katalogi arkuszy (B6).

### M. Odpornosc na chwilowe bledy GUGiK — FAIL (B3)
- 09:29-09:32: 0 bledow. Od ~09:32 GUGiK zrywal polaczenia (`RemoteDisconnected`,
  `ConnectionResetError`). W przebiegach CLI bylo to 39 z ~294 zapytan WMS (~13 %), w probach
  recznych ~1/3, raz 8 porazek pod rzad.
- Arkusz bez danych wymaga 4 udanych zapytan (wszystkie warstwy). Przy 13 % na zerwanie: 5 takich
  arkuszy daje wycinek w ~6 % prob, 10 arkuszy w ~0,4 %.
- Zmierzone: trojstyk 1 wycinek PL na 4 proby; Osinow `--country pl` 0 na 2 proby; Zgorzelec,
  Osinow auto i Berlin padly przy 1. probie.
- Harness z samymi ponowieniami polaczen (bez zmiany logiki) przechodzi od razu (7 i 8 ponowien).
- Zastrzezenie: rownolegle z tego samego IP pracowalo ~9 agentow, co moglo nasilic zjawisko.
  Pojedynczy uzytkownik z duzym bboxem (setki arkuszy x 4 warstwy) trafi na nie tak samo.
- Pod `--country auto` z sukcesem CZ taki blad daje **rc=0** (ADR-023). Skrypt nie odrozni wiec
  "sa oba pliki" od "jest tylko CZ".

### N. Wybor kampanii przy bledzie chwilowym — UWAGA (B5)
- s4d (1. proba `--country pl`): `N-33-113-C-a-2-2`, `C-b-1-2` i `A-d-3-1` pobrano z kampanii
  78939 (warstwa `SkorowidzeNMT2023`). s4c pobral `C-a-2-2`/`C-b-1-2` jako 83841 (2025), a proba
  reczna potwierdza rekord 2025 dla `C-a-2-2` i `A-d-3-1`. Przyczyna: `RemoteDisconnected` na
  warstwie 2025, a potem "URL w odpowiedzi zawsze wygrywa" w starszej warstwie.
- Pliki zostaja w `data/` (`skip_existing`), wiec wycinek po ponowieniu uzyl wersji 2023.
  Sidecar arkusza nie zapisuje URL ani kampanii (`request = {godlo}`), wiec nie da sie tego wykryc.
- W tym przypadku waznosci i wartosci sa identyczne: 3 arkusze porownane (m.in.
  `A-d-3-1`: 90 095 px, 0 roznic), rozne sa tylko obwiednie ASC (`C-a-2-2`: 62x468 vs 44x60 px).
  Szkoda jest potencjalna, tam gdzie nowsza kampania niesie inne wysokosci.

## 3. Bledy

**B1 — tryb listy arkuszy (bez `--target-crs`) konczy KAZDY bbox przecinajacy granice PL-DE kodem 1.**
- Repro: `kartograf download --bbox 14.52,52.335,14.60,52.36 --bbox-crs EPSG:4326 --resolution 5m --workers 2`.
  Wynik: rc=1, `Error:` o jednym niemieckim arkuszu, 6 arkuszy PL na dysku, brak podsumowania.
  Z `--workers 1`: rc=1 i 0 plikow.
- Oczekiwane (propozycja, decyzja uzytkownika): spojnosc z R5. `NoCoverageError` = `Warning:`
  z pelna lista i kod 0, o ile cos pobrano, plus podsumowanie; blad transportu = kod 1.
  Minimum: wymienic wszystkie arkusze i dopisac "arkusz poza zasiegiem danych GUGiK (np. za granica)".
- Hipoteza:
  - `kartograf/cli/download_cmd.py:893-905` (`_download_godlo_list`, galaz rownolegla): `raise`
    na pierwszym `DownloadError`, a `NoCoverageError` jest jego podklasa. Wyjscie z `with` czeka
    na reszte futures, wiec pliki powstaja, ale ich sciezki i bledy przepadaja.
  - Galaz sekwencyjna `:855-859` (`manager.download_sheet` dla 1:10000 rzuca od razu).
  - `:1145-1147` (`_download_pl_bbox`) zamienia to na rc=1.
- Zgodne z ogolnym zdaniem ARCHITECTURE 4.2 ("Nieudany arkusz konczy polska czesc zadania kodem 1"),
  ale na pograniczu tryb listy jest przez to praktycznie bezuzyteczny.

**B2 — mylacy `Warning:` pod `--country auto`, gdy PL zwraca rc!=0 po czesciowym sukcesie.**
- Repro: `kartograf download --bbox 14.79,50.855,14.86,50.89 --bbox-crs EPSG:4326 --resolution 5m --workers 2`.
  Wynik: rc=0 i `Warning: nie pobrano danych z PL ...`, choc 4 arkusze PL z sidecarami sa na dysku.
  Oczekiwane: komunikat zgodny z faktami, np. "PL: pobrano 4 z 6 arkuszy; 2 bez danych GUGiK".
- Hipoteza: `download_cmd.py:533-545` buduje komunikat wylacznie z kodu wyjscia kraju, a
  `_download_pl_bbox` zwraca 1 takze przy czesciowym sukcesie (B1). Po naprawie B1 znika
  wiekszosc przypadkow.

**B3 — zapytania GetFeatureInfo skorowidza nie maja ponowien; jedno zerwane polaczenie przewraca wycinek.**
- Repro: dowolny wycinek przygraniczny przy niestabilnym GUGiK (s3b/s3b2/s3b3, s4c, s4d, s4d2, s5b).
  Wynik: `Error: N z M arkuszy nie pobrano (blad pobrania, nie brak danych) ... ponow pobranie`.
- Oczekiwane: ponowienie bledow polaczenia na poziomie zapytania (jak `download_to` dla ASC),
  zanim zapytanie zostanie zaliczone do "warstwa nie odpowiedziala".
- Hipoteza:
  - `kartograf/providers/pl/gugik.py:572` — `session.get` bez ponowien. Domyslna `requests.Session`
    nie ma `HTTPAdapter(max_retries=...)`.
  - `:618-622` — `except requests.RequestException` daje `transport_errors += 1; continue`.
  - `:624-641` zamienia to w `DownloadError` ("brak pokrycia niepewny" / "unavailable").
- Harness `kg_retry.py` (urllib3 `Retry(connect/read=6, backoff 0,5, tylko GET)`) usuwa problem
  bez zmiany semantyki R5.

**B4 — `--country auto` przycina zadanie do prostokatow krajow bez komunikatu.**
- Repro: s4c2 wobec s4d3 (wyzej). Czesc zadania poza wszystkimi prostokatami (zachod od 14,07°E)
  znika z wycinka i z listy arkuszy. Nazwa pliku i `request.bbox` sa przyciete.
- Oczekiwane: co najmniej `Info: --country auto: czesc obszaru poza zasiegiem PL/CZ (na zachod od 14,07°E) pominieta; uzyj --country pl, aby dostac caly bbox (nodata za granica)`.
- Hipoteza: `download_cmd.py:282-342` (`_country_bbox`, przyciecie `:316-327`), wolane w
  `_dispatch_area` `:510-516` bez komunikatu. Przyciecie jest zamierzone (docstring), cichosc nie.
- Nie testowane: tor `--geometry` pod auto (dostaje ten sam `part`) i krawedzie 24,20°E / 54,90°N
  (zakres L3/L6).

**B5 (latentny) — starsza kampania po bledzie chwilowym nowszej warstwy, utrwalona w cache.**
- Repro: s4d (patrz N).
- Oczekiwane: blad transportu na warstwie nowszej niz ta, w ktorej znaleziono URL, nie powinien
  dac cichego wyboru starszych danych (np. traktowac go jak "brak pokrycia niepewny" albo ponawiac).
  Warto tez zapisac URL arkusza w sidecarze.
- Hipoteza: `gugik.py:577-599` (pierwszy znaleziony URL wygrywa) razem z `:618-622`.

**B6 (kosmetyczny) — puste katalogi po arkuszach bez danych.**
- `FileStorage.get_path` tworzy katalog przed pobraniem (`kartograf/download/storage.py:336`),
  a `NoCoverageError` zostawia pusty lancuch katalogow. Zmierzone: s1c 3, s3b 5, s4d 10 pustych.
- Dotyczy listy i wycinka. `prune_empty_dirs` sprzata tylko `<segment>/bbox/`.

**H1 (hipoteza, poza zakresem PL-DE) — regex URL skorowidza jest wrazliwy na wielkosc liter.**
- `gugik.py:578`: `url:"(https://opendata[^"]+\.asc)"`. Warstwa `SkorowidzeNMT2022iStarsze` zwraca
  czesc URL z `.ASC`, np. `76969_1298029_N-33-126-C-c-3-2.ASC` i `76969_1297650_N-33-113-C-b-1-2.ASC`
  (body w `wms_probe/`). Inne rekordy tej warstwy maja `.asc` (`73675_..._M-33-31-C-a-1-1.asc`).
- Arkusz, ktorego JEDYNY rekord ma `.ASC`, zostalby uznany za brak danych (nodata w wycinku).
- W moich obszarach kazdy taki arkusz mial tez nowszy rekord `.asc`, wiec wplywu nie
  zaobserwowalem. Do sprawdzenia przez L1/L3/L6.

**UX (nie blad):**
- Kazdy arkusz bez danych daje na stderr goly wpis loggera
  `No data for <godlo>: No NMT 5m data available ... Check https://mapy.geoportal.gov.pl ...`.
  Przy 10 arkuszach to 10 dlugich linii przed wlasciwym `Warning:`; tekst nie sugeruje "za granica".
- Postep dla arkuszy pominietych (`○`) nie konczy linii.

## 4. Zachowanie do udokumentowania

Nic z ponizszego nie jest dzis opisane. Grep `niem|germany|przycin|zadnego znanego kraju` po
CLAUDE.md, SCOPE, ARCHITECTURE i README nie daje trafien dotyczacych pogranicza PL-DE.
Proponowane teksty:

**Z1 — CLAUDE.md "Ograniczenia", nowy punkt (po punkcie `--target-crs` dla PL):**
> - **Pogranicze z krajem bez obslugi (DE; analogicznie SK/UA/BY/LT/RU):** arkuszy PL-1992 lezacych
>   w calosci za granica GUGiK nie ma w skorowidzu (pusta odpowiedz GetFeatureInfo: HTTP 200,
>   text/html, bez rekordu) -> `NoCoverageError`. Arkusz przygraniczny GUGiK wydaje z nodata za
>   linia granicy (dane urywaja sie na nurcie Odry/Nysy; skorowidz znajduje go takze, gdy srodek
>   arkusza lezy juz za granica).
>   - Z `--target-crs` wynik to wycinek z nodata po stronie zagranicznej, `Warning:` +
>     `extra.missing_sheets`, kod 0 (R5).
>   - BEZ `--target-crs` (lista arkuszy) taki arkusz to zwykla porazka: kod 1 i
>     `Error: No NMT <res> data available for <godlo>` o JEDNYM arkuszu, bez podsumowania
>     `Downloaded N files`. Przy `--workers >= 2` arkusze z danymi i tak laduja na dysku (z sidecarami).
>     Przy `--workers 1` petla staje na pierwszym takim arkuszu (Slubice: pierwszy arkusz listy
>     lezy w Niemczech -> zero plikow).
>   - Na pograniczu uzywaj `--target-crs EPSG:2180` (wartosci 1:1 z arkuszy).

**Z2 — CLAUDE.md, punkt `--country` domyslnie = `auto`, dopisac (4):**
> (4) czesc zadania dla kazdego kraju jest PRZYCINANA do jego prostokata `extent_wgs84`. Czesc
> poza WSZYSTKIMI prostokatami (np. pas na zachod od 14,07°E przy Osinowie Dolnym albo na Uznamie)
> jest pomijana BEZ komunikatu: wycinek konczy sie na ~14,07°E, a jego nazwa i `request.bbox` niosa
> bbox przyciety (oryginal tylko w `extra.parent_request.bbox`). Jawne `--country pl` nie przycina
> (caly bbox, nodata za granica). Bbox w calosci poza prostokatami konczy sie
> `Error: obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)`, kod 1, bez zapytan sieciowych.

**Z3 — CLAUDE.md (punkt CZ o prostokacie) i SCOPE 3.2, dopisac:**
> Prostokat CZ obejmuje tez Saksonie ponizej 51,06°N (Zittau, Hirschfelde) i pas Bogatyni.
> `--country auto` pyta tam CUZK i zapisuje raster CZ w 100 % nodata (np. bbox 14,86-14,90°E /
> 50,92-50,94°N: 587 x 476 px, 1,1 MB) bez `Info:`/`Warning:`.

**Z4 — ARCHITECTURE 4.2, dopisac:**
> Arkusz bez danych u zrodla (`NoCoverageError`: morze, arkusz za granica) jest w tym trybie
> zwykla porazka arkusza. Kod 1 z `Error:` o PIERWSZYM takim arkuszu wg kolejnosci konczenia
> watkow (`_download_godlo_list` rzuca pierwszy `DownloadError`). Przy `max_workers > 1` reszta
> arkuszy i tak sie pobiera (pula czeka przy wyjsciu), przy 1 petla staje. R5 (nodata +
> `missing_sheets`) obowiazuje wylacznie wycinek `--target-crs` (4.3). Pod `--country auto` z
> sukcesem drugiego kraju taki czesciowy sukces PL raportowany jest jako
> "nie pobrano danych z PL" (znany blad B2 z testow live 2026-09-29).

**Z5 — ARCHITECTURE 4.3 krok 4 i CLAUDE.md (R5):**
- Zmienic "(morze, strona czeska bboxa przygranicznego, dziury pokrycia 1 m)" na
  "(morze, ZAGRANICZNA strona bboxa przygranicznego — CZ, DE i inne, dziury pokrycia 1 m)".
- Dopisac dowod live: 2026-09-29, 5 m: Slubice 3, Zgorzelec 2, trojstyk 5, Osinow 10 arkuszy
  w `missing_sheets`; nodata wylacznie po stronie zagranicznej, 0 px nodata po stronie PL,
  wartosci 1:1.
- Dopisac ograniczenie (do czasu naprawy B3): zapytania skorowidza nie maja ponowien. Pojedyncze
  zerwanie polaczenia w trakcie odpytywania arkusza bez danych konczy wycinek
  `DownloadError` ("brak pokrycia niepewny"). Rozwiazanie: ponowic polecenie — arkusze z dysku sa
  uzywane ponownie, a odpytywane sa tylko brakujace.

**Z6 — ARCHITECTURE 4.6:**
- Dopisac przyciecie do prostokatow (jak Z2) i blad "obszar nie przecina zasiegu".
- Dopisac, ze kod 0 pod auto nie gwarantuje pliku z kazdego kraju: blad chwilowy GUGiK (B3)
  daje rc=0 + `Warning:` przy sukcesie CZ. Skrypt powinien sprawdzac pliki albo stderr.

**Z7 — ARCHITECTURE 4.3 krok 1:**
> Bbox w EPSG:4326 staje sie wycinkiem obejmujacym jego OBWIEDNIE w EPSG:2180. Przy 14°E zbieznosc
> poludnikow ~ -4° wzgledem poludnika osiowego 19°E powieksza waski pas. Przyklad: Osinow
> 8,9 x 1,7 km daje 18 arkuszy w wycinku wobec 6 w trybie listy; Slubice 12 wobec 8. Na pograniczu
> oznacza to wiecej arkuszy w `missing_sheets`.

**Z8 — README (komentarz przy przykladzie pogranicza):**
> Na pograniczu z Niemcami (dane DE nieobslugiwane) uzyj `--target-crs EPSG:2180`: dostaniesz
> wycinek z nodata za granica. Bez tej flagi arkusz lezacy w Niemczech konczy polecenie kodem 1.

**Z9 — PROGRESS pkt 12 (h) / SCOPE 3.1 (R6), wejscie z pomiaru G:**
> Trojstyk: GUGiK i CUZK przycinaja dane na granicach z Niemcami (Nysa: brak danych po stronie DE
> z obu zrodel). Na granicy PL-CZ przy trojstyku zrodla ZACHODZA pasem ~350 m (1,0 km² w bboxie
> 5 x 4 km). Roznica PL(EVRF2007) - CZ(EVRF2007) ma mediane 0,17 m (MAD 0,24).

## 5. Odpowiedzi na pozycje checklisty (PROGRESS "Nastepne kroki" pkt 12)

- **(e) pogranicze `--country auto --target-crs EPSG:2180` na realnych danych obu krajow:**
  WYKONANE na trojstyku (F). Powstaja dwa pliki o tej samej nazwie w segmentach
  `pl_1992_5m_evrf2007/bbox/` i `cz_dmr4g_bpv/bbox/`, ze wspolnym `parent_request`. PL jest 1:1
  z arkuszami, CZ przypiety warp z natywnego 5514. Zastrzezenie: 3 z 4 prob skonczyly sie bez
  pliku PL przy rc=0 (B3 + ADR-023).
- **(h) jak GUGiK i CUZK przycinaja dane na granicy / styk:**
  - GUGiK przycina na linii granicy PL-DE (Odra, Nysa); arkusze przygraniczne maja nodata po
    stronie DE, a ASC bywaja przyciete do zasiegu danych (`C-a-2-2`: 62 x 468 px).
  - CUZK zwraca nodata poza CZ (strona DE i PL).
  - Na odcinku PL-CZ przy trojstyku jest zakladka ~350 m (G). Po stronie DE jest dziura obu zrodel
    (poza zakresem, zgodnie z oczekiwaniem).
- **(j) body pustej odpowiedzi GetFeatureInfo:** HTTP 200, `Content-Type: text/html`, 7721 B,
  szablon HTML bez `skor_NMT_wg_akt.push`, bez `ServiceException`/`ExceptionReport`.
  md5 `e41703179e3efd50082920f6053dc771` jest identyczne dla 4 warstw 5 m, po stronie niemieckiej
  (Slubice, Zgorzelec) i czeskiej (trojstyk `c-4-4`). Straz I-2 nie myli wiec pustej odpowiedzi
  z raportem wyjatku i R5 dziala. Odpowiedz z rekordem ma 8889/8907 B. Pliki: `wms_probe/*.html`,
  `wms_probe/summary.jsonl`.
- **(g) fallback "URL innego arkusza":** 0 wystapien w 26 przebiegach (5 m, pogranicze).
- **(c) CZ bbox -> `nmt/cz_dmr4g_<vcrs>/bbox/`:** potwierdzone dla `bpv` i `evrf2007`.
- (a), (b), (d), (f), (i): poza zakresem L5.

## 6. Surowe artefakty

Katalog: `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L5-pogranicze-de/`
- `runs/<przebieg>/{cmd,stdout,stderr,rc,time,hosts.log}` oraz `runs/<przebieg>/data/` (dane
  i sidecary; ponowienia s2c2/s3b2-4/s4c2/s4d2-3/s5b2 pisza do katalogu `data/` pierwszej proby).
- Skrypty:
  - `kg.py` — lustro CLI + log hostow.
  - `kg_retry.py` — [retry-harness].
  - `run.sh`, `run_any.sh`.
  - `plan_sheets.py` — offline, selekcja arkuszy.
  - `analyze_cutout.py` — geometria, nodata i 1:1 wycinka 2180.
  - `raster_map.py` — mapa waznosci.
  - `seam_map.py` — styk PL/CZ.
  - `wms_probe.py`, `probe_exact.py` — reczne GetFeatureInfo.
- `wms_probe/` — surowe body GetFeatureInfo (puste DE/CZ, z rekordem, z `.ASC`) i `summary.jsonl`.
- `campaign_check/` — arkusz `N-33-113-A-d-3-1` w kampaniach 83841 (2025) i 78939 (2023) (B5).
- `seam_trojstyk*.npz` — maski i wartosci PL/CZ na wspolnej siatce (G).
- `.kartograf_cache.db` — powstal dopiero przy pierwszym przebiegu CZ. Tor PL w CLI nie uzywa
  `MetadataCache`, wiec URL-e arkuszy PL nie sa cache'owane miedzy przebiegami.
