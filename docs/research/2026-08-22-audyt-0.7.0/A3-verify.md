# A3-verify — weryfikacja ustalen [Critical]/[Important] z A3-report.md

Weryfikator: V3 (sceptyk). Obszar: `kartograf/providers/cuzk/*`, `kartograf/cli/*`.
Metoda: lektura pelnych plikow + samodzielna reprodukcja offline. Zaden plik repo nie zostal
zmieniony; wszystkie skrypty leza w scratchpadzie sesji
(`/tmp/claude-1001/.../scratchpad/v3_*.py`). Zero polaczen z siecia (`PROJ_NETWORK=OFF`
tam, gdzie budowana byla operacja pionowa). Baseline przed weryfikacja:
`pytest tests/test_cli.py tests/test_cuzk_client.py tests/test_cuzk_dmr.py tests/test_transport_mosaic.py`
= **287 passed** (5,5 s).

Ustalenia [Minor] (A3-6..A3-13) pominiete zgodnie z formatem.

---

### A3-1 — Kafelkowanie exportImage gubi dolny wiersz danych (pas `-9999`) i przesuwa zasieg
- Werdykt: **CONFIRMED** (skutek POWAZNIEJSZY niz w raporcie — patrz Uzasadnienie)
- Reprodukcja: `v3_a31.py` — realne `CuzkClient.export_image` + realne `_tile_grid`
  + realne `mosaic_and_crop`; podmieniony wylacznie "serwer" (`_export_single` generuje
  GeoTIFF dla ZADANEGO bboxa/rozmiaru, wartosc piksela = f(x,y) znana analitycznie)
  i limity `MAX_EXPORT_*`. Bbox 500 x 181,4 m przy 2 m (wysokosc 90,7 px -> `round` = 91):
  ```
  frac_tiled : kafli=3 ksztalt=(91,250) bounds_dol=-1100000.6 nodata=250 px, cale_wiersze=[90]
               wartosci zgodne z f(x,y): 7250 / niezgodne: 15250
  frac_single: kafli=1 ksztalt=(91,250) bounds_dol=-1100000.0 nodata=0    cale_wiersze=[]
               wartosci zgodne z f(x,y): 22750 / niezgodne: 0
  exact_tiled: (bbox = dokladna wielokrotnosc piksela, jak test w repo) nodata=0, niezgodne=0
  ```
  Pomiar bledu w METRACH (`v3_a31c.py`, wartosc piksela = jego northing):
  ```
  tiled : bounds=(-1100000.6,-1099818.6) nodata_wierszy=1 blad geolokalizacji tresci: -1,400 .. +0,600 m
  single: bounds=(-1100000.0,-1099818.6) nodata_wierszy=0 blad geolokalizacji tresci:  0,000 m
  ```
  Zamiatanie (`v3_a31b.py`, wysokosci 180,1..181,9 m): caly wiersz `-9999` pojawia sie
  w 7 z 19 przypadkow, a dolna krawedz rozjezdza sie z zadaniem w **19 z 19**.
