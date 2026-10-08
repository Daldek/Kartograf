# Bugfix: reprojekcja tresci CZ szla przez serwer CUZK

Galaz `feature/etap1-cz-dmr`, 2026-08-11. Commity: `3c2cf44` (kod), `155c2b9` (docs).
Zgloszenie: `seam-report.md` (analiza szwu PL/CZ na Olzie)
(kopia: docs/research/2026-08-11-adr024-seam-report.md).

> **Errata (2026-08-22):** (a) liczba 1,25 m dotyczy wylacznie kafli kolo
> Cieszyna - pomiar na 302_5550 dal 4,92 m; blad serwerowej sciezki 3045 byl
> zmienny przestrzennie (docs/research/2026-08-11-adr024-verify-report.md
> sekcja 2, ADR-024 "Korekta liczby"); (b) Zastrzezenie 1 ("fix nie
> zweryfikowany na zywo") zostalo zamkniete - verify-report, punkty 1 i 4
> macierzy E2E: PASS (ADR-024 "Zywa weryfikacja fixu").

---

## 1. Diagnoza zakresu: czy sciezka godlowa TM33 (`imageSR=3045`) tez jest przesunieta?

**Odpowiedz: NIE tak samo — bledu datum (135 m) tam nie ma, ale jest wlasne,
systematyczne przesuniecie 1,25 m.**

### Metoda

Jak w seam-report, ale bez posrednictwa danych PL (referencja wewnetrzna):
dla tego samego obszaru pobrano (a) produkt serwerowy w ukladzie docelowym
i (b) dane **natywne 5514**, po czym (b) przeprobkowano bilinear w pozycjach
przesunietych o (dx, dy) przez przypieta operacje pyproj i szukano minimum
RMS roznic **wokol mediany** (odporne na offset pionowy). Kafle 2x2 km kolo
Cieszyna: `758_5514`, `760_5514` (TM33), pixel 2 m.

Ballpark liczony poprawnie: ten sam pipeline PROJ **z usunietymi krokami
datum** (`push/pop v_3`, `cart`, `molobadekas`) — czyli lat/lon Bessela
potraktowane jak ETRS89.

### Wyniki

| sciezka | RMS przy (0,0) | minimum RMS | przy (dx, dy) | ballpark wg pyproj |
|---|---|---|---|---|
| `imageSR=2180` (`--target-crs`, kontrola pozytywna) | **6,651 m** | 0,041 m | **(−119,0; −64,5)** | dE +118,80 / dN +64,40 (\|d\| **135,13 m**) |
| `imageSR=3045` (godlo TM33, kafel 1) | 0,129 m | 0,034 m | **(0; +1,25)** | dE +115,32 / dN +70,72 (\|d\| 135,28 m) |
| `imageSR=3045` (godlo TM33, kafel 2) | — | 0,034 m | **(0; +1,25)** | — |
| kontrola: natywny 5514 vs natywny 5514 (bbox przesuniety o 1 m) | — | 0,045 m | **(0; 0)** | — |

Odczyt:

- **2180 potwierdza seam-report co do metra** i waliduje metode: zmierzone
  przesuniecie (−119,0; −64,5) to dokladnie ballpark ze znakiem przeciwnym.
  Metoda **wykrywa** blad tej klasy, wiec wynik zerowy dla 3045 nie jest
  artefaktem nieczulosci.
- **3045: serwer datum STOSUJE** — przesuniecia 135 m nie ma (RMS w tej
  odleglosci ~7-8 m wobec 0,13 m w zerze).
- **3045 ma jednak wlasne +1,25 m** (tresc przesunieta na poludnie, 0,6 px):
  **powtorzone na dwoch niezaleznych kaflach**, przy samozgodnosci eksportow
  natywnych 0,045 m — czyli nie jest to faza mojej siatki ani szum. Zrodlo
  po stronie serwera, nieznane.

Dane i skrypty: `diag3045/{fetch,analyse,analyse2,control,mechanism}.py`,
`result2.json`, `control.json` (w /tmp, poza repo).

### Decyzja o zakresie

Objeto **obie** sciezki rastrowe. Uzasadnienie: 1,25 m to 0,6 piksela DMR 5G
(na stoku 20° daje 0,45 m bledu wysokosci — tyle, ile caly budzet roznic
zmierzony na szwie), a zasada wiazaca z zadania ("serwer dostaje zadania
wylacznie w 5514") i tak obejmuje kazdy uklad != natywny. Dwie rozne zasady
dla dwoch sciezek tego samego produktu byłyby trudniejsze do obrony niz
jedna. Skutek uboczny: znika cala klasa "cichej reprojekcji serwerowej".

---

## 2. Projekt naprawy (ADR-024)

**Serwer dostaje zadania rastrowe wylacznie w `EPSG:5514`; reprojekcje tresci
robi Kartograf lokalnie, wymuszona przypieta operacja.**

1. `CuzkDmrProvider._export_raster()` — jeden punkt wejscia dla obu sciezek
   (godlo TM33 i bbox). Gdy cel == natywny → eksport wprost. Gdy inny:
   obwiednia celu przeliczona do 5514 istniejacym `bbox_to_crs()` +
   `_WARP_MARGIN_PX = 4` px zapasu → `exportImage` w 5514 → lokalny warp.
2. `_warp_to_grid()` — `rasterio.warp.reproject`, bilinear, siatka wyniku
   liczona **identycznie jak w `CuzkClient.export_image`** (zasieg i rozmiar
   pliku nie zaleza od tego, czy byla reprojekcja), `src_nodata`/`dst_nodata`
   = −9999, zapis atomowy (tmp + `os.replace`), plik natywny sprzatany
   w `finally`.
3. **Wymuszenie operacji**: `PinnedTransform.gdal_operation()` →
   `COORDINATE_OPERATION` GDAL-a. Bez wymuszenia GDAL wybiera operacje sam,
   poza polityka `transform/crs.py` — zmierzona roznica wzgledem przypietej:
   srednio 0,08 m, maks. 1,9 m (czyli to nie jest teoretyczna troska).
4. **Sidecar**: `transform.horizontal = "pinned: <opis> (<acc> m)"`,
   symetrycznie do `transform.vertical`; pole pojawia sie takze dla kafla
   TM33 (dotad `transform: null`). `_write_cz_sidecar()` nie przyjmuje juz
   `server_crs` — pyta providera `horizontal_transform(<uklad wyniku>)`,
   wiec opisuje **te sama instancje** operacji, ktora wykonala prace.
5. **Fail-fast**: brak bezpiecznej operacji poziomej przerywa w konstruktorze
   providera (jak przy pionowej), przed transferem. Polityka
   `_HORIZONTAL_POLICY` = 1,0 m (ostrzejsza niz obwiedniowa 2 m — to jedyna
   operacja przesuwajaca piksele), bez siatek z CDN.

### Pulapka, ktora kosztowala najwiecej: kolejnosc osi

GDAL podaje operacji wspolrzedne w kolejnosci osi **autorytatywnej**, a
`PinnedTransform` powstaje z `always_xy=True` (E-N). Oba realne cele sa
northing-first (`EPSG:2180`: x=north, `EPSG:3045`: N-E), wiec goły pipeline
daje raster **w calosci nodata** — bez wyjatku, bez ostrzezenia. Dlatego
`gdal_operation()` dokleja `step proj=axisswap order=2,1` wyliczajac potrzebe
z `CRS.axis_info` (a nie zakladajac). Zweryfikowane empirycznie:

| wariant | 3045 (N-E) | 2180 (N-E) | 32633 (E-N) |
|---|---|---|---|
| goly pipeline `always_xy` | 0 pikseli | 0 pikseli | OK |
| + `axisswap` (wybrany) | OK, zgodny z pyproj (srednio 0,009 m, maks. 0,31 m) | OK (0,006 / 0,236 m) | n/d |
| `to_wkt()` operacji | 0 pikseli | 0 pikseli | — |
| bez `COORDINATE_OPERATION` | dziala, ale **inna operacja** (0,081 / 1,71 m) | (0,081 / 1,91 m) | — |

Odrzucona tez trzecia droga: wyszukanie autorytatywnej wersji operacji
w `TransformerGroup(always_xy=False)` — nie da sie dopasowac po opisie,
bo normalizacja dokleja "+ axis order change (2D)".

Reszta roznicy wzgledem wzorca pyproj (maks. 0,3 m na stromiznach, srednio
0,009 m) to efekt kernela bilinear GDAL i jego transformera aproksymacyjnego,
nie georeferencji.

### Rzeczy zachowane (wymogi zadania)

- nodata −9999 przez caly lancuch; **nie wchodzi do interpolacji** — GDAL
  maskuje zrodlo przy `src_nodata` (zweryfikowane pomiarem i testem: pole
  plaskie 300 m z polowa nodata daje wynik zlozony **wylacznie** z 300,0).
- atomowosc zapisu (tmp + `os.replace`), sprzatanie przy kazdym bledzie.
- kafelkowanie/mozaikowanie **przed** warpem, po stronie natywnej — inaczej
  interpolacja na krawedzi kafla (bez sasiadow z kafla obok) utrwalilaby szwy.
  Dodatkowo znika warunek "kafelkowanie wymaga bbox.crs == image_sr": teraz
  oba sa zawsze 5514.
- rozdzielczosc wyniku bez zmian (2 m / 5 m w ukladzie docelowym).
- sciezka SM5 (DMR 4G z openzu, pliki natywne 5514) nietknieta.

---

## 3. TDD — dowody RED/GREEN

**RED (na kodzie sprzed fixu)** — `red_evidence.py`, mock serwera oddajacy
raster "server-reprojected" z wbudowanym przesunieciem ballparku:

```
image_sr zadan do serwera: ['EPSG:2180']
oczekiwany wierzcholek (pyproj): 470818.8, 209181.9
wierzcholek w pliku wynikowym:  470937.4, 209245.3
BLAD: dE=118.6 m, dN=63.4 m, |d|=134.5 m
```

Stary kod przepuszczal wynik serwera bez zadnej kontroli. Test **tresci**
(nie bounds): pole to stozek `1000 − odleglosc od wierzcholka`, asercja
sprawdza, **gdzie wyladowal wierzcholek** (argmax) wzgledem wzorca pyproj,
tolerancja < 1 px (2 m).

**GREEN** — `tests/test_cuzk_dmr.py::TestHorizontalReprojection` (9 testow):

| test | co pilnuje |
|---|---|
| `test_bbox_target_crs_puts_content_where_pyproj_says` | regresja TRESCI (< 1 px od pyproj) — ten failowal z bledem 134,5 m |
| `test_server_is_asked_only_for_native_5514` | `imageSR` **i** `bbox.crs` zawsze 5514, niezaleznie od `--target-crs` |
| `test_tm33_godlo_also_goes_native_then_local_warp` | to samo dla sciezki godlowej + CRS/bounds/rozmiar wyniku |
| `test_native_request_covers_whole_target_bbox` | obwiednia natywna pokrywa cel (zapas na warp) |
| `test_nodata_does_not_bleed_into_interpolation` | pole plaskie + nodata → w wyniku wylacznie 300,0 i −9999 |
| `test_temporary_native_file_is_cleaned_up` | po pobraniu w katalogu jest **tylko** plik wynikowy |
| `test_failed_warp_leaves_no_output` | awaria warpu nie zostawia pliku (skip_existing nie utrwali korupcji) |
| `test_horizontal_transform_is_none_for_native` / `..._fails_before_download` | kontrakt `horizontal_transform()` + fail-fast przed transferem |

Plus `tests/test_transform_crs.py::TestGdalOperation` (5) — regula osi,
obecnosc kroku datum w operacji, para ukladow, blad bez niej. Oraz
`TestVerticalTransform::test_tm33_godlo_warps_then_shifts_vertically` —
skladanie obu transformacji.

**Zmiany w testach zastanych** (kodowaly stare zachowanie):
`test_tm33_godlo_exports_native_3045` → `..._requests_native_then_warps_to_3045`;
`test_target_crs_via_server_reprojection` → `..._produces_target_grid_from_native_request`;
`test_bbox_with_target_crs_records_server_transform` → `..._records_pinned_transform`.
Szesc testow z `TestVerticalTransform` uzywalo godla TM33 tylko jako sposobu
na raster na dysku — przeniesione na sciezke natywna (bbox 5514), bo ich
przedmiotem jest `_apply_vertical_shift`, a warp przeprobkowywal ich
syntetyczne fixtury; wspolgranie obu osi pokrywa nowy test wyzej.

**Zielone:** 1399 testow (+18), `ruff check` czysty, `ruff format --check`
czysty, `mypy` 33 bledy = baseline. Wszystko offline.

---

## 4. Pliki zmienione

| plik | zmiana |
|---|---|
| `kartograf/transform/crs.py` | `PinnedTransform.src_crs/dst_crs` + `gdal_operation()` (pipeline dla GDAL z korekta osi), `_is_northing_first()` |
| `kartograf/providers/cuzk/dmr.py` | `NATIVE_CRS`, `_HORIZONTAL_POLICY`, `_WARP_MARGIN_PX`, `horizontal_transform()`, `_export_raster()`, `_native_request_bbox()`, `_warp_to_grid()`, `_quiet_transformer_only_option()`; fail-fast w `__init__` |
| `kartograf/cli/download_cmd.py` | `_write_cz_sidecar()` bez `server_crs` — obie osie jako `"pinned: ... (acc)"` |
| `tests/test_cuzk_dmr.py` | `+TestHorizontalReprojection`, emulator serwera, aktualizacja testow zastanych |
| `tests/test_transform_crs.py` | `+TestGdalOperation` |
| `tests/test_cli.py` | mock providera dostal `horizontal_transform`; asercje sidecarow |
| `docs/DECISIONS.md` | **ADR-024** + ADR-023 pkt 1 oznaczony jako zastapiony |
| `docs/CHANGELOG.md` | Breaking (format `transform.horizontal`), Fixed (135 m / 1,25 m), Changed |
| `docs/research/2026-08-11-etap1-e2e.md` | adnotacja o luce E2E i nowym zachowaniu |
| `docs/PROGRESS.md`, `docs/SCOPE.md`, `CLAUDE.md` | sekcja "Fix po etapie 1", liczby, "serwerowa" → "lokalna" |

---

## 5. Zastrzezenia i rzeczy nierozstrzygniete

1. **Fix nie zostal zweryfikowany na zywych danych.** Zadanie dopuszczalo
   siec wylacznie w fazie diagnozy, wiec po zmianie kodu nie uruchamialem
   pobran. Dowody sa dwuczesciowe: pomiary z fazy 1 pokazuja, ze
   natywne+lokalny warp trafia w referencje w (0,0), a testy offline
   pokazuja, ze kod idzie dokladnie ta sciezka. **Rekomendacja przed
   mergem: powtorzyc punkty 1 i 4 macierzy E2E, tym razem z kontrola
   tresci** (adnotacja juz jest w dokumencie E2E).
2. **Zrodlo 1,25 m po stronie serwera pozostaje nieznane.** Wiemy, ze jest
   systematyczne i powtarzalne, ale nie, skad sie bierze; po naszej stronie
   przestaje miec znaczenie, bo tej sciezki juz nie uzywamy.
3. **Obwiednia zadania a warp uzywaja dwoch roznych przypietych operacji**
   (`_ENVELOPE_POLICY` 2 m vs `_HORIZONTAL_POLICY` 1 m, do tego w
   przeciwnych kierunkach). To celowe — obwiednia ma tylko *pokryc* obszar,
   a margines 4 px z zapasem przykrywa rozjazd ≤ 2 m. Warto o tym pamietac,
   gdyby ktos kiedys zmniejszyl margines.
4. **Cache `_transforms` jest kluczowany para ukladow, bez polityki.**
   Pierwsze zadanie wygrywa. Dzis nieszkodliwe (jedna polityka na pare
   w calym przeplywie), ale to cichy assumption.
5. **`_quiet_transformer_only_option()`** wycisza jeden komunikat GDAL
   (`COORDINATE_OPERATION` to opcja transformera, a rasterio podaje kwargs
   takze warperowi). Filtr dopasowuje po nazwie opcji i jest zdejmowany
   natychmiast, ale to jednak tlumienie logu biblioteki — gdyby GDAL
   zmienil tresc komunikatu, filtr po cichu przestanie dzialac (skutek:
   wraca szum na stderr, nie utrata bledu).
6. **Nie sprawdzalem zuzycia pamieci na duzym bboxie.** Warp idzie
   strumieniowo band→band (bez pelnej tablicy w Pythonie), ale
   `mosaic_and_crop` przed nim laduje mozaike do pamieci — to stan sprzed
   fixu, tyle ze teraz mozaika bywa nieco wieksza (obwiednia z marginesem).

---

# Runda naprawcza po review (2026-08-11)

Commit: `71b7b4e`. Testy: **1402** (+3), ruff/format czyste, mypy 33 = baseline.

## FINDING 1 (Important) — wymuszenie operacji bez zadnego testu: **POTWIERDZONE, naprawione**

Zweryfikowalem pomiar reviewera wprost: usunalem
`COORDINATE_OPERATION=pinned.gdal_operation()` z `_warp_to_grid()` i uruchomilem
suite CZ — **45 testow zielonych, zero faili**. Test tresci z definicji tego nie
zlapie: bez wymuszenia GDAL wybiera wlasna operacje, ktora trafia ~1,0 m od
wzorca pyproj, czyli wewnatrz tolerancji 1 px (2 m). `TestGdalOperation`
sprawdzalo tylko postac stringa, nigdy jego uzycia. Jedyna gwarancja
ADR-024(b) byla bezbronna.

**Naprawa:** `test_warp_forces_the_pinned_operation`, parametryzowany na obie
sciezki (`bbox` → 2180, `godlo` TM33 → 3045). Patch `wraps=real_reproject`
(warp nadal wykonuje sie naprawde), asercja
`warp.call_args.kwargs["COORDINATE_OPERATION"] == _pinned_5514_to(crs).gdal_operation()`
plus sanity `"molobadekas" in expected` (obecnosc kroku datum — jego brak to
wlasnie zmierzony blad 135 m).

**Dowod dzialania:** z usunietym parametrem oba warianty failuja
(`KeyError: 'COORDINATE_OPERATION'`), z parametrem — przechodza.

## FINDING 2 (Important) — traceback na sciezce godlowej: **NIE POTWIERDZONE**

Zweryfikowalem empirycznie na pelnym przeplywie CLI (`verify_f2.py`:
`main(["download","302_5550","--country","cz",...])` z
`build_pinned_transform` rzucajacym `TransformUnavailableError`):

```
Error: brak operacji EPSG:5514->EPSG:3045 Remedium: zainstaluj siatki
exit code: 1
```

Zadnego tracebacku. Powod: godlo CZ idzie przez `_run_cz()`
(`cmd_download` → `download_cmd.py:524`), ktore lapie `TransformError` dla
**calego** przeplywu CZ i drukuje przez `_print_transform_error()`. Format
komunikatu jest znakowo identyczny z handlerem konstruktora w
`_cmd_download_cz` (`f"Error: {e}"` + `" Remedium: …"`), wiec nie ma tez
roznicy w UX miedzy sciezka godlowa a bboxowa.

**Czego wiec NIE zrobilem:** nie dodalem `TransformError` do `except`
w `_cz_download_godlo`. Ten handler przechwytywalby wyjatek przed
istniejacym, produkujac **identyczny** komunikat — czyli byloby to
duplikowanie dzialajacej gwarancji, a przy okazji uczynienie zewnetrznego
handlera martwym dla tej sciezki. Jesli kontroler chce jednak lokalnego
handlera jako defense-in-depth, to swiadoma decyzja stylistyczna, nie
naprawa bledu — prosze o jawna instrukcje.

**Co w tym znalezisku bylo realne i zostalo naprawione:**

1. **Brak testu.** Ochrona lezy w `_run_cz`, czyli daleko od miejsca
   rzucenia (`_export_raster`), i nikt jej nie pilnowal — dokladnie taka
   konfiguracja psuje sie po cichu przy refaktorze. Dodalem
   `test_godlo_without_safe_horizontal_operation_exits_cleanly` na pelnym
   `main()`: kod 1, komunikat z para ukladow, `"Remedium:"`, brak
   `"Traceback"`, zero plikow na dysku. **Zweryfikowany jako skuteczny**:
   po usunieciu `except TransformError` z `_run_cz` test failuje.
2. **Blad w ADR-024(f).** Zdanie "przerywa w konstruktorze providera" bylo
   prawdziwe tylko dla `--target-crs`. Rozpisalem punkt na dwa przypadki
   (cel znany przy konstrukcji vs. cel wynikajacy z godla → operacja
   budowana w `_export_raster`, przed pierwszym HTTP, wyjatek lapany
   w `_run_cz`) i dopisalem odnosnik do testu. Dodalem tez punkt (g)
   o koniecznosci osobnego testu wymuszenia (FINDING 1).

## Pakiet tekstowy (sankcjonowany)

| # | miejsce | zmiana |
|---|---|---|
| a | `cli/_parser.py` (`--help` komendy + `--target-crs`) | "wycinek serwerowy" → "wycinek (exportImage w ukladzie natywnym EPSG:5514)"; "Reprojekcja serwerowa wyniku" → "Reprojekcja wyniku, wykonywana lokalnie przypieta operacja". Zweryfikowane na zywym `kartograf download --help` |
| b | `transform/crs.py` KNOWN_PATHS 5514→2180 | "preferowac reprojekcje serwerowa CUZK" → "reprojekcja tresci LOKALNA — serwerowej CUZK nie uzywamy, gubi datum shift (ADR-024)" |
| c | `dmr.py::download()`, `download_cmd.py` (`_cz_download_bbox`, `_cmd_download_cz`) | docstringi opisuja stan po fixie: kafel TM33 = siatka 3045 + zadanie natywne + lokalny warp; SM5 bez warpu; "wycinek serwerowy" → "wycinek `exportImage`" |
| d | `dmr.py` komentarz `_ENVELOPE_POLICY`/`_LONLAT_POLICY` | usuniete nieaktualne uzasadnienie "bbox zadania i tak reprojektuje serwer"; wpisane realne sprzezenie: obwiednia ma tylko POKRYC cel, a rozjazd ≤ 2 m miesci sie w `_WARP_MARGIN_PX` — **ze zdaniem, co trzeba zrobic, gdyby ktos zmniejszyl ten zapas** |
| e | ADR-024 "Konsekwencje" | "zasieg i rozmiar identyczne jak dotad" → rozmiar w pikselach identyczny, zasieg przyklejony do wielokrotnosci `pixel_size` (`round()` na liczbie pikseli), roznica od zadania **≤ ½ piksela** na krawedzi |

Nietkniete zgodnie z instrukcja: minory 9 (galaz src-swap/southing), 10 (filtr
logu), 11 (datowane migawki spec/plan).

## Zastrzezenia po tej rundzie

1. **Zastrzezenie nr 1 z pierwszej rundy nadal aktualne** — fix nie byl
   uruchomiony na zywych danych (siec tylko w fazie diagnozy). Rekomendacja
   powtorzenia punktow 1 i 4 macierzy E2E z kontrola tresci pozostaje.
2. `test_warp_forces_the_pinned_operation` przypina **string** operacji do
   wyniku `gdal_operation()`. Gdyby ktos zepsul samo `gdal_operation()`
   (np. usunal `axisswap`), ten test nadal przejdzie — chroni go osobno
   `TestGdalOperation` (postac) i testy tresci (skutek). Trzy warstwy sa
   rozlaczne i zadna nie zastepuje pozostalych; warto o tym pamietac przy
   ewentualnym "porzadkowaniu" testow.
3. FINDING 2 zostawiony bez zmiany kodu — jesli kontroler podtrzymuje
   zadanie lokalnego `except`, to jedna linia plus import, ale wtedy warto
   swiadomie zdecydowac, ktory handler ma byc martwy.
