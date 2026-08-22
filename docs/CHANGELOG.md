# Changelog

Wszystkie istotne zmiany w projekcie sa dokumentowane w tym pliku.

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - Unreleased

### Breaking Changes
- **Glebokie sciezki importu providerow** (bez shimow — decyzja z review
  specu etapu 0; publiczne API `from kartograf import ...` BEZ zmian):

  | Stary import | Nowy import |
  |---|---|
  | `kartograf.providers.gugik` | `kartograf.providers.pl.gugik` |
  | `kartograf.providers.gugik_nmpt` | `kartograf.providers.pl.gugik_nmpt` |
  | `kartograf.providers.gugik_orto` | `kartograf.providers.pl.gugik_orto` |
  | `kartograf.providers.gugik_laz` | `kartograf.providers.pl.gugik_laz` |
  | `kartograf.providers.bdot10k` | `kartograf.providers.pl.bdot10k` |
  | `kartograf.providers.landcover_base` | `kartograf.providers.base` |

  Dodatkowo: wrapper zgodnosciowy `download_by_teryt` (w `LandCoverProvider`)
  zweza pozycyjna arnosc wzgledem dotychczasowych podklas — przyjmuje pozycyjnie
  tylko `teryt`, `output_path`, `timeout`; kazdy kolejny argument (np. `format`
  w `Bdot10kProvider.download_by_admin_unit`) przekazany pozycyjnie (4. argument)
  konczy sie `TypeError`. Przekazuj takie argumenty jako keyword (`format=...`).
- **Sidecary CZ: `transform.horizontal` zmienia format i zakres** (ADR-024).
  Bylo `"server:EPSG:<kod>"` (tylko przy `--target-crs`), jest
  `"pinned: <opis operacji> (<dokladnosc> m)"` — i pojawia sie takze dla kafli
  TM33 pobranych godlem, ktore dotad mialy `transform: null`. Konsumenci
  parsujacy prefiks `server:` musza zostac dostosowani; format jest teraz
  wspolny dla obu osi (`transform.vertical` mial go od poczatku).
- **`vertical_crs_code("EVRF2007")` zwraca teraz `EPSG:5621`** (ogolnoeuropejski
  EVRF2007), nie `EPSG:9651` (dawna wartosc dla realizacji polskiej). Powod:
  `EVRF2007` jest teraz nazwa RODZINY ukladow, wspolna dla PL i CZ. Realizacja
  polska dostepna pod nowa nazwa `EVRF2007-PL`. Sidecary PL bez zmian tresci
  (mapowanie rodzina→realizacja przez nowa funkcje `resolve_vertical_crs`).
  Dotyczy: Hydrograf/Hydrolog, jesli woluja `vertical_crs_code` bezposrednio.

  | Nazwa (CLI/API) | Stary kod (< 0.7.0) | Nowy kod (>= 0.7.0) |
  |---|---|---|
  | `KRON86` | `EPSG:9650` | `EPSG:9650` (bez zmian) |
  | `EVRF2007` | `EPSG:9651` (realizacja PL) | `EPSG:5621` (rodzina, ogolnoeuropejski) |
  | `EVRF2007-PL` | — (nie istniala) | `EPSG:9651` (nowa nazwa realizacji polskiej) |
  | `Bpv` | — (nie istniala, CZ) | `EPSG:8357` (Baltic 1957, CUZK) |

### Added
- **Etap 0 — architektura zrodel wielokrajowych (przygotowanie pod CZ/DE/SK)**
  - `kartograf/sources/` — deskryptory zrodel (SourceDescriptor, AccessChannel,
    TransportKind, LicenseInfo, CountryProfile) + rejestr (`get_source`,
    `sources_for`, `get_country`, `vertical_crs_code`); zero IO przy imporcie
  - **Sidecar metadanych**: po kazdym udanym pobraniu powstaje
    `<plik>.meta.json` (schema `kartograf-meta/1`: dataset, CRS-y, nodata,
    licencja, request, wersja) — kontrakt dla Hydrografa; blad zapisu sidecara
    nie przerywa pobrania
  - `kartograf/transform/crs.py` — twarda polityka transformacji:
    `TransformerGroup(allow_ballpark=False)`, filtr dokladnosci, probe
    odrzucajacy siatki obcych krajow (inf), kontrola isfinite,
    `TransformError`/`TransformUnavailableError` z remedium; `KNOWN_PATHS`
  - `kartograf/transport/` — `download_to()` (atomic write + retry) i
    `mosaic_and_crop()` (rasterio.merge + przyciecie, propagacja nodata)
  - `kartograf/core/parser_registry.py` — rejestr systemow godel (pl1992,
    pl2000); `SheetParser` i `FileStorage` deleguja do rejestru (wyniki
    identyczne)
  - `providers/pl/__init__.py`: fabryka `create_nmt_provider()` — jedno
    miejsce polskich domyslow NMT (w tym regula 5m => EVRF2007)
  - `FileStorage(subdir=...)` — opcjonalny podkatalog sterowany deskryptorem
  - `LandCoverProvider.download_by_admin_unit`/`validate_admin_unit`
    (kanoniczne) + `download_by_teryt`/`validate_teryt`/`source_url` jako
    dzialajace aliasy zgodnosciowe
  - CLI podzielone na moduly (`cli/_parser.py`, `parse_cmd.py`,
    `download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`,
    `cache_cmd.py`); `cli/commands.py` zostaje fasada zgodnosci (entry point
    bez zmian)
