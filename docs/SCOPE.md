# SCOPE.md - Zakres Projektu Kartograf
**Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 3.23
**Data:** 2026-10-13
**Status:** Kod v0.8.0-dev (wydanie 0.8.0 w przygotowaniu; ostatnie wydanie v0.7.2, 2026-10-11)

---

## 1. Cel Projektu

**Kartograf** to narzędzie do pobierania danych przestrzennych z zasobów GUGiK i CUZK (NMT), Copernicus i ISRIC dla Polski, a od etapu 1 (v0.7.0) — częściowo dla Czech (pełna parytetowość produktowa DMR, planowana dalsza dla DE/SK).

### 1.1 Problem

Pobieranie danych przestrzennych z różnych źródeł wymaga:
- Znajomości systemów identyfikacji (godła, TERYT, bbox)
- Nawigowania przez różne interfejsy webowe i API
- Ręcznej organizacji pobranych plików
- Różnych protokołów autentykacji (OAuth2, API keys)

### 1.2 Rozwiązanie

Kartograf automatyzuje ten proces oferując:
- **Unified API** - jednolity interfejs dla różnych źródeł danych
- **Parser godeł** - walidacja i parsowanie godeł map topograficznych
- **Providery danych** - abstrakcja nad różnymi serwisami (GUGiK, Copernicus, ISRIC)
- **Selekcja obszaru** - godło, TERYT, bbox, plik geometrii (SHP/GPKG)
- **Automatyczne pobieranie** - pobieranie wielu plików jedną komendą
- **Organizacja plików** - automatyczna struktura katalogów

### 1.3 Użytkownicy

1. **Deweloperzy Hydrograf/Hydrolog** - integracja jako biblioteka Python
2. **Specjaliści GIS** - CLI do pobierania danych
3. **Hydrolodzy** - dane glebowe i HSG dla metody SCS-CN

---

## 2. Zakres - Wersja 0.8.0

### 2.1 NMT (Numeryczny Model Terenu) - IN SCOPE

```python
# Funkcjonalności:
- Parser godeł PL-1992 (SheetParser): skale 1:1M do 1:10k
- Parser godeł PL-2000 (Parser2000): skale 1:10k do 1:500, 4 strefy (EPSG:2176-2179)
- Auto-detekcja systemu: SheetParser automatycznie rozpoznaje PL-1992 vs PL-2000
- Hierarchia arkuszy (get_parent, get_children, get_all_descendants)
- Bounding box arkusza (EPSG:2180, EPSG:4326, EPSG:2176-2179)
- Reverse lookup: bbox → godła (find_sheets_for_bbox, find_sheets_2000_for_bbox)
- Reverse lookup: geometry file → godła (find_sheets_for_geometry)
- Selekcja obszaru: godło, bbox, plik geometrii (SHP/GPKG)
- Pobieranie przez godło → ASC (OpenData)
- `provider.download_bbox` (poza magazynem wersji): NMT 1 m KRON86
  (TIFF float32), EVRF2007 i NMPT (ASC multipart -> jednopasmowy GeoTIFF
  float32 z wysokosciami), bbox wyrownany do siatki 1 m EPSG:2180;
  `DownloadManager.download_bbox` usuniete w 0.8.0 (D27).
  CLI `--bbox` bez `--cutout`: arkusze OpenData.
- Wycinek bbox z WCS GUGiK: `--cutout --horizontal-crs {EPSG:2180,EPSG:5514,
  EPSG:3045}` w trybie `--bbox`/`--geometry` dla NMT **i NMPT** 1 m
  (`download_pl_cutout`/`check_pl_cutout`; w CLI przez `download_data`);
  maska ladu PRG `A00 - W02 - W03` i nodata -9999 poza ladem,
  0,0 na ladzie zachowane; bbox wyrownany NA ZEWNATRZ do siatki
  arkuszy 1 m (`k + 0,5`), lokalna przypieta reprojekcja.
  WCS pokazuje kompozycje lotow serwera, niekoniecznie najnowszy
  arkusz dokladnie 1 m wg ADR-028; dla lotow 0,5 m wynik 1 m
  jest decymacja. Od 0.8.0 `bbox/<coords>.tif` bez daty jest
  dowiazaniem do wersji; domyslnie lokalna wersja bez zapytan PRG/WCS,
  `--force` pobiera ponownie (ta sama tresc = bez zmian).
  Brak wyboru kampanii/roku, 5 m z `--cutout` = `Error:`;
  5 m pozostaje dostepne jako arkusze bez tej flagi.
- Rozdzielczości: 1m (GRID1), 5m (GRID5)
- Układy wysokościowe: KRON86, EVRF2007
- Godło PL-2000 1:10000: w CLI i `download_data` `--scale` jest wymagane
  (błąd przed siecią, lista skal); provider/`DownloadManager` wywołany
  bez skali, gdy GUGiK ma wyłącznie arkusze potomne, daje `NoCoverageError`
  z podpowiedzią `--scale 1:2000` (bez cichego pobrania zastępczego PL-1992)

# Źródło: GUGiK (Główny Urząd Geodezji i Kartografii)
# API: WCS, WMS GetFeatureInfo, OpenData
```

**Etykiety skal (PL-1992).** Etykiety skal Kartografu są o jeden poziom
drobniejsze niż nomenklatura GUGiK: 7-członowe godło (N-34-130-D-d-2-4) ma tu
etykietę `1:10000`, a u GUGiK jest modułem archiwizacji 1:5000; siatka 1-144
(etykieta `1:200000`) ma wymiary oficjalnego arkusza 1:100000 (20' x 30').
Etykiety zostają dla zgodności publicznego API i CLI `--scale`; aliasy
planowane w następnej wersji major (patrz docstring `SheetParser`).

**Konwencja krawędzi.** `find_sheets_for_bbox` / `find_sheets_for_geometry`
wymagają dodatniego pola przecięcia — stykające się krawędzie NIE są
przecięciem. Bbox równy arkuszowi w EPSG:4326 zwraca więc tylko jego własne
arkusze (`N-34-130-D` w skali 1:50000 → 4, nie 9); w EPSG:2180 (domyślny
`--bbox-crs`) obwiednia arkusza przechodzi przez szerszą obwiednię WGS84
i obejmuje fragmenty sąsiadów (16 zamiast 4). Bbox zdegenerowany do punktu →
dokładnie jeden arkusz. Nieznana wartość `sheet_system=` to `ValidationError`.

### 2.2 NMT — Czechy (CUZK, etap 1, v0.7.0) - IN SCOPE

```python
# Funkcjonalności (DMR — Digitalni model reliefu, odpowiednik NMT):
- DMR 5G (rozdzielczość 2m) — pobieranie po godle TM33 (siatka 2x2 km,
  EPSG:3045, obliczalna) LUB po bbox przez exportImage (ArcGIS ImageServer)
- DMR 4G (rozdzielczość 5m) — pobieranie po godle SM5 (indeks arkuszy
  KladyMapovychListu, EPSG:5514; arkusz istnieje tylko w 5m, więc CLI bez
  `--resolution` pobiera 5m, a `--resolution 2m` z godłem SM5 to błąd)
  LUB po bbox przez exportImage
- Selekcja obszaru: godło (TM33/SM5), bbox, plik geometrii — `--country
  {pl,cz,auto}`; `auto` wykrywa kraj z godła/bboxa, dzieli bbox/geometrię
  transgraniczną na osobne pliki per kraj (bez scalania — dziś scala
  konsument, np. Hydrograf; scalanie PL+CZ w jedną powierzchnię to etap 2,
  R6 — sekcja 3.1). Obszar sięgający CZ jest zawsze wycinkiem i wymaga
  `--cutout --horizontal-crs` (ADR-038); pod `auto` część PL jest wtedy
  wycinkiem WCS
- Reprojekcja pozioma **lokalna** (rasterio.warp + przypięta operacja; serwer
  dostaje żądania wyłącznie w natywnym EPSG:5514 — ADR-024):
  `--cutout --horizontal-crs {EPSG:2180,EPSG:5514,EPSG:3045}` (natywnie
  `EPSG:5514`) — tylko w trybie `--bbox`/`--geometry` (z godłem = błąd)
  krok datum S-JTSK → ETRS89 przypięty do czeskich operacji EPSG:1622/1623
  (dokładność deklarowana 1,0 m; ADR-024 errata 2)
- Układ wysokościowy natywny: Bpv (Baltic 1957, EPSG:8357); opcjonalna
  transformacja do EVRF2007 (EPSG:5621, przypięta operacja 0,1 m); KRON86
  nieosiągalny (brak publicznych siatek Bpv→KRON86)
- `extra.parent_request` w sidecarach trybu bbox/geometry — grupowanie
  plików jednego zadania po obu stronach granicy PL/CZ

# Źródło: CUZK (Český úřad zeměměřický a katastrální)
# API: ArcGIS REST (query, exportImage) + pliki openzu (ZIP z TIFF+TFW)
# Licencja: CC BY 4.0
```

