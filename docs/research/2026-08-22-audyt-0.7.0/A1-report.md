# A1 — poprawnosc logiczna core / transform / transport / sources

Zakres: przeczytane w calosci: `kartograf/core/sheet_parser.py`, `kartograf/core/parser_2000.py`,
`kartograf/core/parser_tm33.py`, `kartograf/core/parser_registry.py`, `kartograf/core/geometry.py`,
`kartograf/core/__init__.py`, `kartograf/transform/crs.py`, `kartograf/transform/__init__.py`,
`kartograf/transport/http.py`, `kartograf/transport/mosaic.py`, `kartograf/transport/__init__.py`,
`kartograf/sources/descriptor.py`, `kartograf/sources/registry.py`, `kartograf/sources/sidecar.py`,
`kartograf/sources/__init__.py`, `kartograf/exceptions.py`, `kartograf/__init__.py`.
Dodatkowo (fragmenty, do weryfikacji spojnosci deskryptor<->provider): `download/manager.py`,
`download/storage.py`, `cli/download_cmd.py`, `cli/parse_cmd.py`, `providers/pl/gugik.py`,
`providers/cuzk/dmr.py`, `providers/cuzk/client.py`, `docs/DECISIONS.md` (ADR-022/023/024),
`docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md` (sekcje 6.3/6.4), README/PRD/CLAUDE.md.

Metoda: pelne czytanie plikow + grep konsumentow (`server_reprojection`, `probe_point`,
`get_parent/get_children/get_all_descendants`, `_SHEET_DIMENSIONS`, `FileStorage(`, `build_metadata(`),
snippety weryfikacyjne w `.venv/bin/python -c`, uruchomienia CLI (`kartograf parse`, `kartograf download`)
na zywych danych GUGiK/CUZK (siec dostepna), `projsync` do odtworzenia srodowiska z siatkami PROJ
(pliki wylacznie w scratchpadzie), `pytest tests/test_sheet_parser.py tests/test_parser_2000.py
tests/test_parser_tm33.py tests/test_parser_registry.py tests/test_geometry.py tests/test_transform_crs.py
tests/test_transport_http.py tests/test_transport_mosaic.py tests/test_sources_registry.py
tests/test_sidecar.py -q -p no:cacheprovider` (436 passed — zadne z ponizszych ustalen nie jest
pokryte testem, ustalenie A1-1 jest przez testy utrwalone jako "poprawne").

Nie sprawdzono: logiki wewnetrznej providerow PL/CZ i landcover (zakres A2/A3) poza punktami stykowymi
z deskryptorami; `cache/metadata.py`, `hydrology/`, `auth/`; poprawnosci wzoru PL-2000 wobec zrodla
zewnetrznego (sprawdzona tylko spojnosc wewnetrzna i to, ze arkusze wypadaja w zakresie dlugosci swojej
strefy); wydajnosci.

## Ustalenia

### A1-1 [Critical] Bledne mapowanie 1:200k <-> 1:500k — `get_parent()`/`get_children()` wskazuja polowe arkuszy w zlym miejscu
- Plik: `kartograf/core/sheet_parser.py:391` (`_get_parent_from_200k`) i `:455` (`_get_children_from_500k`)
- Twierdzenie: przynaleznosc arkusza z siatki 12x12 (numery 1-144) do cwiartki A-D liczona jest jako
  `(nr-1)//36` (pasami po 3 wiersze), a nie z pozycji w siatce (wiersz/kolumna) — dla 72 ze 144 arkuszy
  rodzic i dzieci sa geometrycznie sprzeczne z `get_bbox()`.
- Dowod:
  ```python
  section_idx = (arkusz_num - 1) // 36            # sheet_parser.py:391
  section_letter = ["A", "B", "C", "D"][section_idx]
  ```
  Wejscie -> zle wyjscie (uruchomione):
  `SheetParser('N-34-7').get_bbox('EPSG:4326')` = lon 21.0..21.5 (czyli wnetrze `N-34-B`, lon 21..24),
  ale `SheetParser('N-34-7').get_parent().godlo` = `'N-34-A'` (lon 18..21).
  Odwrotnie `N-34-61` (lon 18.0..18.5, czyli `N-34-A`) dostaje rodzica `N-34-B`.
  `SheetParser('N-34-A').get_all_descendants('1:10000')` zwraca 9216 arkuszy, ktorych suma obwiedni to
  **lon 18..24, lat 55..56**, podczas gdy `N-34-A` to **lon 18..21, lat 54..56** — polowa wyniku lezy poza
  rodzicem, polowa obszaru rodzica nie jest pokryta.
