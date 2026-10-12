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
`area_files`, `admin_unit_files`, `bbox_vector` (ktore z nich deklaruje dany
zbior, mowi jego wpis w `registry.py`). Logika wykonawcza zostaje w providerach —
deskryptor mowi CO zrodlo potrafi i gdzie ma wyladowac wynik, nie JAK je pobrac.

**Sidecar przy kazdym udanym pobraniu.** Obok kazdego pliku danych powstaje
`<pelna_nazwa_pliku>.meta.json` ze schema `kartograf-meta/1`: uklad poziomy
i pionowy, `nodata`, oryginalne zadanie, licencja, wersja pakietu, opis
wykonanych transformacji. Sidecary pisza **warstwy zarzadzajace** —
`DownloadManager`, `LandCoverManager`, wycinek PL w bibliotece
(`download/cutout.py::write_pl_cutout_sidecar`), kafle LAZ w bibliotece
(`download/laz.py::write_laz_sidecar`, ADR-029), wynik HSG
(`HSGCalculator._write_sidecar`, sekcja 4.8) i wynik CZ
(`download/cz_cutout.py::write_cz_sidecar`, od 0.7.1) — nigdy providery;
provider zwraca `Path`, metadane skladane sa pietro wyzej, gdzie znany jest
kontekst zadania. Wynika z tego, ze bezposrednie wywolanie
providera z biblioteki (np. `GugikProvider.download`,
`CuzkDmrProvider.download`/`download_bbox`) zapisuje sam plik danych, bez
sidecara — w szczegolnosci sidecar DMR CZ pisze
`download/cz_cutout.py::write_cz_sidecar`: dla wycinka bbox wolany przez
`run_cz_cutout` (biblioteka i CLI, sekcja 4.5), dla godla CZ przez CLI
(`_cz_download_sheet`), bo tor CZ omija `DownloadManager` (ADR-023).
Nowy sidecar powstaje zawsze przez
`sources/sidecar.py::emit_sidecar` — jedyne miejsce polityki zapisu
(poza nim: kopia sidecara wersji w sciezce standardowej,
`download/links.py::write_link_sidecar`, i lista lotow zadania
`update_sidecar_extra` w sidecarze dowiazania). Zapis
jest domyslnie best-effort: kazdy blad (IO, brakujacy klucz deskryptora,
wyjatek w budowie metadanych) konczy sie `logger.warning` i zwrotem `None`,
nigdy przerwaniem pobrania — dane sa wazniejsze niz metadane. Poza bledem
zapisu jedyny cichy przypadek braku sidecara przy sukcesie to provider bez
`descriptor_key` (`descriptor_key` nie bedacy `str`): `emit_sidecar` wraca
wtedy `None` bez ostrzezenia. Wyjatek: sidecar WERSJI w magazynie
wersjonowanym (ADR-036, sekcja 3.3) jest obowiazkowy i pisany wylacznie
(`exclusive=True`: tmp + `fsync` + `os.link`); bez deskryptora powstaje
sidecar okrojony (`request`, `extra`, `sha256`, `size_bytes`,
`downloaded_at`), a kazdy inny blad to `DownloadError` i brak wersji.
Sidecar wersji nigdy sie nie zmienia (`extra.parent_requests` usuniete
w 0.8.0; `parent_request` opisuje zadanie, ktore utworzylo wersje).

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
kartograf ──> core, download, providers, landcover, hydrology,
        cache                          # re-eksport Public API
cli ──> kartograf (__version__), download, landcover, core, sources,
        providers (l), transform (l), transport (l), hydrology (l), cache (l)
download ──> providers, sources, transform, core, transport (l)
landcover ──> providers, download (FileStorage), core, cache, sources (l)
hydrology ──> core, providers (l), sources (l), transform (l)
providers ──> sources, transform, transport, core, cache,
        auth (l), download (l)
sources ──> core, kartograf (l, __version__)
transport ──> transform, core, kartograf (l, __version__)
transform ──> core
cache ──> core                         # tylko pod TYPE_CHECKING (BBox)
auth ──> (nic wewnetrznego)
core ──> (nic wewnetrznego)
exceptions ──> (lisc; krawedzie DO niego pominiete powyzej — importuja go
        kartograf, cli, core, sources, transform, transport, providers, download,
        landcover)
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
- `download` siega po `transform` WYLACZNIE w `download/cutout.py`
  (wycinek PL, sekcja 4.3), a po `transport` w `download/cutout.py`
  i `download/cz_cutout.py`: przy imporcie `transform.crs`
  (`PinnedTransform`, `CONTENT_POLICY`, `WARP_MARGIN_PX`), leniwie
  `transform.crs.build_pinned_transform` (`prepare_pl_cutout`),
  `transform.raster` (warp wycinka WCS) oraz
  `transport.mosaic.has_valid_pixels` (`run_pl_wcs_cutout` i
  `run_cz_cutout`, kontrola `all_nodata`; w `cz_cutout.py` tylko ten leniwy
  import).
  `manager.py` i `storage.py` nie importuja zadnego z nich —
  `DownloadManager` pozostaje warstwa koordynacji arkuszy.
- `cli` nie buduje mozaiki ani warpu wycinka (robi to biblioteka, R3),
  a z `transform` bierze tylko `TransformError`. Jedyna krawedz
  `cli ──> transport` to leniwy import `transport.mosaic.has_valid_pixels`
  w `_warn_cz_all_nodata` (kontrola "wynik CZ w calosci nodata" dla godla
  CZ; wycinek bbox CZ sprawdza biblioteka, `run_cz_cutout`).
- `transport ──> transform`: `transport/mosaic.py` owija zrodla mozaiki
  w VRT przez `transform.raster` (`vrt_xml`, `VRT_TYPES`; import na poziomie
  modulu). `transform` nie importuje `transport` — cyklu nie ma.
- `providers ──> download` jest leniwa i MUSI taka zostac (pakiet
  `download` importuje `providers` przy imporcie): walidacja opcji kampanii
  `download.campaigns.validate_campaign_args` w
  `SkorowidzLayersMixin.resolve_campaigns` (`providers/pl/skorowidz.py`)
  i w `GugikLazProvider.select_tiles` (`providers/pl/gugik_laz.py`) oraz
  przeliczenie obszaru do EPSG:2180 `download.cutout.bbox_to_2180`
  w `providers/pl/prg.py` (jedna regula dla wycinka PL i odkrywania TERYT).
- `cache ──> core` istnieje tylko pod `if TYPE_CHECKING:` (adnotacja
  `BBox` w `MetadataCache.get_teryts_for_bbox`/`set_teryts_for_bbox`);
  w czasie wykonania `cache` nie importuje nic wewnetrznego.
- `landcover ──> cache`: `LandCoverManager(cache=MetadataCache | None)`
  importuje `MetadataCache` na poziomie modulu (adnotacja) i przekazuje go
  providerom tworzonym po nazwie (`Bdot10kProvider(cache=)` — odpowiedzi
  PRG, `SoilGridsProvider(cache=)`); CORINE cache nie ma.
- `hydrology ──> core` istnieje na poziomie modulu tylko pod
  `if TYPE_CHECKING:` (adnotacja `BBox` w `hsg_from_rasters`; wg reguly grafu
  to import na poziomie modulu). Reszta jest leniwa: `providers.soilgrids`
  (warstwy gleb), `core.sheet_parser` (godlo -> bbox), `core.bbox`
  (`transform_bbox`), `transform` (przypieta reprojekcja wejsc
  `hsg_from_rasters`) i `sources.sidecar` (`emit_sidecar`, `file_digest` —
  sidecar wyniku HSG).
- `sources` i `transport` siegaja do pakietu glownego leniwie i tylko po
  `__version__` (sidecar, naglowek `User-Agent`) — import przy imporcie
  modulu dalby cykl, bo `kartograf/__init__.py` importuje providery.
- Krawedz `download ──> providers` siega tez do zamrozonego toru CZ:
  `download/cutout.py` (tor PL) importuje leniwie generyczny `bbox_to_crs`
  z `providers/cuzk/dmr.py` (ADR-024); przeniesienie go do `transform/` to
  etap 2, razem z odmrozeniem toru CZ.

### Moduly

Drzewo wymienia kazdy modul `.py` pakietu (`auth/` i `cli/` zbiorczo,
`__init__.py` podpakietow tylko gdy niosa wlasna logike). Zrodlo prawdy:
`find kartograf -name '*.py'`; Public API: `kartograf/__init__.py` (`__all__`).

Stabilne API transportu i mozaiki (od 0.7.1): `get_with_retry` (dowolny URL
uslugi, polityka ponowien siec/429/5xx/`Retry-After`, tylko GET),
`make_gugik_session`, `mosaic_and_crop`, `check_source_grid` — eksportowane
z `kartograf`; zmiana sygnatury = zmiana lamiaca w CHANGELOG.