**Poza zakresem etapu 1 (planowane — etap 2/3):** DMP (Digitalni model
povrchu, odpowiednik NMPT), Ortofoto CZ, LAZ/LIDAR CZ (etap 2); ZABAGED
(wektorowa baza topograficzna, odpowiednik BDOT10k, 149 warstw — etap 3).
Wielokąt granicy administracyjnej (zamiast prostokątnej obwiedni kraju) —
patrz sekcja 3.2, znane ograniczenie.

### 2.3 NMPT (Numeryczny Model Pokrycia Terenu) - IN SCOPE

```python
# Funkcjonalności:
- Digital Surface Model (DSM) — teren + obiekty (drzewa, budynki)
- Pobieranie przez godło → ASC (OpenData)
- Pobieranie przez bbox z biblioteki (`provider.download_bbox`) -> GeoTIFF
  float32 z wysokosciami WCS (ASC multipart);
  CLI `--bbox` bez `--cutout` pobiera arkusze OpenData,
  z `--cutout --horizontal-crs` wycinek WCS z maska ladu
- Rozdzielczość: tylko 1m
- Układy wysokościowe: KRON86, EVRF2007
- Dziedziczenie z GugikProvider (wspólna logika pobierania)

# Źródło: GUGiK
# API: WCS, WMS GetFeatureInfo, OpenData
```

### 2.4 Ortofotomapa - IN SCOPE

```python
# Funkcjonalności:
- Zdjęcia lotnicze Standard Resolution (25cm)
- Pobieranie przez godło → TIF (OpenData)
- Pobieranie przez bbox → GeoTIFF (WCS) — z biblioteki (`provider.download_bbox`, poza magazynem);
  CLI `--bbox` pobiera arkusze OpenData
- Brak vertical CRS (2D RGB); najnowszy zgodny rekord wariantu `color`
  (`RGB`/`CIR`/`B/W`, wymagany w API; CLI pobiera RGB) z
  GetCapabilities/GetFeatureInfo; `GugikOrtoProvider(color="CIR")` wybiera
  wariant podczerwieni
- Obsługa formatów WCS: GTiff, PNG, JPEG

# Źródło: GUGiK
# API: WCS, WMS GetFeatureInfo, OpenData
```

### 2.5 LAZ (Chmury Punktów LIDAR) - IN SCOPE

```python
# Funkcjonalności:
- Chmury punktów ALS (dane pomiarowe LIDAR), format .laz
- Discovery area-based przez godło (≤1:10000) / bbox / geometry → WFS
  GetFeature, bbox i envelope w porządku osi EPSG (N,E), filtr przecięcia;
  błąd jednego rocznika przerywa odkrywanie (`DownloadError`)
- Kafle drobniejsze niż 1:10000 (jedno godło 1:10000 → wiele kafli .laz)
- url_do_pobrania brany wprost z atrybutu WFS (godło kafla nieparsowane)
- Domyślnie najnowszy kafel per obszar (ADR-029); flagi --year/--min-year/--max-year
  (przedział lat, ADR-032), --vertical-crs, --min-density, --all-campaigns (sekcja 2.12)
- Dwa układy wysokościowe (wybór wymagany od 0.8.0): EVRF2007 (2018+), KRON86 (legacy, 2010-2019)
- Pobieranie równoległe (--workers); kafle jako wersje w magazynie
  (ADR-036 D26): kafel z lokalną wersją nie jest pobierany ponownie,
  nowszy nalot (inne pliki) pobiera się domyślnie; --check-updates,
  --upgrade, --force, --plan
- Biblioteka: download_data(product="laz", ...) (= CLI) albo
  download_laz_area (bbox w dowolnym układzie; wybór + pobranie + sidecary,
  wynik LazDownloadResult: files/failed/superseded/stale/notices) i
  check_laz_area (plan bez pobierania)
- Porażka choć jednego kafla = Error: z pełną listą, kod 1 (pobrane zostają)

# Źródło: GUGiK
# API: WFS (GetCapabilities + GetFeature), OpenData
```

### 2.6 Land Cover (Pokrycie Terenu) - IN SCOPE

```python
# BDOT10k (GUGiK):
- 15 warstw (12 pokrycia terenu PT* + 3 hydrograficzne SW*)
- Pobieranie całego pakietu powiatu; w GPKG opcjonalny filtr warstw
  (`--layers`/`layers=`, np. SWRS,PTWP) i oryginalny ZIP (`--keep-raw`)
- Pobieranie przez TERYT (powiat)
- Pobieranie przez godło, bbox (dowolny obsługiwany układ, `--bbox-crs`)
  lub geometrię — pakiet KAŻDEGO powiatu obszaru (`--workers` równolegle)
- Format: GeoPackage (domyślny) albo Shapefile (archiwum .zip, bez rozpakowania)
- Automatyczne scalanie warstw z zachowaniem rtree spatial index; GPKG
  składany w lokalnym katalogu tymczasowym i przenoszony do magazynu
  (SQLite nie pisze na udziale sieciowym — działa na CIFS/SMB bez blokad
  zakresów bajtów)
- Magazyn wersji (0.8.0): landcover/pl_bdot10k_gpkg[_<warstwy>]/teryt/<T>,
  sygnał: brak (lokalna wersja niesprawdzona, --force pobiera); keep_raw =
  osobna wersja ZIP; obszar = każdy powiat (LandCoverAreaResult), błąd per powiat

# CORINE Land Cover (Copernicus):
- 44 klasy pokrycia terenu
- Lata: 1990, 2000, 2006, 2012, 2018
- Pobieranie przez godło, bbox lub geometrię (bez TERYT)
- Format: GeoTIFF (CLMS API) lub PNG (WMS fallback: EEA Discomap, dla 1990
  DLR; sidecar extra.fallback = "wms_png")
- OAuth2 RSA authentication (opcjonalne; CLMS_CREDENTIALS na każdym systemie,
  Keychain tylko macOS)
- Auth Proxy dla izolacji credentials
- Magazyn wersji (0.8.0): CLMS w landcover/eu_corine_<rok>/ z etykietą
  wydania z katalogu CLMS (sygnał metadata), podgląd WMS osobno
  w landcover/eu_corine_<rok>_preview/ (etykieta = data pobrania)

# Wszystkie źródła land cover: sidecar wersji <plik>.meta.json (sekcja 2.11)
```

### 2.7 SoilGrids (Dane Glebowe) - IN SCOPE

```python
# ISRIC SoilGrids:
- 11 parametrów glebowych (clay, sand, silt, soc, pH, etc.)
- 6 głębokości (0-5cm do 100-200cm)
- 5 statystyk (mean, Q0.05, Q0.5, Q0.95, uncertainty)
- Rozdzielczość: 250m (globalne)
- Pobieranie przez godło, bbox lub geometrię (BEZ TERYT — patrz 3.2)
- Format: GeoTIFF
- Magazyn wersji (0.8.0): soil/global_soilgrids_<wł>_<gł>_<stat>/,
  etykieta = wydanie SoilGrids z GetCapabilities (sygnał metadata)

# Źródło: ISRIC (International Soil Reference and Information Centre)
# API: WCS
```

### 2.8 HSG (Hydrologic Soil Groups) - IN SCOPE

