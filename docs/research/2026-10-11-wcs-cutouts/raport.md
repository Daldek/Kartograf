# Pomiar na zywo: WCS GUGiK vs arkusze OpenData — siatki, 0,5 m, ASC, maska PRG

**Data:** 2026-10-11
**Cel:** dane wejsciowe do specu (a)
`docs/superpowers/specs/2026-10-11-wcs-cutouts-design.md` (pomiary M1-M3)
oraz rozszerzenie uzytkownika: zakres zapytania wyrownany NA ZEWNATRZ do
siatki arkuszy, tak zeby dane WCS dalo sie porownac z arkuszami 1:1;
zbadac dane 0,5 m.
**Srodowisko:** jednorazowe skrypty `requests` + `rasterio` + `numpy`
z `.venv`, sekwencyjnie; probki, skrypty i logi poza repo (katalog
wskazany przez uzytkownika, ponizej `<out>`). Arkusze 1 m pobrane CLI
(`download <godlo> --product nmt|nmpt --vertical-crs ... --output <out>`,
najnowszy lot 1 m wg ADR-028); arkusze 0,5 m pobrane wprost z URL-i
skorowidza (Kartograf pobiera dokladnie 1 m). Porownanie: `|a - b| <=
0,005` na pikselach waznych w obu (arkusz `-9999` wykluczony).

## 1. Dostepnosc i formaty (2026-10-11)

| Endpoint | Coverage | Wysokosci w | Uwagi |
|---|---|---|---|
| `NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF` | `DTM_PL-KRON86-NH_TIFF` | `image/tiff` float32 | jedyne coverage tego endpointu |
| `NMT/GRID1/WCS/DigitalTerrainModel` | `DTM_PL-EVRF2007-NH`, `DTM_PL-KRON86-NH` | tylko `image/x-aaigrid` (multipart) | `image/tiff` = RGB 3 x uint8 |
| `NMPT/GRID1/WCS/DigitalSurfaceModel` | `DSM_PL-EVRF2007-NH`, `DSM_PL-KRON86-NH` | tylko `image/x-aaigrid` (multipart) | `image/tiff` = RGB 3 x uint8 |
| `NMT/GRID1/WCS/DigitalTerrainModelFormatTIFFEVRF2007` (wpis biblioteki) | — | — | 404 |
| `NMPT/GRID1/WCS/DigitalSurfaceModelFormatTIFF` | — | — | 404 |

- WCS EVRF2007 dziala (backlog: "tymczasowo niedostepny" — nieaktualne).
- Multipart `multipart/related; boundary=wcs`: `result.asc` (naglowek
  `ncols/nrows/xllcorner/yllcorner/cellsize`, bez `NODATA_value`),
  `result.asc.aux.xml`, `result.prj` (ESRI WKT `ETRS89_Poland_CS92`).
  Brak `Content-Encoding` (bez kompresji).
- Domyslna rozdzielczosc odpowiedzi = krok coverage: NMT 1 m, NMPT 0,5 m.

## 2. Siatki arkuszy

| Arkusz | Krok | Naglowek | Krawedzie pikseli |
|---|---|---|---|
| NMT/NMPT 1 m (EVRF2007, KRON86; 5 arkuszy) | 1,0 | `xllcenter`/`yllcenter` calkowite | `k + 0,5` m |
| NMT/NMPT 0,5 m EVRF2007 (3 arkusze, lot 2025) | 0,5 | `xllcenter 302564.50`, `yllcenter 289212.00` | `k + 0,25` / `k + 0,75` m |

Regula wspolna: **srodki pikseli na wielokrotnosciach kroku**
(1 m — pelne metry, 0,5 m — co 0,5 m). Siatki 1 m i 0,5 m sie NIE
zagniezdzaja: krawedz 1 m (`k + 0,5`) to srodek piksela 0,5 m. Piksel 1 m
odpowiada jednemu pikselowi 0,5 m (temu ze srodkiem na pelnym metrze),
a nie blokowi 2 x 2.

## 3. WCS vs arkusz na siatce arkusza (M1)

