# A1-verify — weryfikacja ustalen raportu A1 (core / transform / transport / sources)

Weryfikator: V1. Galaz: `fix/release-0.7.0-audit`. Zaden plik repo nie zostal zmieniony.

**Stan srodowiska (istotny dla A1-2):** `pyproj 3.7.2`,
`PROJ_DATA=.venv/.../pyproj/proj_dir/share/proj`, `network: False`,
**zero plikow `*.tif` z siatkami** w katalogu danych PROJ. To wyjasnia, dlaczego E2E z
2026-08-11 (`docs/research/2026-08-11-etap1-e2e.md`) przechodzil na tej maszynie i nadal
przechodzi — sprzecznosci z A1-2 nie ma. Reprodukcje A1-2 wykonalem po skopiowaniu
`sk_gku_JTSK03_to_JTSK.tif` (183 kB, cdn.proj.org) do `~/.local/share/proj/` i **usunalem
plik po kazdym tescie** — srodowisko zostawiam w stanie zastanym (`ls ~/.local/share/proj`
= `cache.db`, `files.geojson`).

---

### A1-1 — Bledne mapowanie 1:200k <-> 1:500k w `get_parent()`/`get_children()`
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  N-34-7  bbox lon 21.000..21.500  -> parent N-34-A (lon 18..21)   # sprzecznosc
  N-34-61 bbox lon 18.000..18.500  -> parent N-34-B (lon 21..24)   # sprzecznosc
  petla po 1..144: "mismatched sheets: 72 /144" (bbox dziecka poza bboxem rodzica)
  SheetParser('N-34-A').get_all_descendants('1:10000'): 9216 arkuszy,
    union lon 18.00..24.00 lat 55.00..56.00 vs rodzic lon 18..21 lat 54..56
  .venv/bin/kartograf parse N-34-7 --hierarchy -> "N-34-7 -> N-34-A -> N-34"
  ```
- Uzasadnienie: `(nr-1)//36` tnie siatke 12x12 na **pasy po 3 wiersze** (pelna szerokosc 6°),
  a nie na cwiartki. Cwiartka to blok wierszy x kolumn: dla siatki 12x12 (ta, ktora kod
  etykietuje `1:200000`) cwiartka A = numery 1-6, 13-18, 25-30, 37-42, 49-54, 61-66; dla
  oficjalnej siatki 6x6 arkuszy 1:200000 byloby to I,II,III,VII,VIII,IX,XIII,XIV,XV — ten sam
  wzorzec. Testy `tests/test_sheet_parser.py:409-437,484-502` **nie** pokrywaja przypadku
  spornego poprawnie: `N-34-1->A`, `N-34-73->C`, `N-34-130->D` wychodza dobrze przypadkowo
  (leza w kolumnach 0-5 wlasciwej cwiartki), realnie bledne asercje to
  `test_get_parent_from_200k_section_b` (`N-34-37 -> N-34-B`, poprawnie `N-34-A`),
  `children[35] == "N-34-36"` dla A (poprawnie `N-34-66`) i `children[0] == "N-34-109"` dla D
  (poprawnie `N-34-79`). Zaden test nie sprawdza zawierania sie bboxow — stad "utrwalenie".
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/core/sheet_parser.py` — `_get_parent_from_200k()`
  (`row,col = divmod(nr-1,12)`, `letter = "ABCD"[(row>=6)*2 + (col>=6)]`) i
  `_get_children_from_500k()` (iteracja po bloku 6x6 zamiast `range(start,start+36)`).
  Test przypinajacy: nowy invariant "dla wszystkich 144 numerow bbox dziecka zawiera sie w
  bboxie `get_parent()`" + poprawka 3 asercji w `tests/test_sheet_parser.py`. Rozmiar: S
  (~20 linii kodu + testy). Ryzyko regresji: niskie — `find_sheets_for_bbox` nie uzywa tej
  sciezki (liczy siatke matematycznie), wiec tryby `--bbox`/`--geometry` sa nietkniete;
  zmienia sie wynik `get_parent`/`get_children`/`get_all_descendants`/`parse --hierarchy`
  wylacznie dla poziomow 1:1M i 1:500k (odnotowac w CHANGELOG).

### A1-2 — Brak `probe_point` w politykach produkcyjnych: przy siatkach PROJ pobranie CZ wybiera operacje zwracajaca inf
- Werdykt: CONFIRMED
- Reprodukcja (siatka `sk_gku_JTSK03_to_JTSK.tif` w `~/.local/share/proj/`, siec PROJ off):
  ```
  build_pinned_transform 5514->2180 (polityka = _HORIZONTAL_POLICY)
    WYBRANA: 0.051 | ... Inverse of S-JTSK [JTSK03] to S-JTSK (1) ... ; pipeline sk_gku: True
    CZ (-447000,-1114000) -> TransformError: Transformacja zwrocila wartosc nieskonczona
    ta sama polityka + probe_point=(-447000,-1114000) -> 0.5 m, wynik (472887.5, 208337.5)
  3045->5514 (=_ENVELOPE_POLICY): acc 0.051, sk_gku: True, probe -> TransformError
  kartograf download 302_5550 --country cz
    -> "Error: Transformacja zwrocila wartosc nieskonczona [... ETRS89 to S-JTSK [JTSK03] (1) ...]"
  kartograf download --bbox 18.55,49.60,18.56,49.61 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180
    -> niezlapany traceback: rasterio._err.CPLE_NotSupportedError: Cannot instantiate pipeline
       ... grids=sk_gku_JTSK03_to_JTSK.tif
  KONTROLA (po usunieciu siatki): kartograf download 302_5550 --country cz -> plik pobrany OK
  ```
- Uzasadnienie: `grep -rn "probe_point" kartograf/` — pole ustawiane wylacznie w testach,
  zadna z 4 polityk w `providers/cuzk/dmr.py` go nie ma, wiec regula 3 z docstringu
  `transform/crs.py` jest w produkcji martwa; `KNOWN_PATHS` obiecuje dla tej pary
  "probe odrzuca sk_gku (inf w CZ)". Zasieg jest wezszy niz "kazde pobranie CZ": dotkniete sa
  pary z S-JTSK po jednej stronie, czyli **godlo TM33** (3045<->5514) i **kazde `--target-crs`**
  (5514->cel); nietkniete `EPSG:5514->4326` (acc 1.0, bez siatki), `8357->5621` (0.1) oraz
  sciezka arkuszy SM5 (plik openzu bez warpu) — sprawdzone osobno.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/providers/cuzk/dmr.py` — `probe_point` dla polityk dotykajacych
  5514: staly punkt kontrolny w srodku Czech dla `_HORIZONTAL_POLICY` (zrodlo zawsze
  `NATIVE_CRS`), a dla `_ENVELOPE_POLICY` probe zalezny od danych (srodek przeliczanego bboxa
  — jest w `_bbox_to_crs`, w ukladzie zrodlowym, wiec dostepny bez dodatkowej transformacji);
  ewentualnie dodatkowo twarde wymaganie `probe_point` w `build_pinned_transform` dla par
  wskazanych w `KNOWN_PATHS`. Test przypinajacy: `tests/test_cuzk_dmr.py` z zamockowanym
  `TransformerGroup` (wzor `tests/test_transform_crs.py::test_probe_rejects_inf`) —
  operacja 0,051 m zwracajaca inf ma zostac odrzucona na rzecz 0,5 m; dodatkowo asercja, ze
  polityki CZ maja `probe_point is not None`. Rozmiar: M (~40-60 linii z testami).
  Ryzyko regresji: niskie — na maszynie bez siatek zbior kandydatow sie nie zmienia (probe
  tylko odrzuca), wiec obecne 1402 testy i biezace zachowanie pozostaja bez zmian.