- **Etap 1 — Czechy (CUZK)**
  - `providers/cuzk/` — `CuzkClient` (pierwszy silnik sterowany deskryptorem:
    `AccessChannel.endpoint`; `query()` z paginacja i filtrem nadmiarowego
    wyboru po stronie klienta, `export_image()` z kafelkowaniem 15000x4100 px
    + nadpisaniem CRS, `fetch_file()` z ZIP openzu → TIFF+TFW), `SheetIndex`/
    `SheetInfo`/`Sm5Sheet` (indeks arkuszy SM5/TM33 z KladyMapovychListu),
    `CuzkDmrProvider` + fabryka `create_dmr_provider` — DMR 5G/4G (CUZK),
    godla TM33/SM5, bbox przez exportImage, opcjonalna transformacja
    Bpv->EVRF2007 (EPSG:8357 -> EPSG:5621, przypieta operacja 0,1 m, offset
    +0,11..+0,15 m rosnacy S→N); endpointy wylacznie z deskryptorow, naprawa
    metadanych CRS w plikach DMR4G-TIFF i w wynikach exportImage
  - `core/parser_tm33.py` — `ParserTM33`: obliczalna siatka kafli TM33
    2x2 km (EPSG:3045, godlo `{E_km}_{N_km}` = naroznik SW), wzorowana na
    `Parser2000`; zarejestrowana w `parser_registry` jako `cz_tm33`/`cz_sm5`
    (przed fallbackiem pl1992)
  - `AccessChannel.endpoint` — nowe pole deskryptora: jedyne zrodlo URL-i dla
    silnikow sterowanych deskryptorem (CZ); kanaly PL maja `endpoint=""`
    (zrodlem prawdy pozostaja stale providerow z etapu 0)
  - `sources/registry.py`: deskryptory `cz.cuzk.dmr5g`/`cz.cuzk.dmr4g`,
    `CountryProfile` dla CZ (obwiednia prostokatna EPSG:4326), `all_countries()`
  - `MetadataCache`: nowa tabela `sheet_cache` (indeks SM5, TTL 30 dni —
    praktycznie staly); `cache stats` pokazuje tez liczbe wpisow Sheet
  - `sources/sidecar.build_metadata(capability=, nodata=)` — jawna selekcja
    kanalu po capability (zamiast wylacznie heurystyki bbox/nie-bbox) i jawne
    nadpisanie `nodata` (potrzebne, bo usluga `exportImage` CUZK zwraca
    `noDataValue: null` na poziomie ImageServera)
  - `DownloadManager(sidecar_extra=...)` — addytywny parametr konstruktora:
    dodatkowe pola scalane do `extra` kazdego sidecara (uzyty przez CLI PL w
    trybie bbox/geometry do wpiecia `parent_request`, patrz nizej)
  - CLI `--country {pl,cz,auto}` z auto-podzialem bboxa/geometrii
    transgranicznej: obszar trafia do zrodel KAZDEGO przecietego kraju (w trybie
    auto przyciety do jego obwiedni), a opcje nierozwiazywalne dla ktoregos
    z krajow (np. `--resolution 1m` z CZ, `--system` z CZ, `--target-crs` z PL)
    sa odrzucane PRZED pobraniem, z podpowiedzia jawnego `--country`
  - CLI `--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}` — reprojekcja wyniku CZ
    w trybie `--bbox`/`--geometry`, wykonywana lokalnie przypieta operacja
    (pierwotnie serwerowo przez `imageSR`; zmienione fixem ADR-024 — patrz
    Changed/Fixed nizej); godlo + `--target-crs` = blad (patrz Changed);
    `--vertical-crs {Bpv,EVRF2007,KRON86}` rozszerzone o CZ
  - `extra.parent_request` w sidecarach trybu bbox/geometry (oryginalny bbox
    zadania, jego uklad i **probowane** — niekoniecznie pobrane — kraje) —
    grupowanie plikow jednego zadania, takze po obu stronach granicy; tryb
    godlowy sidecarow nie zmienia (nigdy nie dostaje `parent_request`)
  - `--product laz` w trybie obszarowym `--country auto`: obszar siegajacy CZ
    konczy sie bledem z podpowiedzia `--country pl` (bez cichego pomijania kraju)

### Changed
- CLI: sentinele `None` dla `--resolution`/`--vertical-crs`/`--system`
  rozwiazywane dopiero po ustaleniu kraju docelowego (PL: 1m/EVRF2007/1992
  bez zmian; CZ: 2m/Bpv, `--system` nie dotyczy) — zamiast twardo zakodowanych
  domyslnych PL, ktore nie mialy sensu dla CZ
- `PinnedTransform.transform` (`transform/crs.py`) jest teraz **polimorficzne**
  — przyjmuje skalary LUB tablice `numpy` (`np.isfinite` zamiast
  `math.isfinite`, ktory rzucal `TypeError` na `numpy.ndarray`); potrzebne do
  transformacji pionowej calego rastra per-piksel (DMR CZ → EVRF2007)
- `build_pinned_transform`: probe na punkcie kontrolnym wykonywany teraz
  **wewnatrz** kontekstu `network.set_network_enabled(...)`, nie po jego
  przywroceniu (poprawka semantyki "probe pod polityka sieci" odroczonej
  z etapu 0)
- Sidecary PL w trybie `--bbox`/`--geometry` (takze `--country pl`/`auto`)
  dostaja teraz dodatkowo `extra.parent_request` — nowe pole, tresc
  pozostalych pol bez zmian; wspolny klucz grupowania z sidecarami CZ dla
  tego samego zadania
- **Sidecary CZ: `transform.horizontal` niesie operacje przypieta zamiast
  serwerowej** (ADR-024) — `"pinned: <opis operacji> (<dokladnosc> m)"`,
  symetrycznie do `transform.vertical`, zamiast `"server:EPSG:<kod>"` bez pola
  dokladnosci. Pole pojawia sie takze dla kafli TM33 pobranych godlem, ktore
  dotad mialy `transform: null` (kafel lezy w EPSG:3045, a dane CUZK w
  EPSG:5514 — reprojekcja zachodzi i jest teraz opisana). Sciezka SM5
  (DMR 4G, pliki openzu w 5514) nadal ma `transform` bez czesci poziomej.
- `PinnedTransform` niesie pare ukladow (`src_crs`/`dst_crs`) i udostepnia
  `gdal_operation()` — te sama operacje jako pipeline PROJ dla GDAL-owego
  `COORDINATE_OPERATION`, z korekta kolejnosci osi (cel northing-first bez
  `axisswap` daje raster w calosci nodata)
- `import kartograf` laduje teraz eagerly `rasterio` (GDAL/PROJ bindings) —
  eksporty CZ w `__init__.py` importuja `providers/cuzk/client.py`, ktory
  importuje `rasterio` na poziomie modulu; zmierzony koszt +55–65 ms
  (~185 ms → ~244 ms). Zepsuty GDAL/PROJ (np. brakujaca biblioteka natywna)
  psuje teraz sam `import kartograf`, nie dopiero pierwsze wywolanie funkcji
  rastrowej — istotne dla Hydrografu/Hydrologu, ktore importuja Kartograf
  jako zaleznosc (patrz ADR-023, "Ustalenia dodatkowe" pkt 2)
