# PRD.md - Product Requirements Document
**Kartograf - Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 4.1
**Data:** 2026-10-08
**Product Owner:** Piotr
**Status:** Wydanie v0.7.0 (2026-10-08)

> Dokument opisuje wymagania produktowe wersji 0.7.0 w postaci
> zrealizowanej w kodzie wydania v0.7.0. Szczegóły zachowania (komunikaty,
> kody wyjścia, przypadki brzegowe) — `docs/SCOPE.md` i
> `docs/ARCHITECTURE.md`; uzasadnienia decyzji — `docs/DECISIONS.md`
> (ADR-022..ADR-030); historia zmian — `docs/CHANGELOG.md`. Pełna lista
> opcji CLI: `kartograf <komenda> --help`. Wymagania docelowe wersji
> 1.0.0 — sekcja 8 (roadmapa i kolejność podprojektów: `docs/SCOPE.md` 3.3).

---

## 1. Executive Summary

### 1.1 Problem Statement

Pobieranie danych przestrzennych z różnych źródeł (GUGiK, CUZK, Copernicus, ISRIC) jest:
- **Czasochłonne** - różne interfejsy webowe i protokoły API
- **Skomplikowane** - wymagana znajomość systemów identyfikacji (godła, TERYT, bbox)
- **Nieefektywne** - pobieranie plików jeden po drugim
- **Niejednolite** - różne formaty, układy współrzędnych i autentykacja dla każdego źródła
- **Wieloznaczne** - te same arkusze GUGiK występują w wielu kampaniach pomiarowych, a pliki nie niosą informacji o swoim pochodzeniu

### 1.2 Solution

Kartograf to narzędzie CLI + biblioteka Python oferujące:
1. **Unified API** - jednolity interfejs dla NMT, NMPT, Ortofoto, LAZ, Land Cover, SoilGrids
2. **Multiple Providers** - GUGiK (NMT/NMPT/Orto/LAZ/BDOT10k), CUZK (DMR 5G/4G, Czechy — etap 1), CORINE, SoilGrids
3. **Intelligent Selection** - godło (PL-1992/PL-2000, CZ TM33/SM5), TERYT, bbox, plik geometrii; wybór kraju `--country {pl,cz,auto}`
4. **Automatic Processing** - scalanie warstw BDOT10k, kalkulacja HSG, wycinek NMT z mozaiki arkuszy z lokalną reprojekcją (`--target-crs`)
5. **Provenance** - kanoniczny układ katalogów `data/`, metadane `<plik>.meta.json` dla każdego pobrania, jawny wybór kampanii GUGiK
6. **Secure Auth** - Auth Proxy dla izolacji credentials CLMS

### 1.3 Target Users

| Persona | Potrzeby | Użycie |
|---------|----------|--------|
| **Deweloper Hydrograf/Hydrolog** | Dane NMT, gleba, HSG dla obliczeń | Python API |
| **Specjalista GIS** | Dane topograficzne, pokrycie terenu | CLI |
| **Hydrolog** | HSG dla metody SCS-CN | CLI + Python API |

Docelowo (v1.0.0, sekcja 8) dochodzą:

| Persona | Potrzeby | Użycie |
|---------|----------|--------|
| **Użytkownik QGIS** | Dane GUGiK dla obszaru z mapy albo warstwy, gotowe do analizy | Wtyczka QGIS |
| **Zespół projektowy / firma** | Wspólny magazyn danych, ponowne użycie w kolejnych projektach, zapis wersji danych użytych w projekcie | GUI webowe + CLI |

---

## 2. Goals & Metrics

### 2.1 Technical Goals

| Cel | Target | Status |
|-----|--------|--------|
| Test coverage (core) | >= 80% | Brama CI: `fail_under` w `pyproject.toml`; pomiar: `pytest -m "not live" --cov=kartograf` |
| Testy offline | Każdy test bez sieci (`conftest.py` blokuje gniazda spoza loopbacku) | Spełniony; testy sieciowe tylko z markerem `live` |
| Reliability | >= 95% success rate | Osiągnięty |
| Performance | Download < 60s | Osiągnięty |
| Code quality | ruff (check + format), mypy bez nowego długu | Osiągnięty |

### 2.2 Integration Goals

| Cel | Status |
|-----|--------|
| Integracja z Hydrograf | Gotowy |
| Integracja z Hydrolog | Gotowy |
| Public API exports | Kompletny (`kartograf/__init__.py` `__all__`, sekcja 5) |
| Wspólny klucz grupowania plików PL/CZ (`extra.parent_request`) | Gotowy (scalanie PL+CZ po stronie konsumenta) |

---

## 3. Core Features

### 3.1 Feature: NMT (Numeryczny Model Terenu)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Pobieranie danych wysokościowych NMT z GUGiK w rozdzielczościach 1m i 5m
(5m tylko EVRF2007), w układach wysokościowych EVRF2007 (domyślny) i KRON86.

#### Requirements
- Godło PL-1992 (`SheetParser`, skale 1:1M–1:10k) i PL-2000 (`Parser2000`,
  strefy EPSG:2176–2179); godło grubsze niż 1:10000 rozwijane do arkuszy
  1:10000 bez dodatkowych flag; `--scale` zmienia skalę docelową — potrzebne,
  gdy GUGiK publikuje arkusze w innej skali (PL-2000, zwykle 1:2000;
  USAGE 1.6).
