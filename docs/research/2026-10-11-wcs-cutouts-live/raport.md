# Weryfikacja na zywo: wycinki PL z WCS GUGiK (a)

**Data:** 2026-10-11
**Galaz:** `feat/wcs-cutouts` (plan
`docs/superpowers/plans/2026-10-11-wcs-cutouts.md`, Task 8)
**Srodowisko:** CLI `.venv/bin/kartograf` z korzenia repo i jednorazowe
skrypty `requests` + `rasterio` + `numpy` z `.venv`; dane, skrypty i logi
poza repo (katalog wskazany przez uzytkownika, ponizej `<out>`). Referencje
arkuszowe: arkusze pobrane w pomiarze
`docs/research/2026-10-11-wcs-cutouts/raport.md` (1 m CLI, 0,5 m z URL-i
skorowidza). Porownanie: rownosc wartosci float32 na pikselach waznych
w obu rastrach.

## 1. Wycinki CLI (krok 1)

`download --bbox ... --country pl --target-crs EPSG:2180 --output <out>`:

| Produkt / uklad | Bbox (EPSG:2180) | Kod | Czas | Wynik |
|---|---|---|---|---|
| NMT EVRF2007 | 567500,242500,568500,243500 (`M-34-64-D-d-2-3`) | 0 | 34-94 s | `nmt/pl_1992_1m_evrf2007/bbox/567500_242500_568500_243500_20261011.tif` |
| NMT KRON86 | 479000,451000,480000,452000 (`M-34-2-A-b-4-3`) | 0 | 8-10 s | `nmt/pl_1992_1m_kron86/bbox/..._20261011.tif` |
| NMPT EVRF2007 | jak NMT EVRF2007 | 0 | 93-104 s | `nmpt/pl_1992_1m_evrf2007/bbox/..._20261011.tif` |
| NMPT KRON86 | jak NMT KRON86 | 0 | 34-87 s | `nmpt/pl_1992_1m_kron86/bbox/..._20261011.tif` |

- Plik: 1 pasmo float32, nodata -9999, zasieg `k + 0,5` (np.
  567499,5-568500,5), CRS EPSG:2180.
- Sidecar: `extra.source` z endpointem, coverage, formatem
  (`image/x-aaigrid`; KRON86 NMT `image/tiff`) i `composition: "server"`;
  `extra.mask.masked_pixels = 0` (obszary w glebi ladu); `vertical_crs`
  EPSG:9651/9650.
- Drugi bieg tego samego dnia zastapil pliki (te same nazwy), bez
  `Skipped`. CLI wypisal `Info:` o 2 zapytaniach WCS (zakres 1001 x 1001 px
  po wyrownaniu). Host w trakcie pomiaru: pojedyncze `Read timed out`
  i zerwania polaczen; ponowienia `download_to` przeszly.

## 2. Wycinek WCS = arkusz (krok 2)

| Wycinek | Referencja | Rowne |
|---|---|---|
| NMT EVRF2007 | arkusz 1 m `M-34-64-D-d-2-3` (lot 2025) | 100 % (1 002 001 px) |
| NMT KRON86 | arkusz 1 m `M-34-2-A-b-4-3` (lot 2011) | 100 % |
| NMPT KRON86 | arkusz NMPT 1 m `M-34-2-A-b-4-3` | 100 % |
| NMPT EVRF2007 | arkusz NMPT 0,5 m zdecymowany (piksel o srodku na pelnym metrze) | **99,83 %** przed poprawka, **100 %** po poprawce (pkt 3) |

## 3. Nieparzysty rozmiar zapytania (znalezione w kroku 2)

W pierwszym przebiegu NMPT EVRF2007 roznil sie od zdecymowanego arkusza
0,5 m w 1739 px (max 13,6 m) — dokladnie w jednej kolumnie i jednym
wierszu: srodku kazdego zapytania (kawalek 501 px: kolumna 250; jedno
zapytanie 1001 x 1001: kolumna i wiersz 500). Wartosc w tych liniach
pochodzi z sasiedniego piksela 0,5 m. Kawalki i jedno zapytanie roznily
sie miedzy soba (2225 px) — wynik zalezal od podzialu na kawalki.