- Uzasadnienie: `_tile_grid` (`client.py:270-275`) kotwiczy kafle w narozniku **SW**
  (`bbox.min_y + off*pixel_size`), a `rasterio.merge` wywolane z `bounds=` kotwiczy siatke
  wyniku w narozniku **NW** (`Affine.translation(dst_w, dst_n)`), przy wysokosci
  `round((max_y-min_y)/res)`. Gdy wysokosc nie jest calkowita wielokrotnoscia piksela, oba
  rastry sa przesuniete wzgledem siebie o `delta = h_px*res - (max_y-min_y)` (0 < delta < res).
  Skutki: (1) dolny wiersz wyniku lezy pod zasiegiem kafli => caly wiersz `-9999` mimo danych
  z serwera; (2) zasieg pliku rozni sie od zadanego; (3) **czego raport nie zmierzyl**: `merge`
  przenosi bloki pikseli bez resamplingu, wiec TRESC jest przesunieta pasami o maks. 1 piksel
  (zmierzone -1,4 .. +0,6 m przy 2 m) — czyli ten sam rzad bledu, dla ktorego ADR-024 zakazal
  reprojekcji serwerowej (1,25 m), i tak samo niewidoczny w metadanych. Test
  `test_tiling_above_limits_mosaics` (`tests/test_cuzk_client.py:400`) uzywa bboxa 16x16 m przy
  2 m — dokladnej wielokrotnosci piksela — i wypelnia kazdy kafel STALA wartoscia, wiec nie
  wykrylby ani wiersza nodata, ani przesuniecia tresci. E2E (`docs/research/2026-08-11-etap1-e2e.md`)
  tez nie moglo tego pokazac: najwiekszy raster CZ w E2E to 2789x1821 px (krok 4), a kafelkowanie
  wlacza sie dopiero powyzej 4100 px wysokosci — **zaden krok E2E ani weryfikacji ADR-024 nie
  dotknal sciezki kafelkowanej** (grep "kafel/mozaik/4100" w obu raportach: brak).
  Sciezka jest realna dla zadan zlewniowych (bbox wyzszy niz 8,2 km przy DMR 5G) i dotyczy tez
  trybu `--target-crs` (obwiednia natywna z `_native_request_bbox` ma z natury ulamkowa wysokosc,
  a przesuniecie tresci wchodzi do warpu).
- Naprawa przed wydaniem 0.7.0: **TAK**
- Zakres naprawy: `kartograf/providers/cuzk/client.py` — `_tile_grid` kotwiczyc w NW
  (`bbox.max_y - (row_off+row_px)*pixel_size` .. `bbox.max_y - row_off*pixel_size`), spojnie
  z `merge`/`_warp_to_grid` (`from_origin(min_x, max_y, ...)`), + poprawka docstringa
  ("S->N" staje sie "N->S"). Zweryfikowane `v3_a31fix.py`: dla 20 wysokosci 180,0..181,9 m
  wariant NW daje 0 wierszy nodata i 0,000 m bledu geolokalizacji (obecny: 7 przypadkow
  z nodata, do 1,4 m bledu); rozmiary wynikow bez zmian. Test przypinajacy: nowy przypadek
  w `tests/test_cuzk_client.py` obok `test_tiling_above_limits_mosaics` — bbox o ulamkowej
  wysokosci (np. 500 x 181,4 m przy 2 m), kafle z wartoscia zalezna od wiersza; asercje:
  brak wiersza `nodata`, `bounds` == zasieg kafli, wartosc piksela zgodna z transformem wyniku.
  Rozmiar: **S** (~6 linii produkcyjnych). Ryzyko regresji: **niskie** (zmienia sie tylko
  kolejnosc i kotwica kafli; istniejace testy uzywaja wielokrotnosci piksela i przechodza).

---

### A3-2 — `--country auto` uruchamia galaz PL dla bboxow w glebi Czech i konczy zadanie kodem 1
- Werdykt: **CONFIRMED** (czesc "zapytanie idzie takze do PL" to DESIGN-DECISION; kod wyjscia 1 — nie)
- Reprodukcja: `v3_a32.py` (CLI przez `main()`, wzor `TestAutoSplit*`; `_cmd_download_cz`
  zamockowane na 0, `DownloadManager.download_sheet` rzuca `DownloadError("No NMT 1m data
  available for ...")` jak `providers/pl/gugik.py`):
  ```
  Praga   kraje=('CZ','PL')    Brno kraje=('CZ','PL')    Ostrawa kraje=('CZ','PL')
  Pilzno  kraje=('CZ',)        # jedyny sprawdzony punkt na zachod od 14,07 E
  Praga -> galaz PL wyznacza 9 arkuszy GUGiK: ['M-33-65-D-b-3-3', 'M-33-65-D-b-3-4', ...]
  RC calego polecenia = 1  (CZ zwrocilo 0, prob GUGiK = 9)
  ```
