# L4 — pogranicze PL-CZ na zywych danych (GUGiK + CUZK), 2026-09-29

Agent L4, galaz `develop` @ 152c31e, repo nietkniete (`git status` czysty). Katalog roboczy:
`e2e-data/2026-09-29-live/L4-pogranicze-cz/` (wszystkie polecenia z niego, cache `.kartograf_cache.db`
lokalny). Pobrano lacznie ok. 0,53 GB (PL arkusze 273 MB, CUZK 254 MB z sondami). `--workers` <= 2.

**Status ogolny: tory PL/CZ i dyspozycja `--country auto` dzialaja mechanicznie (sciezki, sidecary,
`parent_request`, `missing_sheets`, `Warning:`, kody wyjscia), ale sa 2 bledy o wysokiej wadze:
(1) przypieta operacja pozioma S-JTSK wybiera transformacje SLOWACKA (EPSG:4829) takze w Czechach —
tresc CZ po kazdej reprojekcji Kartografa (kafel TM33, `--target-crs`, wycinek PL do EPSG:5514)
jest przesunieta o 1-5 m (zmierzone na zywo 2,3 m w Karkonoszach); (2) realny limit `exportImage`
CUZK to ~8 Mpx, nie 15000x4100 — obszar CZ 2 m wiekszy niz ok. 5,5 x 5,5 km konczy sie HTTP 500,
takze po kafelkowaniu.**

---

## 1. Zakres

| Obszar | Zadanie | Dlaczego |
|---|---|---|
| A Cieszyn (Olza) — przyklad z CLAUDE.md | `--bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326` | przyklad dokumentacji 1:1; granica na rzece, teren plaski |
| A2 Cieszyn duzy | `--bbox 18.56,49.72,18.68,49.78 --bbox-crs EPSG:4326` (8,7 x 6,7 km, 20 arkuszy 5 m) | arkusze calkowicie po stronie CZ -> `missing_sheets`; dlugi odcinek granicy do pomiaru styku |
| B Karkonosze (Sniezka) | 5 m: `--bbox 15.70,50.725,15.78,50.748 --bbox-crs EPSG:4326`; 1 m/2 m: `--bbox 266600,323400,270500,325200` (EPSG:2180, 2 arkusze) | granica na grzbiecie, stoki >20° — czuly test rejestracji poziomej |
| C Beskid Slaski (Jaworzynka/Hrcava) | `--bbox 488000,186800,490300,188300` (EPSG:2180, 2 arkusze 1 m) | trzeci odcinek, wschod (blisko SK) — kontrola rejestracji w innym miejscu |
| D Raciborz (PL w prostokacie CZ) | `--bbox 18.20,50.08,18.22,50.09 --bbox-crs EPSG:4326` | semantyka `--country auto` poza faktyczna granica |
| Godla CZ | `302_5550` (TM33, przyklad z docs), `CTES96` (SM5, Cesky Tesin) | segmenty `nmt/cz_dmr5g_*`/`cz_dmr4g_*`, sidecary, EVRF2007 |
| Kafelkowanie CZ | `--bbox=-646000,-994000,-636000,-984000` (10x10 km) i pas `--bbox=-612000,-1045000,-608400,-1020400` (3,6 x 24,6 km) EPSG:5514, 2 m | pozycja checklisty release (>16 Mpx), nigdy nieuruchomiona na zywo |

Granica panstwa do pomiarow styku: CUZK INSPIRE AU WFS (`au:AdministrativeBoundary`, `nationalLevel=1stOrder`,
pobrana dla kazdego obszaru jednym zapytaniem BBOX, `border/*.xml`).

## 2. Wyniki per scenariusz

Kody wyjscia/czasy/stderr: `runs/<nazwa>/{cmd,stdout,stderr,rc,time,maxrss}.txt`.

