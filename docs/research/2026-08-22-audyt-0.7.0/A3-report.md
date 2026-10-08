# A3 — Poprawnosc logiczna: providers/cuzk/ + cli/

Zakres: przeczytane W CALOSCI: `kartograf/providers/cuzk/{client.py,sheets.py,dmr.py,__init__.py}`,
`kartograf/cli/{_parser.py,download_cmd.py,parse_cmd.py,landcover_cmd.py,soilgrids_cmd.py,cache_cmd.py,commands.py}`.
Pomocniczo (do weryfikacji kontraktow, nie audytowane jako obszar): `transform/crs.py`,
`transport/{http.py,mosaic.py}`, `sources/{registry.py,sidecar.py,descriptor.py}`,
`core/{parser_registry.py,parser_tm33.py}`, `docs/DECISIONS.md` (ADR-023, ADR-024), `docs/SCOPE.md`, `CLAUDE.md`.

Metoda: czytanie pelnych plikow + grep; 343 testy `tests/test_cli.py tests/test_cuzk_*.py tests/test_parser_tm33.py`
(zielone, 6,5 s); `mypy kartograf/cli/ kartograf/providers/cuzk/`; 8 wywolan `.venv/bin/kartograf download ...`
na sciezkach walidacyjnych (bez sieci, uruchamiane spoza repo, zeby nie tworzyc `.kartograf_cache.db`);
11 skryptow weryfikacyjnych w scratchpadzie (`h1..h15`) — mocki `download_to`/`CuzkClient`, syntetyczne
GeoTIFF-y i `.tfw`, podmiana limitow `MAX_EXPORT_*`, realne fixtury `tests/fixtures/cuzk/`.
Zadnego polaczenia z CUZK/GUGiK. Zaden plik repo nie byl modyfikowany (poza tym raportem).

Nie sprawdzono: zachowania serwerow CUZK/GUGiK na zywo (limity exportImage, ksztalt TIFF-ow z openzu,
stabilnosc paginacji ArcGIS) — tylko przez fixtury i mocki; `landcover_cmd/soilgrids_cmd/cache_cmd`
przejrzane, ale nie sa nowym kodem etapu 1 i nie znalazlem tam bledow logicznych poza dlugiem mypy
(swiadomy baseline); wydajnosc/pokrycie testow (obszar innych audytorow).

## Ustalenia

### A3-1 [Critical] Kafelkowanie exportImage gubi dolny wiersz danych (pas `-9999`) i przesuwa zasieg
- Plik: `kartograf/providers/cuzk/client.py:181` (wolanie `mosaic_and_crop`) w zestawieniu z `kartograf/providers/cuzk/client.py:248-281` (`_tile_grid`)
- Twierdzenie: siatka kafli jest kotwiczona w narozniku **SW** (`bbox.min_y + off*pixel_size`), a `mosaic_and_crop`
  przycina do `bbox` kotwiczonego w narozniku **NW** — gdy `(max_y-min_y)/pixel_size` zaokragla sie W GORE,
  najnizszy wiersz wyniku jest w calosci `-9999`, mimo ze serwer zwrocil dla niego dane.
- Dowod: identyczna koperta CZ przez CLI (`--country cz --bbox -450000,-1100000,-449500,-1099818.6 --bbox-crs EPSG:5514`,
  wysokosc 181,4 m / 2 m = 90,7 px), mock `download_to` zwraca kafle wypelnione WYLACZNIE wartoscia 300.0:
  ```
  kafelkowany:     rc=0 ksztalt=(91,250) nodata=250 cale_wiersze_nodata=[90] bounds_dol=-1100000.6
  jednokafelkowy:  rc=0 ksztalt=(91,250) nodata=0   cale_wiersze_nodata=[]   bounds_dol=-1100000.0
  ```
  Dolna krawedz wyniku kafelkowanego lezy tez 0,6 m ponizej zadania (inny zasieg niz sciezka jednokafelkowa).
- Weryfikacja: skrypt `h13.py` (powyzej, pelna sciezka `cmd_download`) oraz zamiatanie `h2b.py` po czesciach
  ulamkowych: nodata pojawia sie deterministycznie dla KAZDEGO przypadku, w ktorym wysokosc zaokragla sie w gore
  (12 z 36 kombinacji; przy dowolnym bboxie uzytkownika ~50% przypadkow). Test `test_tiling_above_limits_mosaics`
  (`tests/test_cuzk_client.py:400`) uzywa koperty 16x16 m przy 2 m — dokladna wielokrotnosc piksela, wiec
  problemu nie widzi. Kafelkowanie wlacza sie dla kazdego bboxa wyzszego niz 4100 px (8,2 km przy DMR 5G),
  czyli dla typowych zadan zlewniowych.
