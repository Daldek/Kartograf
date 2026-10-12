# PRD.md - Product Requirements Document
**Kartograf - Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 4.3
**Data:** 2026-10-11
**Product Owner:** Piotr
**Status:** Wydanie v0.7.2 (2026-10-11)

> Dokument opisuje wymagania produktowe wersji 0.7.2 w postaci
> zrealizowanej w kodzie wydania v0.7.2 (w tym rok danych ADR-032,
> `full_sheet/` ADR-033 i wycinki z WCS ADR-035). Szczegóły
> zachowania (komunikaty, kody wyjścia, przypadki brzegowe) —
> `docs/SCOPE.md` i `docs/ARCHITECTURE.md`; uzasadnienia decyzji —
> `docs/DECISIONS.md` (ADR-022..ADR-035); historia zmian — `docs/CHANGELOG.md`. Pełna lista
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
4. **Automatic Processing** - scalanie warstw BDOT10k, kalkulacja HSG, wycinek NMT/NMPT z WCS GUGiK z maska ladu PRG i lokalna reprojekcja (`--target-crs`)
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
(5m tylko EVRF2007), w układach wysokościowych EVRF2007 i KRON86 (wybór
wymagany od 0.8.0, bez wartości domyślnej).

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
- Kampanie GUGiK (`--all-campaigns`, `--min-year`) — sekcja 3.11.

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
sheets = find_sheets_for_bbox(bbox, "1:10000", "1992")

# Reverse lookup: geometry file → godła
from kartograf import find_sheets_for_geometry
sheets = find_sheets_for_geometry(Path("area.shp"), "1:10000", system="1992")

# Pobieranie przez godło (ASC) — plik w data/nmt/pl_1992_1m_evrf2007/...
manager = DownloadManager("./data", GugikProvider(vertical_crs="EVRF2007", resolution="1m"))
path = manager.download_sheet("N-34-130-D-d-2-4")
fetch = manager.last_sheet  # SheetFetch: status, version, newer, files, unverified, full_link

# Surowy WCS NMT 1m poza magazynem wersji: KRON86 z TIFF, EVRF2007 z ASC
# multipart; obie sciezki daja GeoTIFF float32 z wysokosciami (NMPT tez).
# Wycinek w magazynie (maska PRG, wersje): download_pl_cutout (sekcja 3.10).
kron = GugikProvider(vertical_crs="KRON86", resolution="1m")
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
path = kron.download_bbox(bbox, Path("area.tif"))

# Rozdzielczość 5m (tylko EVRF2007)
manager_5m = DownloadManager("./data", GugikProvider(vertical_crs="EVRF2007", resolution="5m"))
path = manager_5m.download_sheet("N-34-130-D-d-2-4")
```

#### CLI Commands
```bash
kartograf parse N-34-130-D-d-2-4
kartograf parse N-34-130-D --hierarchy
kartograf download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-130-D --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # godło grubsze -> arkusze 1:10000 (bez --scale)
kartograf download --sheet 7.171.21 --scale 1:2000 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # PL-2000: skala arkuszy GUGiK (USAGE 1.6)
kartograf download --bbox 771000,509000,772000,510000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --bbox 19.93,50.05,19.95,50.07 --bbox-crs EPSG:4326 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --sheet N-34-130-D --resolution 5m --product nmt --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --product nmpt --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --product orto -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --product laz --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 771000,509000,772000,510000 --product orto --country pl --system 1992 -o ./data
kartograf download --geometry area.shp --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --geometry area.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 -o ./data
```

---

### 3.2 Feature: NMPT (Numeryczny Model Pokrycia Terenu)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Pobieranie danych NMPT (Digital Surface Model) z GUGiK — teren + obiekty powierzchniowe (drzewa, budynki).
Tylko 1m; układy wysokościowe KRON86 i EVRF2007. Wybór rekordu skorowidza
i kampanie jak dla NMT (sekcje 3.1, 3.11). CLI `--bbox` bez
`--target-crs` pobiera arkusze OpenData; z `--target-crs` wycinek WCS
(sekcja 3.10). `GugikNmptProvider.download_bbox` zwraca wysokosci
float32 z WCS, nie kolorowy TIFF.

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
kartograf download --sheet N-34-130-D-d-2-4 --product nmpt --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 771000,509000,772000,510000 --product nmpt --country pl --vertical-crs EVRF2007 --system 1992 -o ./data
```

---

### 3.3 Feature: Ortofotomapa (Standard Resolution)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Pobieranie ortofotomapy (zdjęcia lotnicze) z GUGiK w rozdzielczości 25cm.
Wariant koloru wymagany w API (`GugikOrtoProvider(color="RGB")`; CLI pobiera RGB); `GugikOrtoProvider(color="CIR")`
wybiera podczerwień (osobny segment `orto/pl_<układ>_cir/`). Kampanie jak dla
NMT (sekcja 3.11).