| # | Scenariusz (polecenie skrocone; wszystkie z `-o ./data`) | rc | czas | Wynik |
|---|---|---|---|---|
| S1a | A: `--country auto --target-crs EPSG:2180 --vertical-crs EVRF2007 --resolution 5m -w 2` | 0 | 5,0 s | **PASS** |
| S1b | A2: jw. | 0 | 22,2 s | **PASS** (UWAGA U1: 2 arkusze poza siatka) |
| S1c | B 5 m: jw. (CLI, 3 proby) | 0 | 4-10 s | **FAIL** (chwilowe `RemoteDisconnected` GUGiK, BUG-L4-4); przez API z sesja z retry — **UWAGA** (wycinek PL 100% nodata, BUG-L4-5) |
| S1d/e | B 1 m: `--country auto --resolution 1m --target-crs EPSG:2180` + `--country cz --target-crs EPSG:2180 --vertical-crs EVRF2007` | 0/0 | 16/5 s | **PASS** (`Info: --country auto -> pl (--resolution 1m dotyczy tylko PL)`) |
| S-STYK | pomiar styku A2, B(1m/2m), C | — | — | **UWAGA** — zakladka ~310-340 m, bez szczeliny; tresc CZ przesunieta o 2,3 m w B (BUG-L4-1) |
| S2j | A dokladnie jak w CLAUDE.md (domysly: PL 1 m, CZ 2 m) | 0 | 24,6 s | **PASS** (UWAGA U3: PL EVRF2007 + CZ Bpv w jednym zadaniu) |
| S2a/k/l | A2 bez `--target-crs` (tryb listy): auto `-w 2`, `--country pl -w 1` | 0/1/1 | 5-17 s | **FAIL** (BUG-L4-3: `-w 1` -> 0 plikow) |
| S2b, S1f, S4c | `--country cz --bbox` natywnie (EPSG:5514) | 0 | 2-11 s | **PASS** z UWAGA (piksel != 2 m, BUG-L4-6) |
| S2c/d | `302_5550 --country cz` (Bpv / EVRF2007) | 0/0 | 2-3 s | **PASS** sciezki/sidecar; **UWAGA**: kafel w 93,4% nodata (U9), polozenie tresci obciazone BUG-L4-1 |
| S2e/f | `CTES96 --resolution 5m` (Bpv / EVRF2007) | 0/0 | 2-3 s | **PASS** |
| S2g/h/i | `CTES96` bez `--resolution`; `302_5550 --target-crs`; `CTES96 ... KRON86` | 1/1/1 | 0,4 s | **PASS** (bledy przed siecia; UWAGA U5/U6) |
| S3 | kafelkowanie 10x10 km 2 m (2 kafle 5000x2500) | 1 | 30 s | **FAIL** (HTTP 500, BUG-L4-2) |
| S3b-d | pas 1800x12300 px = 22,1 Mpx (3 kafle po 7,38 Mpx) + 2 niezalezne paski przez szwy | 0 | 135 s | **PASS** — szwy bit w bit |
| S3e | pojedyncze zadanie 3000x3000 (9 Mpx, bez kafelkowania) | 1 | 25 s | **FAIL** (HTTP 500, BUG-L4-2) |
| S4a/b | C: PL 1 m + CZ 2 m do EPSG:2180 | 0/0 | 15/5 s | **PASS** |
| S5 | D: auto `--target-crs EPSG:2180 --resolution 5m` | 0 | 5,4 s | **PASS** (zgodnie z docs: wycinek CZ 100% nodata, bez komunikatu — U4) |
| S6 | B: `--country pl --resolution 1m --target-crs EPSG:5514` (arkusze z cache) | 0 | 31 s | **UWAGA** — wycinek przesuniety o 2,3 m wzgledem natywnego DMR 5G (BUG-L4-1) |

Podsumowanie: **PASS 10, FAIL 4 (S1c-CLI, S2a/k/l, S3, S3e), UWAGA 4 (S-STYK, S1c-lib, S2c/d, S6)**.

### Dowody szczegolowe

**S1a** (przyklad z docs): dwa pliki o identycznej nazwie w dwoch segmentach:
`nmt/pl_1992_5m_evrf2007/bbox/471194.6628_209462.3009_474803.6146_211258.6264.tif` (EPSG:2180, 723x361,
`transform: null`, `vertical_crs: EPSG:9651`) i `nmt/cz_dmr4g_evrf2007/bbox/<ta sama nazwa>.tif`
(EPSG:2180, 722x359, `vertical_crs: EPSG:5621`, `transform.horizontal: pinned: ... S-JTSK to ETRS89 (3) ... (0.5 m)`,
`transform.vertical: pinned: Baltic 1957 height to EVRF2007 height (1) (0.1 m)`). Oba sidecary:
`extra.parent_request = {"bbox": [18.6, 49.752, 18.65, 49.768], "bbox_crs": "EPSG:4326", "countries": ["CZ", "PL"]}`.
Wycinek PL vs arkusze (srodek piksela -> arkusz): **0 rozbieznosci z 207 360**; nodata dokladnie tam,
gdzie zaden arkusz nie ma danych (`verify_pl2180.py`). Wycinek PL lezy na siatce arkuszy (faza 2,5/2,5,
rozszerzenie 2,2/4,8/3,9/3,9 m < 1 px), CZ na siatce kotwiczonej w NW rogu bboxa (faza 4,66/3,63).

