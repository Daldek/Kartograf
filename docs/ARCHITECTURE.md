# Architektura Kartografa

**Wersja opisywana:** kod galezi, w ktorej lezy ten plik — nie stan na
konkretny dzien. Wersja pakietu: `src/kartograf/__init__.py` (`__version__`);
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
`src/kartograf/sources/registry.py`: kanaly dostepu, uklady poziome i pionowe,
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
(`AccessChannel.params`) konfiguruja generyczne silniki paczek jednostek,
obiektow obszaru i plikow feedu ATOM CUZK, wiec taki produkt nie ma
providera (sekcja 4.10); ortofoto CZ uzywa silnika ATOM we wlasnym torze
(sekcja 4.4), a kanaly WCS wycinka ortofotomapy PL (`WcsCutoutParams`)
konfiguruja `GugikOrtoProvider` (sekcja 4.3).

**Sidecar przy kazdym udanym pobraniu.** Obok kazdego pliku danych powstaje
`<pelna_nazwa_pliku>.meta.json` ze schema `kartograf-meta/1`: uklad poziomy
i pionowy, `nodata`, oryginalne zadanie, licencja, wersja pakietu, opis
wykonanych transformacji. Sidecary pisza **warstwy zarzadzajace** —
`DownloadManager`, `LandCoverManager`, wycinek PL w bibliotece
(`download/cutout.py::write_pl_wcs_cutout_sidecar`), kafle LAZ PL w bibliotece
(`download/laz.py::write_laz_sidecar`, ADR-029), pliki LAZ CZ
(`download/cz_laz.py`), wynik HSG
(`HSGCalculator._reuse_or_compute`, sekcja 4.8), rastry CZ (nizej),
ortofoto CZ (`download/cz_orto.py`, sekcja 4.4), wycinek ortofotomapy PL
(`download/orto_cutout.py`, sekcja 4.3) i pliki kolekcji
(`download/collections.py::run_job`, sekcja 4.10)
— nigdy providery; provider zwraca `Path`, metadane skladane sa pietro wyzej,
gdzie znany jest kontekst zadania. Wynika z tego, ze bezposrednie wywolanie
providera z biblioteki (np. `GugikProvider.download`,
`CuzkRasterProvider.download`/`download_bbox`, `CuzkLazProvider.download`)
zapisuje sam plik danych, bez sidecara — w szczegolnosci sidecar rastra CZ
pisze `download/cz_cutout.py::write_cz_sidecar` dla wycinka bbox
(`download_cz_cutout`, sekcja 4.5), a dla godla CZ `download_cz_sheet`
(`download/cz_sheets.py`), bo tory CZ omijaja `DownloadManager` (ADR-023).
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
`src/kartograf/transform/crs.py` — poza obwiednia w WGS84 do rozpoznania kraju
i przyciecia pod `auto` (`bbox_to_wgs84` w `download/countries.py`, takze dla
bboxa podanego w ukladzie czeskim) i obwiednia pliku geometrii w torze LAZ
(`download/area.py::geometry_envelope_2180`: `get_overall_bbox(..., target_crs="EPSG:2180")`).
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
Budowa grupy pomija wylacznie ostrzezenie pyproj `Best transformation is not
available` (brak siatki PROJ, np. CUZK na czystej instalacji): polityka wybiera
sama sposrod dostepnych operacji, a surowy `UserWarning` lamalby kontrakt
pustego stderr w `--json` (USAGE 9.2).
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

**Brak scalania miedzykrajowego (stan 0.8.0).** Zadanie obszarowe przecinajace
wiecej niz jeden kraj daje **osobne pliki i osobne sidecary per kraj**,
powiazane wspolnym `extra.parent_request`. Kartograf nie sklada
mozaiki transgranicznej i nie harmonizuje pionu miedzy krajami — pliki PL i CZ
scala konsument (Hydrograf). Scalanie PL+CZ w jedna ciagla powierzchnie
przygraniczna (wspolna siatka, EVRF2007 po obu stronach; R6, 2026-09-28,
wczesniej zapisane jako zadanie Hydrografa) to zadanie bez przypisanego
wydania (`docs/SCOPE.md` 3.1; dane styku zmierzone na zywo 2026-09-29 —
sekcja 4.6). Kartograf dostarcza wszystko,
czego takie scalenie wymaga: jawne kody CRS obu osi, `nodata`, opis uzytej
operacji z dokladnoscia i wspolny klucz grupowania.

---

## 2. Warstwy i zaleznosci modulow

Graf krawedzi importu miedzy pakietami najwyzszego poziomu `kartograf/`.
`(l)` = krawedz WYLACZNIE leniwa (import tylko wewnatrz funkcji); bez znaku =
co najmniej jeden import na poziomie modulu (takze pod `if TYPE_CHECKING:`).
`kartograf` = pakiet glowny (`src/kartograf/__init__.py`):

```
kartograf ──> core, download, providers, landcover, hydrology, cache,
        sources, transport, notices, project, store, store_geometry,
        transform, catalog, commands, error_report, sheet_info,
        source_info, cache_info, store_documents    # re-eksport Public API
__main__ ──> cli
cli ──> catalog, commands, error_report, sheet_info, source_info,
        cache_info, download, landcover, hydrology, notices, project,
        sources, interrupt, kartograf
mcp_server ──> catalog, commands, error_report, download, cache, kartograf
        # SDK `mcp`, `anyio`, `jsonschema`: tylko leniwie, w create_server
commands ──> catalog, project, download, cache, notices
catalog ──> sources, download, landcover, hydrology, providers, core,
        error_report, _version, kartograf (l)
error_report ──> transform, interrupt, catalog (l)
sheet_info ──> catalog, core
source_info ──> download, landcover, providers, sources
cache_info ──> cache, notices
store_documents ──> download, store
project ──> download, landcover, hydrology, sources, cache, catalog,
        notices, _version, kartograf (_clock)
download ──> providers, sources, transform, core, cache, notices,
        _version, kartograf (_clock), transport, interrupt
landcover ──> providers, download, core, cache, sources, notices, transport,
        interrupt
hydrology ──> core, download, landcover, cache (TYPE_CHECKING), notices,
        providers (l), sources (l), transform (l)
providers ──> sources, transform, transport, core, cache, notices,
        auth (l), download (l), interrupt
sources ──> core, kartograf (_clock), _version
transport ──> transform, core, sources, cache, notices, providers,
        interrupt, kartograf (l, __version__)
transform ──> core, sources (TYPE_CHECKING), transport (TYPE_CHECKING)
cache ──> core (TYPE_CHECKING), notices
_version ──> kartograf (l, __version__)
store ──> core, download, sources, providers (l)
store_geometry ──> core, transform, store (typy pod TYPE_CHECKING; w czasie
        dzialania takze leniwy import `read_sidecar`), providers (l),
        transport (l)
_clock, notices, auth, interrupt ──> (nic wewnetrznego)
core ──> (nic poza exceptions i serialization)
exceptions ──> serialization (koder dla `details()`; krawedzie DO niego
        pominiete powyzej — importuja go kartograf, cli, core, sources,
        transform, transport, providers, download, landcover, hydrology,
        cache, project, store, store_geometry, error_report, catalog)
serialization ──> (lisc, nic wewnetrznego; krawedzie DO niego pominiete jak
        do exceptions — importuja go typy wyniku: Document, EncodeContext)
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

- `store` i `store_geometry` (odczyt magazynu, sekcja 3.3.1) tylko czytaja:
  korzystaja z regul zapisu `download` (`links.linked_version`, stale
  `versions`) i rejestru `sources`, bez `DownloadManager`; zaden modul
  pobierania nie importuje `store`.
- `core` nie importuje nic spoza `core` i `exceptions` — takze leniwie.
  Kierunek jest odwrotny: `providers.cuzk.sheets`
  i `core.parser_tm33` importuja wzorce godel CZ z `core.parser_registry`.
  Operacja przypieta (ADR-024) wchodzi do `core.bbox.transform_bbox`
  przez duck typing (`transformer=`), bez importu `transform`.
- `download` siega po `transform` w `download/cutout.py` (wycinek PL,
  sekcja 4.3) i leniwie w `download/collections.py` (zapis GPKG wyniku
  obszaru, sekcja 4.10). Po `transport` siega leniwie w
  `download/cutout.py` i `download/cz_cutout.py` oraz na poziomie modulu
  w `download/cz_sheets.py` i `download/cz_laz.py` (`response_signal`).
  `cutout.py` importuje na
  poziomie modulu `transform.crs` (`PinnedTransform`, `CONTENT_POLICY`,
  `WARP_MARGIN_PX`), leniwie `build_pinned_transform`, `transform.raster`
  (warp wycinka WCS), `transport.aaigrid`, `transport.chunks` i
  `transport.mosaic.has_valid_pixels`; `cz_cutout.py` importuje leniwie
  ostatnia funkcje (kontrola `all_nodata`).
  `manager.py` i `storage.py` nie importuja zadnego z nich —
  `DownloadManager` pozostaje warstwa koordynacji arkuszy.
  `download/cz_orto.py` (ortofoto CZ, sekcja 4.4) importuje na poziomie
  modulu `transport.atom` (feedy ATOM, czlony ZIP) i `transport.http`
  (`SessionPerThread`), a leniwie `providers.cuzk` (`SheetIndex`,
  `bbox_to_crs`, `wkid`); `download/orto_cutout.py` (wycinek ortofotomapy,
  sekcja 4.3) - na poziomie modulu `transport.chunks` (`align_bbox`,
  `GridSpec`) i `providers.pl.gugik_orto` (kanal WCS wycinka,
  `GugikOrtoProvider`).
- `download/collections.py` (kolekcje, ADR-042, sekcja 4.10) importuje na
  poziomie modulu `transport.http` (`SessionPerThread`, `head_signal`),
  `transport.unit_package` (paczki jednostek) i `transport.atom` (plik
  krajowy z feedu ATOM), a leniwie - dopiero dla
  wyniku obszaru - `transport.feature_bbox.fetch_features`
  i `transform.gpkg.write_gpkg`: GDAL wektorowy (`pyogrio`) laduje sie
  tylko wtedy, gdy zadanie pobiera obiekty uslugi. Z `providers` bierze
  `providers.pl.prg.discover_teryts_for_bbox` (powiaty obszaru)
  i `WOJEWODZTWO_NAMES`, leniwie `providers.cuzk.raster.bbox_to_crs`.
- `cli` tylko tlumaczy flagi na argumenty funkcji poziomu komendy
  i wypisuje wynik (Z1, Z8; ADR-037, ADR-046): parser buduje z deklaracji
  katalogu (`catalog.cliparser`; `cli/_parser.py::create_parser` to fasada),
  handler komendy wybiera po jej id (`cli/_handlers.py::HANDLERS`), flagi
  zamienia na argumenty funkcji przez `catalog.kinds.convert_arguments`
  (`cli/_args.py::library_arguments`) i wola funkcje poziomu komendy:
  `download.data` (`download_data`/`check_data`), `download.availability`
  (`check_availability`, ADR-041), `download.collections`
  (`download_collection`/`check_collection`), `landcover.manager`
  i `hydrology`; `parse`, `list-sources`, `list-layers`, `cache` i `catalog`
  ida przez `sheet_info`, `source_info`, `cache_info` i `catalog.get_catalog`,
  a `project add` przez `commands.parse_command`. Wynik drukuje: tryb `--json`
  (`cli/_json.py`) to `Document.to_json()`, tryb tekstowy renderuje te same
  dokumenty (tabele, linie statusu, pasek postepu z
  `download.manager.DownloadProgress`), a `main` zamienia wyjatki na
  `error_report` i kody wyjscia 0/1/2/130/143. Z `download` bierze ponadto
  `download.plan`/`fetch` (plik planu, `UpdateMode`, `VersionedFile`) i
  `download.options` (`output_required`, `require_product`), z `sources.variants`
  tabele wariantow, z `notices` komunikaty, z `project.commands` `task_command`.
  Nie importuje `providers`, `transport`, `transform`, `core` ani doboru
  arkuszy (`tests/contract/test_cli_translation.py::test_cli_imports_no_data_logic`
  dopuszcza ponad to tylko `catalog` i `serialization`).
- Rejestr wariantow `sources/variants.py` (ADR-041) to czyste dane:
  importuje tylko `exceptions`, `sources.descriptor` i
  `core.parser_registry.detect_system` (system godla CZ: `sm5`/`tm33`),
  a `sources.registry` leniwie (rejestr buduje deskryptory z typow tego
  modulu). Czytaja go `download/options.py` (walidacja), `download/area.py`
  (`pl_only_flags`), `download/storage.py`, `download/cutout.py` (wariant
  z kanalem WCS), `download/data.py`, `download/cz_sheets.py`,
  `download/cz_laz.py`, `download/availability.py`, providery PL
  (wariant, `IndexRef`) i CZ (`find_cz_variant`, `find_cz_laz_variant`)
  oraz `cli`.
- `download/availability.py` (raport, sekcja 4.9) importuje na poziomie
  modulu `providers.pl.skorowidz_wfs` (ten sam klient i parser rekordow
  co pobieranie arkuszy), `providers.pl.prg` (maska ladu),
  `providers.pl.gugik_laz.laz_tile` (parser kafla LAZ),
  `providers.cuzk.sheets.SheetIndex` i `providers.cuzk.raster.bbox_to_crs`
  (arkusze CZ, plan B) oraz `transport.http` (`SessionPerThread`,
  `head_signal`); nie importuje `DownloadManager` ani magazynu.
- `project` (`model`, `commands`, `manifest`, `operations`) mapuje komendy danych
  na funkcje biblioteki `download`/`landcover`/`hydrology`; nie implementuje
  logiki per produkt. Nazwy i rodzaje opcji komend danych (`TaskCommand.options`)
  pochodza z katalogu (`Command.task_options`; konwersja JSON <-> argumenty:
  `catalog.kinds`), stad krawedz `project ──> catalog`. `cli/project_cmd.py` tylko
  tlumaczy argumenty i wypisuje wyniki API projektu (ADR-037, ADR-040).
- `serialization` (sekcja 3.6) jest lisciem jak `exceptions`: typy wyniku dziedzicza
  z mixinu `Document`, a `exceptions` uzywa kodera w `KartografError.details()`;
  `core.bbox` importuje tylko `EncodeContext` (hak `BBox.__json__`).
- `catalog` (sekcja 4.11) opisuje komendy: deklaracje w `catalog/commands/*` czytaja
  rejestr zrodel i stale walidatorow (`sources`, `providers`, `download`, `landcover`,
  `hydrology`) oraz `core` (godla, bbox), a `catalog.build` bierze tabele kodow z
  `error_report` (`ERROR_CODES`, `EXIT_CODES`). Jedyna krawedz zwrotna to leniwy import
  `catalog.hints` w `error_report` (przyklad komendy w podpowiedzi bledu). Biblioteka,
  w tym `catalog`, nie importuje `cli` ani `mcp` (test w czystym procesie).
- `commands` (KB-2..KB-5) laczy `catalog` (deklaracje, `convert_arguments`,
  `parsed_options`), `project.commands` (walidacja i wykonanie zadania danych:
  `task_command`) i `download` (`UpdateMode`, `UpdatePlan`, `DownloadProgress`).
- `sheet_info`, `source_info`, `cache_info` i `store_documents` sa raportami z logika
  przeniesiona z CLI (Z1): `describe_sheet`/`find_sheets` (`core`, `catalog`:
  `SheetInfo.commands` z `ParamInfo.accepts`), `list_sources`/`list_layers`
  (`sources`, `providers`, `landcover`, `download`), `get_cache_info`/
  `get_cache_path`/`clear_cache` (`cache`, `notices`), `describe_store`/
  `list_store_entries`/`read_store_sidecar` (`store`, `download`); zaden nie importuje `cli`.
- `mcp_server` jest jedynym modulem, ktory dotyka SDK `mcp` (oraz `anyio` i
  `jsonschema`), zawsze leniwie w `create_server`: `import kartograf` i `import
  kartograf.mcp_server` dzialaja bez `mcp`. Narzedzia jako dane daje
  `catalog.tools` (bez `mcp`), wykonanie `commands`, bledy `error_report`.
- `transport ──> transform`: `transport/mosaic.py` owija zrodla mozaiki
  w VRT przez `transform.raster` (`vrt_xml`, `VRT_TYPES`; import na poziomie
  modulu). `transform` siega po `transport` i `sources` wylacznie pod
  `if TYPE_CHECKING:` (adnotacje `FeaturePages`/`LayerPages`
  i `FeatureBBoxParams` w `transform/gpkg.py`) — w czasie wykonania cyklu
  nie ma.
- `transport ──> sources`: silniki kolekcji (`transport/unit_package.py`,
  `transport/feature_bbox.py`, `transport/atom.py`) czytaja typowane
  parametry kanalu (`UnitPackageParams`, `PackageVariant`,
  `FeatureBBoxParams`, `FeatureLayer`, `AtomFilesParams` z
  `sources/descriptor.py` — dane bez IO), a `transport/atom.py` takze
  `sources.edition.edition_label` (etykieta wydania); `sources` nie
  importuje `transport`.
- `transport ──> cache`: `transport/atom.py` trzyma indeks feedu uslugi
  ATOM w `MetadataCache` (tabela `atom_cache` z `ETag` feedu, ADR-042
  D12); `cache` nie importuje `transport`.
- `transport ──> notices`: silniki kolekcji (`transport/unit_package.py`,
  `transport/atom.py`) skladaja komunikaty bledow z `notices` (`count_text`,
  `FILES`, `cli_flag`); `notices` nie importuje nic wewnetrznego.
- `transport ──> providers`: jedyna krawedz to `transport/index_records.py`
  (rekordy indeksow plikow, ADR-043), ktory na poziomie modulu importuje
  `providers.pl.skorowidz_wfs` (`WfsIndex` i stale zapytan WFS). Krawedz
  odwrotna `providers ──> transport` biegnie do `transport.http`, a
  `transport.index_records` importuje tylko `download.collections`, wiec
  cyklu modulow nie ma.
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
  `PlanItem`, `MetadataCache`...; wg reguly grafu to import
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
- Krawedz `download ──> providers` siega tez do toru CZ:
  `download/cutout.py` i `download/area.py` importuja leniwie generyczny
  `bbox_to_crs` z `providers/cuzk/raster.py` (ADR-024); przeniesienie go do
  `transform/` zostaje w backlogu (plan B przemianowal tylko `dmr.py`
  na `raster.py`).

### Moduly

Drzewo wymienia kazdy modul `.py` pakietu (`auth/` i `cli/` zbiorczo,
`__init__.py` podpakietow tylko gdy niosa wlasna logike). Zrodlo prawdy:
pliki `.py` pod `kartograf/`; Public API: `src/kartograf/__init__.py` (`__all__`).

Stabilne API transportu i mozaiki (od 0.7.1): `get_with_retry` (dowolny URL
uslugi, polityka ponowien siec/429/5xx/`Retry-After`, tylko GET),
`make_gugik_session`, `mosaic_and_crop`, `check_source_grid` — eksportowane
z `kartograf`; zmiana sygnatury = zmiana lamiaca w CHANGELOG.

```
kartograf/
├── __init__.py          # Public API (BBox, SheetParser, DownloadManager, providery, ...)
├── _version.py         # build_version() — identyfikator wersji dev (git, leniwie)
├── __main__.py          # `python -m kartograf` = skrypt `kartograf` (cli.commands.main)
├── py.typed             # znacznik PEP 561: mypy konsumenta widzi typy biblioteki
├── serialization.py     # Document (mixin dataclass: to_dict/to_json, `schema` pierwszym
│                        # kluczem), encode/EncodeContext (koder: Path, Decimal, BBox, Notice,
│                        # hak __json__), SCHEMAS (rejestr schematow kartograf-*/1); lisc
├── exceptions.py        # KartografError(.code, .exit_code, .hint, DETAIL_FIELDS, .details());
│                        # ValidationError(.option, .options, .allowed) -> UsageError(.command),
│                        # ParseError (kod 2); DownloadError(.sheet, .status_code)
│                        # -> NoCoverageError(DownloadError; .hints) — zrodlo nie ma danych
│                        # arkusza, .hints = podpowiedzi (np. --scale 1:2000), YearRangeError;
│                        # CacheError; InvalidSidecarError(.path) — nieczytelny sidecar (read_sidecar);
│                        # kody bledow i kody wyjscia: USAGE 9.3
├── error_report.py      # ErrorReport (kartograf-error/1), error_report(exc, command=):
│                        # wyjatek jako dane (io_error, interrupted, terminated, internal_error
│                        # buduje tu), ERROR_CODES/EXIT_CODES - jedyne zrodlo tabel USAGE 9.3 i katalogu
├── interrupt.py         # Przerwanie: run_parallel (pula z anulowaniem kolejki i flaga stopu dla
│                        # trwajacych jednostek), check_stop, Stopped/Terminated, sigterm_interrupts
├── core/                # Logika bazowa, bez IO sieciowego
│   ├── bbox.py             # BBox, validate_bbox, transform_bbox (gesta obwiednia: _DENSIFY
│   │                       # punktow na krawedz, cache transformerow, operacja przypieta
│   │                       # przez duck typing `transformer=`), is_czech_crs
│   ├── sheet_parser.py     # SheetParser (PL-1992), find_sheets_for_bbox (BBox z core/bbox.py)
│   ├── parser_2000.py      # Parser2000 (PL-2000), find_sheets_2000_for_bbox
│   ├── parser_tm33.py      # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045)
│   ├── parser_registry.py  # Rejestr systemow godel (SYSTEMS: pl2000, cz_tm33, cz_sm5,
│   │                       # pl1992), detect_system/path_parts ze strip(), wzorce CZ
│   │                       # (SM5: 2 albo 4 litery + 2 cyfry, np. CTES96, AS91)
│   ├── geometry.py         # Czytanie SHP/GPKG, resolve_layer (wybor warstwy),
│   │                       # find_sheets_for_geometry, get_overall_bbox
│   └── coverage.py         # Wypukle wielokaty: przeciecie, roznica, bufor (wybor kafli LAZ)
├── sources/             # Deskryptory zrodel jako dane (zero IO przy imporcie)
│   ├── descriptor.py    # SourceDescriptor (+ resolve_subdir, variants), AccessChannel,
│   │                    # TransportKind, TileScheme, LicenseInfo, CountryProfile;
│   │                    # parametry kanalow kolekcji (AccessChannel.params, ADR-042):
│   │                    # UnitPackageParams/PackageVariant, FeatureBBoxParams/FeatureLayer,
│   │                    # AtomFilesParams (feed ATOM CUZK), WcsCutoutParams (wycinek orto)
│   ├── registry.py      # Rejestr PL/CZ/EU/GLOBAL: get_source, sources_for, get_country,
│   │                    # all_countries, vertical_crs_code, resolve_vertical_crs (rodzina ->
│   │                    # realizacja), parse_pl_system, horizontal_crs_for_sheet/_for_system;
│   │                    # channel_for/channel_signal (kanal po transporcie i ukladzie, CZ_SYSTEM_CRS);
│   │                    # deskryptory NMT/NMPT per (produkt, format, rozdzielczosc) z wariantami
│   ├── variants.py      # Rejestr wariantow (ADR-041): IndexRef, FileFormat/FORMATS, ProductVariant,
│   │                    # variants(), resolution_label/parse_resolution (etykiety K2),
│   │                    # source_format (twardy filtr formatu), variant_error/find_variant;
│   │                    # CZ (plan B): CZ_MODELS, cz_sheet_system, find_cz_variant/
│   │                    # cz_variant_error (trasa rastra), find_cz_laz_variant/cz_laz_error
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
│   │                    # package_url ({teryt}, {woj}, {sheet}, {ku}, {theme}), fetch_package (Content-Length, katalog
│   │                    # ZIP, wymagane czlony, rozpakowanie jednego czlonu; 404 = NoCoverageError)
│   ├── feature_bbox.py  # Silnik obiektow obszaru (ADR-042 D3/D4): WFS 2.0 i ArcGIS REST —
│   │                    # metadane swiezo, liczba obiektow, strony po pozycji, kompletnosc;
│   │                    # count_features, fetch_features -> FeaturePages (strony na dysku)
│   ├── atom.py          # Silnik atom_files (ADR-042 D12): atom_index (indeks feedu uslugi
│   │                    # w cache z ETag), resolve_atom_file (feed zbioru -> plik, wydanie
│   │                    # z updated), check_atom_crs, atom_segment_tokens, fetch_atom_file
│   │                    # (rozmiar = length feedu), unpack_members (czlony ZIP 1:1)
│   └── index_records.py # Rekordy indeksow plikow (ADR-043): IndexRecord, gfi_records/
│                        # records_from_gfi (tabela linkow WMS GetFeatureInfo), wfs_records/
│                        # records_from_wfs (rekordy WFS, np. kafle mesh)
├── providers/           # Providery danych
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider, LandCoverProvider
│   ├── pl/              # GUGiK: gugik.py (NMT; jeden wariant rejestru na provider, P10,
│   │                    # index_sheets — arkusze archiwum ze skorowidza), gugik_nmpt.py,
│   │                    # gugik_orto.py (GugikImageProvider: arkusze obrazow ze skorowidza
│   │                    # WMS opisanego SheetIndexParams - ortofotomapa (GugikOrtoProvider,
│   │                    # barwy), intensywnosc, true orto, orto ukosna (provider na
│   │                    # kierunek, storage_suffix); wycinek WCS z kanalow rejestru:
│   │                    # coverage_choices, cutout_resolution_labels, wcs_cutout_channels),
│   │                    # gugik_laz.py (select_tiles, select_all_intersecting;
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
│   │                    # nadmiarowy wybor uslugi; file_sheets — arkusze plikow CUZK obszaru),
│   │                    # raster.py (CuzkRasterProvider — NMT DMR 5G/4G i NMPT DMP OK/1G,
│   │                    # route(): plik openzu albo ImageServer, opcjonalnie Bpv -> EVRF2007),
│   │                    # laz.py (CuzkLazProvider — LAZ DMR 5G/4G, DMP 1G/OK bez transformacji),
│   │                    # ruian.py (cadastral_areas_for_bbox — KU obszaru z RUIAN, mapa katastralna CZ),
│   │                    # __init__.py (create_cz_raster_provider — jedyne miejsce czeskich
│   │                    # domyslow)
│   ├── corine.py        # CORINE z Copernicus CLMS (+ fallback WMS PNG)
│   └── soilgrids.py     # SoilGrids z ISRIC (WCS)
├── _clock.py            # now() — jedno zrodlo czasu wynikow (sidecar, etykiety wersji,
│                        # plan); testy zgodnosci je zamrazaja (frozen_clock)
├── notices.py           # Notice(level, code, message), NoticeSink, kody komunikatow (Z3, ADR-037)
├── sheet_info.py        # describe_sheet -> SheetInfo, find_sheets -> SheetList
│                        # (kartograf-sheet/1, -sheets/1; logika `parse` przeniesiona z CLI)
├── source_info.py       # list_sources -> SourceList, list_layers -> LayerList
│                        # (kartograf-sources/1, -layers/1; rejestr zrodel, bez sieci)
├── cache_info.py        # get_cache_info/get_cache_path/clear_cache -> CacheInfo (kartograf-cache/1)
├── config.py            # ustawienia uzytkownika (DEV-18, ADR-050): nogat.toml, KARTOGRAF_*/NOGAT_*,
│                        # get_config -> Config (kartograf-config/1), check_config -> ConfigError
├── store_documents.py   # describe_store -> StoreOverview, list_store_entries -> StoreEntries,
│                        # read_store_sidecar -> StoreSidecar (odczyt magazynu jako dokumenty, ADR-045)
├── commands.py          # warstwa komend (KB-2..KB-5): parse_command, validate_command,
│                        # format_command, run_command, check_command, CommandCall
├── mcp_server.py        # serwer MCP (stdio; extra `mcp`, skrypt kartograf-mcp): create_server,
│                        # main, INSTRUCTIONS; jedyny modul dotykajacy SDK
├── catalog/             # Katalog komend - jedyne zrodlo prawdy (sekcja 4.11), bez importu cli/mcp
│   ├── spec.py          # Command, Param, Constraint, Example, Group (dane; dostawcy wartosci z rejestru)
│   ├── model.py         # dokument kartograf-catalog/1: Catalog, GroupInfo, ProductInfo, CommandInfo,
│   │                    # ParamInfo, ConstraintInfo, ExampleInfo, ExitCodeInfo, ErrorCodeInfo, SchemaInfo
│   ├── build.py         # get_catalog(group, command, params, tables), data_commands; widoki overview/full
│   ├── shared.py        # parametry wspolne komend (obszar, wyjscie, tryby aktualizacji, --json...)
│   ├── kinds.py         # rodzaje wartosci: parsery tekstow flag, convert_arguments (JSON opcji ->
│   │                    # argumenty biblioteki), options_from_json/options_to_json
│   ├── cliparser.py     # parser argparse z deklaracji: build_parser, parse_command_line, parsed_options
│   ├── formatting.py    # kanoniczna linia komendy (format_command_line)
│   ├── hints.py         # example_for, usage_hint (przyklad w podpowiedzi bledu)
│   ├── tools.py         # narzedzia MCP jako dane: tool_specs, check_arguments_schema, FAMILIES
│   └── commands/        # deklaracje, jeden modul = grupa (elevation, imagery, landcover, soil, boundaries,
│                        # cadastre, models3d, hydro, names, maps, geodesy, project, misc: parse, catalog,
│                        # cache i komendy tylko-API); _collection.py = ksztalt grup kolekcji
├── store.py             # Odczyt magazynu bez zapisu (ADR-045, 3.3.1): list_segments,
│                        # list_partitions, iter_store -> StoreEntry (units, partition,
│                        # skip_versions), read_sidecar -> Sidecar, describe_segment
│                        # -> SegmentInfo, link_target
├── store_geometry.py    # file_footprint -> Footprint (bbox zadania, godlo, naglowek,
│                        # indeks jednostek), pinned_transform (polityka obwiedni, per watek)
├── cache/metadata.py    # MetadataCache — SQLite WAL, thread-safe; tabele record_cache,
│                        # campaigns_cache, teryt_cache, teryt_bbox_cache, index_area_cache
│                        # (raport dostepnosci; rekordy obszaru indeksu kafli WFS),
│                        # atom_cache (indeksy feedow ATOM z ETag;
│                        # TTL 7 d, DEFAULT_TTL_SECONDS)
│                        # i sheet_cache (30 d, SHEET_TTL_SECONDS); plik bazy
│                        # otwierany leniwie, powstaje przy pierwszym zapisie
├── cache/defaults.py    # open_cache(cache: MetadataCache | bool, force) — wspolny cache
│                        # CLI i biblioteki w <cache_dir>/kartograf/metadata.db (DEV-18.2)
├── download/            # Pobieranie: komenda download (data.py) i tory
│   ├── data.py          # download_data/check_data — komendy `kartograf elevation download` / `imagery download` w bibliotece
│   │                    # (ADR-037): kraj i `auto`, rozwiniecie obszaru PL, wybor toru,
│   │                    # parent_request, DataReport/UnitFile/UnitFailure, Notice
│   ├── options.py       # validate_request / validate_request_bbox (takze bbox CRS),
│   │                    # walidacja wyborow: produkt, kraj, format, rozdzielczosc i uklad
│   │                    # (z rejestru wariantow), system, skala, lata, opcje LAZ,
│   │                    # ortofoto CZ (cz_orto_option_error) i wycinek orto; teksty jak w --help
│   ├── arguments.py     # Kontrola typow argumentow biblioteki (STANDARDS 11.2): require_int,
│   │                    # require_str, require_bool, require_codes
│   ├── availability.py  # Raport dostepnosci (ADR-041, sekcja 4.9): check_availability (PL, CZ, auto),
│   │                    # AvailabilityReport (kartograf-availability/1)/AvailabilityCombination/AvailabilityArea
│   ├── area.py          # Obszar zadania: bbox_to_2180, obwiednie geometrii,
│   │                    # parent_request_for, przyciecie `auto` (Notice)
│   ├── campaigns.py     # Kampanie GUGiK (ADR-030): CampaignRef, format z rekordu,
│   │                    # verify_file_format, verify_record_url/verify_sheet_extent (B4),
│   │                    # verify_record_vertical_crs (uklad wysokosci rekordu)
│   ├── countries.py     # Podzial obszaru na kraje: countries_for_bbox, split_bbox_by_country
│   ├── links.py         # Dowiazanie sciezki standardowej do wersji (wylacznie hardlink, nigdy wstecz)
│   ├── fetch.py         # Polityka plikow bez kampanii: fetch_version, VersionedFile;
│   │                    # FileSlot.related_roots (D23 miedzy wydaniami, ADR-042 D7)
│   ├── plan.py          # Plan aktualizacji: UpdatePlan = dokument kartograf-plan/1 (PlanItem.track/unit,
│   │                    # notices, ok, from_dict)
│   ├── cutout.py        # Wycinek PL WCS (ADR-035): download_pl_cutout/check_pl_cutout,
│   │                    # maska ladu, sidecar (kroki wewnetrzne prywatne)
│   ├── orto_cutout.py   # Wycinek obrazu PL WCS (ADR-042 D14, plan E1, ADR-044): download_image_cutout/
│   │                    # check_image_cutout (ortofotomapa i true orto po kluczu deskryptora),
│   │                    # ImageCutoutResult, orto_cutout_error
│   ├── cz_cutout.py     # Wycinek CZ: download_cz_cutout/check_cz_cutout, write_cz_sidecar
│   ├── cz_sheets.py     # Arkusz CZ TM33/SM5: download_cz_sheet/check_cz_sheet, CzSheetResult,
│   │                    # cz_sheet_variant (wiersz trasy rastra CZ, plan B)
│   ├── cz_laz.py        # LAZ CZ (plan B): download_cz_laz/check_cz_laz, CzLazResult/
│   │                    # CzLazFailure — arkusz albo obszar, pula watkow, tor planu cz_laz
│   ├── cz_orto.py       # Ortofoto CZ (ADR-042 D13): download_cz_orto_sheet/check_cz_orto_sheet,
│   │                    # CzOrtoResult, cz_orto_sheet, cz_orto_area_sheets (indeks SM5)
│   ├── cz_contours.py   # Warstwice ZABAGED CZ (plan E1): download_cz_contours_sheet/
│   │                    # check_cz_contours_sheet, CzContoursResult, cz_contours_area_sheets;
│   │                    # ZIP arkusza SM5 1:1, sygnal http, tor planu cz_sheet
│   ├── laz.py           # Kafle LAZ PL (ADR-029): download_laz_area/check_laz_area — bbox
│   │                    # w dowolnym CRS, pula watkow, sidecar kafla, porazki w wyniku
│   ├── manager.py       # DownloadManager — arkusze PL (ThreadPoolExecutor), sidecary;
│   │                    # kampanie (year=, all_campaigns=, min_year=, max_year=),
│   │                    # update/plan, check_sheets, DownloadResult (wartosc zwracana)
│   ├── storage.py       # FileStorage — segmenty z szablonow rejestru (ADR-026), versions/;
│   │                    # prune_empty_dirs — sprzatanie pustych bbox/ po porazce;
│   │                    # content_segment (prefiks + tokeny tresci), unit_slot (teryt/bbox/
│   │                    # godlo/country, sloty pokrewne D7 — ADR-042 D8)
│   ├── collections.py   # Kolekcje (ADR-042): download_collection/check_collection =
│   │                    # komendy boundaries/cadastre/models3d/hydro/names/maps/
│   │                    # geodesy download, validate_collection_request (bez sieci),
│   │                    # CollectionReport, zadania jednostek (package_job/run_job/
│   │                    # inspect_job; tor planu collection), limit obszaru (100 plikow,
│   │                    # 10 GB), landcover_request/run_request/plan_request (ZABAGED,
│   │                    # BDOO, Data50, Data250)
│   ├── updates.py       # Wewnetrzne pozycje planu PL (kartograf-plan/1, ADR-036)
│   └── versions.py      # Magazyn wersjonowany (ADR-036): zapis wylaczny, etykiety,
│                        # lista wersji, sprzatanie .incoming/
├── landcover/manager.py # Publiczne download_landcover/check_landcover (LandCoverReport),
│                        # download_soil/check_soil (SoilReport); wewnetrzny
│                        # LandCoverManager, BDOT10k obszaru = kazdy powiat;
│                        # roczniki BDOT10k oraz ZABAGED, BDOO, Data50 i Data250
│                        # (COLLECTION_SOURCES) przez silniki kolekcji
├── landcover/store.py   # hsg_segment, HSG_SEGMENT_PREFIX, selection_unit (spec 3.4)
├── hydrology/hsg.py     # Publiczne calculate_hsg/check_hsg (HsgReport),
│                        # hsg_statistics; wewnetrzny HSGCalculator z wersji
│                        # clay/sand/silt (D33, reused), klasyfikacja USDA -> HSG,
│                        # hsg_from_rasters
├── project/             # Manifest projektu (ADR-040):
│   ├── model.py         # Project, ProjectTask, PinnedFile, ProjectReport,
│   │                    # ProjectCheck i wyniki zadan oraz plikow
│   ├── commands.py      # COMMANDS: opcje JSON (TaskCommand.options z katalogu), walidacja bez sieci,
│   │                    # pobranie (TaskDownload: plan, summary), check_* i przypiecia na komende danych
│   │                    # (bez logiki per produkt)
│   ├── manifest.py      # kartograf-project/1: walidacja, blokada mkdir, atomowy
│   │                    # zapis i scalanie zmian per zadanie
│   └── operations.py    # Publiczne API: init, add, remove, download,
│                        # check, status, verify i open_project
├── auth/                # proxy.py (subprocess izolujacy credentials CLMS), client.py
│                        # (AuthProxyClient — singleton, sam uruchamia proxy)
└── cli/                 # Tylko tlumaczenie flag i wypisanie wyniku (Z1, Z8; ADR-037, ADR-046):
                         # _parser.py (create_parser: fasada na catalog.cliparser - parser z deklaracji
                         # katalogu, ADR-039), _handlers.py (HANDLERS: id komendy -> handler),
                         # _args.py (library_arguments: flagi -> argumenty funkcji przez katalog),
                         # _json.py (tryb --json: json_mode, emit_document, UTF-8),
                         # download_cmd.py (download_data/check_data),
                         # availability_cmd.py (check_availability: tabele PL i CZ, --details, --json),
                         # collection_cmd.py (download_collection/check_collection),
                         # landcover_cmd.py, soil_cmd.py (SoilGrids + HSG), layers_cmd.py (list-layers),
                         # sources_cmd.py (list-sources), parse_cmd.py (describe_sheet),
                         # cache_cmd.py (cache_info), catalog_cmd.py (get_catalog),
                         # project_cmd.py (API projektu; project add przez parse_command),
                         # commands.py (entry point main: wyjatki -> error_report, kody 0/1/2/130/143)
