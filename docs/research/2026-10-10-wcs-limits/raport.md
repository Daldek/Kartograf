# Pomiar na zywo: limity i zachowanie WCS GUGiK (KRON86)

**Data:** 2026-10-10
**Cel:** dane wejsciowe do speca (d) — wspolny mechanizm dzielenia zapytan
obszarowych (`transport/`), z ktorego skorzysta (a) wycinki PL z WCS.
**Zakres:** tylko KRON86 (EVRF2007 tymczasowo niedostepny — decyzja
uzytkownika): NMT 1 m `DigitalTerrainModelFormatTIFF` /
`DTM_PL-KRON86-NH_TIFF`, NMPT `DigitalSurfaceModel` / `DSM_PL-KRON86-NH`.
Ortofotomapa poza zakresem.
**Srodowisko:** jednorazowe skrypty `requests` + `rasterio` z `.venv`,
sekwencyjnie, 2 s przerwy; probki i skrypty poza repo (katalog wskazany
przez uzytkownika, ponizej `<out>`). Zapytania WCS 2.0.1 GetCoverage
`SUBSET=x(...)&SUBSET=y(...)` w EPSG:2180, jak `GugikWcsMixin`. Obszar
testowy: od (480000, 450000), centralna Polska.

## 1. GetCapabilities / DescribeCoverage

- Serwer to MapServer (komentarze `WARNING: Optional metadata ...`).
  Capabilities nie deklaruja zadnego limitu rozmiaru (brak `MaxWidth`,
  `MaxHeight`, `MAXSIZE`).
- Rozszerzenia: `scaling`, `interpolation` (`NEAREST`, `AVERAGE`,
  `BILINEAR`), `crs` (2180, 4326, 3857), `range-subsetting`.
- Formaty NMT: `image/tiff`, `image/png`, `image/jpeg` + warianty 8 bit.
  NMPT dodatkowo `image/x-aaigrid`.
- NMT: siatka 715202 x 697593 px, krok 1 m. NMPT: 1430403 x 1395186 px,
  krok 0,5 m. Pole `nilValues` puste (brak deklarowanego nodata).
- Origin w DescribeCoverage (NMT `796521.169410 160828.843266`) NIE
  odpowiada faktycznej siatce pikseli (pkt 4) — nie nadaje sie do
  wyznaczania fazy siatki.

## 2. Rozmiar odpowiedzi NMT KRON86 (GeoTIFF)

| Zadanie [px] | Mpx | HTTP | Czas [s] | Rozmiar [MB] | Wynik |
|---|---|---|---|---|---|
| 1000 x 1000 | 1 | 200 | 3,9 | 4,0 | float32, 1000 x 1000 |
| 2000 x 2000 | 4 | 200 | 11,6 | 16,0 | float32 |
| 4000 x 4000 | 16 | 200 | 46,6 | 64,0 | float32 |
| 4096 x 4096 | 16,8 | 200 | 51,6 | 67,1 | float32 |
| 4097 x 4097 | 16,8 | 200 | 51,3 | 67,2 | float32 (brak progu MapServera 4096) |
| 5000 x 5000 | 25 | 200 | 78,1 | 100,0 | float32 |
| 8000 x 8000 | 64 | 200 | 212,6 | 256,0 | float32 |
| 10000 x 10000 | 100 | 200 | 307,8 | 400,1 | float32 |
| 20000 x 500 | 10 | — / 200 | 0,2 / 34,0 | — / 40,0 | 1. proba: `RemoteDisconnected`; ponowienie OK |
| 500 x 20000 | 10 | 200 | 32,1 | 40,0 | float32 |
| 40000 x 250 | 10 | 200 | 32,5 | 40,0 | float32 |

- **Brak twardego limitu do 100 Mpx** (10 x 10 km przy 1 m) i brak limitu
  dlugosci boku do 40000 px. Wyzej nie mierzono.
- Odpowiedz to nieskompresowany float32: ok. 4 MB/Mpx. Przepustowosc
  ok. 1,0-1,4 MB/s, czyli ok. 3 s/Mpx; czas rosnie liniowo.
- Faktyczne ograniczenie to czas i stabilnosc hosta: 1 z 12 zadan zerwane
  bez odpowiedzi (`RemoteDisconnected`), ponowienie przeszlo. Duzy kawalek
  = dlugie zadanie i drogie ponowienie.
- Rozmiar wyniku zawsze rowny zadanemu (`round(bok / krok)`), transform
  zaczyna sie dokladnie w (min_x, max_y) zadania, CRS EPSG:2180.

## 3. Brak nodata

- `nodata` w GeoTIFF: brak (None) we wszystkich odpowiedziach.
- Poza pokryciem serwer wypelnia **0,0**: morze na polnoc od Helu
  (460000-460200, 790000-790200) i Niemcy za Odra ok. 25 km na poludnie
  od Slubic (195000-197000, 480000-482000) — 100 % pikseli = 0,0. Wiecej
  okien granicznych: pkt 8.