**S1b**: rc 0, `Warning: GUGiK nie ma danych dla 8 arkuszy wycinka (M-34-74-C-a-3-2, ...) — w tych miejscach
wycinek ma nodata (lista w sidecarze: extra.missing_sheets)`; sidecar ma te 8 godel. Wszystkie 8 arkuszy
leza w calosci po stronie czeskiej (0% nodata CZ w ich zasiegu) — brak "falszywych" braków. Wycinek vs
arkusze: 0 rozbieznosci poza zasiegiem 2 arkuszy spoza siatki (9 652 px w ich zasiegu — zgodnie z
ostrzezeniem `mosaic_and_crop: 2 z 12 zrodel poza siatka ... (maks. 0.330 px)`, U1).

**S1d**: `Info: --country auto -> pl (--resolution 1m dotyczy tylko PL)`; `parent_request.countries = ["PL"]`.

**S2c/d/e/f (godla CZ)**: `nmt/cz_dmr5g_bpv/302/5550/302_5550.tif` (EPSG:3045, 1000x1000, 2 m, sidecar
`request.godlo`, `horizontal_crs: EPSG:3045`, `vertical_crs: EPSG:8357`), `nmt/cz_dmr5g_evrf2007/302/5550/...`
(`EPSG:5621`, `transform.vertical`), `nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif` (+ `.tfw`, EPSG:5514, 500x400, 5 m,
siatka na wielokrotnosciach 5 m, `extra.mapname: "Český Těšín 9-6"`, `extra.podil: 0.99`),
`nmt/cz_dmr4g_evrf2007/CTES/96/...`. Maski nodata Bpv/EVRF2007 identyczne. Przesuniecie EVRF2007 - Bpv:
+0,1324 m (302_5550), +0,1277 m (CTES96), stale do 0,1 mm w obrebie pliku. Kafel TM33 vs niezalezny
wycinek natywny 5514 tego samego obszaru (S2b), ta sama operacja: dz srednio 0,0000 m, std 1,6 cm,
dopasowane przesuniecie (0,000; 0,002) m — spojnosc wewnetrzna OK (bezwzgledne polozenie: BUG-L4-1).

**S3b-d (kafelkowanie)**: `nmt/cz_dmr5g_bpv/bbox/-612000_-1045000_-608400_-1020400.tif` 1800x12300 px,
piksel dokladnie 2,0 m, bounds = zadanie, 88,6% waznych; max RSS 293 MiB (merge kawalkami, 22 Mpx >
16 Mpx). Niezalezne paski 1800x200 przez oba szwy (wiersze 4100 i 8200): **360 000/360 000 pikseli
rownych bitowo, max |d| = 0,0**; srednia |dz| miedzy sasiednimi wierszami na szwie = poza szwem
(0,256 vs 0,250 m; 0,181 vs 0,183 m). Mechanizm kafelkowania + chunked merge dziala — o ile kafel
miesci sie w realnym limicie serwera (BUG-L4-2).

## 3. Styk PL/CZ (dane wejsciowe do R6)

Metoda (`styk.py`): oba wycinki w EPSG:2180; CZ probkowany bilinear w srodkach pikseli PL; granica
panstwa z CUZK (EPSG:5514 -> 2180 ta sama polityka co warp); odleglosc znakowana (+ = strona CZ).
Krawedz danych = piksel wazny sasiadujacy z nodata wewnatrz obszaru analizy. dz liczone bez pasa 2 px
przy krawedziach danych. Pliki: `styk_*.txt`, `styk_*.png`.

| Odcinek | Dane PL / CZ | Krawedz GUGiK w glab CZ (med [p5..p95]) | Krawedz CUZK w glab PL | Zakladka krawedz-krawedz (med [min..max]) | Szczelina |
|---|---|---|---|---|---|
| A2 Cieszyn | NMT 5 m (2023, "Zdj. lotnicze") / DMR 4G | 197,2 m [87,2..402,4] | 117,3 m [113,1..121,8] | 312,0 m [176,7..668,6] | 0 px |
| B Karkonosze | NMT 1 m (2025) / DMR 5G | 200,7 m [198,5..215,9] | 118,7 m [117,1..120,2] | 318,5 m [314,7..380,5] | 0 px |
| C Beskid | NMT 1 m / DMR 5G | 200,7 m [199,2..354,8] | 119,1 m [117,0..120,8] | 338,3 m [315,2..530,7] | 0 px |
| B Karkonosze **5 m** | brak arkuszy 5 m GUGiK / DMR 4G | — (0 px danych PL) | 118,6 m | — | **5,17 km² po stronie PL** (od 118 do 1240 m od granicy) |