- Uzasadnienie: `CountryProfile` PL to prostokat `BBox(14.07, 49.00, 24.20, 54.90)`
  (`sources/registry.py:310`), ktory pokrywa niemal cale Czechy na wschod od Pilzna, wiec
  `_countries_for_bbox` zwraca `('CZ','PL')` w Pradze, Brnie i Ostrawie. Sam fakt odpytania obu
  krajow jest **swiadomy** (docstring `_countries_for_bbox`: "auto-split zada wtedy obu zrodel,
  a nie zgaduje granicy"; ADR-023 "Ustalenia dodatkowe" pkt 4; wielokat granicy zaplanowany na
  etap 2). Niedokumentowana i asymetryczna jest **konsekwencja**: ADR-023 pkt 4 opisuje wylacznie
  kierunek PL->CUZK i zapewnia, ze skutkiem jest "dodatkowy raster wypelniony nodata (...), **a nie
  blad**"; kierunek CZ->GUGiK konczy sie twardym `DownloadError`, a `max(exit_codes)`
  (`cli/download_cmd.py:422`) zamienia poprawnie pobrany raster CZ w kod 1 calego polecenia
  (plus 9-16 zbednych zapytan do GUGiK). Dotyczy to trybu DOMYSLNEGO (`--country auto`) na
  wiekszosci terytorium CZ, czyli glownej nowosci wydania 0.7.0; obejscie (`--country cz`)
  nie jest nigdzie opisane jako konieczne. `parent_request.countries` = kraje PROBOWANE
  (ADR-023 pkt 3), wiec sidecar CZ i tak niesie oba kody — semantyka "czesciowego sukcesu"
  jest juz w modelu danych, brakuje jej tylko w kodzie wyjscia.
- Naprawa przed wydaniem 0.7.0: **TAK**
- Zakres naprawy: `kartograf/cli/download_cmd.py` (`_dispatch_area`, l. 404-422) — w trybie
  `auto` z >1 krajem: gdy co najmniej jeden kraj zwrocil 0, wypisac ostrzezenie na stderr
  ("brak danych w <kraj> dla tego obszaru — pobrano <kraj2>") i zwrocic 0; `max(exit_codes)`
  zostaje dla jawnego `--country` i dla przypadku, w ktorym padly wszystkie kraje.
  Dodatkowo jedno zdanie w ADR-023 pkt 4 i w CLAUDE.md (akapit CZ) o symetrii prostokata PL.
  Test przypinajacy: nowy przypadek w `TestAutoSplitBBox` (bbox praski, `_cmd_download_cz`->0,
  `DownloadManager` rzuca `DownloadError`) => `result == 0` + komunikat na stderr; zaden
  istniejacy test nie przypina dzis semantyki "jeden kraj padl" (sprawdzone: w `TestAutoSplit*`
  wszystkie asercje to `result == 0` lub bledy walidacji przed pobraniem).
  Rozmiar: **S** (~10 linii). Ryzyko regresji: **srednie** (zmiana semantyki kodu wyjscia
  w trybie auto — maskuje realna awarie PL na pasie przygranicznym; dlatego ostrzezenie na
  stderr jest czescia naprawy, a nie dodatkiem).

---

### A3-3 — Uszkodzony kafel w sciezce kafelkowanej ucieka jako `RasterioIOError`
- Werdykt: **CONFIRMED**
- Reprodukcja: `v3_a33.py` (poziom klienta) i `v3_a33cli.py` (pelne `main()`), mock
  `download_to` zapisuje 2. kafel jako `b"II*\x00" + 64 zera` (magic poprawny, cialo urwane):
  ```
  kafelkowany   : !!! NIEMAPOWANY rasterio.errors.RasterioIOError: Cannot open TIFF image
  jednokafelkowy: DownloadError (mapowany) -> "exportImage: nie udalo sie nadpisac CRS ..."
  CLI: WYJATEK UCIEKL Z main(): rasterio.errors.RasterioIOError: Cannot open TIFF image
  ```
  W obu przypadkach pliki czastkowe sa posprzatane, a wynik nie powstaje.