```python
# Kalkulacja HSG dla metody SCS-CN:
- Klasyfikacja tekstury wg trójkąta USDA (12 klas)
- Mapowanie tekstury → HSG (A, B, C, D)
- Wejścia clay/sand/silt = wersje SoilGrids w tym samym magazynie
  (brakujące pobierane); te same wejścia = wersja HSG użyta ponownie
- Statystyki pokrycia dla każdej grupy
- Format wyjściowy: GeoTIFF (wartości 1-4, 0 = nodata) w
  hsg/global_soilgrids_<gł>_<stat>/
- Selekcja: --sheet, --bbox, --geometry
- Sidecar wersji <plik>.meta.json (extra.derived = "hsg", warstwy źródłowe,
  głębokość, statystyka, kody klas, source_files z sha256 wejść)

# Moduł: kartograf.hydrology.hsg
```

### 2.9 CLI Interface - IN SCOPE

```bash
# Komendy:
kartograf parse <godlo>                    # info o godle (PL-1992 lub PL-2000)
kartograf parse 6.179.12.20               # PL-2000 auto-detekcja
kartograf elevation download --sheet <godlo> --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # pobierz NMT
kartograf elevation download --sheet <godlo> --product nmpt --vertical-crs EVRF2007 -o ./data # pobierz NMPT
kartograf imagery download --sheet <godlo> --product orto -o ./data # pobierz ortofoto
kartograf elevation download --sheet <godlo> --product laz --vertical-crs EVRF2007 -o ./data # pobierz chmury punktów LAZ (wiele kafli)
kartograf elevation download --bbox ... --product laz --year 2024 --min-density 12 --country pl --vertical-crs EVRF2007 -o ./data
kartograf elevation download --bbox min_x,min_y,max_x,max_y --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data # NMT dla bbox
kartograf elevation download --bbox ... --sheet-system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 -o ./data # NMT w ukladzie PL-2000 (arkusze 1:2000)
kartograf imagery download --bbox ... --product orto --country pl --sheet-system 1992 -o ./data # ortofoto dla bbox
kartograf elevation download --geometry area.shp --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data # NMT z pliku geometrii
kartograf elevation download --geometry area.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
kartograf elevation download --sheet <godlo> --resolution 5m --product nmt --vertical-crs EVRF2007 -o ./data # NMT 5m
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv -o ./data # DMR 5G (CZ), godlo TM33
kartograf elevation download --sheet CTES96 --product nmt --vertical-crs Bpv -o ./data # DMR 4G (CZ, 5m), godlo SM5, kraj z godla
kartograf elevation download --bbox ... --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:5514 --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv -o ./data # bbox transgraniczny -> wycinek per kraj
kartograf elevation download --bbox ... --country cz --cutout --horizontal-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv -o ./data # reprojekcja lokalna (pinned)
kartograf elevation download --bbox ... --country pl --cutout --horizontal-crs EPSG:2180 --product nmt --vertical-crs EVRF2007 -o ./data # wycinek NMT/NMPT 1 m WCS + maska PRG (ADR-035)
kartograf elevation download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m -o ./data # Bpv -> EVRF2007 (EPSG:5621)
kartograf elevation download --sheet <godlo> --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # wszystkie kampanie GUGiK arkusza (ADR-030)
kartograf elevation download --sheet <godlo> --year 2025 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # najnowszy lot z roku (ADR-032)
kartograf elevation download --sheet <godlo> --year 2025 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # wszystkie loty z roku
kartograf elevation download --sheet <godlo> --min-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # najnowszy lot, nie starszy niż rok
kartograf elevation download --bbox ... --max-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data # najnowszy lot do roku (dowiązanie nigdy wstecz)
kartograf elevation download --bbox ... --product laz --all-campaigns --country pl --vertical-crs EVRF2007 -o ./data # LAZ bez deduplikacji pokrycia
kartograf landcover download --source bdot10k --teryt <kod> -o ./data  # obszar: --bbox [--bbox-crs] / --sheet / --geometry; --layers, --keep-raw, --workers, -q
kartograf landcover download --source corine --sheet <arkusz> -o ./data --year 2018
kartograf soil download --property <param> -o ./data --depth 0-5cm --stat mean # --sheet/--bbox (bez --teryt)
kartograf landcover list-sources
kartograf landcover list-layers --source <source>
kartograf soil hsg --sheet <arkusz> -o ./data --depth 0-5cm # oblicz HSG z wersji SoilGrids
kartograf cache stats|clear|path           # cache metadanych (SQLite)
# Pełna lista opcji: kartograf <grupa> <komenda> --help
```

### 2.10 Python API - IN SCOPE

```python
# Public API — źródło prawdy: kartograf/__init__.py (__all__); lista poniżej
# jest z nim zgodna i aktualizowana razem z nim.
from kartograf import (
    # Cache
    MetadataCache,
    # Notices
    Notice,
    # Core
    SheetParser, Parser2000, ParserTM33, BBox, find_sheets_for_bbox,
    find_sheets_2000_for_bbox, find_sheets_for_geometry, get_overall_bbox,
    transform_bbox, parent_request_for,
    # Download (command level: `kartograf elevation download` / `imagery download`, spec 4.1)
    download_data, check_data, DataReport, UnitFile, UnitFailure,
    # Download (NMT)
    DownloadManager, DownloadProgress, DownloadResult, CampaignRef, FileStorage,
    # Download (versioned store, update plan)
    UpdateMode, VersionedFile, VersionRef, PlanItem, UpdatePlan,
    # Download (PL cutout: WCS ADR-035)
    PlCutoutResult, check_pl_cutout, download_pl_cutout,
    # Download (CZ cutout, countries)
    CountryPart, countries_for_bbox, split_bbox_by_country, CzCutoutResult,
    check_cz_cutout, download_cz_cutout,
    # Download (CZ sheet: SM5 sheet / TM33 tile, R4)
    CzSheetResult, check_cz_sheet, download_cz_sheet,
    # Download (LAZ tiles, D17)
    LazDownloadResult, LazTileFailure, check_laz_area, download_laz_area,
    # Land Cover
    LandCoverManager, LandCoverResult, LandCoverAreaResult, LandCoverFailure,
    Edition,
    # Providers
    BaseProvider, GugikProvider, GugikNmptProvider, GugikOrtoProvider,
    GugikLazProvider, LazTile, LazTileSelection, SupersededLazTile,
    LandCoverProvider, Bdot10kProvider, Bdot10kPackage, CorineProvider,
    SoilGridsProvider, CuzkDmrProvider, create_dmr_provider,
    # TERYT (PRG)
    discover_teryts_for_bbox, teryt_for_point,
    # Hydrology
    HSGCalculator, HsgResult, hsg_from_rasters,
    # Transport and mosaic (stable since 0.7.1)
    get_with_retry, make_gugik_session, mosaic_and_crop, check_source_grid,
    # Exceptions
    KartografError, ParseError, ValidationError, DownloadError, NoCoverageError,
    YearRangeError, CacheError,
    # Version
    __version__,
)
```

### 2.11 Układ danych na dysku - IN SCOPE

- `data/<produkt>/<kraj>_<układ>[_<wariant>][_<vcrs>]/...` (ADR-026);
  kanoniczna tabela segmentów i migracja 0.6.x→0.7.0:
  `docs/ARCHITECTURE.md` sekcja 3
- Wycinki CZ i wycinki PL NMT/NMPT 1 m (tylko z `--cutout`; bez
  tej flagi PL zapisuje arkusze w hierarchii godel) w
  `<segment>/bbox/<coords>.tif` — dowiazanie do wersji w
  `<segment>/versions/bbox/` (D15)
- `<układ>` w segmencie (`pl_1992` vs `pl_2000`) rozstrzyga format godła
  każdego pliku z osobna — jeden stary katalog (np. `orto/`) rozchodzi się
  przy migracji na dwa segmenty; wyjątek: kafle LAZ — układ z `uklad_xy`
  kafla (`LazTile.system`), dopiero w drugiej kolejności z formatu godła