- Proponowana naprawa: kotwiczyc `_tile_grid` w narozniku NW (`bbox.max_y - (off+px)*pixel_size` ... `bbox.max_y - off*pixel_size`),
  tak jak robia to `merge` i `_warp_to_grid` (`from_origin(min_x, max_y, ...)`); alternatywnie przycinac mozaike do
  faktycznego zasiegu kafli. Wariant NW zweryfikowany skryptem `h15.py`: 0/6 przypadkow z nodata wobec 2/6 obecnie,
  rozmiary wyniku bez zmian.
- Pewnosc: wysoka

### A3-2 [Important] `--country auto` uruchamia galaz PL dla bboxow w glebi Czech i konczy zadanie kodem 1
- Plik: `kartograf/cli/download_cmd.py:213-234` (`_countries_for_bbox`) i `kartograf/cli/download_cmd.py:404-422` (`_dispatch_area`)
- Twierdzenie: prostokat PL (`14.07, 49.00, 24.20, 54.90`) pokrywa wieksza czesc Czech, wiec dla bboxa np. w Pradze
  `--country auto` wysyla zadanie takze do GUGiK; GUGiK nie ma tam danych, `_download_pl_bbox` zwraca 1, a
  `max(exit_codes)` zamienia poprawnie pobrany raster CZ w blad calego polecenia.
- Dowod: `_countries_for_bbox` dla Pragi/Brna zwraca `('CZ','PL')`, a galaz PL wyznacza realne godla do pobrania:
  ```
  Praga (WGS84): kraje=('CZ','PL')  arkusze GUGiK: 9 -> ['M-33-65-D-b-3-3', 'M-33-65-D-b-3-4', ...]
  Brno  (WGS84): kraje=('CZ','PL')  arkusze GUGiK: 16 -> ['M-33-106-A-c-1-4', ...]
  ```
  Symulacja calego zadania (CZ=0, GUGiK rzuca `DownloadError` jak w `providers/pl/gugik.py:544`
  "No NMT ... data available for ..."): `rc = 1` przy poprawnie pobranym pliku CZ.
- Weryfikacja: skrypty `h7.py` (kraje + lista arkuszy, `find_sheets_for_bbox` liczone realnie) i `h14.py`
  (patch `_run_cz` -> 0, `_download_godlo_list` -> `DownloadError`; wynik `rc=1`). ADR-023 "Ustalenia dodatkowe" pkt 4
  opisuje wylacznie kierunek odwrotny (zadanie do CUZK dla bboxa w PL) i zapewnia, ze skutkiem jest raster nodata,
  "a nie blad" — kierunek PL nie jest udokumentowany i konczy sie twardym bledem plus 9-16 zbednymi zapytaniami HTTP.
- Proponowana naprawa: w trybie `auto` traktowac kraj, ktorego zadanie sie nie powiodlo, jako "brak pokrycia" gdy
  inny kraj dal wynik (np. kod 0 z ostrzezeniem na stderr, kod 1 tylko gdy padly wszystkie kraje), albo przyciac
  galaz PL do rzeczywistej granicy (wielokat granicy planowany na etap 2) — do czasu etapu 2 wystarczy pierwsza czesc.
- Pewnosc: wysoka

### A3-3 [Important] Uszkodzony kafel w sciezce kafelkowanej ucieka jako `RasterioIOError` (traceback zamiast komunikatu)
- Plik: `kartograf/providers/cuzk/client.py:181` -> `kartograf/transport/mosaic.py:31` (`rasterio.open(p)`); handlery: `kartograf/cli/download_cmd.py:1182` i `:164`
- Twierdzenie: `_export_single` sprawdza tylko 4 bajty magic TIFF, a `mosaic_and_crop` otwiera kafle PRZED
  `_overwrite_crs` (ktory jako jedyny mapuje bledy rasterio na `DownloadError`); urwany kafel powoduje wyjatek
  spoza `(DownloadError, ValidationError, ParseError, TransformError)`, wiec uciekaja poza `_cz_download_bbox`
  i `_run_cz` do uzytkownika jako traceback.