### A1-3 — Shapefile z punktami wywraca `--geometry` niezlapanym `AttributeError`
- Werdykt: DOWNGRADE(Important)
- Reprodukcja:
  ```
  pyshp 3.0.3; Writer(shapeType=POINT), 2 punkty, .prj = PL-1992
  shapeType 1 -> hasattr(shape,'bbox') == False   (MULTIPOINT/typ 8 -> True)
  read_feature_bboxes(Path('pts.shp')) -> AttributeError: 'Point' object has no attribute 'bbox'
  kartograf download --geometry pts.shp --output out
    -> traceback ... geometry.py:143  AttributeError: 'Point' object has no attribute 'bbox'
  ```
- Uzasadnienie: blad realny i odtworzony, ale zasieg wezszy niz sugeruje raport i awaria jest
  **glosna** (traceback, kod != 0), nie cicha: brak `bbox` dotyczy wylacznie POINT/POINTZ/POINTM;
  MultiPoint, Polyline i Polygon maja `bbox` (sprawdzone). Nie ma decyzji projektowej, ktora by
  to tlumaczyla — ADR-015 wprost zaklada `shape.bbox` jako uniwersalne ("pyshp czyta .shp
  natywnie (shape.bbox)"), a SCOPE/README obiecuja SHP bez zastrzezen. Dlatego Important, nie
  Critical.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/core/geometry.py:143` — `bbox = getattr(shape, "bbox", None)`, a
  przy `None` zlozyc zdegenerowana obwiednie z `shape.points[0]` (`x,y,x,y`). Test przypinajacy:
  nowy test w `tests/test_geometry.py` tworzacy punktowy `.shp` przez `shapefile.Writer` i
  sprawdzajacy `read_feature_bboxes` + `find_sheets_for_geometry`. Rozmiar: S (<15 linii).
  Ryzyko regresji: niskie. Uwaga: bez naprawy A1-13 punkt lezacy dokladnie na linii siatki
  4°/6° nadal da pusta liste; przy zmianie konwencji z A1-7 zdegenerowany bbox trzeba
  obsluzyc jawnie, inaczej punkty przestana dawac jakikolwiek arkusz.

### A1-4 — Deskryptor `pl.gugik.nmt_1m` deklaruje kanal WCS dla EVRF2007, ktorego serwer nie ma
- Werdykt: DOWNGRADE(Important)
- Reprodukcja:
  ```
  GET .../WCS/DigitalTerrainModelFormatTIFFEVRF2007?REQUEST=GetCapabilities -> 404 (283 B)
  GET .../WCS/DigitalTerrainModelFormatTIFF          ?REQUEST=GetCapabilities -> 200 (7334 B)
  DownloadManager(output_dir=...).download_bbox(BBox(530000,382000,530500,382500,"EPSG:2180"),"evrf.tif")
    -> 3x "404 ... DigitalTerrainModelFormatTIFFEVRF2007" -> DownloadError
  ten sam bbox z vertical_crs="KRON86" -> OK, 1 001 205 B
  ```
- Uzasadnienie: fakt potwierdzony na zywo, ale to awaria glosna i sciezka **wylacznie
  biblioteczna**: `grep` pokazuje, ze `provider.download_bbox` woła tylko galaz CZ
  (`cli/download_cmd.py:1181`), a PL `--bbox` idzie przez skorowidz + OpenData. Dokumentacja
  (README:89-91, PRD:104/146/175, CLAUDE.md "Ograniczenia") o wycofaniu endpointu milczy, wiec
  poprawka docs jest obowiazkowa niezaleznie od zakresu kodu.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: (1) `kartograf/sources/registry.py:80-85` — kanal WCS zawezic do
  `("EPSG:9650",)` + `notes` o wycofaniu przez GUGiK (2026-08-11); (2)
  `kartograf/providers/pl/gugik.py` — `download_bbox` przy `vertical_crs="EVRF2007"` ma rzucac
  `ValidationError` z podpowiedzia ("uzyj KRON86 albo pobierz arkusze") zamiast 3x404;
  (3) README/PRD/CLAUDE.md — dopisac ograniczenie. **Uwaga do zakresu:**
  `tests/test_sources_registry.py:236-241` (`test_nmt_1m`) porownuje `vertical_crs_options`
  **kazdego** kanalu z jednym zbiorem providera, wiec musi zostac przerobiony na porownanie
  per-kanal — inaczej zawezenie deskryptora wysadzi ten test. Rozmiar: S/M. Ryzyko regresji:
  niskie (zmiana zamienia blad 404 na blad walidacji; sciezka CLI nietkniete).

### A1-5 — GPKG z geometria punktowa: wszystkie obiekty po cichu pomijane, komunikat mylacy
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  ogr2ogr -f GPKG pts.gpkg pts.shp   (GDAL systemowy)
  blob: len 29, flags 0x1, env_type 0
  read_feature_bboxes(Path('pts.gpkg')) -> []
  kartograf download --geometry pts.gpkg -> "Error: No features with geometry found in: ...pts.gpkg"
  ```
- Uzasadnienie: `_parse_gpkg_envelope` zwraca `None` dla `envelope_type == 0`, a GDAL/QGIS
  zapisuja punkty wlasnie tak (obwiednia w naglowku GPKG jest opcjonalna wg specyfikacji).
  Komunikat jest nieprawdziwy — geometria istnieje. ADR-015 przyznaje, ze parsowanie obwiedni
  "jest kruche", ale nie deklaruje pominiecia punktow jako decyzji, wiec to luka, nie design.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/core/geometry.py:62-63` — gdy `envelope_type == 0`, odczytac
  wspolrzedne z samego WKB dla POINT (naglowek GP: 8 bajtow + WKB byte order + typ 1 + 2x
  float64), a dla pozostalych typow rzucic `ValidationError` z jasnym komunikatem
  ("warstwa bez obwiedni w naglowku GPKG"). Test przypinajacy: `tests/test_geometry.py` z
  recznie zlozonym blobem `env_type=0` (bez zaleznosci od GDAL). Rozmiar: M (~30-40 linii).
  Ryzyko regresji: niskie — sciezka dotyka wylacznie blobow, ktore dzis sa odrzucane.

### A1-6 — `server_reprojection=True` w deskryptorach CZ jest sprzeczne z ADR-024 i nigdzie nie konsumowane
- Werdykt: DOWNGRADE(Minor)
- Reprodukcja: `grep -rn "server_reprojection" kartograf/ tests/` ->
  `descriptor.py:45` (definicja), `registry.py:240`, `registry.py:281`,
  `tests/test_sources_registry.py:61,190,210,216` (same asercje). Zero odczytow w
  providerach/managerach/CLI.
- Uzasadnienie: fakt potwierdzony, ale skutek zerowy w runtime — pole jest martwe. Zrodlo
  rozjazdu jest udokumentowane: spec etapu 1
  (`docs/superpowers/specs/2026-08-11-etap1-cz-fundament-dmr-design.md:175`) przewidywala
  `server_reprojection=True`, a errata z 2026-08-18 (tamze, pkt 1) i ADR-024 (DECISIONS.md:654)
  te sciezke uniewaznily — deskryptora przy erracie nie poprawiono. Skoro deskryptor jest wg
  ADR-022 zrodlem prawdy dla etapu 2 (DE/SK), warto poprawic, ale to nie jest blad
  uzytkownika — stad Minor.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/sources/registry.py:240,281` -> `server_reprojection=False` +
  `notes` ("serwer potrafi `imageSR`, ale ADR-024 zabrania — reprojekcja lokalna"); korekta
  asercji `tests/test_sources_registry.py:190,216`. Rozmiar: S (<10 linii). Ryzyko regresji:
  niskie (pole bez konsumenta).

### A1-7 — Niespojne traktowanie stykajacych sie krawedzi — bbox rowny arkuszowi daje 9 arkuszy zamiast 4
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  find_sheets_for_bbox(SheetParser('N-34-130-D').get_bbox('EPSG:4326'), '1:50000')
    -> 9: A-d, B-c, B-d, C-b, C-d, D-a, D-b, D-c, D-d
  find_sheets_for_bbox(SheetParser('N-34-130-D-d-2-4').get_bbox('EPSG:4326'), '1:10000') -> 4
  find_sheets_for_bbox(SheetParser('N-34-1').get_bbox('EPSG:4326'), '1:100000') -> 4 (poprawnie)
    -- asymetria: poziom 12x12 uzywa konwencji "dodatnie pole", nizsze "styk sie liczy"
  ```
- Uzasadnienie: `_bboxes_intersect` (`<`) traktuje styk jako przeciecie (co utrwala
  `tests/test_sheet_parser.py:916 test_touching_edge`), a `_find_1m_sheets`/`_find_200k_sheets`
  robia odwrotnie sztuczka `-1e-10`. W DECISIONS.md nie ma decyzji o konwencji krawedzi —
  ADR-010 opisuje tylko algorytm — wiec to niespojnosc, nie design. Skutek praktyczny:
  2-4x wiecej plikow ASC dla bboxa wyrownanego do siatki, a taki bbox produkuje sam
  `SheetParser.get_bbox()`.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/core/sheet_parser.py:845` — wymagac dodatniego pola przeciecia
  z tolerancja (`a.max_x <= b.min_x + 1e-9 or ...`), z jawnym wyjatkiem dla bboxa
  zdegenerowanego (punkt — patrz A1-3/A1-13); sztuczki `-1e-10` moga zostac (daja ten sam
  wynik). **Zmierzony koszt regresji:** uruchomilem cala suite z podmieniona funkcja
  (plugin pytest w scratchpadzie, bez modyfikacji repo) — `1 failed, 1401 passed`, jedyna
  porazka to `test_touching_edge`, ktory trzeba przepisac; po zmianie bbox `N-34-130-D` daje
  dokladnie 4 arkusze, a bbox `N-34-130-D-d-2-4` — 1. Test przypinajacy: te dwa przypadki.
  Rozmiar: S (<20 linii). Ryzyko regresji: srednie — zmienia sie widoczny wynik publicznej
  `find_sheets_for_bbox` (wpis do CHANGELOG jako zmiana zachowania).

### A1-8 — Etykiety skal PL-1992 sa przesuniete o jeden poziom wzgledem GUGiK
- Werdykt: CONFIRMED
- Reprodukcja (WMS GetFeatureInfo na zywo, warstwa `SkorowidzeNMT2023iStarsze`,
  endpoint `.../NMT/WMS/SkorowidzeUkladEVRF2007`):
  ```
  skor_NMT_wg_akt.push({url:"...M-34-27-B-b-2-3.asc", godlo:"M-34-27-B-b-2-3", ...,
     charakterystykaPrzestrzenna:"1.00 m", modulArchiwizacji:"1:5000", aktualnoscRok:"2022"})
  SheetParser('M-34-27-B-b-2-3').scale == '1:10000'
  wymiary z kodu: '1:200000' -> 20' x 30' (standard 1:100000), '1:10000' -> 1.25' x 1.875' (standard 1:5000)
  ```
- Uzasadnienie: potwierdzone niezaleznie od raportu (wlasne zapytanie GetFeatureInfo +
  przeliczenie wymiarow wszystkich siedmiu poziomow). Oficjalny podzial: 1:500k = cwiartka
  1:1M (A-D), 1:200k = 1/36 (I-XXXVI), 1:100k = 1/144 (1-144) — kod etykietuje siatke 1-144
  jako `1:200000`, wiec brakuje w hierarchii prawdziwego poziomu 1:200000. Zmiana etykiet
  lamie publiczne API, CLI (`--scale`) i cala dokumentacje, wiec do 0.7.0 tylko opis.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: docstring `SheetParser` + `docs/SCOPE.md` (sekcja o godlach) — jawna nota
  "etykiety skal Kartografu sa o jeden poziom drobniejsze niz nomenklatura GUGiK: 7-czlonowe
  godlo = modul archiwizacji 1:5000, 3-czlonowe = arkusz 1:100000", plus zapowiedz aliasow w
  kolejnej wersji major. Test przypinajacy: brak (docs). Rozmiar: S. Ryzyko regresji: zadne.

### A1-9 — Arkusze PL-2000 laduja w `nmt_1m/`, choc dokumentacja i ADR obiecuja `nmt_2000_1m/`
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  FileStorage('./data', resolution='1m').get_path('6.179.12.20','.asc')
    -> data/nmt_1m/6/179/12/20/6.179.12.20.asc
  grep -rn "nmt_2000" kartograf/  -> tylko docstring storage.py:32-33
  grep "product=" kartograf/cli/download_cmd.py, download/manager.py:186
    -> produkcyjnie tylko nmpt/orto/laz/subdir(CZ) albo resolution; nigdy nmt_2000_*
  ```
- Uzasadnienie: rozjazd realny. Sprostowanie do raportu: obietnica jest w **ADR-017**
  (`docs/DECISIONS.md:299`, "FileStorage: podkatalog `nmt_2000_1m` dla PL-2000 arkuszy"),
  nie w ADR-018 (ten dotyczy ThreadPoolExecutor); `docs/CHANGELOG.md:342` powtarza obietnice.
  Skutek jest wylacznie organizacyjny — nazwy plikow PL-2000 (z kropkami) nie koliduja z
  PL-1992 (z myslnikami), wiec nic sie nie nadpisuje.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `kartograf/download/storage.py:31-33` (docstring), `docs/CHANGELOG.md:342`
  i konsekwencje ADR-017 — opisac stan faktyczny (PL-2000 w `nmt_<res>`), ewentualnie dopisac,
  ze rozdzielenie katalogow jest odlozone. Wariant kodowy (dispatch w `FileStorage._subdir`
  przez `parser_registry.detect_system(godlo)`) jest rowniez maly (S), ale zmienia uklad
  katalogow u istniejacych uzytkownikow (istniejace pliki przestaja byc widziane przez
  `skip_existing`), wiec na 0.7.0 rekomenduje wariant docs. Rozmiar: S. Ryzyko regresji: zadne.

---

## Tabela

| ID | Werdykt | Naprawa 0.7.0 | Rozmiar | Ryzyko |
|---|---|---|---|---|
| A1-1 | CONFIRMED | TAK | S | niskie |
| A1-2 | CONFIRMED | TAK | M | niskie |
| A1-3 | DOWNGRADE(Important) | TAK | S | niskie |
| A1-4 | DOWNGRADE(Important) | TAK | S/M | niskie |
| A1-5 | CONFIRMED | TAK | M | niskie |
| A1-6 | DOWNGRADE(Minor) | TAK | S | niskie |
| A1-7 | CONFIRMED | TAK | S | srednie |
| A1-8 | CONFIRMED | DOCS-ONLY | S | zadne |
| A1-9 | CONFIRMED | DOCS-ONLY | S | zadne |

## Nowe ustalenia przy okazji (max 3, tylko jesli Critical/Important i z dowodem)

### N1 [Important] `main()` nie ma bariery na wyjatki spoza `KartografError` — uzytkownik dostaje traceback zamiast komunikatu
- Plik: `kartograf/cli/commands.py:67-105` (`main()` — brak `try/except`), lokalne handlery
  lapia tylko `(DownloadError, ValidationError)` (np. `cli/download_cmd.py:1097`).
- Dowod (dwie niezalezne reprodukcje, obie z tej weryfikacji):
  1. `kartograf download --geometry pts.shp` -> `AttributeError: 'Point' object has no
     attribute 'bbox'` (pelny traceback, exit != 0);
  2. `kartograf download --bbox ... --country cz --target-crs EPSG:2180` (z siatka PROJ) ->
     `rasterio._err.CPLE_NotSupportedError: Cannot instantiate pipeline ...` (pelny traceback).
  Kazdy blad rasterio/GDAL (uszkodzony plik, brak miejsca, nieczytelny raster) wyjdzie tak samo.
- Sugestia: `try/except KartografError` -> komunikat + `except Exception` -> jednolinijkowy
  komunikat z podpowiedzia `--debug`/`KARTOGRAF_DEBUG=1` dla pelnego traceback w `main()`.
  Rozmiar S, ryzyko niskie; niezalezne od napraw A1-2/A1-3 (te usuwaja przyczyny, nie objaw).