- Magazyn wersjonowany (ADR-036, od 0.8.0; arkusze PL NMT/NMPT/orto,
  kafle LAZ, arkusze i wycinki CZ, wycinki PL, land cover i HSG): prawdziwe pliki w
  `<segment>/versions/<hierarchia>/<data>_<id>_<sha8>/...`, niezmienne
  (sidecar wersji pisany raz, zapis wylaczny), sciezka standardowa =
  hardlink do najnowszej lokalnej wersji (bez kopii i symlinkow; system
  plikow z hardlinkami wymagany); `kampanie/` z 0.7.x bez migracji;
  tryby `--check-updates`/`--upgrade`/`--force`, plan `kartograf-plan/1`
  dla kazdego toru `elevation download`, `imagery download`, `landcover download`, `soil download` i `soil hsg`
  (sygnal swiezosci per kanal: skorowidz, rekord WFS, `ETag` SM5,
  wydanie SoilGrids/CORINE CLMS, brak dla WCS/`exportImage`/BDOT10k)
- Drugie dowiązanie `<segment>/full_sheet/<hierarchia>/<godło>.<ext>` do
  najnowszego lokalnego lotu pełnego (ADR-033); `list_files()` je pomija,
  `delete()` usuwa oba dowiązania
- Land cover i HSG w segmentach `landcover/`, `soil/`, `hsg/` (spec 3.4,
  ARCHITECTURE 3.3 regula 8); `--output` = korzen magazynu
- Każde udane pobranie (CLI, DownloadManager, LandCoverManager,
  download_pl_cutout, download_laz_area) i wynik HSG ma sidecar
  `<plik>.meta.json` (schemat `kartograf-meta/1`, best-effort); sidecar
  wersji jest obowiązkowy (porażka zapisu = brak wersji)

### 2.12 Kampanie GUGiK (ADR-030) - IN SCOPE

```python
# Strategie (tylko PL; CZ zawsze bieżąca mozaika):
- Bez `--all-campaigns` (domyślnie): najnowszy rekord skorowidza (ADR-028)
  w zakresie lat, sprawdzany przy każdym uruchomieniu po wygaśnięciu cache (7 dni)
- `--all-campaigns`: każda kampania arkusza (w zakresie lat) po twardym filtrze ADR-028
- Rok danych (ADR-032; NMT/NMPT/orto: aktualnosc, LAZ: akt_rok):
  --year RRRR = --min-year RRRR --max-year RRRR; flagi roku wyznaczają tylko
  dopuszczalne lata, --all-campaigns liczbę lotów (model A; każda kombinacja dozwolona)
- Najpierw sprawdzenie pełnej listy kampanii każdego arkusza, potem pobranie:
  arkusz z danymi tylko z innych lat = Error: z latami i podpowiedzią, nic nie
  pobrane; arkusz bez danych = Warning: (pominięty); awaria skorowidza = Error:
  (wyjątek: lokalna wersja, punkt niżej)
- Kilka lotów w przedziale (all): pomiar pokrycia gdy najnowszy niepełny;
  Info: + extra.better_coverage, dowiązanie bez zmian (najnowszy)
- Drugie dowiązanie full_sheet/ (ADR-033): najnowszy lokalny lot z
  calyArkuszWypelnionyTrescia = TAK (pełny = w granicach Polski), obok
  ścieżki standardowej; --full-sheet dociąga najwyżej jeden lot na arkusz,
  gdy najnowszy w zakresie nie jest pełny (z --all-campaigns bez skutku); Warning: E13
  wskazuje full_sheet/ albo podpowiada --full-sheet
- LAZ: --all-campaigns (kafle z ramą przecinającą obszar, bez deduplikacji ADR-029);
  przedział lat z kontrolą pokrycia kafli referencji (ADR-032 P8); --year
  wyklucza się z --min-year/--max-year (Error:)
- Wycinek WCS `--cutout`: kompozycja serwera bez wyboru roku
  lub kampanii (--all-campaigns/--year/--min-year/--max-year/--full-sheet =
  Error:); LAZ z --full-sheet = Error:
- CZ nie ma kampanii ani wyboru roku: zadanie bez części PL z --all-campaigns,
  flagą roku albo --full-sheet = Error: przed siecią; obszar PL+CZ pod auto
  wymaga --cutout (ADR-038), który odrzuca te flagi - arkusze PL: --country pl
- Weryfikacja treści pliku kampanii (nagłówek AAIGrid / sygnatura TIFF),
  format z pola `format` rekordu; sidecar kampanii obowiązkowy
- Skorowidz GUGiK niedostępny (błąd transportu) w trybie domyślnym (bez
  --upgrade/--force): arkusz z lokalnej wersji + Warning:, kod bez zmian —
  bez flag roku dla każdej strategii (także --all-campaigns), gdy ścieżka
  standardowa wskazuje lokalną wersję (errata 5 ADR-030); z flagami roku,
  gdy KAŻDY arkusz zadania ma lokalną wersję z zakresu lat (ADR-036 D14).
  Brak lokalnej wersji, --upgrade albo --force = błąd
- API: DownloadManager(year=, all_campaigns: bool = False, min_year=, max_year=,
  full_sheet=), .check_year_range(), YearRangeError, available_years
  (providery GUGiK), DownloadResult (.unverified, .reused_campaign_files,
  .better_coverage, .full_links, .without_full), FileStorage.get_full_sheet_path,
  CampaignRef; download_data(year=, min_year=, max_year=, all_campaigns=,
  full_sheet=) = flagi CLI
```

---

## 3. Out of Scope - Wersja 0.8.0

### 3.1 Funkcjonalności Zaplanowane - FUTURE

```python
# Etap 2 (CZ, po etapie 1):
- DMP (Digitalni model povrchu) — odpowiednik NMPT
- Ortofoto CZ, LAZ/LIDAR CZ
- Wielokąt granicy administracyjnej CZ zamiast prostokątnej obwiedni
  (CountryProfile.extent_wgs84) — usuwa fałszywe zapytania do CUZK dla
  bboxów leżących w całości w Polsce (patrz 3.2)
- Ujednolicenie extra.parent_request.bbox_crs między trybami jawny/auto
- Scalanie wycinków PL+CZ w jedną ciągłą powierzchnię przygraniczną
  (wspólna siatka, EVRF2007 po obu stronach, reguła zakładki) — R6; dane
  wejściowe zmierzone na żywo 2026-09-29: GUGiK wydaje dane ~200 m w głąb CZ,
  CUZK ~118 m w głąb PL, pas wspólny ~310-350 m bez szczeliny (poza dziurami
  pokrycia GUGiK), różnice wysokości PL−CZ w pasie −0,19..+0,14 m (mediany
  zależne od zbioru), siatki PL i CZ niewspólne
- Przestarzaly wycinek arkuszowy PL z arkuszy PL-2000
  (reprojekcja arkuszy, mozaika miedzystrefowa; obecnie blad);
  wycinek WCS nie obsluguje `--sheet-system 2000`

# Kampanie — poza zakresem 0.7.0 (odrzucone w ADR-030):
- --campaign <id> (wybór jednej kampanii), strategie coverage i mosaic
- Narzędzie składania kampanii w jedną powierzchnię — bez przypisanego
  wydania (nie weszło do 0.7.1; ADR-030 errata 6)
- Kampanie dla CZ (CUZK nie publikuje historii) — backlog po 0.7.0

# Etap 3 (CZ):
- ZABAGED — wektorowa baza topograficzna (149 warstw), odpowiednik BDOT10k

# Później — inne kraje:
- Niemcy (DE) — federacja 17 modeli krajów związkowych (BKG/basemap.de)
- Słowacja (SK) — DMR 5.0, ZBGIS (uwaga: WCS zwraca wysokości elipsoidalne)

# Wersja 1.0+:
- GUI: wtyczka QGIS i GUI webowe — roadmapa w sekcji 3.3
- Integracja z PostGIS
- REST API server
```

### 3.2 Ograniczenia Techniczne

