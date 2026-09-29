# Architektura Kartografa

**Data:** 2026-09-29
**Wersja opisywana:** 0.7.0 (develop, przed tagiem)

Stan po testach na zywych danych 2026-09-29: opisane nizej mechanizmy zostaly
potwierdzone na zywo, a znane bledy kodu (K1-K6, S1-S5, N1-N9) sa zaznaczone
w miejscu, ktorego dotycza — tabela, waga i decyzja o naprawie:
`docs/PROGRESS.md`, "Znane bledy (testy na zywo 2026-09-29)"; raporty testow
(L1-L7) i audytu (D1, D2): `docs/research/2026-09-29-live-e2e-i-audyt-docs/`.
Tekst nie opisuje tych zachowan jako zamierzonych.

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
Poza bledem zapisu (wtedy `logger.warning`) jedyny CICHY przypadek braku
sidecara przy sukcesie to provider bez `descriptor_key`
(`DownloadManager._write_sidecar` wraca wtedy po cichu). Arkusz pominiety
jako juz pobrany zachowuje swoj poprzedni sidecar — takze bez
`extra.parent_request` nowego zadania (znany blad N4).

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
z `axis_info`, nie zakladana. Sposrod operacji, ktore przeszly reguly
(1)-(3), wybierana jest najdokladniejsza (`min` po `accuracy`), bez
sprawdzenia jej obszaru uzycia: dla S-JTSK -> ETRS89 jest to dzis
EPSG:4829 (Slowacja, 0,5 m), a nie EPSG:1622 (Czechy, 1,0 m) — tresc CZ po
reprojekcji i wycinek PL -> EPSG:5514 sa przesuniete do ~5 m (wzdluz granicy
PL-CZ 1,1-3,4 m), a sidecar deklaruje 0,5 m (znany blad K2; errata
ADR-024).

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
│   ├── http.py          # download_to — zapis atomowy + retry z backoffem
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
| `horizontal_crs` | uklad poziomy pliku: PL arkusze `EPSG:2180`; CZ natywnie `EPSG:5514`, kafel TM33 pobrany godlem `EPSG:3045`; po `--target-crs` (PL i CZ) uklad docelowy. Pole bierze sie z kanalu deskryptora, nie z pliku: arkusz PL-2000 (strefa 2176-2179) tez dostaje `EPSG:2180` (znany blad N8) |
| `vertical_crs` | kod realizacji ukladu pionowego: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007); `null` gdy produkt nie ma pionu (orto) |
| `vertical_source` | `native` / `ellipsoidal` / `server` (z `AccessChannel`) |
| `resolution` | rozdzielczosc z deskryptora (`1m`/`5m`/`2m`) albo `null` |
| `nodata` | wartosc pustego piksela: dla `.asc` czytana automatycznie z naglowka (`read_asc_nodata`), w torze CZ podawana przez CLI z tagu GeoTIFF (`_read_tif_nodata`; w trybie bbox z fallbackiem `CUZK_NODATA`), dla wycinka PL stala `-9999.0`; `null` gdy zadna z tych drog nie ma zastosowania (np. orto) |
| `request` | zadanie, ktore dal TEN plik: `{"godlo": ...}` (arkusz/kafel, takze arkusze PL z trybu obszarowego), `{"bbox": [...], "bbox_crs": ...}` (wycinek CZ i PL — obwiednia w ukladzie WYNIKU, po przycieciu do kraju i transformacji; LAZ — bbox w EPSG:2180) albo `{"teryt": ...}` (BDOT10k/landcover); oryginalne zadanie uzytkownika niesie `extra.parent_request` (3.4). Sidecar arkusza PL nie zapisuje URL-a ani daty kampanii (po fakcie nie da sie sprawdzic, ktora edycje pobrano — istotne przy K3/K4); tor LAZ zapisuje `extra.url` |
| `license` | `{id, attribution, url}` z deskryptora |
| `downloaded_at`, `kartograf_version` | znacznik czasu UTC (ISO 8601, sekundy) i wersja pakietu |
| `transform` | slownik osi (`horizontal`/`vertical`) z opisem uzytej operacji w formacie `pinned: <opis> (<dokladnosc> m)`; os bez przeliczenia nie ma klucza, a bez zadnego przeliczenia cale pole to `null` |
| `extra` | slownik dodatkowy: `parent_request` w trybie obszarowym (ale NIE w torze LAZ — sekcja 3.4); w torze LAZ zamiast niego `godlo_kafla`/`rok`/`gestosc`/`url`; dla SM5 dodatkowo `mapname`/`podil`; wycinek PL dodatkowo `missing_sheets` — posortowana lista godel bez danych GUGiK, w ich miejscu nodata (tylko gdy niepusta, sekcja 4.3) |
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
   (`warp_to_grid` PL, `_warp_to_grid` CZ) ma calkowita liczbe pikseli
   liczona od naroznika NW, wiec jej krawedz E i S moze odbiegac o do 0,5 px
   (sekcja 4.3).
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
uklad i kraje faktycznie odpytane w tym wywolaniu (probowane, nie pobrane).
W trybie `--geometry` "zadanie" to obwiednia geometrii: dla pliku w ukladzie
czeskim (EPSG:5514/3045) w ukladzie PLIKU (od 2026-09-28), dla pozostalych
w EPSG:2180; jawne `--country cz` zapisuje obwiednie w ukladzie zadania CZ
(EPSG:5514 albo `--target-crs`). Klucz buduje CLI (`_build_parent_request`);
API biblioteki (`download_pl_cutout`, `run_pl_cutout`) zapisuje go tylko,
gdy wolajacy poda `parent_request=` — bez niego oryginal zadania nie trafia
do zadnego sidecara. Arkusze pominiete jako juz pobrane zachowuja poprzedni
sidecar, wiec grupa bywa niepelna (znany blad N4). To jest klucz grupowania:
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
kazdego arkusza `GugikProvider` pyta WMS skorowidz (`GetFeatureInfo`, warstwy
walidowane przez `GetCapabilities` — ADR-020) o URL pliku OpenData, po czym
plik jest pobierany z retry (3 proby) i zapisany atomowo. Zapytania
skorowidza nie maja ponowien, a bez wstrzyknietej sesji kazdy arkusz dostaje
nowa `requests.Session` (nowe polaczenie; zapytania warstw jednego arkusza
dziela ja) — znany blad S1. URL moze byc cache'owany w SQLite
(`MetadataCache`, TTL 7 dni), ale tylko gdy wolajacy przekaze `cache=` do
providera (np. `create_nmt_provider(cache=MetadataCache())`) — CLI
i domyslne sciezki biblioteki (`DownloadManager`, `download_pl_cutout`)
tworza providery PL bez cache, wiec kazde pobranie arkusza odpytuje
skorowidz (`MetadataCache` w CLI uzywa tylko tor CZ — indeks SM5; znany blad
N6). Wybor pliku ma znane bledy: chwilowy blad nowszej warstwy daje po cichu
URL starszej kampanii (K3), a wygrywa pierwszy URL zawierajacy godlo, bez
wzgledu na rozdzielczosc, date i zasieg (K4 — sekcja 4.3 krok 4).
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
Sidecar kazdego pobranego arkusza dostaje `extra.parent_request` (arkusz
pominiety jako juz pobrany — nie, N4). Nieudany arkusz konczy polska
czesc zadania kodem 1 (o koncowym kodzie wyjscia rozstrzyga jeszcze dyspozycja
— sekcja 4.6).

