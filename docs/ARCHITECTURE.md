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
(`HSGCalculator._write_sidecar`, sekcja 4.8) i CLI (tor CZ) —
nigdy providery; provider zwraca `Path`, metadane skladane sa pietro wyzej,
gdzie znany jest kontekst zadania. Wynika z tego, ze bezposrednie wywolanie
providera z biblioteki (np. `GugikProvider.download`,
`CuzkDmrProvider.download`/`download_bbox`) zapisuje sam plik danych, bez
sidecara — w szczegolnosci sidecar DMR CZ powstaje wylacznie w CLI
(`cli/download_cmd.py::_write_cz_sidecar`), bo tor CZ omija warstwe
zarzadzajaca (ADR-023). Nowy sidecar powstaje zawsze przez
`sources/sidecar.py::emit_sidecar` — jedyne miejsce polityki zapisu
(poza nim: kopia sidecara celu w sciezce standardowej,
`download/links.py::write_standard_sidecar`, i dopisanie
`extra.parent_requests` w `DownloadManager`). Zapis
jest domyslnie best-effort: kazdy blad (IO, brakujacy klucz deskryptora,
wyjatek w budowie metadanych) konczy sie `logger.warning` i zwrotem `None`,
nigdy przerwaniem pobrania — dane sa wazniejsze niz metadane. Poza bledem
zapisu jedyny cichy przypadek braku sidecara przy sukcesie to provider bez
`descriptor_key` (`descriptor_key` nie bedacy `str`): `emit_sidecar` wraca
wtedy `None` bez ostrzezenia. Z `required=True` (tylko sidecar pliku
kampanii) oba przypadki koncza sie `DownloadError`. Pominiety juz pobrany plik zachowuje
dotychczasowy sidecar (wyjatek ADR-030: sidecar pliku w `kampanie/` jest obowiazkowy, sekcja 3.2); arkusz z sidecarem ponownie wykorzystany
w zadaniu obszarowym dopisuje `extra.parent_requests` bez zmiany
oryginalnego `parent_request`.

**Polityka transformacji (ADR-024).** Transformacje, ktore przesuwaja TRESC
rastra albo opuszczaja uklady czeskie (EPSG:5514/3045), przechodza przez
`kartograf/transform/crs.py` — poza obwiednia w WGS84 do rozpoznania kraju
i przyciecia pod `auto` (`_bbox_to_wgs84` w `cli/download_cmd.py`, takze dla
bboxa podanego w ukladzie czeskim) i obwiednia pliku geometrii w torze LAZ
(`_resolve_laz_bbox`: `get_overall_bbox(..., target_crs="EPSG:2180")`).
Przeliczenia obwiedni miedzy ukladami PL i WGS84 (selekcja arkuszy
w `core/sheet_parser.py` i `core/geometry.py`, `_bbox_to_2180` wycinka dla
ukladow nieczeskich, dyspozycja krajow w CLI, obwiednia bboxa EPSG:2180
w ukladzie uslugi CORINE/SoilGrids — `transform/bbox.py::envelope_from_2180`)
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
landcover ──> providers, download (FileStorage), core, sources (l)
hydrology ──> providers (l), core (l), sources (l)
providers ──> sources, transform, transport, core, cache,
        auth (l), download (l)
sources ──> core, kartograf (l, __version__)
transport ──> transform, core, kartograf (l, __version__)
transform ──> core
cache ──> (nic wewnetrznego)
auth ──> (nic wewnetrznego)
core ──> (nic wewnetrznego)
exceptions ──> (lisc; krawedzie DO niego pominiete powyzej — importuja go
        kartograf, cli, core, sources, transform, transport, providers, download)
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
- `download` siega po `transform` i `transport` WYLACZNIE w
  `download/cutout.py` (wycinek PL, sekcja 4.3): przy imporcie
  `transform.crs` (`PinnedTransform`, `CONTENT_POLICY`, `WARP_MARGIN_PX`),
  leniwie `transform.crs.build_pinned_transform` (`prepare_pl_cutout`),
  `transport.mosaic` i `transform.raster` (`build_pl_cutout`) oraz
  `transport.mosaic.has_valid_pixels` (`run_pl_cutout`, kontrola
  `all_nodata`). `manager.py` i `storage.py` nie importuja zadnego z nich —
  `DownloadManager` pozostaje warstwa koordynacji arkuszy.
- `cli` nie buduje mozaiki ani warpu wycinka (robi to biblioteka, R3),
  a z `transform` bierze tylko `TransformError`. Jedyna krawedz
  `cli ──> transport` to leniwy import `transport.mosaic.has_valid_pixels`
  w `_warn_cz_all_nodata` (kontrola "wynik CZ w calosci nodata"; review
  N13 — przeniesienie jej do providera CZ, jak `all_nodata` w torze PL,
  to backlog).
- `transport ──> transform`: `transport/mosaic.py` owija zrodla mozaiki
  w VRT przez `transform.raster` (`vrt_xml`, `VRT_TYPES`; import na poziomie
  modulu). `transform` nie importuje `transport` — cyklu nie ma.
- `providers ──> download` jest leniwa i MUSI taka zostac (pakiet
  `download` importuje `providers` przy imporcie): walidacja opcji kampanii
  `download.campaigns.validate_campaign_args` w
  `SkorowidzLayersMixin.resolve_campaigns` (`providers/pl/skorowidz.py`)
  i w `GugikLazProvider.select_tiles` (`providers/pl/gugik_laz.py`).
- `hydrology` importuje wszystko leniwie: `providers.soilgrids` (warstwy
  gleb), `core.sheet_parser` (godlo -> bbox) i `sources.sidecar.emit_sidecar`
  (sidecar wyniku HSG).
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