```
- Brak weryfikacji integralności sumami kontrolnymi (checksums); pliki
  kampanii NMT/NMPT/orto PL mają tylko kontrolę formatu treści
  (verify_file_format: nagłówek AAIGrid / sygnatura TIFF, ADR-030)
- Timeouty domyślne: 30 s dla NMT/NMPT (GUGiK) i dla discovery WFS w LAZ,
  60 s dla Ortofoto, pobierania kafli LAZ, CORINE (bbox/godło), CUZK oraz
  SoilGrids przez godło, 120 s dla BDOT10k (wszystkie tryby) oraz SoilGrids
  przez bbox i HSG (CORINE/SoilGrids przez TERYT: NotImplementedError);
  GetCapabilities skorowidza GUGiK dziedziczy timeout providera (30 s
  NMT/NMPT, 60 s orto). Źródło prawdy — stałe w kodzie:
  GugikProvider.DEFAULT_TIMEOUT (NMT; NMPT dziedziczy),
  GugikOrtoProvider.DEFAULT_TIMEOUT, GugikLazProvider.DEFAULT_TIMEOUT (kafle)
  i .WFS_TIMEOUT (discovery), CorineProvider.DEFAULT_TIMEOUT,
  SoilGridsProvider.DEFAULT_TIMEOUT (bbox; godło: domyślne 60 s
  z LandCoverProvider.download_by_sheet), Bdot10kProvider.DEFAULT_TIMEOUT
  (zapytanie TERYT w PRG, teryts_for_area: 30 s), _DEFAULT_TIMEOUT
  w providers/cuzk/dmr.py, HSGCalculator: parametr timeout=120
  (grep -rn "_TIMEOUT =" kartograf/providers)
- Max 3 próby retry (nie konfigurowalne); ponawiane tylko błędy sieci,
  HTTP 429 i 5xx — inne 4xx (np. 404) kończą od razu z DownloadError.status_code;
  przerwa 2 s, potem 4 s, Retry-After wydłuża ją maks. do 60 s; jedno
  miejsce dla wszystkich providerów: transport/http.py (download_to,
  get_with_retry; stałe i szczegóły: DEVELOPMENT_STANDARDS 13.4)
- Synchroniczne pobieranie w obrębie jednego pliku (równoległość tylko
  między plikami, przez ThreadPoolExecutor/--workers; domyślnie 4 workery
  w CLI i download_data(workers=4), 1 w DownloadManager(workers=1))
- NMT 5m (PL) wymaga EVRF2007
- WCS (`provider.download_bbox`) NMT i NMPT daje wysokosci 1 m float32
  w obu ukladach wysokosciowych; NMT 5 m tylko z OpenData
- Wycinki PL WCS `--cutout` tylko 1 m, bez wyboru kampanii/roku;
  serwer decyduje o locie, ktory moze roznic sie od lotu arkusza
- SoilGrids: tylko WGS84 bbox (transformacja automatyczna)
- SoilGrids: brak selekcji po TERYT — `--teryt` dotyczy wyłącznie bdot10k,
  a `SoilGridsProvider.download_by_teryt` rzuca NotImplementedError (wcześniej
  cicho zwracał kwadrat 60x60 km wokół środka województwa); użyj --bbox/--sheet
- find_sheets_for_bbox/find_sheets_for_geometry: stykające się krawędzie NIE
  są przecięciem (wymagane dodatnie pole) — bbox równy arkuszowi w EPSG:4326
  zwraca tylko jego arkusze (w EPSG:2180 także fragmenty sąsiadów), a bbox
  zdegenerowany do punktu → dokładnie jeden arkusz
- Skorowidz GUGiK: retry (do 3 prób: sieć, 429, 5xx), sesja per wątek; awaria warstwy /
  szablonu przerywa z DownloadError, bez degradacji kampanii. Rekord musi
  mieć całe godło, zgodny układ i rozdzielczość; w pierwszej warstwie
  z pasującymi rekordami wygrywa najnowsza data. Brak rekordu daje
  NoCoverageError; extra.source zachowuje pochodzenie.
  Cache PL zapisuje pełen rekord albo brak pokrycia (TTL 7 dni); --force pomija
  odczyt i zapisuje świeży wpis (w CZ tak samo dla indeksu arkuszy SM5)

# CZ (CUZK, etap 1) — dodatkowe ograniczenia:
- Produkt CZ w etapie 1: wyłącznie nmt (DMR 5G/4G) — nmpt/orto/laz w etapie 2
- exportImage: sufity usługi 15000x4100 px, praktyczny limit ~8 Mpx;
  klient kafelkuje według budżetu 4 Mpx na żądanie, snap NW daje piksel
  dokładnie 2 m/5 m, a krawędź E/S może różnić się o <= 1/2 px
- KRON86 nieosiągalny dla CZ (brak publicznych siatek Bpv→KRON86) — jedyna
  transformacja pionowa to Bpv→EVRF2007 (EPSG:5621)
- --cutout działa tylko z --bbox/--geometry; z godłem CZ = ValidationError;
  obszar CZ bez --cutout = ValidationError (ADR-038)
- `--cutout` dla PL: NMT/NMPT 1 m z WCS, segment PL-1992
  (`--sheet-system 2000` = blad); orto/LAZ i NMT 5 m z `--cutout`
  = blad. Obszar poza maska ladu PRG `A00 - W02 - W03` = nodata
  -9999; wysokosc 0,0 na ladzie zostaje. Caly wycinek nodata =
  Warning: i kod 0. WCS wybiera lot na serwerze, inny niz
  najnowszy arkusz dokladnie 1 m wg ADR-028 (sekcja 2.1)
- Wycinek WCS (od 0.8.0): domyslnie lokalna wersja bez zapytan PRG
  i WCS (brak taniego sygnalu swiezosci), `--force` pobiera ponownie;
  nowa wersja powstaje obok starej, poprzednia wersja i dowiazanie
  zostaja przy awarii; `--workers`, `--scale` bez wplywu.
  `Info:` podaje liczbe zadan WCS dla wielu kawalkow lub wyniku
  >= 1 GiB (gdy wycinek jest pobierany), bez twardego limitu rozmiaru
- Lista arkuszy PL (--bbox/--geometry bez --cutout oraz hierarchia
  godła) próbuje wszystkie arkusze niezależnie od --workers. R5:
  NoCoverageError -> pominięcie, Warning: i status no_coverage;
  >= 1 plik, bez twardej awarii = kod 0; wszystkie arkusze bez danych
  albo dowolna awaria inna niż brak pokrycia = kod 1 (lista wszystkich
  awarii). Pojedynczy arkusz bez danych = kod 1
- Tryb --bbox jest jawny (ADR-038): PL bez --cutout zwraca listę arkuszy
  (wiele plików), z --cutout jeden plik; CZ ma tylko wycinek (exportImage,
  pobierany natywnie w 5514 i reprojektowany lokalnie, gdy zażądano innego
  układu), więc obszar CZ wymaga --cutout. Pod auto obszar PL+CZ nie daje
  arkuszy PL obok wycinka CZ (arkusze PL: --country pl)
- CountryProfile.extent_wgs84 dla CZ to PROSTOKĄT (obwiednia), nie wielokąt
  granicy — --country auto w pasie na zachód od 18,86°E i na południe od
  51,06°N (m.in. Opole, Wałbrzych, Rybnik, południowe obrzeża Wrocławia;
  Kraków, Rzeszów i centrum Wrocławia są już poza prostokątem) wysyła
  zapytanie do CUZK także dla bboxów leżących w całości w Polsce, a także
  w Saksonii poniżej 51,06°N i w pasie Bogatyni (dodatkowy raster
  cały nodata = Warning: na stderr i kod 0). Symetrycznie prostokąt PL
  (14,07..24,20°E, 49,00..54,90°N) pokrywa
  większość Czech, więc auto w Pradze, Brnie czy Ostrawie odpytuje także
  GUGiK — naprawa (wielokąt granicy) planowana w etapie 2 (patrz ADR-023)
- --country (wymagane z --bbox/--geometry od 0.8.0; wcześniej domyślnie
  auto): pod auto na obszarze spornym wartości bez odpowiednika czeskiego
  (--product nmpt|orto, --vertical-crs KRON86, --resolution 1m w zwykłej
  postaci) ROZSTRZYGAJĄ kraj do pl z komunikatem Info: na
  stderr, zamiast przewracać zadanie; wyjątkiem jest --product laz, który ma
  własny przepływ i na obszarze sięgającym CZ nadal kończy się błędem
  z podpowiedzią --country pl
- --country auto przycina część zadania każdego kraju do prostokąta,
  wypisuje `Info:` o przycięciu i o obszarze pominiętym poza obiema
  obwiedniami. Nazwa pliku i request.bbox niosą część przyciętą,
  extra.parent_request oryginalne zadanie; nietknięte krawędzie PL zachowują
  oryginalne współrzędne (bez poszerzania na tych krawędziach).
  Jawne --country pl nie przycina, --geometry bez --cutout wyznacza
  arkusze PL z geometrii; bbox całkiem poza krajami = błąd przed siecią.
  Na granicach DE/SK/UA/BY/LT/RU auto odpytuje PL z przycięciem;
  wewnątrz prostokąta CZ dochodzi CUZK (bez wymogu poligonu granicy)
- Częściowy sukces w trybie auto (jeden kraj pobrany, drugi nieudany — brak
  danych albo awaria źródła) to kod wyjścia 0 + Warning: na stderr; kod 1
  zostaje dla jawnego --country i dla porażki wszystkich krajów (ADR-023 pkt
  4-5). Kod 0 nie gwarantuje więc pliku z każdego kraju. Info:/Warning: idą
  na stderr, więc -q ich NIE tłumi
- extra.parent_request.bbox_crs zależy od trybu, gdy plik geometrii nie jest
  w układzie żądania CZ: jawne --country cz niesie układ żądania CZ
  (--horizontal-crs), auto/pl — EPSG:2180, a plik w EPSG:5514/3045
  — układ pliku (od 2026-09-28: obwiednia opuszcza Krovaka przypiętą
  operacją); plik w EPSG:5514 z --horizontal-crs EPSG:5514 daje więc ten sam bbox_crs we
  wszystkich trybach — znane ograniczenie klucza grupowania, do ujednolicenia
  w etapie 2
- extra.parent_request.countries = kraje PRÓBOWANE, nie pobrane (przy
  awarii jednego kraju w trybie auto sidecary drugiego nadal niosą oba kody)
```