```
kartograf/
├── __init__.py          # Public API (BBox, SheetParser, DownloadManager, providery, ...)
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
│   ├── descriptor.py    # SourceDescriptor (+ resolve_subdir), AccessChannel,
│   │                    # TransportKind, TileScheme, LicenseInfo, CountryProfile
│   ├── registry.py      # Rejestr PL/CZ/EU/GLOBAL: get_source, sources_for, get_country,
│   │                    # all_countries, vertical_crs_code, resolve_vertical_crs (rodzina ->
│   │                    # realizacja), parse_pl_system, horizontal_crs_for_sheet/_for_system
│   └── sidecar.py       # ResultMetadata, build_metadata, write_sidecar, emit_sidecar
│                        # (jedyna polityka zapisu), pl_sheet_horizontal_crs, read_asc_nodata
├── transform/           # Transformacje wspolrzednych i rastrow
│   ├── bbox.py          # envelope_from_2180 — obwiednia bboxa EPSG:2180 w innym ukladzie
│   │                    # (CORINE, SoilGrids; domyslny transformer pyproj, sekcja 1)
│   ├── crs.py           # TransformPolicy, PinnedTransform, build_pinned_transform, KNOWN_PATHS;
│   │                    # TransformError -> TransformUnavailableError (brak bezpiecznej operacji)
│   └── raster.py        # warp_to_grid — lokalny warp na siatke, operacja WYMUSZONA (tory PL
│                        # i CZ); vrt_xml/VRT_TYPES dla transport/mosaic.py
├── transport/           # Wspolny transport
│   ├── http.py          # download_to (pliki WSZYSTKICH providerow; zapis atomowy os.replace)
│   │                    # i get_with_retry (zapytania: skorowidz, WFS LAZ, WFS PRG,
│   │                    # CuzkClient.query) — jedyne miejsce retry (siec, 429, 5xx;
│   │                    # Retry-After): is_retryable, retry_wait, backoff_delay;
│   │                    # make_gugik_session, SessionPerThread (sesja per watek)
│   ├── chunks.py        # GridSpec, ChunkLimits, Chunk; align_bbox, plan_chunks,
│   │                    # fetch_chunks — wspolne kawalki CUZK i GUGiK WCS
│   ├── aaigrid.py       # multipart WCS -> ASC (streaming), walidacja siatki i atomowy GeoTIFF float32
│   └── mosaic.py        # mosaic_and_crop — merge rastrow + przyciecie, propagacja nodata;
│                        # bez dtype= mieszane typy pasm -> ValidationError;
│                        # opcjonalnie (dtype=) owijanie zrodel w VRT;
│                        # check_source_grid (fazy siatki, SourceGrid.off_grid), has_valid_pixels
├── providers/           # Providery danych
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider, LandCoverProvider
│   ├── pl/              # GUGiK: gugik.py (NMT), gugik_nmpt.py, gugik_orto.py,
│   │                    # gugik_laz.py (select_tiles, select_all_intersecting), bdot10k.py,
│   │                    # skorowidz.py (rekordy GetFeatureInfo, wybor ADR-028,
│   │                    # SkorowidzLayersMixin: resolve_campaigns/download_record/
│   │                    # record_source/available_years; select_campaign_records,
│   │                    # coverage_hints/no_coverage_error),
│   │                    # wcs.py (GugikWcsMixin — kawalki GetCoverage NMT/NMPT/orto),
│   │                    # prg.py (WFS PRG: maska ladu A00 - W02 - W03 dla wycinka,
│   │                    # discover_teryts_for_bbox, teryt_for_point),
│   │                    # __init__.py (create_nmt_provider, nmt_vertical_crs,
│   │                    # require_nmt_vertical_crs)
│   ├── cuzk/            # CUZK: client.py (CuzkClient — silnik sterowany deskryptorem: ArcGIS
│   │                    # REST query/export_image + pliki openzu), sheets.py (SheetIndex/
│   │                    # SheetInfo — indeks SM5/TM33 z KladyMapovychListu, odsiewa
│   │                    # nadmiarowy wybor uslugi), dmr.py (CuzkDmrProvider — DMR 5G/4G,
│   │                    # opcjonalnie Bpv -> EVRF2007), __init__.py (create_dmr_provider —
│   │                    # jedyne miejsce czeskich domyslow)
│   ├── corine.py        # CORINE z Copernicus CLMS (+ fallback WMS PNG)
│   └── soilgrids.py     # SoilGrids z ISRIC (WCS)
├── cache/metadata.py    # MetadataCache — SQLite WAL, thread-safe; tabele record_cache,
│                        # campaigns_cache, teryt_cache, teryt_bbox_cache (TTL 7 d,
│                        # DEFAULT_TTL_SECONDS)
│                        # i sheet_cache (30 d, SHEET_TTL_SECONDS); plik bazy
│                        # otwierany leniwie, powstaje przy pierwszym zapisie
├── download/            # Pobieranie NMT/NMPT/Orto po godle + wycinek PL
│   ├── campaigns.py     # Kampanie GUGiK (ADR-030): CampaignRef, format z rekordu,
│   │                    # verify_file_format, verify_record_url/verify_sheet_extent (B4),
│   │                    # verify_record_vertical_crs (uklad wysokosci rekordu)
│   ├── countries.py     # Podzial obszaru na kraje: countries_for_bbox, split_bbox_by_country
│   ├── links.py         # Dowiazanie sciezki standardowej do wersji (wylacznie hardlink, nigdy wstecz)
│   ├── cutout.py        # Wycinek PL WCS (ADR-035): prepare_pl_cutout,
│   │                    # run_pl_wcs_cutout, download_pl_cutout, maska, sidecar
│   ├── cz_cutout.py     # Wycinek CZ jako API: download_cz_cutout/run_cz_cutout, all_nodata,
│   │                    # write_cz_sidecar
│   ├── laz.py           # Kafle LAZ jako API (ADR-029): download_laz_area/run_laz_download —
│   │                    # pula watkow, sidecar kafla, porazki w wyniku
│   ├── manager.py       # DownloadManager — koordynacja arkuszy (ThreadPoolExecutor), sidecary;
│   │                    # kampanie (all_campaigns=, min_year=, max_year=), tryby update
│   │                    # (None/upgrade/force), SheetFetch/last_sheet, inspect_sheets,
│   │                    # download_sheets/expand_sheets (lista godel, porazki w last_result)
│   ├── storage.py       # FileStorage — segmenty z szablonow rejestru (ADR-026), versions/;
│   │                    # prune_empty_dirs — sprzatanie pustych bbox/ po porazce
│   ├── updates.py       # Plan aktualizacji kartograf-plan/1 (ADR-036): check_updates, upgrade
│   └── versions.py      # Magazyn wersjonowany (ADR-036): zapis wylaczny, etykiety,
│                        # lista wersji, sprzatanie .incoming/
├── landcover/manager.py # LandCoverManager — dispatch do providerow pokrycia terenu;
│                        # download_all_counties (BDOT10k z kazdego powiatu obszaru)
├── hydrology/hsg.py     # HSGCalculator — klasyfikacja USDA -> HSG (ADR-025)
├── auth/                # proxy.py (subprocess izolujacy credentials CLMS), client.py
│                        # (AuthProxyClient — singleton, sam uruchamia proxy)
└── cli/                 # _parser.py (argparse: top-level + subkomendy), parse_cmd.py,
                         # download_cmd.py (godlo / bbox / geometry / LAZ / CZ),
                         # landcover_cmd.py, soilgrids_cmd.py (HSG), cache_cmd.py,
                         # commands.py (fasada zgodnosci: re-eksport + entry point main)
```

---

## 3. Kontrakty danych

### 3.1 `SourceDescriptor` i szablony `storage_subdir`

`SourceDescriptor` (`kartograf/sources/descriptor.py`) niesie: `key`,
`country`, `product`, `name`, `provider_name`, krotke `channels`
(`AccessChannel`), `tile_scheme`, `storage_subdir`, `default_extension`,
`license`, `resolution`, `auth`.

Od 0.7.0 (ADR-026) `storage_subdir` jest **szablonem** z placeholderami
`{system}` i `{vcrs}`, a nie literalna nazwa katalogu. Konsument zewnetrzny
czytajacy to pole wprost dostanie szablon — swiadomy trade-off; poprawna droga
to `resolve_subdir()`.

| Klucz deskryptora | `storage_subdir` | `default_extension` |
|---|---|---|
| `pl.gugik.nmt_1m` | `nmt/pl_{system}_1m_{vcrs}` | `.asc` |
| `pl.gugik.nmt_5m` | `nmt/pl_{system}_5m_{vcrs}` | `.asc` |
| `pl.gugik.nmpt` | `nmpt/pl_{system}_1m_{vcrs}` | `.asc` |
| `pl.gugik.orto` | `orto/pl_{system}` (+ `_<wariant>` dla CIR/B-W, regula 5) | `.tif` |
| `pl.gugik.laz` | `laz/pl_{system}_{vcrs}` | `.laz` |
| `cz.cuzk.dmr5g` | `nmt/cz_dmr5g_{vcrs}` | `.tif` |
| `cz.cuzk.dmr4g` | `nmt/cz_dmr4g_{vcrs}` | `.tif` |
| `pl.gugik.bdot10k` | `None` | `.gpkg` |
| `eu.clms.corine` | `None` | `.tif` |
| `global.isric.soilgrids` | `None` | `.tif` |

NMT 1 m i NMPT maja kanal WCS `bbox_raster` dla obu ukladow pionowych
(`EPSG:9650` KRON86, `EPSG:9651` EVRF2007); kanal `sheet_files` sluzy
osobno arkuszom OpenData. NMT 5 m nie ma kanalu WCS.

`None` oznacza zrodlo obslugiwane przez `LandCoverManager`, ktory ma wlasna
konwencje nazw i wlasny domyslny `--output` (sekcja 4.8).

**`SourceDescriptor.resolve_subdir(*, system=None, vertical_crs=None) -> str`**
wypelnia szablon przez `str.replace`, a nie `str.format` — czesciowe
wypelnienie jest legalne. `vertical_crs` jest normalizowany do lowercase
(`"Bpv"` -> `"bpv"`). Podanie wymiaru, ktorego szablon nie ma, to no-op
(orto ignoruje `vertical_crs`). Zrodlo bez `storage_subdir` rzuca `ValueError`.
Pusty string (albo sam whitespace) w `system`/`vertical_crs` to
`ValidationError` — `None` znaczy "wypelnij pozniej", a pusty napis dawal
cichy segment `nmt/pl_1992_1m_` (review max zn. 7).

