# Architektura Kartografa

**Data:** 2026-09-30
**Wersja opisywana:** 0.7.0 (develop, przed tagiem)

Stan kodu po fali naprawczej 2026-09-29/30 (testy offline, bez ponownej
weryfikacji na zywych serwisach). Raporty historycznych pomiarow live:
`docs/research/2026-09-29-live-e2e-i-audyt-docs/`.

Dokument kanoniczny: README/CLAUDE.md/SCOPE odsylaja tutaj; przy sprzecznosci
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
`area_files`, `admin_unit_files`, `bbox_vector`, z czego rejestr deklaruje
dzis pierwsze cztery. Logika wykonawcza zostaje w providerach —
deskryptor mowi CO zrodlo potrafi i gdzie ma wyladowac wynik, nie JAK je pobrac.

**Sidecar przy kazdym udanym pobraniu.** Obok kazdego pliku danych powstaje
`<pelna_nazwa_pliku>.meta.json` ze schema `kartograf-meta/1`: uklad poziomy
i pionowy, `nodata`, oryginalne zadanie, licencja, wersja pakietu, opis
wykonanych transformacji. Sidecary pisza **warstwy zarzadzajace** —
`DownloadManager`, `LandCoverManager`, wycinek PL w bibliotece
(`download/cutout.py::write_pl_cutout_sidecar`) i CLI (tory LAZ i CZ) —
nigdy providery; provider zwraca `Path`, metadane skladane sa pietro wyzej,
gdzie znany jest kontekst zadania. Zapis sidecara jest best-effort: kazdy blad
(IO, brakujacy klucz deskryptora, wyjatek w budowie metadanych) konczy sie
`logger.warning`, nigdy przerwaniem pobrania — dane sa wazniejsze niz metadane.
Poza bledem zapisu jedyny cichy przypadek braku sidecara przy sukcesie
to provider bez `descriptor_key` (`DownloadManager._write_sidecar`
wraca wtedy po cichu). Pominiety juz pobrany plik zachowuje
dotychczasowy sidecar; arkusz z sidecarem ponownie wykorzystany
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
ukladow nieczeskich, dyspozycja krajow w CLI) swiadomie uzywaja domyslnego
transformera pyproj — migracja to backlog A5-6.
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
scala dzis konsument (Hydrograf). Scalanie PL+CZ w jedna ciagla powierzchnie
przygraniczna (wspolna siatka, EVRF2007 po obu stronach) to etap 2 Kartografa
(R6, 2026-09-28; wczesniej zapisane jako zadanie Hydrografa; dane styku
zmierzone na zywo 2026-09-29 — sekcja 4.6). Kartograf dostarcza wszystko,
czego takie scalenie wymaga: jawne kody CRS obu osi, `nodata`, opis uzytej
operacji z dokladnoscia i wspolny klucz grupowania.

---

## 2. Warstwy i zaleznosci modulow

Ponizszy graf zostal ZMIERZONY na drzewie importow (AST wszystkich plikow
`kartograf/**/*.py`, krawedzie miedzypakietowe), nie zalozony:

```
cli ──> download, landcover, hydrology, providers, sources,
        transform, core, cache
download ──> providers, sources, transform, transport, core
landcover ──> providers, sources, download (FileStorage), core
hydrology ──> providers, core
providers ──> sources, transform, transport, core, cache, auth
sources ──> core
transform ──> core
transport ──> core
cache ──> (nic wewnetrznego)
auth ──> (nic wewnetrznego)
core ──> (nic wewnetrznego przy imporcie)
exceptions ──> (lisc; importowany przez wszystkie warstwy)
```

Trzy uwagi, ktore latwo przeoczyc:

- `core` ma **jeden leniwy** import w druga strone:
  `parser_registry._make_parser_cz_sm5` siega po
  `providers.cuzk.sheets.Sm5Sheet` dopiero w momencie wywolania. Odroczenie
  jest celowe (komentarz w kodzie) — przy imporcie `core` nie ciagnie
  providerow ani ich zaleznosci IO, wiec warstwa pozostaje czysta dla
  wszystkiego poza budowa parsera arkusza SM5.