- `--bbox` / `--geometry` (SHP/GPKG) bez `--target-crs` rozwija obszar na
  listę arkuszy OpenData (`--system {1992,2000}`); stykające się krawędzie
  nie są przecięciem.
- Wybór pliku arkusza ze skorowidza GUGiK (ADR-028): warstwy wyłącznie
  z GetCapabilities, twardy filtr (całe godło, układ, rozdzielczość),
  najnowsza `aktualnosc`; brak zgodnego rekordu = `NoCoverageError`
  z podpowiedzią (np. `--scale 1:2000` dla PL-2000), bez cichego fallbacku.
  Rekordy i brak pokrycia są cache'owane w `MetadataCache` (TTL 7 dni,
  `--force` omija odczyt).
- Lista arkuszy toleruje brak pokrycia (R5): arkusz bez danych = `Warning:`
  i status `no_coverage`, kod 0 przy co najmniej jednym pliku; twarda
  awaria pobrania = kod 1 z pełną listą porażek.
- Pobieranie równoległe arkuszy (`--workers`, domyślnie 4 w CLI; 1
  w bibliotece — `DownloadManager(max_workers=1)`), pomijanie istniejących.
- Kampanie GUGiK (`--campaigns`, `--min-year`) — sekcja 3.11.

#### Capabilities
```python
# Parser godeł
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)       # "1:10000"
print(parser.get_bbox())  # BBox(min_x=..., max_x=..., ...)

# Hierarchia arkuszy
hierarchy = parser.get_hierarchy_up()
descendants = parser.get_all_descendants("1:10000")

# Reverse lookup: bbox → godła
from kartograf import find_sheets_for_bbox
bbox = BBox(771000, 509000, 772000, 510000, "EPSG:2180")
sheets = find_sheets_for_bbox(bbox, "1:10000")

# Reverse lookup: geometry file → godła
from kartograf import find_sheets_for_geometry
sheets = find_sheets_for_geometry(Path("area.shp"), "1:10000")

# Pobieranie przez godło (ASC) — plik w data/nmt/pl_1992_1m_evrf2007/...
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")
fetch = manager.last_sheet  # SheetFetch: skipped, downloaded, reused, link, unverified

# Pobieranie przez bbox (GeoTIFF, WCS) — tylko NMT 1m i tylko KRON86:
# endpoint WCS dla EVRF2007 został wycofany przez GUGiK (HTTP 404 od 2026-08),
# więc download_bbox pod EVRF2007 kończy się ValidationError. Wysokości
# EVRF2007 bierz z arkuszy: download_sheet() albo CLI `--bbox`, a jako jeden
# GeoTIFF: download_pl_cutout() / CLI `--target-crs` (0.7.0).
kron = DownloadManager(output_dir="./data", vertical_crs="KRON86")
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
path = kron.download_bbox(bbox, "area.tif")

# Rozdzielczość 5m (tylko EVRF2007)
manager_5m = DownloadManager(resolution="5m")
path = manager_5m.download_sheet("N-34-130-D-d-2-4")
```

#### CLI Commands
```bash
kartograf parse N-34-130-D-d-2-4
kartograf parse N-34-130-D --hierarchy
kartograf download N-34-130-D-d-2-4
kartograf download N-34-130-D              # godło grubsze -> arkusze 1:10000 (bez --scale)
kartograf download 7.171.21 --scale 1:2000  # PL-2000: skala arkuszy GUGiK (USAGE 1.6)
kartograf download --bbox 771000,509000,772000,510000
kartograf download --bbox 19.93,50.05,19.95,50.07 --bbox-crs EPSG:4326
kartograf download N-34-130-D --resolution 5m
kartograf download N-34-130-D-d-2-4 --product nmpt
kartograf download N-34-130-D-d-2-4 --product orto
kartograf download N-34-130-D-d-2-4 --product laz
kartograf download --bbox 771000,509000,772000,510000 --product orto
kartograf download --geometry area.shp
kartograf download --geometry area.gpkg --layer catchments
kartograf download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --system 2000 --scale 1:2000
```

---

### 3.2 Feature: NMPT (Numeryczny Model Pokrycia Terenu)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Pobieranie danych NMPT (Digital Surface Model) z GUGiK — teren + obiekty powierzchniowe (drzewa, budynki).
Tylko 1m; układy wysokościowe KRON86 i EVRF2007. Wybór rekordu skorowidza
i kampanie jak dla NMT (sekcje 3.1, 3.11). CLI `--bbox` pobiera arkusze
OpenData; WCS (`download_bbox`) dostępny z biblioteki.

#### Capabilities
```python
from kartograf import GugikNmptProvider

# NMPT provider (tylko 1m, KRON86 lub EVRF2007)
provider = GugikNmptProvider(vertical_crs="EVRF2007")
provider.download("N-34-130-D-d-2-4", Path("./sheet.asc"))

# Przez bbox (WCS)
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
provider.download_bbox(bbox, Path("./area.tif"))
```

#### CLI Commands
```bash
kartograf download N-34-130-D-d-2-4 --product nmpt
kartograf download --bbox 771000,509000,772000,510000 --product nmpt
```

---

### 3.3 Feature: Ortofotomapa (Standard Resolution)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Pobieranie ortofotomapy (zdjęcia lotnicze) z GUGiK w rozdzielczości 25cm.
Domyślnie najnowszy zgodny rekord RGB; `GugikOrtoProvider(color="CIR")`
wybiera podczerwień (osobny segment `orto/pl_<układ>_cir/`). Kampanie jak dla
NMT (sekcja 3.11).