Wnioski o przycinaniu: **GUGiK wydaje dane z buforem ~200 m za granice** (1 m i 5 m, trzy odcinki,
p25-p75 w 193-202 m); odstepstwa to krawedzie arkuszy/kampanii (prosta linia arkusza `M-34-74-C-d-1-x`
w Cieszynie, "trojkat" starego arkusza 2019, klin do 400 m w Beskidzie). **CUZK (DMR 4G i 5G) — bufor
~118 m za granice** (rozrzut 110-126 m). Wynik: **zakladka ~310-340 m, zadnej szczeliny** tam, gdzie
GUGiK ma produkt w danej rozdzielczosci. Szczelina pojawia sie przy dziurze pokrycia GUGiK (Karkonosze
5 m: 10 z 12 arkuszy bez 5 m, w tym `M-33-44-C-b-4-4`/`C-d-2-1` w Polsce — 1 m dla nich jest, warstwa
2025 i starsze; GetFeatureInfo w `gfi/kk*`).

Roznice wysokosci w pasie wspolnym, dz = PL - CZ (oba EVRF2007; CZ tak, jak go wydaje Kartograf):

| Odcinek | n | med | std | MAE | teren 0-2° (med / MAE) | spadek >20° (MAE) |
|---|---|---|---|---|---|---|
| A2 Cieszyn (5 m) | 98 991 | +0,097 | 0,526 | 0,336 | +0,094 / 0,283 | 0,637 |
| B Karkonosze (1 m vs 2 m) | 1 394 375 | -0,151 | 0,600 | 0,416 | -0,188 / 0,185 (std 0,093) | 0,876 |
| C Beskid (1 m vs 2 m) | 856 374 | -0,092 | 0,340 | 0,243 | -0,106 / 0,247 | 0,375 |
| B z operacja czeska EPSG:1622 (A/B) | 1 393 118 | -0,170 | **0,194** | **0,197** | -0,186 / 0,183 (std 0,068) | **0,237** |
| C z operacja czeska EPSG:1622 (A/B) | 854 517 | -0,059 | 0,337 | 0,229 | -0,108 / 0,252 | 0,345 |

- Pas +-20 m wokol granicy w Cieszynie (koryto Olzy) ma dz ~ -0,55 m (lustro wody: fotogrametria vs ALS)
  — ciecie po linii granicy wypadloby dokladnie tam; scalanie powinno raczej wazyc w calej zakladce.
- Po usunieciu bledu rejestracji (operacja EPSG:1622) zostaje systematyczny offset pionowy
  zalezny od zbioru (mediany w klasach spadku): -0,17..-0,19 m (Karkonosze), -0,03..-0,12 m (Beskid),
  +0,09..+0,14 m (Cieszyn, 5 m fotogrametryczny, spadek do 10°). Oba uklady to "EVRF2007", ale rozne kody: PL `EPSG:9651`, CZ `EPSG:5621` (przez
  EPSG:5202 z Bpv: +0,125..+0,142 m zmierzone).
- Siatki pikseli NIE sa wspolne: PL 5 m na 5k+2,5, PL 1 m na k+0,5 (8 arkuszy, 3 regiony), CZ z warpu
  kotwiczony w NW rogu bboxa zadania (A: faza 3,30/3,50 m; B, C: 0/0 przy calkowitym bboxie; przesuniecie
  do PL 0,5-2,2 m), rozmiary tez rozne (np. 1736x1344 vs 1735x1343). Dla R6: zakotwiczyc siatke warpa CZ
  na siatce arkuszy PL (wtedy obie siatki pokrywaja sie bez resamplingu PL).

## 4. Bledy (reprodukcja + hipoteza; NIE naprawiane)

### BUG-L4-1 (WYSOKI) — przypieta operacja S-JTSK -> ETRS89 to EPSG:4829 (obszar uzycia: SLOWACJA), uzywana w Czechach

