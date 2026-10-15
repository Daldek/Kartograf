# Architektura Kartografa

**Wersja opisywana:** kod galezi, w ktorej lezy ten plik — nie stan na
konkretny dzien. Wersja pakietu: `kartograf/__init__.py` (`__version__`);
zmiany per wydanie: `docs/CHANGELOG.md`; biezacy stan prac: `docs/PROGRESS.md`;
przewodnik uzytkownika (przyklady CLI i biblioteki): `docs/USAGE.md`;
konwencje i proces pracy: `docs/DEVELOPMENT_STANDARDS.md`.
Pomiary i weryfikacje na zywych serwisach, na ktore powoluja sie sekcje
ponizej, sa datowane w tekscie, a ich raporty leza w `docs/research/`
(nazwy z data `RRRR-MM-DD-<temat>`).

Dokument kanoniczny: README/CLAUDE.md/SCOPE/USAGE odsylaja tutaj; przy sprzecznosci
rozstrzyga ARCHITECTURE.md + DECISIONS.md.

Kazde twierdzenie o zachowaniu systemu jest opisem KODU w tym repo, nie planu
ani specu. Gdzie kod odbiega od specu, dokument opisuje kod i mowi o tym wprost.

---

## 1. Przeglad i zasady projektowe

**Deskryptory jako dane.** Kazdy zbior danych (NMT 1 m z GUGiK, DMR 5G z CUZK,
CORINE, SoilGrids...) jest opisany jednym `SourceDescriptor` w
`kartograf/sources/registry.py`: kanaly dostepu, uklady poziome i pionowe,
licencja, schemat kafli, szablon katalogu, domyslne rozszerzenie pliku. Modul
`sources/` nie robi zadnego IO przy imporcie — to czyste dane i kilka funkcji
wyszukujacych. Rejestr jest zrodlem prawdy dla podkatalogu skladowania
(`storage_subdir`), rozszerzenia (`default_extension`), licencji w sidecarze
oraz capabilities kanalu — slownik nazw to `sheet_files`, `bbox_raster`,
`area_files`, `admin_unit_files`, `archive_unit_files`, `country_files`,
`bbox_vector` (ktore z nich deklaruje dany zbior, mowi jego wpis
w `registry.py`). Logika wykonawcza zostaje w providerach —
deskryptor mowi CO zrodlo potrafi i gdzie ma wyladowac wynik, nie JAK je pobrac.
Wyjatkiem sa kanaly kolekcji (ADR-042): typowane parametry kanalu
(`AccessChannel.params`) konfiguruja generyczne silniki paczek jednostek
i obiektow obszaru, wiec taki produkt nie ma providera (sekcja 4.10).

**Sidecar przy kazdym udanym pobraniu.** Obok kazdego pliku danych powstaje
`<pelna_nazwa_pliku>.meta.json` ze schema `kartograf-meta/1`: uklad poziomy
i pionowy, `nodata`, oryginalne zadanie, licencja, wersja pakietu, opis
wykonanych transformacji. Sidecary pisza **warstwy zarzadzajace** —
`DownloadManager`, `LandCoverManager`, wycinek PL w bibliotece
(`download/cutout.py::write_pl_wcs_cutout_sidecar`), kafle LAZ w bibliotece
(`download/laz.py::write_laz_sidecar`, ADR-029), wynik HSG
(`HSGCalculator._reuse_or_compute`, sekcja 4.8), wynik CZ
(`download/cz_cutout.py::write_cz_sidecar`, takze z `download/cz_sheets.py`)
i pliki kolekcji (`download/collections.py::run_job`, sekcja 4.10)
— nigdy providery; provider zwraca `Path`, metadane skladane sa pietro wyzej,
gdzie znany jest kontekst zadania.
kontekst zadania. Wynika z tego, ze bezposrednie wywolanie
providera z biblioteki (np. `GugikProvider.download`,
`CuzkDmrProvider.download`/`download_bbox`) zapisuje sam plik danych, bez
sidecara — w szczegolnosci sidecar DMR CZ pisze
`download/cz_cutout.py::write_cz_sidecar`: dla wycinka bbox wolany przez
`download_cz_cutout` (sekcja 4.5), dla godla CZ przez `download_cz_sheet`
(`download/cz_sheets.py`), bo tor CZ omija `DownloadManager` (ADR-023).
Nowy sidecar powstaje zawsze przez
`sources/sidecar.py::emit_sidecar` — jedyne miejsce polityki zapisu
(poza nim: kopia sidecara wersji w sciezce standardowej,
`download/links.py::write_link_sidecar`, i uzupelnianie informacji o lotach
przez `update_sidecar_extra` w sidecarze dowiazania). Zapis poza magazynem
wersjonowanym jest best-effort: blad budowy metadanych lub zapisu konczy sie
ostrzezeniem (`logger.warning`) bez przerwania pobrania; `emit_sidecar`
zwraca `None` przy bledzie budowy, natomiast przy bledzie zwyklego zapisu
`write_sidecar` zwraca sciezke mimo braku pliku. Provider bez
`descriptor_key` (`descriptor_key` nie bedacy `str`) daje `None` bez
ostrzezenia. Sidecar WERSJI w magazynie (ADR-036, sekcja 3.3) jest
obowiazkowy i pisany wylacznie (`exclusive=True`: tmp + `fsync` +
`os.link`); bez deskryptora powstaje sidecar okrojony (`request`, `extra`,
`sha256`, `size_bytes`, `downloaded_at`, `kartograf_version`), a kazdy
inny blad to `DownloadError` i brak wersji. Sidecar wersji nigdy sie nie
zmienia (`extra.parent_requests` usuniete w 0.8.0; `parent_request`
opisuje zadanie, ktore utworzylo wersje).

**Polityka transformacji (ADR-024).** Transformacje, ktore przesuwaja TRESC
rastra albo opuszczaja uklady czeskie (EPSG:5514/3045), przechodza przez
`kartograf/transform/crs.py` — poza obwiednia w WGS84 do rozpoznania kraju
i przyciecia pod `auto` (`bbox_to_wgs84` w `download/countries.py`, takze dla
bboxa podanego w ukladzie czeskim) i obwiednia pliku geometrii w torze LAZ
(`_resolve_laz_bbox`: `get_overall_bbox(..., target_crs="EPSG:2180")`).
Przeliczenia obwiedni miedzy ukladami PL i WGS84 (selekcja arkuszy
w `core/sheet_parser.py` i `core/geometry.py`, `bbox_to_2180` wycinka
i odkrywania TERYT dla ukladow nieczeskich, dyspozycja krajow w CLI,
obwiednia bboxa EPSG:2180 w ukladzie uslugi CORINE/SoilGrids — `transform/bbox.py::envelope_from_2180`)
swiadomie uzywaja domyslnego transformera pyproj — migracja to backlog A5-6.
`transform/crs.py` ma cztery twarde reguly: (1) transformer budowany tylko przez
`TransformerGroup(..., always_xy=True, allow_ballpark=False)` — `Transformer.
from_crs` potrafi cicho zwrocic identycznosc; (2) pusta lista operacji to
`TransformUnavailableError`, nigdy fallback; (3) odrzucane sa operacje
o nieznanej dokladnosci (`accuracy < 0`) i powyzej `policy.min_accuracy_m`,
a pozostale przechodza probe na punkcie kontrolnym (inf/NaN = odrzut, to
przypadek siatki obcego kraju); (4) kazdy wynik przechodzi `isfinite`.
Wybrana operacja jest **przypieta** (`PinnedTransform`) i przy reprojekcji
rastra WYMUSZANA na GDAL-u przez `COORDINATE_OPERATION` — bez tego GDAL
wybiera operacje sam, poza polityka. Pulapka osi jest tu realna, nie
teoretyczna: pipeline pochodzi z transformera `always_xy=True`, a GDAL podaje
wspolrzedne w kolejnosci osi autorytatywnej, wiec `proj=axisswap order=2,1`
dokladane jest NIEZALEZNIE dla zrodla (na czele pipeline'u) i dla celu (na
koncu) — za kazdym razem, gdy dany uklad jest northing-first (EPSG:2180,
EPSG:3045; EPSG:5514 nie jest). Brak korekty daje raster w calosci nodata,
takze po stronie zrodla: zmierzone dla toru PL 2180 -> 5514 bez czolowego
`axisswap` — **0 z 46225 waznych pikseli**. Korekta jest liczona
z `axis_info`, nie zakladana. Po filtrach dokladnosci wybierana jest
najdokladniejsza operacja, ale dla kroku datum S-JTSK -> ETRS89/WGS 84
obowiazuje dodatkowy pin EPSG:1622/1623 (`DATUM_STEP_PINS`), wykluczajacy
EPSG:4829 dla Slowacji nawet gdy jego nominalne 0,5 m wyglada lepiej.
Nominalna dokladnosc czeskiej operacji wynosi 1,0 m (ADR-024, errata 2).

**Brak scalania miedzykrajowego (w 0.7.0).** Zadanie obszarowe przecinajace
wiecej niz jeden kraj daje **osobne pliki i osobne sidecary per kraj**,
powiazane wspolnym `extra.parent_request`. W 0.7.0 Kartograf nie sklada
mozaiki transgranicznej i nie harmonizuje pionu miedzy krajami — pliki PL i CZ
scala konsument (Hydrograf). Scalanie PL+CZ w jedna ciagla powierzchnie
przygraniczna (wspolna siatka, EVRF2007 po obu stronach) to etap 2 Kartografa
(R6, 2026-09-28; wczesniej zapisane jako zadanie Hydrografa; dane styku
zmierzone na zywo 2026-09-29 — sekcja 4.6). Kartograf dostarcza wszystko,
czego takie scalenie wymaga: jawne kody CRS obu osi, `nodata`, opis uzytej
operacji z dokladnoscia i wspolny klucz grupowania.

---

## 2. Warstwy i zaleznosci modulow

Graf krawedzi importu miedzy pakietami najwyzszego poziomu `kartograf/`.
`(l)` = krawedz WYLACZNIE leniwa (import tylko wewnatrz funkcji); bez znaku =
co najmniej jeden import na poziomie modulu (takze pod `if TYPE_CHECKING:`).
`kartograf` = pakiet glowny (`kartograf/__init__.py`):

```
kartograf ──> core, download, providers, landcover, hydrology, cache,
        sources, transport, notices, project       # re-eksport Public API
cli ──> _version, download, landcover, core, hydrology, cache,
        notices, transform, project, sources, kartograf
project ──> download, landcover, hydrology, core, sources, cache,
        notices, _version, kartograf (_clock)
download ──> providers, sources, transform, core, cache, notices,
        _version, kartograf (_clock), transport
landcover ──> providers, download, core, cache, sources, notices, transport
hydrology ──> core, download, landcover, cache (TYPE_CHECKING), notices,
        providers (l), sources (l), transform (l)
providers ──> sources, transform, transport, core, cache,
        auth (l), download (l)
sources ──> core, kartograf (_clock), _version
transport ──> transform, core, sources, kartograf (l, __version__)
transform ──> core, sources (TYPE_CHECKING), transport (TYPE_CHECKING)
cache ──> core (TYPE_CHECKING), notices
_version ──> kartograf (l, __version__)
_clock, notices, auth ──> (nic wewnetrznego)
core ──> (nic poza exceptions)
exceptions ──> (lisc; krawedzie DO niego pominiete powyzej — importuja go
        kartograf, cli, core, sources, transform, transport, providers, download,
        landcover, hydrology, cache, project)
```

**Jak odtworzyc graf.** Kod uzywa wylacznie bezwzglednych importow
wewnetrznych, wiec komplet krawedzi daje:

```bash
grep -rnE '^\s*(from|import) kartograf' kartograf/ --include=*.py
```

Krawedz to pakiet pliku zrodlowego (drugi czlon sciezki
`kartograf/<pakiet>/...`) -> pakiet modulu docelowego (`kartograf.<pakiet>`);
importy wewnatrz tego samego pakietu sie pomija. Wiersz z wcieciem to zwykle
import leniwy, ale wciecie maja tez importy pod `if TYPE_CHECKING:`/`try:`
na poziomie modulu — rozstrzyga polozenie instrukcji w AST (wezel
`Import`/`ImportFrom` w ciele funkcji = leniwy). Graf trzeba poprawic przy
kazdej nowej krawedzi miedzy pakietami.

Uwagi, ktore latwo przeoczyc:

- `core` nie importuje nic spoza `core` i `exceptions` — takze leniwie.
  Kierunek jest odwrotny: `providers.cuzk.sheets`
  i `core.parser_tm33` importuja wzorce godel CZ z `core.parser_registry`.
  Operacja przypieta (ADR-024) wchodzi do `core.bbox.transform_bbox`
  przez duck typing (`transformer=`), bez importu `transform`.
- `download` siega po `transform` w `download/cutout.py` (wycinek PL,
  sekcja 4.3) i leniwie w `download/collections.py` (zapis GPKG wyniku
  obszaru, sekcja 4.10). Po `transport` siega leniwie w
  `download/cutout.py` i `download/cz_cutout.py` oraz na poziomie modulu
  w `download/cz_sheets.py` (`response_signal`). `cutout.py` importuje na
  poziomie modulu `transform.crs` (`PinnedTransform`, `CONTENT_POLICY`,
  `WARP_MARGIN_PX`), leniwie `build_pinned_transform`, `transform.raster`
  (warp wycinka WCS), `transport.aaigrid`, `transport.chunks` i
  `transport.mosaic.has_valid_pixels`; `cz_cutout.py` importuje leniwie
  ostatnia funkcje (kontrola `all_nodata`).
  `manager.py` i `storage.py` nie importuja zadnego z nich —
  `DownloadManager` pozostaje warstwa koordynacji arkuszy.
- `download/collections.py` (kolekcje, ADR-042, sekcja 4.10) importuje na
  poziomie modulu `transport.http` (`SessionPerThread`, `head_signal`)
  i `transport.unit_package` (paczki jednostek), a leniwie - dopiero dla
  wyniku obszaru - `transport.feature_bbox.fetch_features`
  i `transform.gpkg.write_gpkg`: GDAL wektorowy (`pyogrio`) laduje sie
  tylko wtedy, gdy zadanie pobiera obiekty uslugi. Z `providers` bierze
  `providers.pl.prg.discover_teryts_for_bbox` (powiaty obszaru)
  i `WOJEWODZTWO_NAMES`, leniwie `providers.cuzk.dmr.bbox_to_crs`.
- `cli` tylko tlumaczy flagi na argumenty funkcji poziomu komendy
  i wypisuje wynik (Z1, ADR-037): importuje `download.data`
  (`download_data`/`check_data`), `download.availability`
  (`check_availability`, ADR-041), `download.collections`
  (`download_collection`/`check_collection` i teksty wyborow `--help`
  grup kolekcji), `landcover.manager`, `hydrology`,
  `download.plan`/`fetch` (plik planu, linie statusu), `notices`,
  `_version` i `cache`; z `transform` bierze tylko `TransformError`,
  z `sources` deskryptory (`sources_for`; tabela `list-sources` z
  `SourceDescriptor.variants`), z pakietu glownego API projektu
  (`cli/project_cmd.py`); teksty `--help` z wariantow buduje `download/options.py`.
  Nie importuje `providers`, `transport` ani doboru arkuszy
  (`tests/test_cli_translation.py::test_cli_imports_no_data_logic`).
- Rejestr wariantow `sources/variants.py` (ADR-041) to czyste dane:
  importuje tylko `exceptions` i `sources.descriptor`, a `sources.registry`
  leniwie (rejestr buduje deskryptory z typow tego modulu). Czytaja go
  `download/options.py` (walidacja), `download/area.py` (`pl_only_flags`),
  `download/storage.py`, `download/cutout.py` (wariant z kanalem WCS),
  `download/availability.py`, providery PL (wariant, `IndexRef`) i `cli`.
- `download/availability.py` (raport, sekcja 4.9) importuje na poziomie
  modulu `providers.pl.skorowidz_wfs` (ten sam klient i parser rekordow
  co pobieranie arkuszy), `providers.pl.prg` (maska ladu),
  `providers.pl.gugik_laz.laz_tile` (parser kafla LAZ) i
  `transport.http` (`SessionPerThread`); nie importuje `DownloadManager`
  ani magazynu.
- `project` (`model`, `commands`, `manifest`, `operations`) mapuje komendy danych
  na funkcje biblioteki `download`/`landcover`/`hydrology`; nie implementuje
  logiki per produkt. `cli/groups/project.py` i `cli/project_cmd.py` tylko
  tlumacza argumenty i wypisuja wyniki API projektu (ADR-037, ADR-040).
- `transport ──> transform`: `transport/mosaic.py` owija zrodla mozaiki
  w VRT przez `transform.raster` (`vrt_xml`, `VRT_TYPES`; import na poziomie
  modulu). `transform` siega po `transport` i `sources` wylacznie pod
  `if TYPE_CHECKING:` (adnotacje `FeaturePages`/`LayerPages`
  i `FeatureBBoxParams` w `transform/gpkg.py`) — w czasie wykonania cyklu
  nie ma.
- `transport ──> sources`: silniki kolekcji (`transport/unit_package.py`,
  `transport/feature_bbox.py`) czytaja typowane parametry kanalu
  (`UnitPackageParams`, `PackageVariant`, `FeatureBBoxParams`,
  `FeatureLayer` z `sources/descriptor.py` — dane bez IO); `sources` nie
  importuje `transport`.
- `providers ──> download` jest leniwa i MUSI taka zostac (pakiet
  `download` importuje `providers` przy imporcie): walidacja lat i wyboru
  kampanii z `download.campaigns` w
  `SkorowidzLayersMixin.resolve_campaigns` (`providers/pl/skorowidz.py`)
  i w `GugikLazProvider.select_tiles` (`providers/pl/gugik_laz.py`) oraz
  przeliczenie obszaru do EPSG:2180 `download.area.bbox_to_2180`
  w `providers/pl/prg.py` (jedna regula dla wycinka PL i odkrywania TERYT).
- `cache ──> core` istnieje tylko pod `if TYPE_CHECKING:` (adnotacja
  `BBox` w `MetadataCache.get_teryts_for_bbox`/`set_teryts_for_bbox`);
  w czasie wykonania `cache.defaults` importuje `notices`, nie `core`.
- `landcover ──> cache`: `LandCoverManager(cache=MetadataCache | bool)`
  (`True` = wspolny cache w cwd, `cache/defaults.py::open_cache`) importuje
  `MetadataCache` na poziomie modulu (adnotacja) i przekazuje go
  providerom tworzonym po nazwie (`Bdot10kProvider(cache=)` — odpowiedzi
  PRG, `SoilGridsProvider(cache=)`); CORINE cache nie ma.
- `landcover ──> download`: `LandCoverManager` uzywa wspolnej polityki
  wersji (`download.fetch.use_local`/`store_file`/`inspect_version`,
  `download.plan`, `download.storage.content_segment`/`unit_slot`,
  `download.versions`), a archiwum rocznikow BDOT10k pobiera zadaniami
  jednostek orkiestratora kolekcji (`download.collections.package_job`/
  `run_job`/`inspect_job`, sekcja 4.10); `download` nie importuje
  `landcover` (cyklu nie ma).
- `landcover ──> transport`: `LandCoverManager` wybiera wariant archiwum
  BDOT10k (`--year`, `--format`) przez
  `transport.unit_package.select_variant` — bez sieci, ta sama regula co
  silnik paczek.
- `hydrology ──> core, download, landcover, cache` istnieje na poziomie
  modulu tylko pod `if TYPE_CHECKING:` (adnotacje `BBox`, `VersionedFile`,
  `PlanItem`, `LandCoverResult`, `MetadataCache`...; wg reguly grafu to import
  na poziomie modulu); `notices` jest importowane normalnie.
  W czasie wykonania reszta jest leniwa: `landcover.manager` (wejscia
  clay/sand/silt jako wersje), `download.fetch`/`plan`/`versions`
  (wersja HSG), `providers.soilgrids`, `core.sheet_parser`, `core.bbox`
  (`transform_bbox`), `transform` (przypieta reprojekcja wejsc
  `hsg_from_rasters`) i `sources.sidecar` (`emit_sidecar`, `file_digest`).
- `sources/sidecar.py` i `download/versions.py` importuja `_clock` przez
  pakiet glowny przy imporcie modulu, a `sources/sidecar.py` i
  `download/plan.py` importuja `_version.build_version`. Dopiero
  `build_version()` siega leniwie po `kartograf.__version__`;
  `transport/http.py` robi to leniwie dla naglowka `User-Agent`.
- Krawedz `download ──> providers` siega tez do zamrozonego toru CZ:
  `download/cutout.py` i `download/area.py` importuja leniwie generyczny
  `bbox_to_crs` z `providers/cuzk/dmr.py` (ADR-024); przeniesienie go do
  `transform/` to etap 2, razem z odmrozeniem toru CZ.

### Moduly

Drzewo wymienia kazdy modul `.py` pakietu (`auth/` i `cli/` zbiorczo,
`__init__.py` podpakietow tylko gdy niosa wlasna logike). Zrodlo prawdy:
pliki `.py` pod `kartograf/`; Public API: `kartograf/__init__.py` (`__all__`).

Stabilne API transportu i mozaiki (od 0.7.1): `get_with_retry` (dowolny URL
uslugi, polityka ponowien siec/429/5xx/`Retry-After`, tylko GET),
`make_gugik_session`, `mosaic_and_crop`, `check_source_grid` — eksportowane
z `kartograf`; zmiana sygnatury = zmiana lamiaca w CHANGELOG.