#### Capabilities
```python
from kartograf import GugikOrtoProvider

# Ortofoto provider (brak vertical CRS — 2D RGB; color="CIR" — podczerwień)
provider = GugikOrtoProvider()
provider.download("N-34-130-D-d-2-4", Path("./sheet.tif"))

# Przez bbox (WCS, formaty: GTiff, PNG, JPEG)
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
provider.download_bbox(bbox, Path("./area.tif"), format="GTiff")
```

#### CLI Commands
```bash
kartograf download N-34-130-D-d-2-4 --product orto
kartograf download --bbox 771000,509000,772000,510000 --product orto
```

---

### 3.4 Feature: LAZ (Chmury Punktów LIDAR)

**Priority:** P1 (High)
**Status:** Production

#### Description
Pobieranie chmur punktów LIDAR (dane pomiarowe ALS, pliki `.laz`) z GUGiK. Discovery jest **area-based** przez WFS: jedno godło 1:10000 (lub `--bbox` / `--geometry`) zwraca wiele kafli LAZ (godłowane drobniej niż 1:10000), każdy z własnym URL OpenData. Godło kafla jest nieparsowalne i traktowane jako etykieta.

#### Capabilities
```python
from kartograf import BBox, GugikLazProvider, download_laz_area

bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")

# Wybór i pobranie kafli z sidecarami (ADR-029) — jedno wywołanie
result = download_laz_area(bbox, output_dir="./data", min_density=12)
result.downloaded, result.skipped   # pliki .laz w data/laz/pl_<układ>_<vcrs>/
result.superseded                   # SupersededLazTile — starsze kafle pokryte nowszymi
result.failed                       # LazTileFailure — porażki pojedynczych kafli

# Sam wybór kafli (bez pobierania)
provider = GugikLazProvider(vertical_crs="EVRF2007")
selection = provider.select_tiles(bbox, year=2024)  # LazTileSelection(tiles, superseded)
```

#### CLI Commands
```bash
kartograf download N-34-130-D-d-2-4 --product laz
kartograf download N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12
kartograf download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86
kartograf download --bbox 530000,382000,533000,386000 --product laz --campaigns all
kartograf download --geometry area.shp --product laz
```

#### Notes
- WFS EPSG:2180 przyjmuje bbox i zwraca envelope w kolejności osi (N,E);
  discovery odrzuca zestaw kafli, w którym żaden nie przecina obszaru.
- Źródło: GUGiK WFS (`DanePomiaroweLidarEVRF2007` / `DanePomiaroweLidarKRON86`)
- Domyślnie najnowszy kafel per obszar (ADR-029): kafle wybierane zachłannie
  od najnowszego `akt_rok`; starszy kafel pomijany, gdy jego część wspólną
  z obszarem pokrywają już wybrane (ramy w EPSG:2180, tolerancja
  `COVERAGE_TOLERANCE_M`); pominięte kafle = `Info:` na stderr.
- `--year` — tylko ten rocznik (sprawdzany wobec GetCapabilities);
  `--min-year` — dolna granica `akt_rok`; `--campaigns all` — wszystkie kafle,
  których rama przecina obszar, bez deduplikacji pokryciowej (sekcja 3.11).
  `--year` i `--min-year` wykluczają się.
- Porażka choć jednego kafla = `Error:` z pełną listą i kod 1 (pobrane kafle
  zostają); sidecar kafla, w trybie `--bbox`/`--geometry` z `extra.parent_request`.
- Tylko PL: na obszarze sięgającym CZ wymagane jawne `--country pl`.
- Pobieranie równoległe (`--workers`), pomijanie istniejących plików

---

### 3.5 Feature: BDOT10k (Land Cover - GUGiK)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie danych pokrycia terenu z polskiej bazy BDOT10k (TERYT powiatu,
godło lub bbox). Format GPKG (domyślny — warstwy scalane w jeden plik `.gpkg`,
składany w lokalnym katalogu tymczasowym i przenoszony do `--output`, więc
działa także na udziałach sieciowych) albo SHP (archiwum `.zip`).

#### Capabilities
```python
from pathlib import Path

from kartograf import LandCoverManager, Bdot10kProvider

# katalog wyjściowy ustawia KONSTRUKTOR; download() przyjmuje output_path=
lc = LandCoverManager(output_dir="./data")
lc.set_provider("bdot10k")

# Pobieranie przez TERYT (powiat) — nazwa pliku generowana automatycznie
lc.download(teryt="1465")

# Pobieranie przez godło z jawną ścieżką pliku
lc.download(godlo="N-34-130-D", output_path=Path("./data/bdot10k_N-34-130-D.gpkg"))
```

#### Warstwy (15 warstw — pobierany caly plik)

**Pokrycie terenu (PT* — 12 warstw):**
| Warstwa | Opis |
|---------|------|
| PTGN | Grunty nieużytkowe |
| PTKM | Tereny komunikacyjne |
| PTLZ | Tereny leśne |
| PTNZ | Tereny niezabudowane |
| PTPL | Place |
| PTRK | Roślinność krzewiasta |
| PTSO | Składowiska |
| PTTR | Tereny rolne |
| PTUT | Uprawy trwałe |
| PTWP | Wody powierzchniowe |
| PTWZ | Tereny zabagnione |
| PTZB | Tereny zabudowane |

**Hydrografia (SW* — 3 warstwy):**
| Warstwa | Opis |
|---------|------|
| SWRS | Rzeki i strumienie |
| SWKN | Kanały |
| SWRM | Rowy melioracyjne |