Reprodukcja offline:
```
.venv/bin/python -c "
import dataclasses; from pyproj.crs import CoordinateOperation
from kartograf.transform.crs import build_pinned_transform
from kartograf.providers.cuzk.dmr import _HORIZONTAL_POLICY, CZ_PROBE_NATIVE
p = build_pinned_transform('EPSG:5514','EPSG:3045', dataclasses.replace(_HORIZONTAL_POLICY, probe_point=CZ_PROBE_NATIVE))
print(p.description); o = CoordinateOperation.from_epsg(4829); print(o.name, o.area_of_use.name, o.area_of_use.bounds)"
# -> ... S-JTSK to ETRS89 (3) + UTM zone 33N ...   /   S-JTSK to ETRS89 (3) Slovakia. (16.84, 47.73, 22.56, 49.61)
```
Ta sama operacja idzie do: kafli TM33 (5514->3045), `--target-crs` CZ (5514->2180/3045), wycinka PL
`--target-crs EPSG:5514` (odwrotnosc; `S6` sidecar: `Inverse of S-JTSK to ETRS89 (3)`), obwiedni
`bbox_to_crs`. Sidecar deklaruje `(0.5 m)` — to dokladnosc w Slowacji.

Dowod na zywo (dane GUGiK 1 m jako niezalezny wzorzec polozenia; `shiftfit.py` dopasowuje
dz ~ a + gx·dx + gy·dy; `ab_warp.py` warpuje TEN SAM natywny raster CUZK tym samym `_warp_to_grid`
dwiema operacjami):

| Obszar | Operacja | przesuniecie tresci CZ wzgl. PL (dE, dN) | std dz bez modelu -> z modelem |
|---|---|---|---|
| Karkonosze (sredni spadek 14°) | EPSG:4829 (Kartograf) | **(-2,26; +0,61) m** | 0,544 -> 0,122 m |
| Karkonosze | EPSG:1622 (CZ) | (+0,38; -0,03) m | 0,138 -> 0,108 m |
| Karkonosze, wycinek PL -> EPSG:5514 vs natywny DMR 5G (S6) | EPSG:4829 | (-2,19; +0,77) m (osie 5514) | 0,530 -> 0,117 m |
| Beskid (przy SK, 12,8°) | EPSG:4829 / EPSG:1622 | (-0,05; +0,68) / (-0,40; -0,43) m | 0,256 / 0,246 m |
| Cieszyn (5 m fotogr., 4°) | EPSG:4829 / EPSG:1622 | (-0,97; -0,81) / (-1,03; -2,14) m | 0,356 / 0,387 m — teren za plaski, nierozstrzygajace |

Kontrola A/B: wycinek CLI (EVRF2007) minus moj warp EPSG:4829 (Bpv) = 0,1415 m stale (std 0,0001) —
A/B odtwarza warp Kartografa. Roznica EPSG:1622 - EPSG:4829 w Czechach: Cheb (302_5550) 5,00 m,
Praga 3,15, Karkonosze 2,72, Kudowa/Nachod 2,15, Cieszyn 1,15, Ostrawa 1,07, Brno 0,98 m.

**Konsekwencja dla ADR-024:** "blad serwerowej reprojekcji 3045" z ADR-024 — 1,25 m na poludnie kolo
Cieszyna (tabela: minimum RMS przy korekcie (0; +1,25)) i 4,92 m w zachodnich Czechach (ADR: dE -4,50,
dN -2,00 w tej samej konwencji korekty, czyli tresc serwera przesunieta o ok. +4,50/+2,00 m) — pokrywa
sie co do wielkosci i kierunku z roznica EPSG:1622 - EPSG:4829 (Cieszyn: dN -1,15 m; 302_5550:
dE +4,56, dN +2,04, razem 5,00 m). Najpewniej serwer
CUZK dla `imageSR=3045` liczyl poprawnie (transformacja czeska), a blad byl po stronie lokalnej operacji
przyjetej za wzorzec. Blad 135 m dla `imageSR=2180` (brak datum shift) pozostaje realnym bledem serwera.
Research `docs/research/2026-08-10-czechy-dmr-zabaged.md` tab. 7.1 oznaczyl operacje (3) jako "TAK —
najlepsza realnie dostepna" dla CZ; PROJ domyslnie (z obszarem) wybiera (1). Ten sam wybor wykryl
offline L2 (BUG-L2-4) — powyzsze pomiary rozstrzygaja, ktora operacja jest poprawna w CZ.

Hipoteza: `kartograf/transform/crs.py:192` (`TransformerGroup` bez `area_of_interest`) + `:236`
(`min(candidates, key=accuracy)`); probe (`isfinite`) nie odrzuca transformacji Helmerta/Molodensky'ego
poza obszarem. Kierunek: `area_of_interest` z bboxa zadania albo odrzucanie kandydatow, ktorych
`area_of_use` nie zawiera punktu probe (lon/lat); z obszarem CZ PROJ zwraca 1622 (1,0 m) na czele.

### BUG-L4-2 (WYSOKI dla CZ bbox) — realny limit `exportImage` CUZK ~8 Mpx, nie 15000x4100

