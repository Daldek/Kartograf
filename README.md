# Kartograf

Narzędzie do automatycznego pobierania danych przestrzennych z zasobów GUGiK, Copernicus i ISRIC dla Polski:
- **NMT/NMPT** - Numeryczny Model Terenu / Pokrycia Terenu (dane wysokościowe)
- **BDOT10k** - Baza Danych Obiektów Topograficznych (pokrycie terenu, wektory)
- **CORINE Land Cover** - Europejska klasyfikacja pokrycia terenu (44 klasy)
- **SoilGrids** - Globalne dane glebowe (tekstura, węgiel organiczny, pH)
- **HSG** - Hydrologic Soil Groups dla metody SCS-CN (grupy hydrologiczne gleb)

## Szybki Start

### Instalacja

```bash
# Klonowanie repozytorium
git clone https://github.com/Daldek/Kartograf.git
cd Kartograf

# Utworzenie środowiska wirtualnego
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalacja pakietu
pip install -e .
```

### Użycie

#### Jako CLI

```bash
# Informacje o godle
kartograf parse N-34-130-D-d-2-4

# Pobieranie NMT (pojedynczy arkusz)
kartograf download N-34-130-D-d-2-4

# Pobieranie NMT (hierarchia)
kartograf download N-34-130-D --scale 1:10000 --output ./data

# Pobieranie NMT w rozdzielczości 5m (tylko EVRF2007)
kartograf download N-34-130-D-d-2-4 --resolution 5m
kartograf download N-34-130-D --scale 1:10000 -r 5m

# Pobieranie Land Cover (BDOT10k - powiat)
kartograf landcover download --source bdot10k --teryt 1465

# Pobieranie Land Cover (BDOT10k - godło)
kartograf landcover download --source bdot10k --godlo N-34-130-D

# Pobieranie Land Cover (CORINE)
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D

# Pobieranie danych glebowych (SoilGrids)
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Obliczanie Hydrologic Soil Groups (HSG) dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats
kartograf soilgrids hsg --godlo N-34-130-D --output /tmp/hsg.tif --keep-intermediate

# Lista źródeł i warstw
kartograf landcover list-sources
kartograf landcover list-layers --source bdot10k
kartograf landcover list-layers --source soilgrids
```

#### Jako biblioteka Python

```python
from kartograf import SheetParser, DownloadManager, BBox

# Parsowanie godła
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)      # "1:10000"
print(parser.godlo)      # "N-34-130-D-d-2-4"
print(parser.components) # {"pas": "N", "slup": "34", ...}

# Bounding box arkusza
bbox = parser.get_bbox(crs="EPSG:2180")  # lub "EPSG:4326"
print(f"x: [{bbox.min_x:.2f}, {bbox.max_x:.2f}]")
print(f"y: [{bbox.min_y:.2f}, {bbox.max_y:.2f}]")

# Pobieranie arkusza przez godło → ASC (OpenData)
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")  # → .asc

# Pobieranie hierarchii arkuszy → ASC (OpenData)
paths = manager.download_hierarchy(
    godlo="N-34-130-D",
    target_scale="1:10000"
)  # → 64 plików .asc

# Pobieranie NMT w rozdzielczości 5m (tylko EVRF2007)
manager_5m = DownloadManager(output_dir="./data", resolution="5m")
path = manager_5m.download_sheet("N-34-130-D-d-2-4")  # → .asc (5m)

# Pobieranie przez bbox → GeoTIFF (WCS) - tylko dla 1m
bbox = BBox(min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180")
path = manager.download_bbox(bbox, "my_area.tif")  # → .tif

# ===== Land Cover =====
from kartograf import LandCoverManager

lc = LandCoverManager()

# BDOT10k - przez godło
lc.download(godlo="N-34-130-D")

# BDOT10k - przez TERYT (powiat)
lc.download(teryt="1465")

# CORINE - przez godło
lc.set_provider("corine")
lc.download(godlo="N-34-130-D", year=2018)

# SoilGrids - dane glebowe
lc.set_provider("soilgrids")
lc.download(godlo="N-34-130-D", property="soc", depth="0-5cm")

# ===== Hydrologic Soil Groups =====
from kartograf.hydrology import HSGCalculator

calc = HSGCalculator()

# Oblicz HSG dla godła
calc.calculate_hsg_by_godlo("N-34-130-D", Path("./hsg.tif"))

# Statystyki HSG
stats = calc.get_hsg_statistics(Path("./hsg.tif"))
for group, data in stats.items():
    print(f"Grupa {group}: {data['percent']:.1f}%")
```

## Funkcjonalności

### NMT (Numeryczny Model Terenu)
- ✅ **Parser godeł** - Obsługa układów 1992 i 2000, skal 1:1 000 000 - 1:10 000
- ✅ **Bounding box** - Obliczanie współrzędnych arkusza (EPSG:2180, EPSG:4326)
- ✅ **Hierarchia arkuszy** - Automatyczne określanie arkuszy nadrzędnych i podrzędnych
- ✅ **Pobieranie NMT** - Z retry logic i progress tracking
- ✅ **Organizacja plików** - Automatyczna struktura katalogów
- ✅ **Formaty** - GeoTIFF, PNG, JPEG (WCS), ASC (OpenData)
- ✅ **Rozdzielczości:**
  - `1m` (GRID1) - wysoka rozdzielczość, KRON86 i EVRF2007
  - `5m` (GRID5) - niższa rozdzielczość, tylko EVRF2007

