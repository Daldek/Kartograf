# Architektura Kartografa

**Data:** 2026-08-28
**Wersja opisywana:** 0.7.0 (develop, przed tagiem)

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
`DownloadManager`, `LandCoverManager` i CLI (tory LAZ, CZ oraz wycinek PL) —
nigdy providery; provider zwraca `Path`, metadane skladane sa pietro wyzej,
gdzie znany jest kontekst zadania. Zapis sidecara jest best-effort: kazdy blad
(IO, brakujacy klucz deskryptora, wyjatek w budowie metadanych) konczy sie
`logger.warning`, nigdy przerwaniem pobrania — dane sa wazniejsze niz metadane.
Jedyny przypadek braku sidecara przy sukcesie to provider bez `descriptor_key`
(`DownloadManager._write_sidecar` wraca wtedy po cichu).

**Polityka transformacji (ADR-024).** Transformacje wspolrzednych w kodzie
etapu 0+ przechodza wylacznie przez `kartograf/transform/crs.py`, ktory ma
cztery twarde reguly: (1) transformer budowany tylko przez
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
z `axis_info`, nie zakladana.

**Brak scalania miedzykrajowego.** Zadanie obszarowe przecinajace wiecej niz
jeden kraj daje **osobne pliki i osobne sidecary per kraj**, powiazane wspolnym
`extra.parent_request`. Kartograf nie sklada mozaiki transgranicznej i nie
harmonizuje pionu miedzy krajami — to swiadomy kontrakt z Hydrografem, ktory
ma pelen kontekst modelu i scala dane u siebie (docstring
`kartograf/sources/sidecar.py`). Kartograf dostarcza natomiast wszystko, czego
takie scalenie wymaga: jawne kody CRS obu osi, `nodata`, opis uzytej operacji
z dokladnoscia i wspolny klucz grupowania.

---

## 2. Warstwy i zaleznosci modulow

Ponizszy graf zostal ZMIERZONY na drzewie importow (AST wszystkich plikow
`kartograf/**/*.py`, krawedzie miedzypakietowe), nie zalozony:

```
cli ──> download, landcover, hydrology, providers, sources,
        transform, transport, core, cache
download ──> providers, sources, core
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

Dwie uwagi, ktore latwo przeoczyc:

- `core` ma **jeden leniwy** import w druga strone:
  `parser_registry._make_parser_cz_sm5` siega po
  `providers.cuzk.sheets.Sm5Sheet` dopiero w momencie wywolania. Odroczenie
  jest celowe (komentarz w kodzie) — przy imporcie `core` nie ciagnie
  providerow ani ich zaleznosci IO, wiec warstwa pozostaje czysta dla
  wszystkiego poza budowa parsera arkusza SM5.
- `download` NIE importuje `transport` ani `transform`. Mozaika i warp
  wycinka PL zyja w CLI (`cli/download_cmd.py`), ktore wola je wprost;
  `DownloadManager` pozostaje warstwa koordynacji arkuszy.

### Moduly

```
kartograf/
├── __init__.py          # Public API (BBox, SheetParser, DownloadManager, providery, ...)
├── exceptions.py        # KartografError, ParseError, ValidationError, DownloadError
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
│   ├── http.py          # download_to — zapis atomowy + retry z backoffem
│   └── mosaic.py        # mosaic_and_crop — merge rastrow + przyciecie, propagacja nodata
├── providers/           # Providery danych
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider, LandCoverProvider
│   ├── pl/              # GUGiK: gugik.py (NMT), gugik_nmpt.py, gugik_orto.py,
│   │                    # gugik_laz.py, bdot10k.py, __init__.py (create_nmt_provider)
│   ├── cuzk/            # CUZK: client.py (silnik sterowany deskryptorem),
│   │                    # sheets.py (indeks SM5/TM33), dmr.py, __init__.py (create_dmr_provider)
│   ├── corine.py        # CORINE z Copernicus CLMS (+ fallback WMS PNG)
│   └── soilgrids.py     # SoilGrids z ISRIC (WCS)
├── cache/metadata.py    # MetadataCache — SQLite WAL, TTL 7 dni (sheet_cache 30 dni), thread-safe
├── download/            # Pobieranie NMT/NMPT/Orto po godle
│   ├── manager.py       # DownloadManager — koordynacja arkuszy (ThreadPoolExecutor), sidecary
│   └── storage.py       # FileStorage — segmenty katalogow z szablonow (ADR-026)
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
| `pl.gugik.orto` | `orto/pl_{uklad}` | `.tif` |
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

