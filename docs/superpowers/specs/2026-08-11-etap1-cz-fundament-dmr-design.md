# Spec: Etap 1 — fundament CZ + DMR (CUZK)

**Data:** 2026-08-11
**Status:** szkic do review
**Wersja docelowa:** 0.7.0 (develop)
**Dokumenty zrodlowe:**
- `docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md` (spec etapu 0,
  sekcja 3 — decyzje kierunkowe etapu 1)
- `docs/research/2026-08-10-czechy-dmr-zabaged.md` (research CUZK, wszystkie endpointy
  weryfikowane na zywo)
- ADR-022 (architektura zrodel wielokrajowych)

---

## 1. Kontekst i cel

Etap 0 (refaktor przygotowawczy) jest zmergowany do develop i zweryfikowany e2e
(macierz 12/12 na realnych danych GUGiK). Kartograf ma teraz: deskryptory zrodel
(`sources/`), sidecar `.meta.json`, twarda polityke transformacji (`transform/crs.py`),
wspolne narzedzia transportowe (`transport/`), rejestr systemow godel
(`core/parser_registry.py`) i providery polskie w `providers/pl/`.

Etap 1 dodaje **pierwszy zagraniczny kraj: Czechy (CUZK)** w zakresie NMT:
- **DMR 5G** (odpowiednik NMT 1m) — raster 2 m z uslugi `exportImage`
- **DMR 4G** (odpowiednik NMT 5m) — GeoTIFF 5 m z plikow `openzu` (arkusze SM5)
  oraz raster z `exportImage`

wraz z fundamentem pod etapy 2-3: `CuzkClient` (silnik ArcGIS REST + pliki),
`SheetIndex` (indeks arkuszy `KladyMapovychListu` + cache), parsery godel `cz_tm33`
i `cz_sm5`, flaga CLI `--country {pl,cz,auto}`, deskryptory CZ z polem `endpoint`.

Motyw przewodni: analizy transgraniczne (zlewnie przekraczajace granice PL/CZ).
Scalania rastrow miedzykrajowych NIE ma — to zadanie Hydrografa; Kartograf dostarcza
osobne pliki per kraj z pelnymi sidecarami (kontrakt z etapu 0).

## 2. Ustalenia z researchu ksztaltujace projekt

| # | Fakt (zweryfikowany na zywo) | Konsekwencja projektowa |
|---|---|---|
| 1 | `exportImage` zwraca GeoTIFF float32 dla dowolnego bboxa; limit 15000x4100 px; `imageSR=2180` dziala (reprojekcja serwerowa) | tryb bbox = jeden wycinek serwerowy; kafelkowanie + `mosaic_and_crop` powyzej limitu; `--target-crs` przez `imageSR` |
| 2 | Obszar poza terytorium CZ wypelniany **zerami bez oznaczenia** (49,3% kafla przy Cieszynie) | kazde zadanie exportImage MUSI niesc `noData=-9999` + `noDataInterpretation`; sidecar deklaruje nodata |
| 3 | URL-e openzu w pelni przewidywalne: `https://openzu.cuzk.gov.cz/opendata/{PRODUKT}/epsg-{5514\|3045}/{ARKUSZ}.zip`; katalog bez listingu (403) | pobieranie plikowe bez feedow ATOM; potrzebna tylko nazwa arkusza |
| 4 | Siatka TM33 2x2 km **obliczalna** (`{E_km}_{N_km}`, naroznik SW, EPSG:3045, zweryfikowana wobec georss); SM5 (`CTES86`) **nieobliczalne** (nazwa miasta + cyfry) | dwa systemy godel: `cz_tm33` czysta matematyka (jak Parser2000), `cz_sm5` przez indeks |
| 5 | `KladyMapovychListu` MapServer: warstwa 24 = SM5 (`MAPNOM`, `MAPNAME`, `PODIL`), warstwa 26 = TM33 (`MAPNOM`, `IN_CZ`); zapytania po bboxie | `SheetIndex` + cache (indeks statyczny); `PODIL` < 1 dla arkuszy przygranicznych → sidecar |
| 6 | DMR4G-TIFF: `crs=None`, georeferencja tylko w `.tfw`, nodata -9999, 500x400 px @ 5 m = dokladnie jeden arkusz SM5 | po rozpakowaniu jawne przypisanie EPSG:5514 (naprawa metadanych, nie transformacja) |
| 7 | 5514→2180 w PROJ: najlepsza operacja (0,051 m) uzywa siatki slowackiej (`inf` w CZ); domyslny wybor PROJ (1,0 m) rozni sie o 1,1 m od najlepszej bezsiatkowej (0,5 m) | reprojekcje pozioma **preferowac serwerowo** (`imageSR`); lokalnie tylko przez `build_pinned_transform` z probe |
| 8 | Bpv = EPSG:8357 (Baltic **1957**, nie 1977/5705; potwierdzone w `vcsWkid` uslug); Bpv→EVRF2007 (5621) = operacja EPSG, 0,1 m, offset +0,117..+0,143 m; sciezki do 9650/9651 = tylko ballpark (siatki GUGiK niepubliczne) | `--vertical-crs EVRF2007` → przypieta 8357→5621; KRON86 → `TransformUnavailableError` z remedium |
| 9 | EPSG:5514 ma wspolrzedne ujemne; Krovak to stozkowa ukosna (nie TM); EPSG:3045 ma osie N,E | `always_xy=True` wszedzie; zadna logika nie zaklada matematyki TM dla 5514 |
| 10 | Brak kluczy API, OAuth, limitow wolumenu; CC BY 4.0; jednolite pokrycie 100% kraju (nie ma problemu "1m jest, 5m nie ma") | brak walidacji dostepnosci przed pobraniem (inaczej niz GUGiK); prostszy provider |

## 3. Zakres etapu 1

**Wchodzi:**
1. `providers/cuzk/` — `client.py` (CuzkClient), `sheets.py` (SheetIndex, Sm5Sheet),
   `dmr.py` (CuzkDmrProvider), `__init__.py` (fabryka `create_dmr_provider`)