#### Capabilities
```python
from kartograf import GugikOrtoProvider

# Ortofoto provider (brak vertical CRS — 2D RGB; color="CIR" — podczerwień)
provider = GugikOrtoProvider(color="RGB")
provider.download("N-34-130-D-d-2-4", Path("./sheet.tif"))

# Przez bbox (WCS, formaty: GTiff, PNG, JPEG)
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
provider.download_bbox(bbox, Path("./area.tif"), format="GTiff")
```

#### CLI Commands
```bash
kartograf download --sheet N-34-130-D-d-2-4 --product orto -o ./data
kartograf download --bbox 771000,509000,772000,510000 --product orto --country pl --system 1992 -o ./data
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
result = download_laz_area(bbox, output_dir="./data", vertical_crs="EVRF2007", min_density=12)
result.files                        # VersionedFile per kafel (status new/local/...), hardlinki w data/laz/pl_<układ>_<vcrs>/
result.superseded                   # SupersededLazTile — starsze kafle pokryte nowszymi
result.failed                       # LazTileFailure — porażki pojedynczych kafli

# Sam wybór kafli (bez pobierania)
provider = GugikLazProvider(vertical_crs="EVRF2007")
selection = provider.select_tiles(bbox, year=2024)  # LazTileSelection(tiles, superseded)
```

#### CLI Commands
```bash
kartograf download --sheet N-34-130-D-d-2-4 --product laz --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12 --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86 --country pl -o ./data
kartograf download --bbox 530000,382000,533000,386000 --product laz --all-campaigns --country pl --vertical-crs EVRF2007 -o ./data
kartograf download --geometry area.shp --product laz --country pl --vertical-crs EVRF2007 -o ./data
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
  `--min-year` — dolna granica `akt_rok`; `--all-campaigns` — wszystkie kafle,
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
lc = LandCoverManager("./data", "bdot10k")

# Pobieranie przez TERYT (powiat) — nazwa pliku generowana automatycznie
lc.download(teryt="1465")

# Pobieranie przez godło z jawną ścieżką pliku
lc.download(sheet="N-34-130-D", output_path=Path("./data/bdot10k_N-34-130-D.gpkg"))
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
kartograf landcover download --source bdot10k --teryt 1465 -o ./data/landcover
kartograf landcover download --source bdot10k --sheet N-34-130-D -o ./data/landcover
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

lc = LandCoverManager("./data", "corine")

# Pobieranie przez godło (rozszerzenie wymusza provider: .tif, .png dla WMS)
lc.download(
    sheet="N-34-130-D",
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
kartograf landcover download --source corine --year 2018 --sheet N-34-130-D -o ./data/landcover
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

lc = LandCoverManager("./data", "soilgrids")

# Pobieranie węgla organicznego (selekcja: godło albo bbox — TERYT
# nie jest obsługiwany przez SoilGrids i kończy się NotImplementedError)
lc.download(
    sheet="N-34-130-D",
    property="soc",
    depth="0-5cm",
    stat="mean",
    output_path=Path("./data/soilgrids_soc_0-5cm.tif"),
)

# Pobieranie zawartości gliny
lc.download(
    sheet="N-34-130-D",
    property="clay",
    depth="15-30cm",
    stat="mean",
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
kartograf landcover download --source soilgrids --sheet N-34-130-D --property soc -o ./data/landcover --depth 0-5cm --stat mean
kartograf landcover download --source soilgrids --sheet N-34-130-D --property clay --depth 15-30cm -o ./data/landcover --stat mean
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
calc.calculate_hsg_by_sheet("N-34-130-D", Path("./hsg.tif"), depth="0-5cm", stat="mean")

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
kartograf soilgrids hsg --sheet N-34-130-D -o ./data/hsg --depth 0-5cm
kartograf soilgrids hsg --sheet N-34-130-D --stats -o ./data/hsg --depth 0-5cm
kartograf soilgrids hsg --sheet N-34-130-D --depth 15-30cm --output /tmp/hsg.tif
kartograf soilgrids hsg --sheet N-34-130-D --keep-intermediate -o ./data/hsg --depth 0-5cm
kartograf soilgrids hsg --bbox 450000,550000,460000,560000 -o ./data/hsg --depth 0-5cm
kartograf soilgrids hsg --geometry area.gpkg --layer catchments -o ./data/hsg --depth 0-5cm
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
- `--country {pl,cz,auto}` (wymagane z `--bbox`/`--geometry` od 0.8.0; z `--sheet` kraj z godła): kraj z formatu godła albo
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
- CZ nie ma kampanii: `--all-campaigns`/`--min-year` bez części PL = `Error:`
  przed siecią (sekcja 3.11).

#### Capabilities
```python
from pathlib import Path