Metadane uslugi (`cuzk/dmr5g_imageserver.json`) deklaruja `maxImageWidth 15000`, `maxImageHeight 4100`,
ale zadanie F32 wieksze niz ~8 Mpx konczy sie `HTTP 500 "Error exporting image"` (po ~7-9 s).
Sondy curl (dmr5g): 2500x2500 OK (26 MB, 40 s), 3000x2500 OK (7,5 Mpx), 6000x1000 OK, 2500x1250 na
obszarze 10x5 km (4 m) OK; 4096x2047 (8,38 Mpx) **500**, 4096x2049 **500**, 5000x2500 **500** (dwa rozne
obszary). Limit zalezy od liczby pikseli, nie od szerokosci ani zasiegu.
Reprodukcja CLI:
```
kartograf download --bbox=-646000,-990000,-640000,-984000 --bbox-crs EPSG:5514 --country cz --resolution 2m   # 3000x3000 -> rc 1 po 3 probach (HTTP 500)
kartograf download --bbox=-646000,-994000,-636000,-984000 --bbox-crs EPSG:5514 --country cz --resolution 2m   # 2 kafle 5000x2500 -> rc 1
```
Oczekiwane: wycinek (kafle w limicie realnym). Skutek: kazdy obszar CZ 2 m > ~5,5 x 5,5 km (i np. pas
graniczny 10 x 5 km) jest niepobieralny; kafelkowanie (limit 61,5 Mpx/kafel) nigdy nie ratuje.
Hipoteza: `providers/cuzk/client.py:37-38` (`MAX_EXPORT_WIDTH/HEIGHT`) + `:145` (warunek tylko per wymiar);
`_tile_grid` potrzebuje budzetu pikseli (np. <= 4-6 Mpx na kafel). Limit dmr4g (5 m) nieweryfikowany.

### BUG-L4-3 (SREDNI) — tryb listy (bbox bez `--target-crs`): brak danych jednego arkusza przerywa zadanie

```
kartograf download --bbox 18.56,49.72,18.68,49.78 --bbox-crs EPSG:4326 --country pl --resolution 5m --workers 1 -o ./data_w1
# rc 1, "Error: No NMT 5m data available for M-34-74-C-a-3-2 ...", 0 plikow (12 arkuszy z danymi nigdy nie odpytanych)
```
Z `--workers 2` pula pobiera wszystko, ale konczy rc 1 i pokazuje tylko pierwszy brak. Pod
`--country auto` (S2a): rc 0 i `Warning: nie pobrano danych z PL dla tego obszaru` — mimo ze 12/20
arkuszy PL jest pobranych (mylace). Niespojne z R5 wycinka (brak danych = nodata + Warning).
Oczekiwane: arkusze bez danych pominiete z `Warning:`/lista, reszta pobrana, rc zalezny od klasy bledu.
Hipoteza: `cli/download_cmd.py` `_download_godlo_list` — petla sekwencyjna bez obslugi `NoCoverageError`
per arkusz (ok. l. 858-872), galaz rownolegla re-raise pierwszego bledu (ok. l. 903-905).

### BUG-L4-4 (SREDNI, odpornosc) — GetFeatureInfo skorowidza bez ponowien

2026-09-29 serwer GUGiK zrywal czesc polaczen (`RemoteDisconnected`, ok. 5-10% zapytan GFI; takze w
L1/L5 — kilku agentow z jednego IP moglo to nasilac). Kazda porazka warstwy daje (poprawnie wg R5)
"brak pokrycia niepewny" -> wycinek Karkonoszy (12 arkuszy x do 4 warstw) padl w **3 z 3** prob CLI
(`runs/S1c_*`: 5+2+4 zerwane zapytania, 3/2/2 arkusze). Ten sam wycinek przez API biblioteki z
providerem na sesji z `urllib3.Retry` (`lib_cutout_retry.py`, `create_nmt_provider(session=...)`) —
sukces za pierwszym razem (6,3 s). Hipoteza: `providers/pl/gugik.py:519` (`self._session or
requests.Session()` — nowe polaczenie na arkusz) i `:567` (pojedynczy `get`), CLI tworzy providera bez
sesji (`cli/download_cmd.py:84`). Pobieranie pliku ma retry (`transport/http.py`), skorowidz nie.
Pokrewne U2 (warstwa najnowsza padla -> cicho starsza kampania).

### BUG-L4-5 (NISKI-SREDNI) — wycinek PL w 100% nodata przyjety jako sukces