```
kartograf/
├── __init__.py          # Public API (BBox, SheetParser, DownloadManager, providery, ...)
├── exceptions.py        # KartografError; ParseError; ValidationError
│                        # -> GridMismatchError(ValidationError; .off_grid) — niezgodna faza
│                        # siatki arkuszy wycinka; DownloadError(.godlo, .status_code)
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
│   ├── geometry.py         # Czytanie SHP/GPKG, find_sheets_for_geometry, get_overall_bbox
│   └── coverage.py         # Wypukle wielokaty: przeciecie, roznica, bufor (wybor kafli LAZ)
├── sources/             # Deskryptory zrodel jako dane (zero IO przy imporcie)
│   ├── descriptor.py    # SourceDescriptor (+ resolve_subdir), AccessChannel,
│   │                    # TransportKind, TileScheme, LicenseInfo, CountryProfile
│   ├── registry.py      # Rejestr PL/CZ/EU/GLOBAL: get_source, sources_for, get_country,
│   │                    # all_countries, vertical_crs_code, resolve_vertical_crs (rodzina ->
│   │                    # realizacja), parse_pl_uklad, horizontal_crs_for_godlo/_for_uklad
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
│   │                    # i get_with_retry (zapytania: skorowidz, WFS LAZ, TERYT BDOT10k,
│   │                    # CuzkClient.query) — jedyne miejsce retry (siec, 429, 5xx;
│   │                    # Retry-After): is_retryable, retry_wait, backoff_delay;
│   │                    # make_gugik_session, SessionPerThread (sesja per watek)
│   └── mosaic.py        # mosaic_and_crop — merge rastrow + przyciecie, propagacja nodata;
│                        # opcjonalnie crop na siatce zrodel i owijanie zrodel w VRT;
│                        # check_source_grid (fazy siatki -> GridMismatchError), has_valid_pixels
├── providers/           # Providery danych
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider, LandCoverProvider
│   ├── pl/              # GUGiK: gugik.py (NMT), gugik_nmpt.py, gugik_orto.py,
│   │                    # gugik_laz.py (select_tiles, select_all_intersecting), bdot10k.py,
│   │                    # skorowidz.py (rekordy GetFeatureInfo, wybor ADR-028,
│   │                    # SkorowidzLayersMixin: resolve_campaigns/download_record/
│   │                    # record_source; select_campaign_records, layer_upper_year,
│   │                    # coverage_hints/no_coverage_error),
│   │                    # wcs.py (GugikWcsMixin — URL GetCoverage dla NMT/NMPT/orto),
│   │                    # __init__.py (create_nmt_provider, nmt_vertical_crs)
│   ├── cuzk/            # CUZK: client.py (CuzkClient — silnik sterowany deskryptorem: ArcGIS
│   │                    # REST query/export_image + pliki openzu), sheets.py (SheetIndex/
│   │                    # SheetInfo — indeks SM5/TM33 z KladyMapovychListu, odsiewa
│   │                    # nadmiarowy wybor uslugi), dmr.py (CuzkDmrProvider — DMR 5G/4G,
│   │                    # opcjonalnie Bpv -> EVRF2007), __init__.py (create_dmr_provider —
│   │                    # jedyne miejsce czeskich domyslow)
│   ├── corine.py        # CORINE z Copernicus CLMS (+ fallback WMS PNG)
│   └── soilgrids.py     # SoilGrids z ISRIC (WCS)
├── cache/metadata.py    # MetadataCache — SQLite WAL, thread-safe; tabele record_cache,
│                        # campaigns_cache, teryt_cache (TTL 7 d, DEFAULT_TTL_SECONDS)
│                        # i sheet_cache (30 d, SHEET_TTL_SECONDS)
├── download/            # Pobieranie NMT/NMPT/Orto po godle + wycinek PL
│   ├── campaigns.py     # Kampanie GUGiK (ADR-030): CampaignRef, format z rekordu, verify_file_format
│   ├── links.py         # Dowiazanie sciezki standardowej (hardlink -> kopia, bez symlinkow, nigdy wstecz)
│   ├── cutout.py        # Wycinek PL --target-crs jako API (ADR-027): prepare/select/run/
│   │                    # download_pl_cutout — mozaika arkuszy + warp, sidecar
│   ├── laz.py           # Kafle LAZ jako API (ADR-029): download_laz_area/run_laz_download —
│   │                    # pula watkow, sidecar kafla, porazki w wyniku
│   ├── manager.py       # DownloadManager — koordynacja arkuszy (ThreadPoolExecutor), sidecary;
│   │                    # kampanie (campaigns=, min_year=), SheetFetch/last_sheet
│   │                    # download_sheets/expand_sheets (lista godel, porazki w last_result)
│   └── storage.py       # FileStorage — segmenty z szablonow rejestru (ADR-026);
│                        # prune_empty_dirs — sprzatanie pustych bbox/ po porazce
├── landcover/manager.py # LandCoverManager — dispatch do providerow pokrycia terenu
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
`{uklad}` i `{vcrs}`, a nie literalna nazwa katalogu. Konsument zewnetrzny
czytajacy to pole wprost dostanie szablon — swiadomy trade-off; poprawna droga
to `resolve_subdir()`.

| Klucz deskryptora | `storage_subdir` | `default_extension` |
|---|---|---|
| `pl.gugik.nmt_1m` | `nmt/pl_{uklad}_1m_{vcrs}` | `.asc` |
| `pl.gugik.nmt_5m` | `nmt/pl_{uklad}_5m_{vcrs}` | `.asc` |
| `pl.gugik.nmpt` | `nmpt/pl_{uklad}_1m_{vcrs}` | `.asc` |
| `pl.gugik.orto` | `orto/pl_{uklad}` (+ `_<wariant>` dla CIR/B-W, regula 5) | `.tif` |
| `pl.gugik.laz` | `laz/pl_{uklad}_{vcrs}` | `.laz` |
| `cz.cuzk.dmr5g` | `nmt/cz_dmr5g_{vcrs}` | `.tif` |
| `cz.cuzk.dmr4g` | `nmt/cz_dmr4g_{vcrs}` | `.tif` |
| `pl.gugik.bdot10k` | `None` | `.gpkg` |
| `eu.clms.corine` | `None` | `.tif` |
| `global.isric.soilgrids` | `None` | `.tif` |

`None` oznacza zrodlo obslugiwane przez `LandCoverManager`, ktory ma wlasna
konwencje nazw i wlasny domyslny `--output` (sekcja 4.8).

**`SourceDescriptor.resolve_subdir(*, uklad=None, vertical_crs=None) -> str`**
wypelnia szablon przez `str.replace`, a nie `str.format` — czesciowe
wypelnienie jest legalne. `vertical_crs` jest normalizowany do lowercase
(`"Bpv"` -> `"bpv"`). Podanie wymiaru, ktorego szablon nie ma, to no-op
(orto ignoruje `vertical_crs`). Zrodlo bez `storage_subdir` rzuca `ValueError`.
Pusty string (albo sam whitespace) w `uklad`/`vertical_crs` to
`ValidationError` — `None` znaczy "wypelnij pozniej", a pusty napis dawal
cichy segment `nmt/pl_1992_1m_` (review max zn. 7).

Kto wypelnia ktory placeholder:

| Placeholder | Kto wypelnia | Kiedy |
|---|---|---|
| `{vcrs}` | konstruktor `FileStorage(vertical_crs=)` albo jawne `resolve_subdir(vertical_crs=)` | raz, na starcie zadania — uklad pionowy jest wlasnoscia zadania, nie arkusza |
| `{uklad}` | `FileStorage` per identyfikator (`get_path`/`get_raw_path`/`exists`/`delete`/`ensure_directory`), regula ta sama co `parser_registry.path_parts`: kropki -> `2000`, reszta -> `1992` | przy budowie kazdej sciezki |
| `{uklad}` (jawnie) | tor LAZ: `LazTile.uklad` (`uklad_xy` kafla przez `parse_pl_uklad`; nieznany = kafel pominiety / `ValidationError`) przez `FileStorage.get_raw_path(..., uklad=)` — jedno zrodlo prawdy dla CLI i biblioteki (zn. 8, review max); wycinek PL (`prepare_pl_cutout`: `uklad="1992"` na stale — `--target-crs` z `--system 2000` jest odrzucane, a arkusz we wspolrzednych PL-2000 konczy budowe bledem, sekcja 4.3) | przed utworzeniem `FileStorage` / sciezki wycinka |

`FileStorage` waliduje wynik koncowy: segment, w ktorym po wypelnieniu zostala
klamra `{`, konczy sie `ValidationError` z nazwa brakujacego wymiaru
(`_ensure_resolved`). Cichy katalog `pl_{uklad}_1m_evrf2007` nigdy nie powstanie.

### 3.2 Schema sidecara `kartograf-meta/1`

Kazde udane pobranie przez CLI albo warstwe zarzadzajaca biblioteki
(`DownloadManager`, `LandCoverManager`, `download_pl_cutout`/`run_pl_cutout`,
`download_laz_area`/`run_laz_download`, `HSGCalculator`) zapisuje **dwa**
pliki: dane i `<plik>.meta.json` (zapis best-effort, wyjatki — sekcja 1).
Bezposrednie wywolanie providera sidecara nie pisze; DMR CZ z biblioteki
(`CuzkDmrProvider`) jest wiec bez sidecara — pisze go tylko CLI.

| Pole | Znaczenie |
|---|---|
| `dataset` | klucz deskryptora zrodla (np. `pl.gugik.nmt_1m`) |
| `country`, `product`, `provider` | kraj, produkt i nazwa dostawcy z deskryptora |
| `horizontal_crs` | faktyczny uklad poziomy pliku: arkusz PL-1992 `EPSG:2180`, arkusz PL-2000 `EPSG:2176`–`EPSG:2179` wedlug strefy godla, CZ natywnie `EPSG:5514`, kafel TM33 `EPSG:3045`; wycinek po `--target-crs` w ukladzie docelowym. Dla arkusza PL uklad z godla jest SPRAWDZANY wspolrzednymi pliku (`sources/sidecar.py::pl_sheet_horizontal_crs`): plik opublikowany przez GUGiK w innym ukladzie niz wskazuje godlo (E17, np. arkusze PL-2000 strefy 7 jak `7.125.11.19` w EPSG:2180) dostaje uklad PLIKU, deklaracja rekordu skorowidza zostaje w `extra.source.declared_crs`, logger `kartograf.sources.sidecar` ostrzega, a CLI drukuje `Warning: N arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: ...` (kod bez zmian; segment katalogu nadal wg godla, ADR-026) |
| `vertical_crs` | kod realizacji ukladu pionowego: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007); `null` gdy produkt nie ma pionu (orto) |
| `vertical_source` | `native` / `ellipsoidal` / `server` (z `AccessChannel`) |
| `resolution` | rozdzielczosc z deskryptora (`1m`/`5m`/`2m`) albo `null` |
| `nodata` | wartosc pustego piksela: dla `.asc` czytana automatycznie z naglowka (`read_asc_nodata`), w torze CZ podawana przez CLI z tagu GeoTIFF (`_read_tif_nodata`; w trybie bbox z fallbackiem `CUZK_NODATA`), dla wycinka PL stala `-9999.0`, dla wyniku HSG `0`; `null` gdy zadna z tych drog nie ma zastosowania (np. orto) |
| `request` | zadanie, ktore dalo TEN plik: `sheet` (godlo), `bbox` + `bbox_crs` w ukladzie wyniku albo `teryt`; dla plikow PL (kampanie, ADR-030) `campaigns` (`newest`/`all`, zawsze) i `min_year` (tylko gdy podany; `request` opisuje POBRANIE, ktore dalo plik, a nie jego ostatnie uzycie — reuzycia ida do `extra.parent_requests`); LAZ: `year`/`min_density`/`min_year` gdy podane oraz `campaigns` tylko dla `all`; oryginalne zadanie niesie `extra.parent_request` (3.4), rekord skorowidza PL niesie `extra.source` |
| `license` | `{id, attribution, url}` z deskryptora |
| `downloaded_at`, `kartograf_version` | znacznik czasu UTC (ISO 8601, sekundy) i wersja pakietu z `kartograf/_version.py::build_version()`: wydanie = samo `__version__`; wersja rozwojowa (`dev`) = `<__version__>+<krotki SHA>` commita, z ktorego zaimportowano pakiet, z sufiksem `.dirty`, gdy sledzone pliki katalogu `kartograf/` maja niezacommitowane zmiany (docs/testy sie nie licza); gdy git jest niedostepny albo pakiet nie pochodzi z repozytorium, w ktorym lezy (`os.path.samefile`), samo `__version__`. Ta sama wartosc w `kartograf --version`; `User-Agent` HTTP niesie samo `__version__` |
| `transform` | slownik osi (`horizontal`/`vertical`) z opisem uzytej operacji w formacie `pinned: <opis> (<dokladnosc> m)`; os bez przeliczenia nie ma klucza, a bez zadnego przeliczenia cale pole to `null` |
| `extra` | `parent_request` (obszar) / `parent_requests` (kolejne zadania wykorzystujace ten sam arkusz); LAZ ma `tile_sheet`/`year`/`nominal_density`/`url`; SM5 ma `mapname`/`cz_share` (udzial arkusza w terytorium CZ, pole `PODIL` CUZK); arkusze NMT/NMPT/orto PL maja `source` (klucze w tabeli nizej); wycinek PL: `parent_request`, `missing_sheets`, `sheet_sources`, `off_grid_sheets`, `all_nodata`, `unverified_sheets` — znaczenie i warunki zapisu w akapicie "Wycinek PL w sidecarze" nizej (jedyne pelne zestawienie); CORINE z podgladu WMS: `fallback: "wms_png"` i `note` (`landcover/manager.py`, sekcja 4.8); wynik HSG: `derived: "hsg"`, `source_layers`, `depth`, `stat`, `classes` (sekcja 4.8); plik kampanii (ADR-030): `campaign` = `{id, date, survey_work_id, source, full_sheet, pzgik_date}` obok `source`; sidecar sciezki standardowej: `link` (`hardlink`/`copy`) i `link_target` (sciezka celu wzgledem dowiazania; jedyne zrodlo celu) |
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
| `color` | tylko orto: wariant `RGB`/`CIR`/`B/W` |

**Stare sidecary i wpisy cache (sprzed ADR-031).** Wpis `record_cache`/
`campaigns_cache` bez nowych kluczy jest chybieniem cache (skorowidz
odpytywany ponownie, wpis nadpisany). Sidecar kampanii bez
`extra.campaign.pzgik_date` nie daje klucza dowiazania z sidecara —
uzywane jest dolne oszacowanie z nazwy katalogu kampanii (jak przy braku
sidecara). Wpisy `extra.sheet_sources` bez `sheet` nie licza sie jako
niepelne arkusze przy pominieciu wycinka; arkusz ze starym sidecarem
daje w nowym wycinku `null` w polach o zmienionej nazwie. Ostrzezenie E17
nie powstaje dla sidecara bez `request.sheet`. Odswiezenie: `--force`.

Kanal, z ktorego brany jest `horizontal_crs`/`vertical_crs_options`/
`vertical_source`, wybiera `build_metadata`: albo jawnie po `capability=`,
albo domyslnie po ksztalcie zadania (`bbox` w `request` -> kanal z
`bbox_raster`/`bbox_vector`, inaczej pierwszy pasujacy). Nazwa rodziny ukladu
pionowego jest mapowana na realizacje krajowa, jesli kanal deklaruje wlasnie
ja (`resolve_vertical_crs`: `EPSG:5621` -> `EPSG:9651` dla PL).

**Wycinek PL (`--target-crs`) w sidecarze.** Rekord budowany jest jawnie
z `capability="sheet_files"`, a nie `"bbox_raster"` — i jest to **swiadome
odstepstwo od litery specu**: dane wycinka pochodza z arkuszy OpenData, kanal
`bbox_raster` nie istnieje dla NMT 5 m, a dla 1 m deklaruje wylacznie KRON86
(WCS EVRF2007 wycofany przez GUGiK). Deklaracja `bbox_raster` opisywalaby
kanal, ktorym te dane nie przyszly. Rekord sklada biblioteka
(`download/cutout.py::write_pl_cutout_sidecar`, od 2026-09-28 — wczesniej
CLI): po zbudowaniu nadpisuje `horizontal_crs` na uklad docelowy i ustawia
`transform = {"horizontal": "pinned: <opis> (<dokladnosc> m)"}`; dla
`--target-crs EPSG:2180` (crop na siatce arkuszy, bez warpa) `transform` to
`null`. `request` = `{"bbox": <bbox_target>, "bbox_crs": <uklad docelowy>}`
— obwiednia zadania po przeliczeniu do ukladu docelowego, nie oryginal.

`extra` wycinka — pelna lista kluczy (to jest jedyne kanoniczne zestawienie;
sekcje 4.3 i ADR-027 odsylaja tutaj). Kazdy klucz trafia do sidecara TYLKO,
gdy wartosc jest niepusta/prawdziwa; bez zadnego z nich `extra` to `{}`:

| Klucz | Zawartosc | Pole `PlCutoutResult` |
|---|---|---|
| `parent_request` | oryginalne zadanie (sekcja 3.4); tylko gdy przekazane `parent_request=` | — |
| `missing_sheets` | lista godel bez danych GUGiK (`NoCoverageError`, R5) — w ich miejscu nodata | `missing_sheets` |
| `sheet_sources` | lista `{sheet, url, layer, acquisition_date, full_sheet}` z `extra.source` sidecarow arkuszy mozaiki (arkusz bez sidecara/`source`: `null` poza `sheet`); `full_sheet: false` = niepelna najnowsza kampania (E13) | `partial_sheets` (godla z `full_sheet: false`) |
| `off_grid_sheets` | godla o innej fazie siatki, reprojektowane osobno (W1) | `off_grid_sheets` |
| `all_nodata` | `true`, gdy wycinek nie ma ani jednego waznego piksela mimo pobranych arkuszy (E15) | `all_nodata` |
| `unverified_sheets` | `{godlo: blad}` — arkusze z lokalnej kampanii bez sprawdzenia nowszej, bo skorowidz byl niedostepny (I-1, errata 5 ADR-030) | `unverified` |

Pominiety istniejacy wycinek (`skipped_pl_cutout`, bez czytania rastra)
odtwarza z tych kluczy WSZYSTKIE pola z ostatniej kolumny, a CLI powtarza
odpowiadajace im `Warning:`/`Info:` z dopiskiem ` (z sidecara istniejacego
wycinka)`.

**Kampanie (ADR-030).** Sidecar pliku w `kampanie/` jest OBOWIAZKOWY:
`emit_sidecar(..., required=True)` zapisuje go atomowo, a porazka zapisu
rzuca `DownloadError` (manager usuwa plik danych, kampania jest porazka,
dowiazanie nie jest przestawiane). Pozostale sidecary (arkusz toru plain,
wycinek, LAZ, CZ, landcover, HSG) zostaja best-effort. Sidecar sciezki standardowej
(dowiazania) to ZWYKLY plik — kopia sidecara celu z dopisanym `extra.link`
i `extra.link_target` (zapis `tmp` + `os.replace`, nigdy "przez" symlink
sidecara pozostawiony przez uzytkownika; best-effort). To JEDYNE zrodlo celu
dowiazania (hardlink nie niesie wskazania): brak sidecara standardowego =
sciezka nieznana.

### 3.3 Kanoniczny uklad `data/`

```
data/
├── nmt/
│   ├── pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # DOWIAZANIE (regula 6)
│   ├── pl_1992_1m_evrf2007/kampanie/2022-05-10_83233/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # prawdziwy plik
│   ├── pl_1992_1m_kron86/...
│   ├── pl_1992_5m_evrf2007/...              # 5m tylko EVRF2007 (regula istniejaca)
│   ├── pl_1992_1m_evrf2007/bbox/<coords>.tif    # wycinek --target-crs (sekcja 4.3)
│   ├── pl_2000_1m_evrf2007/6/179/12/20/6.179.12.20.asc
│   ├── cz_dmr5g_bpv/302/5550/302_5550.tif
│   ├── cz_dmr5g_bpv/bbox/<coords>.tif       # wycinki bbox CZ
│   ├── cz_dmr5g_evrf2007/...
│   └── cz_dmr4g_bpv/CTES/96/CTES96.tif
├── nmpt/pl_1992_1m_evrf2007/...             # (+ _kron86, + pl_2000_...)
├── orto/pl_1992/...                         # bez ukladu pionowego
├── orto/pl_1992_cir/...                     # wariant CIR (B/W: pl_<uklad>_bw), E12
├── laz/pl_2000_evrf2007/...                 # poziomy per kafel (uklad_xy), pionowy z flagi
└── landcover/...                            # bez zmian (wlasny default --output)
```

**Reguly segmentow:**

1. Segment ma postac `<kraj>_<uklad>[_<wariant>][_<vcrs>]`, wszystkie wartosci
   lowercase. Uklad PL: `1992` / `2000`. Uklad pionowy: `kron86` /
   `evrf2007` / `bpv`. CZ nie niesie ukladu poziomego, bo nazwa datasetu
   (`dmr5g`/`dmr4g`) wyznacza go 1:1 (natywnie zawsze EPSG:5514).
2. Hierarchia wewnatrz segmentu jest bez zmian — `parser_registry.path_parts`:
   PL-1992 `N-34-130-D-d-2-4` -> `N-34/130/D/d/2/4`, PL-2000 `6.179.12.20` ->
   `6/179/12/20`, TM33 `302_5550` -> `302/5550`, SM5 `CTES96` -> `CTES/96`.
3. Podkatalog `bbox/` wewnatrz segmentu trzyma wycinki z trybu
   `--bbox`/`--geometry`: `<coords><ext>`, gdzie wspolrzedne sa **w ukladzie
   WYNIKU** (po `--target-crs`), formatowane `%.10g` i sklejane `_`.
   Nazwa niesie ZADANIE, nie dokladny zasieg rastra: wycinek PL w EPSG:2180
   lezy na siatce arkuszy i siega do < 1 px dalej, a siatka warpa
   (`transform/raster.py::warp_to_grid`, wspolny dla PL i CZ) ma calkowita liczbe pikseli
   liczona od naroznika NW, wiec jej krawedz E i S moze odbiegac o do 0,5 px
   (sekcja 4.3).
   Konwencja wspolna dla PL i CZ, ale nie kazde zadanie obszarowe daje
   wycinek: CZ zawsze (`exportImage`), PL **tylko z `--target-crs`** —
   bez tej flagi zadanie PL zapisuje arkusze w hierarchii godel
   (sekcja 4.2 vs 4.3).
4. Rozdzielczosc wchodzi do segmentu tylko tam, gdzie jest parametrem API
   (NMT/NMPT). Nie ma jej dla CZ (`dmr5g` to z definicji 2 m, `dmr4g` 5 m)
   ani dla orto/LAZ (brak takiego parametru).
5. `<wariant>` rozroznia pliki tego samego godla i ukladu, ktore nie sa tym
   samym produktem (E12, 2026-10-06). Wariant deklaruje tylko orto
   (`storage_variant`; w `BaseProvider` domyslnie `None`): RGB (domyslny)
   bez sufiksu w `orto/pl_<uklad>/` (bez migracji), CIR w
   `orto/pl_<uklad>_cir/`, B/W w `orto/pl_<uklad>_bw/`. Wariant pochodzi
   z `provider.storage_variant` (`GugikOrtoProvider(color=...)`) i trafia do
   `FileStorage(variant=...)`; bez niego skip zwracal po cichu plik RGB na
   zadanie CIR.

6. **Kampanie (ADR-030, errata 1-5).** Prawdziwe pliki NMT/NMPT/orto PL
   leza WYLACZNIE w `<segment>/kampanie/<data>_<id>/<hierarchia godla>/
   <godlo>.<ext>` (+ `.meta.json`), takze dla `newest`; sciezka standardowa
   `<segment>/<hierarchia>/<godlo>.<ext>` jest dowiazaniem do najnowszej
   LOKALNEJ kampanii (takze niepelnej). `<data>` = `aktualnosc` rekordu
   (RRRR-MM-DD), `<id>` = pierwszy segment liczbowy nazwy pliku w URL
   (`83233_1744736_<godlo>.asc` -> `83233`), inaczej `u` + 8 znakow hex
   `sha1(URL)`. Segment ADR-026 bez zmian (takze `orto/pl_1992_cir`).
   Metoda dowiazania (errata 4): 1) hardlink, 2) kopia + `Warning:`
   (`extra.link` = `hardlink`/`copy`); symlinkow nie tworzymy (nieczytelne
   dla klientow Windows przez SMB, limit dlugosci celu na udziale); kampania
   lezy zawsze w tym samym segmencie co sciezka standardowa (ten sam system
   plikow). Podmiana atomowa (plik tymczasowy + `os.replace`; istniejacy
   symlink sprzed errata 4 = sciezka nieznana, zastepowany); dowiazanie
   nigdy nie cofa sie na kampanie starsza od biezacego celu (klucz celu
   z jego sidecara, a gdy nieczytelny — z nazwy katalogu). Kontrola
   istnienia: cel z `extra.link_target` sidecara standardowego (`samefile`
   dla hardlinku, rozmiar + mtime dla kopii); usuniety katalog kampanii =
   brak pliku. `FileStorage.get_campaign_path` buduje sciezke kampanii,
   `list_files()` domyslnie pomija `kampanie/` (`campaigns=True` = tylko
   `kampanie/`). W 0.7.0 nic nie skanuje `kampanie/` w poszukiwaniu
   lokalnych kampanii: cel dowiazania zna tylko sidecar standardowy, a
   kampanie do pobrania wyznacza skorowidz. CZ, LAZ, BDOT10k i land cover
   nie uzywaja `kampanie/`.
   Kopiowanie `data/`: `rsync -aH`/`cp -a` (bez zachowania hardlinkow
   powstaje duplikat).

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
Arkusz juz pobrany z sidecarem zachowuje oryginalny `parent_request`,
a nowe zadania trafiaja do deduplikowanej listy `extra.parent_requests`
(bez tworzenia sidecara dla starego pliku bez niego). To jest klucz grupowania:
po nim konsument (Hydrograf, przyszly `find_downloaded`) sklada w calosc
pliki jednego zadania, takze te lezace po obu stronach granicy, ktore
Kartograf swiadomie zostawia rozdzielone (sekcja 1). Slownik jest wspoldzielony
przez referencje miedzy sidecarami zadania i **nie moze byc mutowany** po
utworzeniu.

---

## 4. Przeplywy per produkt

**Migracja 0.7.0-dev -> 0.7.0 (ADR-030, BREAKING):**

| Stan | Zachowanie |
|---|---|
| zwykly plik NMT/NMPT/orto w sciezce standardowej (stary uklad bez `kampanie/`) | traktowany jako nieznany (brak migracji); przy pierwszym `newest` kampania jest pobierana do `kampanie/`, a zwykly plik (z sidecarem) ZASTEPOWANY dowiazaniem |
| dowiazanie (hardlink/kopia) w sciezce standardowej | cel = najnowsza lokalna kampania (z `extra.link_target`); kolejne `newest`/`all` przestawiaja je tylko na kampanie o kluczu `(aktualnosc, dt_pzgik, url)` scisle wiekszym niz klucz biezacego celu (ten sam cel albo klucz rowny/wiekszy = bez zmian; klucz z sidecara celu, a gdy nieczytelny z nazwy katalogu `<data>_<id>`) |
| dowiazanie, ktorego `extra.link_target` nie istnieje (katalog kampanii usuniety) albo bez sidecara standardowego | brak pliku — pobranie od nowa |
| symlink w sciezce standardowej (dane sprzed errata 4) | nieznany — `newest` zastepuje go hardlinkiem (bez kodu zgodnosci) |

### 4.1 Godlo PL (NMT/NMPT/Orto)

`SheetParser` waliduje godlo i normalizuje wielkosc liter (zer wiodacych NIE
usuwa: `M-33-036-...` i `M-33-36-...` to dla `FileStorage` dwie rozne
sciezki; forma kanoniczna, bez zer, to ta z `find_sheets_for_bbox`); godlo
PL-1992 grubsze niz 1:10000 rozwija sie do arkuszy 1:10000
(`download_hierarchy`), godlo PL-2000 pobierane jest bezposrednio. Dla
kazdego arkusza pyta WMS skorowidz (`GetFeatureInfo`, warstwy wykryte lazy
przez `GetCapabilities` — ADR-020). `providers/pl/skorowidz.py` parsuje
pelne rekordy; filtruje cale godlo, zgodny uklad i rozdzielczosc
(dla orto tez domyslnie RGB), wybiera (strategia `newest`) rekord z najnowsza data w pierwszej
warstwie z dopasowaniem; remis rozstrzyga `dt_pzgik`, URL. Brak zgodnego rekordu
po poprawnych odpowiedziach warstw = `NoCoverageError`, np. dla PL-2000
1:10000 z samymi potomkami podpowiedz `--scale 1:2000`. Awaria warstwy,
raport OGC albo nieoczekiwany szablon = `DownloadError`, nie cichy fallback
do starszej kampanii. Zapytania i pobrania maja do 3 prob z backoffem
(ponawiane: siec, 429, 5xx; inne 4xx koncza przy pierwszej probie)
oraz sesje keep-alive per watek. `MetadataCache` (SQLite WAL, TTL 7 dni)
zapisuje rekord `{"source": ...}` lub potwierdzony `{"no_coverage": true}`;
CLI podpina cache w torach PL i CZ; `--force` otwiera go w obu w trybie
`MetadataCache(refresh=True)` — odczyt pominiety, swiezy rekord zapisany
(E14) — biblioteka przyjmuje `cache=`; `kartograf cache stats` pokazuje `Record entries`.
`DownloadManager` pisze sidecar po kazdym udanym arkuszu; arkusz ASC GUGiK
nie niesie CRS (rasterio: `crs=None`), wiec jedynym nosnikiem ukladu jest
sidecar. Ponowne uruchomienie rozwiazuje najnowszy rekord arkusza (cache 7 d;
po jego wygasnieciu zapytanie do skorowidza) i pobiera tylko brakujace
kampanie — kampania juz lokalna jest pomijana (`SheetFetch.skipped`). `--target-crs` w trybie godlowym jest
**odrzucane** (kod 1) — godlo PL dostarcza arkusz natywny 1:1.

**Niepelna najnowsza kampania (E13).** Rekord z `full_sheet: false`
(skorowidz deklaruje arkusz nie w calosci wypelniony) nadal wygrywa, gdy
jest najnowszy (ADR-028 bez preferencji pelnego arkusza); fakt trafia do
`extra.source.full_sheet`, a CLI czyta go z sidecarow wyniku i drukuje
`Warning: najnowsza kampania GUGiK jest niepelna dla N arkuszy (...)` na
stderr w torze godla, listy i hierarchii — takze dla arkuszy pominietych
jako istniejace (kod bez zmian). Wycinek: sekcja 4.3 (`partial_sheets`).

**Kampanie (ADR-030, errata 1-5).** `--campaigns {newest,all}`
(domyslnie `newest`) i `--min-year RRRR` (granica na roku `aktualnosc`,
nie `dt_pzgik`; 1900..2100) steruja wyborem rekordow.
`GugikProvider.resolve_campaigns` zwraca `CampaignRef` (`download/campaigns.py`):
`newest` = jeden rekord wg ADR-028 (bez zmian), `all` = kazdy rekord po
twardym filtrze ADR-028 ze WSZYSTKICH warstw (`select_campaign_records`),
bez limitu liczby kampanii (`logger.info` z liczba). Rok z nazwy warstwy
(`layer_upper_year`) sluzy wylacznie do pominiecia zapytania i tylko w
`all` (warstwa `Starsze` zawsze odpytywana); warstwa spoza `LAYER_PATTERN`
nie jest odpytywana, nazwa z rodziny produktu (`LAYER_FAMILY`) daje
`logger.warning`. Rekord bez ustalonego roku nie spelnia `--min-year`
(`all`: pominiety; `newest`: `NoCoverageError` "starsza niz min_year" z data
najnowszej kampanii). `MetadataCache` ma tabele `campaigns_cache` (klucz jak
`record_cache`, TTL 7 d, `--min-year` poza kluczem; skan czesciowy obsluguje
tylko granice >= granicy skanu), `kartograf cache stats` drukuje
`Campaign entries`. `DownloadManager(campaigns=, min_year=)` pobiera kazda
brakujaca kampanie (`GugikProvider.download_record`; plik w `kampanie/`,
`record_source` -> `extra.source`), po zebraniu kampanii przestawia
dowiazanie RAZ na arkusz (deduplikacja godel; nigdy wstecz) i zwraca
`SheetFetch(godlo, path, skipped, downloaded, reused, link, unverified)` w
`DownloadManager.last_sheet`. `DownloadResult` (`last_result` listy
i hierarchii) niesie `succeeded`, `failed`, `skipped`, `no_coverage`
(podzbior `failed`: brak danych u zrodla), `no_coverage_hints` (godlo ->
`NoCoverageError.hints`, tylko arkusze z podpowiedzia), `campaign_files`,
`reused_campaign_files` (kampanie juz lokalne per arkusz), `copied`
(arkusze, ktorych sciezka standardowa jest KOPIA) i `unverified` (ponizej).
Pelna lista pol: docstringi `SheetFetch`/`DownloadResult` w
`download/manager.py`. Plik: format z pola
`format` rekordu (nie z URL; brak pola — format domyslny produktu),
rozszerzenie zawsze kanoniczne (`.asc`/`.tif`; rekord 72675 z URL `.xyz` to
AAIGrid, zwykla kampania `.asc`), po pobraniu `verify_file_format`
(naglowek AAIGrid / sygnatura TIFF); nieznany format albo niezgodna tresc
= `DownloadError` kampanii z nazwa formatu, plik usuniety. Blad pobrania
podaje nazwe pliku z URL (`84183_1852496_N-34-139-C-a-3-1.asc (OpenData):
HTTP 404`), co w `all` rozroznia kampanie. Porazki: kampania (w tym
niepoprawna `aktualnosc` rekordu w `all`, brak sidecara, porazka
weryfikacji) = porazka tej kampanii — pozostale sa pobierane, dowiazanie
idzie na najnowsza poprawna, ale arkusz konczy sie porazka (kod 1);
porazka samego dowiazania (nawet kopii) = porazka arkusza (lista idzie
dalej takze przy `--workers 1`, pobrane kampanie zostaja). Wyscig bez
blokad: rownolegle wywolania na tej samej sciezce (procesy lub watki
biblioteki) moga chwilowo zostawic dowiazanie na starszej kampanii;
kolejne `newest`/`all` je naprawia, pliki w `kampanie/` sa nietkniete.
Przy metodzie `copy` CLI drukuje `Warning: hardlink niedostepny na tym
systemie plikow — sciezka standardowa jest KOPIA najnowszej kampanii dla N
arkuszy (<godla do 10>) (extra.link=copy)`; podsumowanie `all` (bez `-q`):
`Downloaded <n> campaign files for <m> sheets to <dir> (<k> already
existed)`. Pojedyncze godlo drukuje `Skipped <godlo> - already exists at
<sciezka>` (zamiast `Downloaded to`) tylko, gdy `manager.last_sheet.skipped`.

Awaria skorowidza przy `newest` (I-1, errata 5 ADR-030; wycinek `--target-crs` tez: `PlCutoutResult.unverified`, sidecar `extra.unverified_sheets` `{godlo: blad}`, `Warning:` jak dla listy): gdy `resolve_campaigns` konczy sie
bledem TRANSPORTU (`DownloadError` z `status_code` 429/5xx albo bez kodu,
ale z przyczyna `requests.RequestException` — siec/timeout; NIE
`NoCoverageError`, inne 4xx ani raport OGC/zly szablon), a sciezka
standardowa wskazuje istniejaca lokalna kampanie (`linked_campaign`)
i `skip_existing`, manager NIE zglasza porazki: `logger.warning` i
`SheetFetch(skipped=True, reused=(<kampania>,), unverified=<tresc bledu>)`,
dowiazanie bez zmian. Lista/hierarchia: arkusz w `skipped`, a
`DownloadResult.unverified` (godlo -> tresc bledu). CLI: `Warning: <godlo>:
skorowidz GUGiK niedostepny — uzyto lokalnej kampanii bez sprawdzenia
nowszej (<blad>)` (pojedyncze godlo) albo `Warning: skorowidz GUGiK
niedostepny — dla N arkuszy uzyto lokalnej kampanii bez sprawdzenia nowszej
(<godla do 10>) (<pierwszy blad>)` (lista), stderr takze z `-q`, kod bez
zmian. `all`, `--min-year`, `--force` i brak lokalnej kampanii (takze
dowiazanie z usunieta kampania docelowa) — blad jak dotad. Biblioteka bez `MetadataCache` pyta
skorowidz przy KAZDYM `download_sheet` (takze arkusza juz pobranego);
przekazanie cache providerowi ogranicza to do raz na 7 dni.

Wynik: `data/nmt/pl_1992_1m_evrf2007/kampanie/<data>_<id>/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
(+ `.meta.json`) i dowiazanie `data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`;
dla NMPT `data/nmpt/pl_1992_1m_evrf2007/...`, dla orto
`data/orto/pl_1992/...`.

### 4.2 Bbox / geometria PL bez `--target-crs`

Bbox trafia do `_dispatch_area`, ktore rozstrzyga kraje (sekcja 4.6), a czesc
polska idzie do `_download_pl_bbox`. `find_sheets_for_bbox` (czysta matematyka
siatki, bez zapytan sieciowych — ADR-010) daje liste godel 1:10000, ktore
pobiera `DownloadManager` rownolegle. W trybie `--geometry` arkusze wyznacza
sama geometria per obiekt (`find_sheets_for_geometry`), nie jej obwiednia.
Sidecar pobranego arkusza dostaje `extra.parent_request` i `extra.source`
(URL, warstwa, data, rozdzielczosc). Przy ponownym wykorzystaniu arkusza
sidecar zachowuje oryginalne zadanie, a nowy wpis trafia do
`extra.parent_requests`. Tryb listy (takze hierarchia godla) probuje
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

Opcje kampanii (`--campaigns`, `--min-year`, sekcja 4.1) dzialaja tu per
arkusz; podsumowanie `all` liczy pliki kampanii, nie arkusze. Arkusz, ktorego
najnowsza kampania jest starsza od `--min-year`, to `NoCoverageError`
(status `no_coverage`, `Warning:` R5).

**WCS (`download_bbox`) — tylko biblioteka, tylko NMT/NMPT 1 m.** CLI nie
uzywa WCS dla bboxa PL (ADR-003 czesciowo zastapiony przez ADR-027): zostal
on w `DownloadManager.download_bbox`/`GugikProvider.download_bbox` (GeoTIFF).
Dla 5 m WCS nie istnieje (`ValueError`). Dla NMT 1 m dziala
**wylacznie** `vertical_crs="KRON86"`: endpoint EVRF2007
(`DigitalTerrainModelFormatTIFFEVRF2007`) zwraca HTTP 404 od 2026-08,
wiec deskryptor `pl.gugik.nmt_1m` deklaruje kanal `bbox_raster` tylko dla
`EPSG:9650`, a `GugikProvider.download_bbox` pod EVRF2007 konczy sie
`ValidationError` przed wyjsciem w siec
(`GugikProvider.WITHDRAWN_WCS_VERTICAL_CRS`; `GugikNmptProvider` ma te
krotke pusta — WCS NMPT nie jest objety). Wysokosci EVRF2007 z obszaru:
tryb listy powyzej albo jeden GeoTIFF z arkuszy (sekcja 4.3).

Wynik: **wiele plikow** — lista arkuszy w segmencie jak w 4.1 (dowiazania do
`kampanie/`; przy `all` dodatkowo kazda kampania). To jest
asymetria wzgledem CZ, gdzie bbox daje jeden wycinek.

### 4.3 Bbox / geometria PL z `--target-crs` (ADR-027)

Nowosc 0.7.0, produkt `nmt`, tryby `--bbox` i `--geometry`: wynik to JEDEN
GeoTIFF zamiast listy arkuszy. Od 2026-09-28 (R3) caly tor zyje w bibliotece
— `kartograf/download/cutout.py`, eksport w `kartograf`:

- `download_pl_cutout(bbox, target_crs, *, output_dir, resolution,
  vertical_crs, geometry, layer, scale, max_workers, force, on_progress,
  parent_request, cache=None) -> PlCutoutResult` — fabryka NMT
  z opcjonalnym cache rekordow (pominietym przy `force`), `prepare`,
  skrot "plik istnieje", `select`, `run`.
- te same kroki osobno z wlasnym providerem albo `FileStorage`:
  `prepare_pl_cutout` -> `PlCutout` (zero sieci) ->
  `select_pl_cutout_sheets` -> `PlCutoutSheets` (zero sieci) ->
  `run_pl_cutout` -> `PlCutoutResult` (`path`, `skipped`, `sheet_paths`,
  `missing_sheets`, `off_grid_sheets`, `all_nodata`, `partial_sheets`,
  `unverified`; zwiazek z kluczami sidecara — tabela w sekcji 3.2).

CLI jest nakladka: `_download_pl_bbox`/`_download_pl_geometry` wolaja
`_download_pl_cutout` (`cli/download_cmd.py`), ktore wstrzykuje providera
i `FileStorage` z `_create_provider_and_storage`, wypisuje komunikaty
(`Found N sheets`, `Info:`, `Warning:`, `Downloaded to`) i tlumaczy wyjatki
na kod 1 z komunikatem, bez tracebacku: z `prepare_pl_cutout` —
`TransformError` (z remedium, gdy jest) i `ValidationError`, z
`select_pl_cutout_sheets` — `ValidationError`, a wokol `run_pl_cutout`
(pobranie i budowa) — KAZDY `Exception`. Wyjatek wyciekajacy poza petle
krajow `_dispatch_area` zlamalby kontrakt czesciowego sukcesu (ADR-023
pkt 4-5). Inny wyjatek przygotowania albo selekcji (przy wejsciu
zwalidowanym przez CLI nie wystepuje — tylko przy bledzie w kodzie) trafia
do bariery `main()` (`cli/commands.py`): `KartografError` -> `Error:
<komunikat>`, kazdy inny -> `Error: <Typ>: <komunikat>` z podpowiedzia
`KARTOGRAF_DEBUG=1` (z ta zmienna — pelny traceback); zawsze kod 1, ale
petla krajow jest wtedy przerwana, wiec pod `--country auto` sukces
drugiego kraju nie daje juz kodu 0. Biblioteka nie ma `print` ani argparse.

1. **Fail-fast przed siecia** (`prepare_pl_cutout`). `ValidationError` na
   uklad docelowy spoza `SUPPORTED_TARGET_CRS` (`EPSG:2180`, `EPSG:5514`,
   `EPSG:3045` — ta sama krotka ogranicza `choices` flagi CLI), rozdzielczosc
   spoza 1m/5m, pion spoza EVRF2007/KRON86 i 5m z KRON86 (`prepare_pl_cutout`
   przyjmuje pion FAKTYCZNY; korekte 5m => EVRF2007 robi `download_pl_cutout`
   przez fabryke providera, a CLI juz w `_resolve_pl_sentinels` z `Info:` na
   stderr — regula zyje w jednym miejscu, `providers.pl.nmt_vertical_crs`). Bbox trafia do EPSG:2180 (uklady czeskie
   przypieta operacja `bbox_to_crs`, pozostale domyslnym transformerem, jak
   w calym przeplywie PL), po czym dla pary `EPSG:2180 -> target_crs`
   budowana jest operacja przypieta (polityka `min_accuracy_m=1.0`, bez
   siatek z sieci, probe w srodku zadania); brak bezpiecznej operacji =
   `TransformError` z remedium, zanim cokolwiek pojdzie w siec. Skrot "plik
   juz istnieje" (bez `force`) wraca bez sieci: w CLI (`Skipped - already
   exists`) i w `download_pl_cutout` jeszcze przed selekcja arkuszy,
   w `run_pl_cutout` na wejsciu — zawsze jako
   `PlCutoutResult(skipped=True)` w bibliotece. `run_pl_cutout` sprawdza
   jednak PRZED tym skrotem wstrzyknietego providera: jego pion
   i rozdzielczosc musza byc rowne wycinkowi, inaczej `ValidationError` —
   arkusze trafilyby do cudzego segmentu wspolnego cache (np. wysokosci
   KRON86 do `..._evrf2007`), a kolejne przebiegi uzylyby ich bez
   ostrzezenia. Wstrzyknieta `storage` NIE jest walidowana (backlog) — musi
   miec te same `resolution` i `vertical_crs` co wycinek. Bbox w EPSG:4326
   staje sie wycinkiem obejmujacym jego OBWIEDNIE w EPSG:2180; przy 14°E
   zbieznosc poludnikow wzgledem 19°E powieksza waski pas — wycinek obejmuje
   wtedy wyraznie wiecej arkuszy niz tryb listy (pomiar na zywo:
   `docs/research/2026-09-29-live-e2e-i-audyt-docs/L5-pogranicze-de-report.md`),
   co na pograniczu daje wiecej arkuszy w `missing_sheets`.
2. **Zapas po stronie zrodla** (`PlCutout.bbox_source_2180`). Przy warpie
   obwiednia celu (`bbox_target`) wraca do EPSG:2180 — obrot ukladu
   docelowego robi ja wieksza niz zadanie — i rosnie o `WARP_MARGIN_PX = 4`
   piksele (halo interpolatora bilinear); lustro `_native_request_bbox` toru
   CZ. Dla `EPSG:2180` zapasu nie ma. Ten bbox — nie zadanie uzytkownika —
   steruje cropem mozaiki i selekcja arkuszy. Zapas nie jest ostroznoscia na
   wyrost: bez niego zmierzony wycinek do EPSG:5514 mial pas pikseli nodata
   na krawedziach, a w trybie `--geometry` bez sumy godel (krok 3) — okolo
   polowy pikseli (pomiar:
   `docs/research/2026-08-28-uklad-data-target-crs-pl/`).
3. **Selekcja arkuszy** (`select_pl_cutout_sheets`, zero sieci). Tryb bbox:
   `find_sheets_for_bbox` z obwiedni zrodla powiekszonej o **1 piksel** —
   crop jest przyciagany NA ZEWNATRZ do siatki arkuszy (krok 5), wiec bez
   tego zapasu skrajny piksel mogl wpasc w arkusz spoza listy. Tryb
   `--geometry`: arkusze per obiekt (`find_sheets_for_geometry`), a przy
   warpie SUMA z arkuszami tej samej obwiedni z zapasem 1 px (R-01; bez
   sumy krawedzie wyniku bylyby ramka nodata — krok 2). `--geometry`
   z `EPSG:2180` nie ma ani sumy, ani zapasu 1 px: arkusze wyznacza sama
   geometria, wiec miedzy odleglymi obiektami moze zostac pas nodata, a
   skrajna kolumna albo wiersz wyniku (siegajace do < 1 px poza obwiednie)
   moze byc nodata, gdy lezy juz w niewybranym arkuszu sasiada
   (rozstrzygniecie kontrolera fali 2026-09-28) — zgodnie z kontraktem
   "nodata tylko tam, gdzie nie siega zaden pobrany arkusz". R-01 zostaje
   bez zmian (R2): dla jednego obiektu i dla bboxa "cala obwiednia"
   i "pierscien" (sam pas zapasu wokol obwiedni) daja ten sam zbior
   arkuszy, a rzadka geometria wieloobiektowa, dla ktorej sie roznia, nie
   wystepuje w praktyce (koszt — akapit o `--geometry` nizej). Selekcja
   jest grubsza niz scisla geometria: w duzym wycinku czesc arkuszy (pomiar
   L7 2026-09-29: kilka procent) lezy calkowicie poza siatka wyniku — koszt
   otwarc plikow, nie poprawnosci.
4. **Arkusze jako cache; brak danych = nodata (R5).**
   `DownloadManager.download_sheets` pobiera arkusze (grubsze godla PL-1992
   rozwija do 1:10000) do ich wlasnych segmentow `nmt/pl_1992_<res>_<vcrs>/`
   z wlasnymi sidecarami (z `parent_request`, gdy podany), rownolegle wg
   `max_workers`; `skip_existing = not force`, wiec arkusze z dysku sa
   uzywane ponownie (E2E 2026-09-28: po usunieciu wyniku przebieg bez
   `force` — zero wywolan providera, wynik bajt w bajt). Porazka arkusza
   z rodziny `DownloadError` nie przerywa listy: trafia do
   `last_result.failed`, a brak danych u zrodla — takze do
   `last_result.no_coverage`. Inny wyjatek arkusza (np. `OSError` zapisu)
   przy `max_workers=1` (domyslne w bibliotece) wylatuje z `download_sheets`
   i `run_pl_cutout` bez zmian, przerywajac liste; w puli watkow
   (`max_workers > 1`, w CLI domyslnie 4) pula zapisuje go w `failed` (bez
   `no_coverage`), wiec konczy sie `DownloadError` jak awaria pobrania
   ponizej. W CLI oba warianty lapie `except Exception` wokol
   `run_pl_cutout`, tak samo jak bledy ponizej. `NoCoverageError` rzuca
   `GugikProvider`, gdy warstwy odpowiedzialy i zadna nie ma zgodnego
   rekordu; awaria ktorejkolwiek pytanej warstwy daje `DownloadError`
   (do 3 prob przy bledzie sieci, 429 i 5xx; inne 4xx bez ponowien), bez
   zapisywania negatywnego wpisu w cache.
   Odpowiedz pusta musi zawierac szablon `var ... = [];`; raport OGC
   (`ServiceException`/`ExceptionReport`) lub uszkodzony szablon to
   awaria, nie brak pokrycia. Po pobraniu `run_pl_cutout` rozstrzyga:
   - `NoCoverageError` -> nodata w miejscu arkusza,
     `PlCutoutResult.missing_sheets` i `extra.missing_sheets`; lista
     nie mierzy nodata wewnatrz pobranych arkuszy przybrzeznych;
   - kazdy inny blad arkusza -> `DownloadError` przed budowa wyniku;
   - zero pobranych arkuszy -> `ValidationError` przed budowa wyniku.
   CLI wyswietla `Warning:` dla brakow, a przy sukcesie drugiego kraju
   pod `auto` stosuje kod 0. Rekordy z pobranych arkuszy trafiaja do
   `extra.sheet_sources` wycinka (mapa godel na `extra.source`).
   Gdy wszystkie piksele gotowego wycinka sa nodata mimo pobranych
   arkuszy, `PlCutoutResult.all_nodata=True` i CLI wyswietla `Warning:`
   (kod 0); sidecar dostaje `extra.all_nodata: true`. Pomijany istniejacy
   wycinek nie jest ponownie skanowany — `skipped_pl_cutout` odtwarza
   z sidecara wszystkie pola wyniku wymienione w tabeli sekcji 3.2
   (`missing_sheets`, `off_grid_sheets`, `all_nodata`, `partial_sheets`,
   `unverified`), a CLI powtarza ostrzezenia (E15).
5. **Mozaika na siatce arkuszy** (`build_pl_cutout`).
   `_reject_pl2000_sheets` chroni przed starym plikiem PL-2000 pod godlem
   PL-1992 w cache (usun taki plik i ponow); nowych plikow tego typu
   skorowidz nie wybiera. `check_source_grid` okresla faze wiekszosci
   i liste arkuszy odchylonych. Przy EPSG:2180 odchylenie daje
   `GridMismatchError(ValidationError)` z `.off_grid` i podpowiedzia
   wyboru innego `--target-crs`: nie wolno utracic wartosci 1:1.
   Przy innym celu i odchyleniach W1 wykonuje `warp_to_grid(list[Path])`,
   kazdy arkusz raz z wlasnej siatki na wspolny wynik (bez pliku tmp),
   zapisujac `extra.off_grid_sheets`. Przy zgodnej fazie zostaje
   `mosaic_and_crop(..., snap_to_source_grid=True,
   assign_crs="EPSG:2180", dtype="float32")` i pojedynczy warp;
   kazde zrodlo VRT ma wlasne nodata, jawny EPSG:2180 i Float32.
   Obrocona siatka lub niezgodny CRS to `ValidationError`.
6. **Crop albo warp.** Przy `EPSG:2180` zgodne arkusze tworza mozaike
   na wspolnej siatce bez resamplingu: wynik zachowuje wartosci 1:1,
   obszar jest rozszerzony na zewnatrz o < 1 px; `transform: null`.
   Przy innym celu zwykla sciezka reprojektuje te mozaike z wymuszona
   przypieta operacja GDAL (`COORDINATE_OPERATION`), bilinear i maska
   nodata; przy roznicach fazy W1 reprojektuje kazdy arkusz z jego siatki
   na siatke docelowa raz, bez wspolnej mozaiki posredniej.
   Siatke wyniku wyznacza bbox_target: NW = (`min_x`, `max_y`),
   wymiary `max(1, round(rozpietosc / piksel))`, odchylenie E/S do
   0,5 px (wyjatek: bbox wezszy od pol piksela). Nazwa niesie
   `bbox_target`; nominalna dokladnosc operacji w sidecarze zalezy od
   sciezki, pin S-JTSK wybiera czeski EPSG:1622/1623 (ADR-024).
7. **Rozmiar i dysk.** Brak twardego limitu rozmiaru. Przy zgodnej fazie
   i warpie mozaika posrednia jest skompresowana (deflate, predyktor 3,
   kafle 512 x 512), a po warpie usuwana; W1 nie tworzy mozaiki posredniej.
   `check_pl_cutout_disk_space` sprawdza dolne oszacowanie: rozmiar wyniku
   float32 + 5,5 B na piksel brakujacych arkuszy (bez pliku posredniego).
   Zbior brakujacych arkuszy jest liczony raz i wykorzystywany ponownie;
   za malo miejsca = `ValidationError` przed siecia. CLI wypisuje
   `Info:` dla wyniku >= 1 GiB.
8. **Sidecar** (`write_pl_cutout_sidecar`, best-effort): `capability=
   "sheet_files"`, uklad docelowy, przypieta transformacja, nodata
   i klucze `extra` wycinka — pelna lista, warunki zapisu i odtwarzanie
   przy skip: sekcja 3.2, akapit "Wycinek PL w sidecarze".

**Nieudana budowa a poprzedni wynik.** Obie sciezki zapisu sa atomowe
(`os.replace` pliku posredniego przy samym cropie, wewnetrzny `os.replace`
w `warp_to_grid`), a plik posredni sprzata `finally` — przerwana budowa nie
zostawia pod finalna sciezka polzapisanego pliku. Skoro tak, ZADNE ogniwo
toru PL nie kasuje poprzedniego wyniku: ani `build_pl_cutout`, ani
`transform/raster.py::warp_to_grid` — stary plik przezywa awarie, takze
z `force=True` (testy:
`tests/test_pl_cutout.py::TestBuildPlCutout::test_failed_build_keeps_previous_result`
— przerwany warp w `build_pl_cutout` — i
`tests/test_transform_raster.py::TestWarpToGrid::test_failed_warp_keeps_previous_destination`
— sam `warp_to_grid`), a sciezka sukcesu jest identyczna. Kasowanie bylo
tu czysta utrata danych — pod `--country auto` cale zadanie moglo skonczyc
sie kodem 0 (bo drugi kraj sie udal), zostawiajac uzytkownika bez pliku,
ktory mial wczesniej. Obietnica obejmuje wiec takze
`--target-crs EPSG:5514`/`EPSG:3045`, czyli glowne zastosowanie flagi.
Tor CZ korzysta od 2026-10-06 z tej samej funkcji
(`CuzkDmrProvider._export_raster` -> `warp_to_grid(..., src_crs=EPSG:5514,
nodata=-9999)`; dawna kopia `providers/cuzk/dmr.py::_warp_to_grid`
z `except BaseException: dst.unlink(...)`, ktora przy awarii KASOWALA
poprzedni wycinek lub kafel TM33, zostala usunieta — review 2026-10-06
D8/N7), wiec gwarancja jest wspolna dla PL i CZ (test:
`tests/test_cuzk_dmr.py::TestHorizontalReprojection::test_failed_warp_keeps_previous_output`). Bez
`--force` sytuacja i tak nie wystepuje, bo skrot "plik juz istnieje" wraca
wczesniej. Nieudana budowa nie zostawia tez pustego drzewa
`<segment>/bbox/` (review max zn. 10): `run_pl_cutout` przy wyjatku
z `build_pl_cutout` wola `prune_empty_dirs(<katalog wyniku>, output_dir)`,
ktore usuwa puste katalogi w gore az do `output_dir` (bez niego); katalog
z poprzednim wynikiem nie jest pusty, wiec zostaje. Tor CZ (bbox) sprzata
tak samo.

W trybie `--geometry` wycinek obejmuje **CALA obwiednie geometrii, bez
maskowania do jej obiektow** — do warstwy rastrowej ida same sciezki arkuszy
i bbox. `nodata` pojawia sie wylacznie tam, gdzie nie siega zaden POBRANY
arkusz (takze w miejscu arkusza bez danych GUGiK, krok 4), i nigdy nie
oznacza maskowania. Dlatego przy `--target-crs` innym niz EPSG:2180 arkusze
to SUMA godel geometrii i godel obwiedni z zapasem — obietnice "cala
obwiednia" wypelniaja dane, a nie ramka dziur. **Swiadomy koszt:** przy
rzadkiej geometrii wieloobiektowej suma obejmuje arkusze CALEJ obwiedni,
takze te, ktorych nie przecina zaden obiekt (review max zn. 15: dla
obwiedni kilkudziesieciu km z dwiema malymi zlewniami — setki arkuszy
zamiast kilkunastu potrzebnych; R2: bez zmian), a arkusz jest mniejszy, niz
sugeruje etykieta: godlo 7-czlonowe nazywane w Kartografie "1:10000" ma
w EPSG:2180 **~2,25 x 2,43 km** (zmierzone: `N-34-130-D-d-2-4` -> 2252,6 x
2432,4 m; GUGiK nazywa ten sam arkusz modulem archiwizacji 1:5000 — patrz
Notes w `core/sheet_parser.py`), wiec obwiednia rzedu kilkudziesieciu
kilometrow to juz setki arkuszy. Dla `--target-crs EPSG:2180` sumy nie ma
(krok 3).

Wylaczenia (kod 1 z komunikatem): `--target-crs` z `--product nmpt|orto|laz`
oraz z `--system 2000` (bbox wielostrefowy dalby arkusze w EPSG:2176-2179;
mozaika miedzystrefowa to etap 2) — walidacja w `_resolve_pl_sentinels`;
`--target-crs` z godlem odrzuca `cmd_download` w galezi godlowej (dla CZ
`_cmd_download_cz`, wyjatkiem tlumaczonym przez `_run_cz`), zanim cokolwiek
pojdzie w siec. Scalanie PL+CZ w jedna ciagla powierzchnie przygraniczna
(wspolna siatka, EVRF2007 po obu stronach) to etap 2 (R6) — na pograniczu
`--country auto --target-crs` daje dwa osobne wycinki w tym samym ukladzie,
ze wspolnym `extra.parent_request`.

**Kampanie a wycinek (ADR-030, errata Q2/Q4).** Wycinek jest ZAWSZE
`newest`: `run_pl_cutout` buduje wlasny `DownloadManager` bez `campaigns`
i czyta arkusze przez dowiazania sciezki standardowej (hardlink i kopia to
zwykle pliki), a `extra.sheet_sources` czyta
sidecar standardowy. `--target-crs` + (`--campaigns all` lub `--min-year`)
odrzuca CLI przed siecia (`Error: --campaigns all nie dziala z --target-crs
— wycinek sklada jedna kampanie na arkusz; laczenie kampanii: narzedzie
0.7.1` / `Error: --min-year nie dziala z --target-crs — nazwa wycinka nie
niesie granicy roku`, kod 1). Wycinek jest pomijany po SAMYM istnieniu
pliku wyniku (Q4), takze gdy skorowidz ma juz nowsza kampanie — odswiezenie:
`--force` albo usuniecie wycinka. Kontrola wolnego miejsca
(`estimate_pl_cutout_bytes`, D-3) to DOLNE oszacowanie: liczy arkusze bez
pliku w sciezce standardowej, a pod `newest` arkusz z nowsza (albo
usunieta) kampania zostanie pobrany mimo istniejacego dowiazania.

Wynik: **jeden plik** `data/nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`
(+ `.meta.json`), gdzie `<coords>` = `<min_x>_<min_y>_<max_x>_<max_y>`
obwiedni zadania w ukladzie DOCELOWYM (`bbox_target`), kazda liczba
sformatowana `%.10g` (`download/storage.py`, regula 3 sekcji 3.3). Dla
`--target-crs EPSG:5514` wspolrzedne sa ujemne; ich wartosci zaleza od
przypietej operacji, wiec sciezke wyniku podaje `PlCutout.target_path`
(`prepare_pl_cutout`), a nie reczne przeliczenie bboxa wejsciowego.

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
CZ jest nieosiagalny (brak publicznych siatek). Sidecar pisze CLI.

Wynik: `data/nmt/cz_dmr5g_bpv/302/5550/302_5550.tif` (`horizontal_crs`
EPSG:3045) albo `data/nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif`
(`horizontal_crs` EPSG:5514).

### 4.5 Bbox CZ

Jeden wycinek `exportImage`. Bbox jest najpierw normalizowany do ukladu WYNIKU
(`--target-crs` albo natywny EPSG:5514), zeby nazwa pliku niosla wspolrzedne
faktycznie zadanego wycinka. Zadanie do serwera idzie natywnie; przy
`--target-crs` innym niz 5514 tresc reprojektuje lokalny warp
z czeska operacja przypieta. Serwer deklaruje sufity 15000 x 4100 px,
lecz realnie odrzuca zadania powyzej ok. 8 Mpx. `CuzkClient` dzieli
zadanie z budzetem `MAX_EXPORT_PIXELS = 4_000_000` na kafle z kotwica
NW (kwadratowawe, z zachowaniem sufitow wymiarowych); kafle sklada
`mosaic_and_crop` bez resamplingu przed warpem. Bbox jest dociagany
do calkowitej liczby pikseli takze bez kafelkowania: piksel to
dokladnie 2 m/5 m, E/S moze odbiegac o <= 0,5 px (nazwa pliku i
`request.bbox` niosa bbox sprzed snapu). Wycinek w calosci nodata
daje `Warning:` i kod 0, nie pozorna cisze.

Wynik: `data/nmt/cz_dmr5g_<vcrs>/bbox/<coords>.tif` (+ `.meta.json`).

### 4.6 Dyspozycja per kraj (`--country auto`)

`_countries_for_bbox` porownuje bbox (w WGS84) z `CountryProfile.extent_wgs84`
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
prostokata. `_country_bbox` zmienia tylko obciete krawedzie PL —
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
pogranicze daje PL w EVRF2007 i CZ w Bpv.

Opcje kampanii (ADR-030; errata Q9, N-3) dotycza tylko PL; jedna funkcja
`_reject_campaign_opts_without_pl(args, countries)` obsluguje wszystkie
punkty wejscia: zadanie bez PL wsrod krajow (godlo CZ pod `cz`/`auto`,
obszar lub geometria z jawnym `--country cz`, obszar w calosci czeski pod
`auto`) = `Error: CZ (CUZK) nie ma kampanii — --campaigns all/--min-year
dotycza tylko PL`, kod 1, bez sieci; obszar pod `auto` z PL i CZ = jedno
`Info: --campaigns/--min-year dotycza tylko czesci PL (CZ: biezaca wersja
danych CUZK)`, CZ pobierane dalej. Opcje kampanii nie naleza do
`_pl_only_flags` — nie zwezaja `auto` do PL.

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
jest sprawdzany wobec rocznikow danej uslugi wysokosciowej PRZED
`GetFeature` — rok nieobecny to `DownloadError("rocznik <rok> nie istnieje
w usludze <vcrs> (dostepne: ...)")` bez sugestii ponowienia. Jesli
ktorykolwiek rocznik zawiedzie po ponowieniach, `select_tiles`
rzuca `DownloadError` z informacja o niekompletnym wyniku, zamiast
sugerowac brak kafli. Gdy wszystkie
odpowiedza i nic nie znaleziono, CLI drukuje `No LAZ tiles found`
(`download_laz_area`: `NoCoverageError`).

**Wybor kafli (ADR-029).** Domyslnie (bez `--year`) kafle sa wybierane
zachlannie od najnowszego `akt_rok` (w roku: nowsza `akt_data`): kafel
starszy jest pomijany, gdy jego czesc wspolna z obszarem zadania pokrywa
juz suma wybranych kafli — porownanie ram `msGeometry` w EPSG:2180,
kazda rama pokrycia powiekszona o 1 m (`COVERAGE_TOLERANCE_M`); kafel
wnoszacy niepokryty kawalek zostaje (caly — LAZ nie jest przycinany).
Dzieki temu PL-1992 i PL-2000 tego samego miejsca nie dubluja sie (w2:
2025/PL-1992 zamiast 2025 + 2022/PL-2000:S7). Z `--year` regula dziala
w obrebie tego roku. Pokrywa tylko kafel pelny (`czy_ark_wypelniony` !=
`NIE`) i tylko rama albo tym samym godlem, nigdy obwiednia. Kafel, ktorego
rama nie przecina obszaru (przecina go tylko obwiednia), jest pomijany.
Pominiete kafle: `LazTileSelection.superseded` / `LazDownloadResult.superseded`
(kafel + kafle pokrywajace), w CLI `Info:` na stderr takze z `-q`.

Porazka pobrania choc jednego kafla trafia do `LazDownloadResult.failed`
(biblioteka nie rzuca); CLI konczy wtedy kodem 1 z `Error:`
i PELNA lista nieudanych kafli (jak `_finish_pl_sheets`; udane kafle
zostaja na dysku i przy ponowieniu bez `--force` sa pomijane).
Godlo kafla jest drobniejsze niz 1:10000 i NIE jest
parsowane — `FileStorage.get_raw_path(..., uklad=tile.uklad)` buduje z niego
sama hierarchie katalogow. Uklad poziomy jest ustalany **per kafel**
wlasnoscia `LazTile.uklad` (jedno zrodlo prawdy dla CLI i biblioteki, zn. 8
review max) z `uklad_xy` kafla, parserem `sources.registry.parse_pl_uklad`
wspolnym ze skorowidzem i sidecarem (`horizontal_crs_for_uklad`; review-1 D3):
`PL-1992` -> `1992`, `PL-2000:S5..S8` -> `2000`. Nierozpoznana wartosc (np.
`PL-2000` bez strefy) — kafel pominiety w discovery z ostrzezeniem w logu,
a `LazTile.uklad` recznie zbudowanego kafla rzuca `ValidationError` (dawniej
zgadywanie z formatu godla dawalo segment `pl_2000` z sidecarem EPSG:2180).
Uklad pionowy bierze sie z flagi CLI (biblioteka:
`FileStorage(vertical_crs=)`). Jedno zadanie moze wiec zapisac kafle do dwoch
segmentow naraz — `{uklad}` rozwiazuje sie per wywolanie `get_raw_path`,
jeden `FileStorage` wystarcza na cale zadanie. W trybie obszarowym
`--country auto` obszar siegajacy CZ konczy sie bledem z podpowiedzia
`--country pl` (LAZ dla CZ to etap 2).

**Kampanie LAZ (ADR-030).** `--campaigns newest` (domyslnie) = ADR-029
bez zmian. `--campaigns all` = wszystkie kafle, ktorych rama
(`footprint`) przecina obszar, bez deduplikacji pokryciowej
(`select_all_intersecting`); kafel, ktorego przecina obszar tylko obwiednia
z WFS (rama bez czesci wspolnej), jest pomijany jak dotad i trafia do
`superseded` z pusta lista pokrywajacych (powod "outside"). `--min-year RRRR` = dolna
granica `akt_rok` (obie strategie; `download_laz_area(campaigns=, min_year=)`);
`--min-year` z `--year` wykluczaja sie (`Error: --min-year i --year
wykluczaja sie (LAZ)`, kod 1; w bibliotece `ValidationError`). Uklad LAZ
bez zmian — bez `kampanie/` i dowiazan; `request.campaigns` w sidecarze
tylko dla `all`, `request.min_year` gdy podany.

Wynik: `data/laz/pl_2000_evrf2007/6/162/34/02/3/<oryginalna_nazwa>.laz`
(+ `.meta.json` z `extra.tile_sheet`/`year`/`nominal_density`/`url` oraz
`extra.parent_request` w trybie `--bbox`/`--geometry`; `request`
niesie bbox oraz `year`/`min_density`, gdy podane — E16).
`nominal_density` i filtr `--min-density` to wartosc NOMINALNA z WFS GUGiK
(`char_przestrz`); faktyczna gestosc kafla bywa kilkukrotnie wyzsza
(E2E 2026-10-06: ~119 pkt/m2 przy nominale 15).

### 4.8 Land cover i gleby (BDOT10k, CORINE, SoilGrids)

Uklad katalogow ADR-026 tych zrodel nie dotyczy (`storage_subdir = None`).
Zmiany od 0.6.x (szczegoly: `docs/CHANGELOG.md`): sidecary wynikow,
rozszerzenie pliku z faktycznego formatu (N14), SHP BDOT10k jako `.zip`
(N1), sidecar wyniku HSG, scalanie GPKG BDOT10k w lokalnym katalogu
tymczasowym. `LandCoverManager` ma **wlasny domyslny katalog**
(`./data/landcover`, CLI `--output`) i wlasna konwencje nazw plikow:
baza nazwy `<provider>_teryt_<teryt>`, `<provider>_bbox_<minx>_<miny>_<maxx>_<maxy>`
albo `<provider>_godlo_<godlo>` (`_generate_output_path` nadaje `.gpkg`).
Rozszerzenie FAKTYCZNEGO pliku nadaje provider: BDOT10k `.gpkg`, CORINE
`.tif` (CLMS) albo `.png` (podglad WMS), SoilGrids `.tif`; zwracana
sciezka i sidecar dotycza tego pliku (review 2026-10-06 N14). BDOT10k
z `format="SHP"` (`--format SHP`) zapisuje oryginalne archiwum
GUGiK z shapefile'ami pod ta sama nazwa z rozszerzeniem `.zip`
(np. `bdot10k_teryt_1465.zip`, sidecar `bdot10k_teryt_1465.zip.meta.json`);
rozszerzenie nadaje `Bdot10kProvider.download_by_admin_unit`, a CLI drukuje
faktyczna sciezke (review 2026-10-06 N1). Sidecary pisze `LandCoverManager` tak samo jak
pozostale warstwy zarzadzajace. CORINE bez credentials CLMS pobiera podglad
PNG przez WMS: sidecar ma wtedy `horizontal_crs` uslugi WMS (EPSG:3857, dla
rocznika 1990 EPSG:4326) oraz `extra.fallback = "wms_png"` i `extra.note`
(`"podglad WMS, nie dane"`).

BDOT10k GPKG: archiwum ZIP z GUGiK jest rozpakowywane, a warstwy scalane
w jeden GeoPackage w LOKALNYM katalogu tymczasowym (`tempfile`); do
`--output` trafia gotowy plik (kopia jako `.gpkg.tmp` + `os.replace`).
Powod: SQLite na udzialach CIFS/SMB bez blokad zakresow bajtow konczyl
scalanie bledem `database is locked` (`Bdot10kProvider._merge_gpkg_files`).

`HSGCalculator` (`hydrology/hsg.py`) liczy grupy glebowe z warstw SoilGrids
(`clay`, `sand`, `silt`) wg kanonicznego trojkata USDA (ADR-025) i pisze
sidecar wyniku (`HSGCalculator._write_sidecar` -> `emit_sidecar`, best-effort):
deskryptor `global.isric.soilgrids`, `capability="bbox_raster"`, `request`
= bbox z jego ukladem, `horizontal_crs` = uklad rastra wyniku, `nodata: 0`,
`extra` = `{derived: "hsg", source_layers: ["clay", "sand", "silt"], depth,
stat, classes: "1=A, 2=B, 3=C, 4=D"}`.

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
   i `dataset_keys`. `_countries_for_bbox` czyta kraje z rejestru przez
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
