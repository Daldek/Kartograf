# Znane bledy z testow na zywych danych (2026-09-29) — lista kontrolera

Zrodla: raporty w tym katalogu (`L1`..`L7`, `D1`, `D2`). Wszystkie ponizsze pozycje czekaja na
DECYZJE UZYTKOWNIKA o naprawie kodu — w fali dokumentacyjnej NIE sa naprawiane w kodzie.
Oznaczenia: K = wysoki/krytyczny (zle dane po cichu), S = sredni (odpornosc/UX), N = niski.
"Sprzed fal" = istnialo przed 2026-08-28 (fale data/ i review max go nie wprowadzily).

| ID | Waga | Opis (jedno zdanie) | Dowod (raport, sekcja) | Pochodzenie |
|---|---|---|---|---|
| K1 | KRYTYCZNY | LAZ: discovery WFS wysyla bbox w kolejnosci (E,N), a `urn:ogc:def:crs:EPSG::2180` wymaga (N,E); envelope czytany tez odwrotnie, wiec filtr przechodzi — kafle z miejsca transponowanego (~426 km od zadania); potwierdzone A/B przez kontrolera | L1 BUG-L1-1; `gugik_laz.py:363-369`, `:464-465` | sprzed fal (LAZ 2026-06-24) |
| K2 | WYSOKI | Operacja przypieta S-JTSK -> ETRS89 to EPSG:4829 (obszar uzycia: Slowacja, 0,5 m), uzywana w Czechach; wlasciwa EPSG:1622 (Czechy, 1,0 m). Tresc CZ przesunieta do ~5 m (roznica 1622 - 4829 wg pyproj: 0,1-1,0 m na Morawach — Zlin 0,14, Brno 0,98, Ostrawa 1,04 m — do ~5,0 m na zachodzie, kafel 302_5550; wzdluz granicy PL-CZ 1,1-3,4 m; na zywo Karkonosze: 2,3 m wobec GUGiK 1 m, z 1622: 0,38 m). Dotyczy kafli TM33, `--target-crs` CZ, wycinka PL -> 5514, `bbox_to_crs`; sidecar deklaruje 0,5 m. Roznice 1,25 m / 4,92 m, ktore ADR-024 przypisal serwerowi CUZK, odpowiadaja roznicy 1622 - 4829 — diagnoza ADR-024 najpewniej bledna | L4 BUG-L4-1, L2 BUG-L2-4; `transform/crs.py` KNOWN_PATHS, `providers/cuzk/dmr.py` | etap 1 + ADR-027 |
| K3 | WYSOKI | Zerwane zapytanie o nowsza warstwe skorowidza -> po cichu starsza kampania (NMT/NMPT/orto; LAZ pomija rocznik); arkusz zostaje w cache; dwa przebiegi `--force` roznily sie w 21 % pikseli (do 4,2 m; wydmy do 5,2 m) | L2 BUG-L2-1, L3 B2, L5 B5, L1 BUG-L1-5, D2-04/30; `gugik.py` petla warstw | sprzed fal |
| K4 | WYSOKI | Wybor URL arkusza naiwny: pierwszy URL zawierajacy godlo (podciag) bez wzgledu na rozdzielczosc/date/zasieg — "1 m" jako 0,5 m (Szczecin), wycinek 100 % nodata z kodem 0; w warstwie zbiorczej najstarsza kampania (2019 zamiast 2023; orto: zdjecie z 2003); godlo PL-2000 dostaje po cichu arkusz PL-1992 (lista `--system 2000` kod 0, 0 % pokrycia); remedium `--system 2000` z komunikatu PL-2000 daje arkusz-dziecko 1:2000 | L2 BUG-L2-2/3, L1 BUG-L1-3/4; `gugik.py:576-588`, orto `_get_opendata_url` | sprzed fal |
| K5 | WYSOKI | `--product orto` pobiera CIR zamiast RGB | L1 BUG-L1-2 | sprzed fal |
| K6 | WYSOKI (CZ bbox) | Realny limit `exportImage` CUZK ~8 Mpx na zapytanie, nie 15000 x 4100 — a klient tnie kafle dopiero powyzej 15000 x 4100 px, wiec obszar CZ 2 m zblizony do kwadratu wiekszy niz ~5,5 x 5,5 km (albo np. 10 x 5 km wydluzony W-E) konczy sie HTTP 500; pas N-S szerokosci do ~3,6 km przechodzi (kafle maja najwyzej 4100 px wysokosci; 3,6 x 24,6 km = 3 kafle po 7,4 Mpx; sam mechanizm kafli dziala: 22 Mpx, szwy bit w bit) | L4 BUG-L4-2; `providers/cuzk/client.py:36-37` MAX_EXPORT_*, `:142`, `_tile_grid` | etap 1 |
| S1 | SREDNI | Zapytania skorowidza GetFeatureInfo bez ponowien i bez wspolnej sesji (nowe polaczenie per arkusz): przy zrywanych polaczeniach GUGiK wycinki padaja (Hel CLI 4/4, Karkonosze 3/3); ta sama biblioteka na jednej sesji keep-alive z Retry: 72/72 OK. (Czesc zerwan mogla wynikac z 9 agentow z jednego IP.) | L3 B1, L5 B3, L4 BUG-L4-4; `gugik.py` (`requests.Session()` per wywolanie) | sprzed fal; skutek zaostrzony przez R5 |
| S2 | SREDNI | Tryb listy arkuszy (bez `--target-crs`) bez tolerancji R5: morze/granica = kod 1; `--workers 1` przerywa na pierwszym arkuszu bez danych (0 plikow); `--workers > 1` zglasza tylko pierwszy blad; pod `auto` mylace "nie pobrano danych z PL", choc arkusze sa na dysku | L3 B3, L5 B1/B2, L6 BUG-1/1b, L4 BUG-L4-3, D2-05 | sprzed fal (w backlogu) |
| S3 | SREDNI | `--country auto` po cichu przycina bbox do prostokata kraju (np. na zachod od 14,07°E, na polnoc od 54,90°N; pozostale krawedzie poszerzone o 40-110 m) — inny zasieg i nazwa pliku niz zadanie, bez `Info:` | L5 B4, L3 B5 | etap 1 |
| S4 | SREDNI | NMPT EVRF2007: lista warstw zaszyta w kodzie nieaktualna (2025..2022iStarsze wobec 2026..2023iStarsze) — gdy GetCapabilities zawiedzie, arkusze z edycja w 2025/2024 nadal sie pobieraja (majace takze edycje 2026 — po cichu te starsza), a arkusz spoza nich (tylko w 2026 i/lub 2023iStarsze, a takze arkusz bez danych) konczy sie "brak pokrycia niepewny" | L1 BUG-L1-9; symulacja offline (przeglad fali dokumentacji) | sprzed fal |
| S5 | SREDNI (R1) | Arkusze 5 m kampanii 2022 (okolice Krakowa) maja rozne fazy siatki -> wycinek EPSG:2180 bierze wartosc z sasiedniego piksela (do 0,88 px) i ma 766 px nodata tam, gdzie dane sa (1 m: jedna faza k+0,5 w 84 arkuszach; 5 m w cache Hydrografu i w Lebie: 5k+2,5) | L1 BUG-L1-7 | fala review max (R1) — przeslanka faktu 1 nie jest uniwersalna |
| N1 | NISKI | Puste katalogi po arkuszach bez danych (`mkdir` przed zapytaniem) | L3 B4, L5 B6, L4 BUG-L4-7 | sprzed fal |
| N2 | NISKI | Wynik w 100 % nodata przyjmowany jako sukces bez komunikatu (plik CZ nad DE/PL w prostokacie CZ; wycinek PL) | L4 BUG-L4-5, L5 | etap 1 / fala |
| N3 | NISKI | Natywny wycinek CZ (EPSG:5514) ma piksel 2,0004 m zamiast 2 m | L4 BUG-L4-6 | etap 1 |
| N4 | NISKI | Arkusze pominiete (juz na dysku) nie dostaja `extra.parent_request`; przy pominietym wycinku `PlCutoutResult.missing_sheets == ()` mimo dziur w rastrze | L1 BUG-L1-6, D1 | fale |
| N5 | NISKI | Testy `pytest -m live` (8) niczego nie sprawdzaja (nieistniejaca warstwa, tylko HTTP 200) | L1 BUG-L1-10 | sprzed fal |
| N6 | NISKI | `MetadataCache` nie jest podlaczony w zadnym torze PL (CLI, `DownloadManager`, `download_pl_cutout`: `_cache is None`), choc dokumentacja twierdzi inaczej | D2-01, L3 | sprzed fal |
| N7 | NISKI | LAZ: przy awarii sieci komunikat "No LAZ tiles found" zamiast bledu sieci | L1 BUG-L1-8 | sprzed fal |
| N8 | NISKI | Sidecar pliku PL-2000 deklaruje `horizontal_crs` EPSG:2180 | L1 BUG-L1-11, L2 BUG-L2-3 | sprzed fal |
| N9 | NISKI (wydajnosc) | Oszacowanie miejsca na dysku (`estimate_pl_cutout_bytes`, ~7 ms na arkusz nieobecny w cache) liczone dwukrotnie, gdy wolajacy sam je liczy przed `run_pl_cutout` (13-21 % czasu duzego wycinka); CLI tego nie robi (uzywa `cutout.estimated_bytes`) | L7 | fala review max |
| H1 | hipoteza | Regex URL skorowidza pomija rozszerzenie `.ASC` wielkimi literami (niezweryfikowane) | L5 | — |