- Dowod: mock `download_to` zapisuje 2. kafel jako `b"II*\x00" + 64 zera` (magic poprawny, cialo urwane):
  ```
  WYJATEK UCIEKL Z cmd_download: rasterio.errors.RasterioIOError
      Cannot open TIFF image
  ```
  Kontrola: ten sam urwany plik na sciezce JEDNOkafelkowej daje czysty `Error: exportImage: nie udalo sie nadpisac
  CRS na EPSG:5514 ... Cannot open TIFF image` i `rc=1` (skrypt `h9.py`).
- Weryfikacja: skrypty `h10.py` (kafelkowanie, limity `MAX_EXPORT_*` podmienione na 100x40) i `h9.py` (kontrola).
  Ta sama klasa awarii jest juz swiadomie obsluzona na sciezce SM5 (`dmr.py:559-578` `_assign_crs` + test
  `test_sm5_corrupted_tiff_raises_download_error_and_cleans_up`) — luka jest niespojnoscia we wlasnym wzorcu.
- Proponowana naprawa: opakowac `mosaic_and_crop(...)` w `export_image` w `try/except Exception` -> `DownloadError`
  (z usunieciem wyniku), analogicznie do `_overwrite_crs`; ewentualnie dodatkowo walidowac dlugosc odpowiedzi w `_export_single`.
- Pewnosc: wysoka

### A3-4 [Important] Mozaika CZ trzyma caly wynik w RAM — brak jakiegokolwiek limitu rozmiaru zadania
- Plik: `kartograf/transport/mosaic.py:44` (`merge(sources, bounds=..., nodata=...)` bez `dst_path`)
- Twierdzenie: `rasterio.merge` dzieli prace na kawalki TYLKO gdy dostanie `dst_path`
  (`.venv/.../rasterio/merge.py:401`: `if output_width*output_height < max_pixels ... else subdivide`, galaz osiagalna
  wylacznie przy zapisie do pliku); wolanie bez `dst_path` alokuje jedna tablice na caly wynik, a CLI CZ nie ma
  zadnego progu rozmiaru bboxa — zadanie 40x40 km przy DMR 5G (20000x20000 px) to ~1,6 GB samych danych.
- Dowod: pomiar `tracemalloc` na realnym `mosaic_and_crop` (2 kafle -> wynik 4000x4000 px):
  ```
  wynik 4000x4000 px (64 MB danych) -> szczyt alokacji: 168.0 MB   (~2,6x rozmiar rastra)
  ```
  Ekstrapolacja: 30x30 km => ~900 MB danych => ~2,3 GB szczytu; PL nie ma tego problemu, bo `--bbox` rozklada sie
  na osobne arkusze.
- Weryfikacja: skrypt `h4.py` + lektura `rasterio/merge.py:392-406`.
- Proponowana naprawa: przekazac `dst_path=output_path` do `merge` (rasterio zapisuje kawalkami i sam ogranicza
  pamiec) albo dolozyc twardy limit pikseli zadania CZ z czytelnym `ValidationError` i podpowiedzia podzialu bboxa.
- Pewnosc: wysoka

### A3-5 [Important] Transformacja pionowa arkusza SM5 gubi parowanie `.tif`/`.tfw` — poprawnosc trzyma sie efektu ubocznego GDAL
- Plik: `kartograf/providers/cuzk/dmr.py:378-384` (`temp_path = path.with_name(f"{path.name}.{pid}_{tid}.vshift.tif")` + `shutil.copy2`)
- Twierdzenie: georeferencja DMR 4G z openzu siedzi w `.tfw`, a kopia tymczasowa dostaje nazwe, do ktorej ten
  `.tfw` juz nie pasuje; obliczenie `(lon, lat)` w `_shift_in_place` dziala poprawnie tylko dlatego, ze
  `_assign_crs` (zapis CRS w trybie `r+`) przy okazji utrwala geotransformacje w samym TIFF-ie. Gdy plik z openzu
  ma juz jakikolwiek CRS, `_assign_crs` nic nie zapisuje (`if ds.crs is None`), kopia ma macierz jednostkowa,
  a wysokosci sa przesuwane offsetem policzonym dla wspolrzednych bedacych numerami pikseli — cicho, bez wyjatku.