- **`pyproject.toml`: wersja dynamiczna z `kartograf.__version__`** —
  usuniety rozjazd `version = "0.6.1"` (pyproject) vs `__version__ =
  "0.7.0-dev"` (`kartograf/__init__.py`); teraz jedno zrodlo prawdy
  (`dynamic = ["version"]` + `[tool.setuptools.dynamic] version = {attr =
  "kartograf.__version__"}`); `[tool.setuptools.packages.find]` dostaje
  `include = ["kartograf*"]`, wiec `tests/` nie trafia do dystrybucji;
  opis i keywords rozszerzone o CUZK/DMR/LAZ

### Fixed
- **Reprojekcja tresci CZ szla przez serwer CUZK i gubila transformacje datum**
  (ADR-024). `--target-crs EPSG:2180` zwracal raster przesuniety o **135 m**
  (dE 119, dN 64,5 — `exportImage&imageSR=2180` traktowal S-JTSK jak ETRS89),
  a domyslna sciezka godlowa TM33 (`imageSR=3045`) — o **1,25 m** na poludnie.
  Zaden z tych bledow nie byl widoczny w metadanych: zasieg, CRS, rozdzielczosc
  i nodata byly poprawne, a sidecar niosl tylko `transform.horizontal =
  "server:EPSG:<kod>"` bez dokladnosci. Kontrola przypietych transformow
  obejmowala wylacznie obwiednie zadania (zgodna do 0,07 m) — tresc pikseli
  szla obok niej.
  Serwer dostaje teraz zadania **wylacznie w ukladzie natywnym `EPSG:5514`**,
  a reprojekcje wykonuje `rasterio.warp` z **wymuszonym** pipeline'em
  przypietej operacji (`COORDINATE_OPERATION`) — dla obu sciezek rastrowych.
  Kafelkowanie i mozaikowanie zostaja po stronie natywnej (przed warpem), wiec
  szwy kafli nie sa utrwalane przez interpolacje; nodata nie wchodzi do
  interpolacji, zapis pozostaje atomowy, a zasieg i rozmiar wyniku sa
  identyczne jak dotad. Brak bezpiecznej operacji poziomej przerywa teraz
  w konstruktorze providera, przed transferem.
- CLI z `--resolution 5m --vertical-crs KRON86` tworzy teraz provider skorygowany
  do EVRF2007 przez fabryke `create_nmt_provider` (wczesniej provider dostawal
  niewspierana kombinacje). Skorygowana wartosc jest tez przekazywana do
  `DownloadManager`, wiec ostrzezenie o zmianie ukladu pionowego pojawia sie
  raz, a nie dwa razy.
- Sidecar CORINE na sciezce fallbacku PNG (brak credentials CLMS) deklaruje
  faktyczny CRS podgladu WMS — `EPSG:3857` (EEA Discomap) lub `EPSG:4326`
  (DLR, rok 1990) — zamiast `EPSG:3035` wlasciwego wylacznie dla GeoTIFF z
  CLMS; dochodzi `extra.fallback = "wms_png"` z adnotacja "podglad WMS, nie dane".
- `FileStorage.delete()` usuwa takze sidecar `.meta.json` pliku danych
  (wczesniej zostawal osierocony).

### Added
- **Nowy produkt: LAZ — chmury punktów LIDAR (dane pomiarowe ALS) z GUGiK**
  - `GugikLazProvider` (`kartograf/providers/gugik_laz.py`) — pobieranie plików
    `.laz` przez **WFS** (`DanePomiaroweLidarEVRF2007` / `DanePomiaroweLidarKRON86`)
  - Discovery **area-based**: godło (≤1:10000) / `--bbox` / `--geometry` → bbox
    EPSG:2180 → `discover_tiles()` (WFS GetFeature) → pobranie wszystkich kafli
  - Kafle LAZ są drobniejsze niż 1:10000 (jedno godło 1:10000 → wiele kafli);
    godło kafla jest **nieparsowalne** i traktowane jako etykieta — `url_do_pobrania`
    bierzemy wprost z atrybutu WFS, bez konstruowania URL i bez `SheetParser`
  - WFS zwraca metadane: rok (`akt_rok`), gęstość (`char_przestrz`), CRS, geometria
  - Domyślnie: EVRF2007, **najnowszy rok per kafel** (dedup po godle); flagi
    `--year`, `--vertical-crs`, `--min-density` do nadpisania
  - CLI: `kartograf download <godło|--bbox|--geometry> --product laz [...]`,
    pobieranie równoległe (`--workers`), pomijanie istniejących plików
  - `GugikLazProvider._fetch_available_years()` / `_get_available_years()` —
    lista lat z WFS GetCapabilities, in-memory cache, fallback na hardcoded
  - `FileStorage.get_raw_path()` — ścieżka dla nieparsowalnego (drobnego) godła
    bez `SheetParser`; pliki w `laz/<hierarchia godła>/<oryginalna nazwa>.laz`
  - Eksport: `GugikLazProvider`, `LazTile` w `kartograf/__init__.py`
  - Weryfikacja: pobrano realne pliki LAZ (magic `LASF`) E2E; 41 nowych testów

### Fixed
- **NMT 1m/EVRF2007: zaktualizowane nazwy warstw WMS (nowe roczniki)**
  - `WMS_LAYERS["1m"]["EVRF2007"]`: `[2025, 2024, 2023, 2022iStarsze]` →
    `[2026, 2025, 2024, 2023iStarsze]`
  - Dodana brakujaca warstwa `SkorowidzeNMT2026`
  - Usuniete nieistniejace juz warstwy `SkorowidzeNMT2023` i `SkorowidzeNMT2022iStarsze`
    (GetFeatureInfo zwracalo "Invalid layer(s) given in the LAYERS parameter")
  - Zweryfikowane przez GetCapabilities endpointu `SkorowidzeUkladEVRF2007` (2026-06-24)
  - Wykryte podczas rozpoznania danych dla godla M-34-27-B-b-1-2 (Kielchinow)
  - `1m/KRON86` (`SkorowidzeUkladKRON86`) i `5m/EVRF2007` (`SheetsGrid5mEVRF2007`)
    zweryfikowane — bez zmian; endpoint 5m nadal udostepnia starsze roczniki
    (`[2025, 2024, 2023, 2022iStarsze]`) i nie zostal przesuniety do 2026 jak 1m
  - Mechanizm `_get_validated_layers()` (GetCapabilities + fallback z v0.6.1) i tak
    auto-korygowal te liste w runtime; aktualizacja usuwa rozbieznosc i warning
