# `calyArkuszWypelnionyTrescia` na arkuszach granicznych (pomiar 2026-10-10)

**Pytanie (uzytkownik, 2026-10-10):** czy flaga TAK na arkuszach granicznych
z duzym udzialem nodata (Slubice N-33-126-C-c-3-4: TAK przy 75 % nodata)
oznacza, ze GUGiK liczy pelne pokrycie wylacznie na obszarze Polski?

**Odpowiedz:** tak — na wszystkich 13 zmierzonych plikach z flaga TAK
(12 arkuszy granicznych na granicach z DE, CZ, SK, UA, BY, LT + kontrola
w glebi kraju) w ramce arkusza po polskiej stronie granicy nie ma ANI
JEDNEGO piksela nodata. Nodata lezy wylacznie za granica. Jedyny zmierzony
plik z NIE ma 13,8 % nodata po polskiej stronie. Definicji pola od GUGiK
nie znaleziono (wyszukiwanie w sieci); wniosek jest empiryczny.

## Metoda

- Granica PL: PRG WFS `AdministrativeBoundaries`, warstwa
  `ms:A00_Granice_panstwa` (jeden poligon, EPSG:2180, osie (N, E)).
- Arkusze: dla 12 punktow na granicach (przejscia/miasta graniczne)
  arkusze 1:10000 PL-1992 z `find_sheets_for_bbox`, wybrane te z 10-90 %
  obszaru ramki w PL (rasteryzacja co 25 m). Dla 22 takich arkuszy pelne
  listy rekordow skorowidza NMT 1 m EVRF2007 (`resolve_campaigns(all)`).
  Punkt RU (Gronowo) nie dal arkusza w przedziale 10-90 %.
- Pomiar: najnowszy rekord TAK pierwszego arkusza kazdego obszaru (11
  plikow) + wczesniejsze pliki: Slubice C10d (TAK), Terespol
  N-34-144-C-c-2-2 2022 (TAK) i 2025 (NIE), kontrola N-34-130-D-d-2-4
  (C1a, TAK).
- **Liczone tylko w ramce arkusza.** Plik ASC to obwiednia trapezu ramki
  w EPSG:2180 (np. N-33-126-C-c-3-2: plik 195813,5-198083,5 x
  507959,5-510406,5 = obwiednia ramki); narozniki poza ramka sa nodata
  i odpowiadaja za ~10 % nodata takze w arkuszach w glebi kraju (C1a
  9,9 % w calym pliku, 0,0 % w ramce). Ramka: poludniki/rownolezniki
  zageszczone (50 punktow na bok) i przeliczone `pyproj` do EPSG:2180,
  zwezona o 2 px.
- Pas +/- 10 m wokol linii granicy wylaczony (generalizacja PRG wzgledem
  krawedzi danych).

## Wyniki

Rekordy skorowidza 22 arkuszy granicznych (18-82 % PL): 61 z 62 rekordow
TAK; jedyny NIE: M-34-82-D-b-2-3 (Medyka) 2023-04-18, miedzy dwoma lotami
TAK.

| Obszar | Arkusz | Lot | Flaga | PL w ramce | nodata w ramce | nodata po stronie PL | dane za granica |
|---|---|---|---|---|---|---|---|
| DE Slubice | N-33-126-C-c-3-2 | 2024-09-03 | TAK | 31,1 % | 54,5 % | **0 px** | 20,4 % |
| DE Slubice (C10d) | N-33-126-C-c-3-4 | 2024-09-03 | TAK | 12,6 % | 72,3 % | **0 px** | 16,9 % |
| DE Gubin | M-33-6-A-b-4-3 | 2023-05-22 | TAK | 64,6 % | 19,9 % | **0 px** | 42,6 % |
| DE Zgorzelec | M-33-31-A-c-3-3 | 2025-06-13 | TAK | 82,4 % | 3,9 % | **0 px** | 76,9 % |
| DE Kostrzyn | N-33-126-A-a-4-4 | 2023-04-22 | TAK | 61,9 % | 25,0 % | **0 px** | 33,5 % |
| CZ Cieszyn | M-34-74-C-a-4-4 | 2025-06-22 | TAK | 35,6 % | 48,0 % | **0 px** | 25,0 % |
| CZ Kudowa | M-33-57-C-b-4-2 | 2023-05-04 | TAK | 77,1 % | 7,7 % | **0 px** | 65,4 % |
| SK Lysa Polana | M-34-101-A-a-4-4 | 2024-08-14 | TAK | 59,3 % | 29,5 % | **0 px** | 26,5 % |
| UA Medyka | M-34-82-D-b-2-3 | 2024-06-16 | TAK | 47,7 % | 37,9 % | **0 px** | 26,9 % |
| UA Zosin | M-35-37-C-c-1-4 | 2022-07-26 | TAK | 71,0 % | 13,9 % | **0 px** | 50,9 % |
| BY Terespol | N-34-144-C-d-1-1 | 2022-08-27 | TAK | 70,6 % | 14,7 % | **0 px** | 48,7 % |
| LT Ogrodniki | N-34-72-C-a-3-3 | 2025-10-03 | TAK | 41,6 % | 42,2 % | **0 px** | 27,2 % |
| BY Terespol | N-34-144-C-c-2-2 | 2022-08-27 | TAK | 100 % | 0,0 % | **0 px** | — |
| BY Terespol | N-34-144-C-c-2-2 | 2025-09-22 | NIE | 100 % | 13,8 % | **141 099 px (13,8 %)** | — |
| kontrola (wnetrze) | N-34-130-D-d-2-4 | 2025-04-26 | TAK | 100 % | 0,0 % | **0 px** | — |

"Dane za granica" = udzial pikseli z danymi w ramce za granica (poza pasem
10 m): GUGiK publikuje pas danych w glab sasiada (17-77 % zagranicznej
czesci ramki), ale nie cala zagraniczna czesc.

## Wnioski

1. TAK = arkusz wypelniony w calosci **w granicach Polski**; nodata za
   granica nie odbiera flagi. Slubice 75 % nodata to zagraniczna czesc
   ramki, nie blad flagi.
2. Obawa z backlogu "(c)" o arkuszach brzegowych, ktore nigdy nie sa
   pelne, nie potwierdza sie dla granic ladowych: wszystkie 22 arkusze
   graniczne maja loty TAK. Arkusze bez lotu TAK to (z wczesniejszych
   pomiarow) glownie NMT 0,5 m i pasy dosztukowane (NIE).
3. Nodata w ramce arkusza TAK nie jest wiec miara jakosci danych na
   pograniczu; plik `full_coverage/` ma pelne dane po stronie PL.
4. Nie zmierzono: wybrzeza (zasieg poligonu A00 na morzu nie sprawdzony),
   NMPT, orto, 5 m.

## Pliki

W katalogu danych (STANDARDS 6.4)
`<katalog-danych>/kartograf/e2e/2026-10-10-pelne-pokrycie-granica/`:
`A00_granica_panstwa.gml`, `wybor.py` (wybor arkuszy, `sheets.json`),
`measure.py` (pomiar, `wyniki.json`), `pliki/` (11 plikow ASC).