from kartograf import BBox, create_dmr_provider

provider = create_dmr_provider(resolution="2m", vertical_crs="Bpv")  # DMR 5G
provider.download("302_5550", Path("./302_5550.tif"))      # kafel TM33

provider_evrf = create_dmr_provider(resolution="5m", vertical_crs="EVRF2007")
bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
provider_evrf.download_bbox(bbox, Path("./area.tif"))      # wycinek exportImage
```

#### CLI Commands
```bash
kartograf download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv -o ./data # DMR 5G (TM33), 2m, Bpv
kartograf download --sheet CTES96 --product nmt --vertical-crs Bpv -o ./data # DMR 4G (SM5, tylko 5m), kraj z godła
kartograf download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m -o ./data
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv --system 1992 -o ./data
kartograf download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv -o ./data
kartograf download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --resolution 5m --product nmt --vertical-crs Bpv -o ./data
```

---

### 3.10 Feature: Wycinek NMT/NMPT PL (`--target-crs`, ADR-035)

**Priority:** P1 (High)
**Status:** Development (0.7.2)

#### Description
Jeden GeoTIFF NMT albo NMPT 1 m z WCS GUGiK dla `--bbox` lub
obwiedni `--geometry` + `--target-crs`. Maska ladu PRG nadaje
nodata poza Polska; lokalny warp uzywa przypietej operacji.
Wynik: `<segment>/bbox/<coords>.tif` (dowiazanie do wersji w
`versions/bbox/`, ADR-036 D15) z sidecarem;
pod `auto` PL i CZ to dwa pliki ze wspolnym `extra.parent_request`.

#### Requirements
- Tylko 1 m, oba uklady wysokosciowe. WCS NMT KRON86 zwraca
  TIFF float32, EVRF2007 i NMPT — ASC multipart konwertowany
  do float32 GeoTIFF. Zadanie wyrownane na zewnatrz do siatki
  arkusza 1 m (`k + 0,5`), zapytania o parzystych rozmiarach (pomiar
  na zywo 2026-10-11), ASC dzielony na kawalki do 1 Mpx pikseli coverage
  w NMT i 4 Mpx w NMPT (1 Mpx wyniku 1 m).
- Maska PRG `A00 - W02 - W03` przed WCS: piksele poza ladem
  `-9999`, 0,0 wewnatrz maski pozostaje danymi.
  Wynik caly nodata = `Warning:`, kod 0.
- WCS daje kompozycje serwera, nie wybor najnowszego arkusza
  dokladnie 1 m wg ADR-028; na locie 0,5 m 1 m jest decymacja.
  Bez wyboru roku i kampanii: `--all-campaigns`, flagi roku
  i `--full-sheet` z `--target-crs` = `Error:`.
- Kazdy przebieg pobiera (nie pomija istniejacego wycinka);
  wynik z tego samego dnia atomowo zastepuje wczesniejszy
  tylko po sukcesie. `--force`, `--workers`, `--scale` bez wplywu
  na tor WCS. 5 m: arkusze bez `--target-crs`.

#### Capabilities
```python
from kartograf import BBox, download_pl_cutout, prepare_pl_cutout, run_pl_wcs_cutout

bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
result = download_pl_cutout(
    bbox, "EPSG:5514", output_dir="./data", vertical_crs="EVRF2007", product="nmpt"
)
result.path, result.masked_pixels, result.zero_pixels, result.all_nodata
prepared = prepare_pl_cutout(
    bbox, "EPSG:2180", output_dir="./data", vertical_crs="EVRF2007", product="nmt"
)
result_nmt = run_pl_wcs_cutout(prepared)
```

#### CLI Commands
```bash
kartograf download --bbox 530000,382000,533000,386000 --country pl --product nmt --target-crs EPSG:5514 --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --country pl --product nmpt --target-crs EPSG:2180 --vertical-crs EVRF2007 -o ./data
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
- Domyślnie: najnowsza kampania arkusza wg reguły
  ADR-028 w zakresie lat, rozwiązywana przy każdym uruchomieniu (sieć, gdy
  wygasł cache 7 dni); pobierane są tylko brakujące kampanie.
- `--all-campaigns`: każda kampania arkusza (w zakresie lat) po twardym
  filtrze ADR-028, bez limitu liczby.
- Rok danych (ADR-032): `--year RRRR` = `--min-year RRRR --max-year RRRR`,
  granice domknięte 1900..2100; flagi roku wyznaczają tylko dopuszczalne
  lata, `--all-campaigns` liczbę lotów. Najpierw sprawdzenie pełnej listy
  kampanii każdego arkusza: dane tylko z innych lat = `YearRangeError`
  (`Error:` z latami i podpowiedzią) i nic nie jest pobierane.