### Land Cover (Pokrycie Terenu)
- ✅ **BDOT10k** - Polska baza wektorowa (GUGiK), szczegółowość 1:10 000
  - 12 warstw pokrycia terenu (PT*): lasy, wody, zabudowa, tereny rolne, itp.
  - Automatyczne scalanie warstw do jednego GeoPackage
- ✅ **CORINE Land Cover** - Europejska klasyfikacja (Copernicus), 44 klasy
- ✅ **Metody selekcji** - TERYT (powiat), bbox, godło arkusza
- ✅ **Formaty** - GeoPackage, Shapefile, GeoTIFF, PNG

### SoilGrids (Dane Glebowe)
- ✅ **ISRIC SoilGrids** - Globalne dane glebowe, rozdzielczość 250m
- ✅ **11 parametrów glebowych:**
  - `clay`, `sand`, `silt` - tekstura gleby (%)
  - `soc` - węgiel organiczny (g/kg)
  - `phh2o` - pH w H2O
  - `nitrogen` - azot całkowity (g/kg)
  - `bdod` - gęstość objętościowa (kg/dm³)
  - `cec` - pojemność wymiany kationowej (cmol/kg)
  - `cfvo` - fragmenty gruboziarniste (%)
  - `ocd`, `ocs` - gęstość i zasób węgla organicznego
- ✅ **6 głębokości:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
- ✅ **5 statystyk:** mean, Q0.05, Q0.5, Q0.95, uncertainty

### Hydrologic Soil Groups (HSG)
- ✅ **Kalkulacja HSG** dla metody SCS-CN (Curve Number)
- ✅ **Klasyfikacja USDA** - trójkąt tekstury, 12 klas
- ✅ **4 grupy hydrologiczne:**
  - A - wysoka infiltracja (piasek)
  - B - umiarkowana infiltracja (glina)
  - C - wolna infiltracja (glina ilasta)
  - D - bardzo wolna infiltracja (ił)
- ✅ **Automatyczne pobieranie** clay/sand/silt z SoilGrids
- ✅ **Statystyki pokrycia** dla każdej grupy HSG

## Konfiguracja CLMS API (opcjonalne)

Aby pobierać dane CORINE jako **GeoTIFF z kodami klas** (zamiast podglądu PNG),
potrzebujesz konta w Copernicus Land Monitoring Service:

1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (profil → API access)
3. Zapisz credentials do macOS Keychain:

```bash
security add-generic-password -a "$USER" -s "clms-token" -w '{
  "client_id": "...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "token_uri": "https://land.copernicus.eu/@@oauth2-token",
  "key_id": "...",
  "user_id": "..."
}'
```

**Bezpieczeństwo:** Credentials są izolowane w osobnym procesie (Auth Proxy).
Główna aplikacja nigdy nie widzi kluczy prywatnych.

**Bez konfiguracji:** CORINE automatycznie pobiera podgląd PNG przez WMS.

## Dokumentacja

- [SCOPE.md](docs/SCOPE.md) - Zakres projektu (co JEST i czego NIE MA)
- [PRD.md](docs/PRD.md) - Product Requirements Document
- [IMPLEMENTATION_PROMPT.md](docs/IMPLEMENTATION_PROMPT.md) - Instrukcje dla AI assistants
- [DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md) - Standardy kodowania
- [PROGRESS.md](docs/PROGRESS.md) - Plan i status implementacji
- [CHANGELOG.md](docs/CHANGELOG.md) - Historia zmian

## Wymagania

- Python 3.12+
- requests >= 2.31.0
- pyproj >= 3.6.0
- PyJWT[crypto] >= 2.8.0
- rasterio >= 1.3.0
- numpy >= 1.24.0

## Struktura Projektu

```
Kartograf/
├── kartograf/           # Kod źródłowy
│   ├── auth/            # Auth Proxy (bezpieczna autentykacja CLMS)
│   ├── core/            # Parser godeł, BBox
│   ├── providers/       # Providery danych (GUGiK, BDOT10k, CORINE, SoilGrids)
│   ├── download/        # Download management (NMT)
│   ├── landcover/       # Land Cover management
│   ├── hydrology/       # Hydrologic Soil Groups (HSG)
│   └── cli/             # CLI interface
├── tests/               # Testy (365)
├── docs/                # Dokumentacja
└── README.md
```

## Dla Deweloperów

### Środowisko

```bash
# Aktywuj .venv
source .venv/bin/activate

# Przeczytaj dokumentację przed rozpoczęciem
cat CLAUDE.md
```

### Testy

```bash
# Uruchom wszystkie testy
pytest tests/

# Z pokryciem kodu
pytest tests/ --cov=kartograf --cov-report=html

# Formatowanie
black kartograf/ tests/

# Linting
flake8 kartograf/ tests/ --max-line-length=88
```

## Licencja

Projekt udostępniony na licencji MIT. Szczegóły w pliku `LICENSE`.

## Autor

[Piotr de Bever](https://www.linkedin.com/in/piotr-de-bever/)

## Status

**Wersja 0.3.1** - Dodano wybór rozdzielczości NMT (1m/5m), Land Cover (BDOT10k, CORINE), SoilGrids (dane glebowe) oraz HSG (grupy hydrologiczne dla SCS-CN). Zobacz [CHANGELOG.md](docs/CHANGELOG.md) dla szczegółów.