2. `core/parser_tm33.py` — ParserTM33 (czysta matematyka, zero IO)
3. Rejestracja systemow `cz_tm33` i `cz_sm5` w `core/parser_registry.py`
4. Deskryptory `cz.cuzk.dmr5g`, `cz.cuzk.dmr4g` + `CountryProfile("CZ")` + pole
   `endpoint` w `AccessChannel` + licencja `_CUZK_LICENSE`
5. `MetadataCache`: nowa tabela `sheet_cache`
6. CLI: `--country {pl,cz,auto}`, `--target-crs`, rozszerzenia `--resolution` (`2m`),
   `--vertical-crs` (`Bpv`), `--bbox-crs` (`EPSG:5514`, `EPSG:3045`); przeplyw
   `_cmd_download_cz` (wzor: `_cmd_download_laz`)
7. Rejestr ukladow pionowych: **`EVRF2007` → EPSG:5621 globalnie** (decyzja
   uzytkownika 2026-08-11), nowa nazwa `EVRF2007-PL` → EPSG:9651, `Bpv` → EPSG:8357;
   mapowanie rodzina→realizacja przy budowie sidecara
8. Rozstrzygniecia odroczone z etapu 0: jawna selekcja kanalu w `build_metadata`
   (parametr `capability`), objecie probe polityka sieci w `transform/crs.py`
9. Sidecary CZ: `transform` (konwencja opisow) i `extra` (`PODIL`, godlo kafla);
   `extra.parent_request` grupujacy pliki jednego zadania `--country auto`
   (fundament pod przyszle scalanie w Hydrografie lub Kartografie)
10. Dokumentacja: nowy ADR (silnik CUZK + polityka ukladow CZ + decyzja EVRF2007),
    CHANGELOG, CLAUDE.md, SCOPE.md (w tym zalegle drzewo modulow z etapu 0), PROGRESS

**Nie wchodzi (jawnie poza zakresem):**
- DMP 1G / DMP OK (NMPT), Ortofoto CZ, LAZ (natywny format DMR 5G/4G) — **etap 2**
- ZABAGED — **etap 3**
- DE i SK — osobne decyzje po etapie 3
- zmiany API `DownloadManager` i `LandCoverManager` (przeplyw CZ omija managera —
  patrz sekcja 13.1; jedyny wyjatek: addytywny opcjonalny parametr
  `sidecar_extra` w konstruktorze `DownloadManager` dla `parent_request`,
  sekcja 5.9)
- ekstrakcja silnika ArcGIS z `providers/cuzk/client.py` do `transport/` (nastapi
  przy drugim konsumencie: DE/SK — patrz sekcja 13.4)
- migracja PL na `transport/http.py` (bez zmian — oportunistycznie pozniej)
- scalanie rastrow miedzykrajowych (nigdy — zadanie Hydrografa)
- naprawa endpointu WCS EVRF2007 GUGiK (usuniety przez GUGiK 2026-08-11; osobny temat)

## 4. Architektura po etapie 1

```
kartograf/
├── sources/
│   ├── descriptor.py         # + AccessChannel.endpoint (str, default "")
│   ├── registry.py           # + cz.cuzk.dmr5g, cz.cuzk.dmr4g, CountryProfile CZ,
│   │                         #   _CUZK_LICENSE, nowe _VERTICAL_CRS_CODES,
│   │                         #   _VERTICAL_FAMILY (rodzina→realizacje)
│   └── sidecar.py            # build_metadata(+capability=), nodata=, GeoTIFF
├── transform/crs.py          # probe pod polityka sieci (bez zmian API)
├── transport/                # bez zmian (konsumowane przez CuzkClient)
├── core/
│   ├── parser_tm33.py        # NOWE — ParserTM33 (godlo↔bbox, czysta matematyka)
│   └── parser_registry.py    # + cz_tm33, cz_sm5 (PRZED fallbackiem pl1992)
├── providers/
│   ├── pl/                   # bez zmian
│   └── cuzk/                 # NOWE
│       ├── __init__.py       # create_dmr_provider(resolution, ...) — czeskie domysly
│       ├── client.py         # CuzkClient — silnik: exportImage (+kafelkowanie),
│       │                     #   query (+paginacja), pliki openzu (ZIP→TIFF)
│       ├── sheets.py         # SheetIndex (KladyMapovychListu + sheet_cache), Sm5Sheet
│       └── dmr.py            # CuzkDmrProvider (BaseProvider): download / download_bbox
├── cache/metadata.py         # + tabela sheet_cache (+ clear/stats/prune/CLI)
├── download/                 # bez zmian (manager i storage nietkniete;
│                             #   CZ uzywa FileStorage(subdir=...) + get_raw_path)
└── cli/
    ├── _parser.py            # + --country, --target-crs, 2m, Bpv, 5514/3045
    └── download_cmd.py       # + dyspozycja per kraj, _cmd_download_cz,
                              #   _resolve_country (godlo/bbox → kraj)
```

Granice odpowiedzialnosci (kontynuacja etapu 0): deskryptory opisuja (teraz takze
`endpoint`), `CuzkClient` wykonuje transport i nie zna CLI, provider skleja klienta
z deskryptorem, sidecary pisze warstwa CLI (przeplyw CZ) — nie provider.

## 5. Komponenty

### 5.1 `sources/descriptor.py` — pole `endpoint`

`AccessChannel` dostaje pole `endpoint: str = ""` (addytywne; wpisy PL bez zmian —
dla nich zrodlem prawdy pozostaja stale providerow, zgodnie z etapem 0). Pierwszym
konsumentem jest `CuzkClient`: prowadzenie po deskryptorze oznacza, ze provider CZ
nie ma zahardkodowanych URL-i — bierze je z kanalow deskryptora.

### 5.2 `sources/registry.py` — wpisy CZ i uklady pionowe

**Licencja:**

```python
_CUZK_LICENSE = LicenseInfo(
    id="CC-BY-4.0",
    attribution="Podklad: Cesky urad zememericky a katastralni (CUZK), CC BY 4.0",
    url="https://geoportal.cuzk.gov.cz",
)
```

**Deskryptory (wartosci docelowe):**