- Pliki kampanii jako wersje (ADR-036) w
  `<segment>/versions/<hierarchia godła>/<data>_<id>_<sha8>/` z OBOWIĄZKOWYM,
  niezmiennym sidecarem (`extra.campaign`, `extra.version`); format pliku
  z pola `format` rekordu i weryfikacja treści po pobraniu (nagłówek AAIGrid
  / sygnatura TIFF); zapis wyłączny (nic nie jest nadpisywane).
- Ścieżka standardowa `<segment>/<hierarchia>/<godło>.<ext>` to dowiązanie
  TWARDE do najnowszej lokalnej wersji; bez kopii i symlinków (system plików
  bez hardlinków = błąd). Dowiązanie przestawiane tylko na wersję nowszą,
  nigdy wstecz; cel zapisany w sidecarze (`extra.link`, `extra.link_target`).
  Domyślnie nowsza kampania nie jest pobierana automatycznie (`Info:`,
  `--upgrade`); `--check-updates` raportuje bez pobierania.
- Drugie dowiązanie `<segment>/full_sheet/<hierarchia>/<godło>.<ext>`
  (ADR-033) do najnowszego lokalnego lotu oznaczonego w skorowidzu jako
  pełny (`calyArkuszWypelnionyTrescia = TAK`, pełny = w granicach Polski);
  `--full-sheet` / `DownloadManager(full_sheet=True)` dociąga najwyżej
  jeden taki lot na arkusz, gdy najnowszy w zakresie lat nie jest pełny.
- Skorowidz GUGiK niedostępny (błąd transportu) przy domyślnym wyborze bez
  flag roku i `--force` oraz istniejącej lokalnej kampanii: arkusz brany
  z lokalnej kampanii z `Warning:` (errata 5 ADR-030); biblioteka:
  `SheetFetch.unverified` / `DownloadResult.unverified` /
  `PlCutoutResult.unverified`.
- Tylko PL: zadanie bez części PL z `--all-campaigns`, flagą roku albo
  `--full-sheet` = `Error:` przed siecią; obszar PL+CZ pod `auto` =
  `Info:`, CZ pobierane w bieżącej wersji. Wycinek `--target-crs`
  nie przyjmuje `--all-campaigns`, flag roku ani `--full-sheet`.
- LAZ: `--all-campaigns` = kafle bez deduplikacji pokryciowej, flagi roku
  = granice `akt_rok`; LAZ bez dowiązań i bez `--full-sheet`.

#### Capabilities
```python
from kartograf import DownloadManager, GugikProvider

provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
manager = DownloadManager("./data", provider, min_year=2022, full_sheet=True)
manager.download_sheet("N-34-139-C-a-3-1")
manager.last_sheet.downloaded      # pliki kampanii pobrane teraz
manager.last_sheet.link            # "hardlink" | "copy"
manager.last_sheet.full_link       # ścieżka full_sheet/ albo None
manager.last_result.without_full   # arkusze bez pełnego lotu w zakresie
# CampaignRef — opis kampanii (id, data, dt_pzgik, url, ...)
```

#### CLI Commands
```bash
kartograf download --sheet N-34-130-D-d-2-4 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --min-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --all-campaigns --min-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --sheet N-34-139-C-a-3-1 --full-sheet --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
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
│ download_pl_cutout (ADR-035)       │ HSGCalculator                      │
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
│  calculate_hsg_by_sheet()                                   │
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

    # Download — wycinek PL WCS (ADR-035)
    PlCutout,
    PlCutoutResult,
    download_pl_cutout,
    prepare_pl_cutout,
    run_pl_wcs_cutout,

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

    # Version
    __version__,            # "0.8.0-dev"
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
- Skip-existing dotyczy arkuszy i innych pobran; wycinek PL WCS
  nigdy nie pomija istniejacego pliku, pobiera przy kazdym wywolaniu.
  Arkusze przy domyślnym wyborze sprawdzają dostępność nowszej kampanii
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
- [x] Automatic mosaic creation — wycinki NMT/NMPT WCS
      (`download_pl_cutout`, 0.7.2; tor arkuszowy z 0.7.0 usuniety
      w 0.8.0); pozostale produkty — etap 2
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
- [x] **Wyłącznie angielskie identyfikatory** w API, CLI i sidecarze (ADR-031;
      API/CLI w 0.8.0, errata 1).

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

**Wersja dokumentu:** 4.3
**Data ostatniej aktualizacji:** 2026-10-11
**Status:** Wydanie v0.7.2 (2026-10-11)