---

### 3.3 Roadmapa do v1.0.0

Kierunek zatwierdzony 2026-10-08. Każdy podprojekt ma własny spec, plan
i wydanie 0.x; szczegóły rozstrzygają jego ADR, nie ta sekcja.

**Cel v1.0.0:**

1. **Komplet publicznych danych GUGiK** — wszystkie produkty, które GUGiK
   udostępnia publicznie i bez logowania, o ile pozwalają na to usługi.
   Pełny katalog jest warunkiem wejścia, nie wyróżnikiem.
2. **Gotowe dane jako wyróżnik** — dla każdego produktu wynik dopasowany do
   obszaru zadania (wycinek, scalenie, reprojekcja tam, gdzie mają sens)
   z sidecarem pochodzenia, a nie tylko surowe arkusze i paczki.
3. **Manager danych** — wspólny magazyn zespołu, z którego kolejne projekty
   biorą dane zamiast pobierać je ponownie, z zapisem, jakich wersji danych
   użył każdy projekt.
4. **Wtyczka QGIS** i **GUI webowe** jako nakładki na bibliotekę.
5. **Wyłącznie angielskie identyfikatory** w API, CLI i sidecarze (ADR-031).

**Odbiorcy nakładek:** najpierw użytkownik i jego zespół (instalacja
lokalna, GUI webowe uruchamiane na `localhost`), po przetestowaniu —
publikacja (repozytorium wtyczek QGIS, publiczna instancja GUI webowego).

**Zasady:**

- Nakładki (QGIS, web) wołają wyłącznie publiczne API biblioteki
  (`kartograf/__init__.py`); nie mają własnej logiki pobierania ani obróbki.
- Magazyn nigdy nie nadpisuje danych po cichu: każdy produkt ma niezmienne
  wersje, tak jak kampanie NMT/NMPT/orto PL (ADR-030); ścieżka standardowa
  wskazuje najnowszą lokalną wersję.
- Sidecar pozostaje niezmiennym opisem pochodzenia pliku. Powiązanie
  projektu z danymi zapisuje manifest projektu (projekt → dane: konkretne
  pliki, wersje i sumy kontrolne); informacja „które projekty używają tego
  pliku” to indeks budowany z manifestów, nie wpis w sidecarze.
- Magazyn może leżeć na udziale sieciowym bez blokad zakresów bajtów, więc
  wspólny katalog nie może być bazą SQLite na udziale; źródłem prawdy są
  sidecary i manifesty, indeks i cache metadanych są lokalne.
- Manifest projektu jest nowym formatem, więc od początku używa angielskich
  kluczy (bez migracji ADR-031).

**Podprojekty i kolejność:**

| # | Podprojekt | Zakres | Zależy od |
|---|------------|--------|-----------|
| 1 | Magazyn wersjonowany | niezmienne wersje dla wszystkich produktów, które dziś ich nie mają (wszystko poza kampaniami NMT/NMPT/orto PL: m.in. BDOT10k, LAZ, CORINE, SoilGrids, HSG, CZ, wycinki `bbox/`); stan 2026-10-12: plany 1/3 (arkusze PL), 2/3 (LAZ, CZ, wycinki) i 3/3 (land cover, HSG) wykonane i scalone do `develop` (E2E na żywo: `docs/research/2026-10-12-store-e2e/raport.md`); do wydania 0.8.0: CLMS z credentials niesprawdzony na żywo | — |
| 2 | Manifest projektu | plik manifestu w katalogu projektu; CLI: pobranie do projektu, weryfikacja (sumy kontrolne), wykrywanie nowszych danych u źródła | 1 |
| 3 | Katalog GUGiK i gotowe dane | strumień kolejnych produktów GUGiK i ČÚZK; każdy nowy produkt od razu wersjonowany, z wycinkiem i sidecarem; obróbka także dla produktów istniejących. Inwentaryzacja z próbkami: `docs/research/2026-10-13-katalog-produktow/raport.md`; spec zaakceptowany 2026-10-13: `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md` (plany A: `elevation` PL — NMT/NMPT 0,5 m i raport dostępności pełnych arkuszy; B: `elevation` CZ; C: dane jednostkowe i obszarowe PL — archiwum BDOT10k, PRG, EGiB, modele 3D; D: ČÚZK obszarowe i obrazy; E: niski priorytet) | 1; grupy komend CLI (0.8.0) |
| 4 | Wtyczka QGIS | pobieranie z poziomu QGIS dla obszaru z mapy albo warstwy; repozytorium: to albo osobne, do decyzji w specu | 2, częściowo 3 |
| 5 | GUI webowe | lokalny manager danych: przeglądarka magazynu i manifestów projektów, informacja o nowszych danych | 2 |
| — | ADR-031 (angielskie identyfikatory) | API i CLI po angielsku w 0.8.0 bez aliasów (errata 1) | zrobione (0.8.0) |
| — | Publikacja nakładek | po przetestowaniu 4 i 5 lokalnie | 4, 5 |

Podprojekt 3 to strumień, nie jeden blok: produkty dochodzą w kolejnych
wydaniach i mogą iść równolegle z 2, 4 i 5.

---

## 4. Architektura

### 4.1 Moduły

Drzewo odpowiada katalogowi `kartograf/` (źródło prawdy: sam katalog); opis
szczegółowy — `docs/ARCHITECTURE.md`.