Karkonosze 5 m (`runs/S1c_lib_retry.txt`): 10/12 arkuszy bez danych 5 m, 2 pobrane arkusze z marginesu
1 px nie wnosza ani jednego piksela -> `nmt/pl_1992_5m_evrf2007/bbox/267169.5943_...tif` ma 0/647 424
waznych pikseli, sukces (CLI dalby rc 0 + `Warning` o 10 arkuszach). Regula "zaden arkusz nie ma danych
-> ValidationError" sprawdza tylko `sheet_paths` (`download/cutout.py:604-608`), nie tresc wyniku.

### BUG-L4-6 (NISKI) — wycinek CZ natywny (EPSG:5514, jedno zadanie) ma piksel != nominalny

`--country cz --bbox ... --bbox-crs EPSG:3045` -> 1120x1120, piksel **2,000424 m**; przyklad z CLAUDE.md
(auto, domysly) -> **2,000536 m**; Karkonosze -> 2,000244 m. Serwer wymusza kwadratowy piksel, wiec
zasieg Y rozni sie od zadania o ~0,3-0,5 m. Sidecar: `resolution: "2m"`. Tor z warpem i tor kafelkowany
maja piksel dokladny (2,0) i zmieniaja zasieg — niespojnosc trzech sciezek. Hipoteza:
`providers/cuzk/client.py:141-149` (`width_px = round(...)`, bbox wysylany bez dociagniecia
`max_x = min_x + n·px`, jak robi `_tile_grid`).

### BUG-L4-7 (NISKI) — puste katalogi po arkuszach bez danych

18 pustych drzew `data/nmt/pl_1992_5m_evrf2007/M-33/44/C/d/2/1/` itd. (takze `data_w1/`).
Hipoteza: `providers/pl/gugik.py:448` (`mkdir` przed zapytaniem skorowidza), brak `prune_empty_dirs`
przy `NoCoverageError`/`DownloadError` (zn. 10 objal tylko `<segment>/bbox/`).

## 5. Zachowanie do udokumentowania / UWAGI

- **U1** Arkusze GUGiK 5 m NIE zawsze sa na siatce 5k+2,5: w Cieszynie 2 z 12 (`M-34-74-C-c-2-2`,
  `-c-2-4`, warstwa `2022iStarsze`, aktualnosc 2019-04-19, "Zdj. lotnicze", DFT.7201.017.2019) maja
  fazy (3,35; 1,59) i (0,82; 0,21) m. Mozaika: ostrzezenie w logu + NN do 0,33 px; nic w sidecarze
  (backlog `extra.off_grid_sheets` uzasadniony). `M-34-74-C-c-2-4.asc` jest w **100% nodata** (GDAL: int32)
  mimo metadanych skorowidza `calyArkuszWypelnionyTrescia: "TAK"`.
- **U2** Chwilowa porazka najnowszej warstwy -> po cichu starsza kampania (S1d: 2026 padla, uzyto 2025;
  tu 2026 i tak nie miala arkusza). Rocznik danych zalezy od szczescia sieci.
- **U3** `--country auto` bez `--vertical-crs` daje PL w EVRF2007 i CZ w Bpv (S2j: `EPSG:9651` vs
  `EPSG:8357`) — w przykladzie z CLAUDE.md warto dodac `--vertical-crs EVRF2007`.
- **U4** Obszar polski w prostokacie CZ (Raciborz): wycinek CZ 100% nodata, rc 0, zero komunikatu —
  zgodne z CLAUDE.md, ale `Warning:` bylby pomocny.
- **U5** `CTES96` bez `--resolution` -> `Error: Arkusze SM5 sa dostepne tylko dla --resolution 5m` po
  wypisaniu `Downloading CTES96 (CZ, resolution: 2m)...`; godlo SM5 moglo by implikowac 5 m.
- **U6** Potwierdzony znany minor: `...nie sa publiczne Remedium: Siatki...` (brak separatora).
- **U7** EVRF2007 - Bpv (EPSG:5202: 0,13 m + nachylenie): zmierzone +0,1249 (Beskid), +0,1277 (Cieszyn),
  +0,1324 (Cheb), +0,1415 m (Karkonosze); w calej CZ ok. 0,111-0,144 m — help "+0,12..0,14 m" jest za waski.
- **U8** Transformacja pionowa SM5 przepisuje skompresowany TIFF w miejscu: CTES96 780 KB -> 1057 KB (+35%).
- **U9** Przykladowy kafel z docs `302_5550` lezy glownie w Niemczech: 93,4% nodata — lepszy przyklad to
  kafel we wnetrzu CZ.