#### CLI Commands
```bash
kartograf landcover download --source bdot10k --teryt 1465
kartograf landcover download --source bdot10k --godlo N-34-130-D
kartograf landcover list-layers --source bdot10k
```

---

### 3.6 Feature: CORINE Land Cover (Copernicus)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie europejskiej klasyfikacji pokrycia terenu CORINE (44 klasy).

#### Capabilities
```python
from pathlib import Path

from kartograf import LandCoverManager, CorineProvider

lc = LandCoverManager(output_dir="./data")
lc.set_provider("corine")

# Pobieranie przez godło (rozszerzenie wymusza provider: .tif, .png dla WMS)
lc.download(
    godlo="N-34-130-D",
    year=2018,
    output_path=Path("./data/corine_2018_N-34-130-D.tif"),
)
```

#### Dostępne lata
- 1990, 2000, 2006, 2012, 2018

#### Źródła danych (priorytet)
1. **CLMS API** - GeoTIFF z kodami klas (wymaga OAuth2)
2. **EEA Discomap WMS** - podgląd PNG (fallback)
3. **DLR WMS** - fallback dla 1990

#### Auth Proxy (bezpieczeństwo)
```
CorineProvider → localhost HTTP → AuthProxy subprocess → CLMS API
                                  (credentials: CLMS_CREDENTIALS,
                                   fallback tylko macOS: Keychain "clms-token")
```
Credentials czyta wyłącznie podproces Auth Proxy (`python -m
kartograf.auth.proxy`): zmienna `CLMS_CREDENTIALS` (JSON: `client_id`,
`private_key`, `token_uri`) działa na każdym systemie, Keychain (service
`clms-token`) jest fallbackiem tylko na macOS. Główny proces nie widzi kluczy
ani tokenu. Bez credentials — podgląd PNG przez WMS (sidecar
`extra.fallback = "wms_png"`). Tryb bezpośredni z biblioteki:
`CorineProvider(clms_credentials={...})`.

#### CLI Commands
```bash
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D
kartograf landcover list-layers --source corine
```

---

### 3.7 Feature: SoilGrids (Dane Glebowe)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie globalnych danych glebowych z ISRIC SoilGrids (rozdzielczość 250m).

#### Capabilities
```python
from pathlib import Path

from kartograf import LandCoverManager, SoilGridsProvider

lc = LandCoverManager(output_dir="./data")
lc.set_provider("soilgrids")

# Pobieranie węgla organicznego (selekcja: godło albo bbox — TERYT
# nie jest obsługiwany przez SoilGrids i kończy się NotImplementedError)
lc.download(
    godlo="N-34-130-D",
    property="soc",
    depth="0-5cm",
    stat="mean",
    output_path=Path("./data/soilgrids_soc_0-5cm.tif"),
)

# Pobieranie zawartości gliny
lc.download(
    godlo="N-34-130-D",
    property="clay",
    depth="15-30cm"
)
```

#### Dostępne parametry (11)
| Parametr | Opis | Jednostka |
|----------|------|-----------|
| bdod | Gęstość objętościowa | kg/dm³ |
| cec | Pojemność wymiany kationowej | cmol/kg |
| cfvo | Fragmenty gruboziarniste | % |
| clay | Zawartość gliny | % |
| nitrogen | Azot całkowity | g/kg |
| ocd | Gęstość węgla organicznego | kg/m³ |
| ocs | Zasób węgla organicznego | t/ha |
| phh2o | pH w H2O | - |
| sand | Zawartość piasku | % |
| silt | Zawartość pyłu | % |
| soc | Węgiel organiczny | g/kg |

#### Głębokości (6)
0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm

#### Statystyki (5)
mean, Q0.05, Q0.5, Q0.95, uncertainty

#### CLI Commands
```bash
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm
kartograf landcover list-layers --source soilgrids
```

---

### 3.8 Feature: HSG (Hydrologic Soil Groups)

**Priority:** P1
**Status:** Production

#### Description
Kalkulacja grup hydrologicznych gleb (HSG) dla metody SCS-CN na podstawie danych tekstury z SoilGrids.

#### Capabilities
```python
from kartograf import HSGCalculator
from pathlib import Path

calc = HSGCalculator()

# Oblicz HSG dla godła
calc.calculate_hsg_by_godlo("N-34-130-D", Path("./hsg.tif"))

# Statystyki HSG
stats = calc.get_hsg_statistics(Path("./hsg.tif"))
for group, data in stats.items():
    print(f"Grupa {group}: {data['percent']:.1f}%")
```

#### Grupy hydrologiczne
| Grupa | Infiltracja | Tekstury | Potencjał odpływu |
|-------|-------------|----------|-------------------|
| A | Wysoka | piasek, piasek gliniasty | Niski |
| B | Umiarkowana | glina piaszczysta, glina | Umiarkowany |
| C | Wolna | glina ilasta | Wysoki |
| D | Bardzo wolna | ił | Bardzo wysoki |

#### Format wyjściowy
Raster GeoTIFF z wartościami:
- 1 = Grupa A
- 2 = Grupa B
- 3 = Grupa C
- 4 = Grupa D
- 0 = NoData

Wynik dostaje sidecar `.meta.json` (`extra.derived = "hsg"`, warstwy
źródłowe, głębokość, statystyka, kody klas).