- Dowod: dwa identyczne pliki (10x10 px, `.tfw` z zasiegiem CTES96), jedyna roznica to obecnosc CRS w TIFF-ie;
  po `_assign_crs` + `_apply_vertical_shift` (realna operacja `Baltic 1957 height to EVRF2007 height (1)`, 0,1 m):
  ```
  bez_crs: wynik piksela = 300.1277   (oczekiwane ~300.13)
  z_crs:   wynik piksela = 300.26794  (blad ~0,14 m, brak jakiegokolwiek ostrzezenia)
  ```
- Weryfikacja: skrypty `h1c.py` (dowod, ze kopia traci geotransformacje, gdy `_assign_crs` nic nie zapisze)
  i `h1d.py` (skutek liczbowy). Dzis sytuacja NIE wystepuje: rekonesans utrwalony w `_write_dmr4g_pair`
  (`tests/test_cuzk_dmr.py:67`) mowi "GeoTIFF bez CRS i bez geotransformacji" — dlatego to pulapka utajona,
  zalezna od zachowania serwera, nie aktywny blad.
- Proponowana naprawa: skopiowac `.tfw` obok kopii tymczasowej (`temp.with_suffix(".tfw")`) albo nadac kopii nazwe
  z tym samym stemem (`X.vshift.tif` + `X.vshift.tfw`); najpewniej — czytac `transform`/`crs` z pliku docelowego
  i wpisywac je jawnie w profil kopii przed przeliczeniem.
- Pewnosc: srednia (mechanizm potwierdzony pomiarem; wyzwolenie zalezy od ksztaltu pliku CUZK)

### A3-6 [Minor] mypy `no-redef` dla `all_paths` to wylacznie duplikat adnotacji, nie blad logiczny
- Plik: `kartograf/cli/download_cmd.py:669` (i `:652`)
- Twierdzenie: obie deklaracje `all_paths: list[Path] = []` leza w rozlacznych galeziach (pierwsza konczy sie
  `return all_paths` w linii 663), wiec zachowanie obu sciezek jest identyczne — do usuniecia jest tylko adnotacja.
- Dowod: `_download_godlo_list(M(), ["A","B","C"], True, None, w)` dla `w=1` i `w=4` zwraca ten sam zbior sciezek:
  `['/x/A.asc', '/x/B.asc', '/x/C.asc']`.
- Weryfikacja: skrypt `h11.py` (fake manager, bez sieci).
- Proponowana naprawa: usunac adnotacje w drugim wystapieniu (`all_paths = []`) albo zadeklarowac zmienna raz przed `if`.
- Pewnosc: wysoka

### A3-7 [Minor] Martwa klauzula `except` w rownoleglym pobieraniu godel
- Plik: `kartograf/cli/download_cmd.py:692-693`
- Twierdzenie: `except (DownloadError, ValidationError): raise` nic nie zmienia (wyjatek i tak by propagowal),
  a przy podniesieniu wyjatku pozostale futures nie sa anulowane — `with ThreadPoolExecutor` czeka na ich koniec.
- Dowod: `except (DownloadError, ValidationError):` / `raise` bezposrednio po `paths = future.result()`.
- Weryfikacja: lektura + `h11.py` (obie galezie zwracaja to samo).
- Proponowana naprawa: usunac `try/except` albo zebrac bledy i zglosic je zbiorczo po `as_completed`
  (spojnie z `_cmd_download_laz`, ktore raportuje liczbe nieudanych kafli).
- Pewnosc: wysoka

### A3-8 [Minor] `--scale` jest po cichu ignorowane dla CZ, choc `--system` daje blad
- Plik: `kartograf/cli/download_cmd.py:1204-1299` (`_cmd_download_cz` nie czyta `args.scale`)
- Twierdzenie: `kartograf download 302_5550 --scale 1:10000` pobiera zwykly kafel i konczy sie kodem 0, mimo ze
  skala nie ma zadnego znaczenia w CZ; analogiczna nieadekwatna flaga `--system` jest odrzucana komunikatem.
- Dowod: `grep -n "scale" kartograf/cli/download_cmd.py` — wystapienia wylacznie w sciezkach PL
  (`cmd_download` godlo-PL, `_download_pl_bbox`, `_download_pl_geometry`); w `_cmd_download_cz`/`_cz_download_*` brak.
- Weryfikacja: grep + przebieg `h8.py` (godlo TM33 z `--scale` konczy sie normalnym pobraniem jednego kafla).
- Proponowana naprawa: dolozyc guard w `_cmd_download_cz` (`--scale dotyczy tylko PL`), obok istniejacego dla `--system`.
- Pewnosc: wysoka

