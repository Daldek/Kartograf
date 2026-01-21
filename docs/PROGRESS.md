# Plan Implementacji Kartograf

**Repozytorium:** https://github.com/Daldek/Kartograf.git
**Status:** Wersja 0.3.1
**Ostatnia aktualizacja:** 2026-01-21

---

## Szybki Start (dla powracającego dewelopera)

1. Sprawdź **"Aktualny Etap"** poniżej
2. Przeczytaj kryteria ukończenia dla tego etapu
3. Po ukończeniu: oznacz etap jako [x] i przejdź do następnego

---

## Aktualny Etap: 20 - Cross-Project Compatibility - UKOŃCZONY

**Status:** Ukończony
**Cel:** Naprawa kompatybilności z pozostałymi projektami (Hydrograf, Hydrolog, IMGWTools)

**Wykonane prace:**
- Dodano eksport `SoilGridsProvider` do głównego `kartograf/__init__.py`
- Dodano eksport `HSGCalculator` do głównego `kartograf/__init__.py`
- Zaktualizowano `__all__` z nowymi eksportami
- Wszystkie 365 testów przechodzi

**Import z głównego modułu teraz działa:**
```python
from kartograf import SoilGridsProvider, HSGCalculator
```

**Poprzedni etap:** 19 - QA i naprawy krytyczne - UKOŃCZONY

---

## Etapy Implementacji

### Etap 0: Inicjalizacja Git + PROGRESS.md (S - 10 min)
- [x] Ukończony

---

### Etap 1: Setup Projektu (S - 20 min)
- [x] Ukończony

**Pliki do utworzenia:**
- `pyproject.toml` - konfiguracja projektu, entry points
- `requirements.txt` - requests>=2.31.0
- `requirements-dev.txt` - pytest, pytest-cov, black, flake8
- `.gitignore`
- `.flake8`
- `src/kartograf/__init__.py` (pusty)
- `tests/__init__.py` (pusty)

**Kryterium ukończenia:**
- `pip install -e .` działa
- `pytest tests/` uruchamia się
- Struktura katalogów utworzona

---

### Etap 2: Wyjątki (S - 15 min)
- [x] Ukończony

**Pliki:**
- `src/kartograf/exceptions.py`
- `src/kartograf/core/__init__.py`

**Kryterium:** Import `from kartograf.exceptions import KartografError` działa

---

### Etap 3: Parser Godła - Podstawy (M - 45 min)
- [x] Ukończony

**Pliki:**
- `src/kartograf/core/sheet_parser.py`
- `tests/test_sheet_parser.py`

**Kryterium:**
- `SheetParser("N-34-130-D-d-2-4")` parsuje poprawnie
- Walidacja formatu i układu
- Właściwości: `godlo`, `scale`, `uklad`, `components`
- Testy dla skal 1:1M do 1:10k

**Wzorce regex:**
```python
PATTERNS = {
    "1:1000000": r"^([A-Z])-(\d{1,2})$",
    "1:500000": r"^([A-Z])-(\d{1,2})-([A-D])$",
    "1:200000": r"^([A-Z])-(\d{1,2})-(\d{1,3})$",
    "1:100000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])$",
    "1:50000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-dA-D])$",
    "1:25000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-dA-D])-([1-4])$",
    "1:10000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-dA-D])-([1-4])-([1-4])$",
}
```

---

### Etap 4: Parser Godła - Hierarchia (M - 40 min)
- [x] Ukończony

**Pliki:** Rozszerzenie `sheet_parser.py` i `test_sheet_parser.py`

**Metody do dodania:**
- `get_parent()` - arkusz nadrzędny
- `get_children()` - arkusze podrzędne
- `get_hierarchy_up()` - ścieżka do 1:1M
- `get_all_descendants(target_scale)` - wszystkie potomki

**UWAGA:** Podział 1:500k → 1:200k to **36 arkuszy**, nie 4!

---

### Etap 5: Provider Base (S - 25 min)
- [x] Ukończony

**Pliki:**
- `src/kartograf/providers/__init__.py`
- `src/kartograf/providers/base.py`
- `src/kartograf/providers/gugik.py` (szkielet)