#### CLI Commands
```bash
kartograf soilgrids hsg --godlo N-34-130-D
kartograf soilgrids hsg --godlo N-34-130-D --stats
kartograf soilgrids hsg --godlo N-34-130-D --depth 15-30cm --output /tmp/hsg.tif
kartograf soilgrids hsg --godlo N-34-130-D --keep-intermediate
kartograf soilgrids hsg --bbox 450000,550000,460000,560000
kartograf soilgrids hsg --geometry area.gpkg --layer catchments
```

---

### 3.9 Feature: NMT Czechy (CUZK DMR 5G/4G, etap 1)

**Priority:** P1 (High)
**Status:** Development (0.7.0)

#### Description
Pobieranie czeskiego modelu terenu z CUZK: DMR 5G (2 m, godło TM33 — obliczalna
siatka kafli 2x2 km w EPSG:3045) i DMR 4G (5 m, godło SM5 z indeksu arkuszy
`KladyMapovychListu`, EPSG:5514), a także wycinek bbox/geometrii przez
`exportImage` (ArcGIS ImageServer). Etap 1 obejmuje wyłącznie `nmt`;
DMP, ortofoto, LAZ i ZABAGED dla CZ to etapy 2–3 (`docs/SCOPE.md` 3.1).

#### Requirements
- `--country {pl,cz,auto}` (domyślnie `auto`): kraj z formatu godła albo
  z prostokątnych obwiedni krajów (ADR-023); bbox/geometria przygraniczna pod
  `auto` daje osobne pliki PL i CZ ze wspólnym `extra.parent_request` (bez
  scalania PL+CZ — R6, etap 2). Kod 0 = sukces co najmniej jednego kraju;
  przy porażce drugiego `Warning:`.
- Opcje bez odpowiednika czeskiego (`--product nmpt|orto`, `--system`,
  `KRON86`, `1m`) rozstrzygają obszar sporny do PL z `Info:`.
- Żądania do CUZK wyłącznie w natywnym EPSG:5514; reprojekcja pozioma
  lokalnie (`--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}`, tylko
  `--bbox`/`--geometry`) przypiętą operacją — krok S-JTSK → ETRS89 przez
  EPSG:1622/1623 (ADR-024). `--target-crs` z godłem = błąd.
- Układ wysokościowy natywny Bpv; opcjonalnie `--vertical-crs EVRF2007`
  (EPSG:5621, przypięta operacja). KRON86 nieosiągalny dla CZ.
- `exportImage` kafelkowany po stronie klienta (budżet 4 Mpx na żądanie),
  piksel dokładnie 2 m / 5 m.
- Indeks arkuszy SM5 cache'owany w `MetadataCache` (`sheet_cache`, TTL 30 dni;
  `--force` odpytuje na nowo).
- CZ nie ma kampanii: `--campaigns all`/`--min-year` bez części PL = `Error:`
  przed siecią (sekcja 3.11).

#### Capabilities
```python
from pathlib import Path

from kartograf import BBox, create_dmr_provider

provider = create_dmr_provider(resolution="2m")            # DMR 5G, Bpv
provider.download("302_5550", Path("./302_5550.tif"))      # kafel TM33

provider_evrf = create_dmr_provider(resolution="5m", vertical_crs="EVRF2007")
bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
provider_evrf.download_bbox(bbox, Path("./area.tif"))      # wycinek exportImage
```

#### CLI Commands
```bash
kartograf download 302_5550 --country cz                       # DMR 5G (TM33), 2m, Bpv
kartograf download CTES96                                      # DMR 4G (SM5, tylko 5m), kraj z godła
kartograf download 302_5550 --country cz --vertical-crs EVRF2007
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto
kartograf download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180
kartograf download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --resolution 5m
```

---

### 3.10 Feature: Wycinek NMT PL (`--target-crs`, ADR-027)

**Priority:** P1 (High)
**Status:** Development (0.7.0)

#### Description
Jeden scalony GeoTIFF NMT dla obszaru PL (`--bbox`/`--geometry` +
`--target-crs`): mozaika arkuszy PL-1992 przycięta do obszaru, opcjonalnie
reprojektowana lokalnie przypiętą operacją. Zapis
w `nmt/pl_1992_<res>_<vcrs>/bbox/`. Pogranicze: jedną komendą dwa wycinki
(PL i CZ) w tym samym układzie, ze wspólnym `extra.parent_request`.

#### Requirements
- Tylko `--product nmt` i system 1992; `EPSG:2180` = crop 1:1 na siatce
  arkuszy (arkusze o innej fazie = `GridMismatchError`, kod 1 z podpowiedzią);
  inny cel — reprojekcja każdego arkusza osobno (W1, `extra.off_grid_sheets`).
- Arkusz bez danych GUGiK = nodata, `Warning:` i `extra.missing_sheets` (R5);
  inna awaria pobrania = kod 1. Wynik w całości nodata = `Warning:`
  i `extra.all_nodata`.
- Wycinek zawsze czyta najnowsze kampanie (`newest`); `--campaigns all` lub
  `--min-year` z `--target-crs` = `Error:` przed siecią.
- Istniejący wycinek jest pomijany; skip odtwarza ostrzeżenia z sidecara.
  `--force` przebudowuje wycinek i pobiera ponownie arkusze; nieudana
  przebudowa zostawia poprzedni plik.
- `--geometry` obejmuje całą obwiednię geometrii (bez maskowania).