Kto wypelnia ktory placeholder:

| Placeholder | Kto wypelnia | Kiedy |
|---|---|---|
| `{vcrs}` | konstruktor `FileStorage(vertical_crs=)` albo jawne `resolve_subdir(vertical_crs=)` | raz, na starcie zadania — uklad pionowy jest wlasnoscia zadania, nie arkusza |
| `{system}` | `FileStorage` per identyfikator (`get_path`/`get_raw_path`/`exists`/`delete`/`ensure_directory`), regula ta sama co `parser_registry.path_parts`: kropki -> `2000`, reszta -> `1992` | przy budowie kazdej sciezki |
| `{system}` (jawnie) | tor LAZ: `LazTile.system` (`uklad_xy` kafla przez `parse_pl_system`; nieznany = kafel pominiety / `ValidationError`) przez `FileStorage.get_raw_path(..., system=)` — jedno zrodlo prawdy dla CLI i biblioteki (zn. 8, review max); wycinek PL WCS (`prepare_pl_cutout`: `system="1992"` na stale — `--target-crs` z `--system 2000` jest odrzucane, sekcja 4.3); przestarzaly tor arkuszowy odrzuca arkusz we wspolrzednych PL-2000 | przed utworzeniem `FileStorage` / sciezki wycinka |

`FileStorage` waliduje wynik koncowy: segment, w ktorym po wypelnieniu zostala
klamra `{`, konczy sie `ValidationError` z nazwa brakujacego wymiaru
(`_ensure_resolved`). Cichy katalog `pl_{system}_1m_evrf2007` nigdy nie powstanie.

### 3.2 Schema sidecara `kartograf-meta/1`

Kazde udane pobranie przez CLI albo warstwe zarzadzajaca biblioteki
(`DownloadManager`, `LandCoverManager`, `download_pl_cutout`/`run_pl_wcs_cutout`,
`download_laz_area`/`run_laz_download`, `HSGCalculator`) zapisuje **dwa**
pliki: dane i `<plik>.meta.json` (zapis best-effort, wyjatki — sekcja 1).
Od 0.7.1 takze `download_cz_cutout`/`run_cz_cutout` (wycinek CZ)
i `hsg_from_rasters`. Bezposrednie wywolanie providera sidecara nie pisze
(np. `CuzkDmrProvider.download`); sidecar godla CZ pisze CLI.

| Pole | Znaczenie |
|---|---|
| `dataset` | klucz deskryptora zrodla (np. `pl.gugik.nmt_1m`) |
| `country`, `product`, `provider` | kraj, produkt i nazwa dostawcy z deskryptora |
| `horizontal_crs` | faktyczny uklad poziomy pliku: arkusz PL-1992 `EPSG:2180`, arkusz PL-2000 `EPSG:2176`–`EPSG:2179` wedlug strefy godla, CZ natywnie `EPSG:5514`, kafel TM33 `EPSG:3045`; wycinek po `--target-crs` w ukladzie docelowym. Dla arkusza PL uklad z godla jest SPRAWDZANY wspolrzednymi pliku (`sources/sidecar.py::pl_sheet_horizontal_crs`): plik opublikowany przez GUGiK w innym ukladzie niz wskazuje godlo (E17, np. arkusze PL-2000 strefy 7 jak `7.125.11.19` w EPSG:2180) dostaje uklad PLIKU, deklaracja rekordu skorowidza zostaje w `extra.source.declared_crs`, logger `kartograf.sources.sidecar` ostrzega, a CLI drukuje `Warning: N arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: ...` (kod bez zmian; segment katalogu nadal wg godla, ADR-026) |
| `vertical_crs` | kod realizacji ukladu pionowego: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007); `null` gdy produkt nie ma pionu (orto) |
| `vertical_source` | `native` / `ellipsoidal` / `server` (z `AccessChannel`) |
| `resolution` | rozdzielczosc z deskryptora (`1m`/`5m`/`2m`) albo `null` |
| `nodata` | wartosc pustego piksela: dla `.asc` czytana automatycznie z naglowka (`read_asc_nodata`), w torze CZ z tagu GeoTIFF (`download/cz_cutout.py::read_tif_nodata`; w trybie bbox z fallbackiem `CUZK_NODATA`), dla wycinka PL stala `-9999.0`, dla wyniku HSG `0`, dla GeoTIFF CORINE/SoilGrids z `LandCoverManager` z tagu pliku (sekcja 4.8); `null` gdy zadna z tych drog nie ma zastosowania (np. orto) |
| `request` | zadanie, ktore dalo TEN plik: `sheet` (godlo), `bbox` + `bbox_crs` w ukladzie wyniku albo `teryt`; dla kampanii PL `campaigns` (rozwiazane `newest`/`all`, zawsze), `min_year`/`max_year` (gdy podane) i `year` (gdy granice rowne); LAZ: `year`/`min_year`/`max_year`/`min_density` gdy podane, `campaigns` tylko dla `all`; land cover: parametry tresci z domyslnymi wartosciami — SoilGrids `property`/`depth`/`stat`, CORINE `year`, BDOT10k `format` (4.8). `request` opisuje pierwotne POBRANIE pliku, nie ostatnie wykorzystanie; `extra.parent_request(s)` nie niesie flag roku (3.4) |
| `license` | `{id, attribution, url}` z deskryptora |
| `downloaded_at`, `kartograf_version` | znacznik czasu UTC (ISO 8601, sekundy) i wersja pakietu z `kartograf/_version.py::build_version()`: wydanie = samo `__version__`; wersja rozwojowa (`dev`) = `<__version__>+<krotki SHA>` commita, z ktorego zaimportowano pakiet, z sufiksem `.dirty`, gdy sledzone pliki katalogu `kartograf/` maja niezacommitowane zmiany (docs/testy sie nie licza); gdy git jest niedostepny albo pakiet nie pochodzi z repozytorium, w ktorym lezy (`os.path.samefile`), samo `__version__`. Ta sama wartosc w `kartograf --version`; `User-Agent` HTTP niesie samo `__version__` |
| `transform` | slownik osi (`horizontal`/`vertical`) z opisem uzytej operacji w formacie `pinned: <opis> (<dokladnosc> m)`; os bez przeliczenia nie ma klucza, a bez zadnego przeliczenia cale pole to `null` |
| `extra` | `parent_request` (obszar; zadanie, ktore utworzylo plik — `parent_requests` usuniete w 0.8.0); LAZ `tile_sheet`/`year`/`nominal_density`/`url`, dodatkowo `acquisition_date`/`full_sheet`, gdy znane; arkusze NMT/NMPT/orto PL `source`, `campaign`, `version` (`label`, `label_source`; ADR-036), `coverage` (lot niepelny, przy zapisie wersji) oraz pola rocznikow/lotow opisane nizej; SM5 `mapname`/`cz_share`; wycinek bbox CZ `all_nodata` i `parent_request`; wycinek PL WCS `source`, `mask`, `zero_pixels` (tylko gdy > 0), `all_nodata`, `parent_request` (sekcja 3.2); CORINE WMS `fallback`/`note`; HSG `derived` i parametry obliczen |
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
i `campaigns_cache`):

| Klucz | Zawartosc (pole rekordu GUGiK) |
|---|---|
| `url` | URL pliku OpenData (`url`) |
| `index_url` | endpoint WMS skorowidza, z ktorego pochodzi rekord |
| `layer` | warstwa skorowidza (np. `SkorowidzeNMT2025`) |
| `sheet` | godlo arkusza po normalizacji (`godlo`) |
| `acquisition_date` | data aktualnosci danych `RRRR-MM-DD` (`aktualnosc`) |
| `acquisition_year` | rok aktualnosci (`aktualnoscRok`, inaczej z `aktualnosc`) |
| `pzgik_date` | data przyjecia do PZGiK (`dt_pzgik`) albo `null` |
| `resolution_m` | rozdzielczosc w metrach (`charakterystykaPrzestrzenna`/`wielkoscPiksela`) |
| `declared_crs` | uklad zadeklarowany w rekordzie, np. `PL-2000:S7` (`ukladWspolrzednychPoziomych`) — moze sie roznic od `horizontal_crs` pliku (E17) |
| `full_sheet` | `true`/`false` = pelny/niepelny arkusz (`calyArkuszWypelnionyTrescia`), `null` gdy brak |
| `survey_work_id` | numer zgloszenia pracy geodezyjnej (`numerZgloszeniaPracy`) |
| `data_source` | zrodlo danych (`zrDanych`/`zrodloDanych`) |
| `format` | format pliku z rekordu (`format`), np. `ARC/INFO ASCII GRID` |
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

**Wycinek PL WCS (`--target-crs`) w sidecarze.** Biblioteka
(`download/cutout.py::write_pl_cutout_sidecar`) buduje rekord z
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