```

---

## 3. Kontrakty danych

### 3.1 `SourceDescriptor` i szablony `storage_subdir`

`SourceDescriptor` (`src/kartograf/sources/descriptor.py`) niesie: `key`,
`country`, `product`, `name`, `provider_name`, krotke `channels`
(`AccessChannel`), `tile_scheme`, `storage_subdir`, `default_extension`,
`license`, `resolution`, `auth` i (od 0.8.0, ADR-041) krotke `variants`
(`ProductVariant`, rejestr wariantow — nizej). `product` = wartosc
`--product` wybierajaca zrodlo (`nmt`, `admin`, `bdot10k`, `zabaged`;
SoilGrids bez `--product` - `soil`) i pole `product` sidecara; grupe CLI
zrodla wyznacza pierwszy czlon `storage_subdir` (np. produkty
`landcover download` = deskryptory pod `landcover/`).

Od 0.7.0 (ADR-026) `storage_subdir` jest **szablonem** z placeholderami
`{system}` i `{vcrs}`, a nie literalna nazwa katalogu. Konsument zewnetrzny
czytajacy to pole wprost dostanie szablon — swiadomy trade-off; poprawna droga
to `resolve_subdir()`. Klucz i `storage_subdir` kazdego deskryptora
podlegaja konwencji nazw (sekcja 3.3, regula 10; ADR-044 D7).

| Klucz deskryptora | `storage_subdir` | `default_extension` |
|---|---|---|
| `pl.gugik.nmt_0_15m`, `pl.gugik.nmt_0_5m`, `pl.gugik.nmt_0_6m`, `pl.gugik.nmt_1m`, `pl.gugik.nmt_5m`, `pl.gugik.nmt_10m` | `nmt/pl_{system}_<etykieta>_{vcrs}`, np. `nmt/pl_{system}_0.5m_{vcrs}` | `.asc` |
| `pl.gugik.nmpt_0_5m`, `pl.gugik.nmpt_0_6m`, `pl.gugik.nmpt` (1 m) | `nmpt/pl_{system}_<etykieta>_{vcrs}`, np. `nmpt/pl_{system}_1m_{vcrs}` | `.asc` |
| archiwa `pl.gugik.<produkt>_<format>[_<etykieta>]`, np. `pl.gugik.nmt_tbd_25m`, `pl.gugik.nmt_ascii_nmt_1m`, `pl.gugik.nmt_tin`, `pl.gugik.nmpt_xyz_0_5m` | `<produkt>/pl_{system}_<format>[_<etykieta>]_{vcrs}`, np. `nmt/pl_{system}_tbd_25m_{vcrs}`, `nmt/pl_{system}_ascii-nmt_1m_{vcrs}`, `nmt/pl_{system}_tin_{vcrs}` | wg formatu: `.zip` (XYZ, ASCII-NMT, TBD, TIN), `.ttn`, `.grd`, `.dxf`, `.dgn` |
| `pl.gugik.orto` | `orto/pl_{system}` (+ `_<wariant>` dla CIR/B-W, regula 5); wycinek WCS `orto/pl_1992_<coverage>_<res>` (tokeny, regula 5) | `.tif` |
| `cz.cuzk.orto` | `orto/cz_sjtsk` (hierarchia SM5) | `.jpg` (+ `.jgw`, `.TM33N.jgw`, `.TM34N.jgw`) |
| `pl.gugik.nmt_100m` | `nmt/pl_1992_100m` (bez `{vcrs}`: uklad wysokosci nieznany, P1); slot `teryt/<woj>` | `.zip` |
| `pl.gugik.intensity` | `intensity/pl_{system}` | `.tif` |
| `pl.gugik.true_orto` | `true-orto/pl_{system}`; wycinek WCS `true-orto/pl_1992_<res>` | `.tif` |
| `pl.gugik.oblique_orto` | `oblique-orto/pl_{system}`; plik `<godlo>_<kierunek>` (`FileStorage(suffix=)`) | `.tif` |
| `cz.cuzk.zabaged_contours_shp`, `cz.cuzk.zabaged_contours_dgn` | `contours/cz_zabaged_shp`, `contours/cz_zabaged_dgn` (hierarchia SM5) | `.zip` |
| `pl.gugik.laz` | `laz/pl_{system}_{vcrs}` | `.laz` |
| `cz.cuzk.dmr5g` | `nmt/cz_dmr5g_{vcrs}` | `.tif` |
| `cz.cuzk.dmr4g` | `nmt/cz_dmr4g_{vcrs}` | `.tif` |
| `cz.cuzk.dmpok`, `cz.cuzk.dmp1g` | `nmpt/cz_dmpok_{vcrs}`, `nmpt/cz_dmp1g_{vcrs}` | `.tif` |
| `cz.cuzk.<model>_laz` (`dmr5g`, `dmr4g`, `dmp1g`, `dmpok`) | `laz/cz_<model>_{vcrs}` | `.laz` |
| `pl.gugik.bdot10k` | `landcover/pl_bdot10k` (prefiks + tokeny, regula 8) | `.gpkg` |
| `eu.clms.corine` | `landcover/eu_corine` (prefiks + tokeny) | `.tif` |
| `global.isric.soilgrids` | `soil/global_soilgrids` (prefiks + tokeny) | `.tif` |
| `pl.gugik.prg` | `boundaries/pl_prg` (prefiks + tokeny, regula 9) | `.gpkg` |
| `pl.gugik.egib` | `cadastre/pl_egib` (prefiks + tokeny, regula 9) | `.gpkg` |
| `pl.gugik.buildings` | `models3d/pl_buildings` (prefiks + tokeny, regula 9) | `.zip` |
| `cz.cuzk.zabaged` | `landcover/cz_zabaged` (prefiks + tokeny, regula 9) | `.gpkg` |
| `cz.cuzk.ruian` | `boundaries/cz_ruian` (prefiks + tokeny, regula 9) | `.gpkg` |
| `cz.cuzk.hynet` | `hydro/cz_hynet` (prefiks + tokeny, regula 9) | `.gpkg` |
| `pl.gugik.bdoo` | `landcover/pl_bdoo` (prefiks + tokeny: rocznik i klasy `--layers`, regula 9); slot `teryt/<woj>` | `.zip` |
| `cz.cuzk.data50`, `cz.cuzk.data250` | `landcover/cz_data50`, `landcover/cz_data250` (prefiks + tokeny, regula 9) | `.gpkg` (plik krajowy `.zip`) |
| `pl.gugik.mesh` | `models3d/pl_mesh` (prefiks, regula 9); slot `<uklad>[/<strefa>]/<plik kafla>` | `.zip` |
| `pl.gugik.trees` | `models3d/pl_trees` (prefiks + tokeny `lod1`, `2023`, regula 9) | `.zip` |
| `pl.gugik.control` | `geodesy/pl_control` (prefiks + tokeny: siec, `xls` paczki powiatu, regula 9) | `.gpkg` (paczka i archiwum `.zip`) |
| `pl.gugik.geoid2021` | `geodesy/pl_geoid2021` (prefiks + token `evrf2007`) | `.txt` |
| `cz.cuzk.control` | `geodesy/cz_control` (prefiks + token sieci) | `.gpkg` |
| `cz.cuzk.qgzu2013` | `geodesy/cz_qgzu2013` (prefiks + token `bpv`) | `.zip` |
| `cz.cuzk.cadastral_map` | `cadastre/cz_cadastral-map` (prefiks + token formatu, regula 9); slot `ku/<kod>` | `.zip` |

Kanal arkuszy kazdego deskryptora NMT/NMPT PL to `WFS` (`sheet_files`,
sygnal `index`; skorowidz WFS GUGiK, od 0.8.0 zamiast `WMS_SHEET_INDEX`,
ktory zostaje tylko dla orto). Kanal WCS `bbox_raster` dla obu ukladow
pionowych (`EPSG:9650` KRON86, `EPSG:9651` EVRF2007) maja wylacznie
`pl.gugik.nmt_1m` i `pl.gugik.nmpt` (1 m); pozostale rozdzielczosci
i archiwa go nie maja (stad wycinek NMT/NMPT tylko 1 m, sekcja 4.3).
`pl.gugik.orto` ma obok `WMS_SHEET_INDEX` (`sheet_files`, `index`) dwa
kanaly `WCS` `bbox_raster` wycinka ortofotomapy (plan D, ADR-042 D14):
`.../PZGIK/ORTO/WCS/StandardResolution` (`Orthoimagery_StandardResolution`)
i `.../HighResolution` (`Orthoimagery_High_Resolution`), sygnal `none`,
parametry `WcsCutoutParams` (nizej; sekcja 4.3).

Deskryptory CZ (plan B) maja kanaly plikow openzu `DIRECT_FILES`
(`sheet_files`, sygnal `http`) per uklad poziomy: S-JTSK `EPSG:5514`
z wysokosciami Bpv (`EPSG:8357`) i ETRS89/TM33N `EPSG:3045` z EVRF2007
(`EPSG:5621`); rastry NMT/NMPT maja tez kanal `ARCGIS_IMAGE`
(`bbox_raster`, sygnal `none`, `EPSG:5514`/Bpv; DMP OK: usluga
`dmp_obrazova_korelace`), a rastrowe `cz.cuzk.dmr5g` i `cz.cuzk.dmp1g`
maja tylko ten kanal (pliki tych modeli to wylacznie LAZ). Jeden kanal
wybiera `registry.channel_for(key, transport, horizontal_crs)`
(`ValidationError`, gdy brak albo niejednoznaczny);
`channel_signal(key, transport, horizontal_crs)` daje jego sygnal.

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
`SkorowidzDanychPomiarowychLIDAR`) oraz `model` (CZ: `dmr5g`, `dmr4g`,
`dmp1g`, `dmpok`; PL `None`). Wlasciwosci: `label` (etykieta K2)
i `source_file` (archiwum = plik zrodlowy bez konwersji, wycinka
i mozaiki). `FORMATS` (`FileFormat`: token, nazwa pola `format`
w skorowidzu, rozszerzenie, akceptowane koncowki sciezki URL, opis,
`source_file`) opisuje formaty skorowidza; rozszerzenie wynika z pola
`format` rekordu, nigdy z URL.

Warianty CZ (plan B, deskryptory `cz.cuzk.*`) to wiersze tabeli tras
(sekcja 4.4): po jednym na (produkt, etykieta albo `model`, uklad
wysokosci `Bpv`/`EVRF2007`, system arkusza `systems=("sm5",)` albo
`("tm33",)`), `format` `TIFF`/`LAZ`, `index_ref=None`; `channel` to
`DIRECT_FILES` (plik openzu) albo `ARCGIS_IMAGE` (ImageServer z warpem na
siatke kafla TM33). Wycinek CZ nie jest wierszem rejestru, tylko kanalem
`ARCGIS_IMAGE` deskryptora.

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
`format_tokens`; dla CZ `cz_sheet_system` (system godla `sm5`/`tm33`),
`cz_variant_error`/`find_cz_variant` (wiersz trasy rastra; SM5 moze
pominac etykiete, gdy produkt ma jedna etykiete z plikami SM5) oraz
`cz_laz_error`/`find_cz_laz_variant` (model i uklad wysokosci LAZ CZ,
zgodnosc z systemem godla). Rejestr czytaja: walidacja CLI/API
(`download/options.py`), teksty `--help` i `list-sources`,
`download/area.py::pl_only_flags`, `FileStorage` (deskryptor wariantu),
wycinek (`download/cutout.py::wcs_variant` — wariant z kanalem WCS),
providery PL (wariant, uslugi skorowidza) i CZ (trasa, model), tory CZ
(`download/cz_sheets.py`, `download/cz_laz.py`) i raport dostepnosci
(4.9). Zaden inny modul nie trzyma listy rozdzielczosci, ukladow
wysokosci ani formatow. Pozostale deskryptory (orto, land cover)
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
| `UnitPackageParams` | `unit` (`powiat`/`woj`/`country`), `variants` (`PackageVariant`), `unpack` (sufiks JEDNEGO czlonu zapisywanego zamiast ZIP; `None` = ZIP 1:1), `class_pattern` (plan E4: wyrazenie szukane w nazwie pliku kazdego czlonu ZIP, grupa `code` = klasa czlonu; paczka bez pliku klasy to nie dane, a wybor klas `layers` zapisuje nowy ZIP plikow tych klas - kazdy czlon bajt w bajt, z nazwa, data i kompresja zrodla, w kolejnosci zrodla) | `transport/unit_package.py` |
| `PackageVariant` | `choice` (opcje API/CLI wybierajace wariant, np. `(("format", "SHP"), ("year", "2024"))`; `()` = jedyny wariant), `url_template` (tokeny wylacznie `{teryt}`, `{woj}` = 2 pierwsze cyfry TERYT), `edition` (etykieta wersji), `segment_tokens`, `members` (wymagane sufiksy czlonow ZIP), `vertical_crs` (uklad wysokosci zadeklarowany w danych 3D), `classes` (plan E4: kody klas wydania do wyboru `layers`; `()` = bez wyboru klas) | jw. |
| `FeatureBBoxParams` | `protocol` (`wfs`/`arcgis`, zgodny z `transport` kanalu `WFS`/`ARCGIS_QUERY`), `native_crs`, `axis_order` (`yx` = northing pierwszy w BBOX), `page_size`, `layers` (`FeatureLayer`), `selection` (`level` = jedna warstwa wg `--level`, `all` = kazda), `order_field` (ArcGIS `orderByFields`), `drop_fields` | `transport/feature_bbox.py` + `transform/gpkg.py` |
| `FeatureLayer` | `code` (wartosc `--level` albo staly kod), `source` (typ WFS `ms:A03_Granice_gmin` albo id warstwy ArcGIS), `name` (warstwa GPKG), `id_field` (staly identyfikator obiektu: dedupe i kolejnosc) | jw. |
| `AtomFilesParams` (plan D) | `service_feed` (feed uslugi ATOM), `entry_pattern` (wyrazenie na id feedu zbioru; grupa `sheet` = klucz indeksu, `year` = rok wydania w nazwie pliku; bez `sheet` feed ma jeden zbior), `crs` (kody EPSG kategorii ukladu plikow zbioru; `()` = jeden plik), `members` (pary sufiks czlonu ZIP -> sufiks zapisu; `()` = ZIP 1:1), `segment_tokens` (+ kod EPSG, gdy `crs` ma kilka ukladow) | `transport/atom.py` |
| `WcsCutoutParams` (plan D) | `variant` (`--coverage`: `standard`/`high`), `coverage_id`, `native_step` (krok coverage, 0,1 m), `resolutions` (piksele wyniku: 0.1, 0.25, 0.5, 1; etykiety K2), `max_native_pixels` (budzet zapytania w pikselach coverage, 4 Mpx) | `GugikOrtoProvider` + `download/orto_cutout.py` |

Testy rejestru (`tests/unit/test_sources_registry.py`) pilnuja: tokenow szablonu,
tych samych kluczy `choice` w wariantach kanalu, kluczy, katalogow
i `edition`/`segment_tokens` wg konwencji nazw (sekcja 3.3, regula 10),
protokolu zgodnego z transportem, `page_size > 0` i capability kanalu
kolekcji unikalnej w deskryptorze (`archive_unit_files`, `country_files`,
`bbox_vector`, `admin_unit_files`) - po niej `build_metadata(capability=)`
wybiera kanal sidecara. Kanaly kolekcji PL:

| Deskryptor (`--product`) | Kanal, capability | Parametry |
|---|---|---|
| `pl.gugik.bdot10k` (`landcover --product bdot10k --year`) | `DIRECT_FILES`, `archive_unit_files` | powiat; 24 warianty `(format, year)`: 2014-2025 x `GML` (czlon `.xml`) / `SHP` (`.shp`), `.../Archiwum/bdot10k/<R>/<F>/{woj}/{teryt}_<F>_<R>.zip`, `edition` = rok |
| `pl.gugik.prg` (`admin`) | `WFS` `AdministrativeBoundaries`, `bbox_vector` | `wfs`, EPSG:2180, `yx`, strona 1000, `selection="level"`: `wojewodztwo`=A01, `powiat`=A02, `gmina`=A03, `jednostka-ewidencyjna`=A05, `obreb`=A06, id `IIP_IDENTY` |
| jw. | `DIRECT_FILES`, `admin_unit_files` | woj.; `prg/granice/{woj}_GraniceAdministracyjne.zip`, czlon `.gml`, token `gml` |
| jw. | `DIRECT_FILES`, `country_files` | kraj; `prg/granice/00_jednostki_administracyjne.zip` (ok. 377 MB), czlon `.shp`, token `shp` |
| `pl.gugik.egib` (`map`) | `DIRECT_FILES`, `admin_unit_files` | powiat; `InneDane/latest_exports/eziudp_wfs/GPKG/{teryt}.gpkg.zip`, `unpack=".gpkg"`, token `gpkg` |
| jw. | `WFS` `UslugaZbiorcza`, `bbox_vector` | `wfs`, EPSG:2180, `yx`, strona 1000, `selection="all"`: `dzialki`, `budynki`, id `gml_id`, `drop_fields=("DATA",)` |
| `pl.gugik.buildings` (`buildings`) | `DIRECT_FILES`, `admin_unit_files` | powiat; warianty `(lod, year)`: LoD1 2019 (`.../LOD1/2019/{woj}/{teryt}_gml.zip`, EPSG:9650), LoD1 2021/2022/2024 (`.../LOD1/<R>/{woj}/{teryt}.zip`, EPSG:9651), LoD2 2017 (`.../LOD2/{teryt}_gml.zip`, EPSG:9650); czlon `.gml`, `edition` = rok |
| `pl.gugik.bdoo` (`landcover --product bdoo`, plan E4) | `DIRECT_FILES`, `admin_unit_files` | woj.; 7 wariantow `year` (2015, 2021-2026): `opendata/bdoo/<R>/PL.PZGiK.201.{woj}.zip`, czlon `.xml` (do 2023) albo `.gml` (od 2024), `edition` = rok; `classes` = suma klas 16 paczek rocznika (2015: 44, 2021-2023: 37, 2024-2026: 26), `class_pattern` `__OT_(?P<code>[A-Z]{4})_[A-Z]\.`; EPSG:2180; brak pliku krajowego |
| `pl.gugik.mesh` (`models3d --product mesh`, plan E5) | `DIRECT_FILES`, `area_files` | kafle obszaru z rekordow WFS `NMT/WFS/ModeleSiatkowe3D` (typ `gugik:SkorowidzModeleSiatkowe3D`, strony `next`); `IndexSource(unit_field=None)`: kafel = plik rekordu (`URL_do_pobrania`; pole `modul` powtarza sie w kilku pracach i miastach), etykieta `Aktualnosc_Numer_zgloszenia_pracy`, rok `akt_rok` (filtr `--year`), strefa `uklad_xy` (katalog slotu `1992` albo `2000/<strefa>` i uklad sidecara); czlon `.obj`, `vertical_crs` EPSG:9651; `index` |
| `pl.gugik.trees` (`models3d --product trees`, plan E5) | `DIRECT_FILES`, `admin_unit_files` | powiat; jeden wariant `(lod, year)` = (1, 2023): `InneDane/Drzewa3D/LOD1/2023/{woj}/{teryt}.zip` (0,3-25 GB; nie kazdy powiat ma paczke), czlon `.gml`, `edition` 2023, bez ukladu wysokosci (GML `srsName="EPSG:2180"`) |
| `pl.gugik.control` (`geodesy --product control --country pl`, plan E5) | 4 x `WFS`, `bbox_vector` (wspolna capability, ADR-043 D6) | `wfs`, EPSG:2180, `yx`, strona 1000, `selection="all"`, `choice` `network`: `horizontal` (`PodstawowaOsnowaGeodezyjnaPozioma`: `Fundamentalna_pozioma`, `Bazowa_pozioma`), `vertical` (`PodstawowaOsnowaGeodezyjnaWysokosciowa`), `gravity` (`OsnowaGrawimetryczna`), `magnetic` (`OsnowaMagnetyczna`: punkty i `izogony`, bez `izogony_etykiety`); adres `.../PZGIK/<usluga>/WFS`; obiekty bez `gml:id`: id `nr_punktu` (izogony `zakres_wartosci_deklinacji`); warstwa GPKG = nazwa zrodla malymi literami |
| jw. | `DIRECT_FILES`, `admin_unit_files` | powiat; warianty `network` `horizontal`/`vertical`: `bdpog/Pozioma/{teryt}_PodstawowaOsnowaPozioma.zip` (`Wysokosciowa`), czlon `.xls` (wykazy wspolrzednych; opisy JPG), tokeny `<siec>`, `xls` |
| jw. | `DIRECT_FILES`, `sheet_files` | arkusz 1:100 000 (`SheetGrid(system="1992", parts=3)`); warianty `network` `archive-1942`, `archive-kronsztadt60`: `bdpog/MaterialyArchiwalne/Katalogi_<Kartoteki1942\|Kronsztadt60>/{sheet}.zip` (godlo bez zera wiodacego), czlon `.pdf` (skany katalogow; uklad w sidecarze = uklad siatki arkuszy) |
| `pl.gugik.geoid2021` (`geodesy --product geoid --country pl`, plan E5) | `DIRECT_FILES`, `country_files` | kraj; `InneDane/ModeleQuasiGeoidy/PL-geoid2021/Model_quasi-geoidy-geoid2021-PL-EVRF2007-NH.txt` (42 MB, siatka 0,01 st.), `file_kind="txt"`, token `evrf2007`, EPSG:9702 (ETRF2000-PL), `vertical_crs` brak (model nie jest wysokosciami) |

Kazdy z tych kanalow poza kaflami mesh 3D (`index`: etykieta rekordu
indeksu) ma sygnal `none` (GUGiK nie podaje `ETag` ani `Last-Modified`;
wynik WFS to migawka). Kanaly CZ (plan D, ADR-042 D13-D17; obszar CZ
zawsze w EPSG:5514 = DefaultCRS uslug):

| Deskryptor (wybor) | Kanal, capability | Parametry |
|---|---|---|
| `cz.cuzk.zabaged` (`landcover --product zabaged`) | `ARCGIS_QUERY` `ZABAGED_POLOHOPIS/MapServer`, `bbox_vector` | `arcgis`, EPSG:5514, `xy`, strona 2000, `selection="all"`: 22 warstwy (`registry.py::_ZABAGED_LAYERS`, kod = nazwa warstwy ASCII), `order_field="OBJECTID"`, id `fid_zbg`; `none` |
| jw. | `DIRECT_FILES` + `AtomFilesParams`, `country_files` | feed `atom.cuzk.gov.cz/ZABAGED-GPKG/ZABAGED-GPKG.xml` (jeden zbior), `crs` EPSG:5514 i EPSG:3045, ZIP 1:1, token `gpkg` + kod EPSG; `metadata` |
| `cz.cuzk.ruian` (`admin`) | `ARCGIS_QUERY` `RUIAN/MapServer`, `bbox_vector` | `arcgis`, EPSG:5514, `xy`, strona 1000, `selection="level"`: `kraj`=17, `okres`=15, `obec`=12, `katastralni-uzemi`=7, `order_field="objectid"`, id `kod`; `none` |
| jw. | `DIRECT_FILES` + `UnitPackageParams`, `country_files` | kraj; `services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip` (ok. 253 MB), czlon `.shp`, token `shp`; `http` |
| `cz.cuzk.hynet` (`network`) | `WFS` `geoserver/hy-n/wfs`, `bbox_vector` | `wfs`, EPSG:5514, `xy`, strona 1000, `selection="all"`: `hy-n:WatercourseLink`, `hy-n:HydroNode` (warstwy GPKG bez prefiksu), id `gml_id`; `none` |
| jw. | `DIRECT_FILES` + `UnitPackageParams`, `country_files` | kraj; `openzu.cuzk.gov.cz/opendata/HY-NET/HY-NET.zip` (ok. 194 MB, EPSG:3045), czlon `.gpkg`, token `gpkg`; `http` |
| `cz.cuzk.data50`, `cz.cuzk.data250` (`landcover --product data50\|data250`, plan E4) | `ARCGIS_QUERY` `DATA50/MapServer`, `DATA250/MapServer`, `bbox_vector` | `arcgis`, EPSG:5514, `xy`, strona 2000, `selection="all"`: 69 i 116 warstw obiektowych (`registry.py::_DATA50_LAYERS`, `_DATA250_LAYERS`, kod = nazwa warstwy ASCII jak ZABAGED; rastry reliefu 5 i 6 DATA250 pominiete), `order_field="OBJECTID"`, id `OBJECTID`; `none` |
| jw. | `DIRECT_FILES` + `AtomFilesParams`, `country_files` | feed `atom.cuzk.gov.cz/Data50/Data50.xml` (`Data250/Data250.xml`; jeden zbior), `crs` EPSG:5514 i EPSG:3045, SHP ZIP 1:1 (Data50 516/757 MB, Data250 230/320 MB), token `shp` + kod EPSG; `metadata` |
| `cz.cuzk.control` (`geodesy --product control --country cz`, plan E5) | `ARCGIS_QUERY` `BodovaPole/MapServer`, `bbox_vector` | `arcgis`, EPSG:5514, `xy`, strona 1000, `selection="level"`, `selection_key="network"`: `gnss`=0, `horizontal`=18, 20, 2, 4, 6, 8, `densification`=38, 40, 22, 24, 26, 28, `horizontal-detailed`=42, `vertical`=44, `vertical-detailed`=46, `gravity`=48 (siec = suma warstw: punkty wyznaczone w ETRS89 nie sa podzbiorem warstw glownych; zniesione 10-17, 30-37 i etykiety pominiete), warstwa GPKG = nazwa CUZK ASCII (`bod_zvbp`), id `OBJECTID`; `none` |
| `cz.cuzk.qgzu2013` (`geodesy --product geoid --country cz`, plan E5) | `DIRECT_FILES` + `AtomFilesParams`, `country_files` | feed `atom.cuzk.gov.cz/QGZU/QGZU.xml` (jeden zbior; feed zbioru i plik na hostach `atom.cuzk.cz`, `openzu.cuzk.cz`), EPSG:4258, ZIP 17 siatek TXT 1:1 (58 MB), token `bpv` (uklad wysokosci modelu); `metadata` |
| `cz.cuzk.orto` (`imagery --product orto --country cz`) | `DIRECT_FILES` + `AtomFilesParams`, `sheet_files` | feed `atom.cuzk.gov.cz/ORTOFOTO/ORTOFOTO.xml`, wpis po godle SM5 (grupy `year`, `sheet`), czlony `.jpg`, `.jgw`, `.TM33N.jgw`, `.TM34N.jgw` 1:1; `metadata`; tor `download/cz_orto.py` (nie kolekcja) |

Pliki krajowe CUZK z `ETag` maja sygnal `http`, pliki z feedu ATOM
(rok albo data wydania w nazwie) - `metadata` (wydanie z `updated`).
Typ HY-NET `WatercourseSeparatedCrossing` nie jest warstwa obszaru: nie
ma geometrii w GML (relacja dwoch odcinkow), a GeoServer dla zapytania
z BBOX podaje `hits` 0 mimo obiektow na stronach (ADR-042 errata 2);
skrzyzowania zawiera plik krajowy.

Kanaly planu E1 (ADR-043; produkty `download_data`, nie kolekcje):

| Deskryptor (wybor) | Kanal, capability | Parametry |
|---|---|---|
| `pl.gugik.nmt_100m` (`elevation --product nmt --resolution 100m`) | `DIRECT_FILES` + `AtomFilesParams`, `admin_unit_files` | feed `mapy.geoportal.gov.pl/.../ATOM/httpauth/atom/GUGIK_NMT100`, wpis zbioru po `NMT100_<woj>` (grupa `woj`), `force_https` (linki `http://` feedow GUGiK pobierane przez `https`), ZIP z plikiem XYZ 1:1; `metadata`; wariant rejestru bez ukladu wysokosci (`vertical_crs=None`, `vertical_note`, P1); tor `collection` (`collections.atom_area_request`) |
| `pl.gugik.intensity` (`imagery --product intensity`) | `WMS_SHEET_INDEX` + `SheetIndexParams`, `sheet_files` | `OI/WMS/SkorowidzeObrazowIntensywnosci`, warstwa `SkorowidzeOI`, arkusze PL-1992 (godla 7-czlonowe) i PL-2000, bez `calyArkuszWypelnionyTrescia` (`full_sheet=False`); `index` |
| `pl.gugik.true_orto` (`imagery --product true-orto`) | `WMS_SHEET_INDEX` + `SheetIndexParams`, `sheet_files`; `WCS` + `WcsCutoutParams`, `bbox_raster` | skorowidz `ORTO/WMS/TrueOrtho` (`Skorowidze`, godla 8-czlonowe PL-1992, `extent` = wybrane miasta); WCS `True_Orthoimagery` (siatka 0,05 m, piksele `0.05m`-`1m`, jedna usluga = bez `--coverage`); `index` / `none` |
| `pl.gugik.oblique_orto` (`imagery --product oblique-orto`) | `WMS_SHEET_INDEX` + `SheetIndexParams`, `sheet_files` | `ORTO/WMS/SkorowidzeOrtofotomapyUkosnej`, warstwa na kierunek (`directions`: `n`, `e`, `s`, `w`), arkusze PL-2000 1:2000 i 1:1000, `full_sheet=True`; plik `<godlo>_<kierunek>.tif`; `index` |
| `cz.cuzk.zabaged_contours_shp`, `cz.cuzk.zabaged_contours_dgn` (`elevation --product contours --country cz --format SHP\|DGN`) | `DIRECT_FILES`, `sheet_files` | `openzu.cuzk.gov.cz/opendata/ZABAGED-vyskopis{,-DGN}/epsg-5514/{sheet}.zip` (jeden format = jeden deskryptor, jak archiwa GUGiK), arkusze SM5, S-JTSK, Bpv, ZIP 1:1; `http`; tor `download/cz_contours.py` |