```
kartograf/
├── __init__.py           # Public API exports
├── _clock.py             # now() — jedno źródło czasu wyników (zamrażane w testach zgodności)
├── _version.py           # build_version() — identyfikator wersji
├── notices.py            # Notice, NoticeSink, kody komunikatów o danych (ADR-037)
├── exceptions.py         # KartografError, ValidationError -> ParseError, DownloadError -> NoCoverageError/YearRangeError, CacheError
├── core/                 # Logika bazowa
│   ├── bbox.py              # BBox, validate_bbox, transform_bbox, is_czech_crs
│   ├── sheet_parser.py      # SheetParser — parser godeł map topograficznych
│   ├── parser_2000.py       # Parser2000 — parser godeł PL-2000
│   ├── parser_tm33.py       # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045)
│   ├── parser_registry.py   # Rejestr systemów godeł (pl1992, pl2000, cz_tm33, cz_sm5)
│   ├── geometry.py          # SHP/GPKG reading, find_sheets_for_geometry, get_overall_bbox
│   └── coverage.py          # Wypukłe wielokąty (przecięcie/różnica/bufor) — wybór kafli LAZ (ADR-029)
├── sources/               # Deskryptory źródeł jako dane (zero IO przy imporcie)
│   ├── descriptor.py        # SourceDescriptor, AccessChannel (+endpoint), TransportKind, LicenseInfo, CountryProfile
│   ├── registry.py          # Rejestr PL/CZ/EU/GLOBAL — get_source, sources_for, get_country, all_countries, vertical_crs_code, resolve_vertical_crs
│   ├── edition.py           # Edition — wydanie źródła (sygnał metadata: SoilGrids, CORINE CLMS)
│   └── sidecar.py           # ResultMetadata, build_metadata (capability=, nodata=), write_sidecar (<plik>.meta.json)
├── transform/             # Transformacje CRS i rastrów
│   ├── bbox.py               # envelope_from_2180 — obwiednia bboxa EPSG:2180 w innym CRS (CORINE, SoilGrids)
│   ├── crs.py                # TransformerGroup (allow_ballpark=False, probe pod polityką sieci); PinnedTransform.transform polimorficzne
│   └── raster.py             # warp_to_grid — lokalny warp na siatkę, operacja WYMUSZONA (ADR-027)
├── transport/             # Wspólny transport pobierania
│   ├── http.py               # download_to (atomic write + retry), get_with_retry, sesje, sygnały HTTP
│   ├── aaigrid.py            # odczyt odpowiedzi ASC (AAIGrid) WCS
│   ├── chunks.py             # kawałki zapytań obszarowych na siatce źródła (ADR-034)
│   └── mosaic.py             # mosaic_and_crop — merge kafli (rasterio) + przycięcie (opcjonalnie na siatce zrodel, zrodla w VRT)
├── providers/             # Providery danych
│   ├── base.py               # DataSourceProvider (ABC), BaseProvider (NMT), LandCoverProvider
│   ├── pl/                   # Providery polskie
│   │   ├── gugik.py             # GugikProvider (NMT)
│   │   ├── gugik_nmpt.py        # GugikNmptProvider (NMPT/DSM)
│   │   ├── gugik_orto.py        # GugikOrtoProvider (Ortofotomapa)
│   │   ├── gugik_laz.py         # GugikLazProvider (chmury punktów LAZ, WFS; select_tiles)
│   │   ├── skorowidz.py         # Skorowidz GUGiK: rekordy GetFeatureInfo, wybór kampanii (ADR-028/030)
│   │   ├── wcs.py               # GugikWcsMixin — wspólny URL WCS GetCoverage (NMT/NMPT 1m, orto)
│   │   ├── bdot10k.py           # Bdot10kProvider
│   │   ├── prg.py               # WFS PRG: maska lądu (wycinek PL), TERYT dla obszaru/punktu
│   │   └── __init__.py          # create_nmt_provider() — fabryka providera NMT (vertical_crs, resolution wymagane)
│   ├── cuzk/                  # Providery czeskie (CUZK, etap 1)
│   │   ├── client.py            # CuzkClient — silnik sterowany deskryptorem (ArcGIS REST + openzu)
│   │   ├── sheets.py            # SheetIndex/SheetInfo — indeks arkuszy SM5/TM33
│   │   ├── dmr.py               # CuzkDmrProvider — DMR 5G/4G
│   │   └── __init__.py          # create_dmr_provider() — fabryka providera CZ (resolution, vertical_crs wymagane)
│   ├── corine.py             # CorineProvider
│   └── soilgrids.py          # SoilGridsProvider
├── cache/                 # Cache metadanych
│   ├── defaults.py           # open_cache — wspólny cache CLI i biblioteki (<cwd>/.kartograf_cache.db)
│   └── metadata.py           # MetadataCache — SQLite WAL: record_cache, campaigns_cache, teryt_cache (TTL 7d), sheet_cache (TTL 30d)
├── download/              # Pobieranie: komenda download w bibliotece (data.py) i tory
│   ├── data.py               # download_data/check_data = `kartograf elevation download` / `imagery download` (ADR-037)
│   ├── options.py            # Walidacja wyborów zadania (teksty jak w --help)
│   ├── area.py               # Obszar: bbox_to_2180, geometria, parent_request, przycięcie auto
│   ├── campaigns.py          # Kampanie GUGiK (ADR-030): CampaignRef, format z rekordu, verify_file_format
│   ├── countries.py          # Podział obszaru na kraje (countries_for_bbox, split_bbox_by_country)
│   ├── fetch.py              # Polityka plików bez kampanii: fetch_version, VersionedFile
│   ├── plan.py               # Plan aktualizacji kartograf-plan/1 (PlanItem, UpdatePlan)
│   ├── links.py              # Dowiązanie ścieżki standardowej do wersji (wyłącznie hardlink, nigdy wstecz)
│   ├── cutout.py             # Wycinek PL --cutout (download_pl_cutout/check_pl_cutout)
│   ├── cz_cutout.py          # Wycinek CZ (download_cz_cutout/check_cz_cutout)
│   ├── cz_sheets.py          # Arkusz CZ TM33/SM5 (download_cz_sheet/check_cz_sheet)
│   ├── laz.py                # Kafle LAZ (download_laz_area/check_laz_area; ADR-029)
│   ├── manager.py            # DownloadManager (all_campaigns=, min_year=, sidecar_extra=; download_sheets/expand_sheets)
│   ├── storage.py            # FileStorage(vertical_crs=) — segmenty z szablonów deskryptora (ADR-026)
│   ├── updates.py            # Pozycje planu arkuszy PL
│   └── versions.py           # Magazyn wersjonowany (ADR-036): zapis wyłączny, etykiety, lista wersji
├── landcover/             # Land Cover w magazynie wersji
│   ├── manager.py            # LandCoverManager (download/check: teryt|sheet|bbox|geometry)
│   └── store.py              # segmenty i sloty land cover/HSG (spec 3.4)
├── hydrology/             # Obliczenia hydrologiczne
│   └── hsg.py                # HSGCalculator (calculate_hsg/check_hsg, wersje wejść, reused)
├── auth/                  # Autentykacja (CLMS)
│   ├── proxy.py               # Auth Proxy server
│   └── client.py               # Auth Proxy client
└── cli/                   # CLI: tylko tłumaczenie flag i wypisanie wyniku (ADR-037)
    ├── _parser.py             # argparse — parser główny (parse, cache, błąd usuniętych komend)
    ├── _args.py               # wspólne flagi (obszar, tryby aktualizacji, --quiet)
    ├── groups/                # grupy komend wg typu danych (ADR-039): elevation, imagery, landcover, soil
    │                          #   (jeden moduł = jedna grupa z register(); wykrywane automatycznie)
    ├── parse_cmd.py           # `kartograf parse`
    ├── download_cmd.py        # `elevation download` / `imagery download` -> download_data/check_data
    ├── landcover_cmd.py       # `landcover download` -> LandCoverManager
    ├── soil_cmd.py            # `soil download`, `soil hsg`
    ├── cache_cmd.py           # `kartograf cache`
    └── commands.py            # Fasada zgodności — re-eksport + entry point `main`
```

### 4.2 Zależności

```
Python 3.12+
requests >= 2.31.0     # HTTP client
pyproj >= 3.6.0        # CRS transformations
PyJWT[crypto] >= 2.8.0 # OAuth2 JWT (CLMS)
rasterio >= 1.3.0      # GeoTIFF processing (HSG, CZ exportImage/openzu)
numpy >= 1.24.0        # Array operations (HSG, transformacja pionowa per-piksel CZ)
pyshp >= 2.3.0         # Shapefile reading
```

---

## 5. Źródła Danych

| Źródło | Typ danych | API | Autentykacja |
|--------|-----------|-----|--------------|
| GUGiK | NMT, NMPT, Ortofoto, LAZ, BDOT10k | WCS, WMS, WFS, OpenData | Brak |
| CUZK (etap 1) | NMT/DMR 5G/4G (Czechy) | ArcGIS REST (query, exportImage) + pliki openzu | Brak |
| Copernicus CLMS | CORINE | REST API | OAuth2 RSA |
| EEA Discomap | CORINE (podgląd) | WMS | Brak |
| DLR | CORINE 1990 (podgląd, fallback) | WMS | Brak |
| ISRIC SoilGrids | Gleba | WCS | Brak |