Okno 200 x 200 m w arkuszu; zapytanie na siatce arkusza (przesuniecie 0)
i przesuniete o 1/4 i 1/2 piksela.

| Dane (lot) | Zapytanie | Przes. 0 | 1/4 px | 1/2 px |
|---|---|---|---|---|
| NMT EVRF2007 1 m `M-34-64-D-d-2-3` (2025) | ASC 1 m | **100 %** | 100 % (opis 0,25 m obok) | 11,2 % |
| NMT KRON86 1 m `M-34-2-A-b-4-3` (2011) | TIFF 1 m | **100 %** | 100 % (opis 0,25 m obok) | 8,0 % |
| jw. | ASC 1 m | **100 %** | 100 % | 8,0 % |
| NMT EVRF2007 0,5 m `M-33-57-C-b-4-2` (2025) | ASC `SCALEFACTOR=2` (0,5 m) | **100 %** | — | — |
| jw. | ASC 1 m | **100 %** wzgledem pikseli 0,5 m o srodkach na pelnych metrach | — | — |
| NMPT EVRF2007 0,5 m `M-33-57-C-b-4-2` (2025) | ASC 0,5 m | **100 %** | 100 % (1/8 m) | 8,7 % |
| NMPT EVRF2007 0,5 m `M-34-64-D-d-2-3` (2025) | ASC 0,5 m | **100 %** | 100 % (1/8 m) | 5,0 % |
| NMPT KRON86 1 m `M-34-2-A-b-4-3` (2011) | ASC `SCALEFACTOR=0.5` (1 m) | **100 %** | — | — |
| jw. | ASC 0,5 m na siatce `k + 0,0/0,5` | **100 %** (kazda wartosc arkusza 2 x 2) | 52,0 % (remis) | 27,7 % |
| NMPT EVRF2007 0,5 m `M-34-64-D-d-2-3` (2025), 2 okna | ASC `SCALEFACTOR=0.5` (1 m) | **100 %** wzgledem pikseli 0,5 m o srodkach na pelnych metrach | — | — |

Wnioski:

- Zapytanie na siatce arkusza daje tresc arkusza **bit w bit** we
  wszystkich zbadanych parach (NMT/NMPT, KRON86/EVRF2007, 1 m/0,5 m,
  TIFF/ASC). Wyrownanie zakresu do siatki arkusza wystarcza do porownania
  1:1.
- Przesuniecie < 1/2 px: te same wartosci opisane obok (cichy blad
  geolokalizacji, jak raport 2026-10-10 pkt 4); 1/2 px: remis najblizszego
  sasiada, inne wartosci.
- **NMT "1 m" niesie tresc 0,5 m** tam, gdzie najnowszy lot jest 0,5 m:
  `SCALEFACTOR=2` na siatce `k + 0,25` zwraca arkusz 0,5 m bit w bit
  (sasiednie kolumny rowne w 51,9 % — to nie powielenie). W obszarze lotu
  1 m (`M-34-64-D-d-2-3`) `SCALEFACTOR=2` daje powielone pary (100 %)
  z remisem na krawedzi 1 m — wynik 0,5 m nad trescia 1 m nie jest
  zgodny z arkuszem 1 m na zadnej siatce 0,5 m `k + 0,25`.
- Zapytanie 1 m nad trescia 0,5 m = dokladna decymacja (piksel 0,5 m
  o srodku na pelnym metrze), bez usredniania — NMT (natywnie 1 m)
  i NMPT (`SCALEFACTOR=0.5`).

## 4. WCS = najnowszy lot; `M-33-57-C-b-4-2` to granica, nie dziura

`M-33-57-C-b-4-2`, NMT EVRF2007 (arkusz graniczny PL-DE): w oknie
303563,75-303763,75 x 290409,75-290609,75 najnowszy lot 2025 (0,5 m) jest
wazny w 55,2 %, lot 2023 (1 m) w 100 %.