- Uzasadnienie: `_export_single` waliduje tylko 4 bajty magic, a w sciezce kafelkowanej
  `mosaic_and_crop` otwiera kafle (`transport/mosaic.py:31`) PRZED `_overwrite_crs` — jedynym
  miejscem mapujacym wyjatki rasterio na `DownloadError`. `_cz_download_bbox` lapie
  `(DownloadError, ValidationError)`, `_run_cz` dodatkowo `ParseError`/`TransformError`,
  `main` nie lapie nic — wiec uzytkownik dostaje traceback zamiast komunikatu i kodu 1.
  Ta sama klasa awarii jest juz swiadomie obsluzona na sciezce SM5 (`dmr.py:559-578`
  `_assign_crs` z testem `test_sm5_corrupted_tiff_raises_download_error_and_cleans_up`),
  wiec to niespojnosc we wlasnym wzorcu, nie nowa polityka.
- Naprawa przed wydaniem 0.7.0: **TAK**
- Zakres naprawy: `kartograf/providers/cuzk/client.py` — opakowac `mosaic_and_crop(...)`
  w `export_image` w `try/except Exception` -> `DownloadError` (z `output_path.unlink(missing_ok=True)`),
  dokladnie jak `_overwrite_crs`; `ValidationError` z `mosaic_and_crop` (niezgodne CRS/res)
  przepuszczac bez zmiany. Test przypinajacy: kopia
  `test_sm5_corrupted_tiff_raises_download_error_and_cleans_up` dla sciezki kafelkowanej
  (limity `MAX_EXPORT_*` patchowane, 2. kafel urwany) => `pytest.raises(DownloadError)`
  + brak plikow `*.part*`. Rozmiar: **S** (~8 linii). Ryzyko regresji: **niskie**.

---

### A3-4 — Mozaika CZ trzyma caly wynik w RAM (brak limitu rozmiaru zadania)
- Werdykt: **CONFIRMED**
- Reprodukcja: `v3_a34.py` / `v3_a34big.py` (`tracemalloc` na realnym `mosaic_and_crop`,
  2 kafle -> jeden wynik):
  ```
  wynik 4000x4000 px ( 64 MB danych): szczyt 168,0 MB (2,63x)
  wynik 8000x8000 px (256 MB danych): szczyt 672,0 MB (2,63x)   <- obecny kod
  wynik 8000x8000 px, merge(dst_path=...): szczyt 272,0 MB (1,06x), wynik IDENTYCZNY
      (bounds, shape, nodata, wszystkie piksele)
  ```
- Uzasadnienie: `rasterio/merge.py:383-406` dzieli prace na kawalki (`subdivide`) **wylacznie**
  w galezi `if dst_path is not None`; bez `dst_path` `chunks = [dout_window]`, czyli jedna
  tablica na caly wynik (plus kopie w trakcie zapisu — zmierzone 2,63x). CLI CZ nie ma zadnego
  progu rozmiaru bboxa, a mnoznik jest liniowy: realistyczne zlewniowe zadanie 30x30 km przy
  DMR 5G (15000x15000 px = 900 MB danych) daje ~2,4 GB szczytu, 40x40 km ~4,2 GB. PL nie ma tego
  problemu, bo `--bbox` rozklada sie na osobne arkusze OpenData. Skala jest realna wlasnie na
  sciezce kafelkowanej (wlacza sie od 8,2 km wysokosci), wiec to nie jest przypadek skrajny.