**Kryterium:** Abstrakcyjna klasa `BaseProvider` z metodami `construct_url()`, `download()`

---

### Etap 6: GugikClient - Pobieranie (M - 50 min)
- [x] Ukończony

**Pliki:** Rozszerzenie `gugik.py`, `tests/test_gugik_client.py`

**Kryterium:**
- `construct_url(godlo, format)` generuje URL WCS
- `download()` z retry (3 próby, exponential backoff)
- Timeout 30s
- Testy z mock HTTP

**URL GUGiK:**
```python
BASE_URL = "https://mapy.geoportal.gov.pl"
WCS_GEOTIFF = f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
```

---

### Etap 7: Storage (S - 25 min)
- [x] Ukończony

**Pliki:**
- `src/kartograf/download/__init__.py`
- `src/kartograf/download/storage.py`
- `tests/test_storage.py`

**Kryterium:**
- `FileStorage(output_dir)` klasa
- `get_path(godlo, ext)` → `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif`
- Atomic writes (tmp → rename)

---

### Etap 8: Download Manager (M - 50 min)
- [x] Ukończony

**Pliki:**
- `src/kartograf/download/manager.py`
- `tests/test_download_manager.py`

**Kryterium:**
- `download_sheet(godlo, format)` - jeden arkusz
- `download_hierarchy(godlo, target_scale, format, on_progress)` - hierarchia
- Skip już pobranych plików
- Progress callback

---

### Etap 9: CLI - Parse (S - 30 min)
- [x] Ukończony

**Pliki:**
- `src/kartograf/cli/__init__.py`
- `src/kartograf/cli/commands.py`
- `tests/test_cli.py`

**Kryterium:**
- `kartograf --help` działa
- `kartograf parse N-34-130-D` wyświetla info
- `kartograf parse N-34-130-D --hierarchy` wyświetla hierarchię

---

### Etap 10: CLI - Download (M - 35 min)
- [x] Ukończony

**Pliki:** Rozszerzenie `commands.py`

**Kryterium:**
- `kartograf download N-34-130-D-d-2-4` pobiera arkusz
- `kartograf download N-34-130-D --scale 1:10000` pobiera hierarchię
- Opcje: `--format`, `--output`
- Progress bar w konsoli

---

### Etap 11: Public API (S - 15 min)
- [x] Ukończony

**Pliki:** Wszystkie `__init__.py`

**Kryterium:** `from kartograf import SheetParser, DownloadManager` działa

---

### Etap 12: Testy Integracyjne (M - 40 min)
- [x] Ukończony

**Pliki:**
- `tests/test_integration.py`
- `tests/conftest.py`

**Kryterium:** Pokrycie >= 80% dla core logic

---

### Etap 13: Dokumentacja (S - 20 min)
- [x] Ukończony

**Pliki:**
- `README.md` - aktualizacja przykładów
- `CHANGELOG.md` - wersja 0.1.0

---

### Etap 14: Nowa architektura pobierania (L - 120 min) - v0.2.0
- [x] Ukończony

**Problem:** API GUGiK WCS zmieniło się - format AAIGrid nie jest już obsługiwany. Dotychczasowa logika była zbyt skomplikowana.

**Nowa architektura:**
```
Godło  →  OpenData  →  ASC       (pliki są indeksowane po godle)
BBox   →  WCS       →  GeoTIFF   (WCS wycina dowolny prostokąt)
```

**Zmiany:**
- `kartograf/providers/gugik.py`:
  - `download(godlo, path)` - zawsze OpenData, zawsze ASC
  - `download_bbox(bbox, path, format)` - WCS dla dowolnego bbox
  - `_get_opendata_url()` - znajdowanie URL przez WMS GetFeatureInfo
  - Usunięto `construct_url()` z publicznego API
- `kartograf/download/manager.py`:
  - `download_sheet()` - usunięto parametr `format` (zawsze ASC)
  - `download_bbox()` - nowa metoda dla pobierania przez bbox
- `kartograf/providers/base.py` - zaktualizowano interfejs
- 245 testów

**Kryterium ukończenia:**
- `manager.download_sheet("N-34-130-D")` pobiera ASC przez OpenData
- `manager.download_bbox(bbox, "area.tif")` pobiera GeoTIFF przez WCS
- Wszystkie testy przechodzą