| Piksele okna | WCS |
|---|---|
| lot 2025 wazny | 100 % rowne arkuszowi 2025 |
| lot 2025 nodata (44,8 %) | 100 % = 0,0 (lot 2023 ma tam dane) |

Wyjasnienie (uwaga uzytkownika, sprawdzone rasteryzacja PRG `A00` na
siatce arkuszy, srodek piksela):

| Lot | Wazne w arkuszu | Wazne POZA PL | Nodata W PL |
|---|---|---|---|
| 2025, 0,5 m | 71,8 % | **0 px** | 1 320 716 px (0,33 km2) |
| 2023, 1 m | 85,9 % | 781 754 px (0,78 km2) | 330 233 px (0,33 km2) |

Lot 2025 jest przyciety do granicy panstwa, lot 2023 ma pas za granica.
Nodata obu lotow w PL to ta sama powierzchnia (0,33 km2 — pas wzdluz
granicy w rasteryzacji srodkiem piksela). 0,0 w oknie WCS lezy wiec za
granica, nie w dziurze lotu w PL — maska PRG zamienia je na nodata.
NMPT w tym samym arkuszu (okno przy polnocnej krawedzi, WCS 0,0, lot 2021
wazny) — ten sam uklad granicy (nie rasteryzowano osobno).

Wniosek: WCS pokazuje najnowszy lot i nie dokleja starszych lotow (tu:
pasa lotu 2023 za granica). Dziury najnowszego lotu WEWNATRZ PL nie
zostaly w tym pomiarze znalezione. Z raportu 2026-10-10 pkt 8: Terespol
(arkusz graniczny na Bugu) nie byl rasteryzowany wzgledem `A00` i moze
miec to samo wyjasnienie; Zulawy (wewnatrz PL, WCS inny o 7-14 cm od
arkuszy "2017 i starsze") to inny lot w WCS, nie dziura.

## 5. Rozmiar i czas `image/x-aaigrid` (M2)

| Coverage | Zadanie | Rozmiar | Czas | Uwagi |
|---|---|---|---|---|
| `DTM_PL-EVRF2007-NH` 1 m | 1000 x 1000 (1 Mpx) | 20,5 MB (20,5 B/px) | 25,0 s | |
| jw. | 2000 x 2000 (4 Mpx) | 82,1 MB | 76,1 s (19,0 s/Mpx) | 1. proba: brak danych przez 1200 s (`ReadTimeout`), ponowienie OK |
| jw. | 4000 x 4000 (16 Mpx) | 328,3 MB | 326,6 s (20,4 s/Mpx) | 1. proba: `ReadTimeout` po 1200 s, ponowienie OK |
| `DSM_PL-EVRF2007-NH` 0,5 m | 1000 x 1000 (1 Mpx) | 20,2 MB (20,2 B/px) | 23,1 s | timeout odczytu 60 s |
| jw. | 2000 x 2000 (4 Mpx) | 80,5 MB | 80,7 s (20,2 s/Mpx) | 1. proba `ReadTimeout` 60 s, 2. OK |
| jw. | 4000 x 4000 (16 Mpx) | — | — | 6 prob, kazda `ReadTimeout` po 60 s (brak pierwszego bajtu) |

Czas do pierwszego bajtu (`stream=True`, timeout odczytu 600 s):

| Coverage | Zadanie | Pierwszy bajt | Calosc |
|---|---|---|---|
| `DTM_PL-EVRF2007-NH` | 1 Mpx | 6,8 s | 19,7 s |
| `DTM_PL-EVRF2007-NH` | 4 Mpx | — | `ReadTimeout` po 600 s (zawieszenie) |
| `DSM_PL-EVRF2007-NH` | 4 Mpx | 25,2 s | 77,9 s |

- ASC: ok. 20,5 B/px (5 x TIFF float32), ok. 20 s/Mpx (TIFF KRON86:
  ok. 3 s/Mpx) — ok. 1 MB/s. Parsowanie 16 Mpx: 7 s.
