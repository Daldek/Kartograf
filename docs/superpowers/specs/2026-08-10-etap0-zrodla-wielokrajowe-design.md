# Spec: Etap 0 — refaktor przygotowawczy pod zrodla wielokrajowe

**Data:** 2026-08-10
**Status:** do review uzytkownika
**Wersja docelowa:** 0.7.0 (develop)
**Dokumenty zrodlowe:**
- `docs/research/2026-08-10-czechy-dmr-zabaged.md` (CUZK)
- `docs/research/2026-08-10-niemcy-dgm-atkis.md` (BKG + landy)
- `docs/research/2026-08-10-slowacja-dmr-zbgis.md` (UGKK/GKU)

---

## 1. Kontekst i cel

Kartograf obsluguje dzis jedno panstwowe zrodlo danych (GUGiK, Polska) plus dwa
ponadkrajowe (CORINE/UE, SoilGrids/global). Decyzja kierunkowa z sesji 2026-08-10:
rozszerzenie o **Czechy w pelnej parytetowosci produktowej** (NMT, NMPT, Orto, LAZ,
odpowiednik BDOT10k), a w dalszej kolejnosci o **Niemcy i Slowacje** — na potrzeby
analiz transgranicznych (zlewnie przekraczajace granice).

Przed dodaniem pierwszego nowego kraju wykonujemy **etap 0**: refaktor
przygotowawczy, ktory usuwa polskie zalozenia z warstwy wspolnej i wprowadza
architekture zrodel opisanych deklaratywnie. Etap 0 jest **zachowujacy
zachowanie** — istniejaca funkcjonalnosc dziala identycznie, weryfikacja przez
istniejacy zestaw ~1060 testow. Zamierzone zmiany obserwowalne sa dwie: sidecar
metadanych przy pobraniach (sekcja 6.3) oraz zmiana sciezek importu providerow
polskich — przenosiny do `providers/pl/` **bez shimow zgodnosciowych**
(sekcja 6.8; decyzja uzytkownika: Hydrograf/Hydrolog dostosuja importy).

Motywacja szerokiego (a nie punktowego) refaktoru: research trzech krajow dal
**cztery realne przypadki** (PL + CZ + DE + SK) do zaprojektowania granic
abstrakcji — nie projektujemy "na zapas", tylko na zmierzone wymagania.

## 2. Ustalenia z researchu ksztaltujace projekt

| # | Zasada | Dowod |
|---|---|---|
| 1 | **Zrodlo != kraj; opis zrodla jako dane** | DE = federacja 17 modeli: BKG DGM1 platny (8k EUR), 3 landy graniczne = 3 rozne mechanizmy dostepu; lacznie ~9 transportow w 4 krajach |
| 2 | **CRS pionowy per kanal dostepu, nie per produkt** | SK DMR 5.0: WCS = h elipsoidalne ETRS89, pliki/ArcGIS = Bpv; roznica **42,3 m** w tym samym punkcie |
| 3 | **Licencja i atrybucja per zrodlo, nie per kraj** | DE: GeoNutzV + dl-de/by-2-0 + dl-de/zero-2-0 + CC BY 4.0 + paywalle w jednym panstwie |
| 4 | **Zdolnosci zrodla jawne + generyczny fallback kaflowy** | Saksonia: brak WCS (tylko kafle 2x2 km); SK: brak plikow per arkusz (caly kraj 184 GiB); CZ: limit exportImage 15000x4100 px |
| 5 | **Skorowidz != zrodlo URL** | DE: nazwa kafla = f(x,y), indeks tylko pokrycie/rocznik; CZ: TM33 obliczalny, SM5 wymaga indeksu; PL: skorowidz WMS daje URL |
| 6 | **Twarda polityka transformacji** | PROJ przy braku sieci cicho zwraca identycznosc (ballpark); operacje "dostepne" o acc 0,051-7,0 m daja rozrzut do 11,9 m (SK 5514->2180); siatka slowacka zwraca `inf` w CZ; pierwsza operacja 4937->8357 to siatka czeska (`inf` na SK) |
| 7 | **Reprojekcja pozioma po stronie serwera preferowana** | dziala i zweryfikowana: CZ `imageSR`/`outSR`, SK `outputCrs` — omija dobor operacji PROJ |
| 8 | **Wysokosci: wspolny cel EVRF2007; KRON86 dla zagranicy = odmowa** | brak publicznych siatek `pl86_2019`/`pl07_2019`; geoida PL-KRON86 maskowana do PL (za granica `inf`); Bpv->5621 = 0,1 m; DHHN2016->5621 = 1-14 mm |
| 9 | **Metadane wyniku (sidecar) obowiazkowe** | scalanie danych transgranicznych wykonuje Hydrograf (decyzja zakresowa), wiec konsument musi dostac CRS-y, nodata i zrodlo; CZ wypelnia obszar poza granica **zerami** (49,3% kafla przy Cieszynie) — bez metadanych 0 m udaje poziom morza |

## 3. Roadmapa etapow (decyzje zatwierdzone kierunkowo)

Etap 0 (ten spec) → etap 1 → etap 2 → etap 3; DE i SK po osobnych decyzjach.
Kazdy etap dostaje wlasny spec i plan.

**Zasada natywnosci (dotyczy wszystkich etapow):** domyslnie Kartograf pobiera
dane dokladnie tak, jak publikuje je zrodlo — bez lokalnej reprojekcji,
resamplingu ani konwersji formatu; transformacje wylacznie na jawne zadanie
(`--target-crs`/`--vertical-crs`), preferencyjnie po stronie serwera zrodla.
Sidecar zawsze deklaruje faktyczny uklad i format wyniku. Doprecyzowania:
- tryb bbox z uslug (WCS/exportImage) zwraca wycinek wygenerowany przez serwer
  (GeoTIFF) w natywnym ukladzie kanalu — to pochodna, nie plik zrodlowy; kto
  potrzebuje danych zrodlowych 1:1, uzywa trybu arkuszowego (np. CZ: LAZ/TIFF
  z openzu to doslownie bajty publikowane przez CUZK; DMR 5G natywnie to
  TIN/LAZ, raster 2 m jest produktem uslugi);