- Weryfikacja: snippet w `.venv/bin/python` (bboxy i sumy obwiedni jak wyzej); przeliczenie calej siatki:
  72/144 arkuszy ma zla litere cwiartki; `.venv/bin/kartograf parse N-34-7 --hierarchy` drukuje
  uzytkownikowi `N-34-7 -> N-34-A -> N-34`. Sciezka pobierania: `DownloadManager.download_hierarchy`
  (manager.py:324) i `download_sheet` dla godel grubszych niz 1:10000 uzywaja `get_all_descendants`,
  wiec `kartograf download N-34-A` pobiera zly obszar. Uwaga: `find_sheets_for_bbox` NIE jest dotkniete
  (liczy siatke 12x12 matematycznie, `_find_200k_sheets`), wiec tryb `--bbox`/`--geometry` jest poprawny.
- Proponowana naprawa: liczyc cwiartke z pozycji w siatce: `row,col = divmod(nr-1,12)`,
  `letter = "ABCD"[(row>=6)*2 + (col>=6)]`, a `_get_children_from_500k` odwrotnie — dzieci to numery
  `row*12+col+1` dla `row in {0..5}|{6..11}`, `col in {0..5}|{6..11}` wg cwiartki. Testy
  `tests/test_sheet_parser.py:409-500,662` utrwalaja obecne (bledne) zachowanie i musza byc poprawione
  razem z kodem (asercje typu "N-34-37 -> N-34-B").
- Pewnosc: wysoka