```
kartograf/
├── __init__.py          # Public API (BBox, SheetParser, DownloadManager, providery, ...)
├── _version.py         # build_version() — identyfikator wersji dev (git, leniwie)
├── exceptions.py        # KartografError; ParseError; ValidationError;
│                        # DownloadError(.sheet, .status_code)
│                        # -> NoCoverageError(DownloadError; .hints) — zrodlo nie ma danych
│                        # arkusza, .hints = podpowiedzi (np. --scale 1:2000)
├── core/                # Logika bazowa, bez IO sieciowego
│   ├── bbox.py             # BBox, validate_bbox, transform_bbox (gesta obwiednia: _DENSIFY
│   │                       # punktow na krawedz, cache transformerow, operacja przypieta
│   │                       # przez duck typing `transformer=`), is_czech_crs
│   ├── sheet_parser.py     # SheetParser (PL-1992), find_sheets_for_bbox (BBox z core/bbox.py)
│   ├── parser_2000.py      # Parser2000 (PL-2000), find_sheets_2000_for_bbox
│   ├── parser_tm33.py      # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045)
│   ├── parser_registry.py  # Rejestr systemow godel (SYSTEMS: pl2000, cz_tm33, cz_sm5,
│   │                       # pl1992), detect_system/path_parts ze strip(), wzorce CZ
│   ├── geometry.py         # Czytanie SHP/GPKG, resolve_layer (wybor warstwy),
│   │                       # find_sheets_for_geometry, get_overall_bbox
│   └── coverage.py         # Wypukle wielokaty: przeciecie, roznica, bufor (wybor kafli LAZ)
├── sources/             # Deskryptory zrodel jako dane (zero IO przy imporcie)
│   ├── descriptor.py    # SourceDescriptor (+ resolve_subdir, variants), AccessChannel,
│   │                    # TransportKind, TileScheme, LicenseInfo, CountryProfile;
│   │                    # parametry kanalow kolekcji (AccessChannel.params, ADR-042):
│   │                    # UnitPackageParams/PackageVariant, FeatureBBoxParams/FeatureLayer
│   ├── registry.py      # Rejestr PL/CZ/EU/GLOBAL: get_source, sources_for, get_country,
│   │                    # all_countries, vertical_crs_code, resolve_vertical_crs (rodzina ->
│   │                    # realizacja), parse_pl_system, horizontal_crs_for_sheet/_for_system;
│   │                    # deskryptory NMT/NMPT per (produkt, format, rozdzielczosc) z wariantami
│   ├── variants.py      # Rejestr wariantow (ADR-041): IndexRef, FileFormat/FORMATS, ProductVariant,
│   │                    # variants(), resolution_label/parse_resolution (etykiety K2),
│   │                    # source_format (twardy filtr formatu), variant_error/find_variant
│   ├── edition.py       # Edition (wydanie zrodla, sygnal metadata D29), edition_label
│   └── sidecar.py       # ResultMetadata, build_metadata, write_sidecar, emit_sidecar
│                        # (jedyna polityka zapisu), pl_sheet_horizontal_crs, read_asc_nodata
├── transform/           # Transformacje wspolrzednych i rastrow; zapis GPKG
│   ├── bbox.py          # envelope_from_2180 — obwiednia bboxa EPSG:2180 w innym ukladzie
│   │                    # (CORINE, SoilGrids; domyslny transformer pyproj, sekcja 1)
│   ├── crs.py           # TransformPolicy, PinnedTransform, build_pinned_transform, KNOWN_PATHS;
│   │                    # TransformError -> TransformUnavailableError (brak bezpiecznej operacji)
│   ├── raster.py        # warp_to_grid — lokalny warp na siatke, operacja WYMUSZONA (tory PL
│   │                    # i CZ); vrt_xml/VRT_TYPES dla transport/mosaic.py
│   └── gpkg.py          # write_gpkg — deterministyczny GPKG wyniku feature_bbox (pyogrio:
│                        # dedupe i sort po id, drop_fields do sidecara; ADR-042 D5), GpkgSummary
├── transport/           # Wspolny transport
│   ├── http.py          # download_to (pliki WSZYSTKICH providerow; zapis atomowy os.replace)
│   │                    # i get_with_retry (zapytania: skorowidz WMS/WFS, WFS LAZ, WFS PRG,
│   │                    # CuzkClient.query) — jedyne miejsce retry (siec, 429, 5xx;
│   │                    # Retry-After): is_retryable, retry_wait, backoff_delay;
│   │                    # make_gugik_session, SessionPerThread (sesja per watek)
│   ├── chunks.py        # GridSpec, ChunkLimits, Chunk; align_bbox, plan_chunks,
│   │                    # fetch_chunks — wspolne kawalki CUZK i GUGiK WCS
│   ├── aaigrid.py       # multipart WCS -> ASC (streaming), walidacja siatki i atomowy GeoTIFF float32
│   ├── mosaic.py        # mosaic_and_crop — merge rastrow + przyciecie, propagacja nodata;
│   │                    # bez dtype= mieszane typy pasm -> ValidationError;
│   │                    # opcjonalnie (dtype=) owijanie zrodel w VRT;
│   │                    # check_source_grid (fazy siatki, SourceGrid.off_grid), has_valid_pixels
│   ├── unit_package.py  # Silnik paczek jednostek (ADR-042 D1-D2): select_variant (bez sieci),
│   │                    # package_url ({teryt}/{woj}), fetch_package (Content-Length, katalog
│   │                    # ZIP, wymagane czlony, rozpakowanie jednego czlonu; 404 = NoCoverageError)
│   └── feature_bbox.py  # Silnik obiektow obszaru (ADR-042 D3/D4): WFS 2.0 i ArcGIS REST —
│                        # metadane swiezo, liczba obiektow, strony po pozycji, kompletnosc;
│                        # count_features, fetch_features -> FeaturePages (strony na dysku)
├── providers/           # Providery danych
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider, LandCoverProvider
│   ├── pl/              # GUGiK: gugik.py (NMT; jeden wariant rejestru na provider, P10,
│   │                    # index_sheets — arkusze archiwum ze skorowidza), gugik_nmpt.py,
│   │                    # gugik_orto.py, gugik_laz.py (select_tiles, select_all_intersecting;
│   │                    # transport WfsIndex), bdot10k.py,
│   │                    # skorowidz.py (SkorowidzRecord, wybor ADR-028,
│   │                    # SkorowidzLayersMixin: warstwy WMS GetCapabilities/GetFeatureInfo
│   │                    # dla orto, resolve_campaigns/download_record/
│   │                    # record_source/available_years; select_campaign_records,
│   │                    # coverage_hints/no_coverage_error),
│   │                    # skorowidz_wfs.py (WfsIndex — GetCapabilities/GetFeature skorowidzy
│   │                    # WFS NMT/NMPT/LAZ, parse_index_feature, feature_footprint,
│   │                    # overlaps_area, sheet_frame_2180, WfsSkorowidzLayersMixin),
│   │                    # wcs.py (GugikWcsMixin — kawalki GetCoverage NMT/NMPT 1 m, orto),
│   │                    # prg.py (WFS PRG: maska ladu A00 - W02 - W03 dla wycinka i raportu
│   │                    # dostepnosci, LandMask.burn, discover_teryts_for_bbox,
│   │                    # teryt_for_point), __init__.py (create_nmt_provider)
│   ├── cuzk/            # CUZK: client.py (CuzkClient — silnik sterowany deskryptorem: ArcGIS
│   │                    # REST query/export_image + pliki openzu), sheets.py (SheetIndex/
│   │                    # SheetInfo — indeks SM5/TM33 z KladyMapovychListu, odsiewa
│   │                    # nadmiarowy wybor uslugi), dmr.py (CuzkDmrProvider — DMR 5G/4G,
│   │                    # opcjonalnie Bpv -> EVRF2007), __init__.py (create_dmr_provider —
│   │                    # jedyne miejsce czeskich domyslow)
│   ├── corine.py        # CORINE z Copernicus CLMS (+ fallback WMS PNG)
│   └── soilgrids.py     # SoilGrids z ISRIC (WCS)
├── _clock.py            # now() — jedno zrodlo czasu wynikow (sidecar, etykiety wersji,
│                        # plan); testy zgodnosci je zamrazaja (frozen_clock)
├── notices.py           # Notice(level, code, text), NoticeSink, kody komunikatow (Z3, ADR-037)
├── cache/metadata.py    # MetadataCache — SQLite WAL, thread-safe; tabele record_cache,
│                        # campaigns_cache, teryt_cache, teryt_bbox_cache, index_area_cache
│                        # (raport dostepnosci; TTL 7 d, DEFAULT_TTL_SECONDS)
│                        # i sheet_cache (30 d, SHEET_TTL_SECONDS); plik bazy
│                        # otwierany leniwie, powstaje przy pierwszym zapisie
├── cache/defaults.py    # open_cache(cache: MetadataCache | bool, force) — wspolny cache
│                        # CLI i biblioteki w <cwd>/.kartograf_cache.db (Z6)
├── download/            # Pobieranie: komenda download (data.py) i tory
│   ├── data.py          # download_data/check_data — komendy `kartograf elevation download` / `imagery download` w bibliotece
│   │                    # (ADR-037): kraj i `auto`, rozwiniecie obszaru PL, wybor toru,
│   │                    # parent_request, DataReport/UnitFile/UnitFailure, Notice
│   ├── options.py       # validate_request / validate_request_bbox (takze bbox CRS),
│   │                    # walidacja wyborow: produkt, kraj, format, rozdzielczosc i uklad
│   │                    # (z rejestru wariantow), system, skala, lata, opcje LAZ;
│   │                    # teksty jak w --help
│   ├── availability.py  # Raport dostepnosci (ADR-041, sekcja 4.9): check_availability,
│   │                    # AvailabilityReport/AvailabilityCombination/AvailabilityArea
│   ├── area.py          # Obszar zadania: bbox_to_2180, obwiednie geometrii,
│   │                    # parent_request_for, przyciecie `auto` (Notice)
│   ├── campaigns.py     # Kampanie GUGiK (ADR-030): CampaignRef, format z rekordu,
│   │                    # verify_file_format, verify_record_url/verify_sheet_extent (B4),
│   │                    # verify_record_vertical_crs (uklad wysokosci rekordu)
│   ├── countries.py     # Podzial obszaru na kraje: countries_for_bbox, split_bbox_by_country
│   ├── links.py         # Dowiazanie sciezki standardowej do wersji (wylacznie hardlink, nigdy wstecz)
│   ├── fetch.py         # Polityka plikow bez kampanii: fetch_version, VersionedFile;
│   │                    # FileSlot.related_roots (D23 miedzy wydaniami, ADR-042 D7)
│   ├── plan.py          # Plan aktualizacji kartograf-plan/1 (PlanItem.track/unit)
│   ├── cutout.py        # Wycinek PL WCS (ADR-035): download_pl_cutout/check_pl_cutout,
│   │                    # maska ladu, sidecar (kroki wewnetrzne prywatne)
│   ├── cz_cutout.py     # Wycinek CZ: download_cz_cutout/check_cz_cutout, write_cz_sidecar
│   ├── cz_sheets.py     # Arkusz CZ TM33/SM5: download_cz_sheet/check_cz_sheet, CzSheetResult
│   ├── laz.py           # Kafle LAZ (ADR-029): download_laz_area/check_laz_area — bbox
│   │                    # w dowolnym CRS, pula watkow, sidecar kafla, porazki w wyniku
│   ├── manager.py       # DownloadManager — arkusze PL (ThreadPoolExecutor), sidecary;
│   │                    # kampanie (year=, all_campaigns=, min_year=, max_year=),
│   │                    # update/plan, check_sheets, DownloadResult (wartosc zwracana)
│   ├── storage.py       # FileStorage — segmenty z szablonow rejestru (ADR-026), versions/;
│   │                    # prune_empty_dirs — sprzatanie pustych bbox/ po porazce;
│   │                    # content_segment (prefiks + tokeny tresci), unit_slot (teryt/bbox/
│   │                    # godlo/country, sloty pokrewne D7 — ADR-042 D8)
│   ├── collections.py   # Kolekcje (ADR-042): download_collection/check_collection =
│   │                    # komendy boundaries/cadastre/models3d download, validate_collection_
│   │                    # request (bez sieci), CollectionReport, zadania jednostek
│   │                    # (package_job/run_job/inspect_job; tor planu collection)
│   ├── updates.py       # Wewnetrzne pozycje planu PL (kartograf-plan/1, ADR-036)
│   └── versions.py      # Magazyn wersjonowany (ADR-036): zapis wylaczny, etykiety,
│                        # lista wersji, sprzatanie .incoming/
├── landcover/manager.py # LandCoverManager — download/check (teryt|sheet|bbox|geometry,
│                        # BDOT10k obszaru = kazdy powiat) -> LandCoverAreaResult (D29-D32);
│                        # archiwum rocznikow BDOT10k (year=) przez zadania jednostek kolekcji
├── landcover/store.py   # hsg_segment, HSG_SEGMENT_PREFIX, selection_unit (spec 3.4)
├── hydrology/hsg.py     # HSGCalculator — calculate_hsg/check_hsg (sheet|bbox|geometry) z wersji
│                        # wejsc SoilGrids (D33, reused), klasyfikacja USDA -> HSG (ADR-025),
│                        # hsg_from_rasters
├── project/             # Manifest projektu (ADR-040):
│   ├── model.py         # Project, ProjectTask, PinnedFile, ProjectReport,
│   │                    # ProjectCheck i wyniki zadan oraz plikow
│   ├── commands.py      # COMMANDS: opcje JSON, walidacja bez sieci, pobranie,
│   │                    # check_* i przypiecia na komende danych (bez logiki per produkt)
│   ├── manifest.py      # kartograf-project/1: walidacja, blokada mkdir, atomowy
│   │                    # zapis i scalanie zmian per zadanie
│   └── operations.py    # Publiczne API: init, add, remove, download,
│                        # check, status, verify i open_project
├── auth/                # proxy.py (subprocess izolujacy credentials CLMS), client.py
│                        # (AuthProxyClient — singleton, sam uruchamia proxy)
└── cli/                 # Tylko tlumaczenie flag i wypisanie wyniku (Z1, ADR-037):
                         # _parser.py (parser glowny), _args.py (wspolne flagi),
                         # groups/ (grupy komend wg typu danych, ADR-039: elevation,
                         # imagery, landcover, soil, boundaries, cadastre, models3d,
                         # project — jeden modul = jedna grupa; groups/_collection.py
                         # to wspolny ksztalt komend kolekcji, nie grupa),
                         # download_cmd.py (download_data/check_data),
                         # availability_cmd.py (check_availability: tabela, --details, --json),
                         # collection_cmd.py (download_collection/check_collection),
                         # landcover_cmd.py, soil_cmd.py (SoilGrids + HSG),
                         # project_cmd.py (API projektu), parse_cmd.py,
                         # cache_cmd.py, commands.py (entry point main)
```

---

## 3. Kontrakty danych

### 3.1 `SourceDescriptor` i szablony `storage_subdir`

`SourceDescriptor` (`kartograf/sources/descriptor.py`) niesie: `key`,
`country`, `product`, `name`, `provider_name`, krotke `channels`
(`AccessChannel`), `tile_scheme`, `storage_subdir`, `default_extension`,
`license`, `resolution`, `auth` i (od 0.8.0, ADR-041) krotke `variants`
(`ProductVariant`, rejestr wariantow — nizej).

Od 0.7.0 (ADR-026) `storage_subdir` jest **szablonem** z placeholderami
`{system}` i `{vcrs}`, a nie literalna nazwa katalogu. Konsument zewnetrzny
czytajacy to pole wprost dostanie szablon — swiadomy trade-off; poprawna droga
to `resolve_subdir()`.

| Klucz deskryptora | `storage_subdir` | `default_extension` |
|---|---|---|
| `pl.gugik.nmt_0_15m`, `pl.gugik.nmt_0_5m`, `pl.gugik.nmt_0_6m`, `pl.gugik.nmt_1m`, `pl.gugik.nmt_5m`, `pl.gugik.nmt_10m` | `nmt/pl_{system}_<etykieta>_{vcrs}`, np. `nmt/pl_{system}_0.5m_{vcrs}` | `.asc` |
| `pl.gugik.nmpt_0_5m`, `pl.gugik.nmpt_0_6m`, `pl.gugik.nmpt` (1 m) | `nmpt/pl_{system}_<etykieta>_{vcrs}`, np. `nmpt/pl_{system}_1m_{vcrs}` | `.asc` |
| archiwa `pl.gugik.<produkt>_<format>[_<etykieta>]`, np. `pl.gugik.nmt_tbd_25m`, `pl.gugik.nmt_ascii_nmt_1m`, `pl.gugik.nmt_tin`, `pl.gugik.nmpt_xyz_0_5m` | `<produkt>/pl_{system}_<format>[_<etykieta>]_{vcrs}`, np. `nmt/pl_{system}_tbd_25m_{vcrs}`, `nmt/pl_{system}_ascii-nmt_1m_{vcrs}`, `nmt/pl_{system}_tin_{vcrs}` | wg formatu: `.zip` (XYZ, ASCII-NMT, TBD, TIN), `.ttn`, `.grd`, `.dxf`, `.dgn` |
| `pl.gugik.orto` | `orto/pl_{system}` (+ `_<wariant>` dla CIR/B-W, regula 5) | `.tif` |
| `pl.gugik.laz` | `laz/pl_{system}_{vcrs}` | `.laz` |
| `cz.cuzk.dmr5g` | `nmt/cz_dmr5g_{vcrs}` | `.tif` |
| `cz.cuzk.dmr4g` | `nmt/cz_dmr4g_{vcrs}` | `.tif` |
| `pl.gugik.bdot10k` | `landcover/pl_bdot10k` (prefiks + tokeny, regula 8) | `.gpkg` |
| `eu.clms.corine` | `landcover/eu_corine` (prefiks + tokeny) | `.tif` |
| `global.isric.soilgrids` | `soil/global_soilgrids` (prefiks + tokeny) | `.tif` |
| `pl.gugik.prg` | `boundaries/pl_prg` (prefiks + tokeny, regula 9) | `.gpkg` |
| `pl.gugik.egib` | `cadastre/pl_egib` (prefiks + tokeny, regula 9) | `.gpkg` |
| `pl.gugik.buildings_3d` | `models3d/pl_buildings` (prefiks + tokeny, regula 9) | `.zip` |

Kanal arkuszy kazdego deskryptora NMT/NMPT PL to `WFS` (`sheet_files`,
sygnal `index`; skorowidz WFS GUGiK, od 0.8.0 zamiast `WMS_SHEET_INDEX`,
ktory zostaje tylko dla orto). Kanal WCS `bbox_raster` dla obu ukladow
pionowych (`EPSG:9650` KRON86, `EPSG:9651` EVRF2007) maja wylacznie
`pl.gugik.nmt_1m` i `pl.gugik.nmpt` (1 m); pozostale rozdzielczosci
i archiwa go nie maja (stad wycinek tylko 1 m, sekcja 4.3).

**Rejestr wariantow (ADR-041, `sources/variants.py`).** Jeden
deskryptor PL na (produkt, format, rozdzielczosc), budowany w
`registry.py::_pl_sheet_source` z listy `_PL_SHEET_SOURCES`; klucz,
szablon segmentu, rozszerzenie i nazwe wyznaczaja format i etykieta.
Istniejace klucze zostaja (`pl.gugik.nmpt` = NMPT 1 m, `pl.gugik.nmt_1m`,
`pl.gugik.nmt_5m`). `SourceDescriptor.variants` ma po jednym
`ProductVariant` na uklad wysokosci: `source` (= klucz deskryptora =
`dataset` sidecara), `product`, `country`, `resolution_m` (`Decimal`;
`None` dla LAZ, TIN i TTN), `vertical_crs` (nazwa CLI: `EVRF2007`/`KRON86`),
`format` (token `FileFormat`: `ASC`, `XYZ`, `ASCII-NMT`, `TBD`, `TIN`,
`TTN`, `GRD`, `DXF`, `DGN`; LAZ: `LAZ`), `systems` (`("1992", "2000")`
— to, w jakim ukladzie arkusz istnieje, jest faktem skorowidza, nie
rejestru), `channel` i `index_ref` (`IndexRef(endpoint, layer_prefix)`:
usluga WFS skorowidza i prefiks typow rocznych, np.
`.../NumerycznyModelTerenuEVRF2007/WFS/Skorowidze` + `SkorowidzNMT`;
NMPT: `NumerycznyModelPokryciaTerenu{EVRF2007,KRON86}` + `SkorowidzNMPT`;
LAZ: `DanePomiaroweLidar{EVRF2007,KRON86}` +
`SkorowidzDanychPomiarowychLIDAR`). Wlasciwosci: `label` (etykieta K2)
i `source_file` (archiwum = plik zrodlowy bez konwersji, wycinka
i mozaiki). `FORMATS` (`FileFormat`: token, nazwa pola `format`
w skorowidzu, rozszerzenie, akceptowane koncowki sciezki URL, opis,
`source_file`) opisuje formaty skorowidza; rozszerzenie wynika z pola
`format` rekordu, nigdy z URL.

Funkcje (bez IO): `variants(*, product, country, vertical_crs,
resolution, system, format)` — warianty w kolejnosci rejestru;
`resolution_label(Decimal)` -> `0.15m`/`0.5m`/`10m` (`format(value.normalize(),
"f") + "m"`) i odwrotne `parse_resolution(label)` (tylko dokladna
etykieta; `0,5m`, `50cm`, `0.50m` = `None`); `source_format(format, url)`
— token, gdy pole `format` rekordu i koncowka URL wskazuja ten sam
format, inaczej `None` (twardy filtr, sekcja 4.1); `variant_error`/
`find_variant` — tekst bledu wyboru (lista etykiet per uklad wysokosci)
i jedyny wariant wyboru (`resolution=None` wybiera jedyna etykiete:
`GRD` 5m, TIN/TTN bez rozdzielczosci); `labels_by_vertical_crs`,
`format_tokens`. Rejestr czytaja: walidacja CLI/API
(`download/options.py`), teksty `--help` i `list-sources`,
`download/area.py::pl_only_flags`, `FileStorage` (deskryptor wariantu),
wycinek (`download/cutout.py::wcs_variant` — wariant z kanalem WCS),
providery PL (wariant, uslugi skorowidza) i raport dostepnosci
(4.9). Zaden inny modul nie trzyma listy rozdzielczosci, ukladow
wysokosci ani formatow. Pozostale deskryptory (orto, CZ, land cover)
maja pusta krotke `variants`.

`storage_subdir` jest zawsze napisem (od 0.8.0). Zrodla land cover i kolekcji
maja prefiks bez placeholderow, ktory `download/storage.py::content_segment`
uzupelnia tokenami tresci (sekcja 3.3 reguly 8 i 9, sekcje 4.8 i 4.10).
CORINE ma dwa kanaly: `CLMS_API` (dane, sygnal `metadata`) i `WMS`
(podglad PNG, `none`, `EPSG:3857`).

**Parametry kanalow kolekcji (ADR-042 D1).** `AccessChannel.params`
(domyslnie `None` = kanal obslugiwany przez providera) niesie typowana,
niemutowalna konfiguracje silnika - dane bez IO:

| Typ | Pola | Silnik |
|---|---|---|
| `UnitPackageParams` | `unit` (`powiat`/`woj`/`country`), `variants` (`PackageVariant`), `unpack` (sufiks JEDNEGO czlonu zapisywanego zamiast ZIP; `None` = ZIP 1:1) | `transport/unit_package.py` |
| `PackageVariant` | `choice` (opcje API/CLI wybierajace wariant, np. `(("format", "SHP"), ("year", "2024"))`; `()` = jedyny wariant), `url_template` (tokeny wylacznie `{teryt}`, `{woj}` = 2 pierwsze cyfry TERYT), `edition` (etykieta wersji), `segment_tokens`, `members` (wymagane sufiksy czlonow ZIP), `vertical_crs` (uklad wysokosci zadeklarowany w danych 3D) | jw. |
| `FeatureBBoxParams` | `protocol` (`wfs`/`arcgis`, zgodny z `transport` kanalu `WFS`/`ARCGIS_QUERY`), `native_crs`, `axis_order` (`yx` = northing pierwszy w BBOX), `page_size`, `layers` (`FeatureLayer`), `selection` (`level` = jedna warstwa wg `--level`, `all` = kazda), `order_field` (ArcGIS `orderByFields`), `drop_fields` | `transport/feature_bbox.py` + `transform/gpkg.py` |
| `FeatureLayer` | `code` (wartosc `--level` albo staly kod), `source` (typ WFS `ms:A03_Granice_gmin` albo id warstwy ArcGIS), `name` (warstwa GPKG), `id_field` (staly identyfikator obiektu: dedupe i kolejnosc) | jw. |

Testy rejestru (`tests/test_sources_registry.py`) pilnuja: tokenow szablonu,
tych samych kluczy `choice` w wariantach kanalu, `edition`/`segment_tokens`
w `[a-z0-9.-]+`, protokolu zgodnego z transportem, `page_size > 0`
i capability kanalu kolekcji unikalnej w deskryptorze (`archive_unit_files`,
`country_files`, `bbox_vector`, `admin_unit_files`) - po niej
`build_metadata(capability=)` wybiera kanal sidecara. Kanaly kolekcji PL:

| Deskryptor (`--product`) | Kanal, capability | Parametry |
|---|---|---|
| `pl.gugik.bdot10k` (`landcover --source bdot10k --year`) | `DIRECT_FILES`, `archive_unit_files` | powiat; 24 warianty `(format, year)`: 2014-2025 x `GML` (czlon `.xml`) / `SHP` (`.shp`), `.../Archiwum/bdot10k/<R>/<F>/{woj}/{teryt}_<F>_<R>.zip`, `edition` = rok |
| `pl.gugik.prg` (`admin`) | `WFS` `AdministrativeBoundaries`, `bbox_vector` | `wfs`, EPSG:2180, `yx`, strona 1000, `selection="level"`: `wojewodztwo`=A01, `powiat`=A02, `gmina`=A03, `jednostka-ewidencyjna`=A05, `obreb`=A06, id `IIP_IDENTY` |
| jw. | `DIRECT_FILES`, `admin_unit_files` | woj.; `prg/granice/{woj}_GraniceAdministracyjne.zip`, czlon `.gml`, token `gml` |
| jw. | `DIRECT_FILES`, `country_files` | kraj; `prg/granice/00_jednostki_administracyjne.zip` (ok. 377 MB), czlon `.shp`, token `shp` |
| `pl.gugik.egib` (`map`) | `DIRECT_FILES`, `admin_unit_files` | powiat; `InneDane/latest_exports/eziudp_wfs/GPKG/{teryt}.gpkg.zip`, `unpack=".gpkg"`, token `gpkg` |
| jw. | `WFS` `UslugaZbiorcza`, `bbox_vector` | `wfs`, EPSG:2180, `yx`, strona 1000, `selection="all"`: `dzialki`, `budynki`, id `gml_id`, `drop_fields=("DATA",)` |
| `pl.gugik.buildings_3d` (`buildings`) | `DIRECT_FILES`, `admin_unit_files` | powiat; warianty `(lod, year)`: LoD1 2019 (`.../LOD1/2019/{woj}/{teryt}_gml.zip`, EPSG:9650), LoD1 2021/2022/2024 (`.../LOD1/<R>/{woj}/{teryt}.zip`, EPSG:9651), LoD2 2017 (`.../LOD2/{teryt}_gml.zip`, EPSG:9650); czlon `.gml`, `edition` = rok |

Kazdy z tych kanalow ma sygnal `none` (GUGiK nie podaje `ETag` ani
`Last-Modified`; wynik WFS to migawka).

**`SourceDescriptor.resolve_subdir(*, system=None, vertical_crs=None) -> str`**
wypelnia szablon przez `str.replace`, a nie `str.format` — czesciowe
wypelnienie jest legalne. `vertical_crs` jest normalizowany do lowercase
(`"Bpv"` -> `"bpv"`). Podanie wymiaru, ktorego szablon nie ma, to no-op
(orto ignoruje `vertical_crs`).
Pusty string (albo sam whitespace) w `system`/`vertical_crs` to
`ValidationError` — `None` znaczy "wypelnij pozniej", a pusty napis dawal
cichy segment `nmt/pl_1992_1m_` (review max zn. 7).

Kto wypelnia ktory placeholder:

| Placeholder | Kto wypelnia | Kiedy |
|---|---|---|
| `{vcrs}` | konstruktor `FileStorage(vertical_crs=)` albo jawne `resolve_subdir(vertical_crs=)` | raz, na starcie zadania — uklad pionowy jest wlasnoscia zadania, nie arkusza |
| `{system}` | `FileStorage` per identyfikator (`get_path`/`get_raw_path`/`exists`/`delete`/`ensure_directory`), regula ta sama co `parser_registry.path_parts`: kropki -> `2000`, reszta -> `1992` | przy budowie kazdej sciezki |
| `{system}` (jawnie) | tor LAZ: `LazTile.system` (`uklad_xy` kafla przez `parse_pl_system`; nieznany = kafel pominiety / `ValidationError`) przez `FileStorage.get_raw_path(..., system=)` — jedno zrodlo prawdy dla CLI i biblioteki (zn. 8, review max); wycinek PL WCS (`download_pl_cutout`: `system="1992"` na stale — `--target-crs` z `--system 2000` jest odrzucane, sekcja 4.3); przestarzaly tor arkuszowy odrzuca arkusz we wspolrzednych PL-2000 | przed utworzeniem `FileStorage` / sciezki wycinka |