- niektore kanaly nie oferuja natywnego ukladu produktu w ogole (SK WCS:
  h elipsoidalne zamiast Bpv; DE basemap.de: tylko CRS84/3857) — zapisujemy to,
  co kanal serwuje, a prawde niesie sidecar (`vertical_source` itd.);
- uzupelnienie brakujacych metadanych CRS (CZ DMR4G-TIFF `crs=None` →
  przypisanie EPSG:5514) i zadanie poprawnego oznaczenia nodata
  (CZ `noData=-9999`) nie zmieniaja wartosci danych — to naprawa metadanych,
  nie transformacja;
- istniejacy wyjatek bez zmian: fallback CORINE na PNG z WMS (podglad, nie dane).

**Etap 1 — fundament CZ + DMR** (decyzje juz podjete, doprecyzowanie w specu etapu 1):
- `providers/cuzk/`: `client.py` (CuzkClient — pierwszy silnik sterowany deskryptorem)
, `sheets.py` (SheetIndex), `dmr.py` (CuzkDmrProvider: DMR 5G raster 2 m + DMR 4G TIFF 5 m)
- Godla: `ParserTM33` obliczalny (`{E_km}_{N_km}`, naroznik SW, kafle 2x2 km);
  SM5 (`CTES86`) przez indeks `KladyMapovychListu` warstwa 24 (TM33 = warstwa 26)
  + `MetadataCache` (nowa tabela `sheet_cache`); auto-detekcja w rejestrze parserow
- Pobieranie plikowe wprost z `openzu.cuzk.gov.cz/opendata/...` (bez feedow ATOM);
  DMR4G-TIFF: **jawne przypisanie EPSG:5514** (plik ma `crs=None`, georeferencja w `.tfw`)
- `exportImage`: **zawsze** `noData=-9999` + `noDataInterpretation` (inaczej obszar
  poza CZ = 0,0 bez oznaczenia); kafelkowanie przy przekroczeniu 15000x4100 px
  + `mosaic_and_crop`
- Uklady: **domyslnie natywnie** EPSG:5514 + Bpv (decyzja uzytkownika);
  `--target-crs EPSG:2180` → reprojekcja serwerowa (`imageSR`); `--vertical-crs
  EVRF2007` → lokalnie przypieta operacja 8357->5621 (0,1 m); KRON86 →
  `TransformUnavailableError` z remedium; sidecar niesie `PODIL` dla arkuszy
  przygranicznych
- CLI: `--country {pl,cz,auto}`, domyslnie `auto` — bbox przecinany z extentami
  krajow, pobranie z kazdego kraju osobno do osobnych plikow (scalania brak —
  zadanie Hydrografa); `--resolution 2m`→DMR5G, `5m`→DMR4G, walidacja per kraj;
  konflikt godlo/kraj → `ValidationError`
- Storage: `cz_dmr5g`, `cz_dmr4g`; TM33 → `302/5550/`, SM5 przez `get_raw_path()`

**Etap 2 — CZ: DMP (NMPT), Ortofoto, LAZ** — na gotowym fundamencie SM5;
DMP1G/DMPOK, Ortofoto JPEG+JGW, LAZ jako natywny format DMR 5G.

**Etap 3 — ZABAGED** (odpowiednik BDOT10k): ArcGIS REST `/query` po bboxie,
149 warstw, paginacja 2000 + `exceededTransferLimit`, `outSR`; pliki calego
kraju (5,8 GB) odrzucone. Przy tym etapie decyzja o wspolnym slowniku klas
pokrycia terenu (BDOT10k/ZABAGED/ZBGIS/Basis-DLM).

**Pozniej — DE** (federacja: BKG DGM200 WCS + BB/MV WCS + SN kafle Nextcloud +
basemap.de OGC API Features; licencje per zrodlo; nazwy kafli arytmetyczne,
indeksy pokrycia jako pliki statyczne) **i SK** (WCS GeoServer z wysokosciami
**elipsoidalnymi** → konwersja siatka `sk_gku_Slovakia_ETRS89h_to_Baltic1957`;
JTSK03=8353 vs 5514; brak plikow per arkusz → WCS jedyna droga rastra; WAF:
zakaz `where=`, retry na HTML).

## 4. Zakres etapu 0

**Wchodzi:**
1. `kartograf/sources/` — deskryptory zrodel + rejestr zrodel i krajow (dane, zero IO)
2. `kartograf/sources/sidecar.py` — metadane wyniku + zapis `.meta.json`
   (jedyna zmiana obserwowalna)
3. `kartograf/transform/crs.py` — twarda polityka transformacji (infrastruktura;
   pierwszy konsument w etapie 1)
4. `kartograf/transport/http.py` + `kartograf/transport/mosaic.py` — kanoniczny
   downloader i mozaikowanie (infrastruktura; pierwszy konsument w etapie 1)
5. `kartograf/core/parser_registry.py` — rejestr systemow godel; `SheetParser`
   i `FileStorage` korzystaja z rejestru (wyniki identyczne jak dzis)
6. Ujednolicenie ABC: `DataSourceProvider` ← `BaseProvider`, `LandCoverProvider`;
   uogolnienie `download_by_teryt` → `download_by_admin_unit` (aliasy zachowane)
7. Przeniesienie `providers/gugik*.py`, `providers/bdot10k.py` →
   `providers/pl/` **bez shimow** + fabryka domyslnego providera