#### Capabilities
```python
from kartograf import BBox, MetadataCache, download_pl_cutout

bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
result = download_pl_cutout(bbox, "EPSG:5514", output_dir="./data", cache=MetadataCache())
result.path, result.skipped
result.missing_sheets, result.off_grid_sheets, result.partial_sheets
result.all_nodata, result.unverified
# kroki: prepare_pl_cutout -> select_pl_cutout_sheets -> run_pl_cutout
```

#### CLI Commands
```bash
kartograf download --bbox 530000,382000,533000,386000 --country pl --target-crs EPSG:5514
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --target-crs EPSG:2180 --vertical-crs EVRF2007
```

---

### 3.11 Feature: Kampanie GUGiK (ADR-030)

**Priority:** P1 (High)
**Status:** Development (0.7.0)

#### Description
Arkusz NMT/NMPT/orto PL bywa publikowany przez GUGiK w wielu kampaniach
pomiarowych. Kartograf przechowuje każdą pobraną kampanię osobno i jawnie
wskazuje, która jest "bieżąca".

#### Requirements
- `--campaigns newest` (domyślnie): najnowsza kampania arkusza wg reguły
  ADR-028, rozwiązywana przy każdym uruchomieniu (sieć, gdy wygasł cache
  7 dni); pobierane są tylko brakujące kampanie.
- `--campaigns all`: każda kampania arkusza po twardym filtrze ADR-028, bez
  limitu liczby.
- `--min-year RRRR` (1900..2100): odcina kampanie z rokiem `aktualnosc`
  sprzed granicy; `newest` z najnowszą kampanią starszą od granicy =
  `NoCoverageError`.
- Pliki kampanii w `<segment>/kampanie/<data>_<id>/<hierarchia godła>/`
  z OBOWIĄZKOWYM sidecarem (`extra.campaign`); format pliku z pola `format`
  rekordu i weryfikacja treści po pobraniu (nagłówek AAIGrid / sygnatura TIFF).
- Ścieżka standardowa `<segment>/<hierarchia>/<godło>.<ext>` to dowiązanie
  TWARDE do najnowszej lokalnej kampanii, a gdy hardlink niedostępny — kopia
  z `Warning:`; bez symlinków (errata 4 ADR-030). Dowiązanie przestawiane
  tylko na kampanię nowszą, nigdy wstecz; cel zapisany w sidecarze
  (`extra.link`, `extra.link_target`).
- Skorowidz GUGiK niedostępny (błąd transportu) przy `newest` bez
  `--min-year`/`--force` i istniejącej lokalnej kampanii: arkusz brany
  z lokalnej kampanii z `Warning:` (errata 5 ADR-030); biblioteka:
  `SheetFetch.unverified` / `DownloadResult.unverified` /
  `PlCutoutResult.unverified`.
- Tylko PL: zadanie bez części PL z `--campaigns all`/`--min-year` =
  `Error:` przed siecią; obszar PL+CZ pod `auto` = `Info:`, CZ pobierane
  w bieżącej wersji.
- LAZ: `--campaigns all` = kafle bez deduplikacji pokryciowej, `--min-year`
  = granica `akt_rok`; LAZ bez dowiązań.

#### Capabilities
```python
from kartograf import DownloadManager

manager = DownloadManager(output_dir="./data", campaigns="all", min_year=2022)
manager.download_sheet("N-34-139-C-a-3-1")
manager.last_sheet.downloaded      # pliki kampanii pobrane teraz
manager.last_sheet.link            # "hardlink" | "copy"
# CampaignRef — opis kampanii (id, data, dt_pzgik, url, ...)
```

#### CLI Commands
```bash
kartograf download N-34-130-D-d-2-4 --campaigns all
kartograf download N-34-130-D-d-2-4 --min-year 2024
kartograf download --bbox 530000,382000,533000,386000 --campaigns all --min-year 2022
```

---

### 3.12 Feature: Układ `data/` i metadane pobrań (ADR-026, sidecary)

**Priority:** P0 (Critical)
**Status:** Development (0.7.0)

#### Requirements
- Kanoniczny układ `data/<produkt>/<kraj>_<układ>[_<wariant>][_<vcrs>]/...`
  (np. `nmt/pl_1992_1m_evrf2007/`, `orto/pl_1992_cir/`,
  `laz/pl_2000_evrf2007/`, `nmt/cz_dmr5g_bpv/`); szablony segmentów
  w deskryptorach źródeł (`kartograf/sources/registry.py`). Układ
  `pl_1992`/`pl_2000` z formatu godła każdego pliku (kafle LAZ — z układu
  kafla). Wycinki w `<segment>/bbox/`. Tabela segmentów i migracja:
  `docs/ARCHITECTURE.md` sekcja 3. `landcover/` bez zmian.
- Każde udane pobranie przez CLI albo warstwę zarządzającą biblioteki
  (`DownloadManager`, `LandCoverManager`, `download_pl_cutout`,
  `download_laz_area`; DMR CZ — tor CLI) oraz wynik `HSGCalculator` dostaje
  sidecar `<plik>.meta.json` (schemat
  `kartograf-meta/1`): zbiór, kraj, produkt, układy poziomy i pionowy,
  rozdzielczość, nodata, żądanie, licencja, wersja Kartografu, `extra`
  (pochodzenie rekordu `extra.source`, `extra.parent_request` itp.).
  Sidecary są best-effort, z wyjątkiem plików kampanii (sekcja 3.11).