- **Ortofotomapa: naprawione i odswiezone nazwy warstw WMS**
  - `WMS_LAYERS` (GugikOrtoProvider): `[2025, 2024, 2023, 2022, 2021, 2020, 2019,
    2018, Starsze]` → `[2026, 2025, 2024, Starsze]`
  - GUGiK skonsolidowal starsze warstwy rocznikowe (2023..2018) w jedna
    `SkorowidzeOrtofotomapyStarsze` — zapytania o usuniete warstwy zwracaly
    "Invalid layer(s) given in the LAYERS parameter"; brakowalo tez `2026`
  - Zweryfikowane przez GetCapabilities endpointu `SkorowidzeWgAktualnosci` (2026-06-24)
  - Warstwy `SkorowidzeOrtofotomapyZasiegi*` (zasiegi, bez URL OpenData) sa pomijane

### Added
- **Walidacja warstw WMS przez GetCapabilities dla Ortofotomapy**
  - `GugikOrtoProvider._fetch_wms_layers()` i `_get_validated_layers()` — analogicznie
    do GugikProvider; dotad orto NIE mialo zadnego fallbacku (twarda lista)
  - Lazy, in-memory cache per instancja; graceful fallback do `WMS_LAYERS` przy bledzie
  - Filtruje prefiks `SkorowidzeOrtofotomapy`, wyklucza warianty `Zasiegi`,
    sortuje malejaco po roczniku (warstwa `Starsze` na koncu)

### Tests
- `tests/test_wms_layer_validation.py` — nowa klasa `TestHardcodedLayerNames`
  (5 testow): regresyjne strazniki nazw warstw zweryfikowanych z GetCapabilities
  (KRON86, 1m EVRF2007, 5m EVRF2007, divergencja 5m vs 1m, kolejnosc newest-first)
- Zaktualizowany `test_returns_discovered_layers_on_mismatch` — uzywa hipotetycznego
  przyszlego zestawu rocznikow, aby galaz mismatch byla niezalezna od hardcoded
- `tests/test_wms_layer_validation.py` — nowa klasa `TestOrtoLayerValidation`
  (7 testow): parsowanie/sortowanie GetCapabilities orto, wykluczanie `Zasiegi`,
  mismatch/match/fallback/cache, straznik nazw warstw
- `tests/test_gugik_orto.py` — autouse fixture stubujaca GetCapabilities (offline),
  zaktualizowany `test_get_opendata_url_tries_all_layers` (9 → 4 warstwy)

### Tests
- **1402 testy, pokrycie ~89%** (+260 wzgledem stanu po mergu etapu 0: 1142;
  w tym +18 testow regresji fixu ADR-024 i +3 przypiecia sciezki godlowej);
  ruff i ruff format czyste, mypy bez nowych bledow wzgledem baseline (33/34
  przedistniejacych, niezwiazanych z etapem 1)
- E2E na zywych danych CUZK + regresja PL: **11/11 PASS**
  (`docs/research/2026-08-11-etap1-e2e.md`) — godlo TM33 (dmr5g, Bpv),
  godlo SM5 (dmr4g, kraj auto-wykryty), bbox przygraniczny `--country auto`
  (osobne pliki PL/CZ, wspolny `parent_request`), `--target-crs EPSG:2180`,
  transformacja pionowa `--vertical-crs EVRF2007` (offset zmierzony na zywo
  +0,132366 m, zgodny z modelem), `--vertical-crs KRON86` (blad z remedium),
  regresja PL (godlo, `landcover list-sources`, `cache stats`)

## [0.6.1] - 2026-03-24

### Fixed
- **NMT 5m: naprawione nazwy warstw WMS**
  - `WMS_LAYERS["5m"]["EVRF2007"]`: `SkorowidzeNMT2022` → `SkorowidzeNMT2022iStarsze`
  - Usunieta nieistniejaca warstwa `SkorowidzeNMT2021iStarsze`
  - Dodana brakujaca warstwa `SkorowidzeNMT2025`
  - Bledne nazwy powodowaly brak wynikow przy pobieraniu NMT 5m mimo dostepnosci danych

### Added
- **Walidacja warstw WMS przez GetCapabilities**
  - `_fetch_wms_layers()` — pobiera liste dostepnych warstw z WMS GetCapabilities
  - `_get_validated_layers()` — porownuje hardcoded warstwy z live WMS, auto-aktualizacja przy rozbieznosci
  - Lazy validation: tylko przy pierwszym wywolaniu `_get_opendata_url()`
  - Graceful fallback: jesli GetCapabilities niedostepne, uzywa hardcoded warstw
  - Warning logowany przy wykryciu rozbieznosci miedzy hardcoded a live
  - In-memory cache per instancja providera (bez lock, benign duplicate OK)
  - Osobny timeout 10s dla GetCapabilities
  - Dziala dla GugikProvider (NMT) i GugikNmptProvider (NMPT) przez dziedziczenie
  - GugikOrtoProvider nieobslugiwany (inna hierarchia dziedziczenia)

### Tests
- **1007 testow** (+17 nowych)
  - Nowy `tests/test_wms_layer_validation.py` — 17 testow dla walidacji warstw WMS

---

## [0.6.0] - 2026-03-03

### Added
- **Parallel downloads with ThreadPoolExecutor**
  - `DownloadManager(max_workers=4)` — configurable thread pool for hierarchy downloads
  - `DownloadResult` dataclass — structured results with succeeded/failed/skipped tracking
  - `_download_hierarchy_parallel()` — concurrent sheet downloads with progress callbacks
  - `LandCoverManager.download_batch()` — parallel batch download for land cover data
  - CLI: `--workers`/`-w` flag on `kartograf download` (default: 4)
  - Thread-safe temp filenames in all providers (`pid_threadid.tmp` pattern)
- **SQLite metadata cache (MetadataCache)**
  - `kartograf/cache/metadata.py` — SQLite WAL mode, TTL 7 days, thread-safe writes
  - URL cache for GUGiK OpenData lookups (NMT, NMPT, Orto)
  - TERYT cache for BDOT10k point-to-TERYT resolution
  - `prune_expired()` — automatic cleanup of stale entries
  - Integrated with GugikProvider, GugikNmptProvider, GugikOrtoProvider, Bdot10kProvider
  - CLI: `kartograf cache stats|clear|path`
- **PL-2000 BBox verification tests**
  - 67 new tests: reference values, hierarchy consistency, live WMS, edge cases
  - `@pytest.mark.live` marker for GUGiK WMS integration tests
- **Public API: eksport MetadataCache i DownloadResult**
  - `from kartograf import MetadataCache, DownloadResult`