- **U10** Na pograniczu `--resolution 1m` pod auto zawsze rozstrzyga do PL, wiec strone CZ trzeba pobrac
  osobnym poleceniem (inny `parent_request`, brak grupowania).
- **U11** Wyniki `exportImage` sa zawsze pochodna serwera (bilinear): siatka DMR 5G uslugi ma poczatek
  (-904703,6; -1227414,12), czyli faze (0,4; 1,88) m mod 2 — zadne zadanie na "okraglych" wspolrzednych
  nie oddaje pikseli natywnych 1:1 (1:1 daja tylko arkusze SM5 z openzu).
- **U12** Puste odpowiedzi GetFeatureInfo po stronie czeskiej: HTTP 200, `Content-Type: text/html`,
  7721 znakow (7787 B UTF-8, gzip 2456 B), identyczne md5 (`e4170317...`) dla 4 warstw, bez
  `ServiceException`/`ExceptionReport` (`gfi/a-3-2_center_CZdeep_*.html`) — straz I-2 nie blokuje R5.
- **U13** Siatki i "ten sam EVRF2007": patrz sekcja 3 (rozne kody realizacji, rozne siatki, offsety
  pionowe zbiorow do ~0,19 m).

## 6. Odpowiedzi na pozycje checklisty (PROGRESS "Nastepne kroki" pkt 12/14)

- **(c)** CZ godlo TM33/SM5 i bbox -> `nmt/cz_dmr5g_{bpv,evrf2007}/302/5550/`, `nmt/cz_dmr4g_{bpv,evrf2007}/CTES/96/`,
  `nmt/cz_dmr{4g,5g}_<vcrs>/bbox/<coords>.tif` + sidecary: **PASS** (tresc obciazona BUG-L4-1, piksel BUG-L4-6).
- **(e)/(h)** `--country auto --target-crs EPSG:2180` na zywo: **PASS** w Cieszynie (dwa wycinki,
  wspolny `parent_request`, nodata PL po stronie CZ, `missing_sheets`, `Warning:`, rc 0); Karkonosze 5 m —
  CLI 3/3 porazki przez siec GUGiK (BUG-L4-4), a po udanej budowie wycinek PL = 100% nodata (brak 5 m,
  BUG-L4-5). Styk zmierzony (sekcja 3): GUGiK +~200 m, CUZK +~118 m, zakladka ~310-340 m, bez szczelin
  poza dziurami pokrycia GUGiK; tresc CZ przesunieta o 2,3 m (BUG-L4-1).
- **(f)** 1 m: 8 arkuszy EVRF2007 z 3 regionow — narozniki wszystkie na k+0,5. 5 m: 10/12 na 5k+2,5,
  2/12 (warstwa 2022iStarsze) poza siatka (U1).
- **(g)** Fallback "URL innego arkusza": 0 wystapien w moich przebiegach.
- **(j)** (strona czeska) zapisane body/Content-Type pustej odpowiedzi (U12); zerwane polaczenia sa liczone
  jako awaria, nie brak pokrycia — straz dziala w obie strony.
- **Checklista release, kafelkowanie `exportImage` >16 Mpx**: wykonane — mechanizm i chunked merge
  **dzialaja** (22 Mpx, szwy bit w bit), ale przy obecnych limitach typowe obszary koncza sie HTTP 500
  (BUG-L4-2).

## 7. Surowe artefakty

Katalog: `/home/claude-agent/workspace/Kartograf/e2e-data/2026-09-29-live/L4-pogranicze-cz/`
- `runs/<scenariusz>/` — cmd, stdout, stderr, rc, time, maxrss (32 przebiegi); `runs/S1c_lib_retry.txt`
- `data/` (glowne dane i wycinki), `data_w1/` (BUG-L4-3), `data_rac/` (Raciborz)
- `styk_{cieszyn5m,karkonosze5m,karkonosze1m2m,beskid1m2m,karkonosze_op1622,beskid_op1622}.txt` + `.png`
- `ab/` — warpy A/B EPSG:4829 vs EPSG:1622 (Karkonosze, Beskid, Cieszyn)
- `border/` — GML granic CUZK + JSON odcinkow 1stOrder; `gfi/` — surowe odpowiedzi GetFeatureInfo (62 pliki)
- `cuzk/` — metadane ImageServer + sondy limitu `exportImage`
- skrypty: `run.sh`, `inspect_raster.py`, `verify_pl2180.py`, `verify_cz_tile.py`, `styk.py`, `shiftfit.py`,
  `ab_warp.py`, `gfi.py`, `border_parse.py`, `lib_cutout_retry.py`