`FileStorage` waliduje wynik koncowy: segment, w ktorym po wypelnieniu zostala
klamra `{`, konczy sie `ValidationError` z nazwa brakujacego wymiaru
(`_ensure_resolved`). Cichy katalog `pl_{system}_1m_evrf2007` nigdy nie powstanie.

### 3.2 Schema sidecara `kartograf-meta/1`

Kazde udane pobranie przez CLI albo warstwe zarzadzajaca biblioteki
(`download_data`, `DownloadManager`, `LandCoverManager`, `download_pl_cutout`,
`download_laz_area`, `download_cz_cutout`, `download_cz_sheet`,
`download_collection`, `HSGCalculator`) zapisuje dane i `<plik>.meta.json`: sidecar wersji w
magazynie jest obowiazkowy, sidecar sciezki standardowej best-effort
(sekcja 1). Poza magazynem `hsg_from_rasters` pisze sidecar best-effort.
Bezposrednie wywolanie providera sidecara nie pisze (np.
`CuzkDmrProvider.download`); sidecar godla CZ pisze `download/cz_sheets.py`.

| Pole | Znaczenie |
|---|---|
| `dataset` | klucz deskryptora zrodla (np. `pl.gugik.nmt_1m`) |
| `country`, `product`, `provider` | kraj, produkt i nazwa dostawcy z deskryptora |
| `horizontal_crs` | faktyczny uklad poziomy pliku: arkusz PL-1992 `EPSG:2180`, arkusz PL-2000 `EPSG:2176`–`EPSG:2179` wedlug strefy godla, CZ natywnie `EPSG:5514`, kafel TM33 `EPSG:3045`; wycinek po `--target-crs` w ukladzie docelowym. Dla arkusza PL uklad z godla jest SPRAWDZANY wspolrzednymi pliku (`sources/sidecar.py::pl_sheet_horizontal_crs`): plik opublikowany przez GUGiK w innym ukladzie niz wskazuje godlo (E17, np. arkusze PL-2000 strefy 7 jak `7.125.11.19` w EPSG:2180) dostaje uklad PLIKU, deklaracja rekordu skorowidza zostaje w `extra.source.declared_crs`, logger `kartograf.sources.sidecar` ostrzega, a CLI drukuje `Warning: N arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: ...` (kod bez zmian; segment katalogu nadal wg godla, ADR-026) |
| `vertical_crs` | kod realizacji ukladu pionowego: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007); `null` gdy produkt nie ma pionu (orto) |
| `vertical_source` | `native` / `ellipsoidal` / `server` (z `AccessChannel`) |
| `resolution` | rozdzielczosc z deskryptora: etykieta K2 rejestru (`0.15m`, `0.5m`, `1m`, `10m`, archiwa do `50m`; CZ `2m`/`5m`) albo `null` (orto, LAZ, archiwa TIN/TTN) |
| `nodata` | wartosc pustego piksela: dla `.asc` czytana automatycznie z naglowka (`read_asc_nodata`), w torze CZ z tagu GeoTIFF (`download/cz_cutout.py::read_tif_nodata`; w trybie bbox z fallbackiem `CUZK_NODATA`), dla wycinka PL stala `-9999.0`, dla wyniku HSG `0`, dla GeoTIFF CORINE/SoilGrids z `LandCoverManager` z tagu pliku (sekcja 4.8); `null` gdy zadna z tych drog nie ma zastosowania (np. orto) |
| `request` | zadanie, ktore dalo TEN plik: `sheet` (godlo), `bbox` + `bbox_crs` w ukladzie wyniku albo `teryt`; dla kampanii PL `campaigns` (rozwiazane `newest`/`all`, zawsze), `min_year`/`max_year` (gdy podane) i `year` (gdy granice rowne); LAZ: `year`/`min_year`/`max_year`/`min_density` gdy podane, `campaigns` tylko dla `all`; land cover: parametry tresci z domyslnymi wartosciami — SoilGrids `property`/`depth`/`stat`, CORINE `year`, BDOT10k `format` (4.8). `request` opisuje pierwotne POBRANIE pliku, nie ostatnie wykorzystanie; `extra.parent_request(s)` nie niesie flag roku (3.4) |
| `license` | `{id, attribution, url}` z deskryptora |
| `downloaded_at`, `kartograf_version` | znacznik czasu UTC (ISO 8601, od 0.8.0 z mikrosekundami — porzadek dwoch pobran w jednej sekundzie) i wersja pakietu z `kartograf/_version.py::build_version()`: wydanie = samo `__version__`; wersja rozwojowa (`dev`) = `<__version__>+<krotki SHA>` commita, z ktorego zaimportowano pakiet, z sufiksem `.dirty`, gdy sledzone pliki katalogu `kartograf/` maja niezacommitowane zmiany (docs/testy sie nie licza); gdy git jest niedostepny albo pakiet nie pochodzi z repozytorium, w ktorym lezy (`os.path.samefile`), samo `__version__`. Ta sama wartosc w `kartograf --version`; `User-Agent` HTTP niesie samo `__version__` |
| `transform` | slownik osi (`horizontal`/`vertical`) z opisem uzytej operacji w formacie `pinned: <opis> (<dokladnosc> m)`; os bez przeliczenia nie ma klucza, a bez zadnego przeliczenia cale pole to `null` |
| `extra` | `parent_request` (obszar; zadanie, ktore utworzylo plik — `parent_requests` usuniete w 0.8.0); LAZ `tile_sheet`/`year`/`nominal_density`/`url`, dodatkowo `acquisition_date`/`full_sheet`, gdy znane; arkusze NMT/NMPT/orto PL `source`, `campaign`, `version` (`label`, `label_source`; ADR-036), `coverage` (lot niepelny, przy zapisie wersji) oraz pola rocznikow/lotow opisane nizej; LAZ, arkusze i wycinki CZ, wycinek PL: `version` (ADR-036, plan 2/3); SM5 `mapname`/`cz_share`, `http` (`etag`, `last_modified`, `content_length` odpowiedzi `openzu`; sygnal swiezosci) i `all_nodata`; wycinek bbox CZ `all_nodata` i `parent_request`; wycinek PL WCS `source`, `mask`, `zero_pixels` (tylko gdy > 0), `all_nodata`, `parent_request` (sekcja 3.2); CORINE WMS `fallback`/`note`; HSG `derived` i parametry obliczen |
| `sha256`, `size_bytes` | od 0.7.1: skrot SHA-256 (hex) i rozmiar w bajtach pliku danych, liczone w `build_metadata` (`sources/sidecar.py::file_digest`) z GOTOWEGO pliku — jedno miejsce dla wszystkich produktow, takze pochodnych (wycinek, scalony GPKG BDOT10k, HSG); `null`, gdy sidecar powstaje bez istniejacego pliku danych. Wersja w magazynie (ADR-036) podaje skrot z jedynego odczytu przy zapisie (`build_metadata(digest=)`, D20) — to tozsamosc wersji (`_<sha8>` w nazwie katalogu). Sidecar sciezki standardowej (kopia sidecara wersji) niesie skrot wersji |
| `schema` | stale `kartograf-meta/1` |

Nazwy kluczy sa angielskie (ADR-031, od 0.7.0); wyjatkiem jest `teryt` —
nazwa wlasna rejestru. Wartosci (godla, nazwy warstw, daty, komunikaty)
zostaja w postaci zrodlowej. Sidecary zapisane przed ADR-031 (polskie
klucze, np. `request.godlo`, `extra.source.aktualnosc`) nie sa
migrowane: kod czytajacy sidecary traktuje brak nowego klucza jak brak
informacji (sekcja "Stare sidecary" nizej).

`extra.source` — pochodzenie arkusza PL z rekordu skorowidza GUGiK
(`SkorowidzRecord.to_source`; ten sam slownik trafia do `record_cache`
i `campaigns_cache`). Rekordy NMT/NMPT pochodza od 0.8.0 ze skorowidza
WFS: `parse_index_feature` (`providers/pl/skorowidz_wfs.py`) mapuje pola
WFS (`url_do_pobrania`, `godlo`, `akt_data`, `akt_rok`, `dt_pzgik`,
`uklad_xy`, `uklad_h`, `char_przestrz`, `czy_ark_wypelniony`,
`nr_zglosz`, `zrodlo_danych`, `format`, `blad_sr_wys`, `blad_sr_syt`,
`modul_archiwizacji`) na te same klucze surowego rekordu co dawny
GetFeatureInfo, wiec kolumna nizej podaje nazwy pol rekordu WMS:

| Klucz | Zawartosc (pole rekordu GUGiK) |
|---|---|
| `url` | URL pliku OpenData (`url`) |
| `index_url` | adres uslugi skorowidza, z ktorej pochodzi rekord: NMT/NMPT (od 0.8.0) — usluga WFS wariantu (`IndexRef.endpoint`, np. `https://mapy.geoportal.gov.pl/wss/service/PZGIK/NumerycznyModelTerenuEVRF2007/WFS/Skorowidze`); orto (i sidecary NMT/NMPT sprzed 0.8.0) — endpoint WMS |
| `layer` | NMT/NMPT: typ obiektu WFS bez prefiksu przestrzeni nazw (np. `SkorowidzNMT2025`); orto: warstwa WMS skorowidza |
| `sheet` | godlo arkusza po normalizacji (`godlo`) |
| `acquisition_date` | data aktualnosci danych `RRRR-MM-DD` (`aktualnosc`) |
| `acquisition_year` | rok aktualnosci (`aktualnoscRok`, inaczej z `aktualnosc`) |
| `pzgik_date` | data przyjecia do PZGiK (`dt_pzgik`) albo `null` |
| `resolution_m` | rozdzielczosc w metrach (`charakterystykaPrzestrzenna`/`wielkoscPiksela`; WFS: `char_przestrz`) |
| `declared_crs` | uklad zadeklarowany w rekordzie, np. `PL-2000:S7` (`ukladWspolrzednychPoziomych`) — moze sie roznic od `horizontal_crs` pliku (E17) |
| `full_sheet` | `true`/`false` = pelny/niepelny arkusz (`calyArkuszWypelnionyTrescia`), `null` gdy brak |
| `survey_work_id` | numer zgloszenia pracy geodezyjnej (`numerZgloszeniaPracy`) |
| `data_source` | zrodlo danych (`zrDanych`/`zrodloDanych`) |
| `format` | format pliku z rekordu (`format`), np. `ARC/INFO ASCII GRID`, `ASCII TBD` |
| `height_rmse_m` | od 0.7.1: blad sredni wysokosci w metrach (`bladSredniWysokosci`); `null`, gdy brak albo wartosc nieliczbowa |
| `position_rmse_m` | od 0.7.1: blad sredni polozenia w metrach (`bladSredniPolozenia`); `null` jak wyzej |
| `archive_module` | od 0.7.1: modul archiwizacji, np. `1:5000` (`modulArchiwizacji`), albo `null` |
| `declared_vertical_crs` | od 0.7.1: uklad wysokosci zadeklarowany w rekordzie, np. `PL-EVRF2007-NH` (`ukladWspolrzednychPionowych`), albo `null` |
| `color` | tylko orto: wariant `RGB`/`CIR`/`B/W` |

**Stare sidecary i wpisy cache (sprzed ADR-031).** Wpis `record_cache`/
`campaigns_cache` bez nowych kluczy jest chybieniem cache (skorowidz
odpytywany ponownie, wpis nadpisany); od 0.7.1 dotyczy to takze wpisow
bez klucza `archive_module` (zapisanych przed dodaniem kluczy dokladnosci).
Sidecar kampanii bez `extra.campaign.pzgik_date` nie daje klucza
dowiazania z sidecara — uzywane jest dolne oszacowanie z nazwy katalogu
kampanii (jak przy braku sidecara). Ostrzezenie E17 nie powstaje dla
sidecara bez `request.sheet`. Odswiezenie arkusza: `--force`.

Kanal, z ktorego brany jest `horizontal_crs`/`vertical_crs_options`/
`vertical_source`, wybiera `build_metadata`: albo jawnie po `capability=`,
albo domyslnie po ksztalcie zadania (`bbox` w `request` -> kanal z
`bbox_raster`/`bbox_vector`, inaczej pierwszy pasujacy). Nazwa rodziny ukladu
pionowego jest mapowana na realizacje krajowa, jesli kanal deklaruje wlasnie
ja (`resolve_vertical_crs`: `EPSG:5621` -> `EPSG:9651` dla PL).

**Wycinek PL WCS (`--cutout`) w sidecarze.** Biblioteka
(`download/cutout.py::write_pl_wcs_cutout_sidecar`) buduje rekord z
`capability="bbox_raster"` deskryptora NMT 1 m albo NMPT, `nodata=-9999`,
`horizontal_crs` w ukladzie docelowym i `request` =
`{"bbox": <bbox_target>, "bbox_crs": <uklad docelowy>}` (bbox po przeliczeniu
do ukladu wyniku). Dla EPSG:2180 `transform=null`; dla EPSG:5514/3045
`transform.horizontal` opisuje przypieta operacje lokalnego warpu.
`extra.source` zawiera `service="WCS"`, `endpoint`, `coverage`,
`format`, `composition="server"`: kompozycja serwera NIE jest
wyborem najnowszego arkusza wedlug ADR-028. `extra.mask` zawiera
`source="PRG"`, liste `layers` z trzema wpisami
`A00_Granice_panstwa`, `-W02_Morze_terytorialne_RP`,
`-W03_Morskie_wody_wewnetrzne` oraz `masked_pixels`;
`PlCutoutResult.masked_pixels` jest liczone
na siatce pobrania EPSG:2180, przed ewentualnym warpem. `extra.zero_pixels`
jest zapisywane tylko gdy liczba zerowych pikseli na ladzie > 0 (zera zostaja
danymi); `extra.all_nodata` i `PlCutoutResult.all_nodata` sa prawdziwe, gdy
caly wynik jest nodata. `extra.parent_request` powstaje tylko po przekazaniu
`parent_request=` (w CLI: oryginalne zadanie, sekcja 3.4).

**Kolekcje (ADR-042) w sidecarze.** `download/collections.py::run_job`
wybiera kanal po jego capability (unikalnej w deskryptorze) i zapisuje:
`request` = wybor uzytkownika w tej jednostce (`teryt` albo `bbox` +
`bbox_crs` w ukladzie natywnym uslugi; `year`, `format`, `lod`, `level`
tylko gdy podane - jedyne wydanie LoD2 bez `year`), `horizontal_crs` =
uklad pliku (wynik obszaru: `native_crs` kanalu), `vertical_crs` =
`PackageVariant.vertical_crs` (modele 3D; 2D = `null`), `extra.source`:
paczka `{url, edition?, member?}` (`member` = rozpakowany czlon, EGiB),
wynik obszaru `{service, protocol, layers: [{code, source, name,
features}], dropped_fields?}` (`dropped_fields` = pole -> posortowane
unikalne wartosci pol `drop_fields` usunietych z GPKG, EGiB `{"DATA": [...]}`);
paczka ma tez `extra.http` (naglowki odpowiedzi, bez sygnalu), a obszar
rozlozony na powiaty albo przeliczony z arkusza/geometrii/innego ukladu -
`extra.parent_request` (sekcja 3.4). Etykieta wersji: `edition` wariantu
(`label_source="edition"`: rocznik BDOT10k, rok modeli 3D), inaczej data
pobrania.

**Magazyn wersjonowany (ADR-036).** Sidecar WERSJI (`versions/.../<etykieta>_<sha8>/<plik>.meta.json`)
jest OBOWIAZKOWY i niezmienny we wszystkich torach (arkusze PL i CZ,
wycinki PL i CZ, LAZ, land cover, HSG): `emit_sidecar(..., exclusive=True)`
pisze go raz (tmp + `fsync` + `os.link`, nigdy nie nadpisuje); porazka
zapisu rzuca `DownloadError` (zapis usuwa utworzony plik danych, wersji
nie ma). Sidecar poza magazynem zostaje best-effort.
Sidecar sciezki standardowej (dowiazania) to ZWYKLY plik — kopia sidecara
wersji z dopisanym `extra.link` (`hardlink`) i `extra.link_target`
(zapis `tmp` + `os.replace`, nigdy "przez" symlink sidecara pozostawiony
przez uzytkownika; best-effort). To JEDYNE zrodlo celu dowiazania
(hardlink nie niesie wskazania): brak sidecara standardowego albo
`extra.link = "copy"` z 0.7.x = sciezka nieznana.

**Przedzial lat i pokrycie (ADR-032, ADR-036 D13).** Przy zadaniu z granica
roku sidecar kazdej wersji NMT/NMPT/orto i jego kopia w sciezce
standardowej zawieraja `extra.available_years` (posortowane wszystkie lata
arkusza z pelnego skorowidza); bez granic brak pola. `extra.coverage` (0..1,
cztery miejsca po przecinku) ma sidecar wersji KAZDEGO lotu rastrowego
(`.asc`/`.tif`; archiwa ADR-041 bez pomiaru) bez
`full_sheet=true` — liczone z tego samego odczytu co sha256 przy zapisie
(ASC bez `NODATA_value` = -9999, orto wg nodata/alfa; blad pomiaru = brak
pola + ostrzezenie), nigdy dopisywane pozniej. Przy przedziale i `all`
pole + ostrzezenie), nigdy dopisywane pozniej. Przy przedziale i `all`
sidecar standardowy dostaje `extra.flights` (malejaco wg ADR-028; `id`,
`date`, `full_sheet`); gdy ma > 1 lot i dowiazany lot nie ma
`full_sheet=true`, dopisuje tez `coverage` z sidecarow wersji i porownuje
pokrycie. Przy starszym locie o WIEKSZYM pokryciu `extra.better_coverage` =
jego `id` (lot zadeklarowany jako pelny liczy sie jako pokryty w pelni) i
CLI `Info:` na stderr (takze z `-q`). Pole `better_coverage` jest usuwane,
gdy ponowne zadanie nie wykaze lepszego lotu. Pokrycie NIE przestawia
dowiazania (najpierw najnowszy lot wg ADR-028, zasada "nigdy wstecz").
dodatkowo `extra.acquisition_date` (`akt_data`) i `extra.full_sheet`
(`czy_ark_wypelniony`), gdy znane.

### 3.3 Kanoniczny uklad `data/`

```
data/
├── nmt/
│   ├── pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # DOWIAZANIE (regula 6)
│   ├── pl_1992_1m_evrf2007/full_sheet/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # DOWIAZANIE do najnowszego pelnego lotu (regula 7)
│   ├── pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_3fa91c2e/N-34-130-D-d-2-4.asc   # wersja (prawdziwy plik)
│   ├── pl_1992_1m_evrf2007/versions/.incoming/<host>_<pid>_<token>/   # zapis w toku (sprzatany po 24 h)
│   ├── pl_1992_1m_kron86/...
│   ├── pl_1992_5m_evrf2007/...              # 5m, 0.15m, 0.6m, 10m tylko EVRF2007 (rejestr wariantow, 3.1)
│   ├── pl_1992_0.5m_evrf2007/...            # etykieta K2 w segmencie (0.15m, 0.5m, 0.6m, 1m, 5m, 10m)
│   ├── pl_1992_tbd_25m_kron86/<hier>/<godlo>.zip   # archiwum GUGiK: plik zrodlowy 1:1 (ADR-041), arkusze roznych skal
│   ├── pl_1992_1m_evrf2007/bbox/<coords>.tif         # DOWIAZANIE: wycinek PL WCS (4.3)
│   ├── pl_1992_1m_evrf2007/versions/bbox/2026-10-12_<sha8>/<coords>.tif   # wersja wycinka
│   ├── pl_2000_1m_evrf2007/6/179/12/20/6.179.12.20.asc
│   ├── cz_dmr5g_bpv/302/5550/302_5550.tif   # DOWIAZANIE (wersja w versions/302/5550/)
│   ├── cz_dmr5g_bpv/bbox/<coords>.tif       # DOWIAZANIE: wycinki bbox CZ (wersje w versions/bbox/)
│   ├── cz_dmr5g_evrf2007/...
│   └── cz_dmr4g_bpv/CTES/96/CTES96.tif      # DOWIAZANIE; sidecar wersji z extra.http (ETag)
├── nmpt/
│   ├── pl_1992_1m_evrf2007/...              # (+ _kron86, + pl_2000_..., + 0.5m, 0.6m, xyz_0.5m/xyz_1m KRON86)
│   └── pl_1992_1m_evrf2007/bbox/<coords>.tif # DOWIAZANIE: wycinek NMPT WCS
├── orto/pl_1992/...                         # bez ukladu pionowego
├── orto/pl_1992_cir/...                     # wariant CIR (B/W: pl_<uklad>_bw), E12
├── laz/pl_2000_evrf2007/<hier>/<plik>.laz   # DOWIAZANIE; uklad poziomy per kafel (uklad_xy), pionowy z flagi
├── laz/pl_2000_evrf2007/versions/<hier>/<data>_<zgloszenie>_<sha8>/<plik>.laz   # wersja (D26)
├── landcover/
│   ├── pl_bdot10k_gpkg/teryt/1465.gpkg          # DOWIAZANIE; wersje w versions/teryt/<data>_<sha8>/
│   ├── pl_bdot10k_gpkg_ptwp-swrs/teryt/1465.gpkg # filtr warstw (kody posortowane, lowercase)
│   ├── pl_bdot10k_gpkg_zip/teryt/1465.zip      # keep_raw: oryginalny ZIP paczki
│   ├── pl_bdot10k_shp/teryt/1465.zip           # paczka SHP
│   ├── pl_bdot10k_shp_2024/teryt/1261.zip      # archiwum rocznikow (regula 9); wersje 2024_<sha8>
│   ├── pl_bdot10k_shp_2023/versions/teryt/2023_<sha8>/1261.zip   # rocznik identyczny z 2022: hardlink (D7)
│   ├── eu_corine_2018/N-34/130/D/N-34-130-D.tif  # CLMS; wersje <wydanie>_<sha8> (np. V2020_20u1_...)
│   └── eu_corine_2018_preview/bbox/<coords>.png  # podglad WMS bez credentials (D31)
├── boundaries/
│   ├── pl_prg_gmina/bbox/<coords>.gpkg         # obiekty obszaru (WFS), EPSG:2180; wersje <data>_<sha8>
│   ├── pl_prg_gml/teryt/12.zip                 # paczka wojewodztwa 1:1
│   └── pl_prg_shp/country/pl.zip               # plik krajowy (--whole-country)
├── cadastre/
│   ├── pl_egib/bbox/<coords>.gpkg              # dzialki i budynki obszaru (WFS), bez tokenu
│   └── pl_egib_gpkg/teryt/1261.gpkg            # eksport powiatu (GPKG rozpakowany z ZIP)
├── models3d/pl_buildings_lod1_2024/teryt/1261.zip   # CityGML 1:1; wersje 2024_<sha8> (rok wydania)
├── soil/global_soilgrids_clay_0-5cm_mean/bbox/<coords>.tif   # wersje 2.0_<sha8> (wydanie)
└── hsg/global_soilgrids_0-5cm_mean/bbox/<coords>.tif         # pochodna z wersji clay/sand/silt (D33)
```

**Reguly segmentow:**

1. Segment ma postac `<kraj>_<uklad>[_<wariant>][_<vcrs>]`, wszystkie wartosci
   lowercase. Uklad PL: `1992` / `2000`. Uklad pionowy: `kron86` /
   `evrf2007` / `bpv`. CZ nie niesie ukladu poziomego, bo nazwa datasetu
   (`dmr5g`/`dmr4g`) wyznacza go 1:1 (natywnie zawsze EPSG:5514).
   Czlon NMT/NMPT PL miedzy ukladem a `<vcrs>` pochodzi z szablonu
   deskryptora (`registry.py::_pl_sheet_source`, sekcja 3.1; to nie
   `<wariant>` z reguly 5): siatka ASC — sama etykieta
   (`pl_1992_0.5m_evrf2007`), archiwum — token formatu przed etykieta
   (`pl_1992_tbd_25m_kron86`, `pl_1992_ascii-nmt_1m_evrf2007`), format
   bez rozdzielczosci — sam token (`pl_1992_tin_kron86`).
2. Hierarchia wewnatrz segmentu jest bez zmian — `parser_registry.path_parts`:
   PL-1992 `N-34-130-D-d-2-4` -> `N-34/130/D/d/2/4`, PL-2000 `6.179.12.20` ->
   `6/179/12/20`, TM33 `302_5550` -> `302/5550`, SM5 `CTES96` -> `CTES/96`.