`SheetIndexParams(layers, systems, sheet_parts, full_sheet, directions=(),
extent=None)` opisuje skorowidz WMS obrazu: warstwy rekordow (stale - bez
`GetCapabilities`; ortofotomapa ma `layers=()` i warstwy z
`GetCapabilities`), uklady arkuszy (jeden = `--sheet-system` mozna
pominac), liczbe czlonow godla (`series_scale`: 7 = `1:10000`, 8 =
`1:5000`), czy rekordy deklaruja pelny arkusz (`--full-sheet`), kierunki
widoku (kod, warstwa) i zasieg do podpowiedzi `NoCoverageError`.

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
| `{system}` (jawnie) | tor LAZ: `LazTile.system` (`uklad_xy` kafla przez `parse_pl_system`; nieznany = kafel pominiety / `ValidationError`) przez `FileStorage.get_raw_path(..., system=)` — jedno zrodlo prawdy dla CLI i biblioteki (zn. 8, review max); wycinek PL WCS (`download_pl_cutout`: `system="1992"` na stale — `--cutout` z `--sheet-system 2000` jest odrzucane, sekcja 4.3) i wycinek obrazu (`download_image_cutout`: `system="1992"`, tylko EPSG:2180) | przed utworzeniem `FileStorage` / sciezki wycinka |

`FileStorage` waliduje wynik koncowy: segment, w ktorym po wypelnieniu zostala
klamra `{`, konczy sie `ValidationError` z nazwa brakujacego wymiaru
(`_ensure_resolved`). Cichy katalog `pl_{system}_1m_evrf2007` nigdy nie powstanie.

### 3.2 Schema sidecara `kartograf-meta/1`

Kazde udane pobranie przez CLI albo warstwe zarzadzajaca biblioteki
(`download_data`, `DownloadManager`, `download_landcover`, `download_soil`,
`download_pl_cutout`, `download_laz_area`, `download_cz_cutout`,
`download_cz_sheet`, `download_cz_laz`, `download_cz_orto_sheet`,
`download_image_cutout`, `download_collection`, `calculate_hsg`) zapisuje dane
i `<plik>.meta.json`: sidecar wersji w magazynie jest obowiazkowy,
sidecar sciezki standardowej best-effort (sekcja 1). Poza magazynem
`hsg_from_rasters` pisze sidecar best-effort. Bezposrednie wywolanie
providera sidecara nie pisze (sekcja 1).

| Pole | Znaczenie |
|---|---|
| `dataset` | klucz deskryptora zrodla (np. `pl.gugik.nmt_1m`) |
| `country`, `product`, `provider` | kraj, produkt i nazwa dostawcy z deskryptora; `product` = wartosc `--product` pliku (`nmt`, `true-orto`, `admin`, `bdot10k`, `zabaged`, ...), w grupie bez `--product` nazwa komendy i katalogu: `soil download` - `soil`, raster `soil hsg` - `hsg` (`build_metadata(product=)`, produkt pochodny) |
| `horizontal_crs` | faktyczny uklad poziomy pliku: arkusz PL-1992 `EPSG:2180`, arkusz PL-2000 `EPSG:2176`–`EPSG:2179` wedlug strefy godla, CZ natywnie `EPSG:5514`, kafel TM33 `EPSG:3045`; wycinek `--cutout` w ukladzie `--horizontal-crs` (ortofotomapa PL tylko `EPSG:2180`); ortofoto CZ: JPEG i `.jgw` `EPSG:5514`, `.TM33N.jgw` `EPSG:3045`, `.TM34N.jgw` `EPSG:3046` (kazdy plik swoj uklad); kolekcje: wynik obszaru w ukladzie uslugi (PL `EPSG:2180`, CZ `EPSG:5514`), plik krajowy w ukladzie pliku (HY-NET `EPSG:3045`, ZABAGED wybrany `--horizontal-crs`). Dla arkusza PL uklad z godla jest SPRAWDZANY wspolrzednymi pliku (`sources/sidecar.py::pl_sheet_horizontal_crs`): plik opublikowany przez GUGiK w innym ukladzie niz wskazuje godlo (E17, np. arkusze PL-2000 strefy 7 jak `7.125.11.19` w EPSG:2180) dostaje uklad PLIKU, deklaracja rekordu skorowidza zostaje w `extra.source.declared_crs`, logger `kartograf.sources.sidecar` ostrzega, a CLI drukuje `Warning: N arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: ...` (kod bez zmian; segment katalogu nadal wg godla, ADR-026) |
| `vertical_crs` | kod realizacji ukladu pionowego: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007); `null` gdy produkt nie ma pionu (orto) |
| `vertical_source` | `native` / `ellipsoidal` / `server` (z `AccessChannel`) |
| `resolution` | rozdzielczosc z deskryptora: etykieta K2 rejestru (`0.15m`, `0.5m`, `1m`, `10m`, archiwa do `50m`; CZ `0.5m`/`2m`/`5m`) albo `null` (orto PL i CZ - piksel wycinka ortofotomapy niesie `request.resolution`; LAZ PL i CZ, archiwa TIN/TTN, kolekcje) |
| `nodata` | wartosc pustego piksela: dla `.asc` czytana automatycznie z naglowka (`read_asc_nodata`), w torze CZ z tagu GeoTIFF (`download/cz_cutout.py::read_tif_nodata`; w trybie bbox z fallbackiem `CUZK_NODATA`), dla wycinka PL stala `-9999.0`, dla wyniku HSG `0`, dla GeoTIFF CORINE/SoilGrids z `LandCoverManager` z tagu pliku (sekcja 4.8); `null` gdy zadna z tych drog nie ma zastosowania (np. orto) |
| `request` | zadanie, ktore dalo TEN plik: `sheet` (godlo), `bbox` + `bbox_crs` w ukladzie wyniku albo `teryt`; dla kampanii PL `campaigns` (rozwiazane `newest`/`all`, zawsze), `min_year`/`max_year` (gdy podane) i `year` (gdy granice rowne); LAZ: `year`/`min_year`/`max_year`/`min_density` gdy podane, `campaigns` tylko dla `all`; land cover: parametry tresci z domyslnymi wartosciami — SoilGrids `property`/`depth`/`stat`, CORINE `year`, BDOT10k `format` (4.8); wycinek ortofotomapy: `bbox`/`bbox_crs` siatki wyniku, `coverage` i `resolution`; ortofoto CZ: `sheet`; kolekcje: `teryt`, `bbox`/`bbox_crs` w ukladzie uslugi albo `whole_country: true` oraz podane warianty (`level`, `lod`, `year`, `horizontal_crs`). `request` opisuje pierwotne POBRANIE pliku, nie ostatnie wykorzystanie; `extra.parent_request(s)` nie niesie flag roku (3.4) |
| `license` | `{id, attribution, url}` z deskryptora |
| `downloaded_at`, `kartograf_version` | znacznik czasu UTC (ISO 8601, od 0.8.0 z mikrosekundami — porzadek dwoch pobran w jednej sekundzie) i wersja pakietu z `src/kartograf/_version.py::build_version()`: wydanie = samo `__version__`; wersja rozwojowa (`dev`) = `<__version__>+<krotki SHA>` commita, z ktorego zaimportowano pakiet, z sufiksem `.dirty`, gdy sledzone pliki katalogu `kartograf/` maja niezacommitowane zmiany (docs/testy sie nie licza); gdy git jest niedostepny albo pakiet nie pochodzi z repozytorium, w ktorym lezy (`os.path.samefile`), samo `__version__`. Ta sama wartosc w `kartograf --version`; `User-Agent` HTTP niesie samo `__version__` |
| `transform` | slownik osi (`horizontal`/`vertical`) z opisem uzytej operacji w formacie `pinned: <opis> (<dokladnosc> m)`; os bez przeliczenia nie ma klucza, a bez zadnego przeliczenia cale pole to `null` |
| `extra` | `parent_request` (obszar; zadanie, ktore utworzylo plik — `parent_requests` usuniete w 0.8.0); LAZ PL `tile_sheet`/`year`/`nominal_density`/`url`, dodatkowo `acquisition_date`/`full_sheet`, gdy znane; arkusze NMT/NMPT/orto PL `source`, `campaign`, `version` (`label`, `label_source`; ADR-036), `coverage` (lot niepelny, przy zapisie wersji) oraz pola rocznikow/lotow opisane nizej; LAZ, arkusze i wycinki CZ, wycinek PL: `version` (ADR-036, plan 2/3); arkusz CZ `all_nodata`; SM5 (rastry i LAZ CZ) `mapname`/`cz_share`; plik openzu (SM5, natywny kafel TM33, LAZ CZ — plan B) `http` (`etag`, `last_modified`, `content_length` odpowiedzi `openzu`; sygnal swiezosci); wycinek bbox CZ `all_nodata` i `parent_request`; wycinek PL WCS `source`, `mask`, `zero_pixels` (tylko gdy > 0), `all_nodata`, `parent_request` (sekcja 3.2); wycinek ortofotomapy `source`, `all_nodata` (tylko `true`), `http`, `parent_request`; ortofoto CZ `source`, `world_files` (sidecar JPEG), `mapname`/`cz_share`, `http`, `parent_request`; kolekcje `source`, `http`, `parent_request` (nizej); CORINE WMS `fallback`/`note`; HSG `derived` i parametry obliczen |
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

**Wycinek ortofotomapy PL w sidecarze (ADR-042 D14).**
`download/orto_cutout.py` pisze sidecar `pl.gugik.orto` z
`capability="bbox_raster"` (pola ukladow z pierwszego kanalu WCS; Standard
i High maja te same), `horizontal_crs` EPSG:2180, `transform=null`,
`resolution=null` i `request` = `{"bbox": <siatka wyniku>, "bbox_crs":
"EPSG:2180", "coverage": ..., "resolution": ...}` (bbox wyrownany na
zewnatrz do wielokrotnosci piksela, sekcja 4.3). `extra.source` =
`service="WCS"`, faktyczny `endpoint` i `coverage` (id coverage wariantu),
`format`, `scalefactor` (tylko gdy piksel inny niz 0,1 m, np. `0.4` dla
0,25 m) i `composition="server"`. Wynik bez zadnego piksela obrazu nie
zostaje wersja (sekcja 4.3), wiec `extra.all_nodata` nie wystepuje. Maski
PRG i `zero_pixels` nie ma.

**Ortofoto CZ w sidecarze (ADR-042 D13).** `download/cz_orto.py` pisze
sidecar `cz.cuzk.orto` (`capability="sheet_files"`, `request` =
`{"sheet": <godlo>}`) dla kazdego z czterech plikow arkusza:
`horizontal_crs` = uklad pliku (JPEG i `.jgw` EPSG:5514, `.TM33N.jgw`
EPSG:3045, `.TM34N.jgw` EPSG:3046), `extra.source` = `{url,
dataset_feed, edition, year, updated, member}` (`member` = nazwa czlonu
ZIP, np. `WRTO24.2024.CTES96.jpg`), `extra.http` odpowiedzi ZIP,
`extra.mapname`/`extra.cz_share` z indeksu SM5 (best effort)
i `extra.parent_request` (obszar). Sidecar JPEG ma dodatkowo
`extra.world_files` = `{".jgw": "EPSG:5514", ".TM33N.jgw": "EPSG:3045",
".TM34N.jgw": "EPSG:3046"}` - sam plik JGW ukladu nie niesie. Etykieta
wersji = wydanie `<rok>_<updated>` (`label_source="edition"`).

**Kolekcje (ADR-042) w sidecarze.** `download/collections.py::run_job`
wybiera kanal po jego capability (unikalnej w deskryptorze) i zapisuje:
`request` = wybor uzytkownika w tej jednostce (`teryt`, `ku` (mapa katastralna
CZ, z `format`), `tile` (kafel mesh: `<uklad>/<modul>`, np.
`2000/7/78944_6777_74230_55482`), `sheet`, `bbox` +
`bbox_crs` w ukladzie natywnym uslugi albo `whole_country: true`; `year`,
`format`, `lod`, `level`, `horizontal_crs` tylko gdy podane - jedyne
wydanie LoD2 bez `year`), `horizontal_crs` =
uklad pliku (wynik obszaru: `native_crs` kanalu; plik krajowy: uklad
kanalu albo wybrany plik feedu ATOM), `vertical_crs` =
`PackageVariant.vertical_crs` (modele 3D; 2D = `null`), `extra.source`:
paczka `{url, edition?, member?}` (`member` = rozpakowany czlon, EGiB),
plik z feedu ATOM `{url, dataset_feed, edition, updated}` (ZABAGED
kraj), wynik obszaru `{service, protocol, layers: [{code, source, name,
features}], dropped_fields?}` (`dropped_fields` = pole -> posortowane
unikalne wartosci pol `drop_fields` usunietych z GPKG, EGiB `{"DATA": [...]}`);
plik ma tez `extra.http` (naglowki odpowiedzi; GUGiK bez sygnalu, pliki
CUZK z `ETag`/`Last-Modified` = sygnal `http`), a obszar
rozlozony na powiaty albo przeliczony z arkusza/geometrii/innego ukladu -
`extra.parent_request` (sekcja 3.4). Etykieta wersji: `edition` wariantu
(`label_source="edition"`: rocznik BDOT10k, rok modeli 3D), wydanie
z feedu ATOM (data `updated`, np. `2026-10-04`), inaczej data
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
`extra.link = "copy"` z 0.7.x = sciezka nieznana. Nieudany zapis usuwa
stary sidecar dowiazania (opisywalby poprzednia wersje), wiec nastepne
uruchomienie odtwarza dowiazanie i sidecar (ADR-030 errata 10).