## Korekty po przegladzie (2026-09-29)

Po niezaleznym przegladzie fali dokumentacji (`DOCS-REREVIEW-REPORT.md`) opisy
czterech pozycji poprawiono (tresc tabeli wyzej jest juz po korekcie; ID i wagi bez
zmian):

- **K2** — zakres przesuniecia "1,1-4,9 m" zastapiony "ok. 1-5 m" z rozbiciem:
  roznica EPSG:1622 - EPSG:4829 policzona pyproj (`TransformerGroup("EPSG:4156",
  "EPSG:4258")`, operacje "S-JTSK to ETRS89 (1)" i "(3)", punkt ETRS89 -> S-JTSK
  przez (1), z powrotem przez (3), odleglosc na GRS80): Ostrawa 1,07, Brno 0,98,
  Jaworzynka 1,12, Cieszyn 1,15, Glucholazy 1,60, Kudowa 2,15, Karkonosze 2,73,
  Swieradow 3,12, Bogatynia/Hradek 3,39, Praga 3,15, kafel 302_5550 4,97-4,98
  (L4: 5,00), As 5,06 m. Dotychczasowe "4,9 m" (Cheb 12,37°E) nie obejmowalo
  zachodniego kranca (kafel 302_5550 ~5,0 m).
- **K6** — regula "bbox wiekszy niz ~5,5 x 5,5 km konczy sie HTTP 500, takze po
  kafelkowaniu" byla nieprecyzyjna: limit ~8 Mpx dotyczy pojedynczego zapytania,
  a klient tnie kafle dopiero, gdy wymiar przekroczy 15000 x 4100 px
  (`client.py:142`, `_tile_grid`) — pas N-S szerokosci do ~3,6 km przechodzi
  (kafle maja najwyzej 4100 px wysokosci; L4 S3b), a obszar zblizony do
  kwadratu wiekszy niz ~5,5 x 5,5 km i np. 10 x 5 km W-E nie. Dodane
  `plik:linia` (`client.py:36-37`).