- Naprawa przed wydaniem 0.7.0: **TAK**
- Zakres naprawy: `kartograf/transport/mosaic.py` — przekazac `dst_path=output_path` do `merge`
  (z `output_path.parent.mkdir(...)` PRZED wywolaniem, bo `merge` sam otwiera plik do zapisu);
  walidacje CRS/res zostawic bez zmian, `merge` z `dst_path` zwraca `None`, wiec znika reczne
  budowanie `profile`/`dst.write`. Rownowaznosc wyniku zweryfikowana bit-w-bit (wyzej).
  Test przypinajacy: istniejace `tests/test_transport_mosaic.py` (4 testy przechodza bez zmian —
  sprawdzone przez porownanie wynikow) + opcjonalnie asercja na `merge` wolane z `dst_path`.
  Rozmiar: **S** (~10 linii). Ryzyko regresji: **niskie/srednie** (`mosaic_and_crop` to helper
  generyczny "na przyszlych konsumentow" — po zmianie profil wyjscia pochodzi z `first_profile`
  wewnatrz `merge`, a nie z reczna kopia `sources[0].profile`; w przetestowanym scenariuszu
  wynik jest identyczny, ale warto uruchomic caly zestaw testow transportu).

---

### A3-5 — Transformacja pionowa arkusza SM5 gubi parowanie `.tif`/`.tfw`
- Werdykt: **DOWNGRADE(Minor)** — mechanizm potwierdzony co do liczby, ale dzis niewyzwalany
- Reprodukcja: `v3_a35.py` (mechanizm) i `v3_a35b.py` (skutek liczbowy, realna operacja
  `Baltic 1957 height to EVRF2007 height (1)`, `PROJ_NETWORK=OFF`). Dwa identyczne pliki
  5x4 px z `.tfw` o zasiegu CTES96, jedyna roznica to obecnosc CRS w samym TIFF-ie:
  ```
  .tfw obok kopii tymczasowej istnieje? False (szukany: X.tif.999_1.vshift.tfw)
  bez_crs (dzisiejszy ksztalt openzu): KOPIA transform=(500,0,-450000,0,-500,-1112000) -> OK
  z_crs   (hipotetyczny):              KOPIA transform=(1,0,0,0,1,0) -> srodek (0,0) = 0.5, 0.5
  po _apply_vertical_shift: bez_crs 300.12769 (+0,12769 m, poprawne)
                            z_crs   300.26794 (+0,26794 m, blad ~0,14 m, bez ostrzezenia)
  ```
- Uzasadnienie: odpowiedz na pytanie z briefu — wynik SM5 **nie** jest GeoTIFF-em z wbudowanym
  georeferencingiem; z openzu przychodzi para TIFF + `.tfw` (`_extract_zip_pair`,
  `tests/test_cuzk_dmr.py:67` "GeoTIFF bez CRS i bez geotransformacji"), a kopia tymczasowa
  `_apply_vertical_shift` (`dmr.py:378`) dostaje nazwe `X.tif.<pid>_<tid>.vshift.tif`, do ktorej
  `.tfw` juz nie pasuje. Dzis dziala tylko przez efekt uboczny: `_assign_crs` otwiera plik w `r+`
  i zapisujac CRS utrwala w TIFF-ie takze geotransformacje wczytana z `.tfw` (zmierzone wyzej).
  Gdy `_assign_crs` nic nie zapisze (`if ds.crs is None` — plik juz z CRS), kopia ma macierz
  jednostkowa, a `_shift_in_place` sprawdza tylko `ds.crs is None`, wiec liczy `(lon, lat)`
  z numerow pikseli i przesuwa wysokosci CICHO o zly offset. Znalazlem druga, ta sama klasa
  wyzwolenia: ZIP bez `.tfw` jest przez `_extract_zip_pair` **tolerowany** (`has_tfw = False`),
  co daje plik bez zadnej geotransformacji i identyczny cichy blad. Obie sciezki zaleza od
  ksztaltu plikow serwera (rekonesans mowi: TIFF bez CRS + `.tfw`), wiec przy dzisiejszych
  danych CUZK ustalenie jest **nieaktywne** — stad Minor, a nie Important; impakt (cichy blad
  pionowy) pozostaje wysoki, jesli CUZK zmieni ksztalt pliku.