3. Podkatalog `bbox/` wewnatrz segmentu trzyma dowiazania wycinkow PL WCS
   (`--cutout`) i CZ: `<coords>.tif` bez daty (D15); wersje w
   `<segment>/versions/bbox/<RRRR-MM-DD>_<sha8>/<coords>.tif`.
   Wspolrzedne sa w ukladzie WYNIKU (`--horizontal-crs`), formatowane
   `%.10g` i sklejane `_`. Nazwa niesie ZADANIE, nie dokladny zasieg
   rastra: wycinek PL w EPSG:2180 siega do < 1 px dalej po wyrownaniu
   na zewnatrz do siatki 1 m, a siatka warpa (`warp_to_grid` z
   `transform/raster.py`, wspolna dla PL i CZ) ma calkowita liczbe
   pikseli od NW, wiec E/S moze odbiegac o do 0,5 px (sekcja 4.3). PL bez
   `--cutout` zapisuje arkusze w hierarchii godel (sekcja 4.2).
4. Rozdzielczosc wchodzi do segmentu tylko tam, gdzie jest parametrem API
   (NMT/NMPT): etykieta K2 z rejestru (`0.15m`, `0.5m`, `0.6m`, `1m`, `5m`,
   `10m`; archiwa takze `15m`..`50m`), ta sama co `--resolution`
   i `resolution` sidecara. Nie ma jej dla CZ (`dmr5g` to z definicji 2 m,
   `dmr4g` 5 m) ani dla orto/LAZ (brak takiego parametru).
5. `<wariant>` rozroznia pliki tego samego godla i ukladu, ktore nie sa tym
   samym produktem (E12, 2026-10-06). Wariant deklaruje tylko orto
   (`storage_variant`; w `BaseProvider` domyslnie `None`): RGB
   bez sufiksu w `orto/pl_<uklad>/` (bez migracji), CIR w
   `orto/pl_<uklad>_cir/`, B/W w `orto/pl_<uklad>_bw/`. Wariant pochodzi
   z `provider.storage_variant` (`GugikOrtoProvider(color=...)`) i trafia do
   `FileStorage(variant=...)`; bez niego skip zwracal po cichu plik RGB na
   zadanie CIR.

6. **Wersje (ADR-036; dawniej `kampanie/`, ADR-030).** Prawdziwe pliki
   NMT/NMPT/orto PL leza WYLACZNIE w `<segment>/versions/<hierarchia
   godla>/<etykieta>_<sha8>/<godlo>.<ext>` (+ `.meta.json` wersji);
   sciezka standardowa `<segment>/<hierarchia>/<godlo>.<ext>` jest
   hardlinkiem do najnowszej LOKALNEJ wersji zadania. Etykieta kampanii =
   `<data>_<id>`: `<data>` = `aktualnosc` rekordu (RRRR-MM-DD), `<id>` =
   pierwszy segment liczbowy nazwy pliku w URL (`83233_1744736_<godlo>.asc`
   -> `83233`), inaczej `u` + 8 znakow hex `sha1(URL)`; providery bez
   kampanii: data pobrania UTC. `<sha8>` = poczatek sha256 tresci.
   Zapis (`download/versions.py::commit_version`): katalog roboczy
   `versions/.incoming/<host>_<pid>_<token>/` w tym samym systemie
   plikow, `fsync`, wylaczny `os.link` (nigdy nie nadpisuje; istniejacy
   plik o innym sha256 = `DownloadError`), sidecar wersji pisany wylacznie;
   ta sama tresc = `unchanged`, ta sama tresc z nowa etykieta kampanii =
   `relabeled` (nowy katalog z hardlinkiem). Wersja bez sidecara jest
   niewazna (naprawia ja nastepny zapis tej samej tresci po sprawdzeniu
   sha256); pozostalosci starsze niz 24 h sa usuwane. Dowiazanie: wylacznie
   hardlink (brak obslugi = `DownloadError`, nigdy kopia ani symlink),
   podmiana atomowa (plik tymczasowy + `os.replace`), nigdy wstecz (klucz
   ADR-028 z sidecara wersji). Kontrola: cel z `extra.link_target` +
   `os.path.samefile`; gdy system plikow nie ma stabilnych i-wezlow (SMB bez
   `serverino`), potwierdzenie trescia: oba pliki maja > 1 link, ten sam
   rozmiar i sha256 dowiazania = sha256 sidecara wersji
   (`links._same_content_hardlink`). `FileStorage.get_versions_root(sheet)`/`get_versions_base`,
   `list_files()` pomija `versions/`, `full_sheet/` i `kampanie/`
   (`versions=True` = tylko pliki wersji). Katalog `kampanie/` z 0.7.x
   nie jest czytany (`has_legacy_campaigns()` -> `Info:` w CLI). Od planu
   2/3 te sama mechanika maja kafle LAZ (etykieta `<akt_data>_<zgloszenie>`,
   D26; `FileStorage.get_raw_versions_root/base(sheet, system=)`), arkusze
   CZ (etykieta = data pobrania UTC) i wycinki `bbox/` (hierarchia `bbox`,
   `storage.bbox_slot`); wspolna polityka plikow bez kampanii:
   `download/fetch.py::fetch_version`. Stary zwykly plik 0.7.x w sciezce
   standardowej (sidecar bez `extra.link`) jest zastepowany dowiazaniem
   (D24). Land cover i HSG (plan 3/3) — regula 8.
   Kopiowanie `data/`: `rsync -aH`/`cp -a` (bez zachowania hardlinkow
   powstaje duplikat).

7. **Drugie dowiazanie `full_sheet/` (ADR-033).** Obok sciezki
   standardowej `<segment>/full_sheet/<hierarchia>/<godlo>.<ext>`
   (+ `.meta.json`) wskazuje najnowszy LOKALNY lot zadania oznaczony
   w skorowidzu jako pelny (`full_sheet is True`; NIE i brak flagi = nie
   pelny). Ta sama mechanika co regula 6 (`download/links.py::ensure_link`:
   wylacznie hardlink, nigdy wstecz wsrod lotow pelnych, sidecar z
   `extra.link_target`); gdy najnowszy lot jest pelny, oba dowiazania to
   ten sam plik. Brak pelnego lotu = brak pliku w `full_sheet/`
   (istniejace dowiazanie zostaje). `FileStorage.get_full_sheet_path`
   buduje sciezke, `list_files()` pomija `full_sheet/` (tak jak
   `versions/`), `delete(sheet)` usuwa oba dowiazania z sidecarami.
   Kolizja z hierarchia niemozliwa: pierwszy czlon hierarchii to arkusz
   1:1M albo strefa (`N-34`, `7`). LAZ, CZ, wycinki i land cover nie maja
   `full_sheet/`.

8. **Land cover i HSG (ADR-036 D29-D33, spec 3.4).** Segment = prefiks
   `storage_subdir` deskryptora (`landcover/pl_bdot10k`,
   `landcover/eu_corine`, `soil/global_soilgrids`; HSG: stala
   `HSG_SEGMENT_PREFIX = "hsg/global_soilgrids"`) + `_` + tokeny tresci
   lowercase (`[a-z0-9.-]+`, `download/storage.py::content_segment`):
   BDOT10k `gpkg[_<warstwy>]`/`gpkg_zip`/`shp` (archiwum rocznikow -
   regula 9), CORINE `<rok>[_preview]`, SoilGrids
   `<wlasciwosc>_<glebokosc>_<stat>`, HSG `<glebokosc>_<stat>`.
   Pod segmentem (`download/storage.py::unit_slot`): `teryt/<T><ext>`
   (BDOT10k, takze przy wyborze bboxem/arkuszem), `bbox/<coords><ext>`
   (EPSG:2180, `.10g`, jak wycinki) albo hierarchia godla (`path_parts`,
   kanoniczne godlo). Wersje jak w regule 6 (`versions/<ta sama
   hierarchia>/`).

9. **Kolekcje (ADR-042 D8; rozszerzenie reguly 8).**
   `<grupa>/<kraj>_<zrodlo>[_<tokeny>]/{teryt/<T>|bbox/<coords>|country/<kod>}<ext>`:
   segment = prefiks `storage_subdir` + tokeny wariantu tresci
   (`content_segment`), pod nim `unit_slot`: `teryt/<T>` (paczka powiatu
   albo wojewodztwa - takze, gdy obszar rozlozono na powiaty z PRG),
   `bbox/<coords>` (wynik obszaru; wspolrzedne w ukladzie NATYWNYM uslugi,
   `.10g`, `_`) albo `country/<kod>` (plik krajowy, `pl`/`cz`); wersje
   w `<segment>/versions/<ta sama hierarchia>/`. Tokeny = wariant tresci:
   poziom (`pl_prg_gmina`), LoD i rok (`pl_buildings_lod1_2024`), format
   i rocznik archiwum (`pl_bdot10k_shp_2024`). Wynik obszaru (zawsze GPKG
   w ukladzie natywnym) nie ma tokenu formatu; paczka i plik krajowy maja
   token formatu zrodla, gdy produkt ma kilka formatow albo takze wynik
   obszaru (`pl_prg_gml`, `pl_prg_shp`, `pl_egib_gpkg` obok `pl_egib`),
   a gdy zrodlo publikuje plik w kilku ukladach - takze kod EPSG (plan D).
   Rozne tresci nigdy nie dziela slotu. Identyczna tresc innego wydania tej
   samej jednostki, formatu i LoD (`FileSlot.related_roots`, D7) nie zajmuje
   miejsca drugi raz: nowa wersja jest hardlinkiem do istniejacych danych
   (`relabeled`, `same_as` = etykieta znalezionej wersji).

Nowe zrodlo rastrowe wymaga providera i toru dyspozycji (sekcja 5), ale
jego `storage_subdir` (np. `nmt/de_bb_dgm1_dhhn2016/`) nie wymaga
specjalnej reguly w kodzie sciezek; produkt kolekcji (regula 9) to sam
wpis deskryptora z parametrami kanalu.

**Migracja 0.6.x -> 0.7.0 (BREAKING):**

| Stara sciezka | Nowa sciezka |
|---|---|
| `nmt_1m/` (godla 1992) | `nmt/pl_1992_1m_<vcrs>/` |
| `nmt_1m/` (godla kropkowe 2000) | `nmt/pl_2000_1m_<vcrs>/` |
| `nmt_5m/` | `nmt/pl_<uklad>_5m_evrf2007/` |
| `nmpt/` | `nmpt/pl_<uklad>_1m_<vcrs>/` |
| `orto/` | `orto/pl_<uklad>/` |
| `laz/` | `laz/pl_<uklad>_<vcrs>/` |
| `cz_dmr5g/` (0.7.0-dev) | `nmt/cz_dmr5g_<vcrs>/` |
| `cz_dmr4g/` (0.7.0-dev) | `nmt/cz_dmr4g_<vcrs>/` |

`<uklad>` bierze sie z formatu godla KAZDEGO pliku z osobna (kropki -> `2000`,
myslniki -> `1992`, regula `path_parts` z sekcji 3.1) — stary `nmt_5m/`,
`nmpt/`, `orto/` i `laz/` trzymaly oba systemy razem, wiec jeden stary katalog
rozchodzi sie przy migracji na dwa segmenty (`orto/` -> `orto/pl_1992/`
i `orto/pl_2000/`).

`<vcrs>` przy recznej migracji odczytaj z sidecara (pole `vertical_crs`:
`EPSG:9650` -> `kron86`, `EPSG:9651`/`EPSG:5621` -> `evrf2007`, `EPSG:8357`
-> `bpv`). Pliki sprzed etapu 0 sidecarow nie maja — wtedy zostaje wiedza
wlasna uzytkownika albo re-download. Kartograf nie migruje istniejacego
`data/` automatycznie: pliki w starym ukladzie po prostu przestaja byc
widziane jako pobrane (nastepne zadanie pobierze je ponownie do nowego
segmentu).

### 3.4 `extra.parent_request`

W trybie `--bbox`/`--geometry` sidecary zadania dostaja `extra.parent_request`
— od 2026-10-07 takze kafle LAZ (`download_laz_area(parent_request=)`,
review-2 N15; `countries` = `["PL"]`, bo LAZ odpytuje tylko GUGiK):

```json
{"bbox": [min_x, min_y, max_x, max_y], "bbox_crs": "EPSG:2180", "countries": ["CZ", "PL"]}
```

Niesie **oryginalne** zadanie uzytkownika — przed przycieciem per kraj — jego
uklad i kraje faktycznie odpytane w tym wywolaniu (probowane, nie pobrane).
W trybie `--geometry` "zadanie" to obwiednia geometrii: dla pliku w ukladzie
czeskim (EPSG:5514/3045) w ukladzie PLIKU (od 2026-09-28), dla pozostalych
w EPSG:2180; jawne `--country cz` zapisuje obwiednie w ukladzie zadania CZ
(`--horizontal-crs`). Klucz buduje `download/area.py::parent_request_for`,
wywolywany przez `download_data`; bezposrednie wywolanie toru bibliotecznego
zapisuje go tylko po przekazaniu `parent_request=`.
Wersja z sidecarem zachowuje `parent_request` zadania, ktore ja
UTWORZYLO; kolejne zadania nie zmieniaja sidecara wersji (ADR-036; lista
`extra.parent_requests` usunieta w 0.8.0). To jest klucz grupowania:
po nim konsument (Hydrograf, przyszly `find_downloaded`) sklada w calosc
pliki jednego zadania, takze te lezace po obu stronach granicy, ktore
Kartograf swiadomie zostawia rozdzielone (sekcja 1). Slownik jest wspoldzielony
przez referencje miedzy sidecarami zadania i **nie moze byc mutowany** po
utworzeniu.

### 3.5 Manifest projektu `kartograf-project/1`

`kartograf project init --output KATALOG` tworzy w katalogu projektu
`kartograf-project.json` (UTF-8, JSON z wcieciem 2 spacje). Manifest
przechowuje `schema: "kartograf-project/1"`, `output_dir` (jeden magazyn
wersjonowany) i `tasks` w kolejnosci dodania. Zadanie ma unikalne `name`,
`command` (np. `elevation download`), `options` wyboru danych, `pinned_at`,
`kartograf_version` i `files`; przy przypietej geometrii takze
`geometry_sha256`. `pinned_at` i `kartograf_version` sa `null`, a `files`
puste przed pierwszym pobraniem. Kazdy wpis pliku podaje `role` (`output`,
`raw`, `input`), `unit`, standardowa sciezke `path`, sciezke niezmiennej
wersji `version`, `label`, pelny `sha256` i `size_bytes`. Manifest wybiera
wersje danych; sidecar `kartograf-meta/1` niezmiennie opisuje pochodzenie
pliku. Raport aktualizacji `kartograf-plan/1` nie jest czescia manifestu.

Wzgledny `output_dir` i wzgledny `options.geometry` sa zapisane i
rozstrzygane wzgledem katalogu projektu, a bezwzgledne pozostaja
bezwzgledne. `path` i `version` sa zawsze wzgledne do magazynu, z
separatorem `/`; `version` wskazuje plik pod `versions/`, nigdy
`.incoming/`. Przenoszenie katalogu projektu razem z magazynem zachowuje
powiazania, jezeli ich wzajemne polozenie pozostaje takie samo.