### A3-9 [Minor] Godlo TM33 z `--resolution 5m` jest akceptowane, choc dokumentacja mowi "TM33 to zawsze 2 m"
- Plik: `kartograf/providers/cuzk/dmr.py:220-226` (galaz `cz_tm33` nie sprawdza rozdzielczosci; SM5 sprawdza w `:311-318`)
- Twierdzenie: `kartograf download 302_5550 --resolution 5m` pobiera DMR 4G przycietego do kafla TM33
  (400x400 px), podczas gdy `CTES96 --resolution 2m` jest odrzucane — asymetria wzgledem CLAUDE.md
  ("DMR 5G (godlo TM33) to zawsze 2m, DMR 4G (godlo SM5) to zawsze 5m").
- Dowod: przebieg z mockiem `CuzkClient` dla `--resolution 5m` trafia w endpoint/katalog `cz_dmr4g`
  (`/tmp/x/cz_dmr4g/302/5550/302_5550.tif...`) i wchodzi w warp — brak jakiejkolwiek walidacji.
- Weryfikacja: skrypt `h8.py`.
- Proponowana naprawa: albo odrzucac kombinacje TM33+5m symetrycznie do SM5+2m, albo doprecyzowac dokumentacje,
  ze `--resolution` dla godla TM33 wybiera produkt zrodlowy (DMR 4G przyciety do siatki TM33).
- Pewnosc: wysoka

### A3-10 [Minor] `server_reprojection=True` w deskryptorach CZ przeczy wiazacej regule ADR-024
- Plik: `kartograf/sources/registry.py:240` i `:281`
- Twierdzenie: deskryptor (deklarowane "zrodlo prawdy") nadal reklamuje reprojekcje serwerowa dla kanalow
  `ARCGIS_IMAGE` CZ, mimo ze ADR-024 zakazuje jej uzycia takze dla przyszlych zrodel DE/SK; pole nie jest
  konsumowane przez zaden kod produkcyjny (tylko asercje w `tests/test_sources_registry.py:190,216`).
- Dowod: `grep -rn "server_reprojection" kartograf/` -> definicja (`descriptor.py:45`) + dwa `True` w registry;
  zero odczytow poza testami. `notes` obu kanalow puste.
- Weryfikacja: grep.
- Proponowana naprawa: dopisac w `notes` kanalu (albo w docstringu pola) zdanie z ADR-024
  ("serwer POTRAFI reprojektowac, ale Kartograf tego nie uzywa — gubi datum shift"), zeby kolejny silnik
  nie potraktowal flagi jako zaproszenia.
- Pewnosc: wysoka

### A3-11 [Minor] Brak walidacji zdegenerowanego/odwroconego bboxa na sciezce CZ
- Plik: `kartograf/providers/cuzk/client.py:139-140` (`max(1, round(...))`)
- Twierdzenie: `--country cz --bbox <max<min>` nie jest odrzucane — do serwera idzie zadanie `size=1,1`,
  a uzytkownik dostaje jednopikselowy plik zamiast bledu (`SheetIndex._validate_request_bbox` i
  `find_tiles_tm33_for_bbox` w innych miejscach taka koperte odrzucaja).
- Dowod: przebieg `--country cz --bbox -446000,-1113000,-447000,-1114000 --bbox-crs EPSG:5514`:
  `zadania do serwera: [('-446000,-1113000,-447000,-1114000', '1,1')]`.
- Weryfikacja: skrypt `h11.py` (mock `download_to`, podglad parametrow URL).
- Proponowana naprawa: sprawdzic `min_x < max_x and min_y < max_y` w `_cz_download_bbox` (albo w `export_image`)
  i zglosic `ValidationError`, tak jak robia to funkcje siatkowe.
- Pewnosc: wysoka

### A3-12 [Minor] Auto-split domyslnie miesza uklady pionowe (PL EVRF2007 vs CZ Bpv) w jednym `parent_request`
- Plik: `kartograf/cli/download_cmd.py:106-141` (`_resolve_pl_sentinels`) i `:1243-1244` (`vertical_crs = args.vertical_crs or "Bpv"`)
- Twierdzenie: bez jawnego `--vertical-crs` transgraniczne zadanie produkuje pliki roznice sie o ~0,13 m
  w pionie, zgrupowane wspolnym `parent_request` — czyli dokladnie w scenariuszu, dla ktorego to pole powstalo
  (scalanie szwu w Hydrografie); CLI nie ostrzega o tym ani slowem.