Kto wypelnia ktory placeholder:

| Placeholder | Kto wypelnia | Kiedy |
|---|---|---|
| `{vcrs}` | konstruktor `FileStorage(vertical_crs=)` albo jawne `resolve_subdir(vertical_crs=)` | raz, na starcie zadania — uklad pionowy jest wlasnoscia zadania, nie arkusza |
| `{uklad}` | `FileStorage` per identyfikator (`get_path`/`get_raw_path`/`exists`/`delete`/`ensure_directory`), regula ta sama co `parser_registry.path_parts`: kropki -> `2000`, reszta -> `1992` | przy budowie kazdej sciezki |
| `{uklad}` (jawnie) | tor LAZ: `LazTile.uklad` (kaskada `uklad_xy` kafla -> format godla -> "2000") przez `FileStorage.get_raw_path(..., uklad=)` — jedno zrodlo prawdy dla CLI i biblioteki (zn. 8, review max); wycinek PL (`uklad="1992"` na stale — `--target-crs` z `--system 2000` jest odrzucane) | przed utworzeniem `FileStorage` / sciezki wycinka |

`FileStorage` waliduje wynik koncowy: segment, w ktorym po wypelnieniu zostala
klamra `{`, konczy sie `ValidationError` z nazwa brakujacego wymiaru
(`_ensure_resolved`). Cichy katalog `pl_{uklad}_1m_evrf2007` nigdy nie powstanie.

### 3.2 Schema sidecara `kartograf-meta/1`

Kazde udane pobranie zapisuje **dwa** pliki: dane i `<plik>.meta.json`.

| Pole | Znaczenie |
|---|---|
| `dataset` | klucz deskryptora zrodla (np. `pl.gugik.nmt_1m`) |
| `country`, `product`, `provider` | kraj, produkt i nazwa dostawcy z deskryptora |
| `horizontal_crs` | uklad poziomy FAKTYCZNEGO pliku: PL arkusze `EPSG:2180`; CZ natywnie `EPSG:5514`, kafel TM33 pobrany godlem `EPSG:3045`; po `--target-crs` (PL i CZ) uklad docelowy |
| `vertical_crs` | kod realizacji ukladu pionowego: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007); `null` gdy produkt nie ma pionu (orto) |
| `vertical_source` | `native` / `ellipsoidal` / `server` (z `AccessChannel`) |
| `resolution` | rozdzielczosc z deskryptora (`1m`/`5m`/`2m`) albo `null` |
| `nodata` | wartosc pustego piksela: dla `.asc` czytana automatycznie z naglowka (`read_asc_nodata`), w torze CZ podawana przez CLI z tagu GeoTIFF (`_read_tif_nodata`, fallback `CUZK_NODATA`), dla wycinka PL stala `-9999.0`; `null` gdy zadna z tych drog nie ma zastosowania (np. orto) |
| `request` | oryginalne zadanie: `{"godlo": ...}`, `{"bbox": [...], "bbox_crs": ...}` albo `{"teryt": ...}` (BDOT10k/landcover) |
| `license` | `{id, attribution, url}` z deskryptora |
| `downloaded_at`, `kartograf_version` | znacznik czasu UTC (ISO 8601, sekundy) i wersja pakietu |
| `transform` | slownik osi (`horizontal`/`vertical`) z opisem uzytej operacji w formacie `pinned: <opis> (<dokladnosc> m)`; os bez przeliczenia nie ma klucza, a bez zadnego przeliczenia cale pole to `null` |
| `extra` | slownik dodatkowy: `parent_request` w trybie obszarowym (ale NIE w torze LAZ — sekcja 3.4); w torze LAZ zamiast niego `godlo_kafla`/`rok`/`gestosc`/`url`; dla SM5 dodatkowo `mapname`/`podil` |
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
kanal, ktorym te dane nie przyszly. Po zbudowaniu rekordu CLI nadpisuje
`horizontal_crs` na uklad docelowy i ustawia
`transform = {"horizontal": "pinned: <opis> (<dokladnosc> m)"}`; dla
`--target-crs EPSG:2180` (sam crop, bez warpa) `transform` to `null`.

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
   Konwencja wspolna dla PL i CZ, ale nie kazde zadanie obszarowe daje
   wycinek: CZ zawsze (`exportImage`), PL **tylko z `--target-crs`** —
   bez tej flagi zadanie PL zapisuje arkusze w hierarchii godel
   (sekcja 4.2 vs 4.3).