- **S4** — "gdy GetCapabilities zawiedzie, NMPT nie pobiera sie wcale" bylo
  zawyzone: symulacja offline (sesja-atrapa: warstwy spoza zaszytej listy ->
  `LayerNotDefined`, `_fetch_wms_layers` -> `ConnectionError`) daje URL dla
  arkusza w 2025 i w 2024, "brak pokrycia niepewny" dla arkusza tylko w 2026,
  tylko w 2023iStarsze albo bez danych, a dla arkusza w 2026 i 2024 — po cichu
  edycje 2024. Obserwacja L1 (arkusz `M-34-76-A-a-1-1` z edycja 2023) zgodna.
- **N9** — "przy typowym uzyciu" zastapione warunkiem: podwojny koszt placi
  wolajacy, ktory sam liczy `estimate_pl_cutout_bytes` przed `run_pl_cutout`
  (jak skrypt pomiarowy L7); CLI liczy tylko `cutout.estimated_bytes`
  (`cli/download_cmd.py:1034`).
- **K2 (druga korekta, re-review rundy f52593a — RR-16):** dolna granica "ok. 1 m"
  byla falszywa — na Morawach roznica EPSG:1622 - EPSG:4829 wynosi 0,1-1,0 m
  (pomiar kontrolera ta sama metoda pyproj: Zlin 0,14, Uherske Hradiste 0,23,
  Olomouc 0,75, Brno 0,98, Ostrawa 1,04 m). Zakres w dokumentach: "do ~5 m
  (wzdluz granicy PL-CZ 1,1-3,4 m)".