- Serwer milczy przed pierwszym bajtem tym dluzej, im wieksze zadanie
  (1 Mpx: 7 s, 4 Mpx: 25 s); 16 Mpx nie zaczyna odpowiedzi w 60 s.
  `GugikProvider.DEFAULT_TIMEOUT` = 30 s jest timeoutem odczytu, wiec
  kawalek ASC 4 Mpx jest na granicy, a 16 Mpx nigdy sie nie uda.
- Host zawiesza odpowiedzi bez zerwania polaczenia: 3 zadania NMT 4-16 Mpx
  bez danych przez 600-1200 s; krotki timeout odczytu + ponowienie
  przerywa zawieszenie szybko.

## 6. Maska PRG (M3)

- `BBOX` NIE przycina geometrii: `A00_Granice_panstwa` dla okna 2 x 2 km
  przy Lebie = caly poligon (2,0 MB, 72 997 wierzcholkow, 1,8 s).
  `W02`/`W03` dla okna bez morza = 0 obiektow (1 kB, 0,3 s) — mozna je
  pominac poza wybrzezem.
- `A00` obejmuje morze terytorialne (patrz spec 1.3).
- Przynaleznosc punktow (`BBOX` 2 x 2 m, `RESULTTYPE=hits`):

| Punkt | A00 | W02 | W03 | Maska |
|---|---|---|---|---|
| Leba miasto, plaza | 1 | 0 | 0 | lad |
| Leba 300 m, 2 km, 20 km w morze | 1 | 1 | 0 | nodata |
| Srodek Zatoki Gdanskiej, Gdynia 300 m od brzegu, koniec mola w Sopocie | 1 | 0 | 1 | nodata |
| Plaza w Sopocie | 1 | 0 | 0 | lad |
| Zatoka Pucka (Kuznica), cypel Helu 1 km SE, 1 km N od Helu | 1 | 0 | 1 | nodata |
| Ujscie Wisly (Przekop) 1 km, Zalew Wislany | 1 | 0 | 1 | nodata |
| Zatoka Gdanska na N od Krynicy Morskiej | 1 | 1 | 0 | nodata |

- Przekroje: Gdynia (szer. 54,5165) — lad do dl. 18,550, W03 od 18,555;
  Krynica Morska (dl. 19,444) — Zalew (W03) do szer. 54,375, lad Mierzei
  54,380-54,385, W02 od 54,390.
- Nie zmierzono zgodnosci linii brzegu W02/W03 z pikselami NMT
  (rozdzielczosc przekrojow 300-500 m) — do sprawdzenia w implementacji.

## 7. Wnioski dla specu (a)

1. Siatka zapytania = siatka arkuszy dla rozdzielczosci wyniku: 1 m —
   `GridSpec(1.0, 0.5, 0.5)`, 0,5 m — `GridSpec(0.5, 0.25, 0.25)`;
   zakres wyrownany NA ZEWNATRZ przed podzialem na kawalki. Daje tresc
   arkusza bit w bit (pkt 3).
2. Rozdzielczosc wyniku nie musi byc krokiem coverage: NMT 0,5 m przez
   `SCALEFACTOR=2`, NMPT 1 m przez `SCALEFACTOR=0.5` (pkt 3).
3. Wynik 0,5 m nad trescia 1 m nie jest porownywalny 1:1 z arkuszem 1 m
   (siatki sie nie zagniezdzaja, remis na krawedzi) — pkt 3.
4. WCS = najnowszy lot bez doklejania starszych (pkt 4). W
   `M-33-57-C-b-4-2` 0,0 to obszar za granica (lot 2025 przyciety do
   granicy) — lapie go maska PRG; dziur najnowszego lotu w PL nie
   znaleziono.
5. Kawalki ASC: 1 Mpx (pierwszy bajt ok. 7 s, calosc ok. 20-25 s) —
   bezpiecznie ponizej timeoutu odczytu 30 s; 4 Mpx = pierwszy bajt
   ok. 25 s (za blisko). TIFF bez zmian (16 Mpx).
6. Maska: pobierac W02/W03 tylko, gdy zwracaja obiekty dla obszaru; A00
   zawsze w calosci (pkt 6).