4. Rozdzielczosc wchodzi do segmentu tylko tam, gdzie jest parametrem API
   (NMT/NMPT). Nie ma jej dla CZ (`dmr5g` to z definicji 2 m, `dmr4g` 5 m)
   ani dla orto/LAZ (brak takiego parametru).

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
uklad i kraje faktycznie odpytane w tym wywolaniu. To jest klucz grupowania:
po nim konsument (Hydrograf, przyszly `find_downloaded`) sklada w calosc
pliki jednego zadania, takze te lezace po obu stronach granicy, ktore
Kartograf swiadomie zostawia rozdzielone (sekcja 1). Slownik jest wspoldzielony
przez referencje miedzy sidecarami zadania i **nie moze byc mutowany** po
utworzeniu.

---

## 4. Przeplywy per produkt

### 4.1 Godlo PL (NMT/NMPT/Orto)

`SheetParser` waliduje i normalizuje godlo; godlo PL-1992 grubsze niz 1:10000
rozwija sie do arkuszy 1:10000 (`download_hierarchy`), godlo PL-2000
pobierane jest bezposrednio. Dla kazdego arkusza `GugikProvider` pyta WMS
skorowidz (`GetFeatureInfo`, warstwy walidowane przez `GetCapabilities` —
ADR-020) o URL pliku OpenData, wynik URL-a jest cache'owany w SQLite
(`MetadataCache`, TTL 7 dni), po czym plik jest pobierany z retry i zapisany
atomowo. `DownloadManager` pisze sidecar po kazdym udanym arkuszu.
`--target-crs` w trybie godlowym jest **odrzucane** (kod 1) — tryb godlowy
dostarcza dane natywne 1:1.