8. `FileStorage`: opcjonalny `subdir` sterowany deskryptorem (logika PL bez zmian)
9. Podzial `cli/commands.py` (1600 linii) na moduly + fasada zgodnosci
10. Dokumentacja: nowy ADR, CHANGELOG, CLAUDE.md (struktura modulow), PROGRESS

**Nie wchodzi (jawnie poza zakresem):**
- zadne nowe zrodlo danych (CZ = etap 1)
- ekstrakcja logiki WCS / WMS-skorowidzow z `gugik.py` do warstwy transportu
  (uzasadnienie w sekcji 13)
- formalny interfejs "silnika transportu" (wyloni sie w etapie 1 przy CuzkClient)
- migracja istniejacych wywolan pyproj (soilgrids, parser_2000, geometry) na
  `transform/crs.py` — zostaja jak sa, migracja oportunistyczna pozniej
- zmiany API `LandCoverManager` i `DownloadManager`
- flaga `--country` w CLI (etap 1)
- scalanie rastrow miedzykrajowych (nigdy — zadanie Hydrografa, decyzja uzytkownika)
- silniki ArcGIS REST / OGC API Features (etapy 1 i 3)

## 5. Architektura po etapie 0

```
kartograf/
├── sources/                  # NOWE — zrodla opisane jako dane
│   ├── __init__.py
│   ├── descriptor.py         # SourceDescriptor, AccessChannel, TileScheme,
│   │                         #   LicenseInfo, CountryProfile, TransportKind
│   ├── registry.py           # rejestr deskryptorow i krajow (PL + EU + GLOBAL)
│   └── sidecar.py            # ResultMetadata + write_sidecar()
├── transport/                # NOWE — wspolne narzedzia transportowe
│   ├── __init__.py
│   ├── http.py               # download_to(): retry, atomic write, temp pid_tid
│   └── mosaic.py             # mosaic_and_crop(): rasterio.merge + przyciecie
├── transform/                # NOWE — twarda polityka transformacji
│   ├── __init__.py
│   └── crs.py                # TransformPolicy, PinnedTransform,
│                             #   build_pinned_transform(), bledy
├── core/
│   ├── parser_registry.py    # NOWE — rejestr systemow godel
│   ├── sheet_parser.py       # bez zmian publicznego API; detekcja przez rejestr
│   ├── parser_2000.py        # bez zmian
│   └── geometry.py           # bez zmian
├── providers/
│   ├── base.py               # DataSourceProvider + BaseProvider + LandCoverProvider
│   ├── pl/                   # NOWE — kod przeniesiony 1:1
│   │   ├── __init__.py       # + create_nmt_provider(vertical_crs, resolution, ...)
│   │   ├── gugik.py
│   │   ├── gugik_nmpt.py
│   │   ├── gugik_orto.py
│   │   ├── gugik_laz.py
│   │   └── bdot10k.py
│   ├── corine.py             # bez przenosin (zakres EU)
│   └── soilgrids.py          # bez przenosin (zakres GLOBAL)
│                             # stare moduly gugik*.py, bdot10k.py,
│                             #   landcover_base.py USUNIETE bez shimow (6.8)
├── download/
│   ├── manager.py            # API bez zmian; domyslny provider przez fabryke pl
│   └── storage.py            # + subdir override; path-parts przez parser_registry
├── landcover/manager.py      # API bez zmian; + zapis sidecara po pobraniu
└── cli/
    ├── __init__.py           # bez zmian (main)
    ├── commands.py           # FASADA: create_parser, main, re-export cmd_*
    ├── _parser.py            # budowa argparse (z dotychczasowego create_parser)
    ├── parse_cmd.py          # cmd_parse + format_sheet_info/hierarchy/children/...
    ├── download_cmd.py       # cmd_download, _cmd_download_bbox, _cmd_download_laz,
    │                         #   _cmd_download_geometry, _create_provider_and_storage
    ├── landcover_cmd.py      # cmd_landcover*
    ├── soilgrids_cmd.py      # cmd_soilgrids*
    └── cache_cmd.py          # cmd_cache
```

Granice odpowiedzialnosci: `sources/` nie robi IO; `transport/` nie zna krajow
ani produktow; `transform/` nie zna HTTP; providery nie pisza sidecarow
(robia to managery/CLI, ktore znaja kontekst wywolania).

## 6. Komponenty

### 6.1 `sources/descriptor.py` — opis zrodla jako dane

Zamrozone dataclassy, zero zachowan, zero IO. Szkic (szczegoly moga sie
doprecyzowac w planie, semantyka pol jest wiazaca):