- Sidecar zapisuje faktyczny układ PLIKU; arkusz PL-2000 opublikowany przez
  GUGiK w innym układzie niż wskazuje godło daje `Warning:` (E17).

---

## 4. Architecture

### 4.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User Interface                                │
├──────────────────────────────┬──────────────────────────────────────────┤
│  CLI (--country pl|cz|auto)  │              Python API                  │
└──────────────┬───────────────┴───────────────────┬──────────────────────┘
               │                                   │
               v                                   v
┌─────────────────────────────────────────────────────────────────────────┐
│                       Managers / API pobierania                         │
├────────────────────────────────────┬────────────────────────────────────┤
│ DownloadManager (NMT/NMPT/Orto,    │ LandCoverManager                   │
│   kampanie ADR-030)                │   (BDOT10k, CORINE, SoilGrids)     │
│ download_pl_cutout (ADR-027)       │ HSGCalculator                      │
│ download_laz_area (ADR-029)        │                                    │
└──────────────┬─────────────────────┴───────────────────┬────────────────┘
               │                                         │
               v                                         v
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                   Providers                                      │
├────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────┬─────────┤
│ Gugik  │ GugikNmpt│ GugikOrto│ GugikLaz │ CuzkDmr  │ Bdot10k  │ Corine │SoilGrids│
│ (NMT)  │ (NMPT)   │ (Orto)   │ (LAZ)    │ (DMR CZ) │          │        │         │
└───┬────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴───┬────┴────┬────┘
    v         v          v          v          v          v         v         v