### Tests
- **990 testow** (+155 nowych)

---

## [0.5.0] - 2026-03-02

### Added
- **PL-2000 sheet naming system — full support**
  - `Parser2000` class for parsing PL-2000 godla (format `zone.row.column[.subdivisions]`)
  - 5 skal: 1:10000, 1:5000, 1:2000, 1:1000, 1:500
  - 4 strefy merydianowe: 5 (EPSG:2176), 6 (EPSG:2177), 7 (EPSG:2178), 8 (EPSG:2179)
  - BBox calculation z transformacja CRS (pyproj)
  - Hierarchia: get_parent(), get_children(), get_all_descendants(), get_hierarchy_up()
  - `find_sheets_2000_for_bbox()` — BBox to PL-2000 godla lookup
- **SheetParser auto-detekcja PL-1992 vs PL-2000**
  - `SheetParser("6.179.12")` automatycznie rozpoznaje PL-2000
  - `SheetParser("N-34-130-D")` automatycznie rozpoznaje PL-1992
  - Walidacja zgodnosci uklad/format
- **find_sheets_for_bbox: parametr system="1992"|"2000"**
  - `find_sheets_for_bbox(bbox, system="2000")` zwraca godla PL-2000
  - `find_sheets_for_geometry()` rowniez obsluguje parametr system
- **CLI: pelna obsluga PL-2000**
  - `kartograf parse 6.179.12.20` — auto-detekcja, wyswietla strefe i CRS
  - `kartograf download --bbox ... --system 2000` — pobieranie z godlami PL-2000
  - `--bbox-crs` rozszerzony o EPSG:2176-2179
- **FileStorage: obsluga sciezek PL-2000**
  - Struktura katalogow: `nmt_2000_1m/6/179/12/20/6.179.12.20.asc`
- **Public API: eksport Parser2000 i find_sheets_2000_for_bbox**
  - `from kartograf import Parser2000, find_sheets_2000_for_bbox`

### Removed
- **BDOT10k: usunięto filtrowanie po kategorii (--category pt/hydro)**
  - Pobierany jest cały plik BDOT10k bez podziału na kategorie
  - Usunięto stałe `PT_LAYERS`, `HYDRO_LAYERS`, `CATEGORY_FILTERS`
  - Usunięto parametr `category` z `download_by_teryt()`, `_download_with_retry()`, `_extract_gpkg_from_zip()`
  - Usunięto argument CLI `--category`
  - `_extract_gpkg_from_zip()` wyciąga i scala wszystkie warstwy GPKG z ZIP
  - `get_available_layers()` zwraca wszystkie 15 warstw (PT* + SW*)

### Fixed
- **download_sheet(): PL-2000 sub-10k godla pobierane bezposrednio**
  - Godla PL-2000 w skalach 1:5000, 1:2000, 1:1000, 1:500 sa teraz pobierane
    jako pojedyncze pliki, bez proby rozwijania do 1:10000
- **CLI: dynamiczne etykiety skal**
  - `format_hierarchy()` — naglowek "from current to X" zamiast hardcoded "1:1000000"
  - `format_children()` — "finest scale X" zamiast hardcoded "1:10000"

### Tests
- **835 testow** (+199 nowych; w trakcie prac bylo 849 — 14 testow
  `--category` usunieto w tej samej wersji razem z flaga, ADR-016)

---

## [0.4.1] - 2026-02-08

### Fixed
- **BDOT10k: rtree spatial indices preserved during GPKG merge**
  - After merging multiple GPKG files, only the base (first) file kept its rtree index
  - New `_copy_rtree_index()` method copies rtree virtual table, data, and `gpkg_extensions` entry
  - All merged layers now retain spatial indices for fast spatial queries

### Added
- **Geometry file selection (`--geometry FILE`)**
  - Support for SHP (via pyshp) and GPKG (via sqlite3 + envelope parsing) input files
  - Per-feature bbox extraction for precise tile selection (not entire file bbox)
  - `find_sheets_for_geometry()` — public API for geometry → godla lookup
  - `get_overall_bbox()` — union bbox for landcover/soilgrids
  - CRS auto-detection from .prj (SHP) and gpkg_spatial_ref_sys (GPKG)
  - New dependency: `pyshp>=2.3.0`
- **CLI: `--geometry` and `--layer` for all download commands**
  - `kartograf download --geometry area.shp` — NMT tiles intersecting features
  - `kartograf download --geometry area.gpkg --layer catchments` — GPKG layer selection
  - `kartograf landcover download --source bdot10k --geometry area.shp`
  - `kartograf soilgrids hsg --geometry area.shp`

### Tests
- **636 testow** (+62 nowych)
  - 31 testow `test_geometry.py`: envelope parsing, SHP/GPKG reading, CRS transform, find_sheets_for_geometry, get_overall_bbox
  - 12 testow CLI geometry: download/landcover/soilgrids --geometry, mutual exclusivity
  - 5 testow `TestBdot10kRtreeIndex`: merge preserves indices, no geometry, no index, extensions copied, base preserved

---

## [0.4.0] - 2026-02-07

### Added
- **NMPT (Numeryczny Model Pokrycia Terenu / Digital Surface Model)**
  - `GugikNmptProvider` — dziedziczy z GugikProvider, nadpisuje endpointy NMPT
  - Tylko rozdzielczość 1m, vertical CRS: KRON86 lub EVRF2007
  - Download: godło → OpenData ASC, bbox → WCS GeoTIFF
- **Ortofotomapa (Standard Resolution, 25cm)**
  - `GugikOrtoProvider` — osobna klasa, format TIF
  - Brak vertical CRS (2D RGB), 9 warstw WMS (2018-2025+starsze)
  - Download: godło → OpenData TIF, bbox → WCS GeoTIFF
- **CLI `--product {nmt,nmpt,orto}` — wybór produktu w komendzie download**
  - `kartograf download N-34-130-D-d-2-4 --product nmpt` — pobiera NMPT
  - `kartograf download --bbox ... --product orto` — pobiera ortofoto
  - Domyślnie: nmt (bez zmian)
- **`find_sheets_for_bbox()` — reverse lookup: bbox → godła arkuszy**
  - Algorytm hierarchicznego przycinania (matematyczny, bez WFS)
  - Obsługa EPSG:2180 i EPSG:4326
  - Dowolna skala docelowa (1:1M do 1:10k)
  - Zoptymalizowane wyszukiwanie 1:200k (siatka 12x12)