- Naprawa przed wydaniem 0.7.0: **TAK** (tanie utwardzenie, nie blocker)
- Zakres naprawy: `kartograf/providers/cuzk/dmr.py` — (a) w `_shift_in_place` dolozyc obok
  guardu `ds.crs is None` warunek na brak geotransformacji
  (`ds.transform.is_identity` / `not ds.transform.is_rectilinear`) -> `ValidationError`
  z ta sama trescia (glosna awaria zamiast cichego przesuniecia); opcjonalnie (b) skopiowac
  `.tfw` obok kopii tymczasowej albo wpisac `transform`/`crs` jawnie w profil kopii.
  Test przypinajacy: nowy test obok `_write_dmr4g_pair` — plik z CRS ale bez geotransformacji
  + `.tfw`, `--vertical-crs EVRF2007` => `pytest.raises(ValidationError)` zamiast cichej wartosci
  300,268. Rozmiar: **S** (~5 linii). Ryzyko regresji: **niskie** (guard nie odpala dla
  dzisiejszego ksztaltu plikow — potwierdzone przebiegiem `bez_crs`).

---

## Tabela
| ID | Werdykt | Naprawa 0.7.0 | Rozmiar | Ryzyko |
|----|---------|---------------|---------|--------|
| A3-1 | CONFIRMED (skutek powazniejszy: przesuniecie tresci do 1,4 m) | TAK | S | niskie |
| A3-2 | CONFIRMED (odpytanie PL = DESIGN-DECISION/ADR-023 pkt 4; kod wyjscia 1 = blad) | TAK | S | srednie |
| A3-3 | CONFIRMED | TAK | S | niskie |
| A3-4 | CONFIRMED | TAK | S | niskie/srednie |
| A3-5 | DOWNGRADE(Minor) | TAK (utwardzenie) | S | niskie |

## Nowe ustalenia przy okazji (max 3, tylko jesli Critical/Important i z dowodem)
1. **[Critical — ten sam korzen i ta sama naprawa co A3-1, ale inny skutek niz opisany]
   Sciezka kafelkowana przesuwa TRESC rastra pasami o maks. 1 piksel, nie tylko gubi wiersz.**
   `merge` przenosi bloki pikseli bez resamplingu, wiec przy rozjezdzie siatek kazdy kafel jest
   "zatrzaskiwany" osobno. Pomiar (`v3_a31c.py`, wartosc piksela = jego northing, bbox
   500 x 181,4 m @ 2 m): blad geolokalizacji tresci **-1,400 .. +0,600 m** na sciezce
   kafelkowanej wobec **0,000 m** na jednokafelkowej. To ten sam rzad wielkosci, dla ktorego
   ADR-024 zakazal reprojekcji serwerowej (1,25 m), i tak samo niewidoczny w metadanych pliku —
   argument, by A3-1 traktowac jako blokujacy wydanie, a nie kosmetyczny.
2. **[Important] Ani E2E, ani weryfikacja ADR-024 nigdy nie dotknely sciezki kafelkowanej.**
   Najwiekszy raster CZ w `docs/research/2026-08-11-etap1-e2e.md` to 2789x1821 px (krok 4),
   a w `docs/research/2026-08-11-adr024-verify-report.md` 2089x2981 px — kafelkowanie wlacza sie
   dopiero powyzej 4100 px wysokosci. Grep "kafel|mozaik|4100|15000" w obu raportach nie
   zwraca ani jednego pomiaru mozaiki. Wniosek: "E2E 11/11 PASS na zywych danych" nie jest
   dowodem poprawnosci trybu `--bbox` dla obszarow wiekszych niz ~8x30 km; przed 0.7.0 warto
   dolozyc jeden krok E2E z bboxem wymuszajacym kafelkowanie (albo przynajmniej test
   jednostkowy z ulamkowa wysokoscia, patrz A3-1).