| pole | `cz.cuzk.dmr5g` | `cz.cuzk.dmr4g` |
|---|---|---|
| product | `nmt` | `nmt` |
| resolution | `2m` | `5m` |
| storage_subdir | `cz_dmr5g` | `cz_dmr4g` |
| default_extension | `.tif` | `.tif` |
| kanaly | ARCGIS_IMAGE → `bbox_raster` | DIRECT_FILES → `sheet_files`; ARCGIS_IMAGE → `bbox_raster` |
| tile_scheme | `computable`, EPSG:3045, 2000x2000 m, "TM33 {E_km}_{N_km}, naroznik SW" | `index`, EPSG:5514, 2500x2000 m, "SM5: 4 litery miasta + 2 cyfry, indeks KladyMapovychListu w. 24" |

Kanaly (wspolne pola): `horizontal_crs="EPSG:5514"`, `vertical_crs_options=("EPSG:8357",)`,
`vertical_source="native"`. Kanal ARCGIS_IMAGE: `server_reprojection=True`,
`endpoint="https://ags.cuzk.gov.cz/arcgis2/rest/services/{dmr5g|dmr4g}/ImageServer"`.
Kanal DIRECT_FILES (dmr4g): `endpoint="https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/epsg-5514/{sheet}.zip"`.
Kanal plikowy DMR5G (LAZ) i warianty epsg-3045 dochodza w etapie 2.

**Kraj:**

```python
"CZ": CountryProfile(
    code="CZ", name="Czechy",
    extent_wgs84=BBox(12.09, 48.55, 18.86, 51.06, "EPSG:4326"),
    dataset_keys=("cz.cuzk.dmr4g", "cz.cuzk.dmr5g"),
)
```

Zasieg przyblizony (jak PL) — na styku granicy `--country auto` ma pobrac z obu
krajow, co jest zamierzone.