**Przedzial lat i pokrycie (ADR-032, ADR-036 D13).** Przy zadaniu z granica
roku sidecar kazdej wersji NMT/NMPT/orto i jego kopia w sciezce
standardowej zawieraja `extra.available_years` (posortowane wszystkie lata
arkusza z pelnego skorowidza); bez granic brak pola. `extra.coverage` (0..1,
cztery miejsca po przecinku) ma sidecar wersji KAZDEGO lotu rastrowego
(`.asc`/`.tif`; archiwa ADR-041 bez pomiaru) bez
`full_sheet=true` — liczone z tego samego odczytu co sha256 przy zapisie
(ASC bez `NODATA_value` = -9999, orto wg nodata/alfa; blad pomiaru = brak
pola + ostrzezenie), nigdy dopisywane pozniej. Przy przedziale i `all`
sidecar standardowy dostaje `extra.flights` (malejaco wg ADR-028; `id`,
`date`, `full_sheet`); gdy ma > 1 lot i dowiazany lot nie ma
`full_sheet=true`, dopisuje tez `coverage` z sidecarow wersji i porownuje
pokrycie. Przy starszym locie o WIEKSZYM pokryciu `extra.better_coverage` =
jego `id` (lot zadeklarowany jako pelny liczy sie jako pokryty w pelni) i
CLI `Info:` na stderr (takze z `-q`). Pole `better_coverage` jest usuwane,
gdy ponowne zadanie nie wykaze lepszego lotu. Pokrycie NIE przestawia
dowiazania (najpierw najnowszy lot wg ADR-028, zasada "nigdy wstecz").
Sidecar LAZ niesie dodatkowo `extra.acquisition_date` (`akt_data`)
i `extra.full_sheet` (`czy_ark_wypelniony`), gdy znane.

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
│   ├── cz_dmr4g_bpv/CTES/96/CTES96.tif      # DOWIAZANIE; sidecar wersji z extra.http (ETag)
│   ├── cz_dmr4g_evrf2007/760/5518/760_5518.tif   # natywny kafel TM33 z pliku openzu (plan B), extra.http
│   └── pl_1992_100m/teryt/12.zip            # NMT 100 m: ZIP z XYZ wojewodztwa 1:1 (feed ATOM; uklad wysokosci nieznany)
├── nmpt/
│   ├── pl_1992_1m_evrf2007/...              # (+ _kron86, + pl_2000_..., + 0.5m, 0.6m, xyz_0.5m/xyz_1m KRON86)
│   ├── pl_1992_1m_evrf2007/bbox/<coords>.tif # DOWIAZANIE: wycinek NMPT WCS
│   ├── cz_dmpok_bpv/CTES/96/CTES96.tif      # DMP OK 0.5m, arkusz SM5 z pliku openzu (plan B)
│   ├── cz_dmpok_evrf2007/760/5518/760_5518.tif   # DMP OK, natywny kafel TM33 z pliku openzu
│   └── cz_dmp1g_bpv/bbox/<coords>.tif       # DMP 1G 2m: wycinek ImageServer (kafel TM33: warp)
├── orto/
│   ├── pl_1992/...                          # arkusze; bez ukladu pionowego
│   ├── pl_1992_cir/...                      # wariant CIR (B/W: pl_<uklad>_bw), E12
│   ├── pl_1992_standard_0.25m/bbox/<coords>.tif   # DOWIAZANIE: wycinek WCS ortofotomapy (4.3, ADR-042 D14)
│   ├── pl_1992_high_0.1m/versions/bbox/2026-10-16_<sha8>/<coords>.tif   # wersja wycinka High
│   ├── cz_sjtsk/CTES/96/CTES96.jpg          # DOWIAZANIE: ortofoto CZ, JPEG z ZIP CUZK 1:1 (4.4, ADR-042 D13)
│   ├── cz_sjtsk/CTES/96/CTES96.jgw          # + CTES96.TM33N.jgw i CTES96.TM34N.jgw (pliki georeferencji)
│   └── cz_sjtsk/versions/AS/91/2025_2026-02-24_<sha8>/AS91.jpg   # wersja (etykieta <rok>_<updated>); godlo As
├── true-orto/
│   ├── pl_1992/N-34/50/A/c/3/2/3/N-34-50-A-c-3-2-3.tif   # true orto: arkusz 8-czlonowy (plan E1)
│   └── pl_1992_0.05m/bbox/<coords>.tif      # DOWIAZANIE: wycinek WCS True_Orthoimagery
├── oblique-orto/pl_2000/7/125/11/08/7.125.11.08_n.tif   # orto ukosna: plik na kierunek (_n, _e, _s, _w)
├── laz/pl_2000_evrf2007/<hier>/<plik>.laz   # DOWIAZANIE; uklad poziomy per kafel (uklad_xy), pionowy z flagi
├── laz/pl_2000_evrf2007/versions/<hier>/<data>_<zgloszenie>_<sha8>/<plik>.laz   # wersja (D26)
├── laz/cz_dmr5g_bpv/CTES/96/CTES96.laz      # DOWIAZANIE: LAZ CZ (plan B) 1:1 z ZIP openzu; SM5 = EPSG:5514/Bpv
├── laz/cz_dmr5g_bpv/versions/CTES/96/<data>_<sha8>/CTES96.laz   # wersja
├── laz/cz_dmpok_evrf2007/760/5518/760_5518.laz   # kafel TM33 = EPSG:3045/EVRF2007
├── intensity/pl_1992/M-34/64/D/d/1/4/M-34-64-D-d-1-4.tif   # obraz intensywnosci (1 pasmo; + pl_2000/...)
├── contours/cz_zabaged_shp/CTES/96/CTES96.zip   # warstwice ZABAGED: ZIP arkusza SM5 1:1 (+ cz_zabaged_dgn)
├── landcover/
│   ├── pl_bdot10k_gpkg/teryt/1465.gpkg          # DOWIAZANIE; wersje w versions/teryt/<data>_<sha8>/
│   ├── pl_bdot10k_gpkg_ptwp-swrs/teryt/1465.gpkg # filtr warstw (kody posortowane, lowercase)
│   ├── pl_bdot10k_gpkg_zip/teryt/1465.zip      # keep_raw: oryginalny ZIP paczki
│   ├── pl_bdot10k_shp/teryt/1465.zip           # paczka SHP
│   ├── pl_bdot10k_shp_2024/teryt/1261.zip      # archiwum rocznikow (regula 9); wersje 2024_<sha8>
│   ├── pl_bdot10k_shp_2023/versions/teryt/2023_<sha8>/1261.zip   # rocznik identyczny z 2022: hardlink (D7)
│   ├── eu_corine_2018/N-34/130/D/N-34-130-D.tif  # CLMS; wersje <wydanie>_<sha8> (np. V2020_20u1_...)
│   ├── eu_corine_2018_preview/bbox/<coords>.png  # podglad WMS bez credentials (D31)
│   ├── cz_zabaged/bbox/<coords>.gpkg           # ZABAGED obszaru (REST, 22 warstwy), EPSG:5514
│   ├── cz_zabaged_gpkg_5514/country/cz.zip     # plik krajowy z feedu ATOM; wersje 2026-10-04_<sha8> (wydanie)
│   ├── pl_bdoo_2023/teryt/12.zip               # BDOO: paczka GML wojewodztwa 1:1; wersje 2023_<sha8> (rocznik)
│   ├── pl_bdoo_2023_kuik-ptwp/teryt/12.zip     # --layers: ZIP plikow wybranych klas (kody posortowane)
│   ├── cz_data50/bbox/<coords>.gpkg            # Data50 obszaru (REST, 69 warstw), EPSG:5514; cz_data250: 116
│   └── cz_data50_shp_5514/country/cz.zip       # plik krajowy SHP z feedu ATOM; wersje 2026-04-28_<sha8>
├── boundaries/
│   ├── pl_prg_gmina/bbox/<coords>.gpkg         # obiekty obszaru (WFS), EPSG:2180; wersje <data>_<sha8>
│   ├── pl_prg_gml/teryt/12.zip                 # paczka wojewodztwa 1:1
│   ├── pl_prg_shp/country/pl.zip               # plik krajowy (--whole-country)
│   ├── pl_prg_addresses/bbox/<coords>.gpkg     # punkty adresowe i ulice obszaru (WFS KIN), EPSG:2180
│   ├── pl_prg_addresses_shp/teryt/1261.zip     # paczka powiatu 1:1; plik krajowy: _shp albo _gml, country/pl.zip
│   ├── pl_prg_special/bbox/<coords>.gpkg       # granice specjalne obszaru (OGC API, warstwa na rodzaj), OGC:CRS84
│   ├── pl_prg_special_shp/country/pl.zip       # plik krajowy (+ pl_prg_special_gml)
│   ├── cz_ruian_obec/bbox/<coords>.gpkg        # RUIAN obszaru (REST), EPSG:5514, np. -470000_-1130000_...
│   ├── cz_ruian_shp/country/cz.zip             # plik krajowy SHP (sygnal http)
│   └── cz_geomorphology_celek/bbox/<coords>.gpkg   # jednostki geomorfologiczne poziomu --level (REST), EPSG:5514
├── cadastre/
│   ├── pl_egib/bbox/<coords>.gpkg              # dzialki i budynki obszaru (WFS), bez tokenu
│   ├── pl_egib_gpkg/teryt/1261.gpkg            # eksport powiatu (GPKG rozpakowany z ZIP)
│   ├── pl_rcn/teryt/1261.gpkg                  # RCN: eksport powiatu (teryt/12.gpkg - wojewodztwa), GPKG z ZIP
│   └── cz_cadastral-map_shp/ku/623164.zip      # mapa katastralna CZ: paczka KU 1:1 (+ _dxf, _dgn, _vfk; sygnal http)
├── models3d/
│   ├── pl_buildings_lod1_2024/teryt/1261.zip   # CityGML 1:1; wersje 2024_<sha8> (rok wydania)
│   ├── pl_trees_lod1_2023/teryt/3063.zip       # drzewa CityGML 1:1 (paczka 0,3-25 GB); wersje 2023_<sha8>
│   └── pl_mesh/2000/7/78944_6777_74230_55482.zip   # kafel mesh = plik rekordu indeksu (OBJ+MTL+JPG 1:1),
│                                               # katalog = uklad rekordu: 1992 albo 2000/<strefa>;
│                                               # wersje <Aktualnosc>_<zgloszenie>_<sha8>
├── hydro/
│   ├── cz_hynet/bbox/<coords>.gpkg             # HY-NET obszaru (WFS: WatercourseLink, HydroNode), EPSG:5514
│   └── cz_hynet_gpkg/country/cz.zip            # plik krajowy (GPKG w ZIP, EPSG:3045, sygnal http)
├── geodesy/
│   ├── pl_control_horizontal/bbox/<coords>.gpkg      # punkty sieci obszaru (WFS sieci), EPSG:2180
│   ├── pl_control_horizontal_xls/teryt/1201.zip      # paczka powiatu (wykazy XLS, opisy JPG) 1:1
│   ├── pl_control_archive-1942/N-33/58/N-33-58.zip   # archiwum arkusza 1:100 000 1:1
│   ├── pl_geoid2021_evrf2007/country/pl.txt          # model quasi-geoidy PL-geoid2021 1:1 (TXT)
│   ├── cz_control_vertical/bbox/<coords>.gpkg        # Bodove pole: warstwy sieci, EPSG:5514
│   └── cz_qgzu2013_bpv/country/cz.zip                # QGZU-2013 z feedu ATOM; wersje 2021-02-22_<sha8>
├── names/
│   ├── pl_prng/bbox/<coords>.gpkg              # PRNG obszaru (OGC API), OGC:CRS84 (+ pl_prng_world/)
│   ├── pl_prng_shp/country/pl_miejscowosci.zip # plik krajowy 1:1 (+ pl_obiekty-fizjograficzne.zip; _gml, _xlsx)
│   ├── cz_geonames/bbox/<coords>.gpkg          # Geonames obszaru (REST, 25 warstw), EPSG:5514
│   └── cz_geonames_gpkg_5514/country/cz.zip    # plik krajowy z feedu ATOM (+ _fgdb, _3045); etykieta = wydanie
├── maps/
│   ├── pl_bdot10k_10000_tiff/M-34/64/D/d/1/M-34-64-D-d-1.tif   # wizualizacja BDOT10k; etykieta = data Stan bazy
│   └── cz_ztm_10000_sjtsk_tiff/0510/D/11/0510-D-11.zip   # ZTM: hierarchia godla (PDF: .pdf; sygnal http)
├── soil/global_soilgrids_clay_0-5cm_mean/bbox/<coords>.tif   # wersje 2.0_<sha8> (wydanie)
└── hsg/global_soilgrids_0-5cm_mean/bbox/<coords>.tif         # pochodna z wersji clay/sand/silt (D33)
```

**Reguly segmentow:**

1. Segment ma postac `<kraj>_<uklad>[_<wariant>][_<vcrs>]`, wszystkie wartosci
   lowercase. Uklad PL: `1992` / `2000`. Uklad pionowy: `kron86` /
   `evrf2007` / `bpv`. CZ nie niesie ukladu poziomego: w jego miejscu stoi
   model (`dmr5g`, `dmr4g`, `dmpok`, `dmp1g`), a uklad pliku wynika z godla
   — arkusz SM5 EPSG:5514, kafel TM33 EPSG:3045 (plik openzu albo warp
   z ImageServer; plan B); wycinek `bbox/` ma uklad `--horizontal-crs`
   (sidecar). W LAZ CZ uklad wysokosci wyznacza pliki (Bpv = arkusze SM5,
   EVRF2007 = kafle TM33), wiec `cz_<model>_<vcrs>` wskazuje je jednoznacznie.
   Ortofoto CZ (plan D) ma segment `orto/cz_sjtsk` (uklad JPEG i `.jgw`;
   `.TM33N.jgw` i `.TM34N.jgw` leza obok w tym samym katalogu), wycinek
   ortofotomapy PL - `orto/pl_1992_<coverage>_<res>` (regula 5). Obrazy
   planu E1 maja wlasne katalogi produktu (regula 10) z segmentem
   `pl_<uklad>`: `intensity/pl_1992`, `true-orto/pl_1992` (wycinek
   `true-orto/pl_1992_<res>`), `oblique-orto/pl_2000`.
   Czlon NMT/NMPT PL miedzy ukladem a `<vcrs>` pochodzi z szablonu
   deskryptora (`registry.py::_pl_sheet_source`, sekcja 3.1; to nie
   `<wariant>` z reguly 5): siatka ASC — sama etykieta
   (`pl_1992_0.5m_evrf2007`), archiwum — token formatu przed etykieta
   (`pl_1992_tbd_25m_kron86`, `pl_1992_ascii-nmt_1m_evrf2007`), format
   bez rozdzielczosci — sam token (`pl_1992_tin_kron86`).
2. Hierarchia wewnatrz segmentu jest bez zmian — `parser_registry.path_parts`:
   PL-1992 `N-34-130-D-d-2-4` -> `N-34/130/D/d/2/4`, PL-2000 `6.179.12.20` ->
   `6/179/12/20`, TM33 `302_5550` -> `302/5550`, SM5 `CTES96` -> `CTES/96`,
   a dwuliterowe godla SM5 (99 arkuszy As, `AS22`...`AS94`) `AS91` ->
   `AS/91` (`path_parts` = `[godlo[:-2], godlo[-2:]]`; od 0.8.0 - wczesniej
   wzorzec SM5 mial 4 litery i `AS91` trafial do fallbacku PL-1992).
   Arkusze map CUZK (ZTM, `MAPNOM` warstwy `KladyMapovychListu`) maja te
   sama hierarchie (`parser_registry.cuzk_map_path_parts`, ADR-044 D7):
   S-JTSK `0510-D-11` -> `0510/D/11`, ETRS89 `NM-34-07-1-D-15` ->
   `NM-34/07/1/D/15` (arkusz 1:1 000 000 w jednym katalogu jak `N-34`).
3. Podkatalog `bbox/` wewnatrz segmentu trzyma dowiazania wycinkow PL WCS
   (`--cutout`; NMT/NMPT i ortofotomapa) i CZ: `<coords>.tif` bez daty
   (D15); wersje w `<segment>/versions/bbox/<RRRR-MM-DD>_<sha8>/<coords>.tif`.
   Wspolrzedne sa w ukladzie WYNIKU (`--horizontal-crs`), formatowane
   `%.10g` i sklejane `_`. Nazwa niesie ZADANIE, nie dokladny zasieg
   rastra: wycinek PL w EPSG:2180 siega do < 1 px dalej po wyrownaniu
   na zewnatrz do siatki 1 m, a siatka warpa (`warp_to_grid` z
   `transform/raster.py`, wspolna dla PL i CZ) ma calkowita liczbe
   pikseli od NW, wiec E/S moze odbiegac o do 0,5 px (sekcja 4.3).
   Wyjatek: wycinek ortofotomapy niesie w nazwie siatke WYNIKU (bbox
   wyrownany na zewnatrz do wielokrotnosci piksela). PL bez
   `--cutout` zapisuje arkusze w hierarchii godel (sekcja 4.2).
4. Rozdzielczosc wchodzi do segmentu tylko tam, gdzie jest parametrem API
   (NMT/NMPT): etykieta K2 z rejestru (`0.15m`, `0.5m`, `0.6m`, `1m`, `5m`,
   `10m`; archiwa takze `15m`..`50m`), ta sama co `--resolution`
   i `resolution` sidecara. Nie ma jej dla CZ (model wyznacza ja 1:1:
   `dmr5g` 2 m, `dmr4g` 5 m, `dmpok` 0,5 m, `dmp1g` 2 m) ani dla arkuszy
   orto i LAZ (brak takiego parametru); wycinek ortofotomapy ma piksel
   w tokenie segmentu (regula 5).
5. `<wariant>` rozroznia pliki tego samego godla i ukladu, ktore nie sa tym
   samym produktem (E12, 2026-10-06). Wariant deklaruje tylko orto
   (`storage_variant`; w `BaseProvider` domyslnie `None`): RGB
   bez sufiksu w `orto/pl_<uklad>/` (bez migracji), CIR w
   `orto/pl_<uklad>_cir/`, B/W w `orto/pl_<uklad>_bw/`. Wariant pochodzi
   z `provider.storage_variant` (`GugikOrtoProvider(color=...)`) i trafia do
   `FileStorage(variant=...)`; bez niego skip zwracal po cichu plik RGB na
   zadanie CIR. Wycinek ortofotomapy (plan D, ADR-042 D14) ma tokeny
   `<coverage>_<res>` dopisane do segmentu PL-1992 (`token_segment`):
   `orto/pl_1992_standard_0.25m/`, `orto/pl_1992_high_0.1m/` - wariant WCS
   i piksel to rozne tresci; koloru w segmencie nie ma (wycinek jest tylko
   RGB). Wycinek true orto (jedna usluga WCS) ma sam piksel:
   `true-orto/pl_1992_0.05m/`.

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
   `serverino`), potwierdzenie trescia: ten sam rozmiar i sha256 dowiazania =
   sha256 sidecara wersji (`links._same_content`). Liczba dowiazan nie
   bierze udzialu w potwierdzeniu: klient cifs zglasza `st_nlink` = 1 dla
   sciezki, ktora wlasnie otwarto (takze tym odczytem), przez kilka sekund
   albo dluzej, wiec liczba zmienialaby wynik miedzy kolejnymi wywolaniami
   (e2e 0.8.0: dowiazanie cofniete na starszy lot). Sciezka o tresci wersji
   JEST ta wersja (`links._hold`), takze gdy jest niezalezna kopia, i od jej
   klucza zalezy "nigdy wstecz"; `ensure_link` zamienia taka kopie z
   powrotem w hardlink TEJ samej wersji, gdy zadna ze sciezek nie zglasza
   drugiej nazwy (`_Held.lone`, np. po `rsync -a` bez `-H`), a w innym
   przypadku niczego nie zapisuje. `FileStorage.get_versions_root(sheet)`/
   `get_versions_base`,
   `list_files()` pomija `versions/`, `full_sheet/` i `kampanie/`
   (`versions=True` = tylko pliki wersji). Katalog `kampanie/` z 0.7.x
   nie jest czytany (`has_legacy_campaigns()` -> `Info:` w CLI). Od planu
   2/3 te sama mechanika maja kafle LAZ (etykieta `<akt_data>_<zgloszenie>`,
   D26; `FileStorage.get_raw_versions_root/base(sheet, system=)`), arkusze
   CZ i od planu B pliki LAZ CZ (etykieta = data pobrania UTC), ortofoto CZ
   (plan D: kazdy z czterech plikow arkusza ma wlasne wersje
   w `versions/<hierarchia SM5>/`, etykieta = wydanie `<rok>_<updated>`)
   i wycinki `bbox/` (hierarchia `bbox`,
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
   wg reguly 10 (`download/storage.py::content_segment`):
   BDOT10k `gpkg[_<warstwy>]`/`gpkg_zip`/`shp` (archiwum rocznikow -
   regula 9), CORINE `<rok>[_preview]`, SoilGrids
   `<wlasciwosc>_<glebokosc>_<stat>`, HSG `<glebokosc>_<stat>`.
   Pod segmentem (`download/storage.py::unit_slot`): `teryt/<T><ext>`
   (BDOT10k, takze przy wyborze bboxem/arkuszem), `bbox/<coords><ext>`
   (EPSG:2180, `.10g`, jak wycinki) albo hierarchia godla (`path_parts`,
   kanoniczne godlo). Wersje jak w regule 6 (`versions/<ta sama
   hierarchia>/`).

9. **Kolekcje (ADR-042 D8; rozszerzenie reguly 8).**
   `<grupa>/<kraj>_<zrodlo>[_<tokeny>]/{teryt/<T>|bbox/<coords>|country/<kod>|ku/<kod>|<hierarchia godla>|<uklad>[/<strefa>]/<plik>}<ext>`:
   segment = prefiks `storage_subdir` + tokeny wariantu tresci
   (`content_segment`), pod nim `unit_slot`: `teryt/<T>` (paczka powiatu
   albo wojewodztwa - takze, gdy obszar rozlozono na powiaty z PRG; BDOO:
   wojewodztwa tych powiatow), `bbox/<coords>` (wynik obszaru; wspolrzedne
   w ukladzie NATYWNYM uslugi, `.10g`, `_`) albo `country/<kod>` (plik
   krajowy, `pl`/`cz`); wersje w `<segment>/versions/<ta sama
   hierarchia>/`. Tokeny = wariant tresci: poziom (`pl_prg_gmina`), LoD
   i rok (`pl_buildings_lod1_2024`), format i rocznik archiwum
   (`pl_bdot10k_shp_2024`), rocznik i wybrane klasy BDOO
   (`pl_bdoo_2023_kuik-ptwp`, kody posortowane). Wynik obszaru (zawsze GPKG
   w ukladzie natywnym) nie ma tokenu formatu; paczka i plik krajowy maja
   token formatu zrodla, gdy produkt ma kilka formatow albo takze wynik
   obszaru (`pl_prg_gml`, `pl_prg_shp`, `pl_egib_gpkg` obok `pl_egib`),
   a gdy zrodlo publikuje plik w kilku ukladach - takze kod EPSG (plan D).
   Segmenty CZ (plan D): `landcover/cz_zabaged` (wynik obszaru),
   `landcover/cz_zabaged_gpkg_5514` i `_3045` (plik krajowy w dwoch
   ukladach), `boundaries/cz_ruian_<poziom>` (np. `cz_ruian_obec`),
   `boundaries/cz_ruian_shp`, `hydro/cz_hynet`, `hydro/cz_hynet_gpkg`;
   plan E4: `landcover/cz_data50` i `landcover/cz_data50_shp_<5514|3045>`
   (tak samo `cz_data250`); plik krajowy CZ to `country/cz`, a
   `bbox/<coords>` CZ ma wspolrzedne EPSG:5514 (ujemne, np.
   `-460000_-1120000_-450000_-1110000.gpkg`). Plan E: kafel indeksu ma slot
   `<uklad>[/<strefa>]/<plik>` (mesh: uklad rekordu `1992` albo `2000`
   i strefa PL-2000 `5`-`8`, nazwa pliku rekordu, np.
   `models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip`), arkusz -
   hierarchie godla (`geodesy/pl_control_archive-1942/N-33/58/`, arkusz ZTM
   `maps/cz_ztm_10000_sjtsk_tiff/0510/D/11/0510-D-11.zip`, arkusz
   wizualizacji BDOT10k), a segmenty E5 to `models3d/pl_trees_lod1_2023`,
   `geodesy/pl_control_<siec>` (obszar), `geodesy/pl_control_<siec>_xls`
   (paczka powiatu: wykazy XLS i opisy JPG), `geodesy/pl_geoid2021_evrf2007`,
   `geodesy/cz_control_<siec>` i `geodesy/cz_qgzu2013_bpv` (QGZU-2013 to
   quasi-geoida wysokosci Bpv, jak PL-geoid2021 dla EVRF2007).
   KU mapy katastralnej CZ ma slot `ku/<kod>`
   (`cadastre/cz_cadastral-map_<format>/ku/623164.zip`), temat pliku
   krajowego - `country/<kraj>_<temat>`
   (`names/pl_prng_shp/country/pl_miejscowosci.zip`). Segmenty E2 i E3:
   `names/pl_prng[_<format>]`, `names/pl_prng_world[_<format>]`,
   `names/cz_geonames[_<format>_<epsg>]`, `maps/pl_bdot10k_<skala>_<format>`,
   `maps/cz_ztm_<skala>_<uklad>_<format>`, `boundaries/pl_prg_addresses[_<format>]`,
   `boundaries/pl_prg_special[_<format>]`, `boundaries/cz_geomorphology_<poziom>`,
   `cadastre/pl_rcn` i `cadastre/cz_cadastral-map_<format>`.
   Rozne tresci nigdy nie dziela slotu. Identyczna tresc innego wydania tej
   samej jednostki, formatu i LoD (`FileSlot.related_roots`, D7) nie zajmuje
   miejsca drugi raz: nowa wersja jest hardlinkiem do istniejacych danych
   (`relabeled`, `same_as` = etykieta znalezionej wersji).

10. **Konwencja nazw kluczy i katalogow (ADR-044 D7).** Jedna konwencja dla
    kluczy zrodel i nazw w `data/`. Spelniaja ja segmenty z wydan <= 0.7.2
    (`nmt/pl_1992_1m_evrf2007`, `orto/pl_1992_cir`, `laz/pl_2000_kron86`,
    `nmt/cz_dmr5g_bpv`) i regula 8; produkty nowe w 0.8.0 nazwano wg niej
    przed wydaniem (bez migracji). Pilnuje jej test rejestru
    `tests/unit/test_sources_registry.py::TestNamingConvention`.
    - **Klucz zrodla** = `<kraj>.<dostawca>.<nazwa>`: kraj deskryptora (`pl`,
      `cz`, `eu`, `global`), dostawca (`gugik`, `cuzk`, `clms`, `isric`),
      `<nazwa>` - slowa `[a-z0-9]` laczone `_` (w kluczu nie ma `-` ani
      kropki: `0.5m` -> `0_5m`), zlozone z calych slow sciezki `data/`:
      nazwy zbioru z segmentu (`hynet`, `geoid2021`, `cadastral-map` ->
      `cadastral_map`) albo katalogu produktu, gdy segment zaczyna sie od
      ukladu (`orto`, `true-orto` -> `true_orto`), z tokenami stalymi
      deskryptora (`nmt_tbd_25m`, `zabaged_contours_shp`) i z katalogiem,
      gdy zbior ma deskryptory w kilku katalogach (`dmr5g_laz`,
      `bdot10k_maps`). Klucz to pole `dataset` sidecara; `pl.gugik.nmpt`
      (NMPT 1 m bez `_1m`) zostaje z 0.7.
    - **Katalog najwyzszego poziomu** = wartosc `--product` w `elevation`
      i `imagery` (`nmt/`, `true-orto/`, `oblique-orto/`), nazwa grupy CLI
      w pozostalych grupach (`landcover/`, `geodesy/`); `soil hsg` -> `hsg/`.
    - **Segment** = `<kraj>_<token>[_<token>...]`, male litery; `_` wylacznie
      miedzy tokenami; token to litery i cyfry, `-` miedzy slowami jednego
      tokenu (`ascii-nmt`, `cadastral-map`, `horizontal-detailed`,
      `archive-1942`, `0-5cm`, kody `ptwp-swrs`), `.` tylko w liczbie
      (`0.5m`). Po kraju stoi uklad PL (regula 1) albo nazwa zbioru: skrot
      dostawcy bez spacji i myslnikow (`dmr5g` z DMR 5G, `hynet` z HY-NET,
      `qgzu2013` z QGZU-2013), a bez ustalonego skrotu slowa angielskie
      (`buildings`, `control`, `cadastral-map`). Tokeny wariantu to wartosci
      wyborow, ktore go wybieraja, malymi literami (`--level gmina`,
      `--network horizontal-detailed`, `--format SHP` -> `shp`, `--year 2024`,
      `--lod 1` -> `lod1`, `--scale 1:10000` -> `10000`, `--sheet-system
      sjtsk`, `--horizontal-crs EPSG:3045` -> `3045`, `--resolution 0.5m`,
      `--layers PTWP,SWRS` -> `ptwp-swrs`); tresc bez wyboru nazywa token
      formatu pliku (`gpkg`, `xls`; regula 9) i uklad wysokosci danych
      (`evrf2007`, `bpv`) - ten zawsze na koncu (regula 1). Kolejnosc
      tokenow produktu ustala jego deskryptor (`segment_tokens`).
    - **Uklad PL** wszedzie `1992`/`2000` (token segmentu albo katalog),
      strefa PL-2000 - jej numer jako katalog pod `2000`, tak jak pierwszy
      czlon godla PL-2000 (`nmt/pl_2000_1m_evrf2007/6/179/...`,
      `models3d/pl_mesh/2000/7/<plik>`, `models3d/pl_mesh/1992/<plik>`);
      nigdy `pl1992`, `s7` ani `PL-2000:S7`.
    - **Hierarchia arkusza** = wszystkie czlony godla jako katalogi
      (regula 2), plik = pelne godlo; takze arkusze ZTM, nigdy plasko.
    - **Nazwa pliku** = kod jednostki (TERYT, `pl`/`cz`, kod KU, godlo,
      `<coords>`, plik rekordu kafla), dopisek po `_`: temat pliku krajowego
      (`country/pl_miejscowosci.zip`, `pl_obiekty-fizjograficzne.zip`),
      kierunek orto ukosnej (`7.125.11.08_n.tif`). Czlony ZIP zapisywane 1:1
      zachowuja nazwy zrodla (`CTES96.TM33N.jgw`).
    - **Stabilnosc klucza (kontrakt z konsumentami magazynu, KA-8
      Archiwisty).** Klucz zrodla opublikowany w wydaniu sie nie zmienia:
      sidecary wersji sa niezmienne (ADR-036), wiec kazdy zapisany kiedys
      `dataset` zostaje na dysku. Zmiana nazwy klucza idzie wylacznie przez
      tabele aliasow czytnika (`_DEV_DATASETS` w `src/kartograf/store.py`):
      surowy `dataset` w sidecarze i w `Sidecar.dataset` zostaje bez zmian,
      `Sidecar.dataset_key` podaje biezacy klucz deskryptora, a klucz
      nieznany rejestrowi daje `dataset_key=None`, nie blad (3.3.1).
      Dostawca jest w polu `provider` sidecara (`provider_name`
      deskryptora: `GUGiK`, `CUZK`, `Copernicus CLMS`, `ISRIC`), kraj w polu
      `country`; srodkowa czesc klucza nie jest identyfikatorem dostawcy,
      a konsument porownuje klucz w calosci i nie wyprowadza z niego
      produktu, wariantu, dostawcy ani kraju (bierze je z sidecara
      i `describe_segment`). Pierwsza czesc klucza zbioru ponadnarodowego
      to zasieg (`eu.clms.corine`, `global.isric.soilgrids`).

Nowe zrodlo rastrowe wymaga providera i toru dyspozycji (sekcja 5), ale
jego `storage_subdir` (wg reguly 10, np. `nmt/de_bb_dgm1_dhhn2016/`) nie
wymaga specjalnej reguly w kodzie sciezek; produkt kolekcji (regula 9) to
sam wpis deskryptora z parametrami kanalu.

**Katalogi najwyzszego poziomu** (grupa CLI i wybor produktu):

| Katalog | Grupa CLI | Wybor |
|---|---|---|
| `nmt/` | `elevation` | `--product nmt` |
| `nmpt/` | `elevation` | `--product nmpt` |
| `laz/` | `elevation` | `--product laz` |
| `contours/` | `elevation` | `--product contours` (CZ) |
| `orto/` | `imagery` | `--product orto` |
| `true-orto/` | `imagery` | `--product true-orto` |
| `oblique-orto/` | `imagery` | `--product oblique-orto` |
| `intensity/` | `imagery` | `--product intensity` |
| `landcover/` | `landcover` | `--product bdot10k`, `bdoo`, `corine`, `zabaged`, `data50`, `data250` |
| `soil/` | `soil` | `soil download --property` |
| `hsg/` | `soil` | `soil hsg` |
| `boundaries/` | `boundaries` | `--product admin`, `addresses`, `special`, `geomorphology` |
| `cadastre/` | `cadastre` | `--product map`, `prices` |
| `models3d/` | `models3d` | `--product buildings`, `trees`, `mesh` |
| `hydro/` | `hydro` | `--product network` |
| `names/` | `names` | `--product geographic`, `world` |
| `maps/` | `maps` | `--product topographic` |
| `geodesy/` | `geodesy` | `--product control`, `geoid` |

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

### 3.3.1 Publiczny odczyt magazynu (ADR-045, v0.8.0)

Odczyt `data/` bez zapisu (takze z udzialu SMB zamontowanego tylko do
odczytu) dla Archiwisty i innych czytnikow - jeden kontrakt `data/`
z 3.2-3.3, bez prywatnego parsera po stronie konsumenta. W
`kartograf.__all__`: `list_segments`, `list_partitions`, `iter_store`,
`read_sidecar`, `describe_segment`, `link_target` (modul `src/kartograf/store.py`),
`file_footprint`, `pinned_transform` (`src/kartograf/store_geometry.py`), typy
ponizej i `InvalidSidecarError` (atrybut `path`). Funkcje nie tworza
katalogow, cache ani plikow w magazynie; indeks i cache trzyma
wywolujacy lokalnie. Publiczne rekordy:

| Rekord | Pola i semantyka |
|---|---|
| `StoreEntry` | `kind`: `version`, `link` (sciezka standardowa), `full_sheet`, `problem`; `segment` (`produkt/wariant`), `hierarchy` (katalog slotu wzgledem segmentu, a dla wersji i `full_sheet` - wzgledem `versions/` i `full_sheet/`; `""` dla problemu segmentu), `name`, `path` (zbudowana z `output_dir` w podanej postaci), `version_path` (wersja wskazana przez `extra.link_target` dowiazania, sprawdzona leksykalnie: lezy w slocie tego dowiazania; dla wersji jej wlasna sciezka; `None` = nieznana), `label` i `sha8` (z nazwy katalogu `<etykieta>_<sha8>`; dowiazanie bez znanej wersji - z sidecara), `sidecar` (`Sidecar` albo `None`), `problem` (`missing_sidecar`, `invalid_sidecar`, `unknown_segment`, `legacy_campaigns`, `stale_incoming`) i `skipped` (`True` = wersja z `skip_versions`, sidecar nieczytany). |
| `Sidecar` | Typowane pola z 3.2 (`schema`, `dataset` surowy, `dataset_key` z rejestru albo `None`, `country`, `product`, `provider`, `horizontal_crs`, `vertical_crs`, `vertical_source`, `resolution`, `nodata`, `request`, `license`, `downloaded_at`, `kartograf_version`, `transform`, `extra`, `sha256`, `size_bytes`) i pola wyliczone `data_year`, `data_date`, `campaign`, `survey_work_id`, `edition`, `full_sheet`, `coverage`, `unit`, `raw`. Brak wartosci albo wartosc o nieoczekiwanym typie to `None`, a oryginalny JSON (`raw`) pozostaje bez zmian. |
| `SegmentInfo` | `segment`, `product`, `country`, `dataset_key`, `name`, `known`. Nazwa jest ludzka: nazwa deskryptora + wariant (uklad, uklad wysokosci, format, rocznik, LoD, poziom); brak dopasowania do rejestru = `known=False`, nigdy przypuszczalny deskryptor. |
| `Footprint` | `native: BBox`, `wgs84: BBox` (EPSG:4326, dlugosc/szerokosc), `source`: `request`, `sheet`, `header`, `unit`. Brak sprawdzonego obrysu = `None` (w tym paczki krajowe). |

`list_segments(output_dir)` zwraca posortowane `<produkt>/<wariant>`
wszystkich prawdziwych katalogow drugiego poziomu (bez dowiazan
symbolicznych i nazw zaczynajacych sie od `.`), takze nieznanych rejestrowi.
Brak `output_dir` to `OSError`, nie pusty magazyn (odlaczony udzial).

`iter_store(output_dir, *, segment=None, units=None, skip_versions=None,
partition=None)` to generator; bez `segment` przechodzi segmenty
z `list_segments` po kolei; `partition` (wymaga `segment`, wyklucza
`units`) to jedna czesc z `list_partitions` (nizej).
W segmencie kolejnosc: dowiazania, `full_sheet`, wersje, pozostalosci;
wpis wychodzi, zanim powstanie listing kolejnych katalogow. `units`
(wymaga `segment`) to nazwy jednostek, nie prefiksy: godlo PL-1992/2000,
TM33, SM5, arkusz ZTM albo kafel LAZ (slot = katalog hierarchii godla ze
WSZYSTKIMI plikami arkusza: nazwy plikow LAZ z URL, kierunki orto ukosnej,
pliki georeferencji), `teryt/<kod>`, `bbox/<coords>`, `country/<kod>`,
`ku/<kod>` albo `<katalog>/<nazwa pliku bez rozszerzenia>` (kafel mesh
`2000/7/<plik>`); sam kod TERYT, `<coords>` i kraju tez dziala (6 cyfr =
KU w segmencie, ktorego kanal paczek ma jednostke `ku`). Plik krajowy
z motywem to `<kraj>_<motyw>` (`pl_miejscowosci`) - dokladnie ta nazwa,
ktora zwraca `Sidecar.unit` (wyprowadzona z nazwy pliku slotu, bo motywu
nie ma w `request`), wiec `unit` z indeksu zamyka petle odswiezania
`iter_store(units=[unit])`. Tak samo kafel LAZ: wybrany dla obszaru albo
arkusza ma w `request.bbox` ten obszar (sidecary 0.7.x i 0.8.0), ale jego
`unit` to godlo kafla z `extra.tile_sheet` (takze `godlo_kafla` sprzed
ADR-031); w segmencie samych arkuszy i kafli (ZTM) sam numer (`0510`) to
arkusz, nie TERYT. Nazwy zarezerwowane (`versions`, `full_sheet`,
`kampanie`, takze jako sama jednostka) i nazwy dluzsze niz 255 bajtow to
`ValidationError`. Hierarchie licza
te same funkcje co zapis (`SheetParser`, `path_parts`,
`cuzk_map_path_parts`); skan nie listuje innych katalogow segmentu i nie
zglasza problemow poziomu segmentu; ukryte katalogi wersji
(`.<etykieta>_<sha8>`) pomija tak jak pelny skan. `skip_versions` to znane wywolujacemu
katalogi wersji, wzgledem `output_dir`, z `/` (np.
`nmt/pl_1992_1m_evrf2007/versions/N-34/130/D/d/2/4/2022-05-10_83233_3fa91c2e`):
ich pliki wracaja z `skipped=True` i `sidecar=None` bez czytania sidecarow
(wersje sa niezmienne). Zbior katalogow: pliki z listingu katalogu wersji,
brak sidecara w listingu nadal daje `missing_sidecar`. Mapowanie `katalog ->
nazwy plikow danych`: katalog obecny w listingu rodzica nie jest listowany,
wpisy (te same co z listingu, w kolejnosci nazw, filtrowane przez `units`)
powstaja z podanych nazw - wywolujacy reczy za zawartosc katalogu; plik
usuniety z niego albo dopisany pozniej (Kartograf dopisuje plik do
istniejacego `<etykieta>_<sha8>` przy tej samej etykiecie i tym samym
`sha8` innego pliku slotu) nie jest widoczny do skanu bez mapowania.
Wywolujacy mapuje wiec tylko katalogi, ktorych wszystkie pliki byly przy
ostatnim odczycie poprawnymi wersjami, i okresowo skanuje bez mapowania.
Klucze mapowania nie sa sprawdzane (klucz spoza skanu niczego nie
dopasowuje); nazwy sprawdza skan, gdy dojdzie do katalogu (nazwa ze
sciezka, ukryta albo sidecara to `ValidationError` z iteratora).
Bledne argumenty to `ValidationError` od razu przy wywolaniu (zadna
sciezka nie wychodzi poza magazyn; segment bedacy
dowiazaniem symbolicznym jest odrzucany, a takie katalogi w drzewie nie sa
przechodzone). Blad I/O w trakcie (np. odlaczony udzial) to `OSError` -
wywolujacy zachowuje stary indeks; plik lub katalog, ktory zniknal w
trakcie skanu, nie jest bledem. Niespojne lub nieczytelne metadane daja
problem wpisu, bez wypierania pozostalych wersji slotu. Wersja jest wazna
wg tej samej reguly co `download.versions.read_version` (`sha256`
zaczyna sie od `<sha8>` katalogu, `extra.version` ma `label`
i `label_source`).

`list_partitions(output_dir, segment, *, target=32)` dzieli jeden segment
na rozlaczne czesci do rownoleglych wywolan `iter_store(..., segment=...,
partition=...)`; suma czesci to dokladnie `iter_store(..., segment=...)` -
te same wpisy, zaden dwa razy (test wlasnosci na losowych magazynach).
Klucze: `"."` (zawsze pierwszy) - poziom segmentu: `unknown_segment`,
`legacy_campaigns`, `stale_incoming` i pliki bezposrednio w katalogu
segmentu i w `full_sheet/` (hierarchia `""`); `"<katalog>[/<katalog>...]"`
- slot tego katalogu hierarchii i wszystkie sloty pod nim, jednoczesnie
w sciezce standardowej, `full_sheet/` i `versions/`; `"<katalog>/."` -
tylko wlasny slot katalogu (jego pliki i wersje), gdy jego podkatalogi sa
osobnymi czesciami. Podzial: katalogi pierwszego poziomu (suma trzech
drzew) dzielone poziomami na podkatalogi, dopoki czesci jest mniej niz
`target` i jest co dzielic; katalog bez podkatalogow zostaje cala czescia.
Magazyn testowy Archiwisty (50 tys. slotow): `nmt/pl_1992_1m_evrf2007` -
75 czesci (`M-33/<7>`, `M-34/<66>`, `bbox`), `laz/pl_1992_evrf2007` - 77,
`orto/cz_sjtsk` - 715 (katalogi pierwszego poziomu), segmenty plaskie
(`teryt`, `bbox`) - 2. Klucz sprawdza `iter_store` (skladowe bez `.`
na poczatku, bez separatora i dysku), a sciezke czesci - `lstat` kazdej
skladowej (dowiazanie symboliczne nie jest przechodzone). Segment
nieistniejacy daje `[]`. Katalog dopisany po podziale trafia do kolejnego
podzialu (jak katalog dopisany za miejscem pelnego skanu).

Koszt na wpis (skan nigdy nie wola `link_target`):

| Element | Operacje na dysku/udziale |
|---|---|
| segmenty (`list_segments`) | 1 listing `output_dir` + 1 listing na katalog produktu |
| katalog (hierarchia, `full_sheet/`, `versions/`, katalog wersji) | 1 listing (`scandir`; typ wpisu z listingu - bez `stat` pliku na ext4/XFS/NTFS/SMB) |
| `link`, `full_sheet` | 1 odczyt sidecara (open, read, close); bez `stat`, plik danych nieotwierany |
| `version` | 1 odczyt sidecara; wersja z `skip_versions`: 0 odczytow, tylko listing jej katalogu |
| `missing_sidecar` | 0 (brak `<plik>.meta.json` w listingu) |
| `invalid_sidecar` | 1 odczyt |
| `unknown_segment`, `legacy_campaigns` | 0 (z listingu segmentu) |
| `stale_incoming` | listing `versions/.incoming` (tylko gdy jest w listingu) + `lstat` drzewa katalogow roboczych |
| `iter_store(segment=...)` | `stat` `output_dir` + `lstat` katalogu produktu i segmentu |
| `list_partitions` | jak `iter_store(segment=...)` + listing segmentu, `full_sheet/` i `versions/` + najwyzej 3 listingi (po jednym w kazdym drzewie) na katalog sprawdzany przy podziale (na udziale SMB ok. 2-5 ms na listing; `nmt/pl_1992_1m_evrf2007`: 11 listingow) |
| `partition` | jak `iter_store(segment=...)` + `lstat` skladowych klucza w kazdym z trzech drzew + listingi wylacznie poddrzewa czesci; `"."`: listing segmentu, `full_sheet/` i `versions/` |
| `skip_versions` - mapowanie | znany katalog wersji: 0 listingow i 0 odczytow (bez mapowania: 1 listing) |
| `units` | na jednostke: `lstat` skladowych sciezki slotu (straz dowiazan symbolicznych, wynik wspolny dla jednostek wywolania) dla dowiazania, `full_sheet/` i `versions/` + listing tych katalogow i katalogow wersji; slot plaski (`teryt/`, `bbox/`, `country/`, `ku/`, strefa mesh) jest wspolny wielu jednostkom - jego katalog wersji i kazdy katalog wersji w nim listowany raz na wywolanie (katalog z mapowania `skip_versions` - wcale) |

Watki: dowolne wywolania `iter_store` moga isc rownolegle w osobnych
watkach - rozne segmenty, czesci `list_partitions` jednego segmentu (tak
dzieli prace Archiwista: najwiekszy segment nie czeka na jeden watek)
albo czesci `units` jednego segmentu (jednostki wspolne dla dwoch czesci
daja tylko powtorzone wpisy). Skan tylko czyta i nie ma wspolnego stanu
poza niezmiennym rejestrem i `functools.lru_cache`; jeden iterator nalezy
do jednego watku, a jedno mapowanie `skip_versions` moze sluzyc wielu
wywolaniom naraz (skan go nie kopiuje ani nie zmienia). To samo dotyczy
`read_sidecar`, `describe_segment`, `file_footprint` i `link_target`;
`file_footprint` dzieli miedzy watkami tylko `cache` wywolujacego (jeden
zwykly `dict` moze sluzyc wszystkim watkom - w najgorszym razie dwa watki
odpytaja indeks o te sama jednostke). `pinned_transform` takze mozna wolac
z wielu watkow naraz (nizej). Tej gwarancji pilnuje test rownoleglego
uzycia w `tests/unit/test_store_geometry.py`.

Koszt CPU (magazyn testowy 50 tys. slotow, SSD, jeden watek, 131 111
wpisow): skan przyrostowy (`skip_versions` = wszystkie wersje) 6,3 s,
z mapowaniem 5,2 s, pelny 10,1 s (przed optymalizacja 12,4 s i 20,3 s).
Petla skanu dziala na napisach (sciezki `Path` tylko w wynikowych
`StoreEntry`), wersje dowiazania sprawdza ta sama regula co
`link_target` bez `pathlib`, nazwy krotkie odrzuca bez wyrazenia
regularnego, a typowanie sidecara liczy pola wyliczone leniwie.

`read_sidecar(path)` przyjmuje plik danych albo sidecar i nie otwiera pliku
danych: waliduje schemat (`InvalidSidecarError`: brak pliku, zly JSON, inny
schemat; sidecar bez pola `schema` jest przyjmowany tylko w ksztalcie, jaki
zapisuje `emit_sidecar` dla providera bez `descriptor_key` - obiekt z
`sha256` i `extra`, tak jak akceptuje go `download.versions.read_version`); stare brakujace pola zostaja puste, klucze sprzed ADR-031 i klucze
`dataset` z 0.8.0-dev (ADR-044 D7) sa rozpoznawane przez jawne mapowanie
w czytniku, bez zmiany `raw`. `data_date`/`data_year` pochodza z kampanii,
rekordu skorowidza, kafla LAZ albo wydania (data `updated` feedu ATOM
ortofoto CZ to publikacja, nie rok danych) - nigdy z `downloaded_at` ani
z etykiety `downloaded`. `describe_segment` odwraca reguly zapisu
(`resolve_subdir`, `content_segment`, warianty i wycinki ortofotomapy, HSG);
kazdy segment, ktory zapisuja tory biezacego rejestru, jest rozpoznany
(test `test_every_segment_the_writers_produce_is_known_with_its_source`),
segmenty z 0.8.0-dev (`orto/pl_1992_true`, `cadastre/cz_km_*`) sa
`known=False`.

`file_footprint(entry, *, network=False, cache=None)` wybiera pierwsze
WIARYGODNE zrodlo: bbox zadania (z `bbox_crs`; tylko dla pliku, ktory JEST
tym obszarem - kafel LAZ z `extra.tile_sheet` ma w `request.bbox` obszar,
z ktorego go wybrano, wiec jego obrys to naglowek LAS), obliczalne godlo
PL-1992/PL-2000/TM33 (PL-1992: WGS84 = dokladny prostokat godla), obrys
z naglowka GeoTIFF/ASC, JPG/JGW (plik georeferencji tej samej wersji),
GPKG (SQLite `immutable=1`, bez plikow `-wal`/`-shm`), LAS/LAZ, obrys
jednostki TERYT (PRG), KU (RUIAN) albo arkusza SM5 (indeks CUZK); nie udaje
obrysu kraju. Obrys jednostki z `cache` (`(rodzaj, kod) -> BBox`, pamiec
wywolujacego) jest uzywany takze bez sieci; zapytanie do indeksu tylko przy
`network=True`. Wpis bez `sidecar` (np. `skipped`) najpierw czyta sidecar.
Arkusz SM5 albo jednostka nieznane indeksowi nie maja obrysu (`None`, nie
blad). Zrodlo, ktorego obwiedni nie da sie bezpiecznie przeliczyc na WGS84
(`TransformError`: brak operacji w polityce albo obwiednia poza obszarem
operacji), jest pomijane i decyduje nastepne (pierwsze WIARYGODNE zrodlo);
bez zadnego wynik to `None`. `OGC:CRS84` (PRNG, granice specjalne PRG) i
EPSG:4326 to ta sama dlugosc/szerokosc: obwiednia to te same liczby bez
operacji. Wyjatki: `DownloadError` (indeks niedostepny) i `ParseError`
(cecha KU bez geometrii) - tylko przy `network=True`. Zapytanie PRG
przedstawia sie jak reszta zapytan GUGiK (`make_gugik_session`).

`StoreEntry` i `Sidecar` sa niehashowalne (pola slownikowe; `__hash__ =
None`): kluczem jest `StoreEntry.path` albo `(kind, path)`.
Naglowek rastra GDAL czyta bez listowania katalogu
(`GDAL_DISABLE_READDIR_ON_OPEN=TRUE`). Obwiednie liczy densyfikowanymi
krawedziami (`transform_bbox`) przez `pinned_transform`, nigdy przez
domyslny `Transformer.from_crs`; brak bezpiecznej operacji to
`TransformUnavailableError` z `pinned_transform` (dla pary rownej z
dokladnoscia do kolejnosci osi CRS geograficznego operacja jest dokladna).

`link_target(path)` sprawdza, ze `extra.link_target` wskazuje wersje
slotu tego dowiazania (ta sama regula co `version_path` skanu), a nastepnie
potwierdza ja istniejacym `download.links.linked_version`: ten sam plik wg
i-wezla albo - na udziale bez stabilnych i-wezlow (SMB bez `serverino`) -
trescia (ten sam rozmiar, SHA-256 dowiazania = SHA-256 sidecara wersji,
jeden pelny odczyt pliku przy kazdym wywolaniu; liczba dowiazan nie jest
sprawdzana, bo klient cifs zglasza po odczycie `st_nlink` = 1 i kolejne
wywolania zwracalyby na zmiane wersje i `None`). Plik o tresci wersji
liczy sie jako ta wersja takze wtedy, gdy jest niezalezna kopia (pobranie
zamienia ja w hardlink, regula 6 w 3.3). Zwraca sciezke w tej
samej postaci co `version_path`. Odczyt wszystkich celow przy pelnym skanie
moglby kosztowac wiele gigabajtow, dlatego skan przypisuje wersje ze
sciezki sidecara, a `link_target` wola sie na zadanie.
`pinned_transform(src_crs, dst_crs)` buduje `PinnedTransform` polityka
obwiedni (dokladnosc <= 1 m, bez ballpark i bez siatek sieciowych, krok
datum CZ dla S-JTSK); operacje z `TransformerGroup` pyproj nie sa
bezpieczne watkowo, wiec obiekt jest buforowany per watek, a budowe
(przelacza globalna flage sieci PROJ) wykonuje jeden watek naraz.

### 3.3.2 Plan realizacji odczytu v0.8.0 (wykonany 2026-10-18)

1. Ustalic typy i format problemow (ADR-045), uzyc wzorcow deskryptorow
   i parserow hierarchii, przejsc drzewa generatorem; osobno scenariusz
   bez segmentu i wybór `units` bez skanu calej galezi.
2. Znormalizowac sidecary starych i aktualnych wydan bez zapisu; polaczyc
   linki z istniejaca weryfikacja SMB i odwrocic warianty segmentow.
3. Wyznaczyc obrys wg priorytetu, naglowki czytac tylko dla brakujacych
   bboxow/godel, podlaczyc przypieta transformacje i opcjonalne indeksy
   jednostek.
4. Dodac testy offline na sztucznym magazynie, API `__all__`, dokumentacje,
   CHANGELOG w sekcji 0.8.0; uruchomic brame offline pytest/ruff/mypy.
5. Zaktualizowac PROGRESS, wykonac logiczne commity na galezi
   `feat/archiwista-store-api`; merge do `develop` dopiero po zgodzie
   uzytkownika. Bez pobran danych ani zmian w CLI.

### 3.4 `extra.parent_request`

W trybie `--bbox`/`--geometry` sidecary zadania dostaja `extra.parent_request`
— od 2026-10-07 takze kafle LAZ (`download_laz_area(parent_request=)`,
review-2 N15), od planu B takze pliki LAZ CZ (`download_cz_laz(parent_request=)`);
`countries` to kraje zadania, np. `["PL"]` dla `--country pl`, `["CZ", "PL"]`
pod `auto` z obszarem w obu prostokatach:

```json
{"bbox": [min_x, min_y, max_x, max_y], "bbox_crs": "EPSG:2180", "countries": ["CZ", "PL"]}
```

Niesie **oryginalne** zadanie uzytkownika — przed przycieciem per kraj — jego
uklad i kraje faktycznie odpytane w tym wywolaniu (probowane, nie pobrane).
W trybie `--geometry` "zadanie" to obwiednia geometrii: dla pliku w ukladzie
czeskim (EPSG:5514/3045) w ukladzie PLIKU (od 2026-09-28), dla pozostalych
w EPSG:2180; jawne `--country cz` rastra (wycinek) zapisuje obwiednie
w ukladzie zadania CZ (`--horizontal-crs`). Klucz buduje `download/area.py::parent_request_for`,
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

`src/kartograf/project/manifest.py` scisle sprawdza strukture i typy przy
kazdym odczycie (w tym nazwy i opcje komend, sumy i sciezki; BOM UTF-8
edytora jest dopuszczony, zapis zawsze bez BOM). Zapisuje
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

### 3.6 Dokumenty JSON `kartograf-*/1`

Wynik komendy to dokument: `@dataclass(frozen=True)` z mixinem `Document`
(`src/kartograf/serialization.py`), ktory daje `to_dict()` i `to_json()`. `schema`
(`kartograf-<rodzaj>/<n>`, stala klasy `SCHEMA`, wlasciwosc `schema`) jest zawsze
pierwszym kluczem, dalej klucze `JSON_KEYS` w stalej kolejnosci (domyslnie pola
dataclass; klucz bez pola i bez wlasciwosci bierze `JSON_FILL`). `to_json()` =
`json.dumps(to_dict(), ensure_ascii=False, indent=2, allow_nan=False)` i `\n` na
koncu (`indent=None`: postac zwarta serwera MCP, bez nowej linii). CLI `--json` drukuje
`to_json()` w kopercie `kartograf-result/1` (`cli/_json.py::emit_result`, 9.1 USAGE), serwer MCP zwraca `to_dict()` i
`to_json(indent=None)`; zaden inny modul nie zamienia wynikow na JSON (Z8).

Koder (`encode`, sprawdzane w tej kolejnosci): `Enum` -> wartosc; `float` skonczony
(`NaN`/`Infinity` to `ValueError`); typ z hakiem `__json__(ctx)` (`BBox` ->
`{"bbox": [...], "crs"}`, wpisy projektu); `Path` -> `Path.absolute().as_posix()` (bez
dotykania systemu plikow); `Decimal` -> napis; `datetime` -> ISO 8601 UTC do sekund;
dataclass -> obiekt z polami w kolejnosci deklaracji (`metadata={"json": False}` i pary
`ctx.omit` pomijane); `Mapping` -> obiekt; `tuple`/`list` -> tablica; `set` -> posortowana
tablica; inny typ to `TypeError` (nigdy `str(obj)`). `EncodeContext` niesie `store`
(katalog magazynu, do ktorego sciezki wersji pinow projektu sa wzgledne) i `omit` (pary
`(klasa, pole)`: `StoreEntries` pomija `Sidecar.raw`). Rejestr `SCHEMAS`
(`__init_subclass__`) zbiera klasy per schemat; test sprawdza wzorzec nazwy
(`^kartograf-[a-z][a-z0-9-]*/[1-9][0-9]*$`), ten sam zestaw i kolejnosc kluczy klas jednego
schematu oraz to, ze kazdy `result_schema` katalogu jest w rejestrze.

| Schemat | Typ biblioteki | Modul | Klucze po `schema` |
|---|---|---|---|
| `kartograf-download/1` | `DataReport`, `CollectionReport`, `LandCoverReport`, `SoilReport`, `HsgReport` | `download.data`, `download.collections`, `landcover.manager`, `hydrology.hsg` | `files, raw, inputs, failed, stale, superseded, summary, notices, ok` |
| `kartograf-plan/1` | `UpdatePlan` | `download.plan` | `store, checked_at, kartograf_version, items, notices, ok` |
| `kartograf-result/1` | `CommandResult` | `envelope` | `tool, version, command, check, status, result, items, notices` |
| `kartograf-availability/1` | `AvailabilityReport` | `download.availability` | `request, checked_at, areas, combinations, failed, notices, ok` |
| `kartograf-sheet/1` | `SheetInfo` | `sheet_info` | `sheet, system, country, sheet_system, scale, components, zone, crs, bounds, commands, hierarchy, children, descendants` |
| `kartograf-sheets/1` | `SheetList` | `sheet_info` | `request, sheets, count` |
| `kartograf-sources/1` | `SourceList` | `source_info` | `group, products, sources` |
| `kartograf-layers/1` | `LayerList` | `source_info` | `group, product, source, layers, classes, years, properties, depths, statistics` |
| `kartograf-project-state/1` | `Project` | `project.model` | `directory, output_dir, tasks` |
| `kartograf-project-report/1` | `ProjectReport` | `project.model` | `project, tasks, notices, ok` |
| `kartograf-project-check/1` | `ProjectCheck` | `project.model` | `project, files, not_downloaded, notices, ok` |
| `kartograf-cache/1` | `CacheInfo` | `cache_info` | `action, path, exists, size_bytes, entries, cleared, removed_unreadable` |
| `kartograf-config/1` | `Config` | `config` | `tool, version, config_file, keys, credentials, store` |
| `kartograf-catalog/1` | `Catalog` | `catalog.model` | `view, kartograf_version, language, groups, commands, exit_codes, errors, schemas` |
| `kartograf-store-overview/1` | `StoreOverview` | `store_documents` | `output_dir, segments` |
| `kartograf-store-entries/1` | `StoreEntries` | `store_documents` | `output_dir, segment, units, limit, truncated, entries` |
| `kartograf-store-sidecar/1` | `StoreSidecar` | `store_documents` | `path, sidecar` |
| `kartograf-error/1` | `ErrorReport` | `error_report` | `code, title, message, hint, details, exit_code, command` |

Zasady dokumentow (zrodlo: `docs/superpowers/specs/2026-10-18-agent-interface-design.md`,
sekcja 5; uzycie: USAGE 9.1):

- jeden schemat `kartograf-download/1` dla piecu typow wyniku komend danych ze stalym
  zestawem kluczy (`raw`, `inputs`, `superseded`, `summary` puste, gdy klasa ich nie ma:
  `JSON_FILL`), wiec konsument nie rozrozna typu po kluczach;
- `AvailabilityReport` i `UpdatePlan` nie maja pola `schema` (stala `SCHEMA`
  i wlasciwosc `schema`): nie buduje sie ich z `schema=`, a nieznany schemat odrzuca
  `UpdatePlan.from_dict`; plany zapisane przez 0.8.0-dev nadal sie wczytuja;
- sciezki w dokumentach sa bezwzgledne (wyjatki: `request.geometry` raportu dostepnosci
  i `tasks[].options` projektu w postaci manifestu); `Project`, `ProjectReport` i
  `ProjectCheck` ustawiaja `ctx.store`, wiec sciezki pinow (`PinnedFile`, `FileCheck`)
  sa bezwzgledne;
- klucz jest zawsze obecny (brak wartosci `null`, brak elementow `[]`), listy nie sa
  ucinane po cichu (`kartograf-store-entries/1` niesie `limit` i `truncated`);
- `ok` maja dokumenty wyniku (`-download/1`, `-plan/1`, `-availability/1`,
  `-project-report/1`, `-project-check/1`): `envelope.py` czyta je (`_READERS`, po typie) i
  daje status koperty `ok`, `partial` albo `failed` (kod wyjscia CLI 0, 10, 11);
  `ok: false` jest wynikiem, nie bledem (blad to `kartograf-error/1`, ostatnia linia stderr);
- w obrebie `/1` tylko zmiany addytywne (nowe klucze, nowe wartosci wyliczen); usuniecie
  klucza albo zmiana typu to `/2`. Nowy dokument = klasa z `Document` w module wyniku,
  wpis w tabeli wyzej i wiersz w `tests/contract/test_json_contract.py` (dokladna lista kluczy w
  kolejnosci; zmiana klucza to blad testu).

Schematy plikow - sidecar `kartograf-meta/1` (3.2) i manifest `kartograf-project/1` (3.5) -
nie sa dokumentami wyniku i nie wchodza do `SCHEMAS`; dokument projektu to
`kartograf-project-state/1`.

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
kraj, uklad i rozdzielczosc per kraj, model LAZ CZ, system, skala, lata,
opcje LAZ, ortofoto CZ i wycinek ortofotomapy; `ValidationError` z tekstem
jak w `--help`), rozstrzyga kraj (godlo:
z kodu; obszar: `--country`, `auto` z przycieciem, sekcja 4.6), wybiera tor
(arkusze PL 4.1/4.2, wycinek PL - NMT/NMPT i ortofotomapa - 4.3, CZ 4.4/4.5
z ortofoto CZ w 4.4, LAZ PL i CZ 4.7), buduje
`parent_request` (`download/area.py`) i zbiera wynik
`DataReport(files, failed, stale, superseded, notices, ok)`: `files` =
`UnitFile(unit, country, file: VersionedFile)` (`unit` = godlo, nazwa
pliku LAZ albo wspolrzedne siatki wycinka `<coords>`, jak jednostki
obszaru kolekcji; linia projektu `zadanie: jednostka (plik)`), `failed` =
`UnitFailure(unit, country, error, kind)`, `ok` = regula kodu wyjscia
(czesciowy sukces `auto` = `True`). Komunikaty o danych sa `Notice`
(`src/kartograf/notices.py`; lista kodow w docstringu `download/data.py`)
przekazywane przez `on_notice` w chwili powstania i zwracane w `notices`;
CLI wypisuje je jako `Info:`/`Warning:` na stderr (takze z `-q`), naglowek
listy arkuszy (`SHEET_LIST`) na stdout. `check_data` (te same argumenty
bez `update`, `plan`, `workers`, `on_progress`) zwraca jeden plan
`kartograf-plan/1` (pod `auto` z pozycjami PL i CZ). Tory sa publiczne
(`download_pl_cutout`, `download_image_cutout`, `download_cz_cutout`,
`download_cz_sheet`, `download_cz_orto_sheet`, `download_laz_area`,
`download_cz_laz`, `DownloadManager`) z parami `check_*`; ich kroki
wewnetrzne nie.

**Kolekcje (ADR-042, od 0.8.0).** `kartograf boundaries download`,
`cadastre download`, `models3d download`, `hydro download`, `names
download`, `maps download` i `geodesy download` (grupy ADR-039, ADR-042
D9) to `download_collection(...)`/`check_collection(...)`
(`download/collections.py`) - jeden orkiestrator dla paczek jednostek,
obiektow obszaru i plikow krajowych (takze z feedu ATOM), sterowany
parametrami kanalu deskryptora (sekcja 4.10); ZABAGED (`landcover
download --product zabaged`) idzie przez te same silniki z publicznym
`download_landcover` i wewnetrznym `LandCoverManager` (sekcja 4.8).

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
`https` albo z godlem spoza `SheetParser` nie jest rekordem. Ortofotomapa
zostaje na WMS (`SkorowidzLayersMixin`:
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
`<cache_dir>/kartograf/metadata.db` przez `cache/defaults.py::open_cache`, `False` =
bez cache); `update="force"` (CLI `--force`) i kazde sprawdzenie
(`check_*`, `check_data`, CLI `--check-updates` - zawsze pyta zrodlo)
otwieraja go w trybie `MetadataCache(refresh=True)` — odczyt pominiety,
swiezy rekord zapisany (E14); `--upgrade` tak samo jak `--check-updates`
(`fetch.refreshes_cache`: `upgrade` i `force`), domyslne pobieranie czyta
cache w TTL. `kartograf cache stats` pokazuje `Wpisy rekordow`. Umowa:
`force`/`upgrade` odswiezaja tylko cache otwierany przez funkcje (parametr
`cache`, provider tworzony przez nia albo po nazwie); provider przekazany
jako instancja (`DownloadManager`, `LandCoverManager`,
`download_laz_area(provider=)`) zachowuje wlasny cache, ktorego `force`
nie omija — pelne odswiezenie:
provider z `MetadataCache(..., refresh=True)` (USAGE "Cache metadanych
w bibliotece").
Baza jest otwierana leniwie: plik `metadata.db` (i jego katalog
`<cache_dir>/kartograf/`) powstaje dopiero przy pierwszym zapisie (`set_*`); konstrukcja, odczyty (`get_*` = chybienie),
`stats()` (zera, `db_exists: false`), `clear()` i `close()` na braku pliku
go nie tworza, wiec `kartograf cache path|stats|clear` bez bazy
niczego nie zapisuja (cache nigdy nie lezy w biezacym katalogu: `cache_dir`
pochodzi z ustawien uzytkownika, `kartograf/config.py`, ADR-050). Cache jest tylko przyspieszeniem: kazdy
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
**odrzucane** (`ValidationError`, kod 2) — godlo PL dostarcza arkusz natywny 1:1.

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
(lista lat do 20 arkuszy, podpowiedz zmienia granice, ktora blokuje: przy
przedziale `--min-year` w dol albo `--max-year` w gore do najblizszego
roku, ktory ma kazdy konfliktowy arkusz; `--year` daje flagi jednostronne),
zero pobran dla CALEGO zadania.
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
`cz_laz`/`pl_cutout`/`cz_cutout`, `unit` = jednostka zadania; `UpdatePlan.merge`,
`select_planned`, `new_plan`); pozostale tory dostaja `plan=` w swoich
`run_*`.

**Stany danych w sprawdzeniu (0.8.0, E2E P2-3).** `check_sheets(sheets,
on_no_coverage=)` odtwarza wynik pobrania, a nie tylko pozycje: arkusz bez
danych (`NoCoverageError`) nie jest pozycja planu ani niepowodzeniem
sprawdzenia — `on_no_coverage(brakujace, liczba_arkuszy)` dostaje te arkusze
(`download/data.py` zamienia je w `NO_COVERAGE_SOME` i `NO_COVERAGE_HINT`,
tekstem pobrania, `_no_coverage_warning`/`_coverage_hints`), a gdy zaden
arkusz nie ma danych, zglasza `NoCoverageError` (pojedynczy arkusz: jego
wlasny; lista: `no_coverage_text`). Arkusze z danymi tylko poza zakresem lat to
JEDEN `YearRangeError` (`year_range_error`, jak `_checked_range`), a
`check_failed` zostaje dla awarii skorowidza. `check_data` rzuca wtedy blad
pierwszej porazki (`_Run.causes`): klasa wyjatku = kod bledu (`no_coverage`,
`year_out_of_range`), a w raporcie pobrania ta sama nazwa to `UnitFailure.kind`
(`_failure_kind`; `download` i `country` dla pozostalych).

**Tory bez kampanii (plan 2/3; LAZ CZ: plan B).** LAZ (`download/laz.py`),
LAZ CZ (`download/cz_laz.py`), arkusze CZ
(`download/cz_sheets.py`), wycinki CZ (`download/cz_cutout.py`) i PL
(`download/cutout.py`) oraz tor bez kampanii `DownloadManager` korzystaja
z jednej polityki `download/fetch.py`: `fetch_version(slot, update,
signal=, fetch=, version=, write_sidecar=, probe=)` — lokalna wersja albo
pobranie do `.incoming/`, `commit_version(signal=)`, hardlink — oraz
`inspect_version` (pozycja planu bez pobierania; `check_laz_area`,
`check_cz_laz`, `check_cz_sheet`, `check_cz_cutout`, `check_pl_cutout`).
Sygnal wg kanalu (`AccessChannel.update_signal`, `channel_signal`): LAZ
`index` (kafel z lokalna wersja = `local`, nowszy nalot to nowe pliki,
D26), pliki openzu — arkusz SM5, natywny kafel TM33 (plan B) i LAZ CZ —
`http` (`probe` = `file_signal` providera, `HEAD` pliku `openzu`).
Tryb domyslny nie pyta zrodla o lokalna wersje (errata 3 ADR-036):
`http` + `probe` i `metadata` + `edition` daja lokalna wersje
`unverified="unchecked"` bez zapytania (linia `(bez sprawdzania;
--check-updates)`); `upgrade` robi `HEAD` (rowne `ETag` = lokalna, rozne =
pobranie, nieudane `HEAD` = blad), `--check-updates` = `inspect_version`.
Etykieta rekordu indeksu (`index` + `edition`) jest znana z wyboru plikow,
wiec porownanie zostaje w kazdym trybie. Kafel TM33 z ImageServer i
wycinki `none` (lokalna, `unverified="none"`). Wynik: `VersionedFile(path, status, label, sha256,
version_path, newer, unverified)`; `LazDownloadResult.files`,
`CzLazResult.files`, `CzSheetResult`/`CzCutoutResult`/`PlCutoutResult.file`
(`None` tylko z `plan=`, gdy plan nie wykonuje pliku i nie ma wersji
lokalnej) i `stale`. Pola wyniku lokalnej wersji (`all_nodata`, `masked_pixels`,
`zero_pixels`) pochodza z sidecara wersji, bez odczytu rastra.

CLI drukuje jedna linie na plik: `<godlo>: nowa wersja <etykieta>_<sha8>`,
`nowa etykieta <etykieta> (plik identyczny z <etykieta>)` (najnowsza
istniejaca wersja o tym samym sha256, `VersionedFile.same_as`),
`bez zmian <etykieta>`,
`lokalna wersja <etykieta>`, a po liscie (bez `-q`) `Nowe: N, nowa
etykieta: N, bez zmian: N, lokalne: N, bledy: N (<dir>)` (arkusze PL
i kafle LAZ; jednostka LAZ PL = nazwa pliku, LAZ CZ = godlo, wycinka = sciezka pod
`--output`). Plik bez taniego sygnalu: domyslnie dopisek `(bez
sprawdzania; --check-updates)`, przy `--upgrade` `Info:` o `--force`;
nieudane sprawdzenie sygnalu: `Warning:`. Raport `--check-updates` to
jedna linia na pozycje (`aktualne`, `nowsza: ...`, `do pobrania`, `nie da
sie sprawdzic bez pobrania`, `nie udalo sie sprawdzic: ...`); land cover,
gleby i HSG oznaczaja pozycje sciezka pod `--output` jak linia statusu
(GPKG i surowy ZIP `--keep-raw` tego samego TERYT = dwie rozne linie), kod 1 przy
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
`Warning: <godlo>: skorowidz GUGiK niedostepny - uzyto lokalnej wersji bez
sprawdzenia nowszej (<blad>)` (pojedyncze godlo) albo `Warning: skorowidz
GUGiK niedostepny - dla N arkuszy uzyto lokalnych wersji bez sprawdzenia
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
rowniez `download_landcover`, `download_soil` i `calculate_hsg`; SHP
i jednowarstwowy GPKG nie daja komunikatu.

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
Tak samo `--check-updates`: arkusze bez danych to `NO_COVERAGE_SOME` i kod 0
(zaden arkusz z danymi = `no_coverage`, kod 1), konflikt lat to jeden
`year_out_of_range` dla wszystkich arkuszy (sekcja 4.1).

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