```python
class TransportKind(StrEnum):
    WCS = "wcs"                      # PL nmt_1m bbox, SoilGrids; pozniej DE/SK
    WMS_SHEET_INDEX = "wms_sheet_index"  # PL: skorowidz WMS -> URL pliku
    WFS = "wfs"                      # PL LAZ
    DIRECT_FILES = "direct_files"    # PL BDOT10k; pozniej CZ openzu
    CLMS_API = "clms_api"            # CORINE
    ARCGIS_IMAGE = "arcgis_image"    # etap 1 (CZ exportImage)
    ARCGIS_QUERY = "arcgis_query"    # etap 3 (ZABAGED), SK
    OGC_API_FEATURES = "ogc_api_features"  # DE basemap.de

@dataclass(frozen=True)
class LicenseInfo:
    id: str            # np. "CC-BY-4.0", "PL-PGiK-40a", "dl-de/by-2-0"
    attribution: str   # gotowy tekst atrybucji
    url: str = ""

@dataclass(frozen=True)
class AccessChannel:
    transport: TransportKind
    horizontal_crs: str                      # "EPSG:2180", "EPSG:5514", ...
    vertical_crs_options: tuple[str, ...]    # () gdy nie dotyczy (orto, landcover)
    vertical_source: str = "native"          # "native" | "ellipsoidal" | "server"
    server_reprojection: bool = False
    capabilities: frozenset[str] = frozenset()
    # {"bbox_raster","bbox_vector","sheet_files","area_files","admin_unit_files"}
    notes: str = ""
    # endpointow celowo brak w etapie 0 — zrodlem prawdy pozostaja providery;
    # pole endpoint dojdzie w etapie 1, gdy pierwszy silnik zacznie je konsumowac

@dataclass(frozen=True)
class TileScheme:
    kind: str                 # "computable" | "index"
    crs: str
    width_m: float | None
    height_m: float | None
    description: str          # np. "SM5: nazwa miasta + cyfry, wymaga indeksu"

@dataclass(frozen=True)
class SourceDescriptor:
    key: str                  # "pl.gugik.nmt_1m"
    country: str              # "PL" | "EU" | "GLOBAL" (pozniej "CZ","DE","SK")
    product: str              # "nmt" | "nmpt" | "orto" | "laz" | "landcover" | "soil"
    name: str                 # czytelna nazwa zbioru
    provider_name: str        # "GUGiK", "CUZK", ...
    channels: tuple[AccessChannel, ...]
    tile_scheme: TileScheme | None
    storage_subdir: str | None    # None dla zrodel LandCoverManagera
    default_extension: str
    license: LicenseInfo
    resolution: str | None = None
    auth: str = "none"            # "none" | "clms_oauth"

@dataclass(frozen=True)
class CountryProfile:
    code: str                 # "PL"
    name: str
    extent_wgs84: BBox        # przyblizony zasieg do --country auto (etap 1)
    dataset_keys: tuple[str, ...]
```

Zasady:
- Wartosci wypelniane z istniejacych stalych providerow; **test spojnosci**
  (6.12) pilnuje zgodnosci deskryptor ↔ provider, wiec drift jest wykrywany.
- `vertical_crs_options` uzywa kodow EPSG: KRON86 = "EPSG:9650",
  EVRF2007 (realizacja PL) = "EPSG:9651". Mapowanie nazw uzywanych w CLI
  ("KRON86"/"EVRF2007") na kody trzyma rejestr.

### 6.2 `sources/registry.py` — rejestr zrodel i krajow

Modul z zamrozonymi wpisami + funkcje dostepu:

```python
def get_source(key: str) -> SourceDescriptor          # KeyError gdy brak
def sources_for(country: str | None = None,
                product: str | None = None) -> list[SourceDescriptor]
def get_country(code: str) -> CountryProfile
def vertical_crs_code(name: str) -> str               # "EVRF2007" -> "EPSG:9651"
```

Wpisy etapu 0 (wartosci docelowe; kanaly wg stanu faktycznego providerow):

| key | product | storage_subdir | ext | kanaly (transport → capabilities) | vertical opts |
|---|---|---|---|---|---|
| `pl.gugik.nmt_1m` | nmt | `nmt_1m` | `.asc` | wms_sheet_index→sheet_files; wcs→bbox_raster | 9650, 9651 |
| `pl.gugik.nmt_5m` | nmt | `nmt_5m` | `.asc` | wms_sheet_index→sheet_files | 9651 |
| `pl.gugik.nmpt` | nmpt | `nmpt` | `.asc` | wms_sheet_index→sheet_files | 9650, 9651 |
| `pl.gugik.orto` | orto | `orto` | `.tif` | wms_sheet_index→sheet_files | — |
| `pl.gugik.laz` | laz | `laz` | `.laz` | wfs→area_files | 9650, 9651 |
| `pl.gugik.bdot10k` | landcover | None | `.gpkg` | direct_files→admin_unit_files | — |
| `eu.clms.corine` | landcover | None | `.tif`/`.png` | clms_api→bbox_raster (fallback WMS) | — |
| `global.isric.soilgrids` | soil | None | `.tif` | wcs→bbox_raster | — |

Kraje: w etapie 0 tylko `PL` (extent ~ `BBox(14.07, 49.00, 24.20, 54.90,
crs="EPSG:4326")`; przyblizenie wystarcza — na styku granicy `--country auto`
w etapie 1 ma pobrac z obu krajow, co jest zamierzone). CORINE/SoilGrids nie
maja `CountryProfile` (kody "EU"/"GLOBAL" tylko w deskryptorach).

W etapie 0 deskryptory sa zrodlem prawdy dla: `storage_subdir`,
`default_extension`, licencji, opcji pionowych i capabilities (konsumowane
przez sidecar i testy spojnosci). **Egzekwowanie capabilities w managerach
zaczyna sie w etapie 1** — w etapie 0 zadna logika wykonawcza sie nie zmienia.

### 6.3 `sources/sidecar.py` — metadane wyniku (jedyna zmiana obserwowalna)

Po kazdym udanym pobraniu obok pliku wynikowego powstaje
`<pelna_nazwa_pliku>.meta.json` (np. `N-34-130-D-d-2-4.asc.meta.json`).

```python
@dataclass
class ResultMetadata:
    schema: str = "kartograf-meta/1"
    dataset: str            # klucz deskryptora
    country: str
    product: str
    provider: str
    horizontal_crs: str
    vertical_crs: str | None
    vertical_source: str    # "native" | "ellipsoidal" | "server"
    resolution: str | None
    nodata: float | None    # gdy znane (ASC: -9999 z naglowka; inaczej None)
    request: dict           # {"godlo": "..."} lub {"bbox": [...], "bbox_crs": "..."}
    license: dict           # {"id","attribution","url"}
    transform: dict | None  # etap 0: None; etap 1+: {"horizontal": "server:EPSG:2180",
                            #   "vertical": "pinned: Baltic 1957 -> EVRF2007 (0.1 m)"}
    extra: dict             # pola per zrodlo (etap 1: np. PODIL dla SM5)
    downloaded_at: str      # ISO 8601 UTC
    kartograf_version: str

def build_metadata(descriptor, *, request, vertical_crs=None, ...) -> ResultMetadata
def write_sidecar(data_path: Path, meta: ResultMetadata) -> Path
```