Sonda (zapytanie n x n px od (567599,5; 242599,5), NMPT `SCALEFACTOR=0.5`
wzgledem zdecymowanego arkusza 0,5 m):

| n | 100 | 200 | 255 | 256 | 257 | 400 | 512 |
|---|---|---|---|---|---|---|---|
| Rozne px | 0 | 0 | 480 (kolumna i wiersz 127) | 0 | 481 (kolumna i wiersz 128) | 0 | 0 |

Ten sam efekt bez `SCALEFACTOR` dla NMT EVRF2007 1 m nad lotem 0,5 m
(`M-33-57-C-b-4-2`, od (303600,5; 290400,5)): n = 255 — 388 px w kolumnie
i wierszu 127, n = 256 — 0. NMT nad lotem 1 m (n = 1001) i KRON86 — bez
roznic (serwer nie przeprobkowuje). Wniosek: przy przeprobkowaniu serwer
przy nieparzystym rozmiarze bierze srodkowy wiersz i kolumne z sasiedniego
piksela zrodla.

**Poprawka (commit `fix(wcs): parzyste rozmiary zapytan ...`):** kazde
zapytanie WCS z siatka ma parzysta szerokosc i wysokosc — zakres wyrownany
do siatki jest poszerzany o najwyzej 1 px na wschod/poludnie, kawalki maja
parzyste wymiary (`plan_chunks(multiple=2)`), wynik jest przycinany po
zszyciu. Po poprawce wszystkie cztery wycinki z pkt 2 = arkusz w 100 %.

## 4. Kawalki = jedno zapytanie, czas (krok 3)

Obszar 2000 x 1000 px (567100,5-569100,5 x 243000,5-244000,5):

| Produkt | Kawalki | Czas kawalkami | Jedno zapytanie | Bit w bit |
|---|---|---|---|---|
| NMT EVRF2007 | 2 | 50-206 s | 47-58 s (39,3 MB) | tak (3 przebiegi) |
| NMPT EVRF2007 (`SCALEFACTOR=0.5`) | 8 (po 0,25 Mpx, pkt 5) | 1186 s | 78 s (39,3 MB) | tak |

Czas kawalkami jest zdominowany przez zawieszenia hosta: w przebiegu
NMPT 7 z 8 kawalkow przekroczylo za pierwszym razem limit odczytu 120 s
i przeszlo w ponowieniu.

## 5. Pierwszy bajt ASC (sondy w trakcie kroku 3)

- NMPT `SCALEFACTOR=0.5`, 500 x 500 px wyniku (1 Mpx coverage), timeout
  300 s, 6 zapytan: pierwszy bajt po 18,8 / 45,9 / 68,0 s (calosc +2-3 s,
  4,9 MB), 3 zapytania bez odpowiedzi przez 300 s. Kolejna seria (timeout
  120 s): 36,1 / 37,2 / 106,5 s.
- W tej samej serii NMT EVRF2007 1 Mpx: 2 x `ReadTimeout` po 120 s,
  NMPT natywne 0,5 m: `ConnectionError` po 10 s (host przeciazony; rano
  ten sam NMT 1 Mpx mial pierwszy bajt po ok. 7 s — raport 2026-10-11 pkt 5).
- Odpowiedz ASC nie zaczyna sie przed policzeniem calego kawalka;
  przy `SCALEFACTOR` czas rosnie z liczba pikseli coverage.

**Zmiany:** budzet kawalka ASC liczony w pikselach coverage (NMPT 1 m =
4 piksele 0,5 m na piksel wyniku -> 0,25 Mpx wyniku); kawalki ASC czekaja
na dane co najmniej `WCS_ASC_READ_TIMEOUT = 120` s (dotad 30 s: trzy
kolejne `ReadTimeout` kawalka NMPT 1 Mpx konczyly zadanie bledem).
Zawieszenia 600-1200 s nadal sa przerywane. Zostaje do strojenia przy
spokojniejszym hoscie: budzet kawalka NMPT i limit odczytu (jedno
zapytanie 2 Mpx NMPT przeszlo w 78 s, a kawalki 0,25 Mpx wisialy).