---

### Etap 15: Land Cover - Pokrycie Terenu (L - 4-5h) - v0.3.0
- [x] Ukończony

**Cel:** Dodanie funkcjonalności pobierania danych o pokryciu terenu z dwóch źródeł:
- **BDOT10k** (GUGiK) - polska baza wektorowa, wysoka szczegółowość 1:10k
- **CORINE Land Cover** (Copernicus/GIOŚ) - europejski standard, 44 klasy

**Decyzje projektowe:**
- Źródła danych: BDOT10k + CORINE Land Cover
- Metody selekcji: TERYT (powiat), bbox, godło arkusza
- Format wyjściowy: GeoPackage (.gpkg) jako domyślny

**Podetapy:**

**15.1 Abstrakcja LandCoverProvider (S - 30 min)**
- [x] `kartograf/providers/landcover_base.py`
- Interfejs: `download_by_teryt()`, `download_by_bbox()`, `download_by_godlo()`

**15.2 BDOT10k Provider (M - 60 min)**
- [x] `kartograf/providers/bdot10k.py`
- [x] `tests/test_landcover.py` (wspólne testy dla landcover)
- Pobieranie paczek powiatowych (OpenData)
- Pobieranie przez WMS GetFeatureInfo dla URL paczki
- URL: `https://opendata.geoportal.gov.pl/bdot10k/`

**15.3 CORINE Provider (M - 60 min)**
- [x] `kartograf/providers/corine.py`
- [x] `tests/test_landcover.py`
- Lata: 1990, 2000, 2006, 2012, 2018
- **Źródła danych (w kolejności priorytetu):**
  1. CLMS API (GeoTIFF z kodami klas) - wymaga OAuth2 credentials
  2. EEA Discomap WMS (podgląd PNG) - lata 2000-2018
  3. DLR WMS (fallback dla 1990)

**15.4 LandCover Manager (S - 30 min)**
- [x] `kartograf/landcover/__init__.py`
- [x] `kartograf/landcover/manager.py`

**15.5 CLI - Komendy landcover (M - 45 min)**
- [x] Rozszerzenie `kartograf/cli/commands.py`
- Komendy: `kartograf landcover download`, `list-sources`, `list-layers`

**15.6 Testy i dokumentacja (S - 30 min)**
- [x] `tests/test_landcover.py` - 42 testy
- [x] Aktualizacja README.md

**15.7 CORINE OAuth2 Authentication (M - 60 min)**
- [x] OAuth2 RSA authentication dla CLMS API
- [x] Przechowywanie credentials w macOS Keychain (serwis: `clms-token`)
- [x] JWT assertion z RSA private key → access token exchange
- [x] Automatyczne odświeżanie tokenu

**15.8 Auth Proxy - izolacja credentials (M - 60 min)**
- [x] `kartograf/auth/proxy.py` - serwer HTTP (subprocess)
- [x] `kartograf/auth/client.py` - klient singleton
- [x] Credentials izolowane w osobnym procesie (niedostępne dla głównej aplikacji)
- [x] Automatyczne uruchamianie proxy przez CorineProvider
- [x] Tryb `use_proxy=True` (domyślny) vs `use_proxy=False` (testowy)

**15.9 BDOT10k - naprawa ekstrakcji warstw (S - 30 min)**
- [x] Naprawiono ekstrakcję z ZIP - scalanie warstw PT* zamiast pojedynczego pliku
- [x] Nowa metoda `_merge_gpkg_files()` - scalanie przez SQLite ATTACH DATABASE
- [x] Zaktualizowano listę warstw PT* (9 → 12 warstw)
- [x] Warstwy: PTGN, PTKM, PTLZ, PTNZ, PTPL, PTRK, PTSO, PTTR, PTUT, PTWP, PTWZ, PTZB

**Kryterium ukończenia:**
- `kartograf landcover download --source bdot10k --teryt 1465` pobiera paczkę
- `kartograf landcover download --source corine --year 2018 --godlo N-34-130-D` pobiera CLC
- Pokrycie testami >= 80%

---

### Etap 16: SoilGrids - Dane Glebowe (M - 2-3h)
- [x] Ukończony