- **CLI `kartograf download --bbox` — pobieranie NMT dla bbox**
  - `--bbox min_x,min_y,max_x,max_y` — współrzędne bbox
  - `--bbox-crs {EPSG:2180,EPSG:4326}` — CRS bbox (domyślnie EPSG:2180)
  - `godlo` staje się opcjonalny (godlo XOR --bbox)
  - Automatyczne wykrywanie arkuszy i pobieranie w pętli
- **Automatyczne rozwijanie godeł do 1:10000 w `download_sheet()`**
  - `download_sheet("N-34-130-D-d-2")` (1:25000) → automatycznie pobiera 4 arkusze 1:10000
  - `download_sheet("N-34-130-D-d")` (1:50000) → pobiera 16 arkuszy 1:10000
  - Dla godeł 1:10000 zachowanie bez zmian (pojedynczy plik)
  - Nowy parametr `on_progress` — callback postępu przy rozwijaniu hierarchii
  - Zwracany typ: `Path` (1:10000) lub `list[Path]` (coarser scales)
  - CLI dostosowane — wyświetla liczbę pobranych plików przy rozwijaniu

### Tests
- **574 testow, pokrycie 83.95% (cel 80% osiagniety)**
  - Nowy `tests/test_gugik_nmpt.py` — 21 testow dla GugikNmptProvider
  - Nowy `tests/test_gugik_orto.py` — 25 testow dla GugikOrtoProvider
  - Nowy `tests/test_auth_client.py` — 30 testow dla AuthProxyClient
  - Nowy `tests/test_auth_proxy.py` — 24 testy dla CLMSCredentials, ProxyHandler
  - Rozszerzony `tests/test_cli.py` — +12 testow (product CLI), +11 testow (landcover/soilgrids CLI)
  - Rozszerzony `tests/test_storage.py` — +8 testow (product storage)
  - Rozszerzony `tests/test_download_manager.py` — +3 testy (default_ext)
  - Rozszerzony `tests/test_landcover.py` — +38 testow
  - Rozszerzony `tests/test_hsg.py` — +6 testow

### Fixed
- Poprawiony komunikat błędu przy braku pokrycia NMT 5m — zamiast technicznego "No ASC file found in any WMS layer" wyświetla czytelną informację o braku pokrycia danego obszaru w GUGiK

### Changed
- **FileStorage: podkatalogi `1m`/`5m` → `nmt_1m`/`nmt_5m`**
  - Nowy parametr `product` w FileStorage (np. product="nmpt", product="orto")
  - Struktura: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`
- **DownloadManager: dynamiczne rozszerzenie pliku**
  - `_default_ext` pobierane z `provider.default_extension` zamiast hardcoded `.asc`
- **BaseProvider: nowa property `default_extension`** (domyślnie `.asc`)
- Migracja z black + flake8 na ruff (pyproject.toml)
- Usuniecie .flake8, dodanie .editorconfig
- Standaryzacja dokumentacji wg shared/standards
- Przepisanie CLAUDE.md (7 sekcji, ~148 linii)
- Przepisanie PROGRESS.md (4 sekcje, skondensowane z 785 linii)
- Rozbudowanie DEVELOPMENT_STANDARDS.md (722 linii, 15 sekcji wg shared/standards)
- Rozbudowanie IMPLEMENTATION_PROMPT.md (284 linii, 11 sekcji, aktualny kontekst v0.3.2)
- Aktualizacja README.md, PRD.md, SCOPE.md
- Auto-naprawa kodu przez `ruff check --fix` (63 poprawki: importy, type annotations)

### Added
- Konfiguracja ruff (linter + formatter) w pyproject.toml
- Plik .editorconfig
- Sekcja [project.optional-dependencies] dev w pyproject.toml
- docs/DECISIONS.md — rejestr 9 decyzji architektonicznych (ADR)

### Removed
- Plik .flake8 (konfiguracja pokryta przez ruff)
- Sekcja [tool.black] z pyproject.toml

---

## [0.3.2] - 2026-01-21

### Changed - Storage Structure and Default Vertical CRS

- **Domyślny układ wysokościowy zmieniony na EVRF2007**
  - `GugikProvider`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - `DownloadManager`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - CLI: `--vertical-crs` domyślnie `EVRF2007`
  - Kronsztadt 86 (KRON86) jest przestarzały i dostępny jako opcja legacy

- **Nowa struktura katalogów z rozdzielczością**
  - `FileStorage`: nowy parametr `resolution` (domyślnie `"1m"`)
  - Pliki NMT są teraz rozdzielone według rozdzielczości:
    ```
    data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 1m
    data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 5m
    ```
  - `DownloadManager` automatycznie przekazuje `resolution` do `FileStorage`
  - Domyślne rozszerzenie pliku zmienione z `.tif` na `.asc`

### Breaking Changes

- **Struktura katalogów** - pliki NMT są teraz zapisywane w podkatalogu `1m/` lub `5m/`
  - Stara ścieżka: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
  - Nowa ścieżka: `data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`

- **Domyślny vertical_crs** - zmieniony z `KRON86` na `EVRF2007`
  - Aby używać starego układu: `--vertical-crs KRON86`

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (EVRF2007 domyślnie)
kartograf download N-34-130-D-d-2-4
# → data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m
# → data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Użyj starego układu Kronsztadt (legacy)
kartograf download N-34-130-D-d-2-4 --vertical-crs KRON86
```

---

## [0.3.1] - 2026-01-21

### Added - NMT Resolution Selection

- **Wybór rozdzielczości NMT** - Obsługa danych NMT w dwóch rozdzielczościach
  - `1m` (GRID1) - wysoka rozdzielczość, domyślna
  - `5m` (GRID5) - niższa rozdzielczość, tylko dla EVRF2007

- **GugikProvider** - Nowy parametr `resolution`
  - `GugikProvider(resolution="5m", vertical_crs="EVRF2007")`
  - Nowe endpointy WMS dla 5m: `SheetsGrid5mEVRF2007`
  - Automatyczna walidacja: 5m wymaga EVRF2007
  - Nowe metody: `get_supported_resolutions()`, `is_wcs_available()`
  - `download_bbox()` rzuca ValueError dla 5m (WCS niedostępne)

- **DownloadManager** - Nowy parametr `resolution`
  - `DownloadManager(resolution="5m")` - automatycznie wymusza EVRF2007

- **CLI** - Nowa opcja `--resolution`
  - `kartograf download N-34-130-D --resolution 5m`
  - Skrót: `-r 5m`