## 6. Maska ladu na wybrzezu (krok 4)

Okna 1 x 1 km (1 002 001 px) NMT EVRF2007; `download_bbox` (bez maski)
wzgledem wycinka z maska PRG na tej samej siatce:

| Okno (srodek EPSG:2180) | Poza maska | Wysokosc WCS poza maska (5/50/95/99 percentyl) | Poza maska > 1 m / > 2 m / > 5 m | 0,0 na ladzie (zostaje) | 0,0 poza maska |
|---|---|---|---|---|---|
| Gdynia (471007, 739269) | 479 873 px | -0,06 / 0,03 / 0,19 / 0,94 m | 3825 / 93 / 0 | 82 | 32 443 |
| Hel (487085, 749040) | 518 169 px | 0,19 / 0,28 / 0,80 / 1,50 m | 18 724 / 1048 / 0 | 0 | 0 |
| Mierzeja Wislana, Krynica Morska (528828, 724307) | 83 198 px | 0,15 / 0,23 / 1,00 / 1,39 m | 4142 / 0 / 0 | 0 | 0 |

- Morze i zalewy w WCS to nie 0,0, tylko powierzchnia wody ok. 0-0,3 m
  (mediana); 0,0 jest tylko czescia morza (Gdynia).
- Maska nie wycina ladu wyzszego niz 5 m; powyzej 2 m wypada 93 px
  (Gdynia) i 1048 px (Hel) — pas brzegu/nabrzezy przy linii PRG.
- Na ladzie zostaja niskie piksele: 1. percentyl 0,1-0,8 m, piksele
  <= 0,2 m: 5850 (Gdynia), 440 (Hel), 1322 (Mierzeja) — plaza i brzeg
  wody po ladowej stronie linii PRG. `zero_pixels` = 82 tylko w Gdyni.

## 7. EPSG:5514, `--country auto`, granica (krok 5)

- `--bbox 567500,242500,568000,243000 --country pl --target-crs EPSG:5514`:
  kod 0, 537 x 537 px EPSG:5514, `transform.horizontal` = `pinned: ...
  Krovak East North ... (1.0 m)`, `masked_pixels` 0.
- `--bbox 18.80,49.70,18.81,49.705 --bbox-crs EPSG:4326 --target-crs
  EPSG:2180` (auto): dwa pliki (PL WCS z data, CZ exportImage) ze wspolnym
  `extra.parent_request` (`countries: ["CZ", "PL"]`); obszar lezy w PL
  (PL `masked_pixels` 0, CZ w calosci nodata z `Warning:`), kod 0.
- `M-33-57-C-b-4-2` (granica PL-DE), `--bbox 303400,290300,303900,290800`:
  501 x 501 px, `masked_pixels` 97 495 (39 % — strona niemiecka),
  `zero_pixels` 21.

## 8. `download_bbox` z biblioteki (krok 6)

Bbox 567600-567700 x 242600-242700: NMT EVRF2007, NMPT EVRF2007 i NMPT
KRON86 — 1 pasmo float32, 1 m, zasieg 567599,5-567700,5, nodata brak
(dotad NMPT: 3 pasma uint8 RGB, 0,5 m; NMT EVRF2007: `ValidationError`).

## 9. Wnioski

1. Wycinki NMT/NMPT (oba uklady) na siatce arkuszy 1 m = arkusz tego
   samego lotu piksel w piksel, takze NMPT nad lotem 0,5 m (decymacja) —
   pod warunkiem parzystego rozmiaru zapytania (pkt 3, poprawione).
2. Kawalki skladaja sie bit w bit z jednym zapytaniem (NMT i NMPT).
3. Host jest niestabilny; ASC potrzebuje dluzszego limitu odczytu niz
   GeoTIFF (pkt 5, poprawione); strojenie budzetu NMPT zostaje w backlogu.
4. Maska PRG oddziela wode (ok. 0-0,3 m) od ladu; utrata ladu przy linii
   brzegu ograniczona do pasa pikseli ponizej 5 m (pkt 6).