**Cel:** Dodanie funkcjonalności pobierania danych o glebie z ISRIC SoilGrids (WCS API)

**Źródło danych:**
- **ISRIC SoilGrids** (https://soilgrids.org)
- WCS Endpoint: `https://maps.isric.org/mapserv?map=/map/{property}.map`
- Rozdzielczość: 250m
- Pokrycie: Globalne
- Format: GeoTIFF

**Dostępne parametry glebowe:**
- `bdod` - Gęstość objętościowa (kg/dm³)
- `cec` - Pojemność wymiany kationowej (cmol/kg)
- `cfvo` - Fragmenty gruboziarniste (%)
- `clay` - Zawartość gliny (%)
- `nitrogen` - Azot całkowity (g/kg)
- `ocd` - Gęstość węgla organicznego (kg/m³)
- `ocs` - Zasób węgla organicznego (t/ha)
- `phh2o` - pH w H2O
- `sand` - Zawartość piasku (%)
- `silt` - Zawartość pyłu (%)
- `soc` - Węgiel organiczny (g/kg)

**Głębokości:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm

**Statystyki:** mean, Q0.05, Q0.5, Q0.95, uncertainty

**Podetapy:**

**16.1 SoilGridsProvider (M - 60 min)**
- [x] `kartograf/providers/soilgrids.py`
- [x] Implementacja `download_by_bbox()` przez WCS
- [x] Transformacja CRS (EPSG:2180 → WGS84)

**16.2 Obsługa TERYT (S - 30 min)**
- [x] Implementacja `download_by_teryt()` - lookup bbox dla powiatu
- [x] Reuse wzorca z Bdot10kProvider

**16.3 Integracja z Manager i CLI (S - 30 min)**
- [x] Rejestracja w `PROVIDERS` dict w `manager.py`
- [x] Export w `providers/__init__.py`
- [x] Opcje CLI: `--property`, `--depth`, `--stat`

**16.4 Testy (S - 30 min)**
- [x] `tests/test_soilgrids.py` - 28 testów
- [x] Walidacja parametrów
- [x] Mock HTTP dla pobierania

**Przykłady użycia:**
```bash
# Pobierz węgiel organiczny (SOC) dla godła
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc --depth 0-5cm

# Pobierz zawartość gliny dla bbox
kartograf landcover download --source soilgrids --bbox 450000,550000,460000,560000 --property clay --depth 15-30cm --stat mean

# Lista dostępnych parametrów
kartograf landcover list-layers --source soilgrids
```

**Kryterium ukończenia:**
- `kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc` pobiera GeoTIFF
- `kartograf landcover list-layers --source soilgrids` wyświetla parametry
- Testy przechodzą (28 testów)
- Linting OK (black, flake8)

---

### Etap 17: Hydrologic Soil Groups - HSG (M - 2h)
- [x] Ukończony

**Cel:** Kalkulacja Hydrologic Soil Groups (HSG) z danych tekstury gleby dla metody SCS-CN

**Tło:**
Metoda SCS-CN (Soil Conservation Service - Curve Number) wymaga klasyfikacji gleb do grup hydrologicznych (A, B, C, D) na podstawie ich zdolności infiltracyjnej. HSG można wyznaczyć z danych tekstury gleby (clay, sand, silt) pobieranych z SoilGrids.

**Grupy hydrologiczne (HSG):**
| Grupa | Infiltracja | Tekstury gleby | Potencjał odpływu |
|-------|-------------|----------------|-------------------|
| A | Wysoka | piasek, piasek gliniasty | Niski |
| B | Umiarkowana | glina piaszczysta, glina, pył | Umiarkowany |
| C | Wolna | glina piaszczysto-ilasta, glina ilasta | Wysoki |
| D | Bardzo wolna | ił piaszczysty, ił pylasty, ił | Bardzo wysoki |

**Podetapy:**

**17.1 Moduł hydrologiczny (M - 45 min)**
- [x] `kartograf/hydrology/__init__.py`
- [x] `kartograf/hydrology/hsg.py`
- [x] Klasyfikacja tekstury wg trójkąta USDA (12 klas)
- [x] Mapowanie tekstury → HSG

**17.2 HSGCalculator (M - 45 min)**
- [x] `HSGCalculator.calculate_hsg_by_godlo()` - pobiera clay/sand/silt, klasyfikuje
- [x] `HSGCalculator.calculate_hsg_by_bbox()` - j.w. dla bbox
- [x] `HSGCalculator.get_hsg_statistics()` - statystyki wynikowego rastra

**17.3 CLI - komenda soilgrids hsg (S - 30 min)**
- [x] `kartograf soilgrids hsg --godlo <godło>` - kalkulacja HSG
- [x] Opcje: `--depth`, `--output`, `--keep-intermediate`, `--stats`

**17.4 Testy (S - 30 min)**
- [x] `tests/test_hsg.py` - 34 testy
- [x] Testy klasyfikacji USDA
- [x] Testy mapowania HSG
- [x] Testy CLI

**Nowe zależności:**
- `rasterio>=1.3.0` - przetwarzanie rastrów
- `numpy>=1.24.0` - operacje na tablicach

**Przykłady użycia:**
```bash
# Oblicz HSG dla godła
kartograf soilgrids hsg --godlo N-34-130-D --output /tmp/hsg.tif

# Ze statystykami
kartograf soilgrids hsg --godlo N-34-130-D --stats

# Inna głębokość
kartograf soilgrids hsg --godlo N-34-130-D --depth 15-30cm

# Zachowaj pliki pośrednie (clay, sand, silt)
kartograf soilgrids hsg --godlo N-34-130-D --keep-intermediate
```

**Format wyjściowy:**
Raster GeoTIFF z wartościami 1-4:
- 1 = Grupa A
- 2 = Grupa B
- 3 = Grupa C
- 4 = Grupa D
- 0 = NoData

**Kryterium ukończenia:**
- `kartograf soilgrids hsg --godlo N-34-130-D` generuje raster HSG
- `kartograf soilgrids hsg --godlo N-34-130-D --stats` wyświetla statystyki
- Testy przechodzą (347 testów łącznie)
- Linting OK (black, flake8)

---

### Etap 18: NMT Resolution Selection (S - 1h)
- [x] Ukończony

**Cel:** Dodanie możliwości wyboru rozdzielczości NMT (1m/5m) dla danych z GUGiK

**Tło:**
GUGiK udostępnia dane NMT w dwóch rozdzielczościach:
- **1m** (GRID1) - wysoka rozdzielczość, dostępna dla KRON86 i EVRF2007
- **5m** (GRID5) - niższa rozdzielczość, dostępna tylko dla EVRF2007

**Ograniczenia:**
- Rozdzielczość 5m dostępna tylko w układzie EVRF2007
- WCS (download_bbox) dostępne tylko dla 1m
- 5m pobierane przez OpenData (arkusze ASC)

**Zmiany:**

**18.1 GugikProvider (M - 30 min)**
- [x] Dodano parametr `resolution` ("1m" lub "5m")
- [x] Nowe endpointy WMS dla 5m: `SheetsGrid5mEVRF2007`
- [x] Walidacja: 5m wymaga EVRF2007
- [x] `download_bbox()` rzuca ValueError dla 5m
- [x] Nowe metody: `get_supported_resolutions()`, `is_wcs_available()`

**18.2 DownloadManager (S - 15 min)**
- [x] Dodano parametr `resolution`
- [x] Automatyczne wymuszenie EVRF2007 dla 5m

**18.3 CLI (S - 15 min)**
- [x] Opcja `--resolution` / `-r` dla komendy `download`
- [x] Komunikaty o rozdzielczości w progress

**18.4 Testy (S - 15 min)**
- [x] 18 nowych testów dla resolution
- [x] Testy walidacji, endpointów, WCS availability

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (domyślnie)
kartograf download N-34-130-D-d-2-4

# Pobierz NMT 5m (wymusza EVRF2007)
kartograf download N-34-130-D-d-2-4 --resolution 5m

# Pobierz hierarchię w 5m
kartograf download N-34-130-D --scale 1:10000 --resolution 5m
```

**Kryterium ukończenia:**
- `kartograf download N-34-130-D --resolution 5m` pobiera NMT 5m
- Testy przechodzą (365 testów łącznie)
- Linting OK (black, flake8)

---

## Diagram Zależności

```
Etap 0 (Git) → Etap 1 (Setup) → Etap 2 (Wyjątki)
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
              Etap 3 (Parser)                     Etap 5 (Provider)
                    │                                   │
                    ▼                                   ▼
              Etap 4 (Hierarchia)                 Etap 6 (GugikClient)
                    │                                   │
                    ▼                                   │
              Etap 7 (Storage)                          │
                    │                                   │
                    └─────────────┬─────────────────────┘
                                  ▼
                            Etap 8 (Manager)
                                  │
                                  ▼
                         Etap 9-10 (CLI)
                                  │
                                  ▼
                         Etap 11-13 (Finalizacja)
```

---

## Komendy Pomocnicze

```bash
# Aktywacja środowiska
source .venv/bin/activate

# Testy
pytest tests/ -v
pytest tests/ --cov=kartograf --cov-report=html

# Formatowanie i linting
black kartograf/ tests/
flake8 kartograf/ tests/ --max-line-length=88

# Instalacja w trybie dev
pip install -e .
```

---

## Pliki Krytyczne

1. `kartograf/core/sheet_parser.py` - parser godeł
2. `kartograf/providers/gugik.py` - integracja z GUGiK (NMT)
3. `kartograf/providers/corine.py` - CORINE Land Cover
4. `kartograf/providers/bdot10k.py` - BDOT10k
5. `kartograf/providers/soilgrids.py` - ISRIC SoilGrids (dane glebowe)
6. `kartograf/hydrology/hsg.py` - kalkulacja HSG (grupy hydrologiczne)
7. `kartograf/auth/proxy.py` - Auth Proxy (izolacja credentials)
8. `kartograf/download/manager.py` - zarządzanie pobieraniem
9. `kartograf/cli/commands.py` - interfejs CLI
10. `pyproject.toml` - konfiguracja projektu

---

## Uwagi

- **Podział 1:500k → 1:200k:** 36 arkuszy (nie 4!)
- **URL WCS:** może wymagać weryfikacji z API GUGiK
- **Testy:** zawsze uruchamiaj przed commitem

---

## Stan CLMS API (2026-01-18)

### Auth Proxy (tryb bezpieczny - domyślny)

CorineProvider domyślnie używa **Auth Proxy** - osobnego procesu który izoluje credentials:

```
CorineProvider → HTTP localhost → AuthProxy subprocess → Keychain → CLMS API
                                        ↑
                              Credentials nigdy nie opuszczają tego procesu
```

**Architektura:**
- `kartograf/auth/proxy.py` - serwer HTTP (subprocess)
- `kartograf/auth/client.py` - klient singleton, automatycznie uruchamia proxy
- Proxy odczytuje credentials z Keychain, wykonuje JWT→token, zwraca tylko odpowiedzi

**Konfiguracja credentials:**
```bash
# Zapisz credentials do Keychain
security add-generic-password -a "$USER" -s "clms-token" -w '<json_credentials>'

# Format JSON:
{
  "client_id": "...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "token_uri": "https://land.copernicus.eu/@@oauth2-token",
  "key_id": "...",
  "user_id": "..."
}
```

**Tryby CorineProvider:**
```python
# Tryb proxy (domyślny, bezpieczny)
provider = CorineProvider()  # use_proxy=True

# Tryb bezpośredni (dla testów, credentials widoczne)
provider = CorineProvider(clms_credentials={...}, use_proxy=False)
```

### Status CLMS API

- **Token exchange działa** przez proxy
- **CLMS API przyjmuje żądania** - przetwarzanie może trwać długo (kolejka)
- **Fallback na WMS** gdy brak credentials lub timeout

**Pliki kluczowe:**
- `kartograf/auth/proxy.py` - Auth Proxy server
- `kartograf/auth/client.py` - Auth Proxy client
- `kartograf/providers/corine.py` - CorineProvider
- `kartograf/providers/bdot10k.py` - Bdot10kProvider
- `kartograf/providers/landcover_base.py` - abstrakcja LandCoverProvider
- `tests/test_landcover.py` - 42 testy

---

## QA Review (2026-01-21)

### Przeprowadzone sprawdzenia

| Obszar | Status | Uwagi |
|--------|--------|-------|
| Testy | ✅ 365/365 PASS | 0.92s |
| Linting (black, flake8) | ✅ OK | Wszystkie pliki zgodne |
| Bezpieczeństwo | ✅ OK | Brak hardcoded secrets, Auth Proxy OK |
| Spójność wersji | ✅ NAPRAWIONE | Zsynchronizowano do 0.3.1 |
| Spójność zależności | ✅ NAPRAWIONE | pyproject.toml + requirements.txt |
| Pokrycie testami | ⚠️ 57% | Cel 80%, do poprawy w przyszłości |

### Pokrycie testami - szczegóły

**Dobre pokrycie (>80%):**
- `download/manager.py`: 100%
- `exceptions.py`: 100%
- `core/sheet_parser.py`: 98%
- `providers/gugik.py`: 94%
- `providers/soilgrids.py`: 80%

**Do poprawy (<60%):**
- `auth/client.py`: 0%
- `auth/proxy.py`: 0%
- `providers/bdot10k.py`: 28%
- `providers/corine.py`: 34%
- `hydrology/hsg.py`: 59%

### Backlog - do zrobienia w przyszłości

1. **[REFACTOR] Ujednolicenie interfejsów providerów**
   - `BaseProvider` używa `base_url`, `LandCoverProvider` używa `source_url`
   - Różne domyślne timeouty (30s vs 60s)
   - Rozważyć wspólną klasę bazową lub dokumentację różnic

2. **[TEST] Zwiększenie pokrycia testami do 80%**
   - Priorytet: `auth/`, `providers/bdot10k.py`, `providers/corine.py`

3. **[DOCS] Aktualizacja SCOPE.md i PRD.md**
   - Dokumentacja opisuje tylko MVP (NMT)
   - Brak opisu Land Cover, SoilGrids, HSG
   - Sekcja "Out of Scope" zawiera już zaimplementowane funkcje

4. ✅ **[API] Uzupełnienie eksportów w __init__.py** - NAPRAWIONE (2026-01-21)
   - Dodano `SoilGridsProvider` do głównego modułu
   - Dodano `HSGCalculator` do głównego modułu

---

## Cross-Project Analysis (2026-01-21)

Przeprowadzono analizę integracji 4 repozytoriów: **Hydrograf**, **Hydrolog**, **Kartograf**, **IMGWTools**.

### Mapa zależności

```
HYDROGRAF (główna aplikacja)
    ├── IMGWTools (dane IMGW)
    ├── Kartograf (dane GIS) ← TEN PROJEKT
    └── Hydrolog (obliczenia hydrologiczne)
            ├── IMGWTools (wymagany)
            └── Kartograf (opcjonalny)
```

### Problemy wykryte w Kartograf

| Problem | Status | Priorytet |
|---------|--------|-----------|
| Brak `SoilGridsProvider` w `__init__.py` | ✅ Naprawione | WAŻNY |
| Brak `HSGCalculator` w `__init__.py` | ✅ Naprawione | WAŻNY |
| SCOPE.md/PRD.md nieaktualne (tylko MVP) | 🟡 Backlog | NISKI |

### Standardy kodu - porównanie z innymi projektami

| Aspekt | Kartograf | Hydrolog | IMGWTools | Zgodność |
|--------|-----------|----------|-----------|----------|
| Python | >=3.12 | >=3.12 | >=3.11 | ⚠️ |
| Line length | 88 | 88 | 88 | ✅ |
| Formatter | black | black | ruff | ⚠️ |
| numpy | >=1.24.0 | >=1.24 | - | ✅ |

### Plan naprawy Kartograf

1. ✅ **[NAPRAWIONE 2026-01-21]** Dodano eksporty do `__init__.py`:
   ```python
   from kartograf.providers.soilgrids import SoilGridsProvider
   from kartograf.hydrology.hsg import HSGCalculator
   ```

2. **[BACKLOG]** Zaktualizować SCOPE.md i PRD.md

### Pełna dokumentacja

Szczegółowa analiza cross-project: `Hydrograf/docs/CROSS_PROJECT_ANALYSIS.md`