Wynik: `data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
(+ `.meta.json`); dla NMPT `data/nmpt/pl_1992_1m_evrf2007/...`, dla orto
`data/orto/pl_1992/...`.

### 4.2 Bbox / geometria PL bez `--target-crs`

Bbox trafia do `_dispatch_area`, ktore rozstrzyga kraje (sekcja 4.6), a czesc
polska idzie do `_download_pl_bbox`. `find_sheets_for_bbox` (czysta matematyka
siatki, bez zapytan sieciowych — ADR-010) daje liste godel 1:10000, ktore
pobiera `DownloadManager` rownolegle. W trybie `--geometry` arkusze wyznacza
sama geometria per obiekt (`find_sheets_for_geometry`), nie jej obwiednia.
Kazdy sidecar dostaje `extra.parent_request`. Nieudany arkusz konczy polska
czesc zadania kodem 1 (o koncowym kodzie wyjscia rozstrzyga jeszcze dyspozycja
— sekcja 4.6).

Wynik: **wiele plikow** — lista arkuszy w segmencie jak w 4.1. To jest
asymetria wzgledem CZ, gdzie bbox daje jeden wycinek.

### 4.3 Bbox / geometria PL z `--target-crs` (ADR-027)

Nowosc 0.7.0, produkt `nmt`, tryby `--bbox` i `--geometry`. Kolejnosc krokow
w `_prepare_pl_cutout` -> `_download_pl_bbox`/`_download_pl_geometry` ->
`_finalize_pl_cutout`:

1. **Fail-fast przed siecia.** Bbox normalizowany do EPSG:2180, po czym dla
   pary `EPSG:2180 -> --target-crs` budowana jest operacja przypieta
   (polityka: `min_accuracy_m=1.0`, bez siatek z sieci, probe w srodku
   zadania). Brak bezpiecznej operacji = blad z remedium, zanim cokolwiek
   pojdzie w siec.
2. **Zapas po stronie zrodla.** Obwiednia celu wraca do EPSG:2180 (obrot
   ukladu docelowego robi ja wieksza niz samo zadanie) i dostaje jeszcze
   `_PL_WARP_MARGIN_PX = 4` piksele marginesu na halo interpolatora bilinear.
   Ten powiekszony bbox — nie zadanie uzytkownika — steruje cropem mozaiki
   ORAZ selekcja arkuszy, i to w OBU trybach: `--bbox` podaje go wprost
   (`sheet_bbox = cutout.bbox_source_2180`), a `--geometry` dorzuca wynik
   `find_sheets_for_bbox(cutout.bbox_source_2180, ...)` do godel geometrii
   (suma mnogosciowa). Siatki wyniku zapas NIE dotyczy: `warp_to_grid` liczy
   `width`/`height`/`dst_transform` wylacznie z `bbox_target`, wiec zasieg
   pliku rowna sie obwiedni zadania w ukladzie docelowym (zmierzone: 186 x 94
   px, `bounds == bbox_target`) — zgodnie z nazwa pliku, ktora tez pochodzi
   z `bbox_target`. Lustro `_native_request_bbox` toru CZ. Zapas nie jest
   ostroznoscia na wyrost: bez niego zmierzony wycinek do EPSG:5514 mial
   **17,4 % pikseli nodata** (3034 z 17484) na krawedziach, a w trybie
   `--geometry` bez sumy godel — **50,1 %** (8756 z 17484).
3. **Arkusze jako cache.** Arkusze pobieraja sie normalnie do swoich
   segmentow (`skip_existing` dziala standardowo) i zostaja na dysku wraz
   z wlasnymi sidecarami. Kazdy nieudany arkusz konczy polska czesc zadania
   kodem 1 (bez budowy wycinka) — wycinek wymaga kompletu pokrycia.
4. **Mozaika + crop.** `mosaic_and_crop` skleja arkusze i przycina do bboxa
   z zapasem; wymuszany jest profil `GTiff` + `EPSG:2180`, bo arkusze ASC
   nie niosa CRS. Nodata: `-9999.0`.
5. **Warp.** `transform/raster.py::warp_to_grid` reprojektuje mozaike na
   siatke wyniku z WYMUSZONA operacja przypieta. Wymuszenie nie jest
   ozdobne: na torze PL bez `COORDINATE_OPERATION` wierzcholek ucieka
   o ~122 m, a bez korekty osi (`axisswap`) wynik ma ZERO waznych pikseli.
   `warp_to_grid` dodatkowo sprawdza, czy para ukladow zgadza sie z
   `pinned` — wymuszona operacja czyni bowiem `src_crs` martwym dla GDAL-a.
   Dla `--target-crs EPSG:2180` warp jest pomijany: zostaje sam crop
   (`os.replace`), a sidecar ma `transform: null`.
6. **Sidecar** wg 3.2, z `parent_request`.

**Nieudana budowa a poprzedni wynik.** Obie sciezki zapisu sa atomowe
(`os.replace` przy samym cropie, wewnetrzny `os.replace` w `warp_to_grid`),
wiec przerwana budowa nie zostawia pod finalna sciezka polzapisanego pliku.
Skoro tak, ZADNE ogniwo toru PL nie kasuje poprzedniego wyniku: ani
`_build_pl_cutout`, ani `transform/raster.py::warp_to_grid` — stary plik
przezywa awarie, a sciezka sukcesu jest identyczna. Kasowanie bylo tu czysta
utrata danych — pod `--country auto` cale zadanie moglo skonczyc sie kodem 0
(bo drugi kraj sie udal), zostawiajac uzytkownika bez pliku, ktory mial
wczesniej. Obietnica obejmuje wiec takze `--target-crs EPSG:5514`/`EPSG:3045`,
czyli glowne zastosowanie flagi. Wlasne `except BaseException:
dst.unlink(missing_ok=True)` ma dalej wylacznie tor CZ
(`providers/cuzk/dmr.py::_warp_to_grid`, niezalezna kopia funkcji) — tam jest
ono rownie zbedne (zapis idzie przez plik tymczasowy), ale to kod zweryfikowany
na zywo, ktorego tuz przed wydaniem nie ruszamy (ADR-024). Bez `--force`
sytuacja i tak nie wystepuje, bo skrot "plik juz istnieje" wraca wczesniej.

W trybie `--geometry` wycinek obejmuje **CALA obwiednie geometrii, bez
maskowania do jej obiektow** — do warstwy rastrowej ida same sciezki arkuszy
i bbox. `nodata` pojawia sie wylacznie tam, gdzie nie siega zaden POBRANY
arkusz, i nigdy nie oznacza maskowania. Dlatego przy `--target-crs` innym niz
EPSG:2180 arkusze to SUMA godel geometrii i godel obwiedni z zapasem —
obietnice "cala obwiednia" wypelniaja dane, a nie ramka dziur. **Swiadomy
koszt:** przy rzadkiej geometrii wieloobiektowej suma obejmuje arkusze CALEJ
obwiedni, takze te, ktorych nie przecina zaden obiekt — a arkusz jest mniejszy,
niz sugeruje etykieta: godlo 7-czlonowe nazywane w Kartografie "1:10000" ma
w EPSG:2180 **~2,25 x 2,43 km** (zmierzone: `N-34-130-D-d-2-4` -> 2252,6 x
2432,4 m; GUGiK nazywa ten sam arkusz modulem archiwizacji 1:5000 — patrz
Notes w `core/sheet_parser.py`), wiec obwiednia rzedu kilkudziesieciu
kilometrow to juz setki arkuszy. Dla `--target-crs EPSG:2180` (sam crop, bez
warpa) sumy nie ma: arkusze wyznacza sama geometria, wiec miedzy odleglymi
obiektami moze zostac pas `nodata`.

Wylaczenia (kod 1 z komunikatem): `--target-crs` z `--product nmpt|orto|laz`
oraz z `--system 2000` (bbox wielostrefowy dalby arkusze w EPSG:2176-2179;
mozaika miedzystrefowa to etap 2) — walidacja w `_resolve_pl_sentinels`;
`--target-crs` z godlem odrzuca warstwa wyzej, `cmd_download` (dla CZ
`_cmd_download_cz`, wyjatkiem tlumaczonym przez `_run_cz`), bo tryb godlowy
rozstrzyga sie przed wejsciem w sentinele PL. Dopuszczalne wartosci flagi to
`EPSG:2180`, `EPSG:5514`, `EPSG:3045`.

Wynik: **jeden plik** `data/nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`
(+ `.meta.json`), np. dla bboxa 419000,230000,421000,232000 w EPSG:2180
z `--target-crs EPSG:5514`:
`data/nmt/pl_1992_1m_evrf2007/bbox/-499122.4858_-1088442.412_-496975.1716_-1086295.098.tif`.

### 4.4 Godlo CZ (DMR 5G / DMR 4G)

Godlo TM33 (`302_5550`) rozwija `ParserTM33` do bboxa w EPSG:3045; do serwera
CUZK idzie zadanie `exportImage` **wylacznie w ukladzie natywnym EPSG:5514**
(plus zapas 4 px), a na siatke kafla przenosi je lokalny warp przypieta
operacja (ADR-024 — serwerowa reprojekcja gubila datum shift). Godlo SM5
(`CTES96`) to gotowy plik z openzu, juz w EPSG:5514, bez warpa — po pobraniu
nadpisywane sa tylko metadane CRS. `--vertical-crs EVRF2007` dokleja przypieta
transformacje pionowa Bpv -> EPSG:5621 (przesuniecie w miejscu). `KRON86` dla
CZ jest nieosiagalny (brak publicznych siatek). Sidecar pisze CLI.

Wynik: `data/nmt/cz_dmr5g_bpv/302/5550/302_5550.tif` (`horizontal_crs`
EPSG:3045) albo `data/nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif`
(`horizontal_crs` EPSG:5514).

### 4.5 Bbox CZ

Jeden wycinek `exportImage`. Bbox jest najpierw normalizowany do ukladu WYNIKU
(`--target-crs` albo natywny EPSG:5514), zeby nazwa pliku niosla wspolrzedne
faktycznie zadanego wycinka. Zadanie do serwera idzie natywnie; przy
`--target-crs` innym niz 5514 tresc reprojektuje lokalny warp. Bboxy wieksze
niz limit `exportImage` (**asymetryczny 15000 x 4100 px**) sa kafelkowane po
stronie klienta i scalane przez `mosaic_and_crop` — kafelkowanie dzieje sie
PRZED warpem, w ukladzie natywnym, wiec szew nie zostaje utrwalony przez
interpolacje.

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

### 4.7 LAZ (chmury punktow LIDAR, PL)

Osobny przeplyw CLI (`_cmd_download_laz`), poza `DownloadManager` — jedno
zadanie obszarowe daje wiele kafli. Wejscie (godlo do 1:10000, `--bbox`,
`--geometry`) sprowadzane jest do bboxa EPSG:2180, discovery idzie przez
**WFS** `GetFeature` (WMS skorowidzy LAZ zwraca 401 — ADR-021), a kafle
pobierane sa rownolegle. Godlo kafla jest drobniejsze niz 1:10000 i NIE jest
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
albo `<provider>_godlo_<godlo>.gpkg` (`_generate_output_path`). Szablony
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
   test wychodzacy w siec poza loopback.

---

## 6. Indeks ADR

Pelne uzasadnienia: `docs/DECISIONS.md`.

| ADR | Tytul | Streszczenie |
|---|---|---|
| ADR-001 | Flat layout zamiast src layout | Pakiet `kartograf/` lezy w korzeniu repo, bez warstwy `src/`. |
| ADR-002 | Auth Proxy do izolacji credentials CLMS | Klucze OAuth2 czyta wylacznie podproces `auth/proxy.py`; glowny proces rozmawia z nim po localhost HTTP. |
| ADR-003 | OpenData (ASC) vs WCS (GeoTIFF) — rozdzielenie sciezek pobierania NMT | Godlo zawsze daje ASC z OpenData, bbox GeoTIFF z WCS — sciezki rozdzielone, nie ujednolicane. **Czesc "bbox = WCS" juz nie obowiazuje:** CLI rozwija bbox PL na arkusze OpenData (sekcja 4.2) albo buduje z nich wycinek (ADR-027), a WCS zostal przy `DownloadManager.download_bbox` i tylko dla KRON86. |
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
| ADR-019 | SQLite WAL jako metadata cache | Cache URL-i i TERYT w SQLite (WAL, TTL 7 dni, `threading.Lock` na zapisach), zero nowych zaleznosci. |
| ADR-020 | Walidacja warstw WMS przez GetCapabilities | Hardcoded nazwy warstw sa porownywane z live przy pierwszym uzyciu i auto-korygowane; wynik cache'owany w pamieci providera. |
| ADR-021 | LAZ (chmury punktow LIDAR) — discovery przez WFS, area-based | WMS skorowidzy LAZ zwraca 401, wiec discovery idzie WFS-em; godlo kafla jest nieparsowalna etykieta, sciezke buduje `get_raw_path`. |
| ADR-022 | Architektura zrodel wielokrajowych — deskryptory, rejestry, sidecar, twarda polityka transformacji (etap 0) | Powstaja `sources/`, `sources/sidecar.py`, `transform/crs.py`, `transport/`, `core/parser_registry.py`; providery PL przenosza sie do `providers/pl/` bez shimow. |
| ADR-023 | Silnik CUZK, polityka ukladow CZ i EVRF2007 -> 5621 (etap 1) | `CuzkClient` jako pierwszy silnik sterowany deskryptorem, przeplyw CZ omija `DownloadManager`, `--country auto` z prostokatnych obwiedni, `extra.parent_request`. |
| ADR-024 | Reprojekcja tresci CZ wylacznie lokalnie (zakaz `imageSR` != natywny) | Serwer CUZK dostaje zadania rastrowe tylko w ukladzie natywnym EPSG:5514 (+ zapas 4 px), a reprojekcje robi lokalny warp z WYMUSZONA operacja przypieta — serwerowa gubila datum shift (135 m). |
| ADR-025 | Mapowanie tekstura -> HSG i kanoniczny trojkat USDA (audyt 0.7.0) | Progi tekstur to kanoniczne reguly USDA w jednej liscie (wersja wektorowa zrodlem prawdy); odstepstwa `TEXTURE_TO_HSG` od TR-55 sa swiadome i udokumentowane. |
| ADR-026 | Uklad `data/` per produkt + szablony `storage_subdir` | `data/<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/...`; `storage_subdir` staje sie szablonem z `{uklad}`/`{vcrs}`, a `FileStorage` odrzuca segment z nierozwiazana klamra. |
| ADR-027 | `--target-crs` dla PL jako scalony wycinek | Bbox/geometria PL z `--target-crs` daje jeden GeoTIFF: arkusze jako cache, `mosaic_and_crop`, lokalny warp przypieta operacja, sidecar z `transform.horizontal`. |

ADR-026 i ADR-027 sa spisane w `docs/DECISIONS.md` w ramach tego samego
wydania 0.7.0.