**Ograniczenia 5m:**
- Dostępne tylko w układzie EVRF2007
- Brak obsługi WCS (download_bbox) - tylko arkusze OpenData

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (domyślnie)
kartograf download N-34-130-D-d-2-4

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m

# Pobierz hierarchię w 5m
kartograf download N-34-130-D --scale 1:10000 -r 5m
```

### Changed

- **Testy** - 365 testów (18 nowych dla resolution)

### Fixed - Cross-Project Compatibility (2026-01-21)

- **Public API exports** - Uzupełniono brakujące eksporty w głównym module
  - Dodano `SoilGridsProvider` do `kartograf/__init__.py`
  - Dodano `HSGCalculator` do `kartograf/__init__.py`
  - Teraz możliwy import: `from kartograf import SoilGridsProvider, HSGCalculator`

### Fixed - QA Review (2026-01-21)

- **Synchronizacja wersji** - Ujednolicono wersję we wszystkich plikach
  - `pyproject.toml`: 0.3.0 → 0.3.1
  - `kartograf/__init__.py`: 0.3.0-dev → 0.3.1
  - `README.md`: zaktualizowano status i liczbę testów

- **Synchronizacja zależności** - Uzupełniono brakujące zależności
  - `pyproject.toml`: dodano `rasterio>=1.3.0`, `numpy>=1.24.0`
  - `requirements.txt`: dodano `PyJWT[crypto]>=2.8.0`

- **Testy** - Naprawiono test wersji w `test_integration.py`

- **Dokumentacja** - Dodano sekcję QA Review do `PROGRESS.md`

---

## [0.3.0] - 2026-01-18

### Added - SoilGrids i Hydrologic Soil Groups (HSG)

- **SoilGridsProvider** - Provider dla ISRIC SoilGrids (dane glebowe)
  - Globalne dane glebowe w rozdzielczości 250m
  - WCS Endpoint: `https://maps.isric.org/mapserv`
  - **11 parametrów glebowych:**
    - `bdod` - Gęstość objętościowa (kg/dm³)
    - `cec` - Pojemność wymiany kationowej (cmol/kg)
    - `cfvo` - Fragmenty gruboziarniste (%)
    - `clay` - Zawartość gliny (%)
    - `nitrogen` - Azot całkowity (g/kg)
    - `ocd` - Gęstość węgla organicznego (kg/m³)
    - `ocs` - Zasób węgla organicznego (t/ha)
    - `phh2o` - pH w H2O
    - `sand` - Zawartość piasku (%)
    - `silt` - Zawartość pyłu (%)
    - `soc` - Węgiel organiczny (g/kg)
  - **6 głębokości:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
  - **5 statystyk:** mean, Q0.05, Q0.5, Q0.95, uncertainty
  - Transformacja CRS: EPSG:2180 → WGS84

- **HSGCalculator** - Kalkulacja Hydrologic Soil Groups dla metody SCS-CN
  - `kartograf/hydrology/hsg.py` - moduł hydrologiczny
  - Klasyfikacja tekstury gleby wg trójkąta USDA (12 klas)
  - Mapowanie tekstury do HSG (A, B, C, D)
  - **Grupy hydrologiczne:**
    - A - wysoka infiltracja (piasek, piasek gliniasty)
    - B - umiarkowana infiltracja (glina piaszczysta, glina)
    - C - wolna infiltracja (glina ilasta)
    - D - bardzo wolna infiltracja (ił)
  - Automatyczne pobieranie clay/sand/silt z SoilGrids
  - Statystyki pokrycia dla każdej grupy HSG

- **CLI soilgrids** - Nowe komendy CLI
  - `kartograf landcover download --source soilgrids --property <param> --depth <głębokość>`
  - `kartograf landcover list-layers --source soilgrids`
  - `kartograf soilgrids hsg --godlo <godło>` - kalkulacja HSG
  - Opcje HSG: `--depth`, `--output`, `--keep-intermediate`, `--stats`

**Przykłady użycia:**
```bash
# Pobierz węgiel organiczny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc

# Pobierz zawartość gliny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Oblicz HSG dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats
```

### Added - Land Cover (Pokrycie Terenu)

- **LandCoverProvider** - Nowa abstrakcja dla providerów danych pokrycia terenu
  - Metody: `download_by_teryt()`, `download_by_bbox()`, `download_by_godlo()`
  - Wspólny interfejs dla różnych źródeł danych

- **Bdot10kProvider** - Provider dla BDOT10k (GUGiK)
  - Pobieranie paczek powiatowych przez TERYT
  - Pobieranie przez WMS GetFeatureInfo dla URL paczki
  - Pobieranie przez godło arkusza (konwersja na bbox)
  - **12 warstw pokrycia terenu (PT*):**
    - PTGN - Grunty nieużytkowe
    - PTKM - Tereny komunikacyjne
    - PTLZ - Tereny leśne
    - PTNZ - Tereny niezabudowane
    - PTPL - Place
    - PTRK - Roślinność krzewiasta
    - PTSO - Składowiska
    - PTTR - Tereny rolne
    - PTUT - Uprawy trwałe
    - PTWP - Wody powierzchniowe
    - PTWZ - Tereny zabagnione
    - PTZB - Tereny zabudowane
  - Automatyczne scalanie warstw PT* z ZIP do jednego GeoPackage
  - Format wyjściowy: GeoPackage (.gpkg), SHP

- **CorineProvider** - Provider dla CORINE Land Cover (Copernicus)
  - Europejska klasyfikacja pokrycia terenu (44 klasy)
  - Dostępne lata: 1990, 2000, 2006, 2012, 2018
  - **Trzy źródła danych (w kolejności priorytetu):**
    1. **CLMS API** - GeoTIFF z kodami klas (wymaga OAuth2)
    2. **EEA Discomap WMS** - Podgląd PNG (lata 2000-2018)
    3. **DLR WMS** - Fallback dla 1990
  - OAuth2 RSA authentication dla CLMS API
  - Przechowywanie credentials w macOS Keychain (serwis: `clms-token`)

- **LandCoverManager** - Zarządzanie pobieraniem danych pokrycia terenu
  - Dispatch do odpowiedniego providera
  - Obsługa wielu metod selekcji obszaru

- **CLI landcover** - Nowe komendy CLI
  - `kartograf landcover download --source bdot10k --teryt <kod>`
  - `kartograf landcover download --source corine --year <rok> --godlo <godło>`
  - `kartograf landcover list-sources`
  - `kartograf landcover list-layers --source bdot10k`