**Uklady pionowe (decyzja uzytkownika 2026-08-11 — „EVRF2007 globalnie = 5621"):**

```python
_VERTICAL_CRS_CODES = {
    "KRON86": "EPSG:9650",       # PL-KRON86-NH (bez zmian)
    "EVRF2007": "EPSG:5621",     # ZMIANA: ogolnoeuropejski EVRF2007
    "EVRF2007-PL": "EPSG:9651",  # NOWE: realizacja polska PL-EVRF2007-NH
    "Bpv": "EPSG:8357",          # NOWE: Baltic 1957 (CZ)
}

# Rodzina -> realizacje krajowe. Konsumowane przy budowie sidecara:
# jesli kod rodziny nie wystepuje w vertical_crs_options kanalu, ale wystepuje
# jego realizacja — sidecar zapisuje kod realizacji (fakt, nie zyczenie).
_VERTICAL_FAMILY = {"EPSG:5621": ("EPSG:9651",)}
```

Skutki:
- CLI `--vertical-crs EVRF2007` dziala jak dotad dla PL (wybiera dane w ukladzie
  EVRF2007; GUGiK publikuje realizacje PL) i dla CZ (cel transformacji z Bpv).
- Deskryptory PL **bez zmian** (opcje 9650/9651 — stan faktyczny danych GUGiK).
- Sidecary PL **bez zmian tresci**: `build_metadata` mapuje "EVRF2007"→5621,
  nie znajduje 5621 w opcjach kanalu PL, znajduje realizacje 9651 → zapisuje 9651.
  Sidecary CZ po transformacji pionowej zapisuja 5621 (kod docelowy operacji).
- `vertical_crs_code("EVRF2007")` zmienia wynik z 9651 na 5621 — **BREAKING** dla
  bezposrednich konsumentow tej funkcji (wpis w CHANGELOG); nowa nazwa `EVRF2007-PL`
  daje jawny dostep do 9651.

### 5.3 `core/parser_tm33.py` + rejestracja systemow CZ

**ParserTM33** — czysta matematyka, wzor `Parser2000`:

```python
class ParserTM33:
    godlo: str                      # "302_5550"
    uklad = "cz_tm33"
    def get_bbox(self) -> BBox      # EPSG:3045: (E*1000, N*1000, E*1000+2000, N*1000+2000)
    @staticmethod
    def tile_for(easting: float, northing: float) -> str   # naroznik SW, krok 2 km
def find_tiles_tm33_for_bbox(bbox: BBox) -> list[str]      # bbox EPSG:3045 -> kafle
```

Walidacja godla: `^\d{3}_\d{4}$` + parzystosc kilometrow (kafle co 2 km);
niepoprawne → `ParseError`. Przyklad zweryfikowany researchem: `302_5550` →
E 302000..304000, N 5550000..5552000.

**Rejestracja w `parser_registry`** — dwa nowe wpisy **pomiedzy** `pl2000`
a fallbackiem `pl1992` (fallback ma `detect=lambda godlo: True`, wiec kolejnosc
jest krytyczna):

| id | country | detect | path_parts |
|---|---|---|---|
| `cz_tm33` | CZ | `^\d{3}_\d{4}$` | split po `_` → `["302", "5550"]` |
| `cz_sm5` | CZ | `^[A-Z]{4}\d{2}$` | `[godlo[:4], godlo[4:]]` → `["CTES", "96"]` |

Wzorce nie koliduja z PL (PL-1992 ma myslniki, PL-2000 kropki). `parser_factory`
dla `cz_tm33` → `ParserTM33`; dla `cz_sm5` → `Sm5Sheet` (sekcja 5.4; `get_bbox()`
wymaga indeksu — IO dopiero przy wywolaniu, nigdy przy imporcie ani konstrukcji).

`SheetParser` **nie jest** generalizowany w etapie 1: pozostaje parserem godel
polskich (jego API to kontrakt PL). Przeplyw CZ pracuje na parserach z rejestru
(`detect_system(...).parser_factory(...)`) i `FileStorage.get_raw_path()` —
`SheetParser(godlo_cz)` nadal rzuca `ParseError`, co jest poprawne (godlo CZ bez
`--country cz`/auto-detekcji to blad uzytkownika). Analogicznie
`find_sheets_for_bbox(system=...)` nie dostaje systemow CZ (tryb bbox CZ nie
rozwija bboxa na arkusze — sekcja 5.7).

### 5.4 `providers/cuzk/sheets.py` — SheetIndex + Sm5Sheet + `sheet_cache`

```python
class SheetIndex:
    """Indeks arkuszy KladyMapovychListu (ArcGIS REST /query) z cache SQLite."""
    def __init__(self, session=None, cache: MetadataCache | None = None,
                 endpoint: str = KLADY_ENDPOINT): ...
    def sm5_sheet(self, mapnom: str) -> SheetInfo          # warstwa 24, po MAPNOM
    def sm5_sheets_for_bbox(self, bbox: BBox) -> list[SheetInfo]   # warstwa 24
    def tm33_tiles_for_bbox(self, bbox: BBox) -> list[SheetInfo]   # warstwa 26

@dataclass(frozen=True)
class SheetInfo:
    godlo: str          # MAPNOM ("CTES86" / "756_5516")
    name: str | None    # MAPNAME ("Cesky Tesin 8-6"); None dla TM33
    bbox: BBox          # EPSG:5514 (w. 24) / EPSG:3045 (w. 26)
    podil: float | None # udzial arkusza w terytorium CZ; None dla TM33
    in_cz: bool | None  # warstwa 26; None dla SM5
```

- Endpoint: `https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer`
  (uwaga: host `arcgis`, nie `arcgis2`). Zapytania przez `CuzkClient.query`
  (`f=json`, `geometry`+`geometryType=esriGeometryEnvelope` lub `where=MAPNOM='...'`,
  `outFields`, paginacja `resultOffset`/`exceededTransferLimit`). Dokladne parametry
  warstw 24/26 oznaczone w researchu jako niezweryfikowane — potwierdzenie na zywo
  jest pierwszym krokiem implementacji (sekcja 12).
- **Konsumenci w etapie 1:** (a) walidacja godla SM5 przed pobraniem (nieznany
  `MAPNOM` → czytelny blad zamiast 404 z openzu), (b) `PODIL` + bbox do sidecara,
  (c) `sm5_sheets_for_bbox` jako fundament etapu 2 (LAZ/Orto) — zaimplementowane
  i przetestowane, bez konsumenta CLI w etapie 1.
- **`Sm5Sheet`** — obiekt parsera dla rejestru: `godlo`, `uklad = "cz_sm5"`,
  `get_bbox()` deleguje do `SheetIndex` (lazy, z cache). Przeplyw pobierania SM5
  nie potrzebuje bboxa (URL openzu = czysta nazwa), wiec sciezka szczesliwa nie
  dotyka sieci poza samym pobraniem i zapytaniem o `PODIL`.

**`MetadataCache.sheet_cache`** — trzecia tabela (`CREATE TABLE IF NOT EXISTS`,
stare bazy doposaza sie same przy otwarciu):

```sql
CREATE TABLE IF NOT EXISTS sheet_cache (
    system    TEXT NOT NULL,      -- "cz_sm5" | "cz_tm33"
    godlo     TEXT NOT NULL,      -- MAPNOM
    payload   TEXT NOT NULL,      -- JSON: bbox, name, podil, in_cz
    cached_at REAL NOT NULL,
    PRIMARY KEY (system, godlo)
)
```

TTL wg wzorca leniwego per-odczyt jak `url_cache`; dla `sheet_cache` osobna stala
`SHEET_TTL_SECONDS = 30 * 24 * 3600` (indeks arkuszy jest praktycznie staly).
Rozszerzenia: `clear()`, `stats()` (+`sheet_count`), `prune_expired()`,
`kartograf cache stats` drukuje dodatkowo `Sheet entries`.

### 5.5 `providers/cuzk/client.py` — CuzkClient (silnik)

Pierwszy silnik sterowany deskryptorem (ADR-022). Trzy kontrakty metod — pisane
generycznie (parametryzowane endpointem, bez wiedzy o produktach), tak by DE/SK
mogly je pozniej wyniesc do `transport/` bez zmian semantyki:

```python
class CuzkClient:
    def __init__(self, session: requests.Session | None = None,
                 timeout: int = 60): ...

    def export_image(self, endpoint: str, bbox: BBox, *, pixel_size: float,
                     image_sr: str, no_data: float = -9999.0,
                     output_path: Path) -> Path:
        """GET {endpoint}/exportImage; f=image, format=tiff, pixelType=F32,
        bboxSR z bbox.crs, imageSR, size wyliczony z bbox i pixel_size,
        noData + noDataInterpretation=esriNoDataMatchAny.
        Rozmiar > 15000x4100 px => podzial bboxa na kafle, pobranie kazdego
        do pliku tymczasowego, mosaic_and_crop(inputs, bbox, output_path,
        nodata=no_data). Zapis przez transport.http.download_to (atomic+retry).
        Odpowiedz nie-TIFF (JSON bledu ArcGIS, HTML) => DownloadError z trescia."""

    def query(self, endpoint: str, layer: int, *, bbox: BBox | None = None,
              where: str | None = None, out_fields: str = "*",
              out_sr: str | None = None) -> list[dict]:
        """GET {endpoint}/{layer}/query; f=json; paginacja resultOffset/
        resultRecordCount dopoki exceededTransferLimit."""

    def fetch_file(self, url: str, output_path: Path, *,
                   unzip_single: str | None = None) -> Path:
        """Pobierz plik przez transport.http.download_to; gdy unzip_single
        (np. ".tif") — wyciagnij z ZIP jedyny plik o tym rozszerzeniu
        (+ towarzyszacy .tfw), zapisz atomowo, usun ZIP."""
```

Zasady:
- limity `MAX_EXPORT_WIDTH = 15000`, `MAX_EXPORT_HEIGHT = 4100` jako stale klasy;
  kafelkowanie deterministyczne (siatka wierszy/kolumn, zaokraglenia do pelnych
  pikseli), kazdy kafel z tym samym `no_data`;
- `no_data` NIGDY nie jest pomijane (fakt #2 z sekcji 2);
- retry/backoff i atomic write pochodza z `transport/http.py` (pierwszy konsument
  produkcyjny tych narzedzi);
- klient nie zna godel, produktow ani sidecarow.

### 5.6 `providers/cuzk/dmr.py` — CuzkDmrProvider

`BaseProvider` (kontrakt z `providers/base.py`):

```python
class CuzkDmrProvider(BaseProvider):
    def __init__(self, resolution: str = "2m",          # "2m" -> dmr5g, "5m" -> dmr4g
                 session=None, cache: MetadataCache | None = None,
                 target_crs: str | None = None,         # None = natywnie
                 vertical_crs: str = "Bpv"): ...
    # descriptor_key = "cz.cuzk.dmr5g" | "cz.cuzk.dmr4g"
    # default_extension = ".tif"

    def download(self, godlo: str, output_path: Path, timeout: int = 60) -> Path:
        # cz_sm5 (tylko 5m): walidacja w SheetIndex -> fetch_file(openzu, unzip .tif)
        #   -> przypisanie EPSG:5514 (rasterio, tryb r+; naprawa metadanych)
        # cz_tm33: bbox kafla (EPSG:3045) -> export_image(imageSR=3045)
        # kombinacje niedozwolone (SM5 + 2m) -> ValidationError

    def download_bbox(self, bbox: BBox, output_path: Path,
                      format: str = "GTiff", timeout: int = 60) -> Path:
        # export_image(endpoint wg resolution, imageSR = target_crs lub "EPSG:5514",
        #              pixel_size = 2.0 / 5.0)
```

- Endpointy brane z deskryptora (`get_source(self.descriptor_key)`), nie z modulu.
- `vertical_crs`: `"Bpv"` = natywnie (bez transformacji); `"EVRF2007"` = po pobraniu
  wartosci rastra przeliczone przypieta operacja `build_pinned_transform("EPSG:8357",
  "EPSG:5621", policy)` (offset stalopodobny +0,12..+0,14 m; operacja EPSG 0,1 m);
  `probe_point` w EPSG:8357 nie ma sensu dla operacji czysto pionowej — polityka:
  `TransformPolicy(min_accuracy_m=0.2)`, kontrola `isfinite` na wartosciach;
  `"KRON86"` → `TransformUnavailableError` z remedium z `REMEDIES` (cel 9650).
  Opis wybranej operacji + accuracy trafiaja do sidecara (`transform`).
- Zasada natywnosci: transformacja pionowa wylacznie na jawne zadanie; wynik
  exportImage to pochodna serwera (GeoTIFF), pliki openzu to bajty CUZK 1:1
  (modyfikowany jest wylacznie tag CRS w GeoTIFF bez CRS — naprawa metadanych).

Fabryka `providers/cuzk/__init__.py::create_dmr_provider(resolution="2m", ...)`
— jedno miejsce czeskich domyslow (wzor `providers/pl/create_nmt_provider`);
walidacja `resolution in {"2m", "5m"}`.

### 5.7 CLI — `--country`, dyspozycja i przeplyw CZ

**`_parser.py`:**
- `--country {pl,cz,auto}`, default `auto`
- `--target-crs` (etap 1: akceptowane `EPSG:2180`, `EPSG:5514`, `EPSG:3045`;
  dziala tylko dla CZ — reprojekcja serwerowa `imageSR`; z `--country pl` →
  `ValidationError` z komunikatem, ze PL pobiera natywnie)
- `--resolution`: choices `["1m", "5m", "2m"]`, **default `None`** (sentinel);
  rozwiazywany per kraj: PL→`1m`, CZ→`2m`
- `--vertical-crs`: choices `["KRON86", "EVRF2007", "Bpv"]`, **default `None`**;
  rozwiazywany per kraj: PL→`EVRF2007`, CZ→`Bpv` (natywnie)
- `--bbox-crs`: + `EPSG:5514`, `EPSG:3045`

**Dyspozycja w `cmd_download` (`_resolve_country`):**
1. godlo podane → `detect_system(godlo)`; kraj z `SheetSystem.country`;
   jawny `--country` sprzeczny z krajem systemu → `ValidationError`
   (np. `download CTES96 --country pl`)
2. `--bbox`/`--geometry` + `--country pl|cz` → przeplyw danego kraju
3. `--bbox`/`--geometry` + `auto` → bbox transformowany do WGS84, przeciecie
   z `extent_wgs84` wszystkich `CountryProfile`; dla kazdego przecietego kraju
   osobne pobranie czesci bboxa (osobne pliki, osobne sidecary, zero scalania);
   kazdy sidecar dostaje `extra.parent_request` wiazacy pliki w jedno logiczne
   zadanie (sekcja 5.9); `--resolution`/`--vertical-crs` musza byc
   rozwiazywalne dla KAZDEGO przecietego kraju — inaczej `ValidationError`
   z podpowiedzia jawnego `--country` (bez cichego pomijania kraju)
4. brak godla CZ w `--geometry` (pliki SHP/GPKG daja bbox → pkt 3)

Walidacje per kraj: `pl`+`2m` → `ValidationError`; `cz`+`1m` → `ValidationError`;
`cz` + `--product nmpt|orto|laz` → `ValidationError` („etap 2"); `cz`+`KRON86` →
blad transformacji z remedium; `--system` dotyczy tylko PL (CZ godla wykrywane
wzorcem; `--system` + `--country cz` → `ValidationError`).

**`_cmd_download_cz`** (wzor `_cmd_download_laz` — poza `DownloadManager`):
- godlo: parser z rejestru → `CuzkDmrProvider.download` →
  `FileStorage(output, subdir=descriptor.storage_subdir)` + `get_raw_path(godlo,
  f"{godlo}.tif")` (TM33: `cz_dmr5g/302/5550/302_5550.tif`; SM5:
  `cz_dmr4g/CTES/96/CTES96.tif`)
- bbox: `CuzkDmrProvider.download_bbox` → jeden GeoTIFF plasko w katalogu wyjsciowym
  (parytet z API PL `download_bbox`), nazwa `cz_{dmr5g|dmr4g}_{minx}_{miny}_{maxx}_{maxy}.tif`
  (wspolrzedne w CRS zadania)
- `--force`/`skip_existing`, `--quiet`, podsumowanie ok/skip/fail — jak w LAZ
- sidecar po kazdym udanym pliku (sekcja 5.9)

**Asymetria trybu bbox (jawna decyzja):** dla PL `--bbox` rozwija sie na arkusze
i pobiera pliki zrodlowe (jak dotad); dla CZ `--bbox` zwraca jeden wycinek
serwerowy. Wynika to z natury kanalow (GUGiK: skorowidz→pliki; CUZK: exportImage);
kto potrzebuje czeskich danych zrodlowych 1:1, uzywa trybu godlowego (TM33/SM5) —
zgodnie z zasada natywnosci z etapu 0. Udokumentowane w help CLI.

### 5.8 Rozstrzygniecia odroczone z etapu 0

**(a) Jawna selekcja kanalu.** `build_metadata` dostaje parametr
`capability: str | None = None`. Podany → wybierany pierwszy kanal z ta
capability (`KeyError` gdy brak); `None` → dotychczasowa heurystyka bbox/nie-bbox
(zgodnosc wsteczna — istniejace wywolania bez zmian). Przeplywy CZ przekazuja
jawnie: `"sheet_files"` (SM5), `"bbox_raster"` (TM33/bbox). Managery PL moga
przejsc na jawne capability oportunistycznie (bez zmiany wyniku).

**(b) Probe pod polityka sieci.** W `build_pinned_transform` probe kandydatow
wykonuje sie w obrebie tego samego kontekstu `pyproj.network` (ustawionego wg
`policy.allow_network_grids`), w ktorym zbudowano grupe — a nie po przywroceniu
stanu globalnego. Gwarancja: wynik probe odpowiada srodowisku, w ktorym operacja
bedzie wykonywana produkcyjnie (siatka niedostepna bez sieci ma odpasc na probe,
nie na danych). Bez zmian publicznego API; test jednostkowy na te wlasnosc.

### 5.9 Sidecary CZ — `transform`, `extra`, nodata

- `build_metadata` dostaje tez jawny parametr `nodata: float | None = None`
  (ma pierwszenstwo przed sniffowaniem `.asc`); przeplyw CZ podaje `-9999.0`
  dla exportImage i wartosc z pliku dla DMR4G-TIFF.
- Konwencja `transform` (pierwsza materializacja szkicu z etapu 0):

```json
"transform": {
  "horizontal": "server:EPSG:2180",                      // gdy --target-crs
  "vertical": "pinned: Baltic 1957 height to EVRF2007 height (1) (0.1 m)"
}
```

  `null` gdy pobrano natywnie (domyslnie). Opis pionowy = `PinnedTransform.description`
  + accuracy.
- `extra` dla SM5: `{"mapname": "Cesky Tesin 8-6", "podil": 0.507}`;
  dla TM33: `{"in_cz": true}` gdy znane (bez zapytania do indeksu nie jest —
  wolno pominac); `podil < 1.0` to sygnal dla Hydrografa, ze arkusz jest
  przygraniczny (nodata/zera poza CZ).
- **`extra.parent_request`** — grupowanie plikow jednego zadania `--country auto`.
  Sidecary sa per plik; bez tego pola konsument (Hydrograf, przyszla scalarka)
  nie ma deterministycznego sposobu powiazania czesci PL i CZ tego samego bboxa.
  Przy trybie auto KAZDY plik wyniku (takze polskie arkusze) dostaje w `extra`:

```json
"parent_request": {
  "bbox": [530000.0, 382000.0, 533000.0, 386000.0],
  "bbox_crs": "EPSG:2180",
  "countries": ["PL", "CZ"]
}
```

  (`bbox`/`bbox_crs` = oryginalne zadanie uzytkownika PRZED podzialem na kraje;
  `countries` = kraje faktycznie przeciete). Przy jawnym `--country pl|cz`
  i w trybie godlowym pola nie ma (jedno zadanie = jeden kraj, grupowac nie ma
  czego). Mechanika po stronie PL: `DownloadManager` dostaje addytywny,
  opcjonalny parametr konstruktora `sidecar_extra: dict | None = None`,
  scalany przez `_write_sidecar` do `extra` kazdego sidecara (domyslnie `None`
  — zachowanie i tresc sidecarow PL poza trybem auto bez zmian); przeplyw CZ
  przekazuje to samo przez `build_metadata(extra=...)`.
- `horizontal_crs` w sidecarze = **faktyczny** uklad wyniku: `EPSG:3045` dla kafla
  TM33, `EPSG:5514` dla bbox natywnego, wartosc `--target-crs` przy reprojekcji
  serwerowej. `ResultMetadata` jest mutowalny — przeplyw CZ koryguje pole po
  `build_metadata` (precedens: `LandCoverManager._write_sidecar` dla CORINE PNG).

## 6. Przeplyw danych

```
CLI cmd_download
  └─ _resolve_country (godlo→rejestr parserow / bbox→extenty)
       ├─ PL → dotychczasowy przeplyw (DownloadManager) — bez zmian
       └─ CZ → _cmd_download_cz
             ├─ create_dmr_provider(resolution, target_crs, vertical_crs, cache)
             ├─ godlo TM33 → ParserTM33.get_bbox → CuzkClient.export_image
             ├─ godlo SM5  → SheetIndex.sm5_sheet (walidacja+PODIL, cache)
             │               → CuzkClient.fetch_file (openzu ZIP→TIFF, CRS 5514)
             ├─ bbox       → CuzkClient.export_image (kafelkowanie → mosaic_and_crop)
             ├─ (EVRF2007) → PinnedTransform 8357→5621 na wartosciach rastra
             └─ build_metadata(capability=..., nodata=..., transform=..., extra=...)
                → write_sidecar
```

Zadnego IO przy imporcie modulow (deskryptory to dane; indeks i siec dopiero
w wywolaniach).

## 7. Obsluga bledow

- exportImage: odpowiedz nie bedaca TIFF-em (JSON `{"error": ...}`, HTML) →
  `DownloadError` z poczatkiem tresci odpowiedzi; wyczerpanie retry → `DownloadError`.
- openzu 404 → `DownloadError` z podpowiedzia weryfikacji godla (indeks);
  nieznany `MAPNOM` w indeksie → `ValidationError` przed jakimkolwiek pobraniem.
- ZIP bez oczekiwanego pliku (`unzip_single`) → `DownloadError`.
- Konflikty CLI (kraj/godlo/rozdzielczosc/produkt/system) → `ValidationError`
  z komunikatem wskazujacym poprawna kombinacje.
- KRON86 dla CZ → `TransformUnavailableError` (remedium z `REMEDIES`: siatki
  `pl86_2019`/`pl07_2019` niepubliczne; uzyj EVRF2007/5621).
- Blad zapisu sidecara nadal nigdy nie przerywa pobrania (kontrakt etapu 0).
- Bledy indeksu arkuszy (siec) przy zapytaniu o `PODIL` po udanym pobraniu:
  warning + sidecar bez `extra.podil` (dane wazniejsze niz metadane wzbogacone).

## 8. Strategia testowa i zgodnosc

**Inwariant:** wszystkie dotychczasowe testy przechodza; zmiany istniejacych
testow wylacznie z listy ponizej.

Dozwolone zmiany istniejacych testow (wyliczone; pelne listy grepem w planie):
- `tests/test_sources_registry.py`: `EXPECTED_KEYS` (+2 klucze CZ),
  `test_sources_for_filters` (liczba zrodel), `test_country_pl`
  (`get_country("CZ")` przestaje rzucac — asercja do aktualizacji),
  `test_get_source_unknown_key_lists_available` (uzywa `cz.cuzk.dmr5g` jako
  klucza nieistniejacego — zamiana na np. `xx.none.zadne`),
  `test_vertical_crs_code` (nowe mapowanie — skutek decyzji uzytkownika),
  testy spojnosci PL mapujace nazwy przez `vertical_crs_code` (przejscie na
  mapowanie rodzina→realizacja).
- `tests/test_cli.py` / testy parsera: asercje domyslnych `--resolution`/
  `--vertical-crs` (wartosc → `None`-sentinel; zachowanie obserwowalne PL
  bez zmian — asertowane osobno).
- Zadne inne asercje zachowania nie zmieniaja sie; mocki bez oslabiania.

Nowe testy (offline; siec nigdy nie jest dotykana):
- `tests/test_parser_tm33.py` — godlo↔bbox (przyklady z researchu), walidacja,
  `find_tiles_tm33_for_bbox`, parzystosc.
- `tests/test_parser_registry.py` — rozszerzenie: detekcja `cz_tm33`/`cz_sm5`,
  kolejnosc przed fallbackiem, `path_parts`.
- `tests/test_cuzk_client.py` — exportImage: budowa URL/parametrow (w tym
  `noData`), kafelkowanie (patch `MAX_EXPORT_*` na male wartosci + syntetyczne
  TIFF-y rasterio → mosaic), odpowiedz JSON/HTML → `DownloadError`; query:
  paginacja `exceededTransferLimit`; fetch_file: ZIP→TIFF+tfw, atomic.
  Patch-target: `kartograf.providers.cuzk.client.requests.Session` (stala
  `_CUZK_SESSION_PATCH`), `...time.sleep` dla retry.
- `tests/test_cuzk_sheets.py` — SheetIndex: fixtury JSON warstw 24/26, cache
  hit/miss/TTL (`sheet_cache`), `Sm5Sheet.get_bbox` lazy.
- `tests/test_cuzk_dmr.py` — provider: dispatch SM5/TM33/bbox, przypisanie CRS
  do TIFF bez CRS, EVRF2007 (mock PinnedTransform), KRON86 → wyjatek, spojnosc
  deskryptor↔provider (wzor `TestDescriptorProviderConsistency`).
- `tests/test_cli.py` — `--country` dispatch, konflikty, auto-split bboxa
  (patch `_cmd_download_cz` i przeplywu PL), sentinel-defaults;
  `extra.parent_request` w sidecarach OBU krajow przy auto i jego brak przy
  jawnym `--country`.
- `tests/test_download_manager.py` — rozszerzenie addytywne: `sidecar_extra`
  scalany do `extra` sidecara; `None` (domyslnie) nie zmienia tresci sidecara.
- `tests/test_cache.py` — `sheet_cache` w stats/clear/prune.
- `tests/test_transform_crs.py` — probe pod polityka sieci (5.8b).
- `tests/test_sidecar.py` — `capability=`, `nodata=`, korekta `horizontal_crs`,
  `transform`/`extra` CZ.

Jakosc: `ruff check`, `ruff format --check`, mypy (zero nowych bledow wzgledem
baseline), pokrycie nie spada ponizej 80%.

## 9. Zgodnosc wsteczna — podsumowanie kontraktow

| Kontrakt | Status po etapie 1 |
|---|---|
| Cale CLI i API dla PL (godlo/bbox/geometry/landcover/soilgrids/cache) | bez zmian zachowania |
| `from kartograf import ...` (publiczne API) | bez zmian; + nowe eksporty CZ (`CuzkDmrProvider`, `ParserTM33`, `create_dmr_provider`) |
| Sidecary PL (tresc `.meta.json`) | bez zmian (rodzina→realizacja: nadal 9651) |
| `vertical_crs_code("EVRF2007")` | **BREAKING**: 9651 → 5621 (decyzja uzytkownika; `EVRF2007-PL` daje 9651) |
| `MetadataCache` schemat | rozszerzony addytywnie (`sheet_cache`); stare bazy kompatybilne |
| `DownloadManager` / `LandCoverManager` API | bez zmian (wyjatek addytywny: `DownloadManager(sidecar_extra=None)`) |
| Struktura katalogow PL | bez zmian; nowe podkatalogi `cz_dmr5g`, `cz_dmr4g` |
| `AccessChannel` | + pole `endpoint` (addytywne, default `""`) |

## 10. Ryzyka i mitygacje

| Ryzyko | Mitygacja |
|---|---|
| Niezweryfikowane parametry `/query` warstw 24/26 i `noData`/`noDataInterpretation` w exportImage | pierwsze zadanie planu implementacji = weryfikacja live (sekcja 12); dopiero potem kodowanie na fixture'ach z realnych odpowiedzi |
| exportImage dla `dmr4g` pokazany tylko jako endpoint (request zweryfikowano dla dmr5g) | ta sama weryfikacja live; fallback: DMR4G tylko plikowo (SM5) w etapie 1 |
| Zmiana `vertical_crs_code("EVRF2007")` psuje niewykrytego konsumenta | grep po repo + Hydrograf/Hydrolog w CHANGELOG (BREAKING z tabelka); nazwa `EVRF2007-PL` jako droga migracji |
| Wzorzec `^[A-Z]{4}\d{2}$` (SM5) przechwyci przyszly format innego kraju | rejestracja per kraj; kolejnosc deterministyczna; detekcja uzywana tylko po przejsciu wzorcow PL |
| Kafelkowanie exportImage: szwy/przesuniecia pikseli | kafle ciete po pelnych pikselach w ukladzie wyjsciowym; `mosaic_and_crop` waliduje CRS/rozdzielczosc wejsc; test syntetyczny 2x2 |
| Transformacja pionowa na rastrze (EVRF2007) zmienia bajty wyniku | to jawne zadanie uzytkownika (zasada natywnosci zachowana); sidecar `transform` dokumentuje operacje i accuracy |
| Rozrost zakresu („skoro robimy CZ, to od razu LAZ/orto") | twarda lista „nie wchodzi" (sekcja 3) |

## 11. Kryteria akceptacji

1. Pelny `pytest` zielony: dotychczasowe testy (zmiany tylko z listy w sekcji 8)
   + nowe testy komponentow CZ.
2. `ruff check`, `ruff format --check`, mypy — czyste (zero nowych bledow).
3. E2E na zywych danych (macierz minimalna):
   - `kartograf download 302_5550 --country cz` → `cz_dmr5g/302/5550/302_5550.tif`
     (EPSG:3045, 2 m, nodata -9999) + sidecar z licencja CC-BY-4.0 i Bpv/8357
   - `kartograf download CTES96 --resolution 5m` (kraj auto-wykryty) →
     `cz_dmr4g/CTES/96/CTES96.tif` z wpisanym EPSG:5514 + sidecar z `podil`
   - `kartograf download --bbox <przygraniczny> --country auto` → osobne pliki
     PL i CZ, kazdy z wlasnym sidecar-em zawierajacym ten sam
     `extra.parent_request` (oryginalny bbox + kraje); zadnego scalania
   - `--target-crs EPSG:2180` → GeoTIFF w 2180 (WKT zweryfikowany), sidecar
     `transform.horizontal = "server:EPSG:2180"`
   - `--vertical-crs EVRF2007 --country cz` → sidecar `vertical_crs = "EPSG:5621"`
     + opis przypietej operacji; `--vertical-crs KRON86 --country cz` → czytelny
     blad z remedium
4. Zachowanie PL niezmienione (probka regresyjna: download godla PL, landcover,
   cache stats).
5. Deskryptory CZ kompletne; test spojnosci deskryptor↔provider dla CZ zielony.
6. Dokumentacja: nowy ADR (CuzkClient + uklady CZ + decyzja EVRF2007→5621),
   CHANGELOG (BREAKING `vertical_crs_code`), CLAUDE.md, SCOPE.md (w tym zalegle
   drzewo modulow z etapu 0), PROGRESS.md.

## 12. Fakty do potwierdzenia live przed implementacja

Pierwsze zadanie planu implementacji (rekonesans, bez kodu produkcyjnego):
1. `KladyMapovychListu/{24,26}/query` — dokladne parametry, `maxRecordCount`,
   format odpowiedzi `f=json` (fixture'y do testow z realnych odpowiedzi),
   filtr `where=MAPNOM='CTES96'` vs zapytanie bbox.
2. `exportImage` z `noData=-9999&noDataInterpretation=esriNoDataMatchAny` —
   czy wartosc trafia do tagu nodata GeoTIFF i wypelnia obszar poza CZ.
3. `exportImage` na endpoincie `dmr4g` (request zweryfikowano tylko dla dmr5g).
4. Zachowanie HTTP openzu: nagly 429/limit, naglowki, redirecty (research
   milczy — przyjeto standardowe retry z `transport/http.py`).
5. `bboxSR=3045` + `imageSR=3045` dla kafla TM33 (research pokazal 5514 i 2180).

## 13. Decyzje doprecyzowane wzgledem specu etapu 0

1. **Przeplyw CZ omija `DownloadManager`** (precedens: LAZ). Manager jest silnie
   sprzezony z semantyka PL (`SheetParser`, rozwijanie hierarchii, reguly 5m/EVRF).
   Godlo CZ = zawsze jeden plik (bez hierarchii), wiec maszyneria managera nie
   daje zysku, a jego API pozostaje nietkniete (mniejsze pole razenia dla ~1140
   testow). Generalizacja managera — kandydat na refaktor przy DE/SK, gdy beda
   trzy realne przypadki.
2. **TM33 w trybie godlowym pobierany w EPSG:3045** (`bboxSR=3045&imageSR=3045`):
   kafel jest zdefiniowany w 3045 i odpowiada wariantowi `epsg-3045` publikowanemu
   przez CUZK; zadanie go w 5514 daloby obrocony czworokat zamiast kafla. Tryb
   bbox pozostaje natywnie w 5514 (uklad uslugi).
3. **Asymetria trybu bbox PL/CZ** (arkusze vs wycinek serwerowy) — jawnie
   udokumentowana; parytet danych zrodlowych 1:1 zapewnia tryb godlowy.
4. **„Formalny interfejs silnika" = kontrakty metod `CuzkClient`**
   (`export_image`/`query`/`fetch_file`), pisane generycznie i sterowane
   `endpoint` z deskryptora. Ekstrakcja do `transport/` nastapi przy drugim
   konsumencie (DE/SK) — wyciaganie interfejsu z jednego przypadku byloby
   projektowaniem na zapas (ta sama logika co decyzja 13.1 etapu 0).
5. **EVRF2007 → EPSG:5621 globalnie** (decyzja uzytkownika 2026-08-11) z mapa
   rodzina→realizacja, dzieki ktorej sidecary PL dalej niosa faktyczny kod 9651 —
   BREAKING ogranicza sie do funkcji `vertical_crs_code`.
6. **Domyslne `--resolution`/`--vertical-crs` przez sentinel `None`** rozwiazywany
   per kraj — jedyny sposob na krajowe domysly (CZ: 2m/Bpv) bez zgadywania, czy
   uzytkownik podal wartosc jawnie; zachowanie PL bez zmian.