Tryb listy nie ma tolerancji R5 (znany blad S2, potwierdzony na zywo
2026-09-29 na morzu i na wszystkich granicach): arkusz bez danych GUGiK
(`NoCoverageError` — morze, arkusz za granica) jest tu zwykla porazka.
Lista 1:10000 idzie przez `download_sheet` per godlo
(`_download_godlo_list`): przy `--workers 1` pierwsza porazka przerywa liste
(zmierzone: 0 plikow, gdy pierwszy arkusz lezy za granica), przy
`--workers > 1` CLI zglasza pierwsza porazke wg kolejnosci ukonczenia,
a pozostale arkusze pobieraja sie do konca bez raportu ich porazek. Pod
`--country auto` z sukcesem CZ czesciowy sukces PL raportowany jest jako
"nie pobrano danych z PL", choc arkusze PL sa na dysku. Tolerancje R5 (nodata
+ `missing_sheets`) ma tylko wycinek `--target-crs` (4.3); backlog: przejscie
trybu listy na `DownloadManager.download_sheets`.

Wynik: **wiele plikow** — lista arkuszy w segmencie jak w 4.1. To jest
asymetria wzgledem CZ, gdzie bbox daje jeden wycinek.

### 4.3 Bbox / geometria PL z `--target-crs` (ADR-027)

Nowosc 0.7.0, produkt `nmt`, tryby `--bbox` i `--geometry`: wynik to JEDEN
GeoTIFF zamiast listy arkuszy. Od 2026-09-28 (R3) caly tor zyje w bibliotece
— `kartograf/download/cutout.py`, eksport w `kartograf`:

- `download_pl_cutout(bbox, target_crs, *, output_dir, resolution,
  vertical_crs, geometry, layer, scale, max_workers, force, on_progress,
  parent_request) -> PlCutoutResult` — jedno wywolanie: provider z fabryki
  `create_nmt_provider` (regula 5m => EVRF2007 z ostrzezeniem w logu),
  `prepare_pl_cutout`, skrot "plik istnieje", `select_pl_cutout_sheets`,
  `run_pl_cutout`. Tryb geometrii: `bbox` = obwiednia geometrii (np.
  `get_overall_bbox(plik, target_crs="EPSG:2180")`), `geometry` = plik
  SHP/GPKG.