**Obrazy GUGiK planu E1 (ADR-043).** Intensywnosc, true orto i orto
ukosna ida torem arkuszy ortofotomapy (`DownloadManager`, kampanie, wersje,
sygnal `index`): jeden provider `GugikImageProvider`
(`providers/pl/gugik_orto.py`) sparametryzowany `SheetIndexParams`
deskryptora (sekcja 3.1). Obszar rozwija sie do godel serii skorowidza
(`series_scale(sheet_parts)`: true orto `1:5000`, godla 8-czlonowe;
jeden uklad arkuszy = `--sheet-system` mozna pominac). Orto ukosna to
cztery managery - po jednym na kierunek (`data._managers`, provider
z `direction`, `storage_suffix` `_n`/`_e`/`_s`/`_w`); `verify_record_url`
zdejmuje przyrostek kierunku z nazwy pliku (`_N.tif`), a
`DownloadManager._download_planned` zaweza pozycje planu do segmentu
i nazwy pliku managera. Przed `GET` arkusza obrazu idzie `HEAD`; plik
ponad 100 MiB (`LARGE_FILE_BYTES`) dostaje `Notice` `download_size`
z rozmiarem (K9). Wycinek true orto: sekcja 4.3 (`download_image_cutout`,
kanal `WCS` deskryptora, bez tokenu `coverage` w segmencie).

**NMT 100 m (ADR-043 D10).** `--resolution 100m` to wariant rejestru bez
indeksu arkuszy (`pl_file_variant`): obszar (`--bbox`, `--geometry`, rama
`--sheet`) daje wojewodztwa z PRG (`discover_teryts_for_bbox`, dwie
pierwsze cyfry TERYT), a kazde - plik feedu ATOM GUGiK
(`collections.atom_area_request`, tor planu `collection`, slot
`nmt/pl_1992_100m/teryt/<woj>.zip`, sygnal `metadata` z `updated` wpisu
zbioru). Flagi arkuszy, lotow, wycinka i `--vertical-crs` = `ValidationError`
przed siecia.

### 4.3 Bbox / geometria PL z `--cutout` (ADR-035, ADR-038, ADR-042 D14)