Punkty wpiecia (wszystkie w warstwie manager/CLI, nie w providerach):
- `DownloadManager.download_sheet` / `download_bbox` (NMT/NMPT/Orto)
- `_cmd_download_laz` (przeplyw LAZ omija managera)
- `LandCoverManager.download_by_teryt` / `download_by_bbox` / `download_by_godlo`
  (BDOT10k, CORINE, SoilGrids)

Zasady:
- Blad zapisu sidecara **nie przerywa** pobrania — log warning, zwracamy dane
  (dane sa wazniejsze niz metadane; brak sidecara jest widoczny dla konsumenta).
- `vertical_crs` wypelniany z faktycznego wyboru uzytkownika (KRON86/EVRF2007
  → kod EPSG przez rejestr); dla orto/landcover/soil — `null`.
- Sidecar jest kontraktem dla Hydrografa: to tu trafia w przyszlosci informacja
  o ukladzie danych CZ/DE/SK, nodata i pokryciu czesciowym. Format wersjonowany
  (`schema`), pola dokladane addytywnie.

### 6.4 `transform/crs.py` — twarda polityka transformacji

Cztery reguly bezpieczenstwa (kazda wynika ze zmierzonej pulapki):

1. Transformer budowany **wylacznie** przez
   `TransformerGroup(src, dst, allow_ballpark=False, always_xy=True)`.
   Nigdy `Transformer.from_crs` dla par miedzykrajowych (ballpark potrafi
   cicho zwrocic identycznosc — zmierzone dla DHHN2016 przy braku sieci).
2. **Pusta lista operacji = blad** (`TransformUnavailableError`), nigdy fallback.
3. Filtr operacji: odrzuc `accuracy <= 0` (nieznana) oraz
   `accuracy > policy.min_accuracy_m`; nastepnie **probe** — wykonaj operacje
   na punkcie kontrolnym z obszaru danych; wynik nieskonczony/NaN ⇒ odrzuc
   operacje (przypadek siatki obcego kraju: sk_gku w CZ, cz_cuzk na SK,
   geoida PL za granica). Z pozostalych wybierz najlepsza dokladnosc.
4. Kazdy wynik transformacji przechodzi kontrole `isfinite`; wartosci
   nieskonczone ⇒ `TransformError`, nie dane.

```python
@dataclass(frozen=True)
class TransformPolicy:
    min_accuracy_m: float = 1.0
    probe_point: tuple[float, float] | None = None   # w ukladzie zrodlowym
    allow_network_grids: bool = True                 # PROJ CDN

@dataclass(frozen=True)
class PinnedTransform:
    accuracy_m: float
    description: str        # opis wybranej operacji (trafia do sidecara)
    def transform(self, x, y, z=None) -> tuple: ...  # z kontrola isfinite

def build_pinned_transform(src_crs: str, dst_crs: str,
                           policy: TransformPolicy) -> PinnedTransform
# TransformUnavailableError niesie: liste odrzuconych operacji z powodami
# oraz remedium z tabeli REMEDIES (patrz nizej)

class TransformError(KartografError): ...
class TransformUnavailableError(TransformError): ...
```

Tabela referencyjna przypietych sciezek (stala dokumentacyjna `KNOWN_PATHS`;
w etapie 0 wykorzystywana w testach, konsumpcja produkcyjna od etapu 1):

| src | dst | mechanizm | acc | uwagi |
|---|---|---|---|---|
| EPSG:5514 | EPSG:2180 | probe odrzuca sk_gku (inf w CZ) → `S-JTSK to ETRS89 (3)` | 0,5 m | preferowac reprojekcje serwerowa CUZK |
| EPSG:8353 | EPSG:2180 | dowolna z 2 operacji | 0,001 m | SK, bez siatek |
| EPSG:25833 | EPSG:2180 | jedyna operacja | 0,0 m | DE, bez siatek |
| EPSG:8357 | EPSG:5621 | operacja EPSG (1) | 0,1 m | Bpv→EVRF2007; +0,12..+0,14 m |
| EPSG:7837 | EPSG:5621 | vertoffset | 0,1 m | DHHN2016; realnie 1-14 mm |
| EPSG:4937 | EPSG:8357 | siatka `sk_gku_Slovakia_ETRS89h_to_Baltic1957` | 0,03 m | probe konieczny: pierwsza operacja PROJ to siatka CZ |
| * | EPSG:9650 / EPSG:9651 (dane zagraniczne) | **BRAK** | — | `REMEDIES`: siatki `pl86_2019`/`pl07_2019` niepubliczne; zainstaluj recznie do PROJ_DATA albo uzyj EVRF2007 (EPSG:5621) |

Zakres etapu 0: modul + testy. Zadne istniejace wywolanie pyproj nie jest
migrowane (soilgrids/parser_2000/geometry dzialaja jak dotad — pary
wewnatrzpolskie ETRS89 nie maja problemu wyboru operacji).

### 6.5 `transport/http.py` i `transport/mosaic.py`

`http.py` — kanoniczny downloader dla **nowego** kodu (etap 1+):

```python
def download_to(session, url, output_path, *, timeout, retries=3,
                chunk_size=1_048_576) -> Path
# temp: f"{output_path}.{os.getpid()}_{threading.get_ident()}.tmp" -> os.replace
# retry z backoff; DownloadError po wyczerpaniu prob
```

Istniejace providery **nie sa** przepinane w etapie 0 (kazdy ma wlasna,
przetestowana implementacje tego wzorca; ujednolicenie oportunistycznie pozniej).

`mosaic.py` — generyczny fallback "pobierz kafle → zszyj → przytnij":