`kartograf/project/manifest.py` scisle sprawdza strukture i typy przy
kazdym odczycie (w tym nazwy i opcje komend, sumy i sciezki). Zapisuje
plik tymczasowy obok manifestu, synchronizuje go (`fsync`) i podmienia
atomowo (`os.replace`); synchronizuje rowniez katalog, gdy system plikow
na to pozwala. Krotka blokada katalogowa `.kartograf-project.lock`
(`mkdir`) obejmuje tylko odczyt-scalenie-zapis, a nie pobieranie. Przy
rownoleglych operacjach zmiany roznych zadan sa scalane, zmiana tego
samego zadania zglasza konflikt bez nadpisania cudzych przypiec. Zapis
nastepuje po kazdym zakonczonym zadaniu; nie ma SQLite ani blokad
zakresow bajtow na udziale. Szczegoly formatu i trybow:
[`USAGE.md`, sekcja 8](USAGE.md#8-projekt) oraz spec
`docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`.

---

## 4. Przeplywy per produkt

**Migracja 0.7.x -> 0.8.0 (ADR-036, BREAKING):**

| Stan | Zachowanie |
|---|---|
| `<segment>/kampanie/` z 0.7.x | nie jest czytany ani migrowany; CLI wypisuje raz `Info:`, potrzebne kampanie sa pobierane ponownie do `versions/` |
| dowiazanie albo zwykly plik w sciezce standardowej | sidecar bez `extra.link = "hardlink"` z celem w `versions/` = sciezka nieznana; po pobraniu wersji ZASTEPOWANA hardlinkiem |
| dowiazanie do wersji | kolejne zadania przestawiaja je tylko na wersje o kluczu `(aktualnosc, dt_pzgik, url)` wiekszym niz klucz biezacego celu; rowny klucz (nowa tresc tej samej kampanii) tylko, gdy wersja powstala w tym wywolaniu |
| dowiazanie, ktorego `extra.link_target` nie istnieje (katalog wersji usuniety) | brak pliku — pobranie od nowa |

**Komenda `download` w bibliotece (ADR-037, od 0.8.0).** `kartograf elevation download`
i `kartograf imagery download` (grupy CLI, ADR-039) oraz `download_data(...)`/`check_data(...)` (`download/data.py`) to ta sama
sciezka: CLI zamienia flagi na argumenty (`--bbox` -> `BBox`,
`pl=..,cz=..` -> slownik) i wypisuje wynik. `download_data` waliduje cale
zadanie przed siecia (`download/options.py`: wybor obszaru, produkt,
kraj, uklad i rozdzielczosc per kraj, system, skala, lata, opcje LAZ;
`ValidationError` z tekstem jak w `--help`), rozstrzyga kraj (godlo:
z kodu; obszar: `--country`, `auto` z przycieciem, sekcja 4.6), wybiera tor
(arkusze PL 4.1/4.2, wycinek PL 4.3, CZ 4.4/4.5, LAZ 4.7), buduje
`parent_request` (`download/area.py`) i zbiera wynik
`DataReport(files, failed, stale, superseded, notices, ok)`: `files` =
`UnitFile(unit, country, file: VersionedFile)`, `failed` =
`UnitFailure(unit, country, error, kind)`, `ok` = regula kodu wyjscia
(czesciowy sukces `auto` = `True`). Komunikaty o danych sa `Notice`
(`kartograf/notices.py`; lista kodow w docstringu `download/data.py`)
przekazywane przez `on_notice` w chwili powstania i zwracane w `notices`;
CLI wypisuje je jako `Info:`/`Warning:` na stderr (takze z `-q`), naglowek
listy arkuszy (`SHEET_LIST`) na stdout. `check_data` (te same argumenty
bez `update`, `plan`, `workers`, `on_progress`) zwraca jeden plan
`kartograf-plan/1` (pod `auto` z pozycjami PL i CZ). Tory sa publiczne
(`download_pl_cutout`, `download_cz_cutout`, `download_cz_sheet`,
`download_laz_area`, `DownloadManager`) z parami `check_*`; ich kroki
wewnetrzne nie.

**Kolekcje (ADR-042, od 0.8.0).** `kartograf boundaries download`,
`cadastre download` i `models3d download` (grupy ADR-039, ADR-042 D9)
to `download_collection(...)`/`check_collection(...)`
(`download/collections.py`) - jeden orkiestrator dla paczek jednostek
i obiektow obszaru, sterowany parametrami kanalu deskryptora (sekcja 4.10).

### 4.1 Godlo PL (NMT/NMPT/Orto)

`SheetParser` waliduje godlo i normalizuje je do postaci kanonicznej:
wielkosc liter i liczby PL-1992 bez zer wiodacych (od 0.7.1, A7:
`M-33-036-A` -> `M-33-36-A`, ta sama postac w sciezce, sidecarze i wyniku);
cyfry tylko ASCII `0-9` we wszystkich ukladach godel (PL-1992, PL-2000, CZ;
od 0.7.2 — cyfry pelnej szerokosci itp. to `ParseError`); godlo
PL-1992 grubsze niz 1:10000 rozwija sie do arkuszy 1:10000
(`download_hierarchy`), godlo PL-2000 pobierane jest bezposrednio (archiwa
ADR-041: arkusze ze skorowidza, sekcja 4.2).

**Skorowidz NMT/NMPT: WFS (od 0.8.0, ADR-041).** Provider NMT/NMPT
obsluguje JEDEN wariant rejestru (sekcja 3.1: produkt, format,
rozdzielczosc, uklad wysokosci) i czyta rekordy ze skorowidza WFS tego
wariantu (`IndexRef`; `providers/pl/skorowidz_wfs.py`,
`WfsSkorowidzLayersMixin`): typy roczne uslugi z GetCapabilities
(`WfsIndex.feature_types`: wzorzec `^(?:gugik:)?<prefiks><rok>$`,
najnowsze pierwsze, typ rodziny spoza wzorca = `logger.warning`, brak
typow = `DownloadError`) i JEDEN `GetFeature` ze wszystkimi typami
(`TYPENAMES`), `SRSNAME` i `BBOX` w URN `EPSG::2180` z osiami (N,E),
kwadrat 20 m w srodku arkusza (`sheet_query_bbox`), `COUNT=1000`.
Serwer ignoruje `FILTER`, wiec kazdy filtr jest po stronie klienta;
kolejne strony wylacznie po atrybucie `next` (z tej samej uslugi).
Odpowiedz kilku typow, ktora ma `next` (nie miesci sie na stronie), jest
odrzucana i kazdy typ jest odpytywany osobno — serwer stronicuje kilka
typow niespojnie (powtorzenia i pominiecia, pomiar 2026-10-15), jeden typ
spojnie. `numberReturned` rozny od liczby obiektow, obiekt powtorzony na
kolejnej stronie, `next` spoza uslugi, petla stron, `ExceptionReport` albo
nie-XML przy HTTP 200 = `DownloadError` z dopiskiem `wynik bylby
niepelny` — nigdy pusty wynik (pusta, poprawna kolekcja = brak rekordow,
np. morze); blad transportu zachowuje `status_code` (I-1 nizej).
`parse_index_feature` mapuje pola WFS na klucze rekordu skorowidza
(sekcja 3.2), `layer` = typ obiektu (`SkorowidzNMT2025`); obiekt bez URL
`https` albo z godlem spoza `SheetParser` (np. godla 8-czlonowe PL-1992)
nie jest rekordem. Ortofotomapa zostaje na WMS (`SkorowidzLayersMixin`:
`GetFeatureInfo`, warstwy wykryte lazy przez `GetCapabilities` — ADR-020).

`providers/pl/skorowidz.py` filtruje rekordy (twardy filtr ADR-028,
`SkorowidzQuery`): cale godlo, zgodny uklad i rozdzielczosc, dla
NMT/NMPT takze **format** wariantu (`source_format`: pole `format`
rekordu i koncowka sciezki URL musza wskazywac ten sam format — ten sam
arkusz bywa w skorowidzu jako siatka `.asc` i archiwum `.xyz.zip`; siatki
kampanii 72675 (NMT 2019, 42 rekordy) maja nazwe `.xyz` i sa siatkami ASC), dla orto wariant
koloru z `color`; wybiera (strategia `newest`) rekord z najnowsza data
w pierwszej grupie warstw z dopasowaniem (NMT/NMPT: jedna grupa = wszystkie
typy roczne uslugi); remis rozstrzyga `dt_pzgik`, URL. Uklad wysokosci
wybiera wylacznie usluga (osobny skorowidz na uklad); przed pobraniem
`verify_record_vertical_crs` (`download/campaigns.py`; wywolania w
`DownloadManager._fetch_campaigns` dla `newest` i `all` oraz w
`GugikProvider.download`) porownuje pole rekordu `ukladWspolrzednychPionowych`
z zadanym ukladem (`RECORD_VERTICAL_CRS`: KRON86 -> `PL-KRON86-NH`, EVRF2007
-> `PL-EVRF2007-NH`, wartosci z surowych odpowiedzi GUGiK). Inna wartosc =
`DownloadError` kampanii przed pobraniem (w `all` pozostale kampanie sa
pobierane, arkusz konczy sie porazka); brak pola = rekord przyjety (log
`debug`); orto nie ma ukladu wysokosci — bez sprawdzenia. Wartosc z rekordu
zapisuje `extra.source.declared_vertical_crs`, takze w cache rekordow —
niezgodny rekord z cache daje ten sam blad, odswiezenie: `--force`. Brak zgodnego rekordu
po poprawnych odpowiedziach warstw = `NoCoverageError`, np. dla PL-2000
1:10000 z samymi potomkami podpowiedz `--scale 1:2000`. NMT/NMPT (P10
od 0.7.2, po WFS od 0.8.0; `GugikProvider._no_coverage`): rekordy
arkusza innych wariantow rejestru przychodza w tej samej odpowiedzi
WFS (wszystkie formaty i rozdzielczosci punktu) i daja podpowiedz bez
sieci, np. `Skorowidz GUGiK ma ten arkusz w NMT 1m EVRF2007 - uzyj
--resolution 1m` — najpierw warianty tego samego formatu, inne formaty
(`--format XYZ`) tylko gdy takich nie ma; rekordy spoza rejestru daja
jedna linie `... tylko rekordy, ktorych Kartograf nie pobiera: ...`.
Drugi uklad wysokosci (`_variant_hints`): jedno `GetFeature` do uslugi
drugiego ukladu (wszystkie typy, ten sam kwadrat i twardy filtr, jedna
proba bez ponowien, timeout `DEFAULT_TIMEOUT`). Tekst podpowiedzi jest
bez godla (jedna linia `Info:` dla wielu arkuszy). Blad zapytania
o drugi uklad = brak tej podpowiedzi, `logger.warning`
i pominiecie tej uslugi do konca zycia providera, nigdy zmiana wyniku;
trafienie w cache braku pokrycia (z podpowiedziami) nie odpytuje sieci. Awaria warstwy,
raport OGC albo nieoczekiwany szablon = `DownloadError`, nie cichy fallback
do starszej kampanii. Zapytania i pobrania maja do 3 prob z backoffem
(ponawiane: siec, 429, 5xx; inne 4xx koncza przy pierwszej probie)
oraz sesje keep-alive per watek. `MetadataCache` (SQLite WAL, TTL 7 dni)
zapisuje rekord `{"source": ...}` lub potwierdzony `{"no_coverage": true}`;
CLI i biblioteka uzywaja tego samego cache (Z6, ADR-037): parametr
`cache: MetadataCache | bool = True` funkcji publicznych (`True` =
`<cwd>/.kartograf_cache.db` przez `cache/defaults.py::open_cache`, `False` =
bez cache); `update="force"` (CLI `--force`) otwiera go w trybie
`MetadataCache(refresh=True)` — odczyt pominiety, swiezy rekord zapisany
(E14); `kartograf cache stats` pokazuje `Wpisy rekordow`.
Baza jest otwierana leniwie: plik `.kartograf_cache.db` powstaje dopiero przy
pierwszym zapisie (`set_*`); konstrukcja, odczyty (`get_*` = chybienie),
`stats()` (zera, `db_exists: false`), `clear()` i `close()` na braku pliku
go nie tworza, wiec `kartograf cache path|stats|clear` w katalogu bez bazy
niczego nie zapisuja. Cache jest tylko przyspieszeniem: kazdy
`sqlite3.Error` (uszkodzony/uciety plik, brak uprawnien, `database is
locked`) wylacza instancje na reszte jej zycia (odczyt = chybienie, zapis =
no-op, `MetadataCache.error`, `stats()["error"]`) z jednym ostrzezeniem
(`Notice` `CACHE_DISABLED` przez `on_notice`; CLI: jedno `Warning:` na komende);
pobieranie idzie dalej. `MetadataCache(strict=True)` (biblioteka, od 0.7.1):
ten sam stan konczy sie `CacheError` na wywolaniu, ktore zawiodlo, i na
kazdym kolejnym (`on_disabled` nadal raz). Naprawa: `kartograf cache clear`
usuwa nieczytelny plik z `-wal`/`-shm`.
`DownloadManager` pisze sidecar po kazdym udanym arkuszu; arkusz ASC GUGiK
nie niesie CRS (rasterio: `crs=None`), wiec jedynym nosnikiem ukladu jest
sidecar. Ponowne uruchomienie rozwiazuje najnowszy rekord arkusza (cache 7 d;
po jego wygasnieciu zapytanie do skorowidza) i stosuje tryb `update`
(ponizej, "Tryby i plan aktualizacji"). `--cutout` w trybie godlowym jest
**odrzucane** (kod 1) — godlo PL dostarcza arkusz natywny 1:1.

**Niepelna najnowsza kampania (E13).** Rekord z `full_sheet: false`
(skorowidz deklaruje arkusz nie w calosci wypelniony) nadal wygrywa, gdy
jest najnowszy (ADR-028 bez preferencji pelnego arkusza); fakt trafia do
`extra.source.full_sheet`, a CLI czyta go z sidecarow wyniku i drukuje
jeden `Warning: najnowsza kampania GUGiK jest niepelna dla N arkuszy ...`
na stderr w torze godla, listy i hierarchii — takze dla arkuszy pominietych
jako istniejace (kod bez zmian). Warning dzieli arkusze (ADR-033): "pelny
lot w <segment>/full_sheet/" (`DownloadResult.full_links`), "brak pelnego
lotu w skorowidzu" (`DownloadResult.without_full`; przy `all` kazdy arkusz
bez dowiazania pelnego; z granica roku z dopiskiem "w zakresie lat
zadania") i "pelny lot nie pobrany — uzyj --full-sheet".
Znaczenie flagi: TAK = pelne pokrycie w granicach Polski (pomiar
`docs/research/2026-10-10-full-sheet-link/granica-pelne-pokrycie.md`:
nodata za granica w arkuszach granicznych jest normalne), NIE nie mowi
o skali braku (0,9-98,9 %). Wycinek: sekcja 4.3 (`partial_sheets`),
mozaika nadal ze sciezek standardowych.

**Drugie dowiazanie i `--full-sheet` (ADR-033).** Po dowiazaniu
standardowym `_fetch_campaigns` dowiazuje `full_sheet/` do najnowszego
lotu z `full_sheet is True` wsrod lotow TEGO zadania (regula 7 w 3.3);
bez kandydata dowiazanie pelne zostaje nietkniete. Porazka tego
dowiazania = porazka arkusza (`dowiazanie <sciezka>: <blad>`), `--force`
je odswieza, I-1 go nie dotyka. `DownloadManager(full_sheet=True)` (CLI
`--full-sheet`): przy `newest`, gdy wybrany rekord nie jest pelny, manager
wola dodatkowo `resolve_campaigns(all_campaigns=True, min_year=..., max_year=...)`
i bierze pierwszy rekord pelny (lista od najnowszego, `campaigns_cache`)
jako jeszcze jedna kampanie arkusza — najwyzej jeden dodatkowy lot;
brak = `DownloadResult.without_full`.
Awaria tego zapytania albo pobrania lotu pelnego = porazka arkusza
(sciezka standardowa i tak wskazuje najnowszy). Sidecar kampanii zadania
z flaga: `request.full_sheet: true`. Z `all` flaga bez skutku; z
`--cutout` i LAZ `Error:` przed siecia. Przy przedziale lat
dowiazanie pelne spoza zadania: `full_link_outside_range` i wspolny
`Info:` z U15.

**Kampanie i rok danych (ADR-030, ADR-032).** NMT/NMPT/orto przyjmuja
`--year Y` (skrot `--min-year Y --max-year Y`), `--min-year L` i
`--max-year U` (granice wlacznie, 1900..2100); rok to `aktualnoscRok`,
inaczej `aktualnosc[:4]`, NIE `dt_pzgik`. Flagi roku sa tylko filtrem
dopuszczalnych lat; `--all-campaigns` decyduje o liczbie lotow (model A,
ADR-032 pkt 3): bez przelacznika (domyslnie, dozwolone z kazda granica) = jeden
najnowszy lot z przedzialu, z przelacznikiem = wszystkie loty z przedzialu, takze
kilka w roku. Ta sama regula dla LAZ.
Zadanie z jakakolwiek granica najpierw sprawdza WSZYSTKIE arkusze
w `DownloadManager.check_year_range`: jedna pelna lista kampanii z kazdej
warstwy GetCapabilities na arkusz, filtr lat po twardym filtrze ADR-028.
Lista `campaigns_cache` (TTL 7 dni, bez `scanned_from`) sluzy rowniez
`newest` z dowolna granica; bez granic `newest` nadal bierze
`record_cache`. `GugikProvider.available_years(sheet)` zwraca rosnace
lata z pelnej listy. Arkusz bez danych GUGiK = `NoCoverageError` i
pominiecie R5, a z danymi tylko poza przedzialem = `YearRangeError`
(lista lat do 20 arkuszy, podpowiedz tylko gdy jedna jednostronna
granica obejmuje wszystkie konflikty), zero pobran dla CALEGO zadania.
Awaria skorowidza w fazie sprawdzania przerywa zadanie przed pobraniem,
chyba ze w trybie domyslnym (D14) KAZDY arkusz zadania ma lokalna wersje
z rocznikiem w zakresie (`extra.campaign.date[:4]`) — wtedy arkusze
z bledem skorowidza dostaja te wersje z ostrzezeniem (`unverified`).
Potem manager wykorzystuje JUZ sprawdzone rekordy, zapisuje kazdy wybrany
i brakujacy lot jako wersje w `versions/`, aktualizuje dowiazanie raz
na arkusz (najnowszy lot wg ADR-028, nigdy wstecz), sidecary i pokrycie
opisane w 3.2. `DownloadResult.better_coverage` wskazuje arkusze z
lotem o lepszym pokryciu (tylko `all`); `link_outside_range` i
`full_link_outside_range` — arkusze, ktorych dowiazanie standardowe albo
`full_sheet/` zostalo przy locie spoza zadania (nigdy wstecz), CLI drukuje
wtedy jeden `Info:` z linia `<godlo>: sciezka standardowa|full_sheet/ ->
dowiazanie <data>_<id>`. Dalsze szczegoly: jedna regula
`DownloadManager._select` (wspolna dla pobierania i `inspect_sheets`)
decyduje per rekord "lokalna wersja albo pobranie"; pobranie
(`GugikProvider.download_record` do katalogu roboczego, `record_source`
-> `extra.source`) konczy `commit_version` (ADR-036); po zebraniu kampanii
manager przestawia dowiazanie RAZ na arkusz (deduplikacja godel; nigdy
wstecz). `download_sheet`, `download_hierarchy` i `download_sheets`
zwracaja `DownloadResult`: `succeeded`, `failed`, `skipped`, `no_coverage`
(podzbior `failed`: brak danych u zrodla), `no_coverage_hints` (godlo ->
`NoCoverageError.hints`), `campaign_files`, `reused_campaign_files`
(wersje juz lokalne per arkusz), listy `new`/`relabeled`/`unchanged`/`local`,
`newer` (godlo -> nowsza kampania nie pobrana), `unverified`, `stale`
i `notices`. `files[godlo]` zawiera `VersionedFile` dla kazdego wybranego
lotu, ze statusem, etykieta i sciezka wersji. Wynik pojedynczego arkusza
ma ten sam ksztalt co wynik listy. Pelna lista pol: docstring
`DownloadResult` w `download/manager.py`. Pochodzenie arkusza
przy kampaniach: `provider.source_info()` wypelnia przeplyw jednego rekordu
(`download`, `get_download_url`, `resolve_campaigns` w trybie `newest`), a przy
`all` zostaje `None` — zrodlem pochodzenia jest wtedy sidecar
(`extra.source`, `extra.campaign`); sidecar sciezki standardowej opisuje
wersje, na ktora wskazuje dowiazanie, a ta moze byc starsza niz najnowszy
rekord (D5 albo nieudane pobranie, A12). Przed siecia
`verify_record_url` (B4): nazwa pliku w URL rekordu musi konczyc sie godlem
arkusza (`<id>_<numer>_<godlo>.<ext>`, porownanie w postaci kanonicznej;
nazwy archiwow ADR-041 takze z koncowkami `.xyz.zip`, `.zip.zip`,
`_asc.zip`, `_tin.zip`, prefiksem `NMT-` i godlem bez separatorow);
URL bez godla albo z innym godlem = `DownloadError` kampanii bez pobierania.
Plik: format z pola `format` rekordu (nie z URL; brak pola — format
domyslny produktu), rozszerzenie zawsze kanoniczne z `FORMATS` rejestru
(`.asc`/`.tif`; archiwa `.zip`, `.ttn`, `.grd`, `.dxf`, `.dgn`); rekord
NMT/NMPT, ktorego URL nie zgadza sie z polem `format` (np. siatka z URL
`.zip`), nie przechodzi twardego filtru formatu i nie jest pobierany
(nazwa `.xyz` siatek kampanii 72675 jest akceptowana: AAIGrid sprawdzony
na zywo i ponownie po pobraniu). Po pobraniu `verify_file_format`
(naglowek AAIGrid / sygnatura TIFF; archiwa: kompletny ZIP z czytelnym
katalogiem centralnym, sygnatura TTN, naglowek Intergraph GRD/DGN,
`SECTION` DXF), potem `verify_sheet_extent` (B4,
tylko `.asc`): zasieg z naglowka ASC (`xllcorner`/`xllcenter`,
`yllcorner`/`yllcenter`, `ncols`, `nrows`, `cellsize`; wariant `*center`
przesuniety o pol piksela) musi co najmniej w 50 % powierzchni
(`MIN_FRAME_OVERLAP`) lezec w ramie godla liczonej w ukladzie PLIKU:
`x < 1e6` = EPSG:2180 (takze arkusz PL-2000 opublikowany przez GUGiK w
EPSG:2180, E17), inaczej natywna strefa PL-2000 godla. Arkusz czesciowy
(`full_sheet=False`) lezy w ramie i przechodzi, arkusz sasiedni albo z
innego miejsca nie; naglowek nieczytelny albo niepelny = blad. Nieznany
format albo niezgodna tresc = `DownloadError` kampanii z nazwa formatu,
zasieg spoza ramy = `DownloadError` z zasiegiem pliku i rama godla;
wersja nie powstaje. Blad pobrania
podaje nazwe pliku z URL (`84183_1852496_N-34-139-C-a-3-1.asc (OpenData):
HTTP 404`), co w `all` rozroznia kampanie. Porazki: kampania (w tym
niepoprawna `aktualnosc` rekordu w `all`, brak sidecara, porazka
weryfikacji, kolizja sha256) = porazka tej kampanii — pozostale sa pobierane,
dowiazanie idzie na najnowsza poprawna, ale arkusz konczy sie porazka (kod 1);
porazka samego dowiazania (takze brak hardlinkow) = porazka arkusza (lista
idzie dalej takze przy `--workers 1`, zapisane wersje zostaja). Wyscig bez
blokad: rownolegle zapisy tej samej tresci koncza w jednej wersji
(wylaczny `os.link`), a rownolegle przestawienia dowiazania moga chwilowo
zostawic je na starszej wersji; kolejne wywolanie je naprawia.

**Tryby i plan aktualizacji (ADR-036, D5, D14).** `update` w
`download_sheet`/`download_hierarchy`/`download_sheets` (CLI: brak flagi,
`--upgrade`, `--force`; wzajemnie wykluczajace sie z `--check-updates`):
domyslnie lokalna wersja z etykieta rekordu jest uzywana bez pobrania,
brakujace wersje (`all`, `--full-sheet`, brak lokalnej) sa pobierane,
a gdy najnowszy lot nie jest lokalny, ale jest inna lokalna wersja
z zakresu (najpierw cel dowiazania), zostaje ona i `DownloadResult.newer`
(CLI: dopisek `; dostepna nowsza <etykieta> (--upgrade)` i `Info:`).
`update="upgrade"` pobiera ten lot; `force` pobiera wszystkie wybrane
loty ponownie i odswieza `MetadataCache` (ta sama tresc = `unchanged`,
inna = nowa wersja tej samej etykiety), weryfikacja rekordu dziala we
wszystkich trybach; `update="check"` to `ValidationError` (sprawdzenie
robi `manager.check_sheets(sheets)`). Providery bez kampanii: bez `force`
najnowsza lokalna wersja (brak taniego sygnalu).
`DownloadManager.check_sheets(sheets)` (CLI `--check-updates [--plan PLIK]`)
niczego nie pobiera i zwraca `UpdatePlan` (`kartograf-plan/1`: `store`,
`checked_at`, `kartograf_version`, pozycje z segmentem, hierarchia, nazwa,
wersja lokalna i sygnalem rekordu; statusy `current`/`newer`/`missing`/
`unverifiable`/`check_failed`). `manager.download_sheets(sheets,
update="upgrade", plan=plan)` (CLI `--upgrade --plan PLIK`) odrzuca inny
magazyn i nieznany schemat przed siecia, czyta sygnal ponownie i pobiera
wylacznie pozycje `newer`/`missing` z niezmienionym sygnalem; zmieniony
sygnal = pozycja `result.stale` (blad, bez pobrania). Typy planu leza w
`download/plan.py` (`PlanItem.track` = `pl_sheet`/`laz_tile`/`cz_sheet`/
`pl_cutout`/`cz_cutout`, `unit` = jednostka zadania; `UpdatePlan.merge`,
`select_planned`, `new_plan`); pozostale tory dostaja `plan=` w swoich
`run_*`.

**Tory bez kampanii (plan 2/3).** LAZ (`download/laz.py`), arkusze CZ
(`download/cz_sheets.py`), wycinki CZ (`download/cz_cutout.py`) i PL
(`download/cutout.py`) oraz tor bez kampanii `DownloadManager` korzystaja
z jednej polityki `download/fetch.py`: `fetch_version(slot, update,
signal=, fetch=, version=, write_sidecar=, probe=)` — lokalna wersja albo
pobranie do `.incoming/`, `commit_version(signal=)`, hardlink — oraz
`inspect_version` (pozycja planu bez pobierania; `check_laz_area`,
`check_cz_sheet`, `check_cz_cutout`, `check_pl_cutout`). Sygnal wg
kanalu (`AccessChannel.update_signal`, `channel_signal`): LAZ `index`
(kafel z lokalna wersja = `local`, nowszy nalot to nowe pliki, D26),
SM5 `http` (`probe` = `CuzkDmrProvider.sm5_signal`, `HEAD` pliku
`openzu`; rowne `ETag` = lokalna, rozne = `newer` domyslnie, pobranie
przy `upgrade`; nieudane `HEAD` = `unverified="check_failed: ..."`
domyslnie, blad przy `upgrade`), TM33 i wycinki `none` (lokalna,
`unverified="none"`). Wynik: `VersionedFile(path, status, label, sha256,
version_path, newer, unverified)`; `LazDownloadResult.files`,
`CzSheetResult`/`CzCutoutResult`/`PlCutoutResult.file` (`None` tylko
z `plan=`, gdy plan nie wykonuje pliku i nie ma wersji lokalnej) i
`stale`. Pola wyniku lokalnej wersji (`all_nodata`, `masked_pixels`,
`zero_pixels`) pochodza z sidecara wersji, bez odczytu rastra.

CLI drukuje jedna linie na plik: `<godlo>: nowa wersja <etykieta>_<sha8>`,
`nowa etykieta <etykieta> (plik identyczny z <etykieta>)` (najnowsza
istniejaca wersja o tym samym sha256, `VersionedFile.same_as`),
`bez zmian <etykieta>`,
`lokalna wersja <etykieta>`, a po liscie (bez `-q`) `Nowe: N, nowa
etykieta: N, bez zmian: N, lokalne: N, bledy: N (<dir>)` (arkusze PL
i kafle LAZ; jednostka LAZ = nazwa pliku, wycinka = sciezka pod
`--output`). Plik bez taniego sygnalu: domyslnie dopisek `(bez
sprawdzania; --check-updates)`, przy `--upgrade` `Info:` o `--force`;
nieudane sprawdzenie sygnalu: `Warning:`. Raport `--check-updates` to
jedna linia na pozycje (`aktualne`, `nowsza: ...`, `do pobrania`, `nie da
sie sprawdzic bez pobrania`, `nie udalo sie sprawdzic: ...`), kod 1 przy
pozycji niesprawdzonej; z `--plan` CLI zapisuje JEDEN plan wszystkich
torow zadania (`--country auto`: PL i CZ, `UpdatePlan.merge`), a
`--upgrade --plan` czyta go raz przed praca. Katalog `kampanie/` z 0.7.x:
jednorazowe `Info:`.

Awaria skorowidza bez granicy roku (I-1, errata 5 ADR-030; ADR-036: kazda
strategia, tylko tryb domyslny): gdy `resolve_campaigns` konczy sie
bledem TRANSPORTU (`DownloadError` z `status_code` 429/5xx albo bez kodu,
ale z przyczyna `requests.RequestException` — siec/timeout; NIE
`NoCoverageError`, inne 4xx ani raport OGC/zly szablon), a sciezka
standardowa wskazuje istniejaca lokalna wersje (`linked_version`),
manager NIE zglasza porazki: arkusz ma status `local` z
`unverified=<tresc bledu>`, dowiazanie bez zmian. Lista/hierarchia: arkusz
w `skipped`, a `DownloadResult.unverified` (godlo -> tresc bledu). CLI:
`Warning: <godlo>: skorowidz GUGiK niedostepny — uzyto lokalnej wersji bez
sprawdzenia nowszej (<blad>)` (pojedyncze godlo) albo `Warning: skorowidz
GUGiK niedostepny — dla N arkuszy uzyto lokalnych wersji bez sprawdzenia
nowszej (<godla do 10>) (<pierwszy blad>)` (lista), stderr takze z `-q`, kod
bez zmian. `upgrade`, `force` i brak lokalnej wersji (takze dowiazanie
z usunieta wersja docelowa) — blad. Z granica roku: D14 (wyzej).
Biblioteka bez `MetadataCache` pyta
skorowidz przy KAZDYM `download_sheet` (takze arkusza juz pobranego);
przekazanie cache providerowi ogranicza to do raz na 7 dni.

Wynik: `data/nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/<data>_<id>_<sha8>/N-34-130-D-d-2-4.asc`
(+ `.meta.json`) i dowiazanie `data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`;
dla NMPT `data/nmpt/pl_1992_1m_evrf2007/...`, dla innych rozdzielczosci
i archiwow segment wariantu (np. `data/nmt/pl_1992_0.5m_evrf2007/...`,
`data/nmt/pl_1992_tbd_25m_kron86/.../<godlo>.zip`), dla orto
`data/orto/pl_1992/...`.

### 4.2 Bbox / geometria PL bez `--cutout`

Bbox trafia do `download_data` (`download/data.py`), ktore rozstrzyga kraje
(sekcja 4.6), a czesc polska idzie do toru arkuszy PL. `find_sheets_for_bbox` (czysta matematyka
siatki, bez zapytan sieciowych — ADR-010) daje liste godel 1:10000, ktore
pobiera `DownloadManager` rownolegle. W trybie `--geometry` arkusze wyznacza
sama geometria per obiekt (`find_sheets_for_geometry`), nie jej obwiednia.
Gdy `--geometry` wskazuje GPKG z kilkoma warstwami i nie podano `--layer`,
biblioteka wybiera pierwsza warstwe `gpkg_contents` i emituje RAZ przed
praca `Notice` `GEOMETRY_LAYER_DEFAULT` z jej nazwa, pozostalymi warstwami
i podpowiedzia `--layer NAZWA` (CLI: `Info:`, takze z `-q`). Dotyczy
rowniez `LandCoverManager` i `HSGCalculator`; SHP i jednowarstwowy GPKG nie
daja komunikatu.

Sidecar pobranego arkusza dostaje `extra.parent_request` i `extra.source`
(URL, warstwa, data, rozdzielczosc). Ponowne wykorzystanie wersji nie
zmienia jej sidecara (ADR-036). Tryb listy (takze hierarchia godla) probuje
WSZYSTKIE arkusze niezaleznie od `--workers` (ADR-027 errata 3, R5-lista).
`NoCoverageError` dopisuje brakujace godlo i `Warning:`, status postepu
`no_coverage` (ikona `0`, `DownloadProgress.status`), bez wetowania pobranych
plikow. Podpowiedzi `NoCoverageError.hints` (np. `--scale 1:2000`) sa
`Notice` `NO_COVERAGE_HINT` (CLI: `Info:` na stderr, takze z `-q`), bez
doslownych duplikatow, najwyzej `MAX_HINT_LINES` linii plus `... i N innych
podpowiedzi` (pelna lista: `DownloadResult.no_coverage_hints`). Wynik
`DataReport.ok`: >= 1 plik i zero twardych awarii = `True` (kod 0). Gdy
brak wszystkich arkuszy albo wystapi dowolna inna awaria pobrania,
`DataReport.failed` ma pozycje, `ok` = `False` (kod 1).
Pojedynczy arkusz bez danych to kod 1; pod `--country auto` kod zalezy
jeszcze od sukcesu drugiego kraju (sekcja 4.6).

Opcje kampanii i roku (`--all-campaigns`, `--year`, `--min-year`, `--max-year`,
sekcja 4.1) dzialaja tu per arkusz; podsumowanie `all` liczy pliki kampanii,
nie arkusze. Arkusz bez danych w zadnym roku ma status `no_coverage`
(`Warning:` R5); arkusz z danymi tylko poza przedzialem to
`YearRangeError` i przerwanie CALEJ listy przed pobraniem, rowniez przy
samym `--min-year`. Nieudane sprawdzenie skorowidza tez przerywa liste.

**Archiwa GUGiK (`format` inny niz `ASC`, ADR-041).** Arkusze archiwum
maja rozne skale (godla 6-czlonowe 1:25000 i 7-czlonowe jednego wariantu,
arkusze PL-2000), wiec nie wyznacza ich siatka godel, tylko skorowidz:
`download_data` -> `_download_pl_archive` (`download/data.py`) z obszarem
jako wypukle wielokaty EPSG:2180 (`--sheet` = rama godla
`sheet_frame_2180`, `--bbox` = obwiednia `bbox_to_2180`, `--geometry` =
obwiednie obiektow) wola `GugikProvider.index_sheets(areas, system=,
min_year=, max_year=)`: rekordy wariantu (twardy filtr formatu,
rozdzielczosci i ukladu) z typow rocznych w zakresie lat, ktorych rama
(`msGeometry`, inaczej rama godla) przecina obszar o wiecej niz pasek
krawedzi (`overlaps_area`: rama zwezona o `EDGE_TOLERANCE_M` = 1 m — sasiad
stykajacy sie krawedzia nie liczy sie). Dalej zwykly tor arkuszy
(`DownloadManager.download_sheets`: kampanie, wersje, sidecary,
`full_sheet/`), ale godla ze skorowidza nie sa rozwijane do 1:10000
(`DownloadManager` rozpoznaje wariant `source_file`). Pusta lista =
porazka `no_coverage` z tekstem `Skorowidz GUGiK nie ma plikow ... -
dostepne dane obszaru: kartograf elevation availability`. `--scale`
i `--cutout` z archiwum = `ValidationError` przed siecia; `--sheet-system`
wymagane jak dla siatek. Weryfikacja tresci: `verify_file_format`
(4.1), bez `verify_sheet_extent` i pomiaru pokrycia.

**WCS (`provider.download_bbox`) w bibliotece: NMT/NMPT 1 m i orto.**
CLI PL uzywa WCS tylko z `--cutout` (sekcja 4.3); bez tej flagi
pobiera arkusze OpenData. `GugikProvider.download_bbox` dla NMT 1 m i
`GugikNmptProvider.download_bbox` dla NMPT 1 m daja jednopasmowy GeoTIFF
float32 z wysokosciami na siatce 1 m EPSG:2180 (bez nodata, maski PRG,
sidecara i wersji — plik poza magazynem). `DownloadManager.download_bbox`
usuniete w 0.8.0 (D27, errata 2 ADR-003): wycinek w magazynie to
`download_pl_cutout`.
WCS ma tylko wariant 1 m (kanal `bbox_raster` w rejestrze,
`is_wcs_available()`); provider innej rozdzielczosci albo archiwum
daje `ValidationError`. NMT KRON86: endpoint
`DigitalTerrainModelFormatTIFF`, coverage `DTM_PL-KRON86-NH_TIFF`,
`image/tiff` float32; NMT EVRF2007: `DigitalTerrainModel`,
`DTM_PL-EVRF2007-NH`, `image/x-aaigrid`; NMPT KRON86/EVRF2007:
`DigitalSurfaceModel`, `DSM_PL-<v>-NH`, `image/x-aaigrid`.
Stary endpoint TIFF EVRF2007 zwracal 404, lecz ASC EVRF2007 dziala
(raport `docs/research/2026-10-11-wcs-cutouts/raport.md` pkt 1).
`WITHDRAWN_WCS_VERTICAL_CRS=()` zachowuje mechanizm przyszlych wycofan.

`GugikWcsMixin._download_wcs` wyrownuje bbox NA ZEWNATRZ do siatki
`GridSpec(1.0, 0.5, 0.5)`: krawedzie pikseli `k + 0,5` m, wynik moze
siegac o < 1 px dalej na kazdym boku. `plan_wcs_chunks` poszerza zakres
o najwyzej 1 px na wschod/poludnie do parzystej szerokosci i wysokosci
i tnie go na parzyste kawalki (`plan_chunks(multiple=2)`); nadmiar jest
przycinany po zszyciu. Powod (weryfikacja na zywo
`docs/research/2026-10-11-wcs-cutouts-live/raport.md` pkt 3): gdy serwer
przeprobkowuje (NMPT `SCALEFACTOR`, NMT 1 m nad lotem 0,5 m), przy
nieparzystym rozmiarze bierze srodkowy wiersz i kolumne z sasiedniego
piksela zrodla. Limity: 16 Mpx i 40000 px na bok dla TIFF, dla
wolniejszego ASC (ok. 20 s/Mpx, odpowiedz dopiero po policzeniu calego
kawalka) 1 Mpx pikseli coverage w NMT i 4 Mpx w NMPT (1 Mpx wyniku 1 m;
zawieszenia hosta nie zaleza od rozmiaru kawalka, a kawalek 4 Mpx
odpowiada jak 1 Mpx — `docs/research/2026-10-11-nmpt-asc-tuning/raport.md`).
Kawalek ASC czeka na dane co najmniej `WCS_ASC_READ_TIMEOUT` = 120 s
(pierwszy bajt NMPT na zywo do 106 s). NMPT ma natywny krok coverage
0,5 m; `SCALEFACTOR=0.5` daje wynik 1 m na siatce arkuszy. `fetch_chunks`
sklada sekwencyjne kawalki bez
resamplingu i ponawia kazdy osobno. `transport/aaigrid.py` wydobywa
ASC z odpowiedzi multipart strumieniowo, sprawdza naglowek i zapisuje
atomowo GeoTIFF z EPSG:2180; bledna tresc = `DownloadError` bez
ponawiania. Raporty XML sa odrzucane przez `reject_error_document("WCS")`.
Orto pozostaje na wlasnej sciezce `download_bbox`.

Wynik: **wiele plikow** — lista arkuszy w segmencie jak w 4.1 (dowiazania do
wersji w `versions/`; przy `all` dodatkowo kazda kampania). To jest
asymetria wzgledem CZ, gdzie bbox daje jeden wycinek.

### 4.3 Bbox / geometria PL z `--cutout` (ADR-035, ADR-038)

CLI `elevation download --bbox`/`--geometry --cutout --horizontal-crs` oraz
biblioteczne `download_data(cutout=True, horizontal_crs=...)` i
`download_pl_cutout()` pobieraja NMT albo NMPT 1 m z WCS GUGiK, nie
mozaikuja arkuszy. Tryb jest jawny: `--horizontal-crs` jest wymagane
z `--cutout`, bez `--cutout` to `Error:`, `--cutout` z `--sheet` tez.
Biblioteka: `download_pl_cutout(bbox, *, horizontal_crs,
output_dir, vertical_crs, product="nmt"|"nmpt", update, plan,
parent_request, cache, on_notice)` -> `PlCutoutResult`;
`check_pl_cutout(...)` z ta sama selekcja daje plan bez pobierania.
Przygotowanie (walidacja bez sieci) i wykonanie sa krokami wewnetrznymi
(`_prepare_pl_cutout`, `_run_pl_wcs_cutout`), poza API od 0.8.0.

1. Wycinek ma tylko wariant 1 m: `download_pl_cutout` nie ma parametru
   rozdzielczosci (wariant z kanalem WCS z rejestru,
   `download/cutout.py::wcs_variant`: `pl.gugik.nmt_1m` / `pl.gugik.nmpt`),
   a `download_data(cutout=True)` przed siecia odrzuca inna rozdzielczosc
   niz `1m` i archiwum `format` (`ValidationError`; CLI `Error:`, teksty
   w USAGE 1.3; brak `resolution` = `1m`). `download_pl_cutout` odrzuca
   nieobslugiwany pion/CRS docelowy
   (`EPSG:2180`, `EPSG:5514`, `EPSG:3045`) i brak bezpiecznej
   przypietej operacji transformacji. Bbox docelowy wyznacza bbox
   zrodla EPSG:2180; dla warpu ma on zapas 4 px na interpolacje.
   `--geometry` daje obwiednie calej geometrii, bez maskowania do jej
   obiektow. `--sheet-system 2000`, `--cutout` z godlem lub z orto/LAZ
   nadal sa odrzucane przed pobraniem.
2. `download_pl_cutout` pobiera i buduje maske ladu PRG **przed**
   jakimkolwiek zapytaniem WCS: `A00_Granice_panstwa` minus
   `W02_Morze_terytorialne_RP` minus
   `W03_Morskie_wody_wewnetrzne`. `A00` jest pobierana bez BBOX
   (PRG nie przycina jej geometrii); `W02`/`W03` z BBOX obszaru.
   Rasteryzacja bierze srodek piksela (`all_touched=False`), w tym
   nad rzekami granicznymi, zatokami i zalewami. Poza maska nodata
   `-9999`; na ladzie wartosci WCS, **takze 0,0**, pozostaja danymi
   (Zulawy). Maska nie wypelnia zer wewnatrz ladu z arkuszy.
3. Provider pobiera przez `_download_wcs(bbox_source_2180, work,
   "GTiff")` na 1-metrowej siatce arkuszy
   `GridSpec(1.0, 0.5, 0.5)`, z bboxem wyrownanym NA ZEWNATRZ
   (kawalki ADR-034 i limity per format w 4.2). Dla EPSG:2180
   maskowany wynik trafia atomowo przez `os.replace` do pliku;
   dla EPSG:5514/3045 `warp_to_grid` z przypieta operacja, nodata
   i siatka celu wykonuje lokalna reprojekcje. `PlCutoutResult`
   podaje `masked_pixels`, `zero_pixels` liczone przed warpem oraz
   `all_nodata`. Cala powierzchnia poza ladem PL moze dac `all_nodata`
   i `Warning:` (kod 0).
4. Wynik jest w `nmt/pl_1992_1m_<vcrs>/bbox/` lub
   `nmpt/pl_1992_1m_<vcrs>/bbox/` jako
   dowiazanie `<coords>.tif` (bez daty, D15) do wersji
   `versions/bbox/<RRRR-MM-DD>_<sha8>/<coords>.tif` (+ `.meta.json`
   wersji), gdzie `<coords>` opisuja bbox zadania W UKLADZIE WYNIKU,
   nie wyrownany raster. Kroki 2-3 (maska PRG, WCS, warp) dzialaja
   w prywatnym `versions/.incoming/`, a wynik zapisuje
   `fetch_version` (sygnal `none`): domyslnie i przy `upgrade` lokalna
   wersja bez zapytan PRG i WCS (pola wyniku z sidecara wersji, kontrola
   miejsca tylko przy pobieraniu), `force` pobiera ponownie (ta sama
   tresc = `unchanged`; wycinki sa bajtowo powtarzalne, inwentaryzacja
   2026-10-12). `--workers` i `--scale` nie zmieniaja toru WCS. Awaria
   pozostawia poprzednia wersje i dowiazanie, bez pustego drzewa.
   Pliki `<coords>_<YYYYMMDD>.tif` z 0.7.x nie sa rozpoznawane. Sidecar z
   `capability="bbox_raster"`, `extra.source` WCS i `extra.mask`
   PRG opisano w sekcji 3.2. CLI wypisuje `Info:` z liczba zapytan
   WCS dla > 1 kawalka lub wyniku >= 1 GiB (gdy wycinek bedzie
   pobierany).

WCS oddaje kompozycje serwera (najnowszy lot obszaru bez doklejania
starszych), **nie** najnowsza kampanie dokladnie 1 m wybrana dla arkusza
przez ADR-028. Nad lotem 0,5 m wynik 1 m to decymacja (piksel 0,5 m
o srodku na pelnym metrze), nie srednia 2 x 2. Gdy loty sa te same
i siatki sa zgodne, zmierzone WCS i arkusz sa bit w bit zgodne
(`docs/research/2026-10-10-wcs-limits/raport.md` pkt 4, 8 oraz
`docs/research/2026-10-11-wcs-cutouts/raport.md` pkt 2-4).
`--year`, `--min-year`, `--max-year`, `--all-campaigns` i
`--full-sheet` z `--cutout` pozostaja `Error:` przed siecia;
serwer nie udostepnia wyboru lotu.

Tor arkuszowy wycinka (ADR-027: `select_pl_cutout_sheets`,
`run_pl_cutout`, `build_cutout_from_sheets`, `PlCutoutSheets`, parametry
arkuszowe `download_pl_cutout` i `mosaic_and_crop(snap_to_source_grid=,
assign_crs=)`) usunieto w 0.8.0 (ADR-035 errata 2). Scalanie PL+CZ
w jedna powierzchnie pozostaje etapem 2; pod `--country auto` powstaja
dwa pliki ze wspolnym `extra.parent_request`.

### 4.4 Godlo CZ (DMR 5G / DMR 4G)

Godlo TM33 (`302_5550`) rozwija `ParserTM33` do bboxa w EPSG:3045; do serwera
CUZK idzie zadanie `exportImage` **wylacznie w ukladzie natywnym EPSG:5514**
(plus zapas 4 px), a na siatke kafla przenosi je lokalny warp przypieta
operacja (ADR-024 — serwerowa reprojekcja gubila datum shift). Kafel TM33
nie jest wiec produktem 1:1: to warp z EPSG:5514 na siatke EPSG:3045,
przypieta czeska operacja S-JTSK -> ETRS89 (EPSG:1622/1623,
nominalnie 1,0 m; ADR-024 errata 2).
Odpowiedzi `exportImage` sa zawsze pochodna serwera (bilinear; siatka uslugi
DMR 5G ma faze (0,4; 1,88) m mod 2), wiec 1:1 daje tylko arkusz SM5.
Godlo SM5 (`CTES96`) to gotowy plik z openzu, juz w EPSG:5514, bez warpa —
po pobraniu nadpisywane sa tylko metadane CRS. `--vertical-crs EVRF2007` dokleja przypieta
transformacje pionowa Bpv -> EPSG:5621 (przesuniecie w miejscu). `KRON86` dla
CZ jest nieosiagalny (brak publicznych siatek). Sidecar pisze CLI przez
`download/cz_cutout.py::write_cz_sidecar`.

Wynik: `data/nmt/cz_dmr5g_bpv/302/5550/302_5550.tif` (`horizontal_crs`
EPSG:3045) albo `data/nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif`
(`horizontal_crs` EPSG:5514).

### 4.5 Bbox CZ

Jeden wycinek `exportImage`; obszar CZ wymaga `--cutout --horizontal-crs`
(ADR-038; bez `--cutout` `ValidationError` przed siecia). Bbox jest
najpierw normalizowany do ukladu WYNIKU (`--horizontal-crs`, natywnie
EPSG:5514), zeby nazwa pliku niosla wspolrzedne
faktycznie zadanego wycinka. Zadanie do serwera idzie natywnie; przy
`--horizontal-crs` innym niz 5514 tresc reprojektuje lokalny warp
z czeska operacja przypieta. Serwer deklaruje sufity 15000 x 4100 px,
lecz realnie odrzuca zadania powyzej ok. 8 Mpx. `CuzkClient.export_image`
uzywa `transport/chunks.py`: `align_bbox` bez siatki zrodla zachowuje
kotwice NW i `round` do calkowitej liczby pikseli, `plan_chunks` dzieli
zadanie z budzetem `MAX_EXPORT_PIXELS = 4_000_000` (kwadratowawe kawalki
z zachowaniem sufitow wymiarowych), `fetch_chunks` pobiera je po kolei
i sklada przez `mosaic_and_crop` bez resamplingu przed warpem. Zachowanie
CUZK jest bez zmian: piksel to dokladnie 2 m/5 m, E/S moze odbiegac
o <= 0,5 px (nazwa pliku i `request.bbox` niosa bbox sprzed snapu).
Wycinek w calosci nodata daje `Warning:` i kod 0, nie pozorna cisze.

Tor bbox CZ jest w bibliotece (`download/cz_cutout.py`):
`download_cz_cutout(bbox, *, output_dir, horizontal_crs, vertical_crs,
resolution, update, plan, parent_request, cache, on_notice, on_download)`
buduje providera (`create_dmr_provider`), normalizuje bbox, wyznacza slot
wersji (`bbox_slot`), pobiera (`fetch_version`, sygnal `none`), sprawdza
nodata i pisze sidecar wersji; `check_cz_cutout(...)` z ta sama selekcja
daje plan. Krok wykonania (`_run_cz_cutout`) jest wewnetrzny. Siatka wyniku startuje od zadanego bboxa
przeliczonego do ukladu wyniku, dokladnie jak w CLI przed 0.7.1;
wyrownania do siatki PL nie ma (osobny spec razem z R6). Wynik
`CzCutoutResult(file, all_nodata, stale)`: rastr bez ani jednego
waznego piksela powstaje, ma `all_nodata=True`, `extra.all_nodata: true`
w sidecarze (przy danych `false` — klucz jest zawsze) i `Notice`
`ALL_NODATA` (CLI: `Warning:`). Kontrola jest best-effort: nieczytelny plik daje
`all_nodata=False` (log debug), nigdy przerwania po udanym pobraniu.
Lokalna wersja (tryb domyslny i `upgrade`) zwraca `file.status ==
"local"` z flaga `all_nodata` z sidecara wersji, bez sieci; `force`
pobiera ponownie (ta sama tresc = `unchanged`). Nieudane pobranie nie
zostawia wersji ani pustego drzewa i przekazuje wyjatek dalej.

Wynik: dowiazanie `data/nmt/cz_dmr5g_<vcrs>/bbox/<coords>.tif` do wersji
w `versions/bbox/<RRRR-MM-DD>_<sha8>/`. Arkusze CZ (TM33, SM5) maja
od 0.8.0 publiczne API `download/cz_sheets.py` (`download_cz_sheet`/
`check_cz_sheet` -> `CzSheetResult`; ADR-037): ta sama tresc sidecara co
wczesniej w CLI (`mapname`, `cz_share`, `capability`, `horizontal_crs`),
SM5 z sygnalem `http` (`extra.http`), TM33 `none`.

### 4.6 Dyspozycja per kraj (`--country auto`)

Podzial na kraje jest w bibliotece (`download/countries.py`;
wywoluje go `download_data`, ADR-037): `countries_for_bbox` porownuje bbox
(w WGS84) z `CountryProfile.extent_wgs84`
kazdego kraju z rejestru. Obwiednie sa **prostokatami**, nie wielokatami
granic, wiec obszar w glebi jednego kraju rutynowo trafia takze do drugiego.
Konsekwencje: (1) obszar przecinajacy oba prostokaty pobiera sie z KAZDEGO
kraju — osobne pliki i sidecary, wspolny `parent_request`; wymaga to
`--cutout` (obszar CZ jest zawsze wycinkiem, ADR-038), wiec czesc PL jest
wtedy wycinkiem WCS; bez `--cutout` `ValidationError` z podpowiedzia
`--country pl` (arkusze PL); (2) na obszarze
spornym flaga bez odpowiednika czeskiego (`--product nmpt|orto`,
`--vertical-crs KRON86`, rozdzielczosc spoza rejestru CZ, np.
`--resolution 1m` albo `0.5m`, i kazde `--format`;
`download/area.py::pl_only_flags` czyta rejestry) ROZSTRZYGA kraj do `pl`
z komunikatem `Info:` zamiast przewracac zadanie; (3) porazka jednego kraju
przy sukcesie drugiego daje kod 0 i `Warning:` — kod 1 zostaje dla jawnego
`--country` i dla porazki wszystkich krajow. `Info:`/`Warning:` ida na stderr,
wiec `-q` ich nie tlumi. `--cutout` NIE rozstrzyga kraju w zadna strone,
bo od ADR-027 dziala po obu stronach granicy.

Czesc zadania dla kazdego kraju jest pod `auto` PRZYCINANA do jego
prostokata (`country_bbox`; komplet czesci dla `auto` daje
`split_bbox_by_country(bbox, cz_crs=)` — czesc CZ w `cz_crs`, czesc PL
w ukladzie bboxa). `country_bbox` zmienia tylko obciete krawedzie PL —
pozostale niosa oryginalne wspolrzedne; CZ pozostaje przeliczany
przez WGS84. Przed pobraniem `download_data` emituje `Notice`
(`AUTO_CLIPPED`, `AUTO_AREA_OUTSIDE`; CLI: `Info:`) o przycieciu oraz
o obszarze pozostawionym poza oboma prostokatami (takze naroznym).
Nazwa pliku i `request.bbox` niosa bbox przyciety, oryginal tylko
w `extra.parent_request`. Tryb listy PL (`--bbox` bez `--cutout`, tylko
obszar bez CZ) wyznacza arkusze z przycietego bboxa, a ich sidecary maja
`request.sheet` (oryginal: `extra.parent_request.bbox`). Przy geometrii
bez `--cutout`
arkusze PL wyznacza sama geometria (cala), wiec nie ma komunikatu
o przycieciu PL ani o obszarze poza prostokatami; czesc CZ nadal jest
przycinana i komunikowana. Jawny
`--country pl` nie przycina; bbox w calosci poza prostokatami =
`ValidationError` (CLI `Error:`, kod 1) bez sieci. Poza obwiednia CZ przy granicach
DE/SK/UA/BY/LT/RU `auto` odpytuje tylko PL; w prostokacie CZ
dochodzi CUZK nawet nad Polska/Saksonia, bo obwiednia nie jest
wielokatem granicy. Wynik calkowicie nodata (CZ albo wycinek PL
z pobranymi arkuszami) daje `Warning:` i kod 0. Sukces czesciowy
PL lub CZ pod `auto` daje `DataReport.ok = True` (kod 0), porazke drugiej
czesci w `failed` i `Notice` `AUTO_PARTIAL_SUCCESS`; `--resolution 1m`
rozstrzyga do PL. Uklad wysokosci i rozdzielczosc sa wymagane (0.8.0, bez
domyslnych); jedna wartosc dotyczy kazdego kraju zadania i musi byc dla
niego dostepna, rozne wartosci: `pl=..,cz=..` (biblioteka: slownik
`{"pl": ..., "cz": ...}`); kazdy kraj jest walidowany przed pierwszym
pobraniem.

Opcje kampanii i flagi roku (ADR-030/032; erraty Q9, N-3) dotycza
tylko arkuszy PL; `download_data` sprawdza wszystkie wejscia: zadanie bez PL (godlo CZ pod `cz`/`auto`, jawne
`--country cz`, obszar w calosci CZ pod `auto`) z `--all-campaigns` lub dowolna
flaga roku = `ValidationError` (`CZ (CUZK) nie ma kampanii -
--all-campaigns/--min-year/--max-year/--year dotycza tylko PL`), kod 1 bez
sieci. Obszar PL+CZ pod `auto` wymaga `--cutout`, a wycinek odrzuca te
flagi (4.3) - arkusze PL z kampaniami daje tylko `--country pl` (od
ADR-038; `Notice` `campaign_opts_pl_only` usuniety). Flagi roku nie
naleza do `pl_only_flags` i nie zwezaja `auto` do PL.

Styk PL/CZ zmierzony na zywo 2026-09-29 (dane wejsciowe do R6; raport:
`docs/research/2026-09-29-live-e2e-i-audyt-docs/L4-pogranicze-cz-report.md`; oba wycinki
w EPSG:2180): GUGiK wydaje dane ~200 m w glab CZ, CUZK ~118 m w glab PL, pas
wspolny ~310-350 m (Cieszyn, Karkonosze, Beskid Slaski, trojstyk PL-CZ-DE),
bez szczeliny tam, gdzie GUGiK ma produkt w danej rozdzielczosci (Karkonosze
5 m: brak arkuszy GUGiK — dziura 5,2 km² po stronie PL). Roznice wysokosci
PL - CZ (oba "EVRF2007": PL `EPSG:9651`, CZ `EPSG:5621`) w pasie wspolnym:
mediany -0,19..+0,14 m zaleznie od zbioru i spadku (trojstyk: 0,17 m),
koryto Olzy ~ -0,55 m (lustro wody); siatki PL (5 m: 5k + 2,5; 1 m: k + 0,5)
i CZ (warp kotwiczony w rogu NW zadania) nie sa wspolne.

### 4.7 LAZ (chmury punktow LIDAR, PL)

Przeplyw poza `DownloadManager` — jedno zadanie obszarowe daje wiele kafli.
Logika jest w bibliotece (`download/laz.py`, ADR-029; wzor `cutout.py`):
`download_laz_area(bbox, ...)` przyjmuje bbox w dowolnym obslugiwanym
ukladzie (przeliczenie do EPSG:2180 w bibliotece, `area.bbox_to_2180`),
`check_laz_area(...)` daje plan. Godlo (do 1:10000) i `--geometry`
sprowadza do bboxa `download_data`; CLI tylko wypisuje wynik.
Discovery idzie przez
**WFS** `GetFeature` (WMS skorowidzy LAZ zwraca 401 — ADR-021) na wspolnym
transporcie `WfsIndex` (`providers/pl/skorowidz_wfs.py`, od 0.8.0 — ten
sam klient co skorowidz NMT/NMPT i raport dostepnosci: stronicowanie po
`next`, kontrola `numberReturned`, blad = `DownloadError` "wynik bylby
niepelny", sekcja 4.1); uslugi i prefiks typow (`DanePomiaroweLidar
{EVRF2007,KRON86}`, `SkorowidzDanychPomiarowychLIDAR`) pochodza z rejestru
wariantow (`variants(product="laz")` -> `IndexRef`;
`GugikLazProvider.WFS_ENDPOINTS` usuniete w 0.8.0), a kafle
pobierane sa rownolegle. WFS `urn:ogc:def:crs:EPSG::2180` oczekuje
osi (N,E): bbox jest wysylany, a `gml:Envelope` i rama `msGeometry`
czytane w tym porzadku, potem kafle sa filtrowane rzeczywistym przecieciem.
GetCapabilities (`WfsIndex.feature_types`) ustala roczniki (bez zaszytej listy); jawny `--year`
nieobecny w usludze wysokosciowej = `DownloadError` z lista
dostepnych rocznikow, przed GetFeature;
przedzial bez rocznika uslugi rowniez daje `DownloadError`. Przy fladze
roku WFS odpytuje WSZYSTKIE roczniki dla referencji, przed pobraniem.
Jesli ktorykolwiek rocznik zawiedzie po ponowieniach, `select_tiles`
rzuca `DownloadError` zamiast zgadywac brak kafli. Gdy wszystkie
odpowiedza i nie ma zadnych kafli, `download_laz_area` rzuca
`NoCoverageError` (`Brak kafli LAZ dla podanego obszaru ...`).

**Flagi roku wspolne, `--min-density` tylko LAZ (ADR-032).**
`--year`/`--min-year`/`--max-year` dla NMT/NMPT/orto ida do
`DownloadManager` (4.1), dla LAZ do `download_laz_area`;
`--min-density` dla innych produktow = `Error:` przed siecia
(`_reject_laz_only_opts`). `--year` z dowolna granica roku =
`Error: --year wyklucza sie z --min-year/--max-year` przed siecia,
takze w LAZ. Zadanie wylacznie CZ z flagami roku = `Error: CZ (CUZK)
nie ma kampanii` (4.6). Wycinek `--cutout` z flaga roku = `Error:`
(4.3).

**Wybor kafli (ADR-029/032).** Domyslnie (bez granic roku) kafle sa wybierane
zachlannie od najnowszego `akt_rok` (w roku: nowsza `akt_data`): kafel
starszy jest pomijany, gdy jego czesc wspolna z obszarem zadania pokrywa
juz suma wybranych kafli — porownanie ram `msGeometry` w EPSG:2180,
kazda rama pokrycia powiekszona o 1 m (`COVERAGE_TOLERANCE_M`); kafel
wnoszacy niepokryty kawalek zostaje (caly — LAZ nie jest przycinany).
Dzieki temu PL-1992 i PL-2000 tego samego miejsca nie dubluja sie (w2:
2025/PL-1992 zamiast 2025 + 2022/PL-2000:S7). W przedziale lat ta
regula dziala na wybranych kaflach (jawne `newest` dozwolone).
`NIE`) i tylko rama albo tym samym godlem, nigdy obwiednia. Kafel, ktorego
rama nie przecina obszaru (przecina go tylko obwiednia), jest pomijany.
Pominiete kafle: `LazTileSelection.superseded` / `LazDownloadResult.superseded`
(kafel + kafle pokrywajace), w CLI `Info:` na stderr takze z `-q`.

Z flaga roku `select_tiles` sprawdza pokrycie kafli referencyjnych,
wybranych po WSZYSTKICH latach bez granic, kaflami z przedzialu
(po filtrze gestosci i pionu). Porownuje ramy, nie godla: PL-1992
i PL-2000 moga inaczej dzielic ten sam obszar. Niepokryta czesc
kafla referencji = `YearRangeError` przed pobraniem z godlem
referencji, jego rokiem/ukladem i latami kafli przecinajacych
niepokryty fragment; tolerancja 1 m jak przy zwyklym wyborze.
W obszarze w2 `--year 2022` pokrywaja referencje razem dwa kafle
PL-2000 (zaden sam), a `--year 2023` ten sam godlo. We Wroclawiu
(`6.150.13.16.4`) `--year 2025` to konflikt: rok 2025 ma tam tylko
dostawy `NIE`, ktore nie pokrywaja referencji 2024 (PL-1992); rok,
w ktorym niepokryty fragment przecinaja tylko dostawy `NIE`, ma w
komunikacie dopisek `(tylko arkusze niepelne)`. Fragment
bez kafli w ZADNYM roku pozostaje bez ostrzezenia.

Porazka pobrania choc jednego kafla trafia do `LazDownloadResult.failed`
(biblioteka nie rzuca); CLI konczy wtedy kodem 1 z `Error:`
i PELNA lista nieudanych kafli (jak `_finish_pl_sheets`; udane kafle
zostaja na dysku i przy ponowieniu bez `--force` sa pomijane).
Godlo kafla jest drobniejsze niz 1:10000 i NIE jest
parsowane — `FileStorage.get_raw_path(..., system=tile.system)` buduje z niego
sama hierarchie katalogow. Uklad poziomy jest ustalany **per kafel**
wlasnoscia `LazTile.system` (jedno zrodlo prawdy dla CLI i biblioteki, zn. 8
review max) z `uklad_xy` kafla, parserem `sources.registry.parse_pl_system`
wspolnym ze skorowidzem i sidecarem (`horizontal_crs_for_system`; review-1 D3):
`PL-1992` -> `1992`, `PL-2000:S5..S8` -> `2000`. Nierozpoznana wartosc (np.
`PL-2000` bez strefy) — kafel pominiety w discovery z ostrzezeniem w logu,
a `LazTile.system` recznie zbudowanego kafla rzuca `ValidationError` (dawniej
zgadywanie z formatu godla dawalo segment `pl_2000` z sidecarem EPSG:2180).
Uklad pionowy bierze sie z flagi CLI (biblioteka:
`FileStorage(vertical_crs=)`). Jedno zadanie moze wiec zapisac kafle do dwoch
segmentow naraz — `{system}` rozwiazuje sie per wywolanie `get_raw_path`,
jeden `FileStorage` wystarcza na cale zadanie. W trybie obszarowym
`--country auto` obszar siegajacy CZ konczy sie bledem z podpowiedzia
`--country pl` (LAZ dla CZ to etap 2).

**Kampanie LAZ (ADR-030/032).** Domyslnie
(rowniez z gorna granica) zachlanny wybor ADR-029 w przedziale.
`--all-campaigns` = wszystkie kafle z rama przecinajaca obszar
(`select_all_intersecting`), bez deduplikacji pokryciowej; kafel
przeciety tylko obwiednia WFS trafia do `superseded` z powodem
"outside". `--year Y` = przedzial `[Y, Y]`, `--min-year`/`--max-year`
sa domknietymi granicami `akt_rok`; `--year` z dowolna z nich =
blad w CLI (`ValidationError` w bibliotece). `download_laz_area`
i `select_tiles` przyjmuja `year=`, `min_year=`, `max_year=`.
Uklad LAZ bez zmian: bez `kampanie/` i dowiazan;
`request.campaigns` w sidecarze tylko dla `all`.

Wynik: `data/laz/pl_2000_evrf2007/6/162/34/02/3/<oryginalna_nazwa>.laz`
(+ `.meta.json` z `extra.tile_sheet`/`year`/`nominal_density`/`url`,
`extra.acquisition_date`/`full_sheet`, gdy znane, oraz
`extra.parent_request` w trybie `--bbox`/`--geometry`; `request`
niesie bbox, podane granice roku, `year` dla jednego roku
i `min_density`, gdy podane — E16).
`nominal_density` i filtr `--min-density` to wartosc NOMINALNA z WFS GUGiK
(`char_przestrz`); faktyczna gestosc kafla bywa kilkukrotnie wyzsza
(E2E 2026-10-06: ~119 pkt/m2 przy nominale 15).

### 4.8 Land cover i gleby (BDOT10k, CORINE, SoilGrids)

**Magazyn wersji (ADR-036 D29-D33, plan 3/3, od 0.8.0).** `LandCoverManager(
output_dir, provider, cache=True)` pisze WYLACZNIE do magazynu
`output_dir` (= `--output`; bez `output_path`, D32) w segmentach reguly 8
sekcji 3.3; wynik to `LandCoverResult(unit, file: VersionedFile | None,
raw, stale)` (`file` = `None` tylko z `plan=` dla pozycji spoza planu bez
lokalnej wersji). Opcje sa sprawdzane przed siecia: nieznana opcja (np.
`output_path`) = `TypeError`, brak wymaganej (`year`, `property`/`depth`/
`stat`) = `TypeError`, zla wartosc = `ValueError`. Polityka plikow jest
wspolna z innymi torami (`download/fetch.py`): `use_local` (decyzja bez
pobierania danych), pobranie do `versions/.incoming/`, `store_file`
(sha256 jednym odczytem, `commit_version`, sidecar wersji, hardlink).
Sygnal per kanal (`AccessChannel.update_signal`):

| Zrodlo / kanal | Sygnal | Etykieta wersji | Segment |
|---|---|---|---|
| SoilGrids WCS | `metadata`: `SoilGridsProvider.edition(property)` — pierwszy `ows:Title` GetCapabilities mapy wlasciwosci (`SoilGrids250m 2.0 - ...` -> `2.0`) | wydanie | `soil/global_soilgrids_<wl>_<gl>_<stat>` |
| CORINE CLMS (`uses_clms(year)`: token i rok w `CLMS_YEARS`) | `metadata`: `CorineProvider.edition(year)` — `characteristics_release_major_version` z `@search?UID=<uid>&fullobjects=1` (bez tokenu) | wydanie (`V2020_20u1`) | `landcover/eu_corine_<rok>` |
| CORINE podglad WMS (bez credentials; 1990 zawsze) | `none` | data pobrania | `landcover/eu_corine_<rok>_preview` (`.png`) |
| BDOT10k paczka powiatu | `none` | data pobrania | `landcover/pl_bdot10k_gpkg[_<warstwy>]`, `_shp`, `_gpkg_zip` |
| BDOT10k archiwum rocznikow (`year`, kanal `archive_unit_files`) | `none` | rocznik (`label_source="edition"`) | `landcover/pl_bdot10k_<gml\|shp>_<rok>` |

`metadata` (tabela decyzji 2 planu 3/3): wydanie jest pytane raz na plik
(`memoized_edition`) PRZED pobraniem — bez wydania nie powstaje wersja
(blad pliku, D30). Lokalna wersja z etykieta wydania: rowna = lokalna,
inna = domyslnie `newer=<wydanie>` (CLI: `dostepna nowsza ... (--upgrade)`),
`upgrade` pobiera; wydanie niedostepne = domyslnie `unverified="check_failed:
..."` (CLI `Warning:`), `upgrade`/`force` = blad. Wersja nie z wydania jest
nieporownywalna (`unverified="none"`). Ta sama tresc pod nowym wydaniem
= `relabeled` (D23). `none`: lokalna wersja niesprawdzona; naglowki HTTP
trafiaja do `extra.http`, ale nie sa sygnalem (ta sama tresc innego dnia
= `unchanged`). `check(...)` buduje plan
`kartograf-plan/1` (tor `landcover`, `unit` = TERYT / wspolrzedne bbox /
godlo) bez pobierania danych (dozwolone: GetCapabilities, katalog CLMS,
PRG); `download(..., update="upgrade", plan=)` wykonuje tylko pozycje
planu, zmienione od planu wracaja w `stale`.

Parametry tresci (`_content_params`, U3) niosa segment i `request`
sidecara (`property`/`depth`/`stat`, `year`, `format`, `layers`) obok
wyboru (`teryt` / `bbox`+`bbox_crs` / `sheet` kanoniczne); `nodata` GeoTIFF
czytane z pliku (`null`, gdy brak tagu). Sidecar wersji SoilGrids/CORINE CLMS
ma `extra.edition` (`id`, `url`, `title` / `dataset_uid`). Podglad
CORINE: `horizontal_crs` uslugi WMS (EPSG:3857, 1990 EPSG:4326),
`extra.fallback = "wms_png"`, `extra.note = "podglad WMS, nie dane"`.

**BDOT10k z wielu powiatow (od 0.7.1, A2).** Pakiet BDOT10k jest zawsze
pakietem CALEGO powiatu, wiec sciezka i `request` sidecara opisuja
tresc: `landcover/pl_bdot10k_<format>[_<warstwy>]/teryt/<TERYT>.<ext>`,
`request = {teryt, format[, layers]}` — takze przy zadaniu przez
`--bbox`/`--sheet`/`--geometry`.
Obszar zadania idzie do `extra.parent_request`: `{bbox, bbox_crs,
countries: ["PL"]}` albo `{sheet, countries: ["PL"]}`.
`LandCoverManager.download(teryt=|sheet=|bbox=|geometry=, layer=, update=,
plan=, workers=, on_notice=, format=, layers=, keep_raw=, timeout=)` dla
obszaru BDOT10k pyta PRG (`Bdot10kProvider.teryts_for_area` ->
`discover_teryts_for_bbox`, obszar w dowolnym obslugiwanym ukladzie) i
pobiera pakiet KAZDEGO powiatu przecinajacego obszar, w kolejnosci kodow;
zawsze wynik `LandCoverAreaResult(files, failed, stale, notices, ok)`
(`teryt=` = jeden element; ADR-037 S3) — blad pakietu jednego
powiatu (`DownloadError`) trafia do `failed` (`LandCoverFailure(unit,
error)`), pozostale powiaty sa pobierane (spec 4.2); brak powiatu =
`NoCoverageError`, awaria PRG = `DownloadError`; `workers` pobiera powiaty
rownolegle. CLI `landcover download` (grupa `landcover`, ADR-039) jest jednym wywolaniem `download`
(flagi `--layers`, `--keep-raw`, `--bbox-crs`, `--workers`, `--quiet`),
wypisuje linie statusu, `Error: <TERYT>: ...` per powiat, podsumowanie
i konczy kodem 1, gdy `ok` jest `False`. `Bdot10kProvider.download_by_bbox`/
`download_by_sheet` (plik poza magazynem) pobieraja JEDEN powiat
(`_single_teryt`): obszar z kilku powiatow konczy sie `ValidationError`
z lista kodow i wskazaniem `LandCoverManager.download`. Opcja `timeout`
(provider: domyslnie 120 s; menedzer: gdy nie podana, PRG 30 s) dziala od
0.7.2 takze na zapytanie PRG, nie tylko na pobranie paczki. `layers=` (kody
4-literowe, np. `PTWP`, `SWRS`; tylko GPKG) zostawia w scalonym GPKG
wylacznie pliki `__OT_<kod>_*` pakietu — brakujaca warstwa to
`DownloadError`, zly kod `ValidationError` przed siecia; plik z filtrem
nosi token warstw w segmencie, bo nie jest juz pelnym pakietem. Scalanie
pakietu (`_merge_gpkg_files`) konczy sie `DownloadError`, gdy nazwa
tabeli powtarza sie w dwoch plikach pakietu (dotad druga kopia byla po
cichu pomijana); w prawdziwej paczce (63 pliki `..._<TERYT>__OT_<KOD>_<A|L|P>.gpkg`,
po jednej tabeli) duplikatow nie ma.

BDOT10k GPKG: archiwum ZIP z GUGiK jest rozpakowywane, a warstwy scalane
w jeden GeoPackage w LOKALNYM katalogu tymczasowym (`tempfile`); do
`versions/.incoming/` magazynu trafia gotowy plik (kopia jako `<nazwa>.gpkg.<pid>_<tid>.tmp` + `os.replace`).
Powod: SQLite na udzialach CIFS/SMB bez blokad zakresow bajtow konczyl
scalanie bledem `database is locked` (`Bdot10kProvider._merge_gpkg_files`).

**Pochodzenie pakietu BDOT10k w sidecarze (A4, decyzja 9 planu 3/3).**
Sidecar wersji pliku BDOT10k ma `extra.source = {url, teryt, format}` (URL
paczki OpenData) oraz `extra.http = {etag, last_modified, content_length}` —
naglowki odpowiedzi GUGiK tak, jak przyszly (serwer nie podaje `ETag` ani
`Last-Modified`, tylko `Content-Length`; kanal `none`). `keep_raw=True`
(tylko GPKG — przy SHP `ValidationError`) zapisuje nietkniete archiwum
GUGiK jako WLASNA wersje w `landcover/pl_bdot10k_gpkg_zip/teryt/<T>.zip`
(pelny pakiet: jeden plik dla kazdego filtra `layers=`, `request` bez
`layers`); paczka jest pobierana, gdy KTORYKOLWIEK z plikow (GPKG, ZIP)
wymaga pobrania, oba pliki ida przez `store_file` (ta sama tresc =
`unchanged`): najpierw ZIP, potem GPKG z `extra.source_files = [{name:
"package", file: <sciezka wersji ZIP wzgledem --output>, sha256}]`.
Pliki paczki powstaja w `.incoming/` wlasnych segmentow; blad pobrania,
rozpakowania albo zapisu archiwum nie zostawia wersji ani katalogu
roboczego, poprzednie wersje i dowiazania zostaja. `extra.parent_request`
(obszar zadania) obok `source` i `http`. Powtarzalnosc: GPKG scalony
z tej samej paczki ma ten sam sha256 (live 2026-10-12: `--force` = `bez
zmian`).

**Archiwum rocznikow BDOT10k (ADR-042 D10-D11, od 0.8.0).**
`LandCoverManager(..., "bdot10k").download(..., year=R, format="GML"|"SHP")`
(CLI `landcover download --source bdot10k --year R --format GML|SHP`)
pobiera roczniki 2014-2025 (stan z poczatku roku) z kanalu
`archive_unit_files` deskryptora `pl.gugik.bdot10k`: paczka ZIP powiatu
zapisywana 1:1, bez scalania GPKG, w
`landcover/pl_bdot10k_<gml|shp>_<rok>/teryt/<T>.zip`, etykieta = rok,
`request = {teryt, format, year}`, sygnal `none`. Walidacja bez sieci
w `_check_options` (to samo miejsce dla `download`, `check`
i `validate_request`): wariant przez `transport.unit_package.select_variant`
(brak `format` albo `GPKG` = `ValidationError` z lista `GML, SHP`, rok
spoza listy = lista lat), `layers`/`keep_raw` z `year` = blad, a `GML`
bez `year` = blad z podpowiedzia. Pobranie idzie zadaniami jednostek
orkiestratora kolekcji (`package_job`/`run_job`/`inspect_job`, sekcja
4.10) z sesja HTTP i opcja `timeout` dostawcy BDOT10k
(`Bdot10kProvider.session()`), na torze planu `landcover`. Obszar =
powiaty z PRG jak dla biezacych paczek (`extra.parent_request`, blad
powiatu w `failed`); `teryt` bez paczki w roczniku (HTTP 404, np. po
zmianie kodu TERYT) = `NoCoverageError`. Identyczne roczniki tego samego
powiatu i formatu zajmuja miejsce raz (D7: `relabeled`, hardlink; live
2026-10-15: SHP 2023 powiatu 1261 = 2022).

`HSGCalculator(output_dir, provider=None, cache=True)` (`hydrology/hsg.py`, D33):
`calculate_hsg(*, sheet|bbox|geometry, layer, depth, update, plan,
on_notice)` / `check_hsg(...)` (ADR-037 S4, statystyka zawsze `mean`)
liczy grupy glebowe z wersji SoilGrids `clay`/`sand`/`silt` w tym samym
magazynie (`LandCoverManager(output_dir, provider)`, ten sam wybor i
`update`; blad wejscia = wyjatek, HSG nie powstaje) wg kanonicznego
trojkata USDA (ADR-025). Wynik `HsgResult(unit, file, inputs, stale,
notices, ok)` w
`hsg/global_soilgrids_<gl>_<stat>/` (`bbox/<coords>` albo hierarchia
godla). Wersja HSG, ktorej `extra.source_files` ma te same trzy sha256
wejsc (kolejnosc clay, sand, silt), jest uzywana ponownie (`reused`,
bez liczenia, dowiazanie na nia); inaczej klasyfikacja do `.incoming/`
i `store_file` z etykieta = posortowane unikalne etykiety wejsc laczone `+`
(`label_source = "edition"`). `--force` dotyczy wejsc. Sidecar wersji:
deskryptor `global.isric.soilgrids`, `capability="bbox_raster"`, `request`
= wybor (`bbox`+`bbox_crs` albo `sheet`), `horizontal_crs` = uklad rastra,
`nodata: 0`, `extra` = `{derived: "hsg", depth, stat, classes, source_layers,
source_files: [{name, file (sciezka wersji wejscia), sha256, label}]}`.
`check_hsg(...)` = 3 pozycje `landcover` + pozycja `hsg`
(`current`, gdy jest wersja HSG z sha256 biezacych lokalnych wejsc i kazde
wejscie jest `current`; wejscie `check_failed` = `check_failed`; inaczej
`missing`; nigdy `newer`). Ograniczenie: HSG o identycznej tresci z innych
wejsc to istniejaca wersja z pierwszymi wejsciami w `source_files` — takie
wejscia licza HSG przy kazdym uruchomieniu (wersje sa niezmienne).

`hsg_from_rasters(clay, sand, silt, *, bbox, crs, pixel_m, output_path)`
(od 0.7.1, A8) liczy HSG z gotowych rastrow (g/kg, SoilGrids) bez pobierania
i bez wartosci domyslnych: kazde wejscie jest reprojektowane przypieta
operacja (`CONTENT_POLICY`, bilinear; `warp_to_grid`) na siatke `crs`/`pixel_m`
zaczepiona w `bbox` (przeliczonym do `crs`), a klasyfikacja (`_classify_hsg`)
i zapis GeoTIFF (`_write_hsg_geotiff`) sa wspolne z
`HSGCalculator.calculate_hsg`. Nodata wejscia pochodzi wylacznie z
jego tagu (brak tagu = brak wartosci nodata, bez domyslnego `-32768`); piksele
poza zasiegiem wejscia oraz trojki zerowe daja `0`. Sidecar jak wyzej
(`extra.source_layers` = `["clay", "sand", "silt"]`, ten sam typ), plus
`extra.source_files` = lista `{name, file, sha256}` (skrot pliku wejsciowego,
`file_digest`), bez `depth`/`stat` (nie sa znane), a `request` niesie
siatke (`bbox` w `crs`).

**Odkrywanie TERYT (od 0.7.1).** `providers/pl/prg.py` to jedyne miejsce,
ktore pyta, w jakich powiatach lezy obszar albo punkt:
`discover_teryts_for_bbox(bbox, *, session, cache, timeout)` zwraca
posortowane, unikalne 4-cyfrowe kody powiatow, a `teryt_for_point(x, y,
crs, ...)` kod powiatu punktu (`None` = brak powiatu: morze, za granica;
punkt na granicy dwoch powiatow = nizszy kod). Zrodlo: WFS PRG GUGiK
(WFS 2.0.0, MapServer), warstwa `ms:A02_Granice_powiatow`, atrybut
`JPT_KOD_JE`. Obszar w dowolnym obslugiwanym ukladzie jest przeliczany do
EPSG:2180 ta sama regula co wycinek PL (`download.cutout.bbox_to_2180`),
a `BBOX` idzie w kolejnosci osi (N,E) z `urn:ogc:def:crs:EPSG::2180`,
rozszerzony na zewnatrz do pelnych milimetrow (od 0.7.2).
Filtr dziala na GEOMETRII powiatu, nie na jego obwiedni (sprawdzone na
zywo 2026-10-08; surowe odpowiedzi: `tests/fixtures/gugik_prg/`). Pusta
lista tylko z poprawnej odpowiedzi bez obiektow; blad HTTP (po wspolnej
polityce ponowien `get_with_retry`), `ows:ExceptionReport`, odpowiedz nie-XML,
kod spoza 4 cyfr i lista obcieta stronicowaniem = `DownloadError`.
Obciecie: `numberReturned < numberMatched`, albo `numberMatched`
nieliczbowe (MapServer: `unknown`) przy pelnej stronie, albo atrybut `next`
kolekcji — tak wyglada prawdziwa strona MapServera (`unknown` + `next`).
Odpowiedz, w ktorej liczbowe `numberReturned` rozni sie od liczby
odczytanych kodow (obiekt bez `JPT_KOD_JE`), to tez `DownloadError` (od 0.7.2).
Odpowiedzi trafiaja do `MetadataCache`: obszar (EPSG:2180) -> lista kodow
w `teryt_bbox_cache` (TTL jak pozostale tabele, takze pusta lista), punkt
-> kod w `teryt_cache`; `kartograf cache stats` liczy oba w `Wpisy TERYT`.

### 4.9 Raport dostepnosci (`elevation availability`, ADR-041)

`check_availability(*, product, country=None, sheet=None, bbox=None,
geometry=None, layer=None, year=None, min_year=None, max_year=None,
cache=True, force=False, on_notice=None) -> AvailabilityReport`
(`download/availability.py`) odpowiada, dla jakich lat, ukladow arkuszy,
rozdzielczosci, ukladow wysokosci i formatow obszar ma komplet PELNYCH
arkuszy NMT/NMPT (LAZ: kafli) wg skorowidza GUGiK — bez pobierania
danych. CLI `kartograf elevation availability` (`cli/availability_cmd.py`)
tylko tlumaczy flagi (`--bbox` -> `BBox`, `--force`) i drukuje wynik:
tabela (kombinacje od najnowszego roku), `--details` (godla arkuszy
niepelnych, lad bez arkuszy, polecenia kazdej kombinacji), stopka
z najnowsza kompletna kombinacja, `--json` = dokladnie
`AvailabilityReport.to_json()`. Raport nie jest komenda danych projektu
(brak `_task`; `project add` go odrzuca). Przyklady i wydruki na zywo:
USAGE 1.7.

**Walidacja przed siecia** (teksty jak `download_data`): jeden wybor
obszaru; `product` z `AVAILABILITY_PRODUCTS` (`nmt`, `nmpt`, `laz`);
`sheet` tylko godlo PL (PL-1992/PL-2000, kraj z godla); `bbox`/`geometry`
wymagaja `country`; `country` z `AVAILABILITY_COUNTRIES` (dzis `pl`;
plan B dopisze `cz` i `auto` bez zmiany ksztaltu raportu); granice lat
jak w pobieraniu (`year` = `min_year` = `max_year`).

**Algorytm:**

1. **Obszar** -> wypukle wielokaty (E, N) w EPSG:2180 — ten sam obszar,
   ktory pokrywa pobranie tego wyboru: NMT/NMPT `sheet` = rama godla
   (`sheet_frame_2180`: narozniki w ukladzie godla, krawedzie zageszczone;
   rama PL-2000 nie jest prostokatem w EPSG:2180), `bbox` = obwiednia
   `bbox_to_2180`, `geometry` = obwiednie obiektow warstwy
   (`read_feature_bboxes`, jak arkusze `download_data`); LAZ = obwiednia
   ramy arkusza albo calej geometrii (jak `download_laz_area`).
2. **Uslugi i typy:** uslugi WFS produktu z rejestru (`variants(product=)`
   -> `IndexRef`, jedna na uklad wysokosci), ich typy roczne
   (`WfsIndex.feature_types`) i wybor typow z zakresu lat; zaden typ
   w zakresie = `ValidationError` z rocznikami per uklad.
3. **Rekordy:** jeden `WfsIndex.features(obwiednia, typy)` na usluge
   (wszystkie strony; reguly i bledy jak w 4.1) — ten sam klient i ten
   sam parser (`parse_index_feature`; LAZ: `laz_tile`) co pobieranie,
   plus obrys `msGeometry` (`feature_footprint`).
4. **Lad:** maska PRG obwiedni (`fetch_land_mask`: `A00` minus `W02`
   i `W03`, jak wycinek 4.3).
5. **Kombinacje** (`_group`): rekord nalezy do obszaru, gdy jego rama
   przecina obszar o wiecej niz pasek krawedzi (`overlaps_area`, regula
   arkuszy archiwow z 4.2). Wariant rekordu = `source_format` (format i
   URL) + etykieta `char_przestrz` + uklad wysokosci uslugi ->
   `ProductVariant` rejestru; klucz kombinacji NMT/NMPT: (rok typu,
   uklad PL-1992/PL-2000, deskryptor wariantu = format i etykieta, uklad
   wysokosci); LAZ: (rok, uklad, uklad wysokosci). Archiwa z rejestru sa
   kombinacjami jak siatki. Rekordy bez wariantu (format niezgodny z URL,
   format lub wariant spoza rejestru, godlo spoza `SheetParser` — np.
   8-czlonowe godla ASCII NMT 10 m i czesci ASC 1 m — brak URL `https`
   albo ukladu) nie sa kombinacja: jedna `Notice("info",
   INDEX_UNSUPPORTED, ...)` (`index_unsupported`) z formatem,
   rozdzielczoscia, ukladem wysokosci, latami, liczba arkuszy i powodem.
6. **Pomiar** (`_measure`): siatka 1 m wyrownana do pelnych metrow
   obwiedni, srodki pikseli (`rasterize`, `all_touched=False`), pasy
   wierszy po 4 Mpx (`_STRIP_PX`, jak `LandMask.apply`); w kazdym pasie
   klasy maski z `LandMask.burn`. `area_m2` = piksele obszaru w kraju,
   `land_m2` = piksele ladu (1 px = 1 m2). `target` = obszar & lad; dla
   `sheet` NMT/NMPT bez pasa `EDGE_TOLERANCE_M` = 1 m przy ramie
   (`_inner`: rama liczona z godla rozni sie od ramy GUGiK o centymetry),
   `bbox`/`geometry` mierzone dokladnie. Per kombinacja: piksele
   `target` poza suma obrysow arkuszy z rekordem TAK (`missing`) i poza
   obrysami wszystkich arkuszy kombinacji (`uncovered`). `complete` <=>
   `missing == 0`; `uncovered_m2` = `uncovered`; bez progu.
7. **Wynik:** `AvailabilityCombination` z `source` (klucz deskryptora),
   `year`, `acquisition_dates`/`published` (min/max `akt_data`/
   `dt_pzgik`), `campaigns` (`nr_zglosz`), `horizontal`, `resolution`
   (etykieta albo `None`), `vertical_crs`, `format`, `densities`
   (gestosci nominalne LAZ), `complete`, `sheets_full` (arkusz z co
   najmniej jednym rekordem TAK kombinacji), `sheets_partial` (tylko NIE),
   `uncovered`, `uncovered_m2`, `download_hint`; `sheets_missing`
   i `size_bytes` to pola CZ (plan B; PL puste/`None`). Kolejnosc: rok
   malejaco, uklad, rozdzielczosc, uklad wysokosci, format (kolejnosc
   `FORMATS`). `AvailabilityReport(request, checked_at, areas, combinations,
   notices, ok, schema="kartograf-availability/1")`; `areas` =
   `AvailabilityArea(country, crs, bounds, area_m2, land_m2)`;
   `checked_at` z `kartograf._clock`; `ok` = `False` tylko, gdy czesci
   zadania nie dalo sie sprawdzic (plan B, `auto`) — w PL zawsze `True`.
   `to_json()` = `json.dumps(asdict(...), ensure_ascii=False, indent=2) + "\n"`
   (jak `UpdatePlan.to_json`).

**Podpowiedz pobrania** (`_download_hint`): krotka polecen do wklejenia po
`kartograf ` albo po `kartograf project add NAZWA ` — bez `--output`
(magazyn pochodzi z `--output` uzytkownika albo z projektu, ADR-040).
Obszar jak w zadaniu (`--country pl --bbox ... [--bbox-crs]` albo
`--geometry PLIK [--layer]` + `--sheet-system`; `--sheet` — samo godlo,
gdy jego pobranie siega arkuszy kombinacji, inaczej po poleceniu na
arkusz), dla siatek PL-2000 po jednym poleceniu na skale arkuszy
(`--scale`), wariant (`--format` dla archiwow, `--resolution`, gdy
wariant ma etykiete, `--vertical-crs`), `--year`, a `--full-sheet`, gdy
w ktoryms arkuszu najnowszy rekord roku jest NIE, a pelny rekord tego
roku istnieje. LAZ: obszar + `--vertical-crs` + `--year`. Polecenie
wybiera dokladnie arkusze kombinacji (test
`test_report_sheets_equal_download_selection`).

**Cache:** tabela `index_area_cache` w `MetadataCache`
(`get_index_area`/`set_index_area`, payload JSON, TTL jak rekordy —
`DEFAULT_TTL_SECONDS`, 7 dni): klucze `wfs-types|<endpoint>` (typy roczne
uslugi), `wfs|<endpoint>|<typy>|<obwiednia w mm>` (rekordy obwiedni
z obrysami) i `prg|<obwiednia w mm>` (maska ladu). Cache otwiera
`open_cache(cache, force=force)`; `force=True` (CLI `--force`) pomija
odczyt i nadpisuje wpisy. Ponowny raport tego samego obszaru nie pyta
sieci (pomiar 2026-10-15, 16 km2: ok. 5–7 s z siecia, 0,6–1,5 s
z cache); `kartograf cache stats` liczy wpisy w `Wpisy obszarow
skorowidza`.

**Bledy:** awaria uslugi skorowidza albo PRG = `DownloadError` (CLI
`Error:`, kod 1), nigdy pusty raport; pusta, poprawna odpowiedz = raport
bez kombinacji (CLI: `Brak arkuszy ... dla obszaru w skorowidzu GUGiK`,
kod 0). Raport nie prosi o zaden plik danych
(`test_availability_never_downloads`: atrapa sesji odrzuca kazdy URL
spoza skorowidza i PRG). Zgodnosc CLI = API: `--json` daje ten sam tekst
co `check_availability(...).to_json()` z tym samym cache.

### 4.10 Kolekcje: paczki jednostek i obiekty obszaru (ADR-042)

**Komenda w bibliotece.** `kartograf boundaries|cadastre|models3d download`
= `download_collection(...)`/`check_collection(...)`
(`download/collections.py`); CLI tylko tlumaczy flagi
(`cli/collection_cmd.py::collection_task` - to samo dla `_handler`
i `_task` projektu) i wypisuje wynik, a wspolny ksztalt komend trzech grup
jest w `cli/groups/_collection.py` (teksty `--help` z biblioteki:
`collection_product_choices`, `collection_level_choices`,
`collection_variant_choices`). `validate_collection_request` sprawdza caly
wybor BEZ sieci i jest jedynym miejscem regul (wolaja ja obie funkcje
i pozycje projektu): wspolrzedne bboxa, dokladnie jeden wybor (`teryt`,
`sheet`, `bbox`, `geometry`, `whole_country`), produkt z rejestru, kraj
(`pl`/`cz`/`auto` wymagany z obszarem; `whole_country` tylko `pl`/`cz`;
z `sheet` z godla; z `teryt` tylko `pl`), kanal dla rodzaju wyboru, wariant
(`lod`, `year`) i poziom (`level`, z `auto` per kraj), `horizontal_crs`
rowny ukladowi pliku. Blad podaje flagi CLI i wybory, ktore produkt ma
(np. `--teryt 1261: admin nie ma paczek powiatow; dostepne: ...`).

**Rodzaj wyboru wyznacza kanal (D2).**

| Wybor | Kanal | Jednostki | Plik (regula 9 sekcji 3.3) |
|---|---|---|---|
| `teryt` (2 cyfry = woj., 4 = powiat; PL) | `unit_package` tej jednostki | `[teryt]` | `teryt/<T>` |
| obszar produktu z kanalem `feature_bbox` | `feature_bbox` | jeden obszar w ukladzie natywnym uslugi | `bbox/<coords>.gpkg` |
| obszar produktu bez `feature_bbox` | `unit_package` powiatu | powiaty z PRG (`discover_teryts_for_bbox`, cache metadanych; `Notice` `unit_list`) | `teryt/<T>` kazdego powiatu |
| `whole_country` | `unit_package` jednostki `country` | `pl` (plan D: `cz`) | `country/<kod>` |

Obszar: `bbox` w ukladzie z listy `--bbox-crs`, `sheet` = zasieg godla PL
(EPSG:2180), `geometry` = obwiednia obiektow pliku (`--layer`). Pod
`country="auto"` obszar dzielony jest na kraje jak w `download_data`
(sekcja 4.6) i zawezany do krajow, w ktorych produkt istnieje (`Notice`
`auto_narrowed_to_pl`/`auto_narrowed_to_cz`). Obszar przeliczony do ukladu
natywnego uslugi (`transform_bbox`; uklady czeskie - operacja przypieta)
albo pochodzacy z arkusza/geometrii/`auto` daje `extra.parent_request`
(sekcja 3.4); paczki powiatow obszaru maja je zawsze. Plik krajowy:
najpierw `HEAD` i `Notice` `whole_country_size` (`warning`: bajty z
`Content-Length` albo "rozmiar nieznany"), potem transfer (K7).

**Zadania jednostek.** Kazdy plik to `UnitJob` (slot, `request` sidecara,
zrodlo): `package_job` (paczka jednostki albo plik krajowy) albo zadanie
obiektow obszaru. `run_job` = `fetch_version` slotu (polityka
`use_local`/`store_file`, sekcja 3.3 regula 6; tryby `update`),
`inspect_job` = pozycja planu `kartograf-plan/1` bez pobierania danych
(tor `collection`, `unit` = TERYT / wspolrzedne `_` / `pl`). Blad jednostki
trafia do `CollectionReport.failed` jako `UnitFailure(unit, country, error,
kind)` (`no_coverage` dla `NoCoverageError`, `download` dla
`DownloadError`), pozostale jednostki dzialaja dalej (`workers` =
`ThreadPoolExecutor`, sesja HTTP per watek). Wynik: `CollectionReport(files,
failed, stale, notices, ok)`, `ok` = brak bledow i nieaktualnych pozycji
planu. Czasy: `SERVICE_TIMEOUT` 60 s (zapytanie i strona uslugi),
`PACKAGE_TIMEOUT` 120 s (paczka), `PROBE_TIMEOUT` 30 s (`HEAD`, zapytanie
PRG). `LandCoverManager` uzywa tych samych `package_job`/`run_job`/
`inspect_job` dla archiwum BDOT10k (sekcja 4.8).

**Silnik `unit_package` (`transport/unit_package.py`).**
`select_variant(params, **choice)` wybiera opublikowany wariant bez sieci:
brak wartosci przy kilku wariantach albo wartosc nieopublikowana =
`ValidationError` z lista dozwolonych; jedyny wariant mozna pominac,
a podany musi byc rowny opublikowanemu (K8). `package_url` wypelnia
`{teryt}`/`{woj}`. `fetch_package` pobiera atomowo (`download_to`,
wspolna polityka ponowien), odrzuca dokument HTML/XML przy HTTP 200,
porownuje rozmiar z `Content-Length` (przerwany transfer = `DownloadError`),
czyta centralny katalog ZIP, wymaga czlonow `members` wariantu, a przy
`unpack` rozpakowuje strumieniowo DOKLADNIE jeden czlon o tym sufiksie
(CRC sprawdza `zipfile`). HTTP 404 = `NoCoverageError` (zrodlo nie
publikuje paczki jednostki: LoD2 poza pokryciem, kod TERYT zmieniony),
kazdy inny blad = `DownloadError`; paczka nigdy nie lezy w pamieci, a blad
nie zostawia pliku wyniku.

**Silnik `feature_bbox` (`transport/feature_bbox.py`, D3/D4).** Metadane
uslugi sa pobierane swiezo raz na pobranie, bez cache metadanych: WFS
`GetCapabilities` (kazda warstwa istnieje, DefaultCRS ma kod EPSG
`native_crs` - porownanie po kodzie, nie po zapisie URN/URL; `CountDefault`
nie mniejszy niz `page_size`) i `DescribeFeatureType` warstwy (XSD dla
GDAL); ArcGIS `/<id>?f=json` (uklad warstwy, pola identyfikatora
i kolejnosci, `maxRecordCount`). Rozbieznosc = `DownloadError`, bez
podmiany ukladu. Liczba obiektow N: WFS `RESULTTYPE=hits`
(`numberMatched="unknown"` = `DownloadError`), ArcGIS `returnCountOnly`;
N = 0 we wszystkich warstwach = `NoCoverageError` (bez pliku), pusta
warstwa obok niepustych = warstwa ze schematem bez obiektow. Strony sa
pobierane po pozycji (`STARTINDEX`/`COUNT`; ArcGIS `resultOffset`/
`resultRecordCount` z `orderByFields`) od 0 co `page_size`, a linki `next`
sa ignorowane (MapServer gubi je na stronach srodkowych, GeoServer daje je
na ostatniej). Petla konczy sie, gdy unikalnych identyfikatorow jest N; za
N zaplanowanymi pozycjami idzie dalej tylko, gdy poprzednia strona byla
pelna i dodala nowe identyfikatory - MapServer powtarza obiekt na granicy
stron (PRG A03, `hits` 39, `COUNT=13`: 39. obiekt dopiero na
`STARTINDEX=39`). Krotka strona przy mniej niz N unikalnych, strona za N
bez nowych identyfikatorow albo wiecej niz N unikalnych = `DownloadError`;
HTML, `ows:ExceptionReport` albo JSON `error` przy HTTP 200 tez. BBOX WFS:
`<a>,<b>,<c>,<d>,urn:ogc:def:crs:EPSG::<kod>` w kolejnosci `axis_order`
(GUGiK EPSG:2180 `yx` = N,E; CUZK EPSG:5514 `xy` = X,Y - obie zgodne
z EPSG); zamiana osi daje pusty wynik BEZ bledu, dlatego kolejnosc ma test
na prawdziwej odpowiedzi uslugi. `SRSNAME` = ten sam URN; koperta ArcGIS
zawsze x,y (`inSR`/`outSR` natywny). Wspolrzedne sa zaokraglane NA
ZEWNATRZ do milimetra. Strony trafiaja na dysk
(`<pages_dir>/<warstwa>/<start>.gml|.json`) w miare naplywu - w pamieci
jedna strona naraz.

**Zapis GPKG (`transform/gpkg.py`, D5).** `write_gpkg` czyta strony przez
GDAL (`pyogrio`): GML z `XSD=<DescribeFeatureType>` (te same typy pol na
kazdej stronie), `WRITE_GFS=NO`, `DOWNLOAD_SCHEMA=NO`
i `GML_FETCH_ALL_GEOMETRIES=YES` (obiekt wieloczesciowy EGiB to powtorzone
`<ms:geom>`; bez tej opcji GDAL zostawia ostatnia czesc), GeoJSON ArcGIS
z typami pol z `fields` warstwy. Identyczny duplikat (pola poza
`drop_fields` i bajty geometrii) jest pomijany, ten sam identyfikator
z inna trescia = `DownloadError`, liczba unikalnych obiektow inna niz N =
`DownloadError`. Wynik: warstwa GPKG na warstwe zrodla (`FeatureLayer.name`),
obiekty w kolejnosci `id_field`, pelne geometrie obiektow przecinajacych
obszar (bez przycinania, `promote_to_multi`), uklad `native_crs`, pola
`drop_fields` poza plikiem (wartosci w sidecarze
`extra.source.dropped_fields`, sekcja 3.2). Staly `OGR_CURRENT_DATE` -
te same strony daja te same bajty w obrebie jednej wersji GDAL (live
2026-10-15: `--force` gmin PRG = `bez zmian`). Opcje GDAL sa globalne dla
procesu, wiec jedna blokada serializuje skonfigurowana prace modulu
(rownolegle zadania). Zapis trzyma obiekty jednej warstwy w pamieci (obszar
gminy, dzielnicy - tysiace obiektow; bardzo duze obszary - patrz USAGE 7).
GPKG powstaje w lokalnym katalogu tymczasowym (SQLite nie pisze na
wolumenie sieciowym bez blokad), potem trafia do `versions/.incoming/`
magazynu.

**Magazyn, sygnaly i etykiety (D6, D7).** Sygnal = `update_signal` kanalu;
wszystkie kanaly kolekcji PL maja `none` (GUGiK nie podaje `ETag` ani
`Last-Modified`, wynik WFS to migawka): lokalna wersja jest uzywana bez
zapytan, `--check-updates` = `unverifiable` (CLI: `nie da sie sprawdzic
bez pobrania`), nowa tresc przynosi tylko `--force` (ta sama tresc =
`unchanged`, inna = nowa wersja). Etykieta = `edition` wariantu (rocznik
BDOT10k, rok modeli 3D; `label_source="edition"`) albo data pobrania (PRG,
EGiB). Wydania tej samej tresci - warianty rozniace sie tylko wartoscia
rowna wydaniu (`year`), przy tym samym formacie i LoD - to sloty pokrewne
(`FileSlot.related_roots`): identyczny sha256 w innym wydaniu tej samej
jednostki = hardlink do istniejacych danych, status `relabeled`
(`same_as` = etykieta znalezionej wersji).

---

## 5. Jak dodac nowe zrodlo albo nowy kraj

Checklist na przykladzie DE (Brandenburgia, DGM1):

1. **Deskryptor** w `kartograf/sources/registry.py`: `key="de.bb.dgm1"`,
   `country="DE"`, `product="nmt"`, kanaly (`AccessChannel` z transportem,
   ukladami, `capabilities`, `endpoint`), licencja,
   `storage_subdir="nmt/de_bb_dgm1_{vcrs}"`, `default_extension`. Sam ten
   wpis wystarcza, zeby pliki wyladowaly we wlasciwym katalogu — **zero zmian
   w kodzie sciezek**. Jesli kraj wnosi nowy uklad pionowy, dopisz go do
   `_VERTICAL_CRS_CODES` (a przy rodzinie/realizacji takze do
   `_VERTICAL_FAMILY`).
2. **`CountryProfile`** w `_COUNTRIES`: kod, nazwa, `extent_wgs84`
   i `dataset_keys`. `countries_for_bbox` czyta kraje z rejestru przez
   `all_countries()`, wiec dyspozycja `--country auto` zaczyna widziec nowy
   kraj bez zmian w CLI. Pamietaj, ze obwiednia jest prostokatem (sekcja 4.6).
3. **Parser godel/kafli** w `core/` (jesli kraj ma wlasny system godel):
   klasa parsera + wpis `SheetSystem` (`detect`, `path_parts`) w literale
   `SYSTEMS` w `core/parser_registry.py`; wzorzec godla trzymaj tam jako
   stala publiczna (jak `CZ_TM33_PATTERN`/`CZ_SM5_PATTERN`) i importuj ja
   w parserze/indeksie — jeden wzorzec na system. Wzory: `ParserTM33`
   (siatka obliczalna) i `SheetIndex.sm5_sheet` (siatka wymagajaca
   indeksu). Fallback `pl1992` musi zostac ostatni — jego `detect` zawsze
   zwraca `True`, wiec `detect_system` nigdy nie zwraca `None`.
4. **Provider** w `providers/de/`, wzorowany na `providers/cuzk/`: generyczny
   silnik sterowany deskryptorem (odpowiednik `CuzkClient` — zna URL-e
   z `AccessChannel.endpoint`, nie zna godel ani sidecarow), provider
   produktowy nad nim i fabryka `create_*_provider()` w `__init__.py` jako
   jedyne miejsce domyslow kraju. Provider ustawia `descriptor_key`.
5. **Dyspozycja w bibliotece** (ADR-037): dla nowego kraju dopisz tor
   w `download/data.py` (`_dispatch_area` -> funkcja toru kraju) i uzupelnij
   walidacje `download/options.py` (`validate_request`, `check_per_country`)
   oraz `download/area.py::pl_only_flags` o opcje, ktore w tym kraju nie
   istnieja; CLI nie zmienia sie poza wyborami flag w module grupy
   `cli/groups/elevation.py` / `imagery.py` (stale z `download/options.py`). Scenariusz kraju w `tests/test_parity.py`. Reprojekcje rob lokalnie, przypieta operacja — nigdy przez
   parametr CRS serwera (ADR-024).
6. **Testy**: fixtury z REALNYCH odpowiedzi serwera (wzor `tests/fixtures/cuzk/`),
   test spojnosci deskryptor-provider, wpis w `KNOWN_PATHS` dla kazdej
   uzywanej pary ukladow wraz z oczekiwana dokladnoscia, testy sciezek
   nowego segmentu i test tresci po warpie (polozenie wierzcholka wzgledem
   wzorca pyproj). Testy sa offline — `tests/conftest.py` przewraca kazdy
   test wychodzacy w siec poza loopback; wyjatek maja tylko testy z markerem
   `live` (domyslne komendy: `-m "not live"`).

Przy transformacji tresci z/do EPSG:5514/3045 testuj dodatkowo
pin kroku datum (`DATUM_STEP_PINS` EPSG:1622/1623), nie tylko
nominalna dokladnosc `KNOWN_PATHS`: slowacka operacja ma mylace
0,5 m i moze przejsc filtr AOI w Czechach. Wlasna siatka wynikowa
powinna zachowac dokladny piksel i przypieta operacje w sidecarze.

**Nowa rozdzielczosc albo format istniejacego produktu PL (NMT/NMPT)** to
wpis rejestru, nie kod: jedna linia `_pl_sheet_source(produkt, etykieta,
uklady_wysokosci, format=...)` w `registry.py::_PL_SHEET_SOURCES` (ADR-041,
sekcja 3.1). Klucz deskryptora, segment, rozszerzenie, walidacja
`--resolution`/`--vertical-crs`/`--format`, teksty `--help`,
`list-sources`, twardy filtr rekordu skorowidza, podpowiedzi P10
i kombinacje raportu dostepnosci czytaja rejestr. Nowy format archiwum
wymaga dodatkowo wpisu `FileFormat` w `sources/variants.py::FORMATS`
(token, nazwa pola `format`, rozszerzenie, koncowki URL) i weryfikacji
tresci w `download/campaigns.py::verify_file_format`. Nowy kanal WCS
(wycinek) to osobna decyzja — dzis tylko warianty 1 m.

Nowa **komenda zapisujaca dane** (w tym `download` nowej grupy) musi
otrzymac pozycje w `kartograf/project/commands.py::COMMANDS`: dozwolone
opcje zadania, wspolna z pobraniem walidacja bez sieci, funkcja pobrania
i `check_*`, adapter wyniku na komplet przypinanych `VersionedFile`.
Parser komendy ustawia `_task` korzystajace z tego samego tlumaczenia
flag co `_handler`, bez `output_dir` i opcji pojedynczego uruchomienia.
Dodaj test zadania projektu dla tej komendy (przypiecie, sprawdzenie
i odtworzenie); nowy produkt istniejacej komendy nie wymaga nowej
pozycji w tabeli (ADR-040, spec manifestu sekcja 5).

**Nowy produkt kolekcji (ADR-042).** Paczka jednostki (powiat,
wojewodztwo, plik krajowy) albo obiekty obszaru z WFS 2.0 / ArcGIS REST to
wpis deskryptora z `AccessChannel.params` (`UnitPackageParams` albo
`FeatureBBoxParams`, sekcja 3.1) - bez providera i bez kodu silnika:
segment = `storage_subdir` + tokeny wariantu (sekcja 3.3 regula 9), kanal
wynika z rodzaju wyboru (sekcja 4.10), sidecar, wersje i plan sa wspolne.
Kolejnosc osi BBOX (`axis_order`) potwierdz testem na prawdziwej
odpowiedzi uslugi (zamiana osi daje pusty wynik bez bledu), kanal dopisz
do inwentarza sygnalow testow rejestru, fixtury nagraj z prawdziwych
odpowiedzi. CLI: nowa grupa = modul z `add_collection_commands`
(`cli/groups/_collection.py`) i pozycja projektu (akapit wyzej); nowy
produkt istniejacej grupy = tylko nowy wybor `--product` z rejestru. Nowy
protokol (np. OGC API Features) rozszerza `FeatureBBoxParams.protocol`
razem z pierwszym produktem. Checklista: `docs/DEVELOPMENT_STANDARDS.md`
17.5.

---

## 6. Decyzje (ADR)

Indeks decyzji z tytulami, datami i statusami (relacje "zastapiona",
"uzupelniona") prowadzi `docs/DECISIONS.md` (sekcja "Indeks") — ten
dokument go nie powiela. Sekcje powyzej powoluja sie na numery ADR i ich
erraty tam, gdzie opisuja wynikajace z nich zachowanie kodu.