CLI `elevation download --bbox`/`--geometry --cutout --horizontal-crs` oraz
biblioteczne `download_data(cutout=True, horizontal_crs=...)` i
`download_pl_cutout()` pobieraja NMT albo NMPT 1 m z WCS GUGiK, nie
mozaikuja arkuszy (ortofotomapa ma wlasny tor wycinka - koniec sekcji).
Tryb jest jawny: `--horizontal-crs` jest wymagane
z `--cutout`, bez `--cutout` to `Error:`, `--cutout` z `--sheet` tez.
Biblioteka: `download_pl_cutout(*, bbox, horizontal_crs,
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
   obiektow. `--sheet-system 2000`, `--cutout` z godlem lub z LAZ
   nadal sa odrzucane przed pobraniem.
2. `download_pl_cutout` pobiera i buduje maske ladu PRG **przed**
   jakimkolwiek zapytaniem WCS: `A00_Granice_panstwa` minus
   `W02_Morze_terytorialne_RP` minus
   `W03_Morskie_wody_wewnetrzne`. `A00` jest pobierana bez BBOX
   (PRG nie przycina jej geometrii); `W02`/`W03` z BBOX obszaru.
   Rasteryzacja bierze srodek piksela (`all_touched=False`), w tym
   nad rzekami granicznymi, zatokami i zalewami. Poza maska nodata
   `-9999`; na ladzie wartosci WCS, **takze 0,0**, pozostaja danymi
   (Zulawy). Maska nie wypelnia zer wewnatrz ladu z arkuszy. Obszar bez
   ani jednego srodka piksela na ladzie (`LandMask.has_land`: morze,
   zagranica) konczy sie `NoCoverageError` przed WCS, bez wersji (CLI:
   `Error:`, kod 1; jak tryb arkuszy).
3. Provider pobiera przez `_download_wcs(bbox_source_2180, work,
   "GTiff")` na 1-metrowej siatce arkuszy
   `GridSpec(1.0, 0.5, 0.5)`, z bboxem wyrownanym NA ZEWNATRZ
   (kawalki ADR-034 i limity per format w 4.2). Dla EPSG:2180
   maskowany wynik trafia atomowo przez `os.replace` do pliku;
   dla EPSG:5514/3045 `warp_to_grid` z przypieta operacja, nodata
   i siatka celu wykonuje lokalna reprojekcje. `PlCutoutResult`
   podaje `masked_pixels`, `zero_pixels` liczone przed warpem oraz
   `all_nodata`. `all_nodata` z `Warning:` (kod 0) zostaje tylko dla WCS
   bez danych na ladzie.
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
   WCS i szacowanym czasem (`WCS_REQUEST_SECONDS` = 25-40 s na zapytanie,
   pomiar 2026-10-16/17) dla > 1 kawalka lub wyniku >= 1 GiB (gdy wycinek
   bedzie pobierany, po masce PRG).

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

**Wycinek ortofotomapy PL (ADR-042 D14, od 0.8.0).** `imagery download
--product orto --country pl --bbox|--geometry --cutout --horizontal-crs
EPSG:2180 --coverage standard|high --resolution 0.1m|0.25m|0.5m|1m` =
`download_data(product="orto", cutout=True, horizontal_crs="EPSG:2180",
coverage=..., resolution=...)` -> `download/orto_cutout.py::
download_image_cutout(*, product, bbox, horizontal_crs, output_dir,
resolution, coverage=None, update, plan, parent_request, cache, on_notice)` ->
`ImageCutoutResult(file, stale, notices)` (ADR-044 D3: jedna para dla
`product="orto"` i `"true-orto"`); `check_image_cutout(...)` z tym
samym wyborem daje plan (tor `pl_cutout`; lokalna wersja =
`unverifiable`). Inaczej niz NMT/NMPT:

1. Walidacja bez sieci (`orto_cutout_error`, `cutout_choice_error`):
   `--coverage` (`standard` - najnowsze dostepne ortofotomapy, `high` -
   ortofotomapy o pikselu 10 cm i mniejszym) i `--resolution` (piksel
   wyniku `0.1m`, `0.25m`, `0.5m`, `1m`; etykiety z
   `WcsCutoutParams.resolutions`) sa wymagane bez wartosci domyslnych,
   `--horizontal-crs` tylko `EPSG:2180` (bez lokalnego przeprobkowania
   obrazu), tylko PL (`--country cz` albo obszar tylko w CZ = blad; pod
   `auto` `--coverage`/`--resolution` zawezaja zadanie do PL), bez
   `--sheet`, roku i kampanii; `--coverage` albo `--resolution` orto bez
   `--cutout` = blad. Tylko kompozycja RGB. Maski ladu PRG nie ma: piksele
   bez obrazu w wycinku z obrazem zostaja 0,0,0 jak z serwera.
2. Siatka: bbox (dowolny obslugiwany uklad, geometria = obwiednia)
   przeliczony do EPSG:2180 i wyrownany NA ZEWNATRZ do wielokrotnosci
   piksela; nazwa pliku niesie te siatke. `GugikOrtoProvider(color="RGB",
   coverage=, resolution=)` bierze endpoint i coverage z kanalu rejestru;
   piksel inny niz 0,1 m = `SCALEFACTOR` (0,1 m / piksel). Kawalki maja
   budzet 4 Mpx pikseli coverage (200 x 200 m terenu niezaleznie od
   piksela wyniku - obszar 1 x 1 km to 25 zapytan) i parzyste rozmiary (nieparzysta
   liczba pikseli 0,25 m to ulamek piksela coverage: zla siatka albo
   HTTP 400); sa pobierane po kolei i skladane bez resamplingu, limit
   odczytu kawalka 300 s (`WCS_CUTOUT_READ_TIMEOUT`; pomiar 2026-10-15:
   4 Mpx Standard 64 s, 2000 x 2000 px przy `SCALEFACTOR=0.4` 176 s).
3. Przed pierwszym zapytaniem: `Notice` `cutout_size` (px, MiB, liczba
   zapytan) dla wiecej niz jednego kawalka albo >= 1 GiB oraz kontrola
   miejsca na dysku (2 x rozmiar wyniku, inaczej `ValidationError`).
   Wynik jest sprawdzany (rozmiar, krok, naroznik NW, 3 pasma uint8,
   EPSG:2180): inna siatka = `DownloadError` bez wersji. Wynik bez
   zadnego piksela obrazu (HTTP 200 z obrazem 0,0,0: true orto poza
   wybranymi miastami, High poza obszarami pikseli 10 cm, Standard poza
   ortofotomapami) konczy sie `NoCoverageError` PRZED zapisem wersji
   (`_no_image_error`, tresc z przyczyna i remedium kanalu, przy High
   `--coverage standard`; usluga nie publikuje zasiegu wycinka, wiec obraz
   jest sprawdzany po pobraniu; staging usuniety; w `download_data`
   porazka `no_coverage` PL, CLI `Error:` kod 1) - jak wycinek NMT/NMPT
   poza ladem.
4. Magazyn: dowiazanie `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif`
   do wersji `versions/bbox/<RRRR-MM-DD>_<sha8>/`, sygnal `none`:
   domyslnie i z `--upgrade` lokalna wersja bez zapytan, `--force` pobiera
   ponownie (ten sam obszar i piksel = te same bajty = `unchanged`).
   Sidecar: sekcja 3.2.
5. Zszyte kawalki NIE sa bit w bit rowne jednemu zapytaniu calego
   obszaru: serwer przeprobkowuje kazde zapytanie w jego zasiegu (pomiar
   2026-10-16: 20 x 20 m przy 0,1 m - 75-93 % pikseli rozne, srednio
   4 DN, max 89; 40 x 40 m przy 0,25 m - 70 %, srednio 4,4 DN, max 120);
   bit w bit sklada sie tylko NMT (ADR-034 errata 1). WCS oddaje
   kompozycje serwera bez wyboru roku; w probkach (Krakow, 2026-10-15/16)
   High i Standard daly nad tym samym obszarem te same bajty.

`GugikOrtoProvider.download_bbox` bez `coverage` zostaje surowym
zapytaniem Standard poza magazynem (jedno zapytanie bez wyrownania).

### 4.4 Godlo CZ (NMT: DMR 5G / DMR 4G, NMPT: DMP OK / DMP 1G) i ortofoto CZ

Raster CZ wybiera `product` (`nmt`|`nmpt`), `resolution` i `vertical_crs`
z wariantow rejestru (sekcja 3.1; plan B, decyzja 2):
`CuzkRasterProvider.route(sheet=None) -> CzRasterRoute(channel,
horizontal_crs, horizontal, vertical)` wybiera kanal, uklad wyniku
i przypiete operacje PRZED siecia (`sheet=None` = wycinek, sekcja 4.5):

| Model (`--product`, `--resolution`) | Arkusz SM5 (`CTES96`) | Kafel TM33 (`760_5518`) |
|---|---|---|
| DMR 4G (`nmt`, `5m`), DMP OK (`nmpt`, `0.5m`) | plik openzu EPSG:5514 (Bpv); EVRF2007: plik + transformacja pionowa | EVRF2007: plik openzu EPSG:3045 natywnie; Bpv: `exportImage` + lokalny warp |
| DMR 5G (`nmt`, `2m`), DMP 1G (`nmpt`, `2m`) | brak (`ValidationError` przed siecia: SM5 tylko 5m / 0.5m) | `exportImage` + lokalny warp (EVRF2007: + transformacja pionowa) |

Kafel TM33 bez pliku wariantu rozwija `ParserTM33` do bboxa w EPSG:3045; do serwera
CUZK idzie zadanie `exportImage` **wylacznie w ukladzie natywnym EPSG:5514**
(plus zapas 4 px), a na siatke kafla przenosi je lokalny warp przypieta
operacja (ADR-024 — serwerowa reprojekcja gubila datum shift). Taki kafel
nie jest wiec produktem 1:1: to warp z EPSG:5514 na siatke EPSG:3045,
przypieta czeska operacja S-JTSK -> ETRS89 (EPSG:1622/1623,
nominalnie 1,0 m; ADR-024 errata 2).
Odpowiedzi `exportImage` sa zawsze pochodna serwera (bilinear; siatka uslugi
DMR 5G ma faze (0,4; 1,88) m mod 2), wiec 1:1 daja tylko pliki openzu:
arkusz SM5 DMR 4G/DMP OK (EPSG:5514) i od planu B kafel TM33 DMR 4G/DMP OK
w EVRF2007 (plik ETRS89, EPSG:3045), bez warpa — plik to TIFF bez CRS
(georeferencja w `.tfw`), wiec po pobraniu nadpisywane sa tylko metadane
CRS (CRS kanalu). `--vertical-crs EVRF2007` dokleja przypieta
transformacje pionowa Bpv -> EPSG:5621 (przesuniecie w miejscu) tam, gdzie
kanal podaje Bpv (arkusz SM5, ImageServer); plik TM33 ma EVRF2007 natywnie
(bez `_apply_vertical_shift`, sidecar bez operacji pionowej). `KRON86` dla
CZ jest nieosiagalny (brak publicznych siatek). Arkusz SM5 moze pominac
`resolution` (produkt ma jedna etykiete z plikami SM5: NMT 5m, NMPT 0.5m);
kafel TM33 jej wymaga. Sidecar pisze biblioteka (`download/cz_sheets.py`,
`download_cz_sheet`) z trasy: uklad wyniku, przypiete operacje,
`capability` (`sheet_files` dla pliku, `bbox_raster` dla `exportImage`)
i `extra.http` pliku.

Kafel TM33 DMR 4G EVRF2007 pobrany przed planem B (warp, wersja bez
`extra.http`) zostaje w trybie domyslnym lokalna wersja
(`unverified="none"`, `Notice` `unverified_local`: niesprawdzona, plik
CUZK przez `--force`); `--force` pobiera plik CUZK jako nowa wersje
i przepina dowiazanie (decyzja 12 planu B).

Wynik: `data/nmt/cz_dmr5g_bpv/302/5550/302_5550.tif` (`horizontal_crs`
EPSG:3045) albo `data/nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif`
(`horizontal_crs` EPSG:5514); NMPT np.
`data/nmpt/cz_dmpok_evrf2007/760/5518/760_5518.tif` (plik ETRS89,
`vertical_crs` EPSG:5621) albo `data/nmpt/cz_dmp1g_bpv/760/5518/760_5518.tif`
(warp z `dmp1g`).

**Godla SM5 z dwiema literami (od 0.8.0).** `CZ_SM5_PATTERN` =
`^[A-Z]{2}(?:[A-Z]{2})?[0-9]{2}$`: 99 arkuszy As (`AS22`...`AS94`; indeks
SM5 ma 16 299 arkuszy) jest rozpoznawanych jako `cz_sm5` (`AS91` ->
`AS/91`), takze dla DMR 4G; wczesniej `detect_system("AS91")` zwracal
fallback `pl1992`, wiec arkusz konczyl sie bledem godla PL.

**Ortofoto CZ (ADR-042 D13, od 0.8.0).** `imagery download --product
orto --country cz` (godlo SM5 - kraj takze z godla - albo obszar) =
`download_data(product="orto", ...)` -> tor `download/cz_orto.py`: godlo
przez `cz_orto_sheet` (kafel TM33 = blad z podpowiedzia SM5), obszar ->
arkusze SM5 z indeksu `KladyMapovychListu` (`cz_orto_area_sheets`; bbox
przeliczony do EPSG:5514 przypieta operacja; `Notice` `sheet_list`),
kazdy arkusz `download_cz_orto_sheet(*, sheet, output_dir, update, plan,
parent_request, cache, on_notice, on_download)` -> `CzOrtoResult(files,
stale, notices)`; `check_cz_orto_sheet` daje cztery pozycje planu toru
`cz_orto` (jednostka = godlo). Wydanie pochodzi z feedu ATOM ORTOFOTO
(silnik `atom_files`, sekcja 4.10): jedno `resolve_atom_file` na arkusz
(wynik i porazka zapamietane dla czterech plikow, `check_failed` raz na
arkusz), etykieta `<rok>_<updated>` (np. `2024_2025-02-06`), sygnal
`metadata`: domyslnie lokalne wersje porownane z wydaniem (nowszy
rocznik = dopisek `dostepna nowsza ... (--upgrade)`), `--upgrade` pobiera
nowy rocznik (stare wersje zostaja w `versions/`), `--force` pobiera
ponownie. Pobranie: jeden ZIP (16-64 MB; limit odczytu 120 s; rozmiar =
`length` feedu i `Content-Length`) do `versions/.incoming/`, czlony
`.jpg`, `.jgw`, `.TM33N.jgw`, `.TM34N.jgw` skopiowane 1:1 (bez konwersji
pikseli) i zapisane w kolejnosci `.jgw`, `.TM33N.jgw`, `.TM34N.jgw`,
`.jpg` jako `orto/cz_sjtsk/<hierarchia SM5>/<godlo><sufiks>` (wersja JPEG
zawsze ma pliki JGW). Tylko aktualny rocznik arkusza (archiwalne
ortofoto CUZK sa platne): flagi roku i kampanii, `--full-sheet`,
`--sheet-system`, `--scale`, `--vertical-crs`, `--format` i `--resolution`
z `--country cz` = blad, `--cutout` z CZ = blad. JGW nie niesie ukladu -
uklad kazdego pliku podaje jego sidecar (JPEG: `extra.world_files`,
sekcja 3.2). Piksel arkusza wynika z JGW (probki 2026-10-16: 0,125 m).

**Warstwice CZ (plan E1, od 0.8.0).** `elevation download --product
contours --format SHP|DGN` -> tor `download/cz_contours.py` (dyspozycja
`data._download_cz_contours`, jak ortofoto CZ): godlo SM5 (kafel TM33 =
blad) albo arkusze SM5 obszaru z plikami CUZK
(`SheetIndex.file_sheets("sm5")`, bbox przeliczony do EPSG:5514 przypieta
operacja). Kazdy arkusz: ZIP openzu z szablonu kanalu deskryptora formatu
(`cz.cuzk.zabaged_contours_<format>`) pobrany 1:1 do
`contours/cz_zabaged_<format>/<hierarchia SM5>/<godlo>.zip`; przed zapisem
wersji czlony ZIP i ich CRC sa sprawdzane (strona HTML albo przeciety ZIP
= `DownloadError`, brak wersji), sidecar: lista czlonow (`extra.members`),
`mapname`/`cz_share` z indeksu, `extra.http`, uklad EPSG:5514, wysokosci
Bpv. Sygnal `http` (`HEAD` przy lokalnej wersji tylko z `--upgrade`), tor planu
`cz_sheet` (jednostka = godlo). `--resolution`, `--cutout`,
`--horizontal-crs`, flagi arkuszy PL i lotow = blad przed siecia
(`options._contours_error`).

### 4.5 Bbox CZ

Jeden wycinek `exportImage` uslugi wariantu (DMR 5G `dmr5g`, DMR 4G `dmr4g`,
DMP OK `dmp_obrazova_korelace`, DMP 1G `dmp1g`); obszar rastra CZ wymaga
`--cutout --horizontal-crs` (ADR-038; bez `--cutout` `ValidationError`
przed siecia; LAZ CZ obszaru to arkusze z indeksu, sekcja 4.7; ortofoto CZ
obszaru to arkusze SM5, sekcja 4.4). Bbox jest
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
CUZK jest bez zmian: piksel to dokladnie krok wariantu (0,5 m DMP OK,
2 m DMR 5G i DMP 1G, 5 m DMR 4G), E/S moze odbiegac
o <= 0,5 px (nazwa pliku i `request.bbox` niosa bbox sprzed snapu).
Wycinek w calosci nodata daje `Warning:` i kod 0, nie pozorna cisze.

Tor bbox CZ jest w bibliotece (`download/cz_cutout.py`):
`download_cz_cutout(*, bbox, output_dir, product, horizontal_crs,
vertical_crs, resolution, update, plan, parent_request, cache, on_notice,
on_download)` buduje providera (`create_cz_raster_provider(product,
resolution, ...)`; trasa `route()` z operacjami przed siecia), normalizuje
bbox, wyznacza slot wersji (`bbox_slot`), pobiera (`fetch_version`, sygnal
`none`), sprawdza nodata i pisze sidecar wersji; `check_cz_cutout(...)`
z ta sama selekcja daje plan. Krok wykonania (`_run_cz_cutout`) jest wewnetrzny. Siatka wyniku startuje od zadanego bboxa
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

Wynik: dowiazanie `data/<nmt|nmpt>/cz_<model>_<vcrs>/bbox/<coords>.tif`
(np. `nmt/cz_dmr5g_bpv`, `nmpt/cz_dmp1g_bpv`) do wersji
w `versions/bbox/<RRRR-MM-DD>_<sha8>/`. Arkusze CZ (TM33, SM5) maja
od 0.8.0 publiczne API `download/cz_sheets.py` (`download_cz_sheet`/
`check_cz_sheet(*, sheet, output_dir, product, vertical_crs,
resolution=None, ...)` -> `CzSheetResult`; ADR-037): ta sama tresc
sidecara co wczesniej w CLI (`mapname`, `cz_share`, `capability`,
`horizontal_crs`); pliki openzu (SM5, od planu B tez kafel TM33
DMR 4G/DMP OK w EVRF2007) z sygnalem `http` (`extra.http`), kafel TM33
z ImageServer `none`.

### 4.6 Dyspozycja per kraj (`--country auto`)

Podzial na kraje jest w bibliotece (`download/countries.py`;
wywoluje go `download_data`, ADR-037): `countries_for_bbox` porownuje bbox
(w WGS84) z `CountryProfile.extent_wgs84`
kazdego kraju z rejestru. Obwiednie sa **prostokatami**, nie wielokatami
granic, wiec obszar w glebi jednego kraju rutynowo trafia takze do drugiego.
Konsekwencje: (1) obszar przecinajacy oba prostokaty pobiera sie z KAZDEGO
kraju — osobne pliki i sidecary, wspolny `parent_request`; dla rastrow
NMT/NMPT wymaga to `--cutout` (obszar rastra CZ jest zawsze wycinkiem,
ADR-038), wiec czesc PL jest wtedy wycinkiem WCS; bez `--cutout`
`ValidationError` z podpowiedzia `--country pl` (arkusze PL). LAZ (plan B)
nie ma wycinka: czesc PL to kafle WFS GUGiK (sekcja 4.7), czesc CZ —
arkusze indeksu CUZK systemu wyznaczonego ukladem wysokosci CZ (Bpv: SM5,
EVRF2007: TM33); wymaga `--model`, bez niego `ValidationError` (`obszar
siega CZ: podaj --model ... albo --country pl`). Ortofotomapa (plan D) bez
`--cutout` daje arkusze PL (`--sheet-system` dla czesci PL) i arkusze SM5
CZ (dotad `auto_narrowed_to_pl`), a kolekcje - plik obszaru na kraj
(sekcja 4.10). Produkt jednego kraju (intensywnosc, true orto, orto ukosna:
PL; warstwice: CZ) zaweza `auto` do tego kraju z `Info:`
`auto_narrowed_to_pl`/`auto_narrowed_to_cz` (jak kolekcje); obszar tylko
w drugim kraju = `ValidationError`; (2) na obszarze
spornym flaga bez odpowiednika czeskiego (`--vertical-crs KRON86`,
rozdzielczosc spoza rejestru CZ, np.
`--resolution 1m` albo `0.5m` dla NMT — NMPT `0.5m` to DMP OK, kazde
`--format` oraz `--coverage` i `--resolution` wycinka ortofotomapy; dla LAZ
takze `--year`, `--min-year`, `--max-year`, `--all-campaigns`
i `--min-density`; `download/area.py::pl_only_flags`
czyta rejestry) ROZSTRZYGA kraj do `pl` z komunikatem `Info:` zamiast
przewracac zadanie; (3) porazka jednego kraju
przy sukcesie drugiego daje kod 0 i `Warning:` (takze w kolekcjach, sekcja
4.10) — kod 1 zostaje dla jawnego `--country` i dla porazki wszystkich krajow.
`Info:`/`Warning:` ida na stderr,
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
`ValidationError` (CLI `Error:`, kod 2) bez sieci. Poza obwiednia CZ przy granicach
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
pobraniem. Model LAZ CZ wybiera `--model` (`model=`, plan B); `--model`
z rastrem albo z zadaniem tylko PL (jawne `--country pl`, godlo PL,
obszar tylko w PL albo zawezony do PL) = `ValidationError`.

Opcje kampanii i flagi roku (ADR-030/032; erraty Q9, N-3) dotycza
tylko arkuszy i kafli LAZ PL; `download_data` sprawdza wszystkie wejscia: zadanie bez PL (godlo CZ pod `cz`/`auto`, jawne
`--country cz`, obszar w calosci CZ pod `auto`) z `--all-campaigns` lub dowolna
flaga roku = `ValidationError` (`CZ (CUZK) nie ma kampanii -
--all-campaigns/--min-year/--max-year/--year dotycza tylko PL`; ortofoto
CZ: `--year dotyczy tylko PL - CUZK publikuje tylko aktualny rocznik
arkusza ortofoto CZ ...`), kod 2 bez sieci (LAZ CZ z `--min-density`:
`--min-density dotyczy tylko LAZ PL`). Obszar rastra NMT/NMPT PL+CZ pod
`auto` wymaga `--cutout`, a wycinek odrzuca te
flagi (4.3) - arkusze PL z kampaniami daje tylko `--country pl` (od
ADR-038; `Notice` `campaign_opts_pl_only` usuniety). Ortofotomapa pod
`auto` stosuje flagi roku i kampanii do arkuszy PL, a czesc CZ bierze
aktualny rocznik arkuszy SM5. Dla rastrow flagi roku nie
naleza do `pl_only_flags` i nie zwezaja `auto` do PL; dla LAZ (plan B)
`--year`/`--min-year`/`--max-year`, `--all-campaigns` i `--min-density`
zawezaja obszar PL+CZ do PL (`Info:`, `AUTO_NARROWED_TO_PL`).

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

### 4.7 LAZ (chmury punktow LIDAR, PL i CZ)

Przeplyw poza `DownloadManager` — jedno zadanie obszarowe daje wiele kafli.
Logika jest w bibliotece (`download/laz.py`, ADR-029; wzor `cutout.py`):
`download_laz_area(bbox=..., ...)` przyjmuje bbox w dowolnym obslugiwanym
ukladzie (przeliczenie do EPSG:2180 w bibliotece, `area.bbox_to_2180`)
albo `sheet=` (godlo PL-1992/PL-2000: WFS pytany o obwiednie ramy, kafle
wybierane dla ramy `sheet_frame_2180`, `select_tiles(frame=)`),
`check_laz_area(...)` daje plan. `--geometry` sprowadza do bboxa
`download_data`; CLI tylko wypisuje wynik.
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
(`download/options.py::validate_request`). `--year` z dowolna granica roku =
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
Pokrywa tylko kafel pelny (`czy_ark_wypelniony` !=
`NIE`) i tylko rama albo tym samym godlem, nigdy obwiednia. Kafel, ktorego
rama nie przecina obszaru (przecina go tylko obwiednia), jest pomijany.
Kafel musi siegac w obszar glebiej niz `tolerance_m` (1 m; regula
`overlaps_area` skorowidzy: rama kafla zwezona o tolerancje przecina
obszar): sasiedni arkusz stykajacy sie z rama godla krawedzia albo
naroznikiem (ramy GUGiK zaokraglone do 1 cm) jest `outside`; obszar
wezszy niz 2 tolerancje bierze kazdy przecinajacy kafel.
Pominiete kafle: `LazTileSelection.superseded` / `LazDownloadResult.superseded`
(kafel + kafle pokrywajace; `outside` z pusta lista), w CLI `Info:` na
stderr takze z `-q` - tylko kafle pokryte przez nowsze (`outside` nie
naleza do obszaru i nie sa wypisywane).

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
jeden `FileStorage` wystarcza na cale zadanie PL. Dla `--country auto`
czesc PL korzysta z tego toru, czesc CZ z `download/cz_laz.py`;
obydwie czesci maja wspolny `extra.parent_request` (sekcja 4.6).

**Kampanie LAZ (ADR-030/032).** Domyslnie
(rowniez z gorna granica) zachlanny wybor ADR-029 w przedziale.
`--all-campaigns` = wszystkie kafle z rama przecinajaca obszar
(`select_all_intersecting`), bez deduplikacji pokryciowej; kafel
przeciety tylko obwiednia WFS trafia do `superseded` z powodem
"outside". `--year Y` = przedzial `[Y, Y]`, `--min-year`/`--max-year`
sa domknietymi granicami `akt_rok`; `--year` z dowolna z nich =
blad w CLI (`ValidationError` w bibliotece). `download_laz_area`
i `select_tiles` przyjmuja `year=`, `min_year=`, `max_year=`.
LAZ nie ma `kampanie/`; kafel jest wersja w `versions/`, a sciezka
standardowa to dowiazanie (ADR-036); `request.campaigns` w sidecarze tylko dla `all`.

Wynik: `data/laz/pl_2000_evrf2007/6/162/34/02/3/<oryginalna_nazwa>.laz`
(+ `.meta.json` z `extra.tile_sheet`/`year`/`nominal_density`/`url`,
`extra.acquisition_date`/`full_sheet`, gdy znane, oraz
`extra.parent_request` w trybie `--bbox`/`--geometry`; `request`
niesie bbox OBSZARU zadania (okno EPSG:2180 - nie kafla: obrys i `unit`
kafla czyta sie z naglowka LAS i z `extra.tile_sheet`, sekcja 3.3.1),
podane granice roku, `year` dla jednego roku
i `min_density`, gdy podane — E16).
`nominal_density` i filtr `--min-density` to wartosc NOMINALNA z WFS GUGiK
(`char_przestrz`); faktyczna gestosc kafla bywa kilkukrotnie wyzsza
(E2E 2026-10-06: ~119 pkt/m2 przy nominale 15).

**LAZ CZ (plan B, `download/cz_laz.py`).** `download_cz_laz(*, model,
vertical_crs, output_dir, sheet=None, bbox=None, update=None, plan=None,
parent_request=None, workers=4, cache=True, on_notice=None,
on_progress=None) -> CzLazResult(sheets, files, failed, stale, notices)`
(`ok` = brak `failed`) i `check_cz_laz(*, model, vertical_crs, output_dir,
sheet=None, bbox=None, cache=True, on_notice=None) -> UpdatePlan` to tor
poziomu komendy; `download_data` wola go dla godla CZ i czesci CZ obszaru.
Jedno wywolanie = jeden model (`dmr5g`, `dmr4g`, `dmp1g`, `dmpok`, rejestr
wariantow) i uklad wysokosci, ktory wyznacza pliki: CUZK publikuje LAZ
tylko w parach S-JTSK/Bpv (arkusze SM5, EPSG:5514) i ETRS89/EVRF2007
(kafle TM33, EPSG:3045), a chmur punktow Kartograf nie transformuje. Zla
para (np. godlo SM5 z EVRF2007), brak albo nieznany model, `--cutout`,
`--resolution` i `--min-density` = `ValidationError` przed siecia.
`CuzkLazProvider(model, session=None, cache=None, *, vertical_crs)`:
`sheets(area)` przelicza obszar (dowolny obslugiwany CRS) przypieta
operacja do ukladu systemu i bierze `SheetIndex.file_sheets(system, area)`
— arkusze SM5 z `PODIL > 0` (warstwa 24) albo kafle TM33 (warstwa 26;
`IN_CZ` ma w indeksie jedna wartosc `CZ`, wiec nie odroznia kafli
granicznych) — ta sama regula co raport CZ (4.9); obszar bez arkuszy =
`NoCoverageError`. Godlo SM5 jest sprawdzane w indeksie
(`SheetIndex.sm5_sheet`, `sheet_cache`), kafel TM33 parserem siatki.
`download(sheet, output_path, ...)` zapisuje czlon `.laz` ZIP-a openzu
bajt w bajt (`CuzkClient.fetch_file(..., unzip_single=".laz")`); 404 =
`DownloadError` arkusza z podpowiedzia indeksu. Pliki ida rownolegle
(`workers`); porazka pliku trafia do `failed` (`CzLazFailure(sheet,
error)`), pozostale zostaja (CLI: `Error:` na arkusz, kod 1). Magazyn:
`laz/cz_<model>_<vcrs>/<hierarchia godla>/<godlo>.laz` (`CTES/96`,
`760/5518`), wersje jak arkusz SM5 (etykieta = data pobrania, sygnal
`http`: `HEAD` ZIP-a przy lokalnej wersji z `--upgrade` przez `file_signal`), tor
planu `cz_laz` (`unit` = godlo). Sidecar: `dataset` `cz.cuzk.<model>_laz`,
`request.sheet`, uklad poziomy pliku (EPSG:5514/3045), pionowy natywny
(EPSG:8357/5621), `capability` `sheet_files`, `extra.http`, SM5
`extra.mapname`/`cz_share`, obszar `extra.parent_request`.

### 4.8 Land cover i gleby (BDOT10k, BDOO, CORINE, ZABAGED, Data50, Data250, SoilGrids)

**Magazyn wersji (ADR-036 D29-D33, ADR-044 D5-D6).** Publiczne funkcje
`download_landcover(product=..., output_dir=..., ...)` i
`download_soil(output_dir=..., ...)` pisza wylacznie do magazynu
`output_dir` (= `--output`; bez `output_path`, D32), w segmentach reguly 8
sekcji 3.3. Zwracaja `LandCoverReport`/`SoilReport` z `UnitFile` w `files`,
porazkami jednostek w `failed`, `stale`, `notices` i `ok`; przy `keep_raw`
oryginalne archiwa BDOT10k sa w `LandCoverReport.raw`. Wewnatrz uzywaja
`LandCoverManager`. Bledy wyborow i opcji to `ValidationError` przed
siecia; porazki pojedynczych plikow sa pozycjami `failed` (`ok=False`).
Polityka plikow jest wspolna z innymi torami (`download/fetch.py`):
`use_local` (decyzja bez
pobierania danych), pobranie do `versions/.incoming/`, `store_file`
(sha256 jednym odczytem, `commit_version`, sidecar wersji, hardlink).
Sygnal per kanal (`AccessChannel.update_signal`):

| Zrodlo / kanal | Sygnal | Etykieta wersji | Segment |
|---|---|---|---|
| SoilGrids WCS | `metadata`: `SoilGridsProvider.edition(property)` — pierwszy `ows:Title` GetCapabilities mapy wlasciwosci (`SoilGrids250m 2.0 - ...` -> `2.0`); mapa `ocd` nie podaje wydania w tytule (stan 2026-10-19), wiec jej wydanie to wydanie mapy `clay` (`extra.edition.url`/`title` wskazuja ja, a `extra.edition.source_property` = `clay` mowi to maszynowo) | wydanie | `soil/global_soilgrids_<wl>_<gl>_<stat>` |
| CORINE CLMS (`uses_clms(year)`: token i rok w `CLMS_YEARS`) | `metadata`: `CorineProvider.edition(year)` — `characteristics_release_major_version` z `@search?UID=<uid>&fullobjects=1` (bez tokenu) | wydanie (`V2020_20u1`) | `landcover/eu_corine_<rok>` |
| CORINE podglad WMS (bez credentials; 1990 zawsze) | `none` | data pobrania | `landcover/eu_corine_<rok>_preview` (`.png`) |
| BDOT10k paczka powiatu | `none` | data pobrania | `landcover/pl_bdot10k_gpkg[_<warstwy>]`, `_shp`, `_gpkg_zip` |
| BDOT10k archiwum rocznikow (`year`, kanal `archive_unit_files`) | `none` | rocznik (`label_source="edition"`) | `landcover/pl_bdot10k_<gml\|shp>_<rok>` |
| ZABAGED obszaru (`bbox`/`geometry`, REST, plan D) | `none` | data pobrania | `landcover/cz_zabaged` (`bbox/<coords>.gpkg`, EPSG:5514) |
| ZABAGED plik krajowy (`whole_country`, feed ATOM) | `metadata`: data `updated` wpisu pliku w feedzie zbioru | wydanie (`2026-10-04`) | `landcover/cz_zabaged_gpkg_<5514\|3045>` (`country/cz.zip`) |
| BDOO paczka wojewodztwa (`year` wymagany, plan E4) | `none` | rocznik (`label_source="edition"`) | `landcover/pl_bdoo_<rok>[_<klasy>]` (`teryt/<woj>.zip`) |
| Data50, Data250 obszaru (REST, plan E4) | `none` | data pobrania | `landcover/cz_data50`, `landcover/cz_data250` (`bbox/<coords>.gpkg`, EPSG:5514) |
| Data50, Data250 plik krajowy (`whole_country`, feed ATOM) | `metadata`: data `updated` wpisu pliku | wydanie (Data50 `2026-04-28`, Data250 `2026-05-12`) | `landcover/cz_data50_shp_<5514\|3045>`, `cz_data250_shp_...` (`country/cz.zip`) |

`metadata` (tabela decyzji 2 planu 3/3): wydanie jest pytane raz na plik
(`memoized_edition`) PRZED pobraniem — bez wydania nie powstaje wersja
(blad pliku, D30). Lokalna wersja z etykieta wydania: rowna = lokalna,
inna = domyslnie `newer=<wydanie>` (CLI: `dostepna nowsza ... (--upgrade)`),
`upgrade` pobiera; wydanie niedostepne = domyslnie `unverified="check_failed:
..."` (CLI `Warning:`), `upgrade`/`force` = blad. Wersja nie z wydania jest
nieporownywalna (`unverified="none"`). Ta sama tresc pod nowym wydaniem
= `relabeled` (D23). `none`: lokalna wersja niesprawdzona; naglowki HTTP
trafiaja do `extra.http`, ale nie sa sygnalem (ta sama tresc innego dnia
= `unchanged`). `check_landcover(...)`/`check_soil(...)` buduja plan
`kartograf-plan/1` (tor `landcover`, `unit` = TERYT / wspolrzedne bbox /
godlo) bez pobierania danych (dozwolone: GetCapabilities, katalog CLMS,
PRG); `download_landcover(..., update="upgrade", plan=)` lub
`download_soil(..., update="upgrade", plan=)` wykonuje tylko pozycje
planu, zmienione od planu wracaja w `stale`.