```python
def mosaic_and_crop(inputs: list[Path], bbox: BBox, output_path: Path,
                    *, nodata: float | None = None) -> Path
# rasterio.merge + przyciecie okna do bbox
# walidacje: niezgodny CRS lub rozdzielczosc wejsc -> ValidationError
# nodata propagowane do wyniku (nigdy nie zamieniane na 0)
```

Pierwszy konsument: etap 1 (kafelkowanie exportImage powyzej 15000x4100 px);
kolejni: Saksonia (brak WCS), ewentualnie PL 5m bbox w przyszlosci.

### 6.6 `core/parser_registry.py` + zmiany w `SheetParser` i `FileStorage`

```python
@dataclass(frozen=True)
class SheetSystem:
    id: str                              # "pl1992", "pl2000" (etap 1: "cz_tm33", "cz_sm5")
    country: str
    detect: Callable[[str], bool]
    parser_factory: Callable[[str], Any] # obiekt z .godlo, .get_bbox(), ...
    path_parts: Callable[[str], list[str]]  # czesci sciezki dla FileStorage

def register_system(system: SheetSystem) -> None
def detect_system(godlo: str) -> SheetSystem | None   # w kolejnosci rejestracji
def path_parts(godlo: str) -> list[str]
```

- Wpisy etapu 0: `pl2000` (predykat = dzisiejszy regex `^[5-8]\.\d`),
  `pl1992` (fallback). Logika detekcji i dzielenia sciezek **przeniesiona 1:1**
  z `sheet_parser._is_pl2000_format` i `FileStorage._get_directory_parts`.
- `SheetParser.__init__` konsultuje rejestr zamiast wlasnego ifa; delegacja do
  `Parser2000` i walidacja konfliktu (`PL-2000 godlo + uklad="1992"` →
  `ValidationError`) zachowane co do bajta komunikatow.
- `FileStorage._get_directory_parts` deleguje do `parser_registry.path_parts`;
  wyniki identyczne (pilnuja tego istniejace testy storage).
- Publiczne API bez zmian: `SheetParser("...")`, `parser.uklad`, itd.

### 6.7 `providers/base.py` — ujednolicenie ABC

```python
class DataSourceProvider(ABC):
    @property @abstractmethod
    def name(self) -> str: ...
    @property @abstractmethod
    def base_url(self) -> str: ...
    descriptor_key: str | None = None      # wiazanie z rejestrem zrodel
    def get_supported_formats(self) -> list[str]: ...
    def get_file_extension(self, format: str) -> str: ...

class BaseProvider(DataSourceProvider):          # rastry/arkusze — jak dzis
    default_extension: str (property, ".asc")
    download(godlo, output_path, timeout=30) [abstract]
    download_bbox(bbox, output_path, format="GTiff", timeout=30) [NotImplementedError]
    validate_godlo(godlo) -> bool

class LandCoverProvider(DataSourceProvider):     # pokrycie terenu
    @property
    def source_url(self) -> str: return self.base_url   # deprecated alias
    download_by_bbox(...)   [status abstract jak dzis]
    download_by_godlo(...)  [jak dzis]
    download_by_admin_unit(code, output_path, timeout=120) [NOWE, kanoniczne]
    download_by_teryt(teryt, ...)  # deprecated wrapper -> download_by_admin_unit
    validate_admin_unit(code) -> bool     # NOWE
    validate_teryt(teryt) -> bool         # deprecated wrapper
```

Zasady zgodnosci:
- Dokladny podzial abstract/konkret przeniesiony ze stanu obecnego (plan
  weryfikuje go z kodu przed zmiana) — kontrakt publiczny bez zmian.
- `Bdot10kProvider` przenosi implementacje na `download_by_admin_unit` /
  `validate_admin_unit`; stare nazwy dzialaja przez wrappery. Uwaga na
  rekursje: wrapper woła nowa nazwe, nigdy odwrotnie.
- Deprecje w etapie 0 tylko w docstringach (bez `DeprecationWarning` —
  nie smiecimy uzytkownikom CLI; ewentualne warningi przy nastepnym major).
- `providers/landcover_base.py` zostaje **usuniety** (bez shima) —
  `LandCoverProvider` zyje w `providers/base.py`; wszystkie importy w repo
  (landcover/manager, corine, soilgrids, testy) przechodza na nowa sciezke.

### 6.8 `providers/pl/` — przeniesienie kodu polskiego (bez shimow)

- Kod `gugik.py`, `gugik_nmpt.py`, `gugik_orto.py`, `gugik_laz.py`,
  `bdot10k.py` przenosi sie **1:1** (bez zmian tresci poza importami) do
  `providers/pl/`. Stare moduly zostaja **usuniete bez shimow zgodnosciowych**
  (decyzja uzytkownika z review specu: Hydrograf/Hydrolog dostosuja importy).
- Konsekwencje dla konsumentow biblioteki:
  - `from kartograf import GugikProvider, ...` (publiczne API `__init__.py`)
    — **dziala bez zmian**; to jest zalecana, stabilna powierzchnia importu
  - `from kartograf.providers.gugik import ...` → **ImportError**; migracja
    to jednoliniowa zmiana na `kartograf.providers.pl.gugik`
  - wpis **BREAKING** w CHANGELOG z tabelka sciezek starych → nowych
- **Caly kod wewnetrzny** (manager, CLI, `__init__.py`, testy) przechodzi na
  sciezki kanoniczne `providers.pl.*`.
- Aliasy metod z 6.7 (`download_by_teryt` itd.) **pozostaja** — to inna
  warstwa niz shimy modulow: chronia inwariant testowy etapu 0 (zero zmian
  asercji w ~1060 testach) kosztem trzyliniowego wrappera, bez utrzymywania
  rownoleglego drzewa modulow. Do przegladu przy nastepnym major.
- `providers/pl/__init__.py` dostaje fabryke
  `create_nmt_provider(vertical_crs, resolution, cache) -> GugikProvider`
  wyciagnieta z logiki domyslnej `DownloadManager` i CLI
  `_create_provider_and_storage` (w tym regula "5m ⇒ EVRF2007") — jedno
  miejsce wiedzy o polskich domyslach.