**Magazyn wersjonowany (ADR-036).** Sidecar WERSJI (`versions/.../<etykieta>_<sha8>/<plik>.meta.json`)
jest OBOWIAZKOWY i niezmienny: `emit_sidecar(..., exclusive=True)` pisze
go raz (tmp + `fsync` + `os.link`, nigdy nie nadpisuje); porazka zapisu
rzuca `DownloadError` (zapis usuwa utworzony plik danych, wersji nie ma).
Pozostale sidecary (wycinek, LAZ, CZ, landcover, HSG) zostaja best-effort.
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
cztery miejsca po przecinku) ma sidecar wersji KAZDEGO lotu bez
`full_sheet=true` — liczone z tego samego odczytu co sha256 przy zapisie
(ASC bez `NODATA_value` = -9999, orto wg nodata/alfa; blad pomiaru = brak
pola + ostrzezenie), nigdy dopisywane pozniej. Przy przedziale i `all`
z > 1 lotem, gdy najnowszy lot nie ma `full_sheet=true`, sidecar
standardowy dostaje `extra.flights` (malejaco wg ADR-028; `id`, `date`,
`full_sheet`, `coverage` z sidecarow wersji), a przy starszym locie
o WIEKSZYM pokryciu `extra.better_coverage` = jego `id` (lot zadeklarowany
jako pelny liczy sie jako pokryty w pelni) i CLI `Info:` na stderr (takze
z `-q`). Pole `better_coverage` jest usuwane, gdy ponowne zadanie nie
wykaze lepszego lotu. Pokrycie NIE przestawia dowiazania (najpierw
najnowszy lot wg ADR-028, zasada "nigdy wstecz"). Sidecar LAZ niesie
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
│   ├── pl_1992_5m_evrf2007/...              # 5m tylko EVRF2007 (regula istniejaca)
│   ├── pl_1992_1m_evrf2007/bbox/<coords>_<YYYYMMDD>.tif # wycinek PL WCS (4.3)
│   ├── pl_2000_1m_evrf2007/6/179/12/20/6.179.12.20.asc
│   ├── cz_dmr5g_bpv/302/5550/302_5550.tif
│   ├── cz_dmr5g_bpv/bbox/<coords>.tif       # wycinki bbox CZ
│   ├── cz_dmr5g_evrf2007/...
│   └── cz_dmr4g_bpv/CTES/96/CTES96.tif
├── nmpt/
│   ├── pl_1992_1m_evrf2007/...              # (+ _kron86, + pl_2000_...)
│   └── pl_1992_1m_evrf2007/bbox/<coords>_<YYYYMMDD>.tif # wycinek NMPT WCS
├── orto/pl_1992/...                         # bez ukladu pionowego
├── orto/pl_1992_cir/...                     # wariant CIR (B/W: pl_<uklad>_bw), E12
├── laz/pl_2000_evrf2007/...                 # poziomy per kafel (uklad_xy), pionowy z flagi
└── landcover/...                            # wlasny katalog (--output wymagane)
```

**Reguly segmentow:**

1. Segment ma postac `<kraj>_<uklad>[_<wariant>][_<vcrs>]`, wszystkie wartosci
   lowercase. Uklad PL: `1992` / `2000`. Uklad pionowy: `kron86` /
   `evrf2007` / `bpv`. CZ nie niesie ukladu poziomego, bo nazwa datasetu
   (`dmr5g`/`dmr4g`) wyznacza go 1:1 (natywnie zawsze EPSG:5514).
2. Hierarchia wewnatrz segmentu jest bez zmian — `parser_registry.path_parts`:
   PL-1992 `N-34-130-D-d-2-4` -> `N-34/130/D/d/2/4`, PL-2000 `6.179.12.20` ->
   `6/179/12/20`, TM33 `302_5550` -> `302/5550`, SM5 `CTES96` -> `CTES/96`.
3. Podkatalog `bbox/` wewnatrz segmentu trzyma wycinki: PL WCS z
   `--target-crs` to `<coords>_<YYYYMMDD>.tif`, CZ to `<coords>.tif`.
   Wspolrzedne sa w ukladzie WYNIKU (po `--target-crs`), formatowane
   `%.10g` i sklejane `_`. Nazwa niesie ZADANIE, nie dokladny zasieg
   rastra: wycinek PL w EPSG:2180 siega do < 1 px dalej po wyrownaniu
   na zewnatrz do siatki 1 m, a siatka warpa (`warp_to_grid` z
   `transform/raster.py`, wspolna dla PL i CZ) ma calkowita liczbe
   pikseli od NW, wiec E/S moze odbiegac o do 0,5 px (sekcja 4.3). PL bez
   `--target-crs` zapisuje arkusze w hierarchii godel (sekcja 4.2).
4. Rozdzielczosc wchodzi do segmentu tylko tam, gdzie jest parametrem API
   (NMT/NMPT). Nie ma jej dla CZ (`dmr5g` to z definicji 2 m, `dmr4g` 5 m)
   ani dla orto/LAZ (brak takiego parametru).
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
   `os.path.samefile` — na udziale SMB wymaga stabilnych i-wezlow
   (`serverino`), inaczej dowiazanie jest odtwarzane przy kazdym
   uruchomieniu. `FileStorage.get_versions_root(sheet)`/`get_versions_base`,
   `list_files()` pomija `versions/`, `full_sheet/` i `kampanie/`
   (`versions=True` = tylko pliki wersji). Katalog `kampanie/` z 0.7.x
   nie jest czytany (`has_legacy_campaigns()` -> `Info:` w CLI). CZ, LAZ,
   BDOT10k i land cover nie uzywaja jeszcze `versions/` (plany 2/3, 3/3).
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

Nowe zrodlo dodaje sie samym wpisem deskryptora — np.
`nmt/de_bb_dgm1_dhhn2016/` nie wymaga zadnej zmiany w kodzie sciezek.

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
— od 2026-10-07 takze kafle LAZ (`run_laz_download(parent_request=)`,
review-2 N15; `countries` = `["PL"]`, bo LAZ odpytuje tylko GUGiK):

```json
{"bbox": [min_x, min_y, max_x, max_y], "bbox_crs": "EPSG:2180", "countries": ["CZ", "PL"]}
```

Niesie **oryginalne** zadanie uzytkownika — przed przycieciem per kraj — jego
uklad i kraje faktycznie odpytane w tym wywolaniu (probowane, nie pobrane).
W trybie `--geometry` "zadanie" to obwiednia geometrii: dla pliku w ukladzie
czeskim (EPSG:5514/3045) w ukladzie PLIKU (od 2026-09-28), dla pozostalych
w EPSG:2180; jawne `--country cz` zapisuje obwiednie w ukladzie zadania CZ
(EPSG:5514 albo `--target-crs`). Klucz buduje CLI (`_build_parent_request`);
API biblioteki zapisuje go tylko po przekazaniu `parent_request=`.
Wersja z sidecarem zachowuje `parent_request` zadania, ktore ja
UTWORZYLO; kolejne zadania nie zmieniaja sidecara wersji (ADR-036; lista
`extra.parent_requests` usunieta w 0.8.0). To jest klucz grupowania:
po nim konsument (Hydrograf, przyszly `find_downloaded`) sklada w calosc
pliki jednego zadania, takze te lezace po obu stronach granicy, ktore
Kartograf swiadomie zostawia rozdzielone (sekcja 1). Slownik jest wspoldzielony
przez referencje miedzy sidecarami zadania i **nie moze byc mutowany** po
utworzeniu.

---

## 4. Przeplywy per produkt

**Migracja 0.7.x -> 0.8.0 (ADR-036, BREAKING):**

| Stan | Zachowanie |
|---|---|
| `<segment>/kampanie/` z 0.7.x | nie jest czytany ani migrowany; CLI wypisuje raz `Info:`, potrzebne kampanie sa pobierane ponownie do `versions/` |
| dowiazanie albo zwykly plik w sciezce standardowej | sidecar bez `extra.link = "hardlink"` z celem w `versions/` = sciezka nieznana; po pobraniu wersji ZASTEPOWANA hardlinkiem |
| dowiazanie do wersji | kolejne zadania przestawiaja je tylko na wersje o kluczu `(aktualnosc, dt_pzgik, url)` wiekszym niz klucz biezacego celu; rowny klucz (nowa tresc tej samej kampanii) tylko, gdy wersja powstala w tym wywolaniu |
| dowiazanie, ktorego `extra.link_target` nie istnieje (katalog wersji usuniety) | brak pliku — pobranie od nowa |

### 4.1 Godlo PL (NMT/NMPT/Orto)

`SheetParser` waliduje godlo i normalizuje je do postaci kanonicznej:
wielkosc liter i liczby PL-1992 bez zer wiodacych (od 0.7.1, A7:
`M-33-036-A` -> `M-33-36-A`, ta sama postac w sciezce, sidecarze i wyniku);
cyfry tylko ASCII `0-9` we wszystkich ukladach godel (PL-1992, PL-2000, CZ;
od 0.7.2 — cyfry pelnej szerokosci itp. to `ParseError`); godlo
PL-1992 grubsze niz 1:10000 rozwija sie do arkuszy 1:10000
(`download_hierarchy`), godlo PL-2000 pobierane jest bezposrednio. Dla
kazdego arkusza pyta WMS skorowidz (`GetFeatureInfo`, warstwy wykryte lazy
przez `GetCapabilities` — ADR-020). `providers/pl/skorowidz.py` parsuje
pelne rekordy; filtruje cale godlo, zgodny uklad i rozdzielczosc
(dla orto wariant koloru z `color`), wybiera (strategia `newest`) rekord z najnowsza data w pierwszej
warstwie z dopasowaniem; remis rozstrzyga `dt_pzgik`, URL. Uklad wysokosci
wybiera wylacznie endpoint (osobny WMS skorowidza na uklad); przed pobraniem
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
1:10000 z samymi potomkami podpowiedz `--scale 1:2000`. NMT/NMPT (od 0.7.2,
`GugikProvider._variant_hints`): przy braku pokrycia provider pyta pozostale
warianty produktu z `WMS_INDEX_ENDPOINTS` (rozdzielczosc, uklad
wysokosci; jedno GetFeatureInfo ze wszystkimi warstwami wariantu, ten sam
punkt i twardy filtr, timeout `DEFAULT_TIMEOUT`) i dopisuje podpowiedz
`Skorowidz GUGiK ma ten arkusz w NMT 1m EVRF2007 — uzyj --resolution 1m`
(bez godla: jedna linia `Info:` dla wielu arkuszy). Blad zapytania
o wariant (jedna proba, bez ponowien) = brak tej podpowiedzi, `logger.warning`
i pominiecie tego wariantu do konca zycia providera, nigdy zmiana wyniku;
trafienie w cache braku pokrycia nie odpytuje sieci. Awaria warstwy,
raport OGC albo nieoczekiwany szablon = `DownloadError`, nie cichy fallback
do starszej kampanii. Zapytania i pobrania maja do 3 prob z backoffem
(ponawiane: siec, 429, 5xx; inne 4xx koncza przy pierwszej probie)
oraz sesje keep-alive per watek. `MetadataCache` (SQLite WAL, TTL 7 dni)
zapisuje rekord `{"source": ...}` lub potwierdzony `{"no_coverage": true}`;
CLI podpina cache w torach PL i CZ; `--force` otwiera go w obu w trybie
`MetadataCache(refresh=True)` — odczyt pominiety, swiezy rekord zapisany
(E14) — biblioteka przyjmuje `cache=`; `kartograf cache stats` pokazuje `Record entries`.
Baza jest otwierana leniwie: plik `.kartograf_cache.db` powstaje dopiero przy
pierwszym zapisie (`set_*`); konstrukcja, odczyty (`get_*` = chybienie),
`stats()` (zera, `db_exists: false`), `clear()` i `close()` na braku pliku
go nie tworza, wiec `kartograf cache path|stats|clear` w katalogu bez bazy
niczego nie zapisuja. Cache jest tylko przyspieszeniem: kazdy
`sqlite3.Error` (uszkodzony/uciety plik, brak uprawnien, `database is
locked`) wylacza instancje na reszte jej zycia (odczyt = chybienie, zapis =
no-op, `MetadataCache.error`, `stats()["error"]`) z jednym ostrzezeniem
(`logger.warning` albo `on_disabled=`; CLI: jedno `Warning:` na komende);
pobieranie idzie dalej. `MetadataCache(strict=True)` (biblioteka, od 0.7.1):
ten sam stan konczy sie `CacheError` na wywolaniu, ktore zawiodlo, i na
kazdym kolejnym (`on_disabled` nadal raz). Naprawa: `kartograf cache clear`
usuwa nieczytelny plik z `-wal`/`-shm`.
`DownloadManager` pisze sidecar po kazdym udanym arkuszu; arkusz ASC GUGiK
nie niesie CRS (rasterio: `crs=None`), wiec jedynym nosnikiem ukladu jest
sidecar. Ponowne uruchomienie rozwiazuje najnowszy rekord arkusza (cache 7 d;
po jego wygasnieciu zapytanie do skorowidza) i stosuje tryb `update`
(ponizej, "Tryby i plan aktualizacji"). `--target-crs` w trybie godlowym jest
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
brak = `SheetFetch.no_full_flight` / `DownloadResult.without_full`.
Awaria tego zapytania albo pobrania lotu pelnego = porazka arkusza
(sciezka standardowa i tak wskazuje najnowszy). Sidecar kampanii zadania
z flaga: `request.full_sheet: true`. Z `all` flaga bez skutku; z
`--target-crs` i LAZ `Error:` przed siecia. Przy przedziale lat
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
`full_link_outside_range` (takze `SheetFetch`) — arkusze, ktorych
dowiazanie standardowe albo `full_sheet/` zostalo przy locie spoza
zadania (nigdy wstecz), CLI drukuje wtedy jeden `Info:` z linia
`<godlo>: sciezka standardowa|full_sheet/ -> dowiazanie <data>_<id>`.
Dalsze szczegoly: jedna regula `DownloadManager._select` (wspolna dla
pobierania i `inspect_sheets`) decyduje per rekord "lokalna wersja albo
pobranie"; pobranie (`GugikProvider.download_record` do katalogu
roboczego, `record_source` -> `extra.source`) konczy `commit_version`
(ADR-036); po zebraniu kampanii manager przestawia dowiazanie RAZ na
arkusz (deduplikacja godel; nigdy wstecz) i zwraca `SheetFetch(sheet,
path, skipped, downloaded, reused, status, version, unverified, newer,
files)` w `DownloadManager.last_sheet` (`status`: `new`/`relabeled`/
`unchanged`/`local`, najsilniejszy z plikow; `files`: katalog wersji
i status per plik). `DownloadResult` (`last_result` listy i hierarchii)
niesie `succeeded`, `failed`, `skipped`, `no_coverage` (podzbior `failed`:
brak danych u zrodla), `no_coverage_hints` (godlo -> `NoCoverageError.hints`),
`campaign_files`, `reused_campaign_files` (wersje juz lokalne per arkusz),
listy `new`/`relabeled`/`unchanged`/`local`, `newer` (godlo -> nowsza
kampania nie pobrana), `files` i `unverified` (ponizej).
Pelna lista pol: docstringi `SheetFetch`/`DownloadResult` w
`download/manager.py`. `download_sheet` pojedynczego arkusza ustawia
`last_result` jako wynik jednoelementowy (jak lista). Pochodzenie arkusza
przy kampaniach: `provider.source_info()` wypelnia przeplyw jednego rekordu
(`download`, `get_download_url`, `resolve_campaigns` w trybie `newest`), a przy
`all` zostaje `None` — zrodlem pochodzenia jest wtedy sidecar
(`extra.source`, `extra.campaign`); sidecar sciezki standardowej opisuje
wersje, na ktora wskazuje dowiazanie, a ta moze byc starsza niz najnowszy
rekord (D5 albo nieudane pobranie, A12). Przed siecia
`verify_record_url` (B4): nazwa pliku w URL rekordu musi konczyc sie godlem
arkusza (`<id>_<numer>_<godlo>.<ext>`, porownanie w postaci kanonicznej);
URL bez godla albo z innym godlem = `DownloadError` kampanii bez pobierania.
Plik: format z pola `format` rekordu (nie z URL; brak pola — format
domyslny produktu), rozszerzenie zawsze kanoniczne (`.asc`/`.tif`; rekord
72675 z URL `.xyz` to AAIGrid, zwykla kampania `.asc`), po pobraniu `verify_file_format`
(naglowek AAIGrid / sygnatura TIFF), potem `verify_sheet_extent` (B4,
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
z zakresu (najpierw cel dowiazania), zostaje ona i `SheetFetch.newer`
/ `DownloadResult.newer` (CLI: dopisek `; dostepna nowsza <etykieta>
(--upgrade)` i `Info:`). `upgrade` pobiera ten lot; `force` pobiera
wszystkie wybrane loty ponownie i odswieza `MetadataCache` (ta sama tresc
= `unchanged`, inna = nowa wersja tej samej etykiety), weryfikacja
rekordu dziala we wszystkich trybach; `update="check"` to `ValidationError`
(sprawdzenie robi `check_updates`). Providery bez kampanii: bez `force`
najnowsza lokalna wersja (brak taniego sygnalu). `check_updates(manager,
sheets)` (CLI `--check-updates [--plan PLIK]`) niczego nie pobiera
i zwraca `UpdatePlan` (`kartograf-plan/1`: `store`, `checked_at`,
`kartograf_version`, pozycje z segmentem, hierarchia, nazwa, wersja
lokalna i sygnalem rekordu; statusy `current`/`newer`/`missing`/
`unverifiable`/`check_failed`). `upgrade(manager, plan)` (CLI `--upgrade
--plan PLIK`) odrzuca inny magazyn i nieznany schemat przed siecia,
czyta sygnal ponownie i pobiera wylacznie pozycje `newer`/`missing`
z niezmienionym sygnalem (`DownloadManager.download_records`); zmieniony
sygnal = pozycja `stale` (blad, bez pobrania). Plan 1/3 obejmuje arkusze
PL; `--check-updates`/`--upgrade` z LAZ, CZ, `--target-crs` albo
`--country` innym niz `pl` dla obszaru = `Error:` (kod 1) przed siecia.
CLI drukuje jedna linie na plik: `<godlo>: nowa wersja <etykieta>_<sha8>`,
`nowa etykieta <etykieta> (ta sama tresc)`, `bez zmian <etykieta>`,
`lokalna wersja <etykieta>`, a po liscie (bez `-q`) `Nowe: N, nowa
etykieta: N, bez zmian: N, lokalne: N, bledy: N (<dir>)`; raport
`--check-updates` to jedna linia na pozycje (`aktualne`, `nowsza: ...`,
`do pobrania`, `nie udalo sie sprawdzic: ...`), kod 1 przy pozycji
niesprawdzonej. Katalog `kampanie/` z 0.7.x: jednorazowe `Info:`.

Awaria skorowidza bez granicy roku (I-1, errata 5 ADR-030; ADR-036: kazda
strategia, tylko tryb domyslny): gdy `resolve_campaigns` konczy sie
bledem TRANSPORTU (`DownloadError` z `status_code` 429/5xx albo bez kodu,
ale z przyczyna `requests.RequestException` — siec/timeout; NIE
`NoCoverageError`, inne 4xx ani raport OGC/zly szablon), a sciezka
standardowa wskazuje istniejaca lokalna wersje (`linked_version`),
manager NIE zglasza porazki: `logger.warning` i
`SheetFetch(skipped=True, reused=(<wersja>,), status="local",
unverified=<tresc bledu>)`, dowiazanie bez zmian. Lista/hierarchia: arkusz
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
dla NMPT `data/nmpt/pl_1992_1m_evrf2007/...`, dla orto
`data/orto/pl_1992/...`.

### 4.2 Bbox / geometria PL bez `--target-crs`

Bbox trafia do `_dispatch_area`, ktore rozstrzyga kraje (sekcja 4.6), a czesc
polska idzie do `_download_pl_bbox`. `find_sheets_for_bbox` (czysta matematyka
siatki, bez zapytan sieciowych — ADR-010) daje liste godel 1:10000, ktore
pobiera `DownloadManager` rownolegle. W trybie `--geometry` arkusze wyznacza
sama geometria per obiekt (`find_sheets_for_geometry`), nie jej obwiednia.
Gdy `--geometry` wskazuje GPKG z kilkoma warstwami i nie podano `--layer`,
CLI wybiera pierwsza warstwe `gpkg_contents` i drukuje RAZ przed praca
`Info:` z jej nazwa, pozostalymi warstwami i podpowiedzia `--layer NAZWA`
(takze z `-q`); wybrana nazwa jest przekazywana dalej jawnie. Dotyczy
rowniez `landcover download` i `soilgrids hsg`. Biblioteka bez jawnego
`layer=` wybiera te sama warstwe, ale emituje `logger.warning` przy
kazdym takim rozstrzygnieciu; SHP i jednowarstwowy GPKG nie daja
komunikatu.

Sidecar pobranego arkusza dostaje `extra.parent_request` i `extra.source`
(URL, warstwa, data, rozdzielczosc). Ponowne wykorzystanie wersji nie
zmienia jej sidecara (ADR-036). Tryb listy (takze hierarchia godla) probuje
WSZYSTKIE arkusze niezaleznie od `--workers` (ADR-027 errata 3, R5-lista).
`NoCoverageError` dopisuje brakujace godlo i `Warning:`, status postepu
`no_coverage` (`∅`, `DownloadProgress.status`), bez wetowania pobranych
plikow. Podpowiedzi `NoCoverageError.hints` (np. `--scale 1:2000`) CLI
drukuje jako `Info: <podpowiedz>` na stderr (takze z `-q`), bez doslownych
duplikatow, najwyzej `MAX_HINT_LINES` linii plus `Info: ... i N innych
podpowiedzi` (`cli/download_cmd.py::_print_coverage_hints`; pelna lista:
`DownloadResult.no_coverage_hints`). Kody wyjscia: >= 1 plik i zero
twardych awarii = kod 0. Gdy brak wszystkich arkuszy albo wystapi dowolna
inna awaria pobrania, CLI konczy kodem 1 i wypisuje pelna liste porazek.
Pojedynczy arkusz bez danych to kod 1; pod `--country auto` kod zalezy
jeszcze od sukcesu drugiego kraju (sekcja 4.6).

Opcje kampanii i roku (`--all-campaigns`, `--year`, `--min-year`, `--max-year`,
sekcja 4.1) dzialaja tu per arkusz; podsumowanie `all` liczy pliki kampanii,
nie arkusze. Arkusz bez danych w zadnym roku ma status `no_coverage`
(`Warning:` R5); arkusz z danymi tylko poza przedzialem to
`YearRangeError` i przerwanie CALEJ listy przed pobraniem, rowniez przy
samym `--min-year`. Nieudane sprawdzenie skorowidza tez przerywa liste.

**WCS (`download_bbox`) w bibliotece: NMT/NMPT 1 m i orto.**
CLI PL uzywa WCS tylko z `--target-crs` (sekcja 4.3); bez tej flagi
pobiera arkusze OpenData. `DownloadManager.download_bbox` /
`GugikProvider.download_bbox` dla NMT 1 m i
`GugikNmptProvider.download_bbox` dla NMPT daja jednopasmowy GeoTIFF
float32 z wysokosciami na siatce 1 m EPSG:2180 (bez nodata i maski PRG).
Dla NMT 5 m WCS nie istnieje. NMT KRON86: endpoint
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

### 4.3 Bbox / geometria PL z `--target-crs` (ADR-035)

CLI `download --bbox`/`--geometry --target-crs` oraz biblioteczne
`download_pl_cutout()` pobieraja NMT albo NMPT 1 m z WCS GUGiK, nie
mozaikuja arkuszy. Biblioteka: `prepare_pl_cutout(bbox, target_crs, ...)`
przygotowuje `PlCutout` bez sieci (takze z `product="nmpt"`).
`run_pl_wcs_cutout(cutout, *, provider=None, parent_request=None, today=None)`
wykonuje pobranie i zwraca `PlCutoutResult`; fabryka
`download_pl_cutout(..., product="nmt"|"nmpt", output_dir=...)` wykonuje
oba kroki. Wstrzykniety provider musi odpowiadac produktowi, pionowi
i rozdzielczosci.

1. `run_pl_wcs_cutout`/`download_pl_cutout` odrzucaja rozdzielczosc inna
   niz 1 m (`ValidationError`; CLI `Error:`), a `prepare_pl_cutout`
   nieobslugiwany pion/CRS docelowy
   (`EPSG:2180`, `EPSG:5514`, `EPSG:3045`) i brak bezpiecznej
   przypietej operacji transformacji. Bbox docelowy wyznacza bbox
   zrodla EPSG:2180; dla warpu ma on zapas 4 px na interpolacje.
   `--geometry` daje obwiednie calej geometrii, bez maskowania do jej
   obiektow. `--system 2000`, `--target-crs` z godlem lub z orto/LAZ
   nadal sa odrzucane przed pobraniem.
2. `run_pl_wcs_cutout` pobiera i buduje maske ladu PRG **przed**
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
   `<coords>_<YYYYMMDD>.tif` (+ `.meta.json`), gdzie `<coords>`
   opisuja bbox zadania W UKLADZIE WYNIKU, nie wyrownany raster.
   Kazde uruchomienie pobiera od nowa, `--force`, `--workers` i
   `--scale` nie zmieniaja toru WCS. Tego samego dnia podmiana
   jest atomowa dopiero po sukcesie: awaria pozostawia poprzedni
   plik i sidecar, bez pustego drzewa `bbox/`. Sidecar z
   `capability="bbox_raster"`, `extra.source` WCS i `extra.mask`
   PRG opisano w sekcji 3.2. CLI wypisuje `Info:` z liczba zapytan
   WCS dla > 1 kawalka lub wyniku >= 1 GiB.

WCS oddaje kompozycje serwera (najnowszy lot obszaru bez doklejania
starszych), **nie** najnowsza kampanie dokladnie 1 m wybrana dla arkusza
przez ADR-028. Nad lotem 0,5 m wynik 1 m to decymacja (piksel 0,5 m
o srodku na pelnym metrze), nie srednia 2 x 2. Gdy loty sa te same
i siatki sa zgodne, zmierzone WCS i arkusz sa bit w bit zgodne
(`docs/research/2026-10-10-wcs-limits/raport.md` pkt 4, 8 oraz
`docs/research/2026-10-11-wcs-cutouts/raport.md` pkt 2-4).
`--year`, `--min-year`, `--max-year`, `--all-campaigns` i
`--full-sheet` z `--target-crs` pozostaja `Error:` przed siecia;
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

Jeden wycinek `exportImage`. Bbox jest najpierw normalizowany do ukladu WYNIKU
(`--target-crs` albo natywny EPSG:5514), zeby nazwa pliku niosla wspolrzedne
faktycznie zadanego wycinka. Zadanie do serwera idzie natywnie; przy
`--target-crs` innym niz 5514 tresc reprojektuje lokalny warp
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

Od 0.7.1 tor bbox CZ jest w bibliotece (`download/cz_cutout.py`, A6
Hydrografa): `run_cz_cutout(provider, bbox, output_dir=, image_crs=,
force=, parent_request=, on_download=)` robi normalizacje bboxa, sciezke,
pobranie, kontrole nodata i sidecar; CLI (`_cz_download_bbox`) tylko
drukuje komunikaty. `image_crs` (uklad wyniku, `None` = natywny EPSG:5514)
podaje wywolujacy jawnie — CLI z `--target-crs` — a nie odczyt atrybutow
providera. `download_cz_cutout(bbox, output_dir=, target_crs=,
vertical_crs=, resolution=)` buduje providera (`create_dmr_provider`)
i wola `run_cz_cutout`. Siatka wyniku startuje od zadanego bboxa
przeliczonego do ukladu wyniku, dokladnie jak w CLI przed 0.7.1;
wyrownania do siatki PL nie ma (osobny spec razem z R6). Wynik
`CzCutoutResult(path, skipped, all_nodata)`: rastr bez ani jednego
waznego piksela powstaje, ma `all_nodata=True`, `extra.all_nodata: true`
w sidecarze (przy danych `false` — klucz jest zawsze) i `logger.warning`;
CLI wycisza na czas wywolania ten logger (`_library_log_muted`), bo drukuje
wlasna linie `Warning:`. Kontrola jest best-effort: nieczytelny plik daje
`all_nodata=False` (log debug), nigdy przerwania po udanym pobraniu.
Pominiety istniejacy plik (`force=False`) zwraca `skipped=True`
z flaga `all_nodata` odczytana z pliku; sidecar zostaje bez zmian.
Nieudane pobranie usuwa pusty katalog `<segment>/bbox/` i przekazuje
wyjatek dalej.

Wynik: `data/nmt/cz_dmr5g_<vcrs>/bbox/<coords>.tif` (+ `.meta.json`).

### 4.6 Dyspozycja per kraj (`--country auto`)

Podzial na kraje jest w bibliotece (`download/countries.py`, od 0.7.1;
CLI importuje te same funkcje): `countries_for_bbox` porownuje bbox
(w WGS84) z `CountryProfile.extent_wgs84`
kazdego kraju z rejestru. Obwiednie sa **prostokatami**, nie wielokatami
granic, wiec obszar w glebi jednego kraju rutynowo trafia takze do drugiego.
Konsekwencje: (1) obszar przecinajacy oba prostokaty pobiera sie z KAZDEGO
kraju — osobne pliki i sidecary, wspolny `parent_request`; (2) na obszarze
spornym flaga bez odpowiednika czeskiego (`--product nmpt|orto`, `--system`,
`--vertical-crs KRON86`, `--resolution 1m`) ROZSTRZYGA kraj do `pl`
z komunikatem `Info:` zamiast przewracac zadanie; (3) porazka jednego kraju
przy sukcesie drugiego daje kod 0 i `Warning:` — kod 1 zostaje dla jawnego
`--country` i dla porazki wszystkich krajow. `Info:`/`Warning:` ida na stderr,
wiec `-q` ich nie tlumi. `--target-crs` NIE rozstrzyga kraju w zadna strone,
bo od ADR-027 dziala po obu stronach granicy.

Czesc zadania dla kazdego kraju jest pod `auto` PRZYCINANA do jego
prostokata (`country_bbox`; komplet czesci dla `auto` daje
`split_bbox_by_country(bbox, cz_crs=)` — czesc CZ w `cz_crs`, czesc PL
w ukladzie bboxa). `country_bbox` zmienia tylko obciete krawedzie PL —
pozostale niosa oryginalne wspolrzedne; CZ pozostaje przeliczany
przez WGS84. Przed pobraniem CLI drukuje `Info:` o przycieciu oraz
o obszarze pozostawionym poza oboma prostokatami (takze naroznym).
Nazwa pliku i `request.bbox` niosa bbox przyciety, oryginal tylko
w `extra.parent_request`. Tryb listy PL (`--bbox` bez `--target-crs`)
wyznacza arkusze z przycietego bboxa, a ich sidecary maja `request.sheet`
(oryginal: `extra.parent_request.bbox`). Przy geometrii bez `--target-crs`
arkusze PL wyznacza sama geometria (cala), wiec CLI nie drukuje `Info:`
o przycieciu PL ani o obszarze poza prostokatami
(`_print_clipping_info(pl_geometry_sheets=True)`); czesc CZ nadal jest
przycinana i komunikowana. Jawny
`--country pl` nie przycina; bbox w calosci poza prostokatami =
`Error:`, kod 1 bez sieci. Poza obwiednia CZ przy granicach
DE/SK/UA/BY/LT/RU `auto` odpytuje tylko PL; w prostokacie CZ
dochodzi CUZK nawet nad Polska/Saksonia, bo obwiednia nie jest
wielokatem granicy. Wynik calkowicie nodata (CZ albo wycinek PL
z pobranymi arkuszami) daje `Warning:` i kod 0. Sukces czesciowy
PL lub CZ pod `auto` daje kod 0, `Warning:` przy awarii drugiej
czesci; `--resolution 1m` rozstrzyga do PL. Bez `--vertical-crs`
pogranicze daje PL w EVRF2007 i CZ w Bpv; CLI drukuje jeden `Info:`
przed pobraniem z obiema nazwami i podpowiedzia
`--vertical-crs EVRF2007` dla wspolnego ukladu, takze z `-q`.
Jawny uklad pionowy lub zadanie tylko dla jednego kraju nie daje tego
komunikatu. Poniewaz podzial opiera sie na prostokatach, komunikat moze
pojawic sie takze wtedy, gdy czesc CZ okaze sie calkowicie nodata.

Opcje kampanii i flagi roku (ADR-030/032; erraty Q9, N-3) dotycza
tylko PL; `_reject_campaign_opts_without_pl(args, countries)` obsluguje
wszystkie wejscia: zadanie bez PL (godlo CZ pod `cz`/`auto`, jawne
`--country cz`, obszar w calosci CZ pod `auto`) z `--all-campaigns` lub dowolna
flaga roku = `Error: CZ (CUZK) nie ma kampanii —
--all-campaigns/--min-year/--max-year/--year dotycza tylko PL`,
kod 1 bez sieci. Dla obszaru PL+CZ pod `auto` wypisuje raz
`Info: --all-campaigns/--min-year/--max-year/--year dotycza tylko czesci PL
(CZ: biezaca wersja danych CUZK)`; czesc CZ jest pobierana.
Flagi roku nie naleza do `_pl_only_flags` i nie zwezaja `auto` do PL.

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
`GugikLazProvider.select_tiles` -> `run_laz_download`, albo jednym
wywolaniem `download_laz_area(bbox_2180, ...)`. CLI (`_cmd_download_laz`)
sprowadza wejscie (godlo do 1:10000, `--bbox`, `--geometry`) do bboxa
EPSG:2180, drukuje komunikaty i tlumaczy wynik na kod wyjscia.
Discovery idzie przez
**WFS** `GetFeature` (WMS skorowidzy LAZ zwraca 401 — ADR-021), a kafle
pobierane sa rownolegle. WFS `urn:ogc:def:crs:EPSG::2180` oczekuje
osi (N,E): bbox jest wysylany, a `gml:Envelope` i rama `msGeometry`
czytane w tym porzadku, potem kafle sa filtrowane rzeczywistym przecieciem.
GetCapabilities ustala roczniki (bez zaszytej listy); jawny `--year`
nieobecny w usludze wysokosciowej = `DownloadError` z lista
dostepnych rocznikow, przed GetFeature;
przedzial bez rocznika uslugi rowniez daje `DownloadError`. Przy fladze
roku WFS odpytuje WSZYSTKIE roczniki dla referencji, przed pobraniem.
Jesli ktorykolwiek rocznik zawiedzie po ponowieniach, `select_tiles`
rzuca `DownloadError` zamiast zgadywac brak kafli. Gdy wszystkie
odpowiedza i nie ma zadnych kafli, CLI drukuje `No LAZ tiles found`
(`download_laz_area`: `NoCoverageError`).

**Flagi roku wspolne, `--min-density` tylko LAZ (ADR-032).**
`--year`/`--min-year`/`--max-year` dla NMT/NMPT/orto ida do
`DownloadManager` (4.1), dla LAZ do `_cmd_download_laz`;
`--min-density` dla innych produktow = `Error:` przed siecia
(`_reject_laz_only_opts`). `--year` z dowolna granica roku =
`Error: --year wyklucza sie z --min-year/--max-year` przed siecia,
takze w LAZ. Zadanie wylacznie CZ z flagami roku = `Error: CZ (CUZK)
nie ma kampanii` (4.6). Wycinek `--target-crs` z flaga roku = `Error:`
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

Uklad katalogow ADR-026 tych zrodel nie dotyczy (`storage_subdir = None`).
Zmiany od 0.6.x (szczegoly: `docs/CHANGELOG.md`): sidecary wynikow,
rozszerzenie pliku z faktycznego formatu (N14), SHP BDOT10k jako `.zip`
(N1), sidecar wyniku HSG, scalanie GPKG BDOT10k w lokalnym katalogu
tymczasowym. `LandCoverManager` ma **wlasny domyslny katalog**
(`./data/landcover`, CLI `--output`) i wlasna konwencje nazw plikow
(`_generate_output_path`): `<zrodlo>[_<parametr>...]_<tryb>_<id>.<ext>`,
gdzie `<zrodlo>` to klucz `--source` (`bdot10k`/`corine`/`soilgrids`;
provider spoza rejestru: nazwa malymi literami, spacje -> `_`), `<tryb>_<id>`
to `teryt_<teryt>`, `bbox_<minx>_<miny>_<maxx>_<maxy>` (EPSG:2180, liczby
calkowite; `--geometry` = obwiednia) albo `godlo_<godlo>` — z wyjatkiem
BDOT10k, ktorego plik nazywa sie ZAWSZE `teryt_<teryt>` (nizej), a parametry to
KAZDA opcja zmieniajaca tresc wyniku, z wartoscia domyslna wlacznie
(`LandCoverManager._content_params`, U3):

| Zrodlo | Parametry w nazwie | Przyklad |
|---|---|---|
| SoilGrids | `<property>_<depth>_<stat>` | `soilgrids_clay_0-5cm_mean_bbox_770000_509000_772000_511000.tif` |
| CORINE | `<year>` | `corine_2018_sheet_N-34-130-D.tif` (`.png` z podgladu WMS) |
| BDOT10k | opcjonalny filtr warstw `<kod>-<kod>...` (kody posortowane); `format` niesie rozszerzenie | `bdot10k_teryt_1465.gpkg`, `bdot10k_PTWP-SWRS_teryt_1465.gpkg` (`layers=`), `bdot10k_teryt_1465.zip` (SHP) |

Rozne parametry = rozne pliki; te same parametry = ta sama sciezka (ponowne
pobranie nadpisuje plik, land cover nie pomija istniejacych wynikow). Te
same wartosci trafiaja do sidecara `request` (`property`/`depth`/`stat`,
`year`, `format`, `layers`; klucze ADR-031) obok `teryt`/`bbox`+`bbox_crs`/`sheet`,
a `nodata` wyniku GeoTIFF jest czytane z pliku (`null`, gdy plik go nie
deklaruje — np. GeoTIFF z WCS SoilGrids bywa bez tagu NoData; Kartograf nie
dopisuje wartosci z dokumentacji zrodla). Nazwy sprzed 0.7.0
(`soilgrids_bbox_<coords>.tif`, `corine_land_cover_...`) nie sa rozpoznawane.
Rozszerzenie FAKTYCZNEGO pliku nadaje provider: BDOT10k `.gpkg`, CORINE
`.tif` (CLMS) albo `.png` (podglad WMS), SoilGrids `.tif`; zwracana
sciezka i sidecar dotycza tego pliku (review 2026-10-06 N14). BDOT10k
z `format="SHP"` (`--format SHP`) zapisuje oryginalne archiwum
GUGiK z shapefile'ami pod ta sama nazwa z rozszerzeniem `.zip`
(np. `bdot10k_teryt_1465.zip`, sidecar `bdot10k_teryt_1465.zip.meta.json`);
rozszerzenie nadaje `Bdot10kProvider.download_package`, a CLI drukuje
faktyczna sciezke (review 2026-10-06 N1). Sidecary pisze `LandCoverManager` tak samo jak
pozostale warstwy zarzadzajace.

**BDOT10k z wielu powiatow (od 0.7.1, A2).** Pakiet BDOT10k jest zawsze
pakietem CALEGO powiatu, wiec nazwa pliku i `request` sidecara opisuja
tresc: `bdot10k[_<warstwy>]_teryt_<TERYT>.<ext>`, `request = {teryt,
format[, layers]}` — takze przy zadaniu przez `--bbox`/`--sheet`/`--geometry`
(dawne nazwy `bdot10k_bbox_*`/`bdot10k_godlo_*` nie sa rozpoznawane).
Obszar zadania idzie do `extra.parent_request`: `{bbox, bbox_crs,
countries: ["PL"]}` albo `{sheet, countries: ["PL"]}`.
`LandCoverManager.download_all_counties(bbox=|sheet=, format=, layers=,
timeout=)` pyta PRG (`Bdot10kProvider.teryts_for_area` ->
`discover_teryts_for_bbox`, obszar w dowolnym obslugiwanym ukladzie) i
pobiera pakiet KAZDEGO powiatu przecinajacego obszar, w kolejnosci kodow,
przez `Bdot10kProvider.download_package(code, path, *, timeout, format,
layers, keep_raw, raw_path) -> Bdot10kPackage(path, teryt, url, format, http,
raw_path)`; jeden plik i sidecar per powiat (`_download_county`, jedyna
sciezka pobrania BDOT10k w menedzerze, takze dla `--teryt`); brak powiatu =
`NoCoverageError`, awaria PRG albo pakietu = `DownloadError` (pliki pobrane wczesniej zostaja). CLI
`landcover download --source bdot10k` z `--bbox`/`--sheet`/`--geometry`
wola te metode i drukuje `Downloaded to:` dla kazdego pliku; `--teryt`
bez zmian. Stare `download_by_bbox`/`download_by_sheet` (menedzera bez
jawnego `output_path` i providera) pobieraja JEDEN powiat ta sama sciezka
(`_single_teryt`): obszar z kilku powiatow konczy sie `ValidationError`
z lista kodow i wskazaniem `download_all_counties`. Opcja `timeout`
(provider: domyslnie 120 s; menedzer: gdy nie podana, PRG 30 s) dziala od
0.7.2 takze na zapytanie PRG, nie tylko na pobranie paczki. `layers=` (kody
4-literowe, np. `PTWP`, `SWRS`; tylko GPKG) zostawia w scalonym GPKG
wylacznie pliki `__OT_<kod>_*` pakietu — brakujaca warstwa to
`DownloadError`, zly kod `ValidationError` przed siecia; plik z filtrem
nosi token warstw w nazwie, bo nie jest juz pelnym pakietem. Scalanie
pakietu (`_merge_gpkg_files`) konczy sie `DownloadError`, gdy nazwa
tabeli powtarza sie w dwoch plikach pakietu (dotad druga kopia byla po
cichu pomijana); w prawdziwej paczce (63 pliki `..._<TERYT>__OT_<KOD>_<A|L|P>.gpkg`,
po jednej tabeli) duplikatow nie ma. CORINE bez credentials CLMS pobiera podglad
PNG przez WMS: sidecar ma wtedy `horizontal_crs` uslugi WMS (EPSG:3857, dla
rocznika 1990 EPSG:4326) oraz `extra.fallback = "wms_png"` i `extra.note`
(`"podglad WMS, nie dane"`).

BDOT10k GPKG: archiwum ZIP z GUGiK jest rozpakowywane, a warstwy scalane
w jeden GeoPackage w LOKALNYM katalogu tymczasowym (`tempfile`); do
`--output` trafia gotowy plik (kopia jako `<nazwa>.gpkg.<pid>_<tid>.tmp` + `os.replace`).
Powod: SQLite na udzialach CIFS/SMB bez blokad zakresow bajtow konczyl
scalanie bledem `database is locked` (`Bdot10kProvider._merge_gpkg_files`).

**Pochodzenie pakietu BDOT10k w sidecarze (od 0.7.1, A4).** Sidecar pliku
BDOT10k (`LandCoverManager._write_bdot_sidecars`) ma `extra.source = {url,
teryt, format}` (URL paczki OpenData, z ktorej powstal plik) oraz
`extra.http = {etag, last_modified, content_length}` — naglowki odpowiedzi
GUGiK zapisane tak, jak przyszly (brak naglowka = `null`, nic nie jest
zgadywane). Serwer paczek BDOT10k nie podaje dzis `ETag` ani
`Last-Modified` (ani w `HEAD`, ani w `GET`), tylko `Content-Length`, i
ignoruje `Range`; o zmianie paczki u zrodla mowi wiec glownie `sha256`
pliku. `keep_raw=True` (biblioteka: `download_package`, `LandCoverManager.
download*`; tylko GPKG — przy SHP `ValidationError`, bo wynik SHP to juz
oryginalny ZIP) zapisuje obok GPKG nietkniete archiwum GUGiK. Archiwum
to zawsze PELNY pakiet powiatu, wiec na sciezce standardowej nosi
standardowa nazwe BEZ tokenu warstw (A2): `bdot10k_teryt_<TERYT>_GPKG.zip`
(np. `bdot10k_teryt_1465_GPKG.zip`) — ten sam plik niezaleznie od filtra
`layers=` (menedzer podaje go jako `download_package(raw_path=)`); przy
jawnym `output_path` nazwe wybiera wywolujacy: `<rdzen output_path>_GPKG.zip`.
Archiwum ma wlasny sidecar (`request` jak pliku wyniku, ale bez `layers`,
np. `{teryt, format}`; `extra.source` bez `raw_file`; `sha256`/`size_bytes`
archiwum); sidecar GPKG dostaje wtedy
`extra.source.raw_file` = nazwa archiwum. Archiwum jest zapisywane
atomowo i dopiero po udanym scaleniu, wiec blad rozpakowania nie zostawia
ZIP bez sidecara. Scalony GPKG czeka w `<nazwa>.gpkg.<pid>_<tid>.tmp` i zastepuje
poprzedni plik dopiero po udanym zapisie archiwum (od 0.7.2): nieudany zapis
archiwum albo podmiany zostawia poprzedni GPKG i jego sidecar bez zmian
(przy pierwszym pobraniu — brak pliku), bo sidecar GPKG powstaje dopiero po
powrocie z `download_package`. Okno resztkowe: blad miedzy podmiana
archiwum i GPKG zostawia nowe archiwum ze starym sidecarem. Blad
wejscia-wyjscia przy rozpakowaniu (warstwy kopiowane strumieniowo), scalaniu
albo zapisie archiwum to `DownloadError`. `keep_raw` nie zmienia tresci GPKG, wiec nie trafia do
nazwy pliku ani do `request`. `extra.parent_request` (obszar zadania)
zostaje obok `source` i `http`.

`HSGCalculator` (`hydrology/hsg.py`) liczy grupy glebowe z warstw SoilGrids
(`clay`, `sand`, `silt`) wg kanonicznego trojkata USDA (ADR-025) i pisze
sidecar wyniku (`HSGCalculator._write_sidecar` -> `emit_sidecar`, best-effort):
deskryptor `global.isric.soilgrids`, `capability="bbox_raster"`, `request`
= bbox z jego ukladem (+ `sheet` = godlo, gdy zadanie szlo przez
`--sheet`/`calculate_hsg_by_sheet`; domyslna nazwa pliku CLI zawiera
glebokosc: `hsg_<godlo>_<depth>.tif`, `hsg_bbox_<depth>.tif`),
`horizontal_crs` = uklad rastra wyniku, `nodata: 0`,
`extra` = `{derived: "hsg", source_layers: ["clay", "sand", "silt"], depth,
stat, classes: "1=A, 2=B, 3=C, 4=D"}`.

`hsg_from_rasters(clay, sand, silt, *, bbox, crs, pixel_m, output_path)`
(od 0.7.1, A8) liczy HSG z gotowych rastrow (g/kg, SoilGrids) bez pobierania
i bez wartosci domyslnych: kazde wejscie jest reprojektowane przypieta
operacja (`CONTENT_POLICY`, bilinear; `warp_to_grid`) na siatke `crs`/`pixel_m`
zaczepiona w `bbox` (przeliczonym do `crs`), a klasyfikacja (`_classify_hsg`)
i zapis GeoTIFF (`_write_hsg_geotiff`) sa wspolne z
`HSGCalculator.calculate_hsg_by_bbox`. Nodata wejscia pochodzi wylacznie z
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
-> kod w `teryt_cache`; `kartograf cache stats` liczy oba w `TERYT entries`.

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
5. **Dyspozycja CLI**: dla nowego kraju dopisz galaz w `cli/download_cmd.py`
   (`_dispatch_area` -> `_run_<kraj>`) i uzupelnij checki
   `_validate_cross_country` / `_pl_only_flags` o opcje, ktore w tym kraju
   nie istnieja. Reprojekcje rob lokalnie, przypieta operacja — nigdy przez
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

---

## 6. Decyzje (ADR)

Indeks decyzji z tytulami, datami i statusami (relacje "zastapiona",
"uzupelniona") prowadzi `docs/DECISIONS.md` (sekcja "Indeks") — ten
dokument go nie powiela. Sekcje powyzej powoluja sie na numery ADR i ich
erraty tam, gdzie opisuja wynikajace z nich zachowanie kodu.