- te same kroki osobno — dla wolajacego z wlasnym providerem albo
  `FileStorage`: `prepare_pl_cutout` -> `PlCutout` (zero sieci) ->
  `select_pl_cutout_sheets` -> `PlCutoutSheets` (zero sieci) ->
  `run_pl_cutout` -> `PlCutoutResult` (`path`, `skipped`, `sheet_paths`,
  `missing_sheets`).

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
   `GugikProvider`, gdy WSZYSTKIE warstwy skorowidza odpowiedzialy i zadna
   nie ma arkusza (morze, zagraniczna strona bboxa przygranicznego — CZ, DE,
   SK/UA/BY/LT/RU — dziury pokrycia); awaria czesci warstw przy braku
   arkusza w pozostalych to zwykly `DownloadError` ("brak pokrycia
   niepewny"). Warstwy sa odpytywane od najnowszej, bez ponawiania — gdy
   zapytanie nowszej warstwy padnie (blad transportu albo raport OGC),
   a starsza ma arkusz, provider zwraca URL STARSZEJ edycji (tylko
   `logger.warning`), wiec arkusz i wycinek niosa starszy nalot bez sladu
   w sidecarze, a arkusz zostaje w cache (znany blad K3; na zywo: dwa
   przebiegi `--force` tego samego wycinka 5 m roznily sie w 21 % pikseli,
   lokalnie do 4,2 m). Odpowiedz bez URL arkusza z raportem wyjatku OGC
   w tresci (`ServiceException`/`ExceptionReport`; serwery WMS, np.
   MapServer, zwracaja go z HTTP 200 — np. `LayerNotDefined` dla
   nieaktualnej nazwy warstwy) nie jest odpowiedzia warstwy, tylko awaria
   jej zapytania; URL w odpowiedzi zawsze wygrywa. Granica tej strazy
   sprawdzona na zywo 2026-09-29 w obie strony: pusta odpowiedz (morze,
   strona czeska i niemiecka) to szablon HTML MapServera — HTTP 200
   `text/html`, 7721 B, identyczny dla wszystkich warstw 1 m i 5 m, BEZ
   znacznikow OGC (`NoCoverageError`, R5 dziala), a zla warstwa — HTTP 200
   `text/xml`, `ServiceExceptionReport` z `LayerNotDefined` (`DownloadError`).
   Strona bledu z HTTP 200 bez znacznikow OGC nadal liczylaby sie jako brak
   pokrycia. Po pobraniu `run_pl_cutout` rozstrzyga:
   - arkusz z `NoCoverageError` -> nodata w jego miejscu,
     `PlCutoutResult.missing_sheets` i sidecar `extra.missing_sheets`;
     biblioteka loguje liste zbiorczo na INFO (a `DownloadManager` kazdy
     taki arkusz na WARNING: `No data for <godlo>: ...`), CLI wypisuje
     `Warning:` na stderr (do 10 godel; `-q` go nie tlumi). E2E: arkusz
     nieobecny w cache -> `missing_sheets` = ten arkusz, 33 775 z 80 601
     pikseli nodata — wylacznie tam, gdzie zaden pobrany arkusz nie ma
     danych. Na zywo 2026-09-29: Leba, Hel, Slubice, Zgorzelec, trojstyk
     PL-CZ-DE, Osinow, PL-UA/BY/RU — arkusze morskie i zagraniczne
     w `missing_sheets`, nodata wylacznie nad morzem/za granica (0 pikseli
     rozbieznych z arkuszami: Leba, Hel, pogranicze PL-DE; PL-UA/BY/RU —
     sprawdzone polozenie nodata). `missing_sheets` NIE jest pelnym obrazem
     nodata: nodata bywa tez wewnatrz pobranych arkuszy przybrzeznych
     (kampania 5 m 2025 przycina rastry do zasiegu danych) i przygranicznych
     (PL-SK: do 82 % arkusza), a przy brzegu woda ma wartosci ~0 m (5 m: pas
     setek metrow, 1 m: caly arkusz przybrzezny), wiec granica nodata biegnie
     po krawedziach arkuszy, nie po linii brzegowej;
   - kazdy inny arkusz w `failed` -> `DownloadError` ("N z M arkuszy nie
     pobrano (blad pobrania, nie brak danych)"): chwilowy blad nie moze
     zostawic trwalej dziury w pliku, ktory potem jest pomijany jako
     istniejacy;
   - zaden arkusz nie ma danych -> `ValidationError`.

   Oba bledy padaja PRZED budowa (wycinek nie powstaje); CLI daje kod 1,
   a pod `--country auto` z sukcesem CZ — kod 0 i `Warning:` (sekcja 4.6).
   Zapytania skorowidza nie maja ponowien (S1): arkusz bez danych wymaga
   odpowiedzi WSZYSTKICH warstw, wiec przy zrywanych polaczeniach wycinek
   z wieloma arkuszami bez danych konczy sie kodem 1 ("ponow pobranie";
   na zywo Hel 4/4, Karkonosze 3/3 prob, ta sama biblioteka na jednej sesji
   z `Retry` — 72/72 zapytan). Ponowienie uzywa arkuszy juz pobranych.
   Wybor pliku ma znane bledy (K4, potwierdzone na zywo 2026-09-29): wygrywa
   pierwszy URL zawierajacy godlo (dopasowanie podciagu), bez wzgledu na
   rozdzielczosc, date i zasieg — skorowidz 1 m zawiera tez pliki 0,5 m
   (Szczecin: wycinek "1m" w 0,5 m, a jeden w 100 % nodata z kodem 0 i bez
   `missing_sheets`; mieszanie 0,5 m i 1 m konczy sie `niezgodne
   rozdzielczosci wejsc`), warstwa zbiorcza oddaje rekordy od najstarszego
   (2019 zamiast 2023), a gdy zaden URL nie zawiera godla — przyjmowany jest
   pierwszy (arkusz PL-2000 zatrzymuje krok 5; arkusz innego godla w tym
   samym ukladzie laduje w swoim miejscu, wiec obszar zadanego arkusza moze
   zostac nodata bez wpisu w `missing_sheets`).
5. **Mozaika na siatce arkuszy** (`build_pl_cutout` ->
   `transport/mosaic.py::mosaic_and_crop`). Najpierw `_reject_pl2000_sheets`:
   arkusz z lewa krawedzia `>= 1 000 000 m` (wspolrzedne strefowe PL-2000 —
   skorowidz GUGiK potrafi wydac pod godlem PL-1992 arkusz nowszej kampanii
   w ukladzie 2000) konczy budowe `ValidationError` z lista (strefa, EPSG) —
   inaczej `merge` pominalby go po cichu (dziura nodata); reprojekcja takich
   arkuszy to etap 2. Potem `mosaic_and_crop(..., snap_to_source_grid=True,
   assign_crs="EPSG:2180", dtype="float32")`:
   - **siatka arkuszy (R1)** — crop (obwiednia zrodla z kroku 2) jest
     rozszerzany NA ZEWNATRZ do linii siatki pikseli zrodel (< 1 px na
     strone; tolerancja 1e-6 px na szum zmiennoprzecinkowy). Siatka
     odniesienia to siatka WIEKSZOSCI zrodel (remis: pierwsze w kolejnosci
     wejscia), wzieta z transformacji arkuszy, a nie z wielokrotnosci
     piksela: arkusze GUGiK 5 m maja zwykle narozniki pikseli na
     `5k + 2,5 m` (1977 arkuszy z cache Hydrografu; na zywo 2026-09-29 takze
     48 arkuszy kampanii 2022/2024/2025 pod Wegrowem (L2) oraz arkusze
     w Lebie (L3)), a arkusze 1 m
     — na `k + 0,5 m` (na zywo: 84 pliki PL-1992, EVRF2007 2019-2025
     i KRON86 2011-2018, jedna faza; kampanie roznia sie zasiegiem o 1 px,
     nie faza). Bez tego crop kotwiczony w rogu zadania przesuwal tresc
     o ulamek piksela — dla bboxa na wielokrotnosciach 5 m przy 5 m o 0,5 px,
     z mieszaniem sasiednich kolumn przy remisie (48,7 % pikseli). Arkusz
     spoza siatki wiekszosci NIE przerywa budowy (arkusze sa juz w cache —
     blad bylby trwaly): `logger.warning` z przesunieciem w px, a jego tresc
     `merge` przepisuje bez interpolacji, ale NIE zawsze z najblizszego
     piksela (przy przesunieciu w strone W piksel oddalony o 0,55-0,88 px)
     i z kolumna/wierszem nodata na szwie — znany blad S5: arkusze 5 m
     kampanii 2022 pod Krakowem maja KAZDY inna faze (kotwiczone we wlasnym
     narozniku SW; 9 z 9), w Cieszynie 2 z 12 (kampania 2019); wycinek
     EPSG:2180 z nich bierze wartosci z sasiedniego piksela i ma nodata
     tam, gdzie dane sa (766 px). Siatka obrocona (rotacja/skos
     w transformie) = `ValidationError`;
   - **normalizacja w VRT** — kazde zrodlo owijane jest w jednopasmowy VRT
     1:1 w `/vsimem/` z jawnym SRS EPSG:2180 i pasmem Float32;
     `<NoDataValue>` VRT to nodata WLASNE zrodla (inna wartosc odmaskowalaby
     nodata zrodla i w zakladce arkuszy przykrylaby wazne dane sasiada).
     Arkusz z `.prj` (Hydrograf dopisuje EPSG:2180 do czesci arkuszy) scala
     sie z arkuszem bez niego — dotad `niezgodne CRS wejsc`; zrodlo
     z WLASNYM, innym ukladem = `ValidationError` (porownanie `equals` albo
     parametrow odwzorowania — kazdy WKT1 EPSG:2180, takze `.prj`
     Hydrografu, w samym `equals` daje False). Arkusz ASC z samymi liczbami
     calkowitymi (GDAL czyta go jako Int32) nie obcina juz mozaiki do liczb
     calkowitych (`merge` bierze typ z pierwszego zrodla). Owijanie
     przyjmuje tylko rastry jednopasmowe i typy z `_VRT_TYPES`; wynik bez
     jawnych kafli w `dst_kwds` to GTiff bez kafli (`tiled=False` —
     dziedziczone po VRT kafle min(128, w) x min(128, h) px konczyly zapis
     `RasterBlockError`, gdy wysokosc < 128 nie dzielila sie przez 16);
   - **wejscia posortowane** — `merge` bierze profil wyniku z pierwszego
     zrodla i pierwsze wazne zrodlo wygrywa w zakladce, a pobieranie
     rownolegle oddaje arkusze w kolejnosci ukonczenia; po sortowaniu wynik
     nie zalezy od kolejnosci listy. W zakladce (arkusze 5 m nachodza na
     siebie ~1 wiersz/kolumne) wygrywa arkusz pierwszy w sortowaniu sciezek,
     nie najnowszy — miedzy kampaniami to do 9 cm roznicy, a szew miedzy
     kampaniami potrafi zostawic 1 px nodata;
   - **deskryptory** — metadane czytane sa po jednym pliku, a `merge`
     dostaje nazwy (VRT) i otwiera zrodla leniwie, per kawalek wyniku:
     wycinek z > 1024 arkuszy nie konczy sie juz "Too many open files"
     (limit: Linux 1024, macOS 256). Zmierzone 2026-09-29 (L7, offline na
     cache Hydrografu): 1836 (cel 2180) i 2394 (cel 5514) arkuszy w selekcji,
     688/732 z danymi — maks. 9 otwartych deskryptorow, `ulimit -n 256`
     przechodzi z wynikiem bit w bit.

   Wynik mozaiki: GTiff z EPSG:2180, nodata `-9999.0`.
6. **Crop albo warp.** Dla `EPSG:2180` warpa nie ma: mozaika JEST wynikiem
   (`os.replace`). Wynik lezy wiec na siatce arkuszy — obszar zadania
   rozszerzony na zewnatrz o < 1 px na strone, wartosci 1:1 z arkuszy, bez
   przeprobkowania (`transform: null` w sidecarze pozostaje prawda), a nazwa
   pliku niesie wspolrzedne ZADANIA. Zmierzone E2E 2026-09-28 na realnych
   arkuszach 5 m z cache Hydrografu (bbox przez szew `N-34-139-A-c-4-3` /
   `-4-4`, mieszany cache z `.prj` przy jednym arkuszu): poczatek siatki
   `mod 5 = 2,5 m`, rozszerzenie 2,5 m na strone (bbox calkowity) albo
   0,2-3,8 m (ulamkowy), pikseli rozbieznych z arkuszem zawierajacym srodek
   piksela **0 z 80 601** (bbox calkowity) i **0 z 79 799** (ulamkowy), zero
   nodata, piksele identyczne jak z cache bez `.prj`.
   Dla `EPSG:5514`/`EPSG:3045` `transform/raster.py::warp_to_grid` (bez
   zmian w tej fali) reprojektuje mozaike — juz na siatce arkuszy, wiec bez
   przesuniecia o ulamek piksela — na siatke wyniku z WYMUSZONA operacja
   przypieta (bilinear, nodata maskowane). Wymuszenie nie jest ozdobne: na
   torze PL bez `COORDINATE_OPERATION` wierzcholek ucieka o ~122 m, a bez
   korekty osi (`axisswap`) wynik ma ZERO waznych pikseli. `warp_to_grid`
   sprawdza tez, czy para ukladow zgadza sie z `pinned` — wymuszona
   operacja czyni `src_crs` martwym dla GDAL-a. Siatke wyniku wyznacza
   wylacznie `bbox_target` (zapas zrodla z kroku 2 jej nie dotyczy):
   naroznik NW = (`min_x`, `max_y`), liczba pikseli = `max(1,
   round(rozpietosc / piksel))`, wiec krawedz E i S moze odbiegac od
   `bbox_target` o do 0,5 px — `round` rozstrzyga remis do parzystej, wiec
   dokladnie 0,5 px jest mozliwe, a bbox wezszy niz pol piksela dostaje
   i tak 1 px i odbiega bardziej (E2E: 1,61 m i 0,76 m przy 5 m; te sama
   regule ma `_warp_to_grid` toru CZ). Nazwa pliku niesie `bbox_target`.
   E2E (ten sam bbox, cel EPSG:5514): piksele wyniku sa bit w bit rowne
   odtworzeniu "mozaika na siatce arkuszy + `warp_to_grid`"; wzgledem
   niezaleznego warpu GDAL kazdego arkusza z ta sama operacja na te sama
   siatke — srednio **2,7 mm**, maks. 0,15 m dalej niz 1 px od szwu
   arkuszy (przy szwie do 0,67 m, bo tam warp pojedynczego arkusza widzi
   tylko czesc sasiadow bilinear). Roznice poza
   szwem robi GDAL: skale resamplingu (opcje warpu `XSCALE`/`YSCALE`; od
   nich zalezy, ile pikseli zrodla bierze interpolator) liczy per kawalek
   z proporcji okna celu do okna zrodla, a ta zalezy od zasiegu zrodla —
   mozaika vs pojedynczy arkusz; z `XSCALE=YSCALE=1` w obu warpach poza 1 px
   od szwu: srednio 0,03 mm, maks. 3,2 mm. Wartosci wycinka moga wiec
   minimalnie zalezec od zasiegu mozaiki; `warp_to_grid` i `_warp_to_grid`
   uzywaja ustawien domyslnych (kandydat na etap 2). Ustawienia domyslne to
   takze PRZYBLIZONY transformator (`tolerance` 0,125 px zrodla) — rozklad
   roznicy wobec dokladnego bilineara na zywych arkuszach 1 m (cel 5514):
   tylko `XSCALE`/`YSCALE` — srednio 2,76 mm, maks. 0,25 m; tylko
   `tolerance` — 0,31-0,33 mm, maks. 18 mm; oba wylaczone — 0,004 mm;
   przy 5 m `tolerance` daje do 0,13 m. To samo pole i uklad moga dostac
   inne wygladzenie zaleznie od bboxa. Na zywo 2026-09-29 wycinki 5514/3045
   byly bit w bit rowne warpowi wlasnej mozaiki z ta sama operacja,
   a wobec niezaleznej interpolacji roznily sie srednio o 0,13-3,3 mm
   (raport L2) i 2,97 mm (Leba, maks. 0,15 m na stokach wydm). Operacja
   2180 -> 5514 zawiera slowacka transformacje S-JTSK (EPSG:4829) — tresc
   wycinka w EPSG:5514 jest przesunieta wzgledem czeskiej o ok. 1,1-3,4 m
   wzdluz granicy PL-CZ (roznica EPSG:1622 - EPSG:4829 policzona pyproj:
   Cieszyn 1,15 m, Kudowa 2,15 m, Karkonosze 2,73 m — na zywo 2,3 m wzgledem
   DMR 5G, rejon Bogatyni ~3,4 m; znany blad K2); 2180 -> 3045 go nie
   dotyczy. Uklad docelowy spoza obszaru uzycia operacji (5514/3045 w NE
   Polsce) jest przyjmowany bez uwag, a dokladnosc w `transform` sidecara
   jest nominalna.
7. **Rozmiar i dysk** (review max zn. 9; bez twardego limitu rozmiaru).
   Przy warpie plik POSREDNI mozaiki (`<nazwa>.<pid>_<tid>.mosaic.tif`) jest
   kompresowany: deflate, predyktor 3, kafle 512 x 512 px,
   `BIGTIFF=IF_SAFER` (przy kompresji GDAL nie zna rozmiaru z gory); warp
   czyta go raz, a `finally` go kasuje (E2E: mozaika 439 x 271 px z realnych
   arkuszy 5 m — 2,12x mniej niz bez kompresji, piksele identyczne). Przy
   `EPSG:2180` ten plik JEST wynikiem, wiec zostaje bez kompresji; wynik
   warpa tez jest GTiff bez kompresji. Przed pobraniem `run_pl_cutout` wola
   `check_pl_cutout_disk_space`: DOLNE oszacowanie = wynik float32 bez
   kompresji (`PlCutout.estimated_bytes`, siatka z `bbox_target`) + arkusze
   nieobecne jeszcze w `FileStorage` po 5,5 B na wartosc (realne ASC GUGiK
   5 m: 5,74-7,95 B) — bez pliku posredniego i narzutu systemu plikow. Gdy
   wolne miejsce w najblizszym istniejacym katalogu sciezki wyniku jest
   mniejsze, `ValidationError` przed siecia. To kontrola "na pewno nie
   wystarczy", nie gwarancja. CLI wypisuje dodatkowo `Info: wycinek ~X GiB
   (W x H px float32)` na stderr, gdy `estimated_bytes >= 1 GiB`.
   Oszacowanie kosztuje ~7 ms na arkusz nieobecny w cache; wolajacy, ktory
   liczy je sam (`estimate_pl_cutout_bytes`) przed `run_pl_cutout`, placi
   dwa razy — w duzym wycinku 13-21 % czasu (N9). Zmierzone 2026-09-29 (L7):
   wycinek 103 x 77 km z 688/732 arkuszy 5 m — 36 s (cel 2180) / 109 s (cel
   5514), szczyt RSS ~1 GiB (1037-1039 MiB przy wyniku 1206/1398 MiB), plik
   posredni 5514 skompresowany 6,58x (63 % nodata).
8. **Sidecar** (`write_pl_cutout_sidecar`, best-effort) wg 3.2:
   `capability="sheet_files"`, uklad docelowy, `transform`, `nodata`,
   `extra.parent_request` i `extra.missing_sheets`.

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
Wlasne `except BaseException: dst.unlink(missing_ok=True)` ma dalej
wylacznie tor CZ (`providers/cuzk/dmr.py::_warp_to_grid`, niezalezna
kopia funkcji) — tam jest ono rownie zbedne (zapis idzie przez plik
tymczasowy), ale to kod zweryfikowany na zywo, ktorego tuz przed wydaniem
nie ruszamy (ADR-024). Bez
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
przypieta operacja zawierajaca dzis slowacka transformacje S-JTSK
(EPSG:4829) — tresc przesunieta do ~5 m (znany blad K2; Karkonosze na zywo
2,3 m wzgledem NMT GUGiK 1 m, z operacja czeska EPSG:1622 — 0,38 m).
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
`--target-crs` innym niz 5514 tresc reprojektuje lokalny warp (znany blad K2
— sekcja 4.4). Bboxy wieksze niz limit `exportImage` (deklarowany przez
usluge **15000 x 4100 px**) sa kafelkowane po stronie klienta i scalane przez
`mosaic_and_crop` — kafelkowanie dzieje sie PRZED warpem, w ukladzie
natywnym, wiec szew nie zostaje utrwalony przez interpolacje. Na zywo
2026-09-29 mechanizm dziala (pas 1800 x 12300 px = 22 Mpx z 3 kafli, szwy bit
w bit z niezaleznymi paskami, szczyt RSS 293 MiB), ale realny limit serwera
to ~8 Mpx na zapytanie: kafel 5000 x 2500 i pojedyncze zadanie 3000 x 3000
koncza sie HTTP 500. Klient tnie kafle dopiero, gdy wymiar przekroczy
15000 x 4100 px, wiec obszar 2 m zblizony do kwadratu wiekszy niz
~5,5 x 5,5 km (albo np. 10 x 5 km wydluzony W-E) nie przechodzi, a pas N-S
szerokosci do ~3,6 km przechodzi (kafle maja najwyzej 4100 px wysokosci;
3,6 x 24,6 km = 3 kafle po 7,4 Mpx) — znany blad K6. Pojedynczy
(niekafelkowany) wycinek natywny ma piksel ~2,0004 m zamiast 2 m, bo bbox
idzie do serwera bez dociagniecia do calkowitej liczby pikseli (N3).

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

Czesc zadania dla kazdego kraju jest pod `auto` PRZYCINANA do jego prostokata
(`_country_bbox`, w WGS84, z powrotem do ukladu zadania): obszar poza
WSZYSTKIMI prostokatami (np. na zachod od 14,07°E przy Osinowie Dolnym — 2,7 km
z 8,9 km zadania; na polnoc od 54,90°N nad Baltykiem) znika bez komunikatu,
pozostale krawedzie rosna o dziesiatki metrow (powrot przez WGS84), a nazwa
pliku i `request.bbox` niosa bbox przyciety — oryginal jest tylko
w `parent_request` (znany blad S3). Przyciecie dotyczy czesci CZ, czesci PL
w trybie `--bbox` (lista arkuszy i wycinek) i wycinka z `--geometry`; w trybie
`--geometry` bez `--target-crs` arkusze PL wyznacza sama geometria
(`_download_pl_geometry`), wiec tam czesc PL nie traci niczego. Jawny
`--country pl` nie przycina; bbox w calosci poza prostokatami to `Error:
obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)`, kod 1, bez
zapytan sieciowych. Rejestr zna tylko PL i CZ, wiec na granicach z DE, SK,
UA, BY, LT i RU `auto` odpytuje tylko PL, bez komunikatu (z przycieciem
opisanym wyzej, wiec nie zawsze jak `--country pl`: Osinow Dolny — pod `auto`
wycinek szerokosci 6,2 km i 4 arkusze listy, z `--country pl` 8,9 km
i 6 arkuszy) — poza pasem wewnatrz prostokata CZ (Saksonia i Nysa Luzycka
ponizej 51,06°N, pas Bogatyni), gdzie CUZK dostaje zapytanie i oddaje raster
w 100 % nodata z kodem 0, bez komunikatu (N2; tak samo dla obszarow PL
w prostokacie CZ, np. Opolszczyzny). Kod 0 pod `auto` nie
gwarantuje pliku z kazdego kraju: awaria jednego kraju (takze chwilowy blad
GUGiK, S1) przy sukcesie drugiego to kod 0 + `Warning:` — skrypt powinien
sprawdzac pliki albo stderr. `--resolution 1m` pod `auto` zawsze rozstrzyga do
PL, wiec strone CZ trzeba pobrac osobnym poleceniem (inny `parent_request`).
Bez `--vertical-crs` pogranicze daje PL w EVRF2007 i CZ w Bpv.

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
pobierane sa rownolegle. **Znany blad K1 (krytyczny, testy na zywo
2026-09-29):** `BBOX` idzie w kolejnosci (E, N), a `urn:ogc:def:crs:EPSG::2180`
wymaga (N, E); envelope kafla jest czytany tak samo odwrotnie, wiec filtr
przeciecia przechodzi, a kafle pochodza z miejsca o zamienionych
wspolrzednych (Spytkowice -> Lubuskie, 426 km). Weryfikacja z 2026-06-24 byla
kolowa (ADR-021, errata). LAZ zawsze najpierw odpytuje WFS, wiec ponowne
uruchomienie bez sieci konczy sie bledem, a awaria WFS daje mylace
`No LAZ tiles found` (N7). Godlo kafla jest drobniejsze niz 1:10000 i NIE jest
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
   test wychodzacy w siec poza loopback; wyjatek maja tylko testy z markerem
   `live` (domyslne komendy: `-m "not live"`).

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
| ADR-019 | SQLite WAL jako metadata cache | Cache URL-i i TERYT w SQLite (WAL, TTL 7 dni, `threading.Lock` na zapisach), zero nowych zaleznosci. |
| ADR-020 | Walidacja warstw WMS przez GetCapabilities | Hardcoded nazwy warstw sa porownywane z live przy pierwszym uzyciu i auto-korygowane; wynik cache'owany w pamieci providera. |
| ADR-021 | LAZ (chmury punktow LIDAR) — discovery przez WFS, area-based | WMS skorowidzy LAZ zwraca 401, wiec discovery idzie WFS-em; godlo kafla jest nieparsowalna etykieta, sciezke buduje `get_raw_path`. **Errata 2026-09-29:** kolejnosc osi WFS "zweryfikowana live" byla bledna (znany blad K1). |
| ADR-022 | Architektura zrodel wielokrajowych — deskryptory, rejestry, sidecar, twarda polityka transformacji (etap 0) | Powstaja `sources/`, `sources/sidecar.py`, `transform/crs.py`, `transport/`, `core/parser_registry.py`; providery PL przenosza sie do `providers/pl/` bez shimow. |
| ADR-023 | Silnik CUZK, polityka ukladow CZ i EVRF2007 -> 5621 (etap 1) | `CuzkClient` jako pierwszy silnik sterowany deskryptorem, przeplyw CZ omija `DownloadManager`, `--country auto` z prostokatnych obwiedni, `extra.parent_request`. |
| ADR-024 | Reprojekcja tresci CZ wylacznie lokalnie (zakaz `imageSR` != natywny) | Serwer CUZK dostaje zadania rastrowe tylko w ukladzie natywnym EPSG:5514 (+ zapas 4 px), a reprojekcje robi lokalny warp z WYMUSZONA operacja przypieta — serwerowa gubila datum shift (135 m). **Errata 2026-09-29:** roznice 1,25 m / 4,92 m przypisane serwerowi odpowiadaja roznicy EPSG:1622 - EPSG:4829; wybor operacji do rewizji (K2). |
| ADR-025 | Mapowanie tekstura -> HSG i kanoniczny trojkat USDA (audyt 0.7.0) | Progi tekstur to kanoniczne reguly USDA w jednej liscie (wersja wektorowa zrodlem prawdy); odstepstwa `TEXTURE_TO_HSG` od TR-55 sa swiadome i udokumentowane. |
| ADR-026 | Uklad `data/` per produkt + szablony `storage_subdir` | `data/<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/...`; `storage_subdir` staje sie szablonem z `{uklad}`/`{vcrs}`, a `FileStorage` odrzuca segment z nierozwiazana klamra. |
| ADR-027 | `--target-crs` dla PL jako scalony wycinek | Bbox/geometria PL z `--target-crs` daje jeden GeoTIFF: arkusze jako cache, `mosaic_and_crop`, lokalny warp przypieta operacja, sidecar z `transform.horizontal`. Uzupelnienia 2026-09-28: arkusz bez danych GUGiK = nodata + `extra.missing_sheets` (R5); mozaika na siatce arkuszy z arkuszami w VRT (EPSG:2180/Float32), glosny blad dla arkuszy PL-2000, tor jako API biblioteki `download/cutout.py` (R1, R3). Uzupelnienie 2026-09-29: wyniki testow na zywo (R5 na morzu i granicach, siatka 1 m, S5, K3/K4). |

ADR-026 i ADR-027 sa spisane w `docs/DECISIONS.md` w ramach tego samego
wydania 0.7.0.