---

## 6. Success Criteria

### 6.1 Funkcjonalne

```
- Parser poprawnie parsuje godła 1:1M - 1:10k (PL-1992), PL-2000, TM33/SM5 (CZ)
- NMT pobiera się w rozdzielczościach 1m i 5m (PL), 2m i 5m (CZ)
- BDOT10k pobiera się przez TERYT, godło, bbox i geometrię (każdy powiat obszaru)
- CORINE pobiera się przez godło (GeoTIFF lub PNG fallback)
- SoilGrids pobiera dane glebowe
- HSG oblicza grupy hydrologiczne z danych SoilGrids
- DMR CZ (CUZK) pobiera się przez godło (TM33/SM5) i bbox (exportImage),
  z opcjonalną reprojekcją poziomą (--cutout --horizontal-crs) i pionową (--vertical-crs)
- Bbox/geometria transgraniczna PL/CZ dzieli się na osobne pliki per kraj
  (--country auto), bez scalania, ze wspólnym extra.parent_request
- Wycinek NMT/NMPT PL 1 m (--cutout / download_pl_cutout): jeden GeoTIFF
  z WCS GUGiK na siatce arkuszy (EPSG:2180) albo w EPSG:5514/3045; poza
  ladem PL (maska PRG) nodata -9999
- Kampanie GUGiK: --all-campaigns, --year/--min-year/--max-year; wersje
  w versions/, ścieżka standardowa jako dowiązanie twarde do najnowszej;
  --check-updates/--upgrade/--force i plan aktualizacji (ADR-036)
- LAZ: wybór kafli wg pokrycia obszaru (ADR-029), API download_laz_area
- Integracja z Hydrograf/Hydrolog działa
```

### 6.2 Jakościowe

```
- Wszystkie testy offline przechodzą (`pytest -m "not live"`); testy
  z markerem `live` wymagają sieci i nie należą do bramki offline
- Pokrycie nie niższe niż próg `fail_under` w `pyproject.toml`
- Kod zgodny z ruff (`ruff check .` i `ruff format --check .` czyste),
  `mypy kartograf/ tests/` bez błędów
- Dokumentacja zgodna z kodem; zmiany zachowania wobec usług GUGiK/CUZK
  weryfikowane na żywo przed wydaniem (raporty w `docs/research/`)
```

---

## 7. Historia Zmian

| Data | Wersja | Zmiana |
|------|--------|--------|
| 2026-01-15 | 1.0 | Initial MVP (NMT only) |
| 2026-01-18 | 1.1 | Added Land Cover, SoilGrids, HSG |
| 2026-01-21 | 2.0 | Updated to reflect v0.3.1 features |
| 2026-02-07 | 3.0 | Added NMPT, Ortofotomapa, updated storage structure |
| 2026-02-08 | 3.1 | BDOT10k hydro category, rtree fix |
| 2026-02-08 | 3.2 | Geometry file selection (--geometry SHP/GPKG) |
| 2026-03-02 | 3.3 | Removed BDOT10k category filtering (download full package) |
| 2026-03-02 | 3.4 | PL-2000 support, bump to v0.5.0 |
| 2026-03-24 | 3.5 | WMS layer validation, 5m bugfix, bump to v0.6.1 |
| 2026-08-11 | 3.6 | Etap 0 (sources/transform/transport/providers-pl, CLI split, LAZ) + etap 1 (CZ/CUZK: DMR 5G/4G, --country/--target-crs, ADR-023); drzewo modułów i sekcje odświeżone |
| 2026-08-18 | 3.7 | Przegląd spójności dokumentacji: status mergu etapu 1, nagłówek sekcji 2 (0.5.0→0.7.0), komenda `cache` w 2.9, brakujące eksporty w 2.10 |
| 2026-08-22 | 3.8 | Korekty spójności po audycie przedwydaniowym 0.7.0: WCS NMT tylko 1m/KRON86, 4 warstwy WMS ortofoto, SoilGrids bez TERYT, timeouty per źródło, konwencja krawędzi i etykiety skal, semantyka `--country auto` (zasięg prostokąta CZ/PL, Info/Warning, częściowy sukces) |
| 2026-08-28 | 3.9 | Układ data/ per produkt (ADR-026), --target-crs dla PL (ADR-027), sekcja 2.11 |
| 2026-09-28 | 3.10 | Fala review max: wycinek PL jako API biblioteki (download_pl_cutout), siatka arkuszy, R5 (NoCoverageError -> nodata + extra.missing_sheets), eksporty w 2.10, drzewo modulow, etap 2: scalanie PL+CZ i wycinek z arkuszy PL-2000 |
| 2026-09-29 | 3.11 | Historyczne testy na żywo i audyt przed falą naprawczą: diagnozy LAZ, S-JTSK, skorowidza, orto, limitu CUZK i dyspozycji kraju; dowody zachowania na morzu i pograniczach oraz wejście do R6 |
| 2026-09-30 | 3.12 | Aktualizacja po fali naprawczej: filtr rekordow GUGiK i cache, R5 w liscie/hierarchii, W1/blad fazy w 2180, pin EPSG:1622/1623, budzet 4 Mpx, osie LAZ |
| 2026-10-07 | 3.13 | Kampanie GUGiK (ADR-030): sekcja 2.12, uklad `kampanie/` z dowiazaniem w 2.11, odrzucone strategie w 3.1 |
| 2026-10-08 | 3.14 | Przegląd dokumentacji: errata 5 ADR-030 (lokalna kampania przy awarii skorowidza), CZ i --min-year x --year w 2.12, sidecary (HSG, zasada ogólna), GPKG BDOT10k składany lokalnie, pełna lista eksportów w 2.10, drzewo modułów i tabele cache w 4.1, DLR w 5, bez wartości ulotnych w 6.2 i historii |
| 2026-10-08 | 3.15 | Roadmapa do v1.0.0 (sekcja 3.3): komplet publicznych danych GUGiK, gotowe dane, manager danych (magazyn wersjonowany, manifest projektu), wtyczka QGIS, GUI webowe |
| 2026-10-09 | 3.16 | Narzędzie składania kampanii (3.1) bez przypisanego wydania — nie weszło do 0.7.1 (ADR-030 errata 6) |
| 2026-10-10 | 3.17 | Wybór roku danych (ADR-032): --year/--min-year/--max-year dla NMT/NMPT/orto/LAZ w 2.12, CZ i wycinki bez roku; model A (rok = filtr lat, --campaigns = liczba lotów) |
| 2026-10-10 | 3.18 | Drugie dowiązanie `full_sheet/` i `--full-sheet` (ADR-033) w 2.11 i 2.12 |
| 2026-10-11 | 3.19 | Wydanie v0.7.2: wycinki NMT/NMPT PL z WCS GUGiK z maską lądu PRG (ADR-035), kawałki zapytań obszarowych na siatce źródła (ADR-034), status |
| 2026-10-12 | 3.20 | Magazyn wersjonowany plan 2/3 (ADR-036): LAZ, CZ i wycinki `bbox/` bez daty w wersjach, tryby update dla każdego toru, `DownloadManager.download_bbox` usunięte |
| 2026-10-13 | 3.21 | Pełna weryfikacja z kodem 0.8.0-dev (ADR-037): status i nagłówki 0.8.0, `--scale` dla PL-2000, BDOT10k/CORINE/SoilGrids przez geometrię i filtr warstw, fallback przy niedostępnym skorowidzu (D14), API kampanii, drzewo modułów (brakujące moduły, wyjątki), kryteria 6.1 |
| 2026-10-13 | 3.22 | Jawny tryb wycinka (ADR-038): `--cutout` + `--horizontal-crs` zamiast `--target-crs`, `--sheet-system` zamiast `--system`; obszar CZ wymaga `--cutout` |
| 2026-10-13 | 3.23 | Podprojekt 3: odwołanie do inwentaryzacji GUGiK/ČÚZK i zaakceptowanego specu (kolejność planów A–E) |

---

**Wersja dokumentu:** 3.23
**Data ostatniej aktualizacji:** 2026-10-13
**Status:** Kod v0.8.0-dev (ostatnie wydanie v0.7.2, 2026-10-11)