- Wniosek: 0,0 jest nieodroznialne od prawdziwej wysokosci 0 m (wybrzeze,
  depresje Zulaw). Arkusze OpenData maja `NODATA -9999`.

## 4. Siatka pikseli i przesuniecie bbox

Porownanie z arkuszami OpenData KRON86 1 m tego samego miejsca
(`M-34-2-A-b-4-3`, `M-34-2-A-d-2-1`, krawedzie pikseli na `x.5`):

| Bbox zadania | Transform odpowiedzi | Wzgledem arkusza |
|---|---|---|
| na siatce arkusza (478713.5, ...) | 478713.5 | **bit w bit** (max roznica 0,0) |
| przesuniety o 0,25 m | 478713.75 | te same wartosci, opisane 0,25 m obok — cichy blad geolokalizacji |
| przesuniety o 0,5 m | 478714.0 | przesuniecie o 1 px w x, w y bez zmian (remis najblizszego sasiada) |

- Serwer probkuje do siatki zadania (najblizszy sasiad); bbox spoza
  siatki zrodla daje dane przesuniete wzgledem opisu o ulamek piksela,
  bez zadnego sladu w odpowiedzi (ten sam rzad bledu, ktory ADR-024
  wykluczyl dla serwerowej reprojekcji).
- Zadanie na calkowitych metrach (480000.0) i na 480000.5 dalo identyczne
  tablice z transformami rozniacymi sie o 0,5 m.
- Faza siatki: krawedzie `k + 0,5` m w osmiu dalszych rejonach (pkt 7),
  w tym pod Krakowem, gdzie arkusze 5 m kampanii 2022 maja rozne fazy
  (`GridMismatchError`, fala naprawcza 2026-09-30) — WCS 1 m ma tam
  jedna faze.
- `SCALEFACTOR=4` dziala (zmiany wartosci co 4 px, faza `x.5`).
  `INTERPOLATION=NEAREST` przyjete; URI OGC
  (`.../interpolation/OGC/1/nearest-neighbor`) — `InvalidParameterValue`.

## 5. Skladanie kawalkow

Zadanie 600 x 600 px vs 4 kawalki 300 x 300 px na tej samej siatce,
zlozone `np.block`: **bit w bit** dla NMT i dla NMPT. Dzielenie zadania na
kawalki o wspolnej siatce (calkowita liczba pikseli od jednego punktu
zaczepienia) nie zmienia tresci.

## 6. NMPT KRON86 — `image/tiff` nie zwraca wysokosci

- `FORMAT=image/tiff` dla `DSM_PL-KRON86-NH` zwraca **3-kanalowy uint8**
  (RGB, wartosci 124-125 tam, gdzie wysokosc ok. 124,5 m), nie float32.
  To format, ktorego dzis uzywa `GugikNmptProvider.download_bbox`
  (`WCS_FORMATS["GTiff"]` z `GugikWcsMixin`). Potwierdzone wywolaniem
  biblioteki `GugikNmptProvider(vertical_crs="KRON86").download_bbox(...)`
  (50 x 50 m): plik 3 x uint8, wartosci 124-125 — **biblioteczne
  pobieranie NMPT z bbox daje dzis RGB zamiast wysokosci** (blad).
- `FORMAT=image/x-aaigrid` zwraca wysokosci (float, ASC) jako
  `multipart/related; boundary=wcs` (czesc `result.asc`), jak EVRF2007
  w (a). Naglowek ASC bez linii `NODATA_value`.
- W probce ASC kazda wartosc wystepuje parami w wierszu (124.52 124.52
  124.57 124.57 ...) — tresc o rozdzielczosci 1 m podana na siatce
  0,5 m (w tym rejonie).
- Limitow rozmiaru NMPT nie mierzono (ASC ok. 20 B/px przy 0,5 m —
  kosztowne).

## 7. Faza siatki w innych rejonach

Metoda: `SCALEFACTOR=4` na 50 x 50 m od calkowitego naroznika (piksel
0,25 m), pozycje zmian wartosci mod 4. Wszystkie rejony: zmiany wylacznie
na indeksie 2 (50/50), czyli krawedzie pikseli zrodla na `k + 0,5` m
w x i y.

| Rejon (lon, lat) | Krawedz x | Krawedz y |
|---|---|---|
| Krakow (19,95; 50,06) — rejon mieszanych faz 5 m | 0,5 | 0,5 |
| Szczecin (14,55; 53,43) | 0,5 | 0,5 |
| Bialystok (23,16; 53,13) | 0,5 | 0,5 |
| Rzeszow (22,00; 50,04) | 0,5 | 0,5 |
| Gdansk (18,65; 54,35) | 0,5 | 0,5 |
| Wroclaw (17,03; 51,11) | 0,5 | 0,5 |
| Zakopane (19,95; 49,30) | 0,5 | 0,5 |
| Suwalki (22,93; 54,10) | 0,5 | 0,5 |