- Dowod: `_dispatch_area` przekazuje do obu galezi `vertical_crs=None`, a kazda rozwiazuje go po swojemu
  (PL -> `EVRF2007`, CZ -> `Bpv`); przebieg `h3.py` pokazuje `vertical=None` w obu galeziach przed rozwiazaniem.
- Weryfikacja: skrypt `h3.py` + lektura obu funkcji rozwiazujacych sentinele. Sidecary niosa prawdziwe kody
  (`EPSG:9651` vs `EPSG:8357`), wiec konsument moze to wykryc — stad Minor, a nie Important.
- Proponowana naprawa: w trybie auto-split z >1 krajem wypisac na stderr ostrzezenie o roznych ukladach pionowych
  (lub przyjac wspolny domyslny EVRF2007 dla zadan transgranicznych).
- Pewnosc: wysoka

### A3-13 [Minor] Sidecary LAZ w trybie `--bbox`/`--geometry` nie dostaja `extra.parent_request`
- Plik: `kartograf/cli/download_cmd.py:864-891` (`_write_laz_sidecar` — `extra` bez `parent_request`)
- Twierdzenie: CHANGELOG ("Sidecary PL w trybie `--bbox`/`--geometry` ... dostaja teraz dodatkowo
  `extra.parent_request`") i ADR-023 (f.1: "zawsze w trybie bbox/geometry") czytane doslownie obejmuja takze
  `--product laz`, ktory omija `_dispatch_area` i pisze sidecary wlasnym helperem.
- Dowod: `_cmd_download_laz` nigdy nie wola `_build_parent_request`; `_write_laz_sidecar` przekazuje
  `extra={"godlo_kafla", "rok", "gestosc", "url"}`.
- Weryfikacja: lektura + grep `parent_request` (brak w sciezce LAZ).
- Proponowana naprawa: albo dolozyc `parent_request` do sidecara LAZ (bbox zadania jest tam juz liczony),
  albo doprecyzowac w ADR/CHANGELOG, ze regula dotyczy produktow rastrowych NMT.
- Pewnosc: srednia (mozliwe, ze zakres reguly byl od poczatku wezszy)

## Pozytywy (krotko, max 5 punktow)
1. **ADR-024 dotrzymany**: `imageSR` w `_export_single` pochodzi wylacznie od `image_sr` przekazanego przez
   `_export_raster`, ktore w OBU galeziach ustawia `NATIVE_CRS`; nie znalazlem sciezki (godlo TM33, `--target-crs`,
   kafelkowanie), ktora wyslalaby do serwera uklad inny niz 5514. Warp lokalny wymusza przypieta operacje.
2. **Sidecar CZ zgodny z kontraktem** — sprawdzony end-to-end offline (`--country cz --bbox ... --target-crs EPSG:2180
   --vertical-crs EVRF2007`): `transform.horizontal = "pinned: ... (0.5 m)"`, `transform.vertical = "pinned: Baltic 1957
   height to EVRF2007 height (1) (0.1 m)"`, `vertical_crs = EPSG:5621`, `horizontal_crs = EPSG:2180`,
   `extra.parent_request` z ORYGINALNYM bboxem i lista krajow.
3. **Dyspozycja per kraj i kolizje flag**: 8 wywolan CLI (godlo CZ + `--target-crs`, godlo PL + `--target-crs`,
   `--country pl` z godlem TM33, SM5+2m, CZ+1m, CZ+`--system`, CZ+`--product orto`, CZ+KRON86) — wszystkie
   koncza sie kodem 1 i czytelnym komunikatem, zadne nie dotyka sieci; KRON86 dostaje remedium.
4. **Fail-fast przed transferem i atomowosc**: brak bezpiecznej operacji poziomej/pionowej przerywa przed
   pobraniem; `_warp_to_grid`, `_apply_vertical_shift` i `_extract_zip_pair` pisza przez plik tymczasowy
   + `os.replace` i sprzataja takze towarzyszacy `.tfw`. Kopiowanie `args` w `_dispatch_area` skutecznie izoluje
   sentinele PL od galezi CZ (sprawdzone przebiegiem: CZ widzi `resolution=None`).
5. **Filtr nadmiarowego wyboru w `SheetIndex`** jest przypiety testami na REALNYCH odpowiedziach serwera
   (`tests/fixtures/cuzk/klady_*`), a caly zestaw 343 testow CZ/CLI przechodzi (6,5 s).

## Podsumowanie liczbowe: C=1 I=4 M=8