### A1-2 [Critical] Brak `probe_point` w politykach produkcyjnych — na maszynie z siatkami PROJ kazde pobranie CZ wybiera operacje zwracajaca inf
- Plik: `kartograf/transform/crs.py:187` (filtr probe) vs `kartograf/providers/cuzk/dmr.py:64-80` (polityki)
- Twierdzenie: regula nr 3 polityki transformacji ("probe na punkcie kontrolnym — inf/NaN => odrzut
  operacji, przypadek siatki obcego kraju") nie jest w produkcji nigdy aktywna, bo zadna polityka nie
  ustawia `probe_point`; przy dostepnych siatkach PROJ dla pary 5514->2180 wygrywa operacja slowacka
  (0,051 m), ktora w Czechach zwraca inf.
- Dowod: `grep -rn "probe_point" kartograf/ tests/` daje wylacznie definicje w `crs.py` i 3 uzycia w
  `tests/test_transform_crs.py` — zaden konsument produkcyjny. Tymczasem `KNOWN_PATHS` w tym samym pliku
  deklaruje dla tej pary: `"probe odrzuca sk_gku (inf w CZ)"` (crs.py:132).
  Wejscie -> zle wyjscie (uruchomione z `PROJ_USER_WRITABLE_DIRECTORY` zawierajacym pakiet `sk_gku`,
  siec PROJ WYLACZONA, polityka identyczna z `_HORIZONTAL_POLICY`):
  ```
  WYBRANA: 0.051 | ... Inverse of S-JTSK [JTSK03] to S-JTSK (1) + S-JTSK [JTSK03] to ETRS89 ...
  CZ (-447000,-1114000) -> TransformError (wartosc nieskonczona)
  pipeline ma sk_gku: True
  ```
  Ta sama polityka z `probe_point=(-447000,-1114000)` wybiera poprawna operacje 0,5 m.
- Weryfikacja: dwa uruchomienia CLI na zywo, roznica tylko w obecnosci siatek w katalogu PROJ:
  `kartograf download 302_5550 --country cz` -> `Error: Transformacja zwrocila wartosc nieskonczona [...]`;
  `kartograf download --bbox 18.55,49.60,18.56,49.61 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180`
  -> niezlapany traceback `rasterio._err.CPLE_NotSupportedError: Cannot instantiate pipeline ... grids=sk_gku_JTSK03_to_JTSK.tif`.
  Bez katalogu z siatkami oba polecenia koncza sie sukcesem (kontrola). Siatki instaluje kazdy
  `projsync --all` / pakiet `proj-data` — to typowa stacja GIS, wiec warunek nie jest egzotyczny.
  Trzeci, cichy tryb awarii: `gdal_operation()` oddaje ten sam pipeline do `rasterio.warp.reproject`,
  co przy siatce widocznej dla GDAL-a daje raster w calosci nodata bez zadnego bledu.
- Proponowana naprawa: ustawic `probe_point` we WSZYSTKICH politykach CZ (punkt w srodku Czech w ukladzie
  zrodlowym; dla `_ENVELOPE_POLICY`/`_HORIZONTAL_POLICY` naturalnym kandydatem jest srodek zadanego bboxa,
  co dodatkowo czyni probe zaleznym od danych) — albo, minimalnie, wymagac `probe_point` w
  `build_pinned_transform` (blad przy `None`), zeby regula 3 nie mogla zostac pominieta.
- Pewnosc: wysoka

### A1-3 [Critical] Shapefile z punktami wywraca `--geometry` niezlapanym `AttributeError`
- Plik: `kartograf/core/geometry.py:143`
- Twierdzenie: `shape.bbox` nie istnieje dla typu POINT w pyshp, wiec kazdy punktowy `.shp` konczy sie
  tracebackiem zamiast `ValidationError`.
- Dowod:
  ```python
  for shape in sf.iterShapes():
      if shape.shapeType == 0:   # tylko NULL jest pomijany
          continue
      bbox = shape.bbox          # AttributeError dla POINT
  ```
  Wejscie -> zle wyjscie: `.shp` z dwoma punktami (pyshp 3.0.3, `.prj` = PL-1992):
  `kartograf download --geometry pts.shp` -> `AttributeError: 'Point' object has no attribute 'bbox'`
  (traceback przez `cmd_download` -> `get_overall_bbox` -> `_read_shp_bboxes`).
- Weryfikacja: plik wygenerowany `shapefile.Writer` w scratchpadzie, uruchomione `kartograf download
  --geometry pts.shp --output out` — pelny traceback na stderr, kod wyjscia != 0, brak komunikatu dla
  uzytkownika. Punktowe warstwy (przekroje/wyloty zlewni) to realny przypadek uzycia w toolchainie
  hydrologicznym.
- Proponowana naprawa: w `_read_shp_bboxes` uzyc `getattr(shape, "bbox", None)`, a przy jego braku zlozyc
  obwiednie z `shape.points` (dla punktu jest to zdegenerowany bbox `x,y,x,y`); zdegenerowane bboxy
  wymagaja tez naprawy A1-7/M4, inaczej daja pusta liste arkuszy.
- Pewnosc: wysoka

### A1-4 [Critical] Deskryptor `pl.gugik.nmt_1m` deklaruje kanal WCS dla EVRF2007, ktorego serwer nie ma — `download_bbox()` z domyslnymi ustawieniami zwraca blad
- Plik: `kartograf/sources/registry.py:80-85` (kanal WCS, `vertical_crs_options=_PL_VERTICAL_BOTH`),
  `kartograf/providers/pl/gugik.py:84-85` (endpoint)
- Twierdzenie: endpoint WCS EVRF2007 jest martwy (404), wiec udokumentowana w README/PRD sciezka
  `DownloadManager.download_bbox()` z domyslnym `vertical_crs="EVRF2007"` zawsze konczy sie
  `DownloadError`, a deskryptor (zrodlo prawdy wg ADR-022) deklaruje ten kanal jako dostepny.
- Dowod: `README.md:90-91`
  ```python
  # Pobieranie przez bbox -> GeoTIFF (WCS) - tylko dla NMT 1m
  path = manager.download_bbox(area, "my_area.tif")
  ```
  Wejscie -> zle wyjscie (uruchomione na zywo):
  `DownloadManager(output_dir=...).download_bbox(BBox(530000,382000,530500,382500,"EPSG:2180"),"evrf.tif")`
  -> `DownloadError: ... 404 Client Error: Not Found for url: .../WCS/DigitalTerrainModelFormatTIFFEVRF2007?...`
  (3 proby). Ten sam bbox z `vertical_crs="KRON86"` -> plik 1 001 205 B, OK.
- Weryfikacja: bezposrednie `requests.get(...GetCapabilities)` na endpoint EVRF2007 -> HTTP 404;
  uruchomienie biblioteczne jak wyzej (EVRF FAIL / KRON OK). CLI `--bbox` NIE jest dotkniete (idzie
  sciezka skorowidz+OpenData, sprawdzone: 4 pliki pobrane poprawnie).
- Proponowana naprawa: zawezic kanal WCS w deskryptorze do `("EPSG:9650",)` i dodac `notes` o wycofaniu
  endpointu EVRF2007 przez GUGiK (2026-08-11), a w `GugikProvider.download_bbox` rzucac `ValidationError`
  z podpowiedzia "uzyj vertical_crs='KRON86' albo pobierz arkusze" zamiast trzykrotnego 404; zaktualizowac
  README/PRD/CLAUDE.md ("Ograniczenia").
- Pewnosc: wysoka

### A1-5 [Important] GPKG z geometria punktowa: wszystkie obiekty po cichu pomijane, komunikat mylacy
- Plik: `kartograf/core/geometry.py:62-63` (`envelope_type == 0 -> None`) i `:308-310` (pominiecie)
- Twierdzenie: czytnik GPKG opiera sie wylacznie na obwiedni w naglowku GeoPackage Binary; GDAL/QGIS
  zapisuja punkty z `envelope_type=0`, wiec kazda punktowa warstwa GPKG jest widziana jako "brak geometrii".
- Dowod: `ogr2ogr -f GPKG pts.gpkg pts.shp` -> blob 29 B, `flags=0x1`, `env_type=0`;
  `read_feature_bboxes(Path('pts.gpkg'))` -> `[]`;
  `kartograf download --geometry pts.gpkg` -> `Error: No features with geometry found in: pts.gpkg`
  (komunikat nieprawdziwy — geometria jest, brak jest tylko obwiedni w naglowku).
  Dodatkowo `find_sheets_for_geometry` dla takiego pliku zwraca `[]` bez zadnego ostrzezenia.
- Weryfikacja: uruchomione `ogr2ogr` (GDAL systemowy) + snippet sqlite3 pokazujacy flagi + dwa
  uruchomienia CLI (`download --geometry`, `landcover download --geometry`).
- Proponowana naprawa: gdy `envelope_type == 0`, sparsowac obwiednie z samego WKB (dla POINT wystarcza
  odczyt jednej pary wspolrzednych po naglowku) albo przynajmniej rzucic `ValidationError` z jasnym
  komunikatem ("warstwa bez obwiedni w naglowku GPKG — przekonwertuj plik / uzyj SHP").
- Pewnosc: wysoka

### A1-6 [Important] `server_reprojection=True` w deskryptorach CZ jest sprzeczne z ADR-024 i nigdzie nie konsumowane
- Plik: `kartograf/sources/registry.py:240` i `:281`
- Twierdzenie: deskryptory CZ deklaruja, ze kanal `ARCGIS_IMAGE` reprojektuje po stronie serwera, podczas
  gdy ADR-024 zakazuje tej sciezki (blad 135 m, zmienny przestrzennie); pole nie jest odczytywane przez
  zaden kod produkcyjny, wiec jest martwa deklaracja mogaca wprowadzic w blad kolejnego konsumenta
  deskryptorow (etap 2: DE/SK).
- Dowod: ADR-024 (docs/DECISIONS.md:654): "**Serwer CUZK dostaje zadania rastrowe WYLACZNIE w ukladzie
  natywnym** (`NATIVE_CRS = "EPSG:5514"`). Dotyczy obu sciezek". Kod deskryptora:
  ```python
  transport=TransportKind.ARCGIS_IMAGE,
  horizontal_crs="EPSG:5514",
  server_reprojection=True,      # registry.py:240
  ```
- Weryfikacja: `grep -rn "server_reprojection" kartograf/ tests/` -> definicja (`descriptor.py:45`),
  dwie deklaracje w rejestrze i wylacznie asercje w `tests/test_sources_registry.py:61,190,210,216`;
  zaden odczyt w providerach/CLI/managerach.
- Proponowana naprawa: ustawic `server_reprojection=False` dla obu kanalow CZ i przeniesc informacje do
  `notes` ("serwer potrafi imageSR, ale ADR-024 tego zabrania"), albo usunac pole z `AccessChannel`, jesli
  ma nie miec konsumenta; zaktualizowac asercje w tescie.
- Pewnosc: wysoka

### A1-7 [Important] Niespojne traktowanie stykajacych sie krawedzi — bbox rowny arkuszowi daje 9 arkuszy zamiast 4
- Plik: `kartograf/core/sheet_parser.py:845` (`_bboxes_intersect`, `<`) vs `:991,998,1042,1046` (odjecie `1e-10`)
- Twierdzenie: na poziomie 1:1M i 1:200k stykajace sie krawedzie sa wykluczane sztuczka `-1e-10`, a na
  wszystkich nizszych poziomach (`_find_children_intersecting`) wliczane — ten sam bbox jest wiec
  traktowany dwiema roznymi konwencjami, a wynik zawiera arkusze o zerowym polu przeciecia.
- Dowod (uruchomione):
  `find_sheets_for_bbox(SheetParser('N-34-130-D').get_bbox('EPSG:4326'), '1:50000')` ->
  `['N-34-130-A-d','N-34-130-B-c','N-34-130-B-d','N-34-130-C-b','N-34-130-C-d','N-34-130-D-a','N-34-130-D-b','N-34-130-D-c','N-34-130-D-d']`
  — 9 arkuszy zamiast 4 dzieci `N-34-130-D`; 5 nadmiarowych styka sie tylko krawedzia/rogiem.
  Analogicznie bbox rowny arkuszowi 1:10000 daje 4 arkusze zamiast 1 (sprawdzone dla `N-34-130-D-d-2-4`),
  a arkusze sasiadujace zza granicy arkusza 1:200k sa (niesymetrycznie) pomijane.
- Weryfikacja: snippety jak wyzej; w praktyce oznacza to 2-4x wiecej pobranych plikow ASC (35 MB kazdy)
  dla bboxa wyrownanego do siatki godel — czestego, bo taki bbox produkuje sam `SheetParser.get_bbox()`.
- Proponowana naprawa: ujednolicic konwencje — `_bboxes_intersect` powinno wymagac dodatniego pola
  przeciecia (`<=` zamiast `<`) z tolerancja (np. 1e-9 stopnia), po czym sztuczki `-1e-10` w
  `_find_1m_sheets`/`_find_200k_sheets` staja sie zbedne; zdegenerowany bbox (punkt) obsluzyc jawnie.
- Pewnosc: wysoka

### A1-8 [Important] Etykiety skal PL-1992 sa przesuniete o jeden poziom wzgledem GUGiK i standardu krajowego
- Plik: `kartograf/core/sheet_parser.py:65-84` (`SCALE_HIERARCHY`, `PATTERNS`), `:568-576` (`_SHEET_DIMENSIONS`)
- Twierdzenie: godlo 7-czlonowe jest w kodzie oznaczane jako `1:10000`, podczas gdy GUGiK nazywa ten sam
  arkusz modulem `1:5000`; analogicznie siatka 1-144 (20'x30') jest oznaczona `1:200000`, choc to arkusz
  `1:100000` — prawdziwy poziom 1:200000 (36 arkuszy 40'x1°) w hierarchii nie istnieje.
- Dowod: GetFeatureInfo skorowidza GUGiK dla pobranego arkusza `M-34-27-B-b-2-3` (ten sam godlo, ktory
  Kartograf pobral w tej sesji) zwraca:
  `godlo:"M-34-27-B-b-2-3", ..., modulArchiwizacji:"1:5000", aktualnoscRok:"2022"`,
  a `SheetParser('M-34-27-B-b-2-3').scale` = `'1:10000'`.
  Wymiary liczone przez kod: `1:10000` -> 1,25' x 1,875' (standard dla 1:5000), `1:200000` -> 20' x 30'
  (standard dla 1:100000).
- Weryfikacja: zapytanie WMS GetFeatureInfo na zywo (warstwa `SkorowidzeNMT2023iStarsze`) + snippet
  liczacy rozmiary arkuszy w minutach. Funkcjonalnie pobieranie jest poprawne (GUGiK udostepnia pliki
  dokladnie na tym poziomie takze dla NMT 5m — sprawdzone: `N-34-141-A-a-1-1..4` maja osobne URL-e
  OpenData), wiec skutek jest interpretacyjny: konsument biblioteki (Hydrograf) porownujacy
  `parser.scale` z metadanymi GUGiK dostaje sprzecznosc, a CLI `--scale 1:10000` znaczy w istocie 1:5000.
- Proponowana naprawa: nie zmieniac nazw w v0.7.0 (zmiana lamiaca API i cala dokumentacje) — udokumentowac
  odstepstwo jawnie (`SCOPE.md`/docstring `SheetParser`: "etykiety skal Kartografu sa o jeden poziom
  drobniejsze niz nomenklatura GUGiK; 7-czlonowe godlo = modul archiwizacji 1:5000") i zaplanowac
  aliasowanie w kolejnej wersji major. Poprawka A1-1 jest od tej decyzji niezalezna.
- Pewnosc: wysoka

### A1-9 [Important] Arkusze PL-2000 laduja w `nmt_1m/`, choc dokumentacja i ADR obiecuja `nmt_2000_1m/`
- Plik: `kartograf/download/storage.py:31-33` (docstring), `:98-120` (`_RESOLUTION_SUBDIRS`, `_subdir`)
- Twierdzenie: zaden kod produkcyjny nie ustawia `product="nmt_2000_1m"`, wiec godla PL-2000 trafiaja do
  tego samego podkatalogu co PL-1992 — wbrew docstringowi klasy, CHANGELOG i ADR-018.
- Dowod: `docs/DECISIONS.md:299`: "FileStorage: podkatalog `nmt_2000_1m` dla PL-2000 arkuszy";
  `docs/CHANGELOG.md:342`: "Struktura katalogow: `nmt_2000_1m/6/179/12/20/6.179.12.20.asc`".
  Wejscie -> zle wyjscie: `FileStorage('./data', resolution='1m').get_path('6.179.12.20','.asc')` ->
  `data/nmt_1m/6/179/12/20/6.179.12.20.asc`.
- Weryfikacja: snippet jak wyzej + `grep -rn "nmt_2000" kartograf/` — jedyne wystapienia to docstring;
  jedyne uzycia `product="nmt_2000_1m"` sa w `tests/test_storage.py` (test podaje product recznie, wiec
  nie wykrywa rozjazdu).
- Proponowana naprawa: albo wybierac subdir wg systemu godla (`parser_registry.detect_system(godlo).id ==
  "pl2000"` -> `nmt_2000_<res>`) w `FileStorage._subdir`, albo — jesli mieszanie jest swiadome — poprawic
  docstring, CHANGELOG i ADR-018 (nazwy plikow i tak sie nie kolidują).
- Pewnosc: wysoka

### A1-10 [Minor] `_SHEET_DIMENSIONS` to martwa tablica (i niesie przesuniete etykiety)
- Plik: `kartograf/core/sheet_parser.py:568`
- Twierdzenie: slownik nie jest nigdzie odczytywany (`grep -rn "_SHEET_DIMENSIONS"` — tylko definicja),
  a bbox liczony jest z dzielen w `_apply_*_subdivision`.
- Dowod/Weryfikacja: grep po calym repo (poza `__pycache__`) daje jedno trafienie.
- Proponowana naprawa: usunac albo zaczac go uzywac jako zrodla prawdy dla podzialow (spojnosc z A1-8).
- Pewnosc: wysoka

### A1-11 [Minor] `get_bbox()` obiecuje w docstringu EPSG:2176-2179, ale dla PL-1992 rzuca `ValidationError`
- Plik: `kartograf/core/sheet_parser.py:605` vs `:658`
- Dowod: `SheetParser('N-34-130-D-d-2-4').get_bbox('EPSG:2177')` ->
  `ValidationError: Nieobslugiwany uklad wspolrzednych: EPSG:2177. Obslugiwane: EPSG:2180, EPSG:4326`.
- Weryfikacja: uruchomiony snippet. (Docstring jest prawdziwy tylko dla galezi PL-2000.)
- Proponowana naprawa: doprecyzowac docstring albo dopiac transformacje do stref 2176-2179 przez
  `_transform_bbox` (jak w `Parser2000`).
- Pewnosc: wysoka

### A1-12 [Minor] Normalizacja godla pomija litere arkusza 1:500k — `SheetParser('N-34-a')` to ParseError
- Plik: `kartograf/core/sheet_parser.py:189-201`
- Dowod: petla normalizuje indeksy 0, 3 i 4; indeks 2 (litera A-D w godle 1:500k) zostaje bez zmian, wiec
  `'N-34-a'` i `'n-34-a'` -> `ParseError`, podczas gdy `'n-34-130-d-D-2-4'` normalizuje sie poprawnie.
- Weryfikacja: uruchomiony snippet z 5 wariantami wielkosci liter.
- Proponowana naprawa: uppercase takze dla indeksu 2, gdy czesc jest pojedyncza litera.
- Pewnosc: wysoka

### A1-13 [Minor] Zdegenerowany bbox dokladnie na linii siatki 4°/6° zwraca pusta liste arkuszy
- Plik: `kartograf/core/sheet_parser.py:990-1000`
- Dowod: `find_sheets_for_bbox(BBox(21.0,52.0,21.0,52.0,'EPSG:4326'))` -> `[]`
  (dla `BBox(21.1,52.1,...)` -> `['N-34-139-C-a-4-4']`). Przyczyna: `min_row` liczony z `floor(south/4)`,
  `max_row` z `floor((north-1e-10)/4)`, a korekta granicy wymaga `north > south`.
- Weryfikacja: uruchomiony snippet. Istotne dopiero po naprawie A1-3 (punkty).
- Proponowana naprawa: obsluzyc `min_x == max_x` / `min_y == max_y` jawnie (traktowac jako punkt) lub
  rozszerzyc zdegenerowany bbox o epsilon przed wyszukiwaniem.
- Pewnosc: wysoka

### A1-14 [Minor] `write_sidecar` lapie tylko `OSError` i zwraca sciezke pliku, ktory nie powstal
- Plik: `kartograf/sources/sidecar.py:137-142`
- Twierdzenie: `json.dumps` niesrializowalnego `extra` (np. `Path`, `set`) rzuca `TypeError`, ktory nie jest
  lapany; dzis ratuje to fakt, ze wszyscy wolajacy (`manager.py:684`, `download_cmd.py:887,1067`,
  `landcover/manager.py:448`) owijaja wywolanie w `except Exception`, wiec kontrakt "sidecar nigdy nie
  przerywa pobrania" trzyma sie na warstwie wyzej, nie w samej funkcji.
- Weryfikacja: czytanie kodu + grep wszystkich wywolan `write_sidecar(` (4 miejsca, wszystkie owiniete).
- Proponowana naprawa: rozszerzyc `except` o `TypeError`/`ValueError` (albo `Exception`) i zwracac
  `Path | None`, zeby konsument mogl odroznic sukces od porazki.
- Pewnosc: wysoka

### A1-15 [Minor] `build_pinned_transform` przelacza globalna flage sieci PROJ (nie jest bezpieczne watkowo)
- Plik: `kartograf/transform/crs.py:167-168,204`
- Twierdzenie: `network.set_network_enabled()` to stan procesu; przy dwoch rownoleglych budowach polityk o
  roznym `allow_network_grids` koncowy stan zalezy od przeplotu (jeden watek przywraca wartosc zapamietana
  przez drugi). Dzis sciezki CZ sa sekwencyjne, wiec to ryzyko, nie blad obserwowalny; ale
  `DownloadManager` domyslnie chodzi na 4 watkach i to pierwsze miejsce, gdzie polityki trafia do puli.
- Weryfikacja: czytanie kodu; brak testu wielowatkowego (`tests/test_transform_crs.py:245` sprawdza tylko
  przywrocenie flagi w jednym watku).
- Proponowana naprawa: serializowac budowe transformacji `threading.Lock` na poziomie modulu (koszt
  pomijalny — transformacje sa cache'owane w providerze) albo udokumentowac ograniczenie w docstringu.
- Pewnosc: srednia

### A1-16 [Minor] `download_to` ponawia takze bledy trwale (404/401) i owija je w 3 proby z backoffem
- Plik: `kartograf/transport/http.py:52-62`
- Twierdzenie: `raise_for_status()` daje `requests.HTTPError` (podklasa `RequestException`), wiec
  404 z openzu CUZK kosztuje 3 zadania i 3 s uspienia zanim uzytkownik dostanie komunikat.
- Weryfikacja: czytanie kodu; potwierdzone posrednio ksztaltem logu z A1-4 (3 proby na 404 w WCS GUGiK —
  inna implementacja, ten sam wzorzec).
- Proponowana naprawa: nie ponawiac dla statusow 4xx innych niz 408/429.
- Pewnosc: wysoka

### A1-17 [Minor] `geometry._transform_bbox` omija twarda polityke transformacji (ADR-022)
- Plik: `kartograf/core/geometry.py:359`
- Twierdzenie: obwiednie z plikow uzytkownika przeliczane sa zwyklym `Transformer.from_crs(...)`, ktoremu
  ADR-022 zarzuca cichy ballpark; dla plikow w EPSG:2180/4326 to bezpieczne, ale dla pliku np. w EPSG:5514
  sciezka PL (`--country pl`) uzyje operacji spoza polityki (sciezka CZ juz korzysta z `bbox_to_crs`,
  `cli/download_cmd.py:840-845`).
- Weryfikacja: czytanie kodu + porownanie obu galezi `_resolve_bbox` w `cli/download_cmd.py`.
- Proponowana naprawa: docelowo przepiac `_transform_bbox` na `build_pinned_transform` z polityka
  obwiedniowa (i probe — patrz A1-2); minimum na teraz: nota w docstringu modulu.
- Pewnosc: srednia

## Pozytywy (krotko)
- Sidecar (`sources/sidecar.py`) jest zgodny z kontraktem ze specu 6.3 i ADR-023: sprawdzony na zywym
  pobraniu (`M-34-27-B-b-2-3.asc.meta.json`) — komplet pol, `vertical_crs` poprawnie rozwiazany przez
  `resolve_vertical_crs` do realizacji krajowej `EPSG:9651`, `nodata` odczytane z naglowka ASC,
  `parent_request` wpiety wg ADR-023 f.1.
- `transport/mosaic.py` zachowuje sie poprawnie na wejsciach kaflowanych (blockxsize > wynik) i propaguje
  nodata takze w lukach poza suma kafli — zweryfikowane rasterio na syntetycznych GeoTIFF-ach.
- `Parser2000` jest wewnetrznie spojny: wzor `west = strefa*1e6 + slup*8000 + 332000` daje arkusze
  wypadajace w zakresie dlugosci wlasnej strefy (sprawdzone pyproj dla 6.179.12 -> 16,94..17,06°E).
- `PinnedTransform.gdal_operation()` wylicza korekte osi z `axis_info` zamiast ja zakladac — poprawnie
  rozpoznaje northing-first dla EPSG:2180/3045, a E-N dla 5514/25833 (sprawdzone).
- `parser_registry` porzadkuje detekcje systemow godel deterministycznie (fallback PL-1992 zawsze ostatni),
  a wzorce CZ zgadzaja sie z realnymi danymi CUZK z fixtur (`OSTR01`, `744_5536`).

## Podsumowanie liczbowe: C=4 I=5 M=8