┌───────────────────────┐ ┌─────────┐ ┌────────────┐ ┌────────┐ ┌───────────┐ ┌─────┐
│ GUGiK WCS / OpenData  │ │GUGiK WFS│ │ CUZK       │ │ GUGiK  │ │ CLMS API  │ │ISRIC│
│ + skorowidz (WMS GFI) │ │+OpenData│ │ ArcGIS REST│ │OpenData│ │(AuthProxy)│ │ WCS │
│ (NMT, NMPT, Ortofoto) │ │ (LAZ)   │ │ + openzu   │ │(BDOT10k│ │ + WMS PNG │ │     │
└───────────────────────┘ └─────────┘ └────────────┘ └────────┘ └───────────┘ └─────┘

Wspólne warstwy: sources/ (deskryptory, sidecary), transport/ (HTTP, mozaika),
transform/ (przypięte transformacje CRS), cache/ (MetadataCache, SQLite).
```

### 4.2 Hydrology Module

```
┌─────────────────────────────────────────────────────────────┐
│                    HSGCalculator                            │
├─────────────────────────────────────────────────────────────┤
│  calculate_hsg_by_godlo()                                   │
│  calculate_hsg_by_bbox()                                    │
│  get_hsg_statistics()                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           v
┌─────────────────────────────────────────────────────────────┐
│              SoilGridsProvider                              │
│  (pobiera clay, sand, silt)                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           v
┌─────────────────────────────────────────────────────────────┐
│  USDA Texture Triangle  →  HSG Mapping                      │
│  (12 klas tekstury)        (4 grupy hydrologiczne)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Public API

Źródłem prawdy jest `kartograf/__init__.py` (`__all__`); lista poniżej jest
z nim zgodna i musi być aktualizowana razem z nim.

```python
from kartograf import (
    # Cache
    MetadataCache,

    # Core
    SheetParser,
    Parser2000,
    ParserTM33,
    BBox,
    find_sheets_for_bbox,
    find_sheets_2000_for_bbox,
    find_sheets_for_geometry,

    # Download (NMT/NMPT/Orto, kampanie ADR-030)
    DownloadManager,
    DownloadProgress,
    DownloadResult,
    SheetFetch,
    CampaignRef,
    FileStorage,

    # Download — wycinek PL (ADR-027)
    PlCutout,
    PlCutoutResult,
    PlCutoutSheets,
    download_pl_cutout,
    prepare_pl_cutout,
    run_pl_cutout,
    select_pl_cutout_sheets,

    # Download — kafle LAZ (ADR-029)
    LazDownloadResult,
    LazTileFailure,
    download_laz_area,
    run_laz_download,

    # Land Cover
    LandCoverManager,

    # Providers
    BaseProvider,
    GugikProvider,
    GugikNmptProvider,
    GugikOrtoProvider,
    GugikLazProvider,
    LazTile,
    LazTileSelection,
    SupersededLazTile,
    LandCoverProvider,
    Bdot10kProvider,
    CorineProvider,
    SoilGridsProvider,
    CuzkDmrProvider,        # CZ (CUZK, etap 1)
    create_dmr_provider,

    # Hydrology
    HSGCalculator,

    # Exceptions
    KartografError,
    ParseError,
    ValidationError,
    DownloadError,
    NoCoverageError,        # (DownloadError)
    GridMismatchError,      # (ValidationError)

    # Version
    __version__,            # "0.7.0"
)
```

---

## 6. Dependencies

### 6.1 Runtime Dependencies

```
Python >= 3.12
requests >= 2.31.0     # HTTP client
pyproj >= 3.6.0        # CRS transformations
PyJWT[crypto] >= 2.8.0 # OAuth2 JWT (CLMS)
rasterio >= 1.3.0      # GeoTIFF processing
numpy >= 1.24.0        # Array operations
pyshp >= 2.3.0         # Shapefile reading
```

### 6.2 Development Dependencies

```
pytest >= 8.0          # Testing
pytest-cov >= 5.0      # Coverage
ruff >= 0.8            # Linting + Formatting
mypy >= 1.13           # Type checking
```

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Requirement | Target |
|-------------|--------|
| Parse time | < 0.1s |
| NMT download | < 30s |
| Land Cover download | < 60s |
| HSG calculation | < 120s |

### 7.2 Reliability

- Success rate >= 95%
- Retry logic: `MAX_RETRIES = 3` (nie konfigurowalne), backoff 2 s, potem 4 s
  (`transport/http.py::backoff_delay`); ponawiane tylko błędy sieci, HTTP 429
  i 5xx, `Retry-After` wydłuża przerwę (max `MAX_RETRY_AFTER` = 60 s); inne 4xx
  kończą od razu (`DownloadError.status_code`)
- Timeouty per źródło jako stałe providerów (np. `DEFAULT_TIMEOUT`); zestawienie
  w `docs/SCOPE.md` 3.2
- Atomic writes (tmp → `os.replace`); nieudana przebudowa wycinka zostawia
  poprzedni plik
- Skip-existing: pobrane pliki nie są pobierane ponownie (`--force` wymusza);
  pod `--campaigns newest` sprawdzana jest dostępność nowszej kampanii
- Integralność treści: plik kampanii GUGiK weryfikowany formatem treści
  (nagłówek AAIGrid / sygnatura TIFF); brak sum kontrolnych

### 7.3 Security

- Auth Proxy isolates CLMS credentials (podproces; główny proces nie widzi
  kluczy ani tokenu)
- Credentials: zmienna `CLMS_CREDENTIALS` (JSON, każdy system); fallback
  tylko na macOS: Keychain (service `clms-token`)
- No hardcoded secrets in code

---

## 8. Future Enhancements

### Version 0.6+
- [x] Parallel downloads (multi-threading) (implemented in v0.6.0)
- [x] Metadata cache (SQLite) (implemented in v0.6.0)
- [x] Automatic mosaic creation — NMT PL: wycinek `--target-crs` /
      `download_pl_cutout` (0.7.0); pozostałe produkty — etap 2
- [x] Czechy, etap 1: DMR 5G/4G z CUZK, `--country` (0.7.0)
- [x] Kampanie GUGiK `--campaigns`/`--min-year` (0.7.0)

### Etap 2/3 (CZ) i dalej — szczegóły w `docs/SCOPE.md` 3.1
- [ ] CZ: DMP (odpowiednik NMPT), ortofoto, LAZ; ZABAGED (etap 3)
- [ ] Wielokąt granicy kraju zamiast prostokątnej obwiedni (`--country auto`)
- [ ] Scalanie wycinków PL+CZ w jedną powierzchnię przygraniczną (R6)
- [ ] Wycinek PL `--target-crs` z arkuszy PL-2000
- [ ] Składanie kampanii w jedną powierzchnię

### Version 1.0.0 — roadmapa (kolejność i zasady: `docs/SCOPE.md` 3.3)

Każdy punkt to osobny podprojekt z własnym specem i ADR; wymagania niżej
opisują wynik, nie rozwiązanie.

- [ ] **Magazyn wersjonowany:** żaden produkt nie nadpisuje po cichu
      wcześniej pobranych danych; każda wersja pliku pozostaje dostępna
      pod niezmienną ścieżką, a ścieżka standardowa wskazuje najnowszą
      lokalną wersję (dziś tylko kampanie NMT/NMPT/orto PL, ADR-030).
- [ ] **Manifest projektu:** projekt zapisuje, których konkretnie plików
      i wersji użył (z sumami kontrolnymi); z CLI można pobrać dane do
      projektu, sprawdzić ich integralność i dowiedzieć się, czy u źródła
      są nowsze dane. Dane już obecne w magazynie nie są pobierane ponownie.
- [ ] **Komplet publicznych danych GUGiK:** wszystkie produkty dostępne
      publicznie i bez logowania, o ile pozwalają na to usługi
      (inwentaryzacja w specu podprojektu).
- [ ] **Gotowe dane:** dla każdego produktu wynik dopasowany do obszaru
      zadania (wycinek, scalenie, reprojekcja tam, gdzie mają sens)
      z sidecarem pochodzenia.
- [ ] **Wtyczka QGIS:** pobieranie z poziomu QGIS przez publiczne API
      biblioteki, bez własnej logiki pobierania.
- [ ] **GUI webowe:** lokalny manager danych — przeglądarka magazynu
      i manifestów projektów z informacją o nowszych danych; publikacja
      po przetestowaniu lokalnym.
- [ ] **Wyłącznie angielskie identyfikatory** w API, CLI i sidecarze (ADR-031).

### Później (poza v1.0.0)
- [ ] PostGIS integration
- [ ] REST API server

---

## 9. Cross-Project Integration

### 9.1 Dependency Map

```
HYDROGRAF (główna aplikacja)
    ├── IMGWTools (dane IMGW)
    ├── Kartograf (dane GIS) ← TEN PROJEKT
    └── Hydrolog (obliczenia hydrologiczne)
            ├── IMGWTools (wymagany)
            └── Kartograf (opcjonalny)
```

### 9.2 Integration Points

| Projekt | Używa z Kartograf |
|---------|-------------------|
| Hydrograf | DownloadManager, LandCoverManager |
| Hydrolog | HSGCalculator, SoilGridsProvider |

---

**Wersja dokumentu:** 4.1
**Data ostatniej aktualizacji:** 2026-10-08
**Status:** Wydanie v0.7.0 (2026-10-08)