- `download` siega po `transform` i `transport` WYLACZNIE w
  `download/cutout.py` (wycinek PL, sekcja 4.3): `transform.crs` przy
  imporcie (typy `PinnedTransform`/`TransformPolicy`), `transport.mosaic`
  i `transform.raster` leniwie, w `build_pl_cutout`. `manager.py`
  i `storage.py` nie importuja zadnego z nich — `DownloadManager` pozostaje
  warstwa koordynacji arkuszy. CLI od 2026-09-28 nie importuje juz
  `transport` wcale (mozaika i warp wycinka przeszly do biblioteki, R3),
  a z `transform` bierze tylko `TransformError`.
- Krawedz `download ──> providers` siega tez do zamrozonego toru CZ:
  `download/cutout.py` (tor PL) importuje leniwie generyczny `bbox_to_crs`
  z `providers/cuzk/dmr.py` (ADR-024); przeniesienie go do `transform/` to
  etap 2, razem z odmrozeniem toru CZ.

### Moduly

```
kartograf/
├── __init__.py          # Public API (BBox, SheetParser, DownloadManager, providery, ...)
├── exceptions.py        # KartografError, ParseError, ValidationError, DownloadError,
│                        # NoCoverageError(DownloadError) — zrodlo nie ma danych arkusza
├── core/                # Logika bazowa, bez IO sieciowego
│   ├── sheet_parser.py     # SheetParser (PL-1992), BBox, find_sheets_for_bbox
│   ├── parser_2000.py      # Parser2000 (PL-2000), find_sheets_2000_for_bbox
│   ├── parser_tm33.py      # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045)
│   ├── parser_registry.py  # Rejestr systemow godel: pl1992, pl2000, cz_tm33, cz_sm5
│   └── geometry.py         # Czytanie SHP/GPKG, find_sheets_for_geometry, get_overall_bbox
├── sources/             # Deskryptory zrodel jako dane (zero IO przy imporcie)
│   ├── descriptor.py    # SourceDescriptor (+ resolve_subdir), AccessChannel,
│   │                    # TransportKind, TileScheme, LicenseInfo, CountryProfile
│   ├── registry.py      # Rejestr PL/CZ/EU/GLOBAL + mapowanie ukladow pionowych
│   └── sidecar.py       # ResultMetadata, build_metadata, write_sidecar, read_asc_nodata
├── transform/           # Transformacje wspolrzednych i rastrow
│   ├── crs.py           # TransformPolicy, PinnedTransform, build_pinned_transform, KNOWN_PATHS
│   └── raster.py        # warp_to_grid — lokalny warp na siatke, operacja WYMUSZONA (tory PL)
├── transport/           # Wspolny transport
│   ├── http.py          # download_to/get_with_retry — zapis atomowy + retry (siec, 429, 5xx; Retry-After)
│   └── mosaic.py        # mosaic_and_crop — merge rastrow + przyciecie, propagacja nodata;
│                        # opcjonalnie crop na siatce zrodel i owijanie zrodel w VRT
├── providers/           # Providery danych
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider, LandCoverProvider
│   ├── pl/              # GUGiK: gugik.py (NMT), gugik_nmpt.py, gugik_orto.py,
│   │                    # gugik_laz.py, bdot10k.py, __init__.py (create_nmt_provider)
│   ├── cuzk/            # CUZK: client.py (silnik sterowany deskryptorem),
│   │                    # sheets.py (indeks SM5/TM33), dmr.py, __init__.py (create_dmr_provider)
│   ├── corine.py        # CORINE z Copernicus CLMS (+ fallback WMS PNG)
│   └── soilgrids.py     # SoilGrids z ISRIC (WCS)
├── cache/metadata.py    # MetadataCache — SQLite WAL, TTL 7 dni (sheet_cache 30 dni), thread-safe
├── download/            # Pobieranie NMT/NMPT/Orto po godle + wycinek PL
│   ├── cutout.py        # Wycinek PL --target-crs jako API (ADR-027): prepare/select/run/
│   │                    # download_pl_cutout — mozaika arkuszy + warp, sidecar
│   ├── manager.py       # DownloadManager — koordynacja arkuszy (ThreadPoolExecutor), sidecary;
│   │                    # download_sheets/expand_sheets (lista godel, porazki w last_result)
│   └── storage.py       # FileStorage — segmenty z szablonow rejestru (ADR-026);
│                        # prune_empty_dirs — sprzatanie pustych bbox/ po porazce
├── landcover/manager.py # LandCoverManager — dispatch do providerow pokrycia terenu
├── hydrology/hsg.py     # HSGCalculator — klasyfikacja USDA -> HSG (ADR-025)
├── auth/                # proxy.py (subprocess izolujacy credentials CLMS), client.py
└── cli/                 # _parser.py + moduly per komenda + fasada commands.py
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
| `{uklad}` (jawnie) | tor LAZ: `LazTile.uklad` (kaskada `uklad_xy` kafla -> format godla -> "2000") przez `FileStorage.get_raw_path(..., uklad=)` — jedno zrodlo prawdy dla CLI i biblioteki (zn. 8, review max); wycinek PL (`prepare_pl_cutout`: `uklad="1992"` na stale — `--target-crs` z `--system 2000` jest odrzucane, a arkusz we wspolrzednych PL-2000 konczy budowe bledem, sekcja 4.3) | przed utworzeniem `FileStorage` / sciezki wycinka |

`FileStorage` waliduje wynik koncowy: segment, w ktorym po wypelnieniu zostala
klamra `{`, konczy sie `ValidationError` z nazwa brakujacego wymiaru
(`_ensure_resolved`). Cichy katalog `pl_{uklad}_1m_evrf2007` nigdy nie powstanie.

### 3.2 Schema sidecara `kartograf-meta/1`

Kazde udane pobranie zapisuje **dwa** pliki: dane i `<plik>.meta.json`.

| Pole | Znaczenie |
|---|---|
| `dataset` | klucz deskryptora zrodla (np. `pl.gugik.nmt_1m`) |
| `country`, `product`, `provider` | kraj, produkt i nazwa dostawcy z deskryptora |
| `horizontal_crs` | faktyczny uklad poziomy pliku: arkusz PL-1992 `EPSG:2180`, arkusz PL-2000 `EPSG:2176`–`EPSG:2179` wedlug strefy godla, CZ natywnie `EPSG:5514`, kafel TM33 `EPSG:3045`; wycinek po `--target-crs` w ukladzie docelowym |
| `vertical_crs` | kod realizacji ukladu pionowego: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007); `null` gdy produkt nie ma pionu (orto) |
| `vertical_source` | `native` / `ellipsoidal` / `server` (z `AccessChannel`) |
| `resolution` | rozdzielczosc z deskryptora (`1m`/`5m`/`2m`) albo `null` |
| `nodata` | wartosc pustego piksela: dla `.asc` czytana automatycznie z naglowka (`read_asc_nodata`), w torze CZ podawana przez CLI z tagu GeoTIFF (`_read_tif_nodata`; w trybie bbox z fallbackiem `CUZK_NODATA`), dla wycinka PL stala `-9999.0`; `null` gdy zadna z tych drog nie ma zastosowania (np. orto) |
| `request` | zadanie, ktore dalo TEN plik: `godlo`, `bbox` + `bbox_crs` w ukladzie wyniku albo `teryt`; oryginalne zadanie niesie `extra.parent_request` (3.4), rekord skorowidza PL niesie `extra.source` |
| `license` | `{id, attribution, url}` z deskryptora |
| `downloaded_at`, `kartograf_version` | znacznik czasu UTC (ISO 8601, sekundy) i wersja pakietu |
| `transform` | slownik osi (`horizontal`/`vertical`) z opisem uzytej operacji w formacie `pinned: <opis> (<dokladnosc> m)`; os bez przeliczenia nie ma klucza, a bez zadnego przeliczenia cale pole to `null` |
| `extra` | `parent_request` (obszar) / `parent_requests` (kolejne zadania wykorzystujace ten sam arkusz); LAZ ma `godlo_kafla`/`rok`/`gestosc`/`url`; SM5 ma `mapname`/`podil`; arkusze NMT/NMPT/orto PL maja `source` (URL, warstwa, aktualnosc, rozdzielczosc itd.); wycinek PL: `sheet_sources` (mapa godlo -> source), `missing_sheets` (brak pliku), `off_grid_sheets` (W1, niezgodna faza) |
| `schema` | stale `kartograf-meta/1` |

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
— obwiednia zadania po przeliczeniu do ukladu docelowego, nie oryginal;
`extra` — `parent_request` (gdy podany; bez niego z biblioteki `"extra": {}`)
i `missing_sheets` (gdy niepusta).

### 3.3 Kanoniczny uklad `data/`

```
data/
├── nmt/
│   ├── pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
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
   samym produktem (E12, 2026-10-06). Dzis tylko orto: RGB (domyslny)
   bez sufiksu w `orto/pl_<uklad>/` (bez migracji), CIR w
   `orto/pl_<uklad>_cir/`, B/W w `orto/pl_<uklad>_bw/`. Wariant pochodzi
   z `provider.storage_variant` (`GugikOrtoProvider(color=...)`) i trafia do
   `FileStorage(variant=...)`; bez niego skip zwracal po cichu plik RGB na
   zadanie CIR.

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
— **poza torem LAZ**, ktory ma wlasny przeplyw (`_cmd_download_laz`) i dzis
tego klucza nie niesie wcale (`_write_laz_sidecar` wypelnia `extra` tylko
polami kafla; `_build_parent_request` nie jest stamtad wolane). Konsument
grupujacy po tym kluczu zgubi wiec kafle LAZ:

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

### 4.1 Godlo PL (NMT/NMPT/Orto)

`SheetParser` waliduje godlo i normalizuje wielkosc liter (zer wiodacych NIE
usuwa: `M-33-036-...` i `M-33-36-...` to dla `FileStorage` dwie rozne
sciezki; forma kanoniczna, bez zer, to ta z `find_sheets_for_bbox`); godlo
PL-1992 grubsze niz 1:10000 rozwija sie do arkuszy 1:10000
(`download_hierarchy`), godlo PL-2000 pobierane jest bezposrednio. Dla
kazdego arkusza pyta WMS skorowidz (`GetFeatureInfo`, warstwy wykryte lazy
przez `GetCapabilities` — ADR-020). `providers/pl/skorowidz.py` parsuje
pelne rekordy; filtruje cale godlo, zgodny uklad i rozdzielczosc
(dla orto tez domyslnie RGB), wybiera najnowsza date w pierwszej warstwie
z dopasowaniem; remis rozstrzyga `dt_pzgik`, URL. Brak zgodnego rekordu
po poprawnych odpowiedziach warstw = `NoCoverageError`, np. dla PL-2000
1:10000 z samymi potomkami podpowiedz `--scale 1:2000`. Awaria warstwy,
raport OGC albo nieoczekiwany szablon = `DownloadError`, nie cichy fallback
do starszej kampanii. Zapytania i pobrania maja 3 proby z backoffem
oraz sesje keep-alive per watek. `MetadataCache` (SQLite WAL, TTL 7 dni)
zapisuje rekord `{"source": ...}` lub potwierdzony `{"no_coverage": true}`;
CLI podpina cache w torach PL (chyba ze `--force`), biblioteka przyjmuje
`cache=`; `kartograf cache stats` pokazuje `Record entries`.
`DownloadManager` pisze sidecar po kazdym udanym arkuszu; arkusz ASC GUGiK
nie niesie CRS (rasterio: `crs=None`), wiec jedynym nosnikiem ukladu jest
sidecar. Ponowne uruchomienie pomija istniejace pliki bez sieci (zmierzone:
0,4 s w przestrzeni bez sieci). `--target-crs` w trybie godlowym jest
**odrzucane** (kod 1) — godlo PL dostarcza arkusz natywny 1:1.

Wynik: `data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
(+ `.meta.json`); dla NMPT `data/nmpt/pl_1992_1m_evrf2007/...`, dla orto
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
WSZYSTKIE arkusze niezaleznie od `--workers` (ADR-027 addendum R5).
`NoCoverageError` dopisuje brakujace godlo i `Warning:`, status postepu
`no_coverage` (`∅`), bez wetowania pobranych plikow: >= 1 plik i zero
twardych awarii = kod 0. Gdy brak wszystkich arkuszy albo wystapi dowolna
inna awaria pobrania, CLI konczy kodem 1 i wypisuje pelna liste porazek.
Pojedynczy arkusz bez danych to kod 1; pod `--country auto` kod zalezy
jeszcze od sukcesu drugiego kraju (sekcja 4.6).

Wynik: **wiele plikow** — lista arkuszy w segmencie jak w 4.1. To jest
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
  `missing_sheets`, `all_nodata`, `off_grid_sheets`).

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
   przyjmuje pion FAKTYCZNY; korekte 5m => EVRF2007 robi `download_pl_cutout`,
   a w CLI fabryka providera). Bbox trafia do EPSG:2180 (uklady czeskie
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
   zbieznosc poludnikow wzgledem 19°E powieksza waski pas (zmierzone na zywo:
   Osinow Dolny 8,9 x 1,7 km — 18 arkuszy wycinka wobec 6 w trybie listy,
   Slubice 12 wobec 8), co na pograniczu daje wiecej arkuszy
   w `missing_sheets`.
2. **Zapas po stronie zrodla** (`PlCutout.bbox_source_2180`). Przy warpie
   obwiednia celu (`bbox_target`) wraca do EPSG:2180 — obrot ukladu
   docelowego robi ja wieksza niz zadanie — i rosnie o `WARP_MARGIN_PX = 4`
   piksele (halo interpolatora bilinear); lustro `_native_request_bbox` toru
   CZ. Dla `EPSG:2180` zapasu nie ma. Ten bbox — nie zadanie uzytkownika —
   steruje cropem mozaiki i selekcja arkuszy. Zapas nie jest ostroznoscia na
   wyrost: bez niego zmierzony wycinek do EPSG:5514 mial **17,4 % pikseli
   nodata** (3034 z 17484) na krawedziach, a w trybie `--geometry` bez sumy
   godel (krok 3) — **50,1 %** (8756 z 17484).
3. **Selekcja arkuszy** (`select_pl_cutout_sheets`, zero sieci). Tryb bbox:
   `find_sheets_for_bbox` z obwiedni zrodla powiekszonej o **1 piksel** —
   crop jest przyciagany NA ZEWNATRZ do siatki arkuszy (krok 5), wiec bez
   tego zapasu skrajny piksel mogl wpasc w arkusz spoza listy. Tryb
   `--geometry`: arkusze per obiekt (`find_sheets_for_geometry`), a przy
   warpie SUMA z arkuszami tej samej obwiedni z zapasem 1 px (R-01; bez
   sumy krawedzie wyniku bylyby ramka nodata — 50,1 % wyzej). `--geometry`
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
   jest grubsza niz scisla geometria: w duzym wycinku (L7, 2026-09-29) 22
   z 688 arkuszy lezalo calkowicie poza siatka wyniku, do ~3,7 km od
   zadania — koszt otwarc plikow, nie poprawnosci.
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
   (retry 3 razy), bez zapisywania negatywnego wpisu w cache.
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
   (kod 0); pomijany istniejacy wycinek nie jest ponownie skanowany.
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
   "sheet_files"`, uklad docelowy, przypieta transformacja, nodata,
   `extra.parent_request`, `extra.missing_sheets`, `extra.sheet_sources`,
   a dla W1 rowniez `extra.off_grid_sheets`. Przy skip biblioteka odczytuje
   `missing_sheets` i `off_grid_sheets` z istniejacego sidecara, CLI
   powtarza odpowiednie `Warning:`/`Info:`.

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
takze te, ktorych nie przecina zaden obiekt (review max zn. 15: obwiednia
50 x 50 km z dwiema malymi zlewniami — 702 arkusze zamiast 13 potrzebnych;
sam "pierscien" dalby 254; R2: bez zmian), a arkusz jest mniejszy, niz
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

Wynik: **jeden plik** `data/nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`
(+ `.meta.json`), np. dla bboxa 419000,230000,421000,232000 w EPSG:2180
z `--target-crs EPSG:5514`:
`data/nmt/pl_1992_1m_evrf2007/bbox/-499122.4858_-1088442.412_-496975.1716_-1086295.098.tif`.

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
w `extra.parent_request`. Przy geometrii bez `--target-crs` arkusze
PL wyznacza sama geometria, czesc CZ jest przycinana. Jawny
`--country pl` nie przycina; bbox w calosci poza prostokatami =
`Error:`, kod 1 bez sieci. Poza obwiednia CZ przy granicach
DE/SK/UA/BY/LT/RU `auto` odpytuje tylko PL; w prostokacie CZ
dochodzi CUZK nawet nad Polska/Saksonia, bo obwiednia nie jest
wielokatem granicy. Wynik calkowicie nodata (CZ albo wycinek PL
z pobranymi arkuszami) daje `Warning:` i kod 0. Sukces czesciowy
PL lub CZ pod `auto` daje kod 0, `Warning:` przy awarii drugiej
czesci; `--resolution 1m` rozstrzyga do PL. Bez `--vertical-crs`
pogranicze daje PL w EVRF2007 i CZ w Bpv.

Styk PL/CZ zmierzony na zywo 2026-09-29 (dane wejsciowe do R6; oba wycinki
w EPSG:2180): GUGiK wydaje dane ~200 m w glab CZ, CUZK ~118 m w glab PL, pas
wspolny ~310-350 m (Cieszyn, Karkonosze, Beskid Slaski, trojstyk PL-CZ-DE),
bez szczeliny tam, gdzie GUGiK ma produkt w danej rozdzielczosci (Karkonosze
5 m: brak arkuszy GUGiK — dziura 5,2 km² po stronie PL). Roznice wysokosci
PL - CZ (oba "EVRF2007": PL `EPSG:9651`, CZ `EPSG:5621`) w pasie wspolnym:
mediany -0,19..+0,14 m zaleznie od zbioru i spadku (trojstyk: 0,17 m),
koryto Olzy ~ -0,55 m (lustro wody); siatki PL (5 m: 5k + 2,5; 1 m: k + 0,5)
i CZ (warp kotwiczony w rogu NW zadania) nie sa wspolne.

### 4.7 LAZ (chmury punktow LIDAR, PL)

Osobny przeplyw CLI (`_cmd_download_laz`), poza `DownloadManager` — jedno
zadanie obszarowe daje wiele kafli. Wejscie (godlo do 1:10000, `--bbox`,
`--geometry`) sprowadzane jest do bboxa EPSG:2180, discovery idzie przez
**WFS** `GetFeature` (WMS skorowidzy LAZ zwraca 401 — ADR-021), a kafle
pobierane sa rownolegle. WFS `urn:ogc:def:crs:EPSG::2180` oczekuje
osi (N,E): bbox jest wysylany, a `gml:Envelope` czytany w tym
porzadku, potem kafle sa filtrowane rzeczywistym przecieciem.
GetCapabilities ustala roczniki (bez zaszytej listy); jesli
ktorykolwiek rocznik zawiedzie po ponowieniach, `discover_tiles`
rzuca `DownloadError` zamiast sugerowac brak kafli. Gdy wszystkie
odpowiedza i nic nie znaleziono, CLI drukuje `No LAZ tiles found`.
Porazka pobrania choc jednego kafla konczy polecenie kodem 1 z `Error:`
i PELNA lista nieudanych kafli (jak `_finish_pl_sheets`; udane kafle
zostaja na dysku i przy ponowieniu bez `--force` sa pomijane).
Godlo kafla jest drobniejsze niz 1:10000 i NIE jest
parsowane — `FileStorage.get_raw_path(..., uklad=tile.uklad)` buduje z niego
sama hierarchie katalogow. Uklad poziomy jest ustalany **per kafel**
wlasnoscia `LazTile.uklad` (jedno zrodlo prawdy dla CLI i biblioteki, zn. 8
review max), kaskada: `uklad_xy` kafla (`PL-2000:*` -> `2000`, `PL-1992*` ->
`1992`), potem format godla (kropki/myslniki), a na koncu fallback `2000`
z ostrzezeniem. Uklad pionowy bierze sie z flagi CLI (biblioteka:
`FileStorage(vertical_crs=)`). Jedno zadanie moze wiec zapisac kafle do dwoch
segmentow naraz — `{uklad}` rozwiazuje sie per wywolanie `get_raw_path`,
jeden `FileStorage` wystarcza na cale zadanie. W trybie obszarowym
`--country auto` obszar siegajacy CZ konczy sie bledem z podpowiedzia
`--country pl` (LAZ dla CZ to etap 2).

Wynik: `data/laz/pl_2000_evrf2007/6/162/34/02/3/<oryginalna_nazwa>.laz`
(+ `.meta.json` z `extra.godlo_kafla`/`rok`/`gestosc`/`url`).

### 4.8 Land cover i gleby (BDOT10k, CORINE, SoilGrids)

Bez zmian wzgledem 0.6.x. `LandCoverManager` ma **wlasny domyslny katalog**
(`./data/landcover`, CLI `--output`) i wlasna konwencje nazw plikow:
`<provider>_teryt_<teryt>.gpkg`, `<provider>_bbox_<minx>_<miny>_<maxx>_<maxy>.gpkg`
albo `<provider>_godlo_<godlo>.gpkg` (`_generate_output_path`). Wyjatek:
BDOT10k z `format="SHP"` (`--format SHP`) zapisuje oryginalne archiwum
GUGiK z shapefile'ami pod ta sama nazwa z rozszerzeniem `.zip`
(np. `bdot10k_teryt_1465.zip`, sidecar `bdot10k_teryt_1465.zip.meta.json`);
rozszerzenie nadaje `Bdot10kProvider.download_by_admin_unit`, a CLI drukuje
faktyczna sciezke (review 2026-10-06 N1). Szablony
segmentow z sekcji 3 tych zrodel NIE dotycza — ich deskryptory maja
`storage_subdir = None`. Sidecary pisze `LandCoverManager` tak samo jak
pozostale warstwy zarzadzajace. CORINE bez credentials CLMS pobiera podglad
PNG przez WMS (`extra.fallback = "wms_png"`), a `HSGCalculator` liczy grupy
glebowe z SoilGrids wg kanonicznego trojkata USDA (ADR-025).

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
   klasa parsera + rejestracja `SheetSystem` w `core/parser_registry.py`
   (`detect`, `parser_factory`, `path_parts`). Wzory: `ParserTM33` (siatka
   obliczalna) i `Sm5Sheet` (siatka wymagajaca indeksu). Fallback `pl1992`
   musi zostac ostatni — jego `detect` zawsze zwraca `True`.
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

## 6. Indeks ADR

Pelne uzasadnienia: `docs/DECISIONS.md`.

| ADR | Tytul | Streszczenie |
|---|---|---|
| ADR-001 | Flat layout zamiast src layout | Pakiet `kartograf/` lezy w korzeniu repo, bez warstwy `src/`. |
| ADR-002 | Auth Proxy do izolacji credentials CLMS | Klucze OAuth2 czyta wylacznie podproces `auth/proxy.py`; glowny proces rozmawia z nim po localhost HTTP. |
| ADR-003 | OpenData (ASC) vs WCS (GeoTIFF) — rozdzielenie sciezek pobierania NMT | Godlo zawsze daje ASC z OpenData, bbox GeoTIFF z WCS — sciezki rozdzielone, nie ujednolicane. **Czesc "bbox = WCS" juz nie obowiazuje:** CLI rozwija bbox PL na arkusze OpenData (sekcja 4.2) albo buduje z nich wycinek (ADR-027; od 2026-09-28 takze z biblioteki: `download_pl_cutout`), a WCS zostal przy `DownloadManager.download_bbox` i tylko dla KRON86. |
| ADR-004 | EVRF2007 jako domyslny uklad wysokosciowy | EVRF2007 domyslnie (aktualny standard PL), KRON86 pod `--vertical-crs`. |
| ADR-005 | Struktura katalogow NMT rozdzielona wg rozdzielczosci | Rozdzielono `data/1m` i `data/5m`, zeby ten sam arkusz w dwoch rozdzielczosciach nie nadpisywal sie — uklad zastapiony przez ADR-013, a nastepnie przez ADR-026. |
| ADR-006 | LandCoverProvider jako osobna hierarchia od BaseProvider | Pokrycie terenu ma inny interfejs niz NMT (dochodzi jednostka administracyjna), wiec dostaje wlasna klase bazowa. |
| ADR-007 | Migracja z black + flake8 na ruff | Jedno narzedzie (lint + format) zamiast dwoch, zgodnie ze standardami workspace. |
| ADR-008 | Kondensacja PROGRESS.md z 785 do ~80 linii | PROGRESS.md opisuje biezacy stan, historia zostaje w gicie i CHANGELOG-u. |
| ADR-009 | Rozbudowanie DEVELOPMENT_STANDARDS i IMPLEMENTATION_PROMPT | Oba pliki przepisane na pelna tresc zamiast odsylaczy do shared/standards. |
| ADR-010 | Algorytm find_sheets_for_bbox — hierarchiczne przycinanie bez WFS | Selekcja arkuszy to czysta matematyka siatki (1:1M -> 1:200k -> rekurencyjne przycinanie), zero zapytan sieciowych. |
| ADR-011 | GugikNmptProvider dziedziczy z GugikProvider | NMPT rozni sie od NMT tylko endpointami i nazwami warstw — zero duplikacji logiki pobierania. |
| ADR-012 | GugikOrtoProvider jako osobna klasa (nie dziedziczy z GugikProvider) | Ortofoto rozni sie zbyt mocno (brak pionu, inny format, plaska lista warstw), wiec dziedziczenie bylo nieczyste. |
| ADR-013 | Zmiana nazw podkatalogow storage z 1m/5m na nmt_1m/nmt_5m | Po dodaniu NMPT i orto same rozdzielczosci przestaly byc jednoznaczne. **Zastapiona przez ADR-026** (segmenty `<produkt>/<kraj>_<uklad>...`). |
| ADR-014 | BDOT10k category-based extraction (pt vs hydro) | Filtr warstw `pt`/`hydro` przy ekstrakcji ZIP-a. **Zastapiona przez ADR-016.** |
| ADR-015 | pyshp + sqlite3 zamiast fiona dla czytania geometrii | Do samych obwiedni per obiekt nie trzeba pelnego OGR — SHP przez pyshp, GPKG przez naglowek GeoPackage Binary. |
| ADR-016 | BDOT10k — usuniecie filtrowania po kategorii, pobieranie calego pliku | Filtrowanie po stronie klienta gubilo warstwy; pobierany jest caly ZIP i scalane wszystkie GPKG. |
| ADR-017 | PL-2000 sheet naming — composition pattern with auto-detection | `SheetParser` wykrywa format godla regexem i deleguje do `Parser2000`; BBox w natywnym CRS strefy. Odroczony w niej uklad katalogow `nmt_2000_<res>` zostal **domkniety przez ADR-026** (osobne segmenty `pl_2000_*`); sam wzorzec kompozycji obowiazuje dalej. |
| ADR-018 | ThreadPoolExecutor dla rownoleglego pobierania | Pobieranie hierarchii arkuszy idzie watkami; `max_workers=4` w CLI, 1 w bibliotece. |
| ADR-019 | SQLite WAL jako metadata cache | Rekordy skorowidza (pozytywne i potwierdzony brak pokrycia) w `record_cache`, TTL 7 dni; indeks arkuszy CZ w `sheet_cache` (30 dni); statystyka `record_count`. |
| ADR-020 | Walidacja warstw WMS przez GetCapabilities | Lazy discovery warstw, bez zaszytej listy fallback; bledy warstw daja `DownloadError`. |
| ADR-021 | LAZ (chmury punktow LIDAR) — discovery przez WFS, area-based | Osi WFS EPSG:2180 uzywa sie w porzadku (N,E), filtr przestrzenny chroni przed kaflami poza obszarem; lata z GetCapabilities. |
| ADR-022 | Architektura zrodel wielokrajowych — deskryptory, rejestry, sidecar, twarda polityka transformacji (etap 0) | Powstaja `sources/`, `sources/sidecar.py`, `transform/crs.py`, `transport/`, `core/parser_registry.py`; providery PL przenosza sie do `providers/pl/` bez shimow. |
| ADR-023 | Silnik CUZK, polityka ukladow CZ i EVRF2007 -> 5621 (etap 1) | `CuzkClient` jako pierwszy silnik sterowany deskryptorem, przeplyw CZ omija `DownloadManager`, `--country auto` z prostokatnych obwiedni, `extra.parent_request`. |
| ADR-024 | Reprojekcja tresci CZ wylacznie lokalnie | Serwer dostaje tylko natywny EPSG:5514; GDAL uzywa przypietej operacji czeskiej EPSG:1622/1623 (1,0 m). Kafelkowanie 4 Mpx i snap NW utrzymuja szwy i rozdzielczosc. |
| ADR-025 | Mapowanie tekstura -> HSG i kanoniczny trojkat USDA (audyt 0.7.0) | Progi tekstur to kanoniczne reguly USDA w jednej liscie (wersja wektorowa zrodlem prawdy); odstepstwa `TEXTURE_TO_HSG` od TR-55 sa swiadome i udokumentowane. |
| ADR-026 | Uklad `data/` per produkt + szablony `storage_subdir` | `data/<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/...`; `storage_subdir` staje sie szablonem z `{uklad}`/`{vcrs}`, a `FileStorage` odrzuca segment z nierozwiazana klamra. |
| ADR-027 | `--target-crs` dla PL jako scalony wycinek | R5 obejmuje wycinek i liste/hierarchie; EPSG:2180 wymaga zgodnej fazy (`GridMismatchError`), W1 warpuje kazdy arkusz osobno przy innym CRS. Sidecar: `missing_sheets`, `sheet_sources`, `off_grid_sheets`. |
| ADR-028 | Wybor rekordu skorowidza GUGiK i `extra.source` | Twardy filtr godla, ukladu, rozdzielczosci i koloru orto; najnowsza kampania bez cichego fallbacku; cache pelnych rekordow i pochodzenie w sidecarze. |

ADR-026–028 sa spisane w `docs/DECISIONS.md` w ramach wydania 0.7.0.