### CLMS API Authentication - Auth Proxy

CorineProvider używa **Auth Proxy** dla bezpiecznej autentykacji CLMS API:

**Architektura bezpieczeństwa:**
```
CorineProvider → localhost HTTP → AuthProxy (subprocess) → Keychain → CLMS API
```

- Credentials (klucz prywatny RSA) są izolowane w osobnym procesie
- Główna aplikacja nigdy nie widzi credentials
- Tylko odpowiedzi API są przekazywane do aplikacji

**Nowe moduły:**
- `kartograf/auth/proxy.py` - serwer HTTP izolujący credentials
- `kartograf/auth/client.py` - klient automatycznie uruchamiający proxy

**Konfiguracja:**
1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (JSON)
3. Zapisz do Keychain:
   ```bash
   security add-generic-password -a "$USER" -s "clms-token" -w '<json_credentials>'
   ```

**Tryby pracy:**
```python
# Domyślny (bezpieczny) - używa proxy
provider = CorineProvider()

# Bezpośredni (dla testów) - credentials widoczne
provider = CorineProvider(clms_credentials={...}, use_proxy=False)
```

**Uwaga:** Jeśli credentials nie są skonfigurowane, CorineProvider automatycznie używa WMS (podgląd PNG zamiast GeoTIFF z kodami klas).

### Dependencies

- Dodano `PyJWT[crypto]>=2.8.0` - JWT generation dla OAuth2
- Dodano `rasterio>=1.3.0` - przetwarzanie rastrów GeoTIFF
- Dodano `numpy>=1.24.0` - operacje na tablicach

### Technical Details

- 347 testów (42 dla landcover, 28 dla soilgrids, 34 dla HSG)
- Formatowanie: black, flake8

### Sources

- BDOT10k: https://www.geoportal.gov.pl/en/data/topographic-objects-database-bdot10k/
- CORINE Land Cover: https://land.copernicus.eu/en/products/corine-land-cover
- EEA Discomap: https://image.discomap.eea.europa.eu
- DLR EOC: https://geoservice.dlr.de/eoc/land/wms
- ISRIC SoilGrids: https://soilgrids.org/
- SoilGrids Documentation: https://docs.isric.org/globaldata/soilgrids/

---

## [0.2.0] - 2026-01-18

### Changed - Nowa architektura pobierania

**Uproszczona logika pobierania:**
- **Godło → OpenData (ASC)** - pobieranie arkusza przez godło zawsze daje plik ASC
- **BBox → WCS (GeoTIFF)** - pobieranie przez bounding box daje GeoTIFF/PNG/JPEG

**Zmiany API:**
- `download_sheet(godlo)` - zawsze pobiera ASC (usunięto parametr `format`)
- `download_hierarchy(godlo, target_scale)` - pobiera wszystkie arkusze jako ASC
- `download_bbox(bbox, filename, format)` - **nowa metoda** dla pobierania przez bbox
- Usunięto `construct_url()` z publicznego API
- `DownloadManager` nie przyjmuje już parametru `format` w konstruktorze

### Added

- **Pobieranie ASC przez OpenData** - Automatyczne wyszukiwanie URL przez WMS GetFeatureInfo
  - Zapytania do warstw: `SkorowidzeNMT2019`, `SkorowidzeNMT2018`, `SkorowidzeNMT2017iStarsze`
  - Pobieranie z `opendata.geoportal.gov.pl`

- **SheetParser.get_bbox()** - Obliczanie bounding box arkusza
  - Obsługiwane CRS: `EPSG:2180` (PL-1992), `EPSG:4326` (WGS84)
  - Transformacja współrzędnych przez `pyproj`

- **BBox** - Nowy typ danych w public API

- **GugikProvider.download_bbox()** - Pobieranie przez bounding box z WCS

### Dependencies

- Dodano `pyproj>=3.6.0` do wymagań

### Technical Details

- 245 testów

## [0.1.0] - 2026-01-17

### Added

- **SheetParser** - Parser for Polish topographic map sheet identifiers (godlo)
  - Support for scales 1:1,000,000 to 1:10,000
  - Support for "1992" coordinate system layout
  - Hierarchy navigation: `get_parent()`, `get_children()`, `get_hierarchy_up()`
  - Descendant enumeration: `get_all_descendants(target_scale)`
  - Special handling for 1:500k to 1:200k division (36 sheets per section)

- **DownloadManager** - Coordinated download of NMT data
  - Single sheet download: `download_sheet(godlo)`
  - Hierarchy download: `download_hierarchy(godlo, target_scale)`
  - Progress callbacks with `DownloadProgress` dataclass
  - Skip existing files option for resumable downloads
  - Missing sheets detection: `get_missing_sheets()`

- **GugikProvider** - Integration with GUGiK WCS service
  - GeoTIFF and Arc/Info ASCII Grid format support
  - Retry logic with exponential backoff (3 attempts)
  - 30-second timeout per request

- **FileStorage** - Hierarchical file storage management
  - Automatic directory structure based on godlo components
  - Atomic writes (temp file + rename)
  - Path generation: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif`

- **CLI** - Command-line interface
  - `kartograf parse <godlo>` - Display sheet information
  - `kartograf parse <godlo> --hierarchy` - Show hierarchy to 1:1M
  - `kartograf parse <godlo> --children` - Show direct children
  - `kartograf download <godlo>` - Download single sheet
  - `kartograf download <godlo> --scale <scale>` - Download hierarchy
  - Options: `--format`, `--output`, `--force`, `--quiet`

- **Public API** - Clean imports from main module
  - `from kartograf import SheetParser, DownloadManager`
  - All exceptions: `KartografError`, `ParseError`, `ValidationError`, `DownloadError`
  - Providers: `BaseProvider`, `GugikProvider`

- **Test Coverage** - 97% coverage with 235 tests
  - Unit tests for all modules
  - Integration tests for complete workflows

### Technical Details

- Python 3.12+ required
- Single dependency: `requests>=2.31.0`
- Project structure follows src layout
- Configured with black, flake8, pytest

[0.7.0]: https://github.com/Daldek/Kartograf/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/Daldek/Kartograf/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/Daldek/Kartograf/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Daldek/Kartograf/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Daldek/Kartograf/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Daldek/Kartograf/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.2
[0.3.1]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.1
[0.3.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.0
[0.2.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.2.0
[0.1.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.1.0