Parametry tresci (`_content_params`, U3) niosa segment i `request`
sidecara (`property`/`depth`/`stat`, `year`, `format`, `layers`) obok
wyboru (`teryt` / `bbox`+`bbox_crs` / `sheet` kanoniczne); `nodata` GeoTIFF
czytane z pliku (`null`, gdy brak tagu). Sidecar wersji SoilGrids/CORINE CLMS
ma `extra.edition` (`id`, `url`, `title` / `dataset_uid`). Podglad
CORINE: `horizontal_crs` uslugi WMS (EPSG:3857, 1990 EPSG:4326),
`extra.fallback = "wms_png"`, `extra.note = "podglad WMS, nie dane"`. Warstwe
rastrowa uslugi EEA danego roku (`Corine Land Cover <rok> raster`; nazwa to `12`
tylko w CLC2018, w innych latach `Corine_Land_Cover_<rok>_raster<numer>`)
`CorineProvider._eea_raster_layer` czyta z GetCapabilities raz na providera;
obraz podgladu w calosci przezroczysty (alfa 0: brak danych CLC roku dla obszaru)
to `NoCoverageError` PO pobraniu i PRZED zapisem wersji (`kind: no_coverage`, jak
true orto). Sidecar SoilGrids ma `extra.units` = `{mapped, conventional,
divisor}` (jednostki ISRIC: wartosc w pliku / `divisor` = jednostka
konwencjonalna; `uncertainty` to iloraz `10 x (Q0.95 - Q0.05) / Q0.5`),
a raster samych zer (poza `cfvo`) `extra.all_nodata` i `Warning`
`all_nodata`; `ocs` istnieje tylko dla `0-30cm` (`SoilGridsProvider.check_layer`),
okno mniejsze niz piksel jest rozszerzane do jednego piksela (250 m).

**ZABAGED (CZ, ADR-042 D15, plan D).** `LandCoverManager(output_dir,
"zabaged")` nie ma klasy providera (`COLLECTION_SOURCES`): opcje sprawdza
`_collection_request`, a wybor i pobranie robia funkcje
`download/collections.py` (`landcover_request`, `run_request`,
`plan_request`; te same zadania jednostek co kolekcje, sekcja 4.10) na
torze planu `landcover`. Obszar (`bbox` w dowolnym obslugiwanym ukladzie
albo `geometry`; jedyny kraj to CZ, bez `--country`) daje jeden GPKG
w EPSG:5514 z 22 warstwami pokrycia terenu i hydrografii (kody i nazwy
warstw ASCII z `registry.py::_ZABAGED_LAYERS`, opis warstwy = nazwa
uslugi z id, np. `Vodní tok (93)`), pelne geometrie obiektow
przecinajacych obszar; klasy NIE sa przeliczane na kody BDOT10k.
`whole_country=True` z `horizontal_crs` `EPSG:5514` albo `EPSG:3045`
(wymagany - plik jest publikowany w dwoch ukladach) = krajowy ZIP z feedu
ATOM 1:1 (5,8/6,7 GB, czlon `ZABAGED_RESULTS.gpkg` z warstwami pelnej bazy
pod nazwami CUZK, np. `VodniPlocha_c`), rozmiar z feedu w `Notice`
`whole_country_size` przed transferem. `teryt`, `format`, `layers`,
`keep_raw`, `year` = `ValidationError` z nazwa zrodla, `sheet` = blad,
`horizontal_crs` z obszarem = blad (wynik zawsze EPSG:5514). Jeden plik
na zapytanie: blad pobrania trafia do `LandCoverReport.failed` (`ok=False`).
Wewnetrzny `get_available_layers()` zwraca 22 nazwy warstw wyniku obszaru,
`get_supported_formats()` - `["GPKG"]`.

**BDOO (PL, plan E4, ADR-043).** `LandCoverManager(output_dir, "bdoo")`
idzie ta sama sciezka co ZABAGED (`COLLECTION_SOURCES`, `landcover_request`
z `teryt`, `year` i `layers`). GUGiK publikuje BDOO tylko jako paczke GML
wojewodztwa na rocznik (`opendata/bdoo/<R>/PL.PZGiK.201.<woj>.zip`; 2015,
2021-2026; brak pliku krajowego), wiec `year` jest wymagany (brak albo
rocznik spoza rejestru = `ValidationError` z lista), `teryt` to kod
wojewodztwa (kod powiatu = blad z podpowiedzia `--teryt <woj>`), a obszar
(`bbox`/`sheet`/`geometry`) daje paczki wojewodztw jego powiatow z PRG
(ogolna regula orkiestratora dla produktu bez paczek powiatow, `Info`
`unit_list`; wojewodztwo bez paczki trafia do `failed`, `workers`
rownolegle). Paczka jest zapisywana 1:1 (`teryt/<woj>.zip`, etykieta =
rocznik). `layers` (kody klas rocznika, `PackageVariant.classes`; klasa
spoza rocznika = `ValidationError` z lista klas tego rocznika) zapisuje
ZIP plikow `__OT_<KOD>_<typ>` wybranych klas (`class_pattern`) w osobnym
segmencie `pl_bdoo_<rok>_<klasy>`: czlony bajt w bajt, z nazwa, data
i kompresja zrodla, w kolejnosci zrodla - ta sama paczka daje te same
bajty (`unchanged`); obiekty zlozone (`__OT_Ciek` itd.), XSD i metadane
zostaja tylko w pelnej paczce. Do 2023 paczka nie ma pliku klasy bez
obiektow w wojewodztwie (klasy rocznika = suma po 16 paczkach): brak
czesci wybranych klas = `Info` `classes_absent`, brak wszystkich =
`NoCoverageError` wojewodztwa; `extra.source.classes` = klasy zapisane.
`get_available_layers()` zwraca klasy wszystkich rocznikow,
`get_supported_formats()` - `["ZIP"]`.

**Data50 i Data250 (CZ, plan E4).** Jak ZABAGED: obszar = jeden GPKG
wszystkich warstw obiektowych uslugi `DATA50/MapServer` (69) albo
`DATA250/MapServer` (116; rastry reliefu 5 i 6 nie sa danymi) w EPSG:5514,
nazwy warstw ASCII z nazw CUZK, bez przeliczania na klasy BDOT10k;
`whole_country=True` z `horizontal_crs` (`EPSG:5514` albo `EPSG:3045`) =
krajowy ZIP SHP z feedu ATOM 1:1 (Data50 516/757 MB, Data250 230/320 MB;
warstwy pliku pod wlasnymi nazwami, inne niz warstwy obszaru, np.
`shp/Akvadukt.shp`, `AirfldA.shp`), wydanie z `updated` feedu.

**BDOT10k z wielu powiatow (od 0.7.1, A2).** Pakiet BDOT10k jest zawsze
pakietem CALEGO powiatu, wiec sciezka i `request` sidecara opisuja
tresc: `landcover/pl_bdot10k_<format>[_<warstwy>]/teryt/<TERYT>.<ext>`,
`request = {teryt, format[, layers]}` — takze przy zadaniu przez
`--bbox`/`--sheet`/`--geometry`.
Obszar zadania idzie do `extra.parent_request`: `{bbox, bbox_crs,
countries: ["PL"]}` albo `{sheet, countries: ["PL"]}`.
`download_landcover(product="bdot10k", output_dir=..., teryt=|sheet=|bbox=|
geometry=, layer=, update=, plan=, workers=, on_notice=, format=, layers=,
keep_raw=)` dla obszaru pyta PRG (`Bdot10kProvider.teryts_for_area` ->
`discover_teryts_for_bbox`, obszar w dowolnym obslugiwanym ukladzie) i
pobiera pakiet KAZDEGO powiatu przecinajacego obszar, w kolejnosci kodow.
`LandCoverReport.files` zawiera udane pliki, `raw` osobne archiwa ZIP, a
`failed` porazki powiatow (`UnitFailure`); reszta jest pobierana
(spec 4.2); awaria odkrywania PRG jest bledem zadania, limit PRG wynosi
30 s. `workers` pobiera powiaty rownolegle. CLI `landcover download`
(ADR-039) jest jednym wywolaniem `download_landcover` (flagi `--layers`,
`--keep-raw`, `--bbox-crs`, `--workers`, `--quiet`), wypisuje statusy
plikow, `Error: <TERYT>: ...` dla porazek i konczy kodem 1 przy
`ok=False`. Niskopoziomowe `Bdot10kProvider.download_by_bbox`/
`download_by_sheet` (plik poza magazynem) pobieraja JEDEN powiat
(`_single_teryt`): obszar kilku powiatow to `ValidationError` z lista
kodow i podpowiedzia `download_landcover`. Provider stosuje swoj limit
czasu pobrania i zapytania PRG, nie jawny `timeout` komendy. Obszar wypisuje
`Info` `unit_list` (powiaty z PRG) i podlega limitowi kolekcji
(`download.collections.within_volume`: > 100 pakietow do pobrania albo > 10 GB
wg `HEAD` = `ValidationError` przed pierwszym transferem; takze archiwum
`year`). `layers=` (kody klas z `BDOT10K_CLASSES`: 58 klas rozporzadzenia 2021;
tylko GPKG) zostawia w scalonym GPKG wylacznie pliki `__OT_<kod>_*` pakietu;
nieznany kod i pusty kod to `ValidationError` przed siecia, klasa bez pliku
w paczce powiatu (brak jej obiektow) to `Info` `classes_absent` (jak BDOO;
`Bdot10kPackage.classes`/`absent`, `extra.source.classes`), a brak wszystkich
wybranych klas to `NoCoverageError` powiatu; plik z filtrem
nosi token warstw w segmencie, bo nie jest juz pelnym pakietem. Scalanie
pakietu (`_merge_gpkg_files`) konczy sie `DownloadError`, gdy nazwa
tabeli powtarza sie w dwoch plikach pakietu (dotad druga kopia byla po
cichu pomijana); w prawdziwej paczce (po jednej tabeli na klase i typ
geometrii, `..._<TERYT>__OT_<KOD>_<A|L|P>.gpkg`) duplikatow nie ma.

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
`download_landcover(product="bdot10k", output_dir=..., year=R,
format="GML"|"SHP", teryt=|sheet=|bbox=|geometry=)`
(CLI `landcover download --product bdot10k --year R --format GML|SHP`)
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
4.10) z sesja HTTP i limitem providera BDOT10k
(`Bdot10kProvider.session()`), na torze planu `landcover`. Obszar =
powiaty z PRG jak dla biezacych paczek (`extra.parent_request`, blad
powiatu w `failed`); `teryt` bez paczki w roczniku (HTTP 404, np. po
zmianie kodu TERYT) = `NoCoverageError`. Identyczne roczniki tego samego
powiatu i formatu zajmuja miejsce raz (D7: `relabeled`, hardlink; live
2026-10-15: SHP 2023 powiatu 1261 = 2022).

`calculate_hsg(output_dir=..., sheet=|bbox=|geometry=, layer=, depth=,
update=, plan=, on_notice=)` i `check_hsg(...)` (`hydrology/hsg.py`,
ADR-044 D5; statystyka zawsze `mean`) licza grupy glebowe z wersji
SoilGrids `clay`/`sand`/`silt` w tym samym magazynie (wewnetrzny
`HSGCalculator`; bledy wejscia to `ValidationError`, awarie pojedynczych
plikow trafiaja do `HsgReport.failed` i nie powstaje HSG) wg kanonicznego
trojkata USDA (ADR-025). Wynik `HsgReport(files, inputs, failed, stale,
notices, ok)` w `hsg/global_soilgrids_<gl>_mean/` (`bbox/<coords>` albo
hierarchia godla). Raster HSG jest w `files[0].file`, pobrane wersje
clay/sand/silt w `inputs`. Wersja HSG, ktorej `extra.source_files` ma te
same trzy sha256 wejsc (kolejnosc clay, sand, silt), jest uzywana ponownie
(`reused`, bez liczenia, dowiazanie na nia); inaczej klasyfikacja do `.incoming/`
i `store_file` z etykieta = posortowane unikalne etykiety wejsc laczone `+`
(`label_source = "edition"`). `--force` dotyczy wejsc. Sidecar wersji:
deskryptor `global.isric.soilgrids`, `product: "hsg"` (`build_metadata(
product=)`; wejscia maja `soil`), `capability="bbox_raster"`, `request`
= wybor (`bbox`+`bbox_crs` albo `sheet`), `horizontal_crs` = uklad rastra,
`nodata: 0`, `extra` = `{derived: "hsg", depth, stat, classes, source_layers,
source_files: [{name, file (sciezka wersji wejscia), sha256, label}]}`.
`hsg_statistics(path)` (`soil hsg --summary`) liczy obszar `request`
sidecara (bbox albo rama arkusza; bez niego caly raster): obrys obszaru
przeliczony do ukladu rastra rasteryzuje sie na siatce 10 x gestszej, wiec
komorka SoilGrids na brzegu liczy sie udzialem w obszarze (powierzchnie
komorek geodezyjnie dla EPSG:4326); grupy `A`-`D` i `nodata` sumuja sie do
obszaru, `percent` grup = udzial powierzchni z danymi, `nodata.percent` =
udzial obszaru; opisy grup po polsku (`HSG_DESCRIPTIONS`).
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
`calculate_hsg`. Nodata wejscia pochodzi wylacznie z
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
danych; od planu B takze CZ: ktore arkusze SM5 i kafle TM33 obszaru
(indeks `KladyMapovychListu`) maja pliki CUZK, z data publikacji
i rozmiarem z `HEAD` (CUZK nie publikuje lat nalotu), oraz `auto` (czesci
PL i CZ w jednym raporcie). CLI `kartograf elevation availability`
(`cli/availability_cmd.py`) tylko tlumaczy flagi (`--bbox` -> `BBox`,
`--force`) i drukuje wynik: tabela PL (kombinacje od najnowszego roku)
i tabela CZ (kolumny `MODEL`, `UKLAD`, `ROZDZ.`, `WYSOKOSCI`, `FORMAT`,
`ARKUSZE SA/BRAK`, `PUBLIKACJA`, `ROZMIAR`, `KOMPLET`; nad nia linia
`CUZK nie publikuje lat nalotu; daty = publikacja pliku`), `--details`
(godla arkuszy niepelnych — CZ: bez pliku —, lad bez arkuszy, polecenia
kazdej kombinacji), stopka z najnowsza kompletna kombinacja PL i
z kompletnymi kombinacjami CZ (na kombinacje najwyzej `MAX_HINT_LINES`
= 5 polecen i liczba pozostalych), `--json` = dokladnie
`AvailabilityReport.to_json()` (komunikaty tylko w polu `notices`, bez
powielania na stderr). `ok=False` (czesc `auto` niesprawdzona)
= raport wypisany i kod 1. Raport nie jest komenda danych projektu
(`project_task` katalogu = `false`; `project add` go odrzuca). Przyklady i wydruki na zywo:
USAGE 1.7.

**Walidacja przed siecia** (teksty jak `download_data`): jeden wybor
obszaru; `product` z `AVAILABILITY_PRODUCTS` (`nmt`, `nmpt`, `laz`);
`sheet` = godlo PL (PL-1992/PL-2000) albo CZ (SM5, TM33; kraj z godla;
kafel TM33 sprawdza `ParserTM33`); `bbox`/`geometry`
wymagaja `country`; `country` z `AVAILABILITY_COUNTRIES` (`pl`, `cz`,
`auto`; ten sam ksztalt raportu); granice lat
jak w pobieraniu (`year` = `min_year` = `max_year`) i tylko dla PL: z `cz`
albo godlem CZ = `ValidationError` (`CZ (CUZK) nie publikuje lat nalotu
...`), z `auto` obszar w obu prostokatach zaweza sie do PL (`Info:`,
`AUTO_NARROWED_TO_PL`), a obszar tylko w CZ = `ValidationError`.

**Algorytm PL:**