- Testy: dozwolone zmiany to aktualizacja stalych patch-targetow oraz
  importow po usunietych modulach (sekcja 9).

### 6.9 `download/storage.py`

- `FileStorage.__init__` przyjmuje dodatkowo `subdir: str | None = None`;
  podany `subdir` ma pierwszenstwo, `None` ⇒ dotychczasowa logika
  (`product` / `nmt_<resolution>` / PL-2000 wariant) **bez zmian**.
- `SUPPORTED_RESOLUTIONS` zostaje jako walidacja legacy parametru `resolution`
  (PL); zrodla nowych krajow beda podawac `subdir` wprost z deskryptora
  (etap 1: `cz_dmr5g`), wiec lista nie rosnie o obce rozdzielczosci.
- `_get_directory_parts` → delegacja do `parser_registry` (6.6).
- `get_raw_path()` bez zmian (uzywany przez LAZ; etap 1 uzyje go dla SM5).

### 6.10 `download/manager.py` i `landcover/manager.py`

- `DownloadManager`: API i zachowanie bez zmian; konstrukcja domyslnego
  providera przechodzi na `providers.pl.create_nmt_provider` (6.8); po udanym
  pobraniu dopisuje sidecar (6.3).
- `LandCoverManager`: API bez zmian; `_get_provider_by_name` moze wewnetrznie
  korzystac z rejestru zrodel, ale **wyjscie `list-sources` i komunikaty CLI
  pozostaja identyczne co do znaku** (testy CLI to asertuja); po udanym
  pobraniu dopisuje sidecar.

### 6.11 `cli/` — podzial

- Funkcje przenosza sie do modulow wg tabeli w sekcji 5, **bez zmian tresci**.
- `cli/commands.py` zostaje fasada: `create_parser`, `main` oraz re-export
  wszystkich `cmd_*`, `format_*` i helperow `_cmd_*`/`_create_*` uzywanych
  przez testy — istniejace importy testowe dzialaja bez zmian.
- Entry point `kartograf` w `pyproject.toml` bez zmian (wskazuje na
  `main`, ktory zostaje w dotychczasowym module docelowym).
- Importy providerow w CLI przechodza na `providers.pl.*` (konsekwencja 6.8).

### 6.12 Testy nowych komponentow

- `tests/test_sources_registry.py`: kompletnosc wpisow; **test spojnosci**
  deskryptor↔provider (dla kazdego klucza PL: `default_extension` ==
  `provider.default_extension`, `storage_subdir` == faktyczny podkatalog
  FileStorage dla tego produktu/rozdzielczosci, `vertical_crs_options`
  zgodne z obslugiwanymi wartosciami providera).
- `tests/test_transform_crs.py`: (a) odrzucenie ballpark, (b) pusta grupa →
  `TransformUnavailableError` z remedium, (c) filtr dokladnosci, (d) probe
  odrzuca operacje zwracajaca inf (mock TransformerGroup — offline),
  (e) `isfinite` na wyniku, (f) para 25833→2180 end-to-end (bez siatek, offline).
- `tests/test_transport_mosaic.py`: syntetyczne rastry (2x2 kafle) — zszycie,
  przyciecie do bbox, propagacja nodata, blad przy niezgodnym CRS/res.
- `tests/test_transport_http.py`: atomic write (tmp → replace), retry,
  sprzatanie tmp po bledzie.
- `tests/test_sidecar.py`: schema, zawartosc dla godlo- i bbox-requestu,
  zachowanie przy bledzie zapisu (warning, nie wyjatek).
- `tests/test_parser_registry.py`: detekcja pl1992/pl2000, `path_parts`
  identyczne z dotychczasowymi wynikami dla przykladow z testow storage.
- Rozszerzenie istniejacych testow managerow o assercje "sidecar powstaje"
  (addytywne, bez zmiany dotychczasowych asercji).

## 7. Przeplyw danych

Bez zmian wzgledem stanu obecnego: CLI/API → manager → provider → storage.
Roznica po etapie 0: po udanym pobraniu manager/CLI buduje `ResultMetadata`
z deskryptora (rejestr) + kontekstu wywolania i zapisuje `.meta.json` obok
pliku. Deskryptory sa danymi statycznymi w kodzie — zadnego IO przy imporcie.

## 8. Obsluga bledow

- `TransformError` / `TransformUnavailableError` — nowa galaz pod
  `KartografError`; `TransformUnavailableError` zawsze niesie liste
  odrzuconych operacji z powodami + remedium (jesli znane w `REMEDIES`).
- `mosaic_and_crop`: niezgodnosc CRS/rozdzielczosci wejsc → `ValidationError`;
  brak wejsc → `ValidationError`.
- `write_sidecar`: wyjatki IO lapane, logowane jako warning, pobranie zwraca
  wynik normalnie.
- Rejestr: nieznany klucz zrodla/kraju → `KeyError` z lista dostepnych kluczy.

## 9. Strategia testowa i zgodnosc

**Inwariant:** wszystkie dotychczasowe testy przechodza **bez zmiany asercji**.

Dozwolone modyfikacje istniejacych testow (wylacznie mechaniczne):
- aktualizacja stalych patch-targetow po przeniesieniu modulow:
  - `_SESSION_PATCH` → `kartograf.providers.pl.gugik.requests.Session`
  - `_ORTO_SESSION_PATCH` → `kartograf.providers.pl.gugik_orto.requests.Session`
  - `_LAZ_SESSION_PATCH` → `kartograf.providers.pl.gugik_laz.requests.Session`
  - patch CLI `kartograf.providers.gugik_laz.GugikLazProvider` →
    `kartograf.providers.pl.gugik_laz.GugikLazProvider`
  - patche wewnetrzne `kartograf.providers.bdot10k.*` →
    `kartograf.providers.pl.bdot10k.*`
  - pelna lista do wyznaczenia grepem w planie (`kartograf.providers.gugik`,
    `kartograf.providers.bdot10k` w `tests/`)
