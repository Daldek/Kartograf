# Różnice pokrycia między kampaniami GUGiK (pomiar 2026-10-07)

**Źródło przypadków:** wszystkie surowe odpowiedzi skorowidza z rundy 2026-10-06
(577 grup godło×produkt). Szukano arkuszy, w których najnowszy rekord
(wybierany przez ADR-028) ma `calyArkuszWypelnionyTrescia = NIE`, a istnieje starszy
rekord tego samego wariantu (układ, rozdzielczość NMT, kolor orto) z flagą TAK.
Wynik: 14 arkuszy z niepełnym najnowszym rekordem, w 8 z nich istnieje starsza pełna kampania.
Pozostałe to głównie NMT 0,5 m bez starszej pełnej wersji.

**Pomiar:** obie wersje każdej pary pobrane na
`<katalog-danych>/kartograf/e2e/2026-10-07-pokrycie-kampanii/pliki/`
(1,6 GB). Powierzchnia z danymi: NMT — piksele ≠ nodata; orto — piksel nie (0,0,0),
odczyt co 8. piksel. Skrypty `scan.py` i `measure.py` leżą w tym samym katalogu.

| Produkt | Godło | Wybierany dziś (najnowszy, niepełny) | Starszy pełny | Dane: nowy / stary | Pokrycie nowego |
|---|---|---|---|---|---|
| NMT 1 m | N-34-139-C-a-3-1 | `84183_1852496_N-34-139-C-a-3-1.asc` (2025-10-21, 255×422 px) | `83233_1744736_N-34-139-C-a-3-1.asc` (2025-04-27) | 0,045 / 4,958 km² | **0,9 %** |
| Orto RGB | M-34-90-C-b-4-4 | `84466_1602825_M-34-90-C-b-4-4.tif` (2026-04-25, 0,07 m) | `81437_1434887_M-34-90-C-b-4-4.tif` (2024-06-26, 0,25 m) | 0,174 / 5,485 km² | **3,2 %** |
| NMT 1 m | N-34-144-C-c-2-2 | `83650_1772346_N-34-144-C-c-2-2.asc` (2025-09-22) | `76753_1293139_N-34-144-C-c-2-2.asc` (2022-08-27) | 0,888 / 4,972 km² | **17,9 %** |
| NMT 1 m | N-34-131-D-a-3-2 | `83629_1768456_N-34-131-D-a-3-2.asc` (2025-07-02) | `81449_1658836_N-34-131-D-a-3-2.asc` (2024-06-28) | 1,163 / 4,929 km² | **23,6 %** |
| NMT 1 m | N-34-138-D-d-2-2 | `84183_1852485_N-34-138-D-d-2-2.asc` (2025-10-21) | `83233_1744673_N-34-138-D-d-2-2.asc` (2025-04-27) | 2,882 / 4,962 km² | 58,1 % |
| NMT 1 m | N-34-139-C-a-3-3 | `84183_1852498_N-34-139-C-a-3-3.asc` (2025-10-21) | `83233_1744738_N-34-139-C-a-3-3.asc` (2025-04-27) | 3,131 / 4,960 km² | 63,1 % |
| Orto RGB | 7.125.14.16 (PL-2000 S7) | `84044_1596643_7.125.14.16.tif` (2026-02-27, 0,03 m) | `77914_1187224_7.125.14.16.tif` (2023-03-17, 0,05 m) | 1,514 / 1,600 km² | 94,6 % |
| NMT 1 m | N-34-139-C-c-1-1 | `84183_1852502_N-34-139-C-c-1-1.asc` (2025-10-21) | `83233_1744755_N-34-139-C-c-1-1.asc` (2025-04-27) | 4,910 / 4,963 km² | 98,9 % |

Wszystkie URL mają prefiks `https://opendata.geoportal.gov.pl/NumDaneWys/NMT/<id>/`
(NMT) albo `https://opendata.geoportal.gov.pl/ortofotomapa/<id>/` (orto).
Orto M-34-90-C-b-4-4 ma ten sam wzorzec w wariancie CIR: `84465_1602805` (2026) vs
`81436_1429429` (2024).

**Wnioski:**
- Flaga `calyArkuszWypelnionyTrescia` nie mierzy skali braku. „NIE” obejmuje zarówno
  0,9 %, jak i 98,9 % pokrycia. W drugą stronę też bywa źle: Słubice N-33-126-C-c-3-4
  (E2E-A C10d) mają flagę TAK przy 75 % nodata.
- Kampania 2025-10-21 (zlecenie 84183) to wycinki dosztukowane do pełnej
  kampanii 2025-04-27 (83233). W 4 sąsiednich arkuszach okolic N-34-139-C pokrycie wynosi od 0,9 % do 98,9 %.
- Reguła „najnowsza pełna kampania” byłaby lepsza w 6 z 8 par. W 2 parach
  (94,6 % i 98,9 %) oddałaby jednak starsze dane w zamian za bardzo mały zysk pokrycia.
  Przemawia to za progiem pokrycia albo mozaiką (nowa kampania + uzupełnienie ze starszej),
  a nie za samą flagą.