1. **Obszar** -> wypukle wielokaty (E, N) w EPSG:2180 — ten sam obszar,
   ktory pokrywa pobranie tego wyboru: NMT/NMPT `sheet` = rama godla
   (`sheet_frame_2180`: narozniki w ukladzie godla, krawedzie zageszczone;
   rama PL-2000 nie jest prostokatem w EPSG:2180), `bbox` = obwiednia
   `bbox_to_2180`, `geometry` = obwiednie obiektow warstwy
   (`read_feature_bboxes`, jak arkusze `download_data`); LAZ `sheet` = rama
   godla jak NMT, `geometry` = obwiednia calej warstwy (jak
   `download_laz_area`).
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
   format lub wariant spoza rejestru, godlo spoza `SheetParser`, brak URL
   `https` albo ukladu) nie sa kombinacja: jedna `Notice("info",
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
   `target` poza suma obrysow arkuszy z rekordem TAK (`missing`), poza
   obrysami wszystkich arkuszy kombinacji (`uncovered`) i poza obrysami
   rekordow TAK kazdej kampanii osobno (jeden `rasterize` na kampanie
   w pasie). `complete` <=> `missing == 0`; `uncovered_m2` = `uncovered`;
   bez progu. `full_m2` (KD-2) = `land_px * (target_px - missing) //
   target_px` (`land_px`, gdy `missing == 0`): udzial pokrytej czesci
   `target` przeniesiony na lad, w dol — dla `bbox`/`geometry` dokladnie
   `land_m2 - missing`, dla `sheet` pas ramy nie jest ani pokryty, ani
   brakiem; w PL `complete` <=> `full_m2 == land_m2`, same rekordy NIE = 0.
7. **Wynik:** `AvailabilityCombination` z `source` (klucz deskryptora),
   `year`, `acquisition_dates`/`published` (min/max `akt_data`/
   `dt_pzgik`), `campaigns` (`nr_zglosz`), `horizontal`, `resolution`
   (etykieta albo `None`), `vertical_crs`, `format`, `densities`
   (gestosci nominalne LAZ), `complete`, `sheets_full` (arkusz z co
   najmniej jednym rekordem TAK kombinacji), `sheets_partial` (tylko NIE),
   `uncovered`, `uncovered_m2`, `download_hint`, `full_m2`,
   `sheet_records` i `campaign_coverage` (KD-1, ADR-047; nizej);
   `sheets_missing` i `size_bytes` to pola CZ (plan B; PL puste/`None`).
   Kolejnosc: rok
   malejaco, uklad, rozdzielczosc, uklad wysokosci, format (kolejnosc
   `FORMATS`). `AvailabilityReport(request, checked_at, areas, combinations,
   notices, ok)` (`Document`: schemat `kartograf-availability/1` to stala klasy,
   pierwszy klucz dokumentu; bez pola `schema`); `areas` =
   `AvailabilityArea(country, crs, bounds, area_m2, land_m2)`;
   `checked_at` z `kartograf._clock`; `ok` = `False` tylko, gdy czesci
   zadania nie dalo sie sprawdzic (plan B, `auto`) — w PL zawsze `True`.
   `to_json()` z mixinu `Document` (sekcja 3.6): wciecie 2 spacje, `\n` na koncu.
8. **Rekordy do pobrania i kampanie (KD-1, ADR-047):** `sheet_records` =
   `AvailabilityRecord(sheet, campaign, acquisition_date, published, full_sheet,
   url)` rekordow, ktore pobiera `download_hint` kombinacji, po arkuszu,
   w arkuszu od najnowszego: NMT/NMPT najnowszy rekord arkusza w kolejnosci
   ADR-028 (`akt_data`, `dt_pzgik`, `url`) i — gdy nie jest TAK, a arkusz
   ma rekord TAK (podpowiedz z `--full-sheet`, ADR-033) — najnowszy TAK
   (`_sheet_records`, wspolne z `_needs_full_sheet`); LAZ kafle, ktore
   zostawia `select_newest_cover` (ADR-029) na obszarze zadania sposrod
   kafli kombinacji (jednego ukladu arkuszy). Ograniczenie LAZ: podpowiedz
   nie ma ukladu arkuszy, wiec pobranie `--year` wybiera z kafli obu
   ukladow naraz; gdy rok ma kafle PL-1992 i PL-2000, `sheet_records` moze
   sie roznic od tego, co polecenie zapisze (Krakow 2023: podpowiedz PL-2000
   pobiera kafle PL-1992). NMT/NMPT: `sheet_records` == plan pobrania.
   `campaign_coverage` = `AvailabilityCampaign(campaign, complete,
   full_m2)` na kazda kampanie z `campaigns` (ta sama kolejnosc): czy jej
   rekordy TAK same pokrywaja lad i ile ladu jest w ich ramach (miara
   `full_m2`). Test: `sheet_records` == URL-e planu `check_data`
   z podpowiedzi (`test_sheet_records_are_what_the_hint_downloads`; LAZ
   na roku z jednym ukladem arkuszy).

**Algorytm CZ i `auto` (plan B, decyzje 9-10):**

1. **Czesci:** `cz` z `bbox` = ten bbox, z `geometry` = obwiednia warstwy
   (`geometry_envelope`); godlo CZ = jego rama (SM5 z indeksu po nazwie,
   `SheetIndex.sm5_sheet` — godla spoza indeksu = `ValidationError`;
   TM33 z godla). `auto` dzieli obszar (geometria: jej obwiednie)
   prostokatnymi obwiedniami krajow jak `download_data`
   (`split_bbox_by_country`): czesc PL jak w algorytmie PL (bbox przyciety,
   geometria = jej obiekty), czesc CZ przycinana do prostokata CZ
   (`country_bbox(..., cz_crs=)`) osobno w ukladzie kazdego systemu
   arkuszy. `areas` w kolejnosci PL, CZ.
2. **Kombinacje:** warianty CZ produktu z kanalem plikow w natywnym
   ukladzie wysokosci plikow (`_cz_files`): NMT — DMR 4G, NMPT — DMP OK
   (kazdy `S-JTSK` Bpv i `ETRS89-TM33` EVRF2007), LAZ — 4 modele x 2
   systemy = 8; kolejnosc rejestru (model, potem S-JTSK przed
   ETRS89-TM33). Kombinacja powstaje tylko, gdy jej system ma >= 1 arkusz.
3. **Arkusze:** czesc CZ przeliczona do ukladu systemu (EPSG:5514 SM5,
   EPSG:3045 TM33; poza `auto` przez `bbox_to_crs`, jak pobranie LAZ
   obszaru) i `SheetIndex.file_sheets(system, obszar)` — regula wspolna
   z `CuzkLazProvider.sheets`: SM5 z `PODIL > 0`, kafle TM33 indeksu
   (`IN_CZ` ma jedna wartosc `CZ`, nie jest dyskryminatorem); cache
   `cz-sheets|<system>|<obszar w mm>`. Godlo CZ w swoim systemie jest
   jedynym arkuszem (SM5 z `PODIL` 0 — zaden), arkusze drugiego systemu
   pochodza z obwiedni jego ramy.
4. **Pliki:** jedno `HEAD` na plik openzu (rownolegle, `_HEAD_WORKERS` = 8,
   timeout 60 s, ponowienia jak `head_signal`), cache `head|<url>`;
   200 = plik (`Last-Modified`, `Content-Length`), 404 = arkusz bez pliku,
   kazda inna porazka (5xx, timeout, inne 4xx) = `DownloadError`, nigdy
   "brak pliku". Zadnego `GET` pliku danych
   (`test_cz_availability_never_gets_files`).
5. **Wynik CZ:** `sheets_full` (200), `sheets_missing` (404),
   `complete` = brak `sheets_missing`, `uncovered` = `bool(sheets_missing)`,
   `uncovered_m2` = czesc prostokata obszaru raportu lezaca w ramach arkuszy
   bez pliku, liczona w ukladzie tego prostokata (rama kafla TM33
   przeniesiona naroznik po narozniku przypieta operacja, wiec nigdy
   wiecej niz `area_m2`; `_frames_m2`), `full_m2` = ta sama miara dla
   arkuszy z plikiem (KD-2; `complete` nie wymaga `full_m2 == land_m2`, gdy
   obszar wychodzi poza arkusze indeksu), `published` = min/max
   `Last-Modified`
   (RRRR-MM-DD), `size_bytes` = suma `Content-Length` (`None`, gdy ktorys
   plik go nie podaje albo zaden arkusz nie ma pliku; CLI: `-`),
   `year`/`acquisition_dates` = `None`, `campaigns`/`densities`/
   `sheets_partial`/`sheet_records`/`campaign_coverage` puste,
   `horizontal` `S-JTSK`/`ETRS89-TM33`.
   `AvailabilityArea` CZ: `crs="EPSG:5514"`, `bounds` = czesc CZ
   w EPSG:5514, `area_m2` = `land_m2` = prostokat raportu (obszar: czesc
   CZ w EPSG:5514; godlo: jego rama) — CZ nie ma maski ladu.
6. **Modele bez plikow:** NMT (DMR 5G) i NMPT (DMP 1G) dostaja jedna
   `Notice("info", CZ_SERVICE_ONLY, ...)` (`cz_service_only`): model nie ma
   plikow arkuszy (raport go nie obejmuje), a jest dostepny dla calego CZ
   jako wycinek (`--cutout`), kafel TM33 z ImageServer i LAZ (`--model`);
   tylko gdy czesc CZ ma choc jeden arkusz indeksu (czesc `auto` w PL
   wewnatrz prostokata CZ — bez `Info:`). LAZ ma pliki wszystkich modeli.
7. **`auto`:** kraj, ktorego nie dalo sie sprawdzic (`DownloadError`), przy
   drugim sprawdzonym = `Notice("warning", CHECK_FAILED, ...)` i `ok=False`
   (raport drugiego kraju zostaje; CLI kod 1); porazka obu = wyjatek
   (pierwszy blad), jak zadanie jednokrajowe.

**Podpowiedz pobrania** (`_download_hint`): krotka polecen do wklejenia po
`kartograf ` albo po `kartograf project add NAZWA ` — bez `--output`
(magazyn pochodzi z `--output` uzytkownika albo z projektu, ADR-040).
Obszar jak w zadaniu (`--country pl --bbox ... [--bbox-crs]` albo
`--geometry PLIK [--layer]` + `--sheet-system`; `--sheet` — samo godlo,
gdy kombinacja jest w jego ukladzie (PL-2000: godlo i jego potomkowie),
inaczej po poleceniu na arkusz),
dla siatek PL-2000 po jednym poleceniu na skale arkuszy
(`--scale`), wariant (`--format` dla archiwow, `--resolution`, gdy
wariant ma etykiete, `--vertical-crs`), `--year`, a `--full-sheet`, gdy
w ktoryms arkuszu najnowszy rekord roku jest NIE, a pelny rekord tego
roku istnieje. Regula siatki (decyzja koordynatora 2026-10-16, E2E
planu B przy Cieszynie): polecenie obszaru albo godla tylko wtedy, gdy
arkusze, ktore zaplanuje pobranie PL tej skali (`_selected_sheets`:
siatka calego bboxa `--country pl` bez przyciecia, siatka geometrii albo
potomkowie godla; jeden wybor na uklad i skale, `functools.cache`), sa
podzbiorem arkuszy kombinacji; inaczej po poleceniu `--sheet` na arkusz
z rekordem (`_grid_areas`, PL-2000 osobno dla kazdej skali) — arkusz
siatki bez rekordu (za granica, morze, brak rekordu roku lub
rozdzielczosci) dalby `Brak danych` (`check_failed`, kod 1). Archiwa
(`source_file`) i LAZ: zawsze obszar albo godlo zadania (pobranie
planuje tylko rekordy skorowidza). LAZ: obszar + `--vertical-crs` +
`--year`. Polecenie wybiera dokladnie arkusze kombinacji (testy
`test_report_sheets_equal_download_selection`,
`test_border_hint_plans_only_sheets_with_records`). CZ (`_cz_hint`): raster —
po poleceniu na arkusz z plikiem (`elevation download --product nmpt
--sheet CTES86 --resolution 0.5m --vertical-crs Bpv`, uklad wysokosci
natywny dla plikow systemu); LAZ — jedno polecenie obszaru zadania
(`--country cz`, `--bbox`/`--geometry`, `--model`, `--vertical-crs`),
przy godle po poleceniu na arkusz. Kazda podpowiedz przechodzi walidacje
`download_data` i `project add` bez sieci (`test_cz_hints`,
`test_cz_hints_accepted_by_project_add`).

**Cache:** tabela `index_area_cache` w `MetadataCache`
(`get_index_area`/`set_index_area`, payload JSON, TTL jak rekordy —
`DEFAULT_TTL_SECONDS`, 7 dni): klucze `wfs-types|<endpoint>` (typy roczne
uslugi), `wfs|<endpoint>|<typy>|<obwiednia w mm>` (rekordy obwiedni
z obrysami), `prg|<obwiednia w mm>` (maska ladu) oraz CZ
`cz-sheets|<system>|<obszar w mm>` (arkusze indeksu) i `head|<url>`
(wynik `HEAD` pliku, takze 404); kafle indeksu WFS kolekcji (mesh 3D,
`transport/index_records.py::wfs_records(cache=)`) - klucz
`wfs-records|<endpoint>|<typ>|<obwiednia w mm>` z rekordami obszaru, wiec
ponowne pobranie obszaru z lokalnymi kaflami nie pyta indeksu
(`--check-updates`/`--upgrade`/`--force` odswiezaja wpis);
godlo SM5 trafia do `sheet_cache` (TTL
30 dni). Cache otwiera
`open_cache(cache, force=force)`; `force=True` (CLI `--force`) pomija
odczyt i nadpisuje wpisy. Ponowny raport tego samego obszaru nie pyta
sieci (pomiar 2026-10-15, 16 km2: ok. 5–7 s z siecia, 0,6–1,5 s
z cache; CZ 2026-10-16, 16 ha NMPT: 1,3 s z `--force`, 0,6 s z cache);
`kartograf cache stats` liczy wpisy w `Wpisy obszarow
skorowidza`.

**Bledy:** awaria uslugi skorowidza, PRG albo CUZK (indeks, `HEAD` inny
niz 404) = `DownloadError` (CLI
`Error:`, kod 1), nigdy pusty raport; pusta, poprawna odpowiedz = raport
bez kombinacji (CLI: `Brak arkuszy ... dla obszaru w skorowidzu GUGiK`,
CZ: `w indeksie CUZK`; kod 0). Pod `auto` porazka jednego kraju przy
sprawdzonym drugim = `CHECK_FAILED` i `ok=False` (punkt 7 wyzej). Raport
nie prosi o zaden plik danych
(`test_availability_never_downloads`: atrapa sesji odrzuca kazdy URL
spoza skorowidza i PRG; CZ: `test_cz_availability_never_gets_files`).
Zgodnosc CLI = API: `--json` daje ten sam tekst
co `check_availability(...).to_json()` z tym samym cache.

### 4.10 Kolekcje: paczki jednostek, obiekty obszaru i pliki feedu ATOM (ADR-042)

**Komenda w bibliotece.** `kartograf
boundaries|cadastre|models3d|hydro|names|maps|geodesy download` =
`download_collection(...)`/`check_collection(...)`
(`download/collections.py`); CLI tylko tlumaczy flagi
(`cli/collection_cmd.py`: `library_arguments` z katalogu daje argumenty funkcji,
te same dla pozycji projektu), a wspolny ksztalt grup jest w
`catalog/commands/_collection.py` (teksty `--help` z biblioteki:
`collection_product_choices`, `collection_level_choices`,
`collection_variant_choices`). `validate_collection_request` sprawdza caly
wybor BEZ sieci i jest jedynym miejscem regul (wolaja ja obie funkcje
i pozycje projektu): wspolrzedne bboxa, dokladnie jeden wybor (`teryt`,
`ku`, `sheet`, `bbox`, `geometry`, `whole_country`), produkt z rejestru,
kraj (`pl`/`cz`/`auto` wymagany z obszarem; `whole_country` tylko
`pl`/`cz`; z `sheet` z godla), kanal dla rodzaju wyboru, wariant
(`lod`, `year`, `format`, `scale`, `sheet_system`, `network`) i poziom (`level`,
z `auto` per kraj), `horizontal_crs` rowny ukladowi pliku. Blad podaje flagi
CLI i wybory, ktore produkt ma (np. `--teryt 1261: admin nie ma paczek
powiatow; dostepne: ...`). Wartosc opcji, ktorej nie ma zaden kanal
danego wyboru, a ma kanal innego wyboru, nazywa ten wybor (`--network
gravity: control (PL) - dostepne tylko dla --bbox/--sheet/--geometry
(obiekty obszaru); dla --teryt: horizontal, vertical`); zadanie PL+CZ
(`auto`) bez opcji wybierajacej albo z wartoscia jednego kraju dostaje
wartosci drugiego kraju i wartosci wspolne (jedna wartosc dotyczy obu).
Produktem kolekcji jest deskryptor z kanalem `unit_package` albo
`feature_bbox` poza `landcover` albo z samym plikiem krajowym feedu ATOM
jednego zbioru (QGZU; `atom.single_dataset`); feedy arkuszy i wojewodztw
(ortofoto CZ, NMT 100 m) naleza do `download_data`.

**Rodzaj wyboru wyznacza kanal (D2).**

| Wybor | Kanal | Jednostki | Plik (regula 9 sekcji 3.3) |
|---|---|---|---|
| `teryt` (2 cyfry = woj., 4 = powiat; PL) | `unit_package` tej jednostki | `[teryt]` | `teryt/<T>` |
| `ku` (6 cyfr; CZ) | `unit_package` KU | `[ku]` | `ku/<kod>` |
| `sheet` albo arkusze przecinajace obszar | `unit_package` arkuszy z indeksem PL lub CUZK | `[godlo]`/arkusze obszaru | hierarchia godla (`<MAPNOM>` CUZK: `cuzk_map_path_parts`) w segmencie wariantu |
| obszar produktu z kanalem `feature_bbox` | `feature_bbox` | jeden obszar w ukladzie natywnym uslugi | `bbox/<coords>.gpkg` |
| obszar produktu z kanalem kafli (`unit="tile"`) | `unit_package` kafli z rekordow indeksu WFS | rekordy obszaru (strony `next`), `year` = filtr rekordow (`Notice` `unit_list`) | `<uklad>[/<strefa>]/<kafel>` |
| obszar produktu bez `feature_bbox` (powiat) | `unit_package` powiatu | powiaty z PRG (`discover_teryts_for_bbox`, cache metadanych; `Notice` `unit_list`) | `teryt/<T>` kazdego powiatu |
| `whole_country` | `unit_package` jednostki `country` albo `atom_files` (plik z feedu ATOM CUZK; `horizontal_crs` wymagany, gdy plik ma kilka ukladow) | `pl` albo `cz` (PRNG: tematy) | `country/<kod>` (PRNG: `pl_<temat>`) |

Obszar: `bbox` w ukladzie z listy `--bbox-crs`, `sheet` = zasieg godla
PL albo CZ, `geometry` = obwiednia obiektow pliku (`--layer`).
Pod `country="auto"` obszar dzielony jest na kraje jak w `download_data`
(sekcja 4.6) i zawezany do krajow, w ktorych produkt istnieje (`Notice`
`auto_narrowed_to_pl`/`auto_narrowed_to_cz`); `world --country pl` nie
przycina obszaru do Polski. Obszar przeliczony do ukladu natywnego uslugi
(`transform_bbox`; uklady czeskie - operacja przypieta) albo pochodzacy
z arkusza/geometrii/`auto` daje `extra.parent_request` (sekcja 3.4);
paczki powiatow obszaru maja je zawsze. Plik krajowy:
najpierw `HEAD` (plik z feedu ATOM: `length` feedu, bez `HEAD`)
i `Notice` `whole_country_size` (`warning`: bajty albo "rozmiar
nieznany"), potem transfer (K7). Produkt jednego kraju pod `auto` jest
zawezany do niego (`network` -> CZ: `auto_narrowed_to_cz`), a poziom
`admin` z `auto` podaje sie per kraj (`{"pl": "gmina", "cz": "obec"}`;
jedna wartosc niedostepna w ktoryms kraju = blad z podpowiedzia
`--level pl=<poziom>,cz=<poziom>`).

**Zadania jednostek.** Kazdy plik to `UnitJob` (slot, `request` sidecara,
zrodlo): `package_job` (paczka jednostki albo plik krajowy) albo zadanie
obiektow obszaru. `run_job` = `fetch_version` slotu (polityka
`use_local`/`store_file`, sekcja 3.3 regula 6; tryby `update`),
`inspect_job` = pozycja planu `kartograf-plan/1` bez pobierania danych
(tor `collection`, `unit` = TERYT / wspolrzedne `_` / `pl` / `cz`). Blad jednostki
trafia do `CollectionReport.failed` jako `UnitFailure(unit, country, error,
kind)` (`no_coverage` dla `NoCoverageError`, `download` dla
`DownloadError`), pozostale jednostki dzialaja dalej (`workers` =
`ThreadPoolExecutor`, sesja HTTP per watek). Wynik: `CollectionReport(files,
failed, stale, notices, ok)`, `ok` = brak bledow i nieaktualnych pozycji
planu, z wyjatkiem `--country auto` w PL i CZ (regula `download_data`,
sekcja 4.6): kraj z bledami przy kraju bez bledow to czesciowy sukces -
`ok = True` (kod 0), `Notice` `auto_partial_success`
(`download/area.py::emit_partial_success`, wspolny z `download_data`), bledy
zostaja w `failed`. Kraj, w ktorym obszar nie ma jednostek (brak KU w RUIAN,
powiatu, arkusza, kafla - prostokatna obwiednia CZ obejmuje terytorium PL)
albo zapytanie o jednostki zawiodlo, to blad tego kraju
(`UnitFailure(<kraj>, <kraj>, ...)`, `_jobs`) i nie przerywa drugiego; brak
jednostek we WSZYSTKICH krajach = `NoCoverageError`. `--check-updates`: taki
kraj to `Warning` `check_failed` + `auto_partial_success` (jak `check_data`).
KU obszaru wg RUIAN (`cadastral_areas_for_bbox`, takze pusta odpowiedz) leza
w cache metadanych (`index_area_cache`, TTL 7 dni, jak powiaty PRG), wiec
powtorzenie obszaru dziala bez sieci. `Notice` `unit_list` nazywa co
najwyzej 10 jednostek, reszta jest policzona (`notices.names_text`). Czasy:
`SERVICE_TIMEOUT` 60 s (WFS/REST, kanal moze miec wlasny
`FeatureBBoxParams.timeout`, np. PRNG OGC API 180 s), `PACKAGE_TIMEOUT`
120 s (paczka), `PROBE_TIMEOUT` 30 s (`HEAD` sygnalu, zapytanie PRG),
`SIZE_TIMEOUT` 120 s (`HEAD` rozmiaru: serwer opendata GUGiK odpowiada
po 0,2-90 s, ok. 3,5 s na GB paczek drzew 3D).
`LandCoverManager` uzywa tych samych `package_job`/`run_job`/
`inspect_job` dla archiwum BDOT10k i `landcover_request`/`run_request`/
`plan_request` dla ZABAGED (tor `landcover`, sekcja 4.8).

**Limit obszaru (ADR-043 errata 3).** Zadanie obszaru (`bbox`, `sheet`,
`geometry`), ktore pobraloby wiecej niz `VOLUME_FILES` = 100 plikow albo
wiecej niz `VOLUME_BYTES` = 10 GB, konczy sie `ValidationError` PRZED
pierwszym transferem (`run_request` -> `_within_volume`, jedno miejsce dla
kolekcji, `LandCoverManager` i NMT 100 m): liczba plikow, rozmiar (suma
`HEAD`/`length` feedu ATOM; do 100 plikow kazdy plik jest mierzony, wiec
limit 10 GB jest dokladny, powyzej 100 o odmowie decyduje liczba, a rozmiar
to tylko orientacyjna srednia `VOLUME_SAMPLE` = 5 plikow rozlozonych
rownomiernie) i podpowiedz (zawez
obszar, wybierz jednostke `--teryt`/`--ku`, wykonaj plan z czescia
pozycji). Liczone sa pliki, ktore zadanie przesloloby: bez lokalnej
wersji, z `update="force"` wszystkie, z `--upgrade --plan` pozycje planu;
obiekty obszaru (`feature_bbox`) to jeden plik bez rozmiaru. Rozmiar
zapytany przed transferem nie jest pytany drugi raz (`Notice`
`download_size`, plik ATOM). Wybor jednostki (`teryt`, `ku`)
i `whole_country` nazywaja swoje pliki same - bez limitu, rozmiar dalej
w `Notice` przed transferem; brak opcji obejscia (decyzja 2026-10-15).

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

**Silnik `atom_files` (`transport/atom.py`, D12, plan D).** Feed uslugi
ATOM CUZK ma wpis na zbior (ORTOFOTO: 16 301 arkuszy SM5, 23,7 MB;
ZABAGED-GPKG: jeden zbior), wpis linkuje feed zbioru, a jego wpisy -
pliki (`rel="alternate"` z `length`, kategoria ukladu
`http://www.opengis.net/def/crs/EPSG/0/<kod>`). Nazwy plikow niosa rok
albo date wydania (`WRTO24.<rok>.<arkusz>.zip`,
`ZABAGED-5514-gpkg-<data>.zip`), wiec URL istnieje tylko w feedzie.
`atom_index` czyta feed uslugi strumieniowo (`iterparse`, wpisy
usuwane z drzewa) do `klucz -> AtomEntry`: `entry_pattern` szukany w id
feedu zbioru, grupa `sheet` = klucz (bez niej feed ma jeden zbior,
klucz `""`). Indeks lezy w `MetadataCache` (`atom_cache`) z `ETag`
feedu: w TTL (7 dni) bez zapytania, starszy: warunkowy GET
`If-None-Match` (304 = bez zmian); `--force`, `--upgrade`
i `--check-updates` (cache w trybie odswiezania) czytaja feed od nowa.
`resolve_atom_file` czyta feed zbioru zawsze swiezo (maly, niesie
wydanie) i wybiera plik po kategorii ukladu (`check_atom_crs` - bez
sieci); klucz brakujacy w indeksie z cache albo 404 feedu zbioru = JEDNO
odswiezenie indeksu. Wydanie = data `updated` wpisu pliku, z rokiem
grupy `year`, gdy jest (`2024_2025-02-06`, `2026-10-04`) - etykieta
wersji i sygnal `metadata`. `fetch_atom_file` pobiera atomowo i porownuje
rozmiar z `length` feedu i `Content-Length`; `unpack_members` kopiuje
czlony ZIP 1:1 (najdluzszy sufiks najpierw). Klucz spoza feedu =
`NoCoverageError`; HTML zamiast feedu, wpis bez jednego linku, plik
niejednoznaczny, przerwany transfer = `DownloadError`. Limity odczytu:
feed uslugi 120 s, feed zbioru 60 s.

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
warstwa obok niepustych = warstwa ze schematem bez obiektow (bez schematu
XSD - HY-NET - warstwa z samym polem identyfikatora). Strony sa
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
z typami pol z `fields` warstwy. XSD, ktory sam nie deklaruje typow
(HY-NET: tylko `xsd:include` zdalnego schematu INSPIRE), nie trafia do
GDAL: pola sa czytane z tresci kazdej strony, warstwa dostaje sume pol
stron w kolejnosci pierwszego wystapienia (brak pola = null, jedno pole
o dwoch typach = `DownloadError`), wiec schemat HY-NET zalezy od tresci
obszaru (ADR-042 errata 2); pusty typ bez schematu = warstwa z samym
`gml_id` (geometria `Unknown`). Opis warstwy (`DESCRIPTION`) = typ WFS
albo nazwa warstwy ArcGIS z id (`Vodní tok (93)`, `Obec (12)`). Identyczny duplikat (pola poza
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

**Magazyn, sygnaly i etykiety (D6, D7).** Sygnal = `update_signal` kanalu.
Kanaly bez jawnie ogloszonego sygnalu (`PRG`, `EGiB`, obszary
`PRNG`/`Geonames`, kraj `PRNG` i inne obiekty obszaru) maja `none`:
lokalna wersja jest uzywana bez zapytan, `--check-updates` = `unverifiable`
(`nie da sie sprawdzic bez pobrania`), nowa tresc przynosi tylko
`--force` (ta sama
tresc = `unchanged`, inna = nowa wersja). Pliki krajowe CUZK z `ETag`
(RUIAN, HY-NET) maja `http`: `--upgrade` porownuje lokalna wersje jednym
`HEAD` (inny `ETag` = pobranie), `--check-updates` = `current`/`newer`,
domyslnie lokalna wersja bez zapytania. Plik z feedu ATOM (ZABAGED,
Geonames kraj, QGZU) ma `metadata`: wydanie z feedu przed pobraniem, inne
wydanie = `newer`. Mapy BDOT10k maja `index` (data `Stan bazy` osobno
dla skali z GetFeatureInfo; arkusz z lokalna wersja domyslnie bez
GetFeatureInfo - `_sheet_jobs(skip_local)`, `UnitJob.unchecked`), kafle
mesh 3D tez (etykieta rekordu WFS:
`Aktualnosc` i `Numer_zgloszenia_pracy`; kafle obszaru wybiera indeks WFS,
ktorego rekordy obszaru leza w cache metadanych - `index_area_cache`,
TTL 7 dni - wiec ponowny przebieg z lokalnymi kaflami nie pyta sieci, jak
skorowidze arkuszy PL; tryby `--check-updates`/`--upgrade`/`--force` pytaja
indeks), arkusze ZTM `http` (`HEAD`).
Etykieta = `edition` wariantu (rocznik
BDOT10k, rok modeli 3D; `label_source="edition"`), wydanie z feedu ATOM
albo data pobrania (PRG, EGiB, RUIAN, HY-NET). Wydania tej samej tresci - warianty rozniace sie tylko wartoscia
rowna wydaniu (`year`), przy tym samym formacie i LoD - to sloty pokrewne
(`FileSlot.related_roots`): identyczny sha256 w innym wydaniu tej samej
jednostki = hardlink do istniejacych danych, status `relabeled`
(`same_as` = etykieta znalezionej wersji).

**Nazwy i mapy (E2).** `pl.gugik.prng` i `pl.gugik.prng_world` maja po
jednej kolekcji OGC API Features (natywnie CRS84; `numberMatched`, strony
`next`, strona do 10000 obiektow, limit jednego zapytania 180 s).
`world` nie ogranicza obszaru do zasiegu PL; krajowe PRNG to ZIP-y
oryginalnych dwoch tematow RP albo jednego `SWIAT`. Geonames CUZK to
25 warstw ArcGIS REST w EPSG:5514 i dwa kanaly krajowe feedu ATOM
(`GPKG`/`FGDB`, wybor EPSG:5514/3045). Mapy BDOT10k to 4 skale x
2 formaty z rekordow `wms_gfi` (`Mapy10k`...`Mapy100k`); skala
okresla liczbe czlonow godla, format oddzielny segment magazynu.
ZTM CUZK to 6 skal x 2 uklady (S-JTSK/ETRS89), odpowiednio
ZIP TIFF/DGN/SHP lub PDF (ETRS89 tylko TIFF/PDF). System arkusza
wynika z jego godla, ale sprzeczny `sheet_system` jest bledem;
`sheet_grid.crs` wariantu daje sidecar EPSG:5514 albo EPSG:3045.

**Granice, ewidencja i CZ (E3).** `pl.gugik.prg_addresses` ma trzy
kanaly: WFS KIN (`A07_Punkty_adresowe` i `A08_Ulice` do jednego GPKG
EPSG:2180, osie N,E), paczki SHP powiatow (`unit="powiat"`) i dwa pliki
krajowe (SHP, GML wybierane `--format`). `pl.gugik.prg_special` to OGC API
PRG w CRS84 (44 kolekcje jawnie w deskryptorze) z limitem czasu kanalu
120 s (`FeatureBBoxParams.timeout`; obszar to minuty, bo usluga pyta
o kazda kolekcje osobno) i plikiem krajowym SHP/GML. Kolekcja
`GranicaObwoduSpisowego` nie wchodzi do wyniku obszaru (odpowiedz po
158 do ponad 400 s): `FeatureBBoxParams.area_omitted` niesie tekst, ktory
silnik kolekcji zamienia w `Info` `AREA_OMITTED` (`<produkt>: <tekst>`)
przy kazdym zadaniu obszaru kanalu (obwody sa
w pliku krajowym). Ten sam mechanizm maja `cz.cuzk.hynet` (typ
`WatercourseSeparatedCrossing` bez geometrii tylko w pliku krajowym)
i `cz.cuzk.zabaged` (22 warstwy obszaru wobec pelnej bazy pliku
krajowego). `pl.gugik.rcn` ma kanaly
`unit="powiat"` i `unit="woj"`; paczka ZIP jest rozpakowywana do jednego
GPKG (`UnitPackageParams.unpack=".gpkg"`), a `unpack_layers` (tylko
z `unpack=".gpkg"`; niezmiennik rejestru) wymusza obecnosc warstw
`transakcje_dzialki`, `transakcje_budynki`, `transakcje_lokale`:
rozpakowanie i kontrola ida w lokalnym katalogu roboczym (SQLite nie
dziala na wolumenach sieciowych), brak warstwy = `DownloadError` i brak
wersji. `cz.cuzk.cadastral_map` to `unit="ku"` z czterema wariantami
(`--format SHP|DXF|DGN|VFK`, ZIP 1:1, sygnal `http`); KU obszaru wg
warstwy RUIAN 7. `cz.cuzk.geomorphology` to ArcGIS REST
(`GeomorfologickeJednotky`, EPSG:5514), jedna warstwa na poziom
(`--level`, `selection="level"`). Mapa katastralna w formacie VKM jest
poza 0.8.0 (adres pliku VKM odpowiada 404 dla KU 623164).

**Modele 3D, osnowy i quasi-geoidy (E5).** `pl.gugik.mesh` ma kanal
`unit="tile"` z `IndexSource(kind="wfs", unit_field=None)`: indeks
`ModeleSiatkowe3D` ma jeden rekord na plik, ale pole `modul` (`74230_55482`)
nazywa kafle kilku prac i miast (26 633 wartosci w kilku miejscach kraju,
138 miejsc z dwoma mesh jednego roku - ze zdjec i ze skaningu), wiec
jednostka = nazwa pliku rekordu bez `.zip` (`78944_6777_74230_55482`),
kazdy rekord obszaru to osobny plik, a `year` filtruje rekordy (regula
"najnowszy rekord kafla" nie dotyczy mesh). Katalog slotu (`1992` albo
`2000/<strefa>`, regula 10) i uklad sidecara daje `uklad_xy` rekordu (OBJ
we wspolrzednych tej strefy), wysokosci
`EPSG:9651` z wariantu. `pl.gugik.trees` to paczki powiatow jednego
wydania (LoD1 2023; flagi `--lod`/`--year` mozna pominac, inna wartosc =
blad) - 0,3-25 GB, `Notice` `download_size` przed transferem, strumien do
stagingu i kontrola ZIP na dysku; obszar prawie zawsze przekracza limit
10 GB, `--teryt` nie ma limitu. `pl.gugik.control` ma cztery kanaly WFS
(jedna usluga na siec, wybor `choice` `network`, wspolna capability
`bbox_vector`), paczki powiatu sieci poziomej i wysokosciowej
(`unit="powiat"`, tokeny `<siec>`, `xls`) i archiwa arkuszy 1:100 000
(`unit="sheet"`, `SheetGrid(system="1992", parts=3)`; `--sheet` dowolnej
skali daje arkusze 1:100 000 jego zasiegu). Siec grawimetryczna,
magnetyczna i archiwa nie maja paczek powiatu: `--teryt` z nimi = blad
z podpowiedzia wyboru obszaru. `cz.cuzk.control` to jeden kanal
ArcGIS z `selection_key="network"`, w ktorym jeden kod sieci nazywa kilka
warstw (pozioma: 18, 20 i warstwy wyznaczone w ETRS89 2-8, ktore nie sa
podzbiorem 18/20 - zero wspolnych punktow w kraju). Quasi-geoidy to jeden
plik krajowy: PL-geoid2021 TXT (`file_kind="txt"`, plik bez ZIP sprawdzany
jako tekst bez NUL i znacznikow) i QGZU ZIP z feedu ATOM (produkt kolekcji
z samym kanalem ATOM jednego zbioru); obszar = blad z `--whole-country`.
Kartograf nie stosuje modeli do innych danych (ADR-043, pkt 7 planu E).

### 4.11 Interfejs dla agentow: katalog komend, dokumenty i serwer MCP (ADR-046)

**Zasada.** To samo zadanie wykonane przez CLI z `--json`, przez biblioteke (`to_dict()`) i
przez serwer MCP daje ten sam dokument (3.6); blad ma stabilny `code`, `exit_code` i `hint`
(`kartograf-error/1`). CLI i MCP sa cienkie: tlumacza i drukuja (Z1, Z8), a komendy,
parametry i dozwolone wartosci opisuje jeden katalog (Z9). Uzycie: USAGE, sekcja 9;
uzasadnienia: ADR-046.

**Katalog komend (`src/kartograf/catalog/`).** Deklaracje (`catalog/spec.py`: `Command`, `Param`,
`Constraint`, `Example`, `Group`) leza w `catalog/commands/<modul>.py`, po jednym module na
grupe CLI (`MODULE_ORDER`: elevation, imagery, landcover, soil, boundaries, cadastre,
models3d, hydro, names, maps, geodesy, project, misc); `declared()` znajduje moduly po
nazwie, wiec nowa grupa to jeden nowy plik. `Param` niesie nazwe, rodzaj (`str`, `int`,
`flag`, `bbox`, `bbox_crs`, `path`, `per_country`, `str_list`, `plan`, `options`), flage CLI,
nazwe argumentu API (`argument`), wymagalnosc, `task` (opcja zadania projektu), `allowed`
(dostawca czytajacy rejestr zrodel przy budowie katalogu, nie przy imporcie), opis i pola
tylko dla parsera (`dest`, `metavar`...). Z deklaracji powstaja:

- `get_catalog(group, command, params, tables)` -> `Catalog` (`kartograf-catalog/1`,
  `catalog/build.py`, `model.py`): przeglad (`view: overview`, ok. 7,6 tys. znakow), opis
  grupy albo komendy, caly katalog z parametrami; `tables=True` dodaje `exit_codes` i
  `errors` (`error_report.EXIT_CODES`, `ERROR_CODES`) oraz `schemas` (`SCHEMAS`);
  `data_commands()` zwraca 12 komend danych (KB-1);
- parser CLI (`catalog/cliparser.py::build_parser`; `cli/_parser.py::create_parser` to
  fasada): `--help`, `choices`, wykluczanie flag i przyklady (`epilog` z przykladow
  katalogu); moduly `cli/groups/*` nie istnieja;
- opcje komend danych projektu (`project/commands.py::COMMANDS`: `TaskCommand.options` =
  `Command.task_options`) i konwersja JSON <-> argumenty biblioteki
  (`catalog/kinds.py::convert_arguments`), wspolna dla `project add`, `parse_command` i serwera
  MCP;
- specyfikacje narzedzi MCP (`catalog/tools.py`) i podpowiedzi bledow
  (`catalog/hints.py::example_for`: przyklad komendy w `hint`).

Spojnosc wymuszaja testy kontraktowe (`tests/unit/test_catalog*.py` and `tests/contract/test_catalog_declarations.py`): flagi parsera == katalog w
obie strony, `COMMANDS[...].options` == parametry `task`, `function`/`check_function` w
`kartograf.__all__` ze zgodnymi sygnaturami, `allowed` == rejestr, przyklady przez
`validate_command` i okrazenie `parse_command(format_command(...))`, ograniczenia testowane
naruszeniem wyprowadzonym z przykladu. Biblioteka nie importuje `kartograf.cli` (test w
czystym procesie).

**Warstwa komend (`src/kartograf/commands.py`, KB-2..KB-5 Archiwisty).** `parse_command` (linia
-> `CommandCall(command, options, run)`; parser katalogu w trybie "tylko podane flagi"),
`validate_command` (konwersja i walidacja zadania bez sieci i zapisu), `format_command`
(`catalog/formatting.py`), `run_command`/`check_command` (konwersja, walidacja, potem funkcja
komendy: `download_data`, `download_collection`, ... albo `check_*`). `options` to postac
JSON opcji zadania projektu (ADR-040), `run` - pozostale flagi linii pod nazwami
parametrow (`output_dir`, `upgrade`, `force`, `check_updates`, `plan`, `workers`,
`quiet`, `json`, `summary`; nie ma klucza `update`: `run_command` bierze tryb jako
`update="upgrade"|"force"`, a `check_updates` to `check_command`, wiec odwzorowanie robi
wywolujacy). Funkcje bez sieci (`parse_command`, `validate_command`,
`format_command`) maja test z atrapa transportu odrzucajaca kazde zapytanie.

**Bledy.** Kazda klasa `KartografError` ma w `__dict__` wlasny `code` (snake_case, unikalny;
`tests/integration/test_errors.py`), `exit_code`, `DETAIL_FIELDS` i opcjonalny `hint`; walidatory biblioteki
ustawiaja `ValidationError.option`/`options`/`allowed` (nazwa argumentu API, nie flaga).
`error_report(exc, command=)` zamienia dowolny wyjatek na `ErrorReport` (kody `io_error` dla
`OSError`, `interrupted`, `terminated` i `internal_error` buduje tu, a nie klasy hierarchii); `hint` skladany
deterministycznie z `exc.hint`, `DEFAULT_HINT`, `hints`/`remedy` albo `Dozwolone wartosci ...` i
`Przyklad: ...` z katalogu (do 400 znakow). `main` (`cli/commands.py`) wykrywa tryb JSON przed
parsowaniem (`cli/_json.py::json_mode`), buduje parser z `usage_errors=True` (blad skladni
to `UsageError`, z `command`, gdy linia nazwala znana komende) i zamienia kazdy wyjatek na
dokument `kartograf-error/1` na stdout (stderr pusty) oraz kod wyjscia `e.exit_code`
(0/1/2), 130 dla Ctrl-C, 143 dla SIGTERM; `KARTOGRAF_DEBUG=1` podnosi wyjatek ponownie. Rekordy loggera
`kartograf` (poziom WARNING i wyzej) `main` zamienia na linie `Warning:`/`Error:` na stderr
(`_StderrLines`; bez handlera Python drukuje je bez prefiksu); z `--json` przechodza tylko
rekordy `kartograf.transport.http` (ponowienia), a z `KARTOGRAF_DEBUG` wszystkie. Tabele kodow wyjscia
i bledow sa w USAGE 9.3 (`tests/contract/test_docs_tables.py` pilnuje ich rownosci z katalogiem).

**Przerwanie i pule watkow (`src/kartograf/interrupt.py`).** Ctrl-C to `KeyboardInterrupt` tylko w
watku glownym, wiec `--workers >= 2` (jednostki w `ThreadPoolExecutor`) czekalo na cala kolejke
i zatwierdzalo ja po przerwaniu (e2e 0.8.0: B P2-1, C P2-5, D P2-2). Kazda pula pobierania
(`DownloadManager._download_many`, `run_request` kolekcji, powiaty BDOT10k w `LandCoverManager`,
kafle LAZ PL i arkusze LAZ CZ) idzie przez jednego pomocnika `run_parallel(work, items,
workers=, on_done=)`: gdy watek czekajacy na wyniki dostanie wyjatek (Ctrl-C, blad jednostki,
wyjatek `on_done`), jednostki, ktore nie ruszyly, sa anulowane, a trwajace dostaja flage stopu;
wywolanie wraca dopiero po nich, wiec nic z puli nie dziala dalej i nic nie jest zatwierdzane po
przerwaniu (wersje zatwierdzone wczesniej zostaja). Jednostka widzi flage w `check_stop()` (przed
zapytaniem i miedzy kawalkami ciala w `transport/http.py::download_to`/`get_with_retry`/
`head_signal`, w `transport/aaigrid.py`, w petlach paczki BDOT10k i na poczatku
`commit_version`) oraz zamiast pauzy ponowienia, i konczy sie `Stopped` - podklasa
`KeyboardInterrupt`: dziala to samo sprzatanie co przy `--workers 1` (`except BaseException`,
`finally`), a zaden `except Exception` pakietu nie zamienia jej w porazke jednostki. Zapytanie
zablokowane na sieci konczy sie najpozniej z limitem czasu. Pule sond (`executor.map` z HEAD i
zapytaniami indeksu) anuluja kolejke juz same (`map`) i czekaja tylko na biezace zapytania.
SIGTERM: `sigterm_interrupts()` (CLI `main`) rzuca w watku glownym `Terminated` (tez
`KeyboardInterrupt`; pierwszy sygnal przywraca domyslna reakcje), a `error_report` daje
`terminated`/143. Poza `main` (biblioteka, serwer MCP) sygnal nie jest przechwytywany.

**Serwer MCP (`src/kartograf/mcp_server.py`, `catalog/tools.py`).** `catalog/tools.py` zamienia
deklaracje na specyfikacje 29 narzedzi (nazwa, krotki opis, schemat wejscia JSON Schema
2020-12 bez `$ref`, adnotacje, funkcja) bez `mcp`; `mcp_server.py` wystawia je przez
niskopoziomowy `mcp.server.Server` (stdio): wynik `CallToolResult(content=<zwarty JSON>,
structured_content=<to_dict()>, is_error=<kod wyjscia != 0>)`, bledy jako `kartograf-error/1`,
walidacja wejscia schematem (`jsonschema`), regula sciezek bezwzglednych (`--allow-dir`),
postep przez `report_progress`, najwyzej 4 jednoczesne wywolania sieciowe i cache serwera w
katalogu cache uzytkownika. SDK `mcp` jest zaleznoscia opcjonalna (extra `mcp`), a dotyka go
tylko `mcp_server.py` i to leniwie. Budzet kontekstu agenta (D22): `tools/list` <= 30 000 znakow
(opisy narzedzi pisane na wywolanie, wspolne znaczenia w `instructions`), `get_catalog()` <= 8 000
znakow; pilnuja go testy. Uzycie i konfiguracja klientow: USAGE 9.6.

**Nowa komenda przez katalog.** Deklaracja w `catalog/commands/<modul>.py` (`Command` z
`function`/`check_function` z `kartograf.__all__`, `result_schema`, `tool`, parametrami,
ograniczeniami i przykladami), handler w `cli/_handlers.py::HANDLERS` (grupa kolekcji: nazwa
w `COLLECTION_GROUPS`), dla komendy danych pozycja w `project/commands.py::COMMANDS`, a dla
narzedzia MCP wpisy `_BRIEF` w `catalog/tools.py` (nowy parametr nie zbuduje narzedzi, dopoki
go nie dostanie). Przepis krok po kroku: DEVELOPMENT_STANDARDS 17.2.

---

## 5. Jak dodac nowe zrodlo albo nowy kraj

Checklist na przykladzie DE (Brandenburgia, DGM1):

1. **Deskryptor** w `src/kartograf/sources/registry.py`: `key="de.lgb.dgm1"`,
   `country="DE"`, `product="nmt"`, `provider_name="LGB"`, kanaly
   (`AccessChannel` z transportem, ukladami, `capabilities`, `endpoint`),
   licencja, `storage_subdir="nmt/de_bb_dgm1_{vcrs}"`, `default_extension`;
   klucz i katalog wg konwencji nazw (sekcja 3.3, regula 10; pilnuje jej
   test rejestru). Sam ten
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
   istnieja; CLI nie zmienia sie poza wyborami flag w deklaracji katalogu
   (`catalog/commands/elevation.py` / `imagery.py`, stale z `download/options.py`). Scenariusz kraju w `tests/contract/test_parity.py`. Reprojekcje rob lokalnie, przypieta operacja — nigdy przez
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
wycinka NMT/NMPT to osobna decyzja — dzis tylko warianty 1 m; kanaly
WCS wycinka ortofotomapy sa wpisami `WcsCutoutParams` (sekcja 3.1, 4.3).

Nowa **komenda zapisujaca dane** (w tym `download` nowej grupy) to deklaracja
w `src/kartograf/catalog/commands/<grupa>.py` (parametry `task=True` = opcje zadania
manifestu; parser CLI, opcje projektu i schematy MCP powstaja z niej, sekcja 4.11)
oraz pozycja w `src/kartograf/project/commands.py::COMMANDS`: wspolna z pobraniem
walidacja bez sieci, funkcja pobrania i `check_*`, adapter wyniku na komplet
przypinanych `VersionedFile`. Dodaj test zadania projektu dla tej komendy
(przypiecie, sprawdzenie i odtworzenie); nowy produkt istniejacej komendy nie
wymaga nowej pozycji w tabeli (ADR-040, spec manifestu sekcja 5).

**Nowy produkt kolekcji (ADR-042).** Paczka jednostki (powiat,
wojewodztwo, plik krajowy), obiekty obszaru z WFS 2.0 / ArcGIS REST albo
plik z feedu ATOM CUZK to wpis deskryptora z `AccessChannel.params`
(`UnitPackageParams`, `FeatureBBoxParams` albo `AtomFilesParams`, sekcja
3.1) - bez providera i bez kodu silnika:
segment = `storage_subdir` + tokeny wariantu (sekcja 3.3 reguly 9 i 10), kanal
wynika z rodzaju wyboru (sekcja 4.10), sidecar, wersje i plan sa wspolne.
Kolejnosc osi BBOX (`axis_order`) potwierdz testem na prawdziwej
odpowiedzi uslugi (zamiana osi daje pusty wynik bez bledu), kanal dopisz
do inwentarza sygnalow testow rejestru, fixtury nagraj z prawdziwych
odpowiedzi. CLI: nowa grupa = modul `catalog/commands/<grupa>.py` z `collection_commands`
i `collection_group` (`catalog/commands/_collection.py`), nazwa grupy w `COLLECTION_GROUPS`
(`cli/_handlers.py`) i pozycja projektu (akapit wyzej); nowy
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