- aktualizacja importow w testach po usunieciu starych modulow (bez shimow):
  `kartograf.providers.gugik*` / `kartograf.providers.bdot10k` →
  `kartograf.providers.pl.*`; `kartograf.providers.landcover_base` →
  `kartograf.providers.base` (mechaniczna zamiana sciezek, bez zmian asercji)
- jesli ktorys test asertuje dokladna zawartosc katalogu wynikowego —
  dopisanie `.meta.json` do oczekiwan (lista takich testow z grepa w planie).

Zakazane: zmiany asercji zachowania, usuwanie testow, oslabianie mockow.

Jakosc: `ruff check` + `ruff format --check` + `mypy kartograf/` czyste;
pokrycie nie spada ponizej 80%.

## 10. Zgodnosc wsteczna — podsumowanie kontraktow

| Kontrakt | Status po etapie 0 |
|---|---|
| `from kartograf import GugikProvider, ...` (pelna lista `__all__`) | bez zmian |
| `from kartograf.providers.gugik import GugikProvider` (i pokrewne) | **BREAKING** → `kartograf.providers.pl.gugik` (bez shimow — decyzja uzytkownika) |
| `from kartograf.providers.landcover_base import LandCoverProvider` | **BREAKING** → `kartograf.providers.base` |
| `LandCoverProvider.download_by_teryt` / `validate_teryt` / `source_url` | dziala (deprecated alias) |
| CLI: wszystkie komendy z CLAUDE.md | identyczne zachowanie |
| Struktura katalogow danych | identyczna + pliki `.meta.json` |
| `MetadataCache` (schemat SQLite) | bez zmian (rozszerzenie w etapie 1) |

## 11. Ryzyka i mitygacje

| Ryzyko | Mitygacja |
|---|---|
| Przenosiny modulow lamia patch-targety testow | patch-targety sa stalymi w testach (1 linia/plik); pelna lista grepem; commit przenosin osobny i weryfikowany pelnym pytest |
| Hydrograf/Hydrolog importuja gleboka sciezke providers | wpis BREAKING w CHANGELOG z tabelka starych → nowych sciezek; publiczne API `from kartograf import ...` bez zmian; migracja jednoliniowa |
| Fasada CLI pominie helper uzywany w testach | grep `from kartograf.cli.commands import` + `kartograf.cli.commands.` w tests/ przed podzialem |
| Sidecar psuje test asertujacy zawartosc katalogu | grep `iterdir\|listdir\|glob` w tests/ przy plikach wynikowych; korekta oczekiwan (dozwolona lista) |
| Zbyt ambitna unifikacja ABC zmienia kontrakt | podzial abstract/konkret przepisany ze stanu obecnego; nowe metody tylko konkretne wrappery |
| Rozrost zakresu ("skoro juz refaktorujemy...") | twarda lista "nie wchodzi" (sekcja 4); wszystko spoza listy = osobna decyzja |

## 12. Kryteria akceptacji

1. Pelny `pytest`: dotychczasowe testy zielone (zmiany tylko z listy w sekcji 9)
   + nowe testy komponentow z 6.12.
2. `ruff check`, `ruff format --check`, `mypy kartograf/` — czyste.
3. `kartograf download N-34-130-D-d-2-4` dziala identycznie i dodatkowo tworzy
   `N-34-130-D-d-2-4.asc.meta.json` z poprawnymi CRS-ami i licencja.
4. Wszystkie kontrakty z sekcji 10 potwierdzone testami.
5. Deskryptory PL kompletne; test spojnosci deskryptor↔provider zielony.
6. Dokumentacja zaktualizowana: nowy ADR (deskryptory + rejestry + polityka
   transformacji + sidecar; kontekst = research 3 krajow), CHANGELOG (0.7.0-dev,
   w tym wpis **BREAKING** o sciezkach importow providerow z tabelka migracji),
   CLAUDE.md (struktura modulow), PROGRESS.md.

## 13. Decyzje doprecyzowane wzgledem zatwierdzonego podsumowania

1. **Silniki transportu.** Zatwierdzone podsumowanie mowilo o zdefiniowaniu
   interfejsu silnikow i implementacji trzech uzywanych przez PL (WMS-skorowidz,
   WCS, kafel-po-URL). Po analizie kodu etap 0 realizuje to weziej: transporty
   jako **dane** (`TransportKind` + capabilities w deskryptorze) oraz dwa
   wspolne narzedzia (`http.py`, `mosaic.py`); logika WCS/WMS-skorowidzow
   **pozostaje w `gugik.py`**. Powod: jedynym konsumentem WMS-skorowidzow jest
   i pozostanie GUGiK, a WCS zyska drugiego konsumenta dopiero przy DE/SK —
   ekstrakcja teraz to ryzyko dla ~1060 testow bez zadnego zysku funkcjonalnego.
   Formalny interfejs silnika powstanie w etapie 1 przy `CuzkClient` (pierwszy
   realny drugi przypadek).
2. **Sidecar a "brak nowych funkcji".** Podsumowanie zawieralo sprzecznosc:
   "kazde pobranie dostaje sidecar" oraz "bez jednej nowej funkcji uzytkowej".
   Rozstrzygniecie: sidecar **wchodzi** w etap 0 jako jedyna zmiana
   obserwowalna — bez niego refaktor nie jest weryfikowalny end-to-end
   (deskryptory nie mialyby zadnego konsumenta), a etap 1 debugowalby dwie
   nowe rzeczy naraz. Decyzja "scalanie w Hydrografie" czyni metadane
   potrzebnymi takze dla danych polskich.