Zgodne z pomiarem arkuszy 1 m (84 arkusze, faza `k + 0,5`, PROGRESS
2026-09-29) i z pkt 4. Siatka WCS NMT 1 m = krok 1 m, faza 0,5 m.

## 8. Pogranicze, wybrzeze, depresja — WCS vs arkusze OpenData

Metoda: okno 2 x 2 km na siatce `k + 0,5`; WCS jednym zadaniem; arkusze
KRON86 1 m tego okna pobrane CLI (`download --bbox ... --country pl
--vertical-crs KRON86`, najnowszy lot wg ADR-028), zlozone `merge`
z nodata -9999 i porownane piksel w piksel.

| Okno | Arkusze (lot) | Wazne w arkuszach | WCS = arkusz (wazne) | Arkusz nodata -> WCS | Uwagi |
|---|---|---|---|---|---|
| PL-DE Slubice (Odra) | 2 | 100 % | 100 % | — | okno w calosci po stronie PL |
| PL-CZ Cieszyn (Olza) | 3 z 4 (1 bez KRON86 1 m) | 80,4 % | 100 % | 0,0 (784 371 px), 5 px != 0 | |
| PL-CZ Karkonosze | 2 z 4 | 88,1 % | 100 % | 0,0 (478 065 px) | |
| PL-SK Tatry | 2 z 4 | 71,0 % | 100 % | 0,0 (1 162 140 px) | |
| Wybrzeze Leba | 3 z 4 (2017 i starsze) | 74,6 % | 100 % | 0,0 (1 016 670 px) | 4233 px wazne arkusza = 0,0 (lustro wody) — WCS takze 0,0 |
| Zulawy (depresja) | 4 (2 x 2018, 2 x 2017 i starsze) | 100 % | 77,8 % | — | min -2,25 m; arkusze 2018: 100 % zgodne; arkusze 2017 i starsze: 100 % pikseli rozne, mediana 0,07 i 0,14 m |
| PL-BY Terespol (Bug) | 2 z 4 (2018, oba `full_sheet` NIE) | 35,2 % | 93,5 % | 0,0 (2 591 617 px) | `N-34-144-C-a-4-4`: 1 097 379 px waznych w arkuszu, w WCS = 0,0 (mediana roznicy 132 m) |

Pomiar per arkusz (Zulawy, Terespol — arkusz w swoim zasiegu): WCS ma
tez dane w pasie nodata arkusza (55-67 tys. px na arkusz Zulaw,
36-312 tys. px w Terespolu) — zasieg WCS nie jest zasiegiem arkusza.

Wnioski:

- Za granica, na morzu i w brakujacych arkuszach WCS zwraca **0,0**, bez
  nodata. Na wybrzezu prawdziwe wysokosci 0,0 m wystepuja w danych
  waznych (Leba: 4233 px), wiec 0,0 nie moze sluzyc jako nodata.
- Tam, gdzie arkusz jest najnowszym lotem i WCS ma ten sam lot, tresc jest
  bit w bit (Cieszyn, Karkonosze, Tatry, Leba, Zulawy 2018).
- **WCS nie zawsze pokazuje najnowszy lot ADR-028:** Zulawy (arkusze
  z warstwy "2017 i starsze": caly arkusz inny o 7-14 cm — inny lot)
  i Terespol (WCS bez danych na 1,1 mln px, ktore najnowszy lot arkusza
  ma). Ktory lot sklada serwer, nie wiadomo; WCS jest gotowa kompozycja
  serwera, nie odpowiednik `--campaigns newest`.
- Mechanizm dzielenia (d) tego nie zmienia — kazdy kawalek dostaje te
  sama kompozycje serwera (pkt 5). To fakty dla (a): wybor zrodla
  wycinka, nodata, sidecar (brak kampanii).

## Wnioski dla speca (d)

1. Limit kawalka dla GUGiK WCS to budzet niezawodnosci, nie limit serwera:
   kawalek okreslony liczba pikseli (proponowane ok. 16 Mpx, ok. 50 s,
   64 MB) z ponowieniem per kawalek. Wartosc jako stala providera,
   z odnosnikiem do tego raportu.
2. Mechanizm musi przyjac siatke zrodla (krok + faza) i wyrownac bbox
   NA ZEWNATRZ do tej siatki przed podzialem — inaczej cichy blad
   geolokalizacji (pkt 4). Dla NMT 1 m: krok 1 m, faza 0,5 m w calym
   kraju (pkt 7). CUZK juz kotwiczy w NW; ta sama regula.
3. Kawalki z jednego zadania maja jeden typ i jedna siatke — skladanie
   bez resamplingu jest bit w bit (pkt 5).
4. Brak nodata (0,0 poza pokryciem i w danych waznych), kompozycja lotow
   serwera inna niz ADR-028 (pkt 8) oraz NMPT `image/tiff` = RGB uint8
   (pkt 6) to problemy tresci, nie dzielenia — do rozstrzygniecia w (a).
