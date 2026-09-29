# Kartograf

Narzędzie do automatycznego pobierania danych przestrzennych z zasobów GUGiK (Polska), CUZK (Czechy), Copernicus i ISRIC:
- **NMT (PL)** - Numeryczny Model Terenu z GUGiK (dane wysokościowe, 1m/5m)
- **NMT (CZ)** - DMR 5G/4G z CUZK (2m/5m, godło TM33/SM5 lub bbox, `--country {pl,cz,auto}`)
- **NMPT** - Numeryczny Model Pokrycia Terenu / DSM (teren + obiekty, 1m)
- **Ortofotomapa** - Zdjęcia lotnicze Standard Resolution (25cm, TIF)
- **LAZ** - Chmury punktów LIDAR (dane pomiarowe ALS) z GUGiK przez WFS
- **BDOT10k** - Baza Danych Obiektów Topograficznych (pokrycie terenu, wektory)
- **CORINE Land Cover** - Europejska klasyfikacja pokrycia terenu (44 klasy)
- **SoilGrids** - Globalne dane glebowe (tekstura, węgiel organiczny, pH)
- **HSG** - Hydrologic Soil Groups dla metody SCS-CN (grupy hydrologiczne gleb)

> **0.7.0-dev:** testy na żywych danych (2026-09-29) wykazały znane błędy —
> m.in. `--product laz` pobiera kafle z innego miejsca. Zobacz
> [Znane problemy (0.7.0-dev)](#znane-problemy-070-dev).

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
# Informacje o godle (auto-detekcja PL-1992 / PL-2000)
kartograf parse N-34-130-D-d-2-4

# Pobieranie NMT: pojedynczy arkusz albo hierarchia, opcjonalnie 5m
kartograf download N-34-130-D-d-2-4
kartograf download N-34-130-D --scale 1:10000 --resolution 5m --output ./data

# Inne produkty GUGiK: NMPT (DSM), ortofotomapa, chmury punktów LAZ
kartograf download N-34-130-D-d-2-4 --product nmpt
kartograf download N-34-130-D-d-2-4 --product laz   # znany błąd K1 - patrz Znane problemy

# Selekcja obszaru: bbox albo plik geometrii (SHP/GPKG).
# Domyślnie działa --country auto: obszar przecinający prostokątną obwiednię CZ
# (na zachód od 18,86°E i na południe od 51,06°N) trafia także do CUZK - dla czystego
# PL użyj --country pl. Flagi bez odpowiednika czeskiego (--product nmpt|orto,
# --system, --vertical-crs KRON86, --resolution 1m) same przełączają auto na pl
# (komunikat "Info:" na stderr) na obszarze objętym obwiedniami OBU krajów.
# Prostokąt PL (14,07–24,20°E, 49,00–54,90°N) obejmuje większość Czech, więc
# np. w Pradze czy Brnie taka flaga kieruje zadanie do GUGiK, który nie ma tam
# danych (błąd pobrania); od razu, przed siecią, błąd dostaje dopiero obszar
# poza prostokątem PL (dla --product nmpt|orto - komunikat o etapie 2).
# Pod auto część obszaru poza prostokątami krajów (np. na zachód od 14,07°E)
# jest pomijana bez komunikatu (znany błąd S3) - cały bbox pobiera --country pl.
kartograf download --bbox 771000,509000,772000,510000 --product orto
kartograf download --geometry zlewnia.gpkg --layer catchments

# Jeden scalony GeoTIFF NMT zamiast listy arkuszy (--target-crs; lokalna
# reprojekcja przypiętą operacją; PL: tylko --product nmt i system 1992;
# arkusz bez danych GUGiK - morze, strona zagraniczna - to nodata + "Warning:").
# Na pograniczu, także z Niemcami (danych DE nie obsługujemy), używaj
# --target-crs: bez niego arkusz leżący za granicą kończy polecenie kodem 1.
kartograf download --bbox 530000,382000,533000,386000 --country pl --target-crs EPSG:2180
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --target-crs EPSG:2180

# PL-2000: godło albo bbox w CRS strefy
kartograf download 6.179.12.20
kartograf download --bbox 6500000,5895000,6508000,5900000 --bbox-crs EPSG:2177 --system 2000

# NMT Czechy (CUZK DMR 5G/4G); na pograniczu --country auto dzieli żądanie na PL i CZ
# (osobne pliki i sidecary, wspólny extra.parent_request). Porażka jednego kraju
# (brak danych albo awaria źródła) przy sukcesie drugiego kończy się kodem 0
# i ostrzeżeniem "Warning:" na stderr.
kartograf download 302_5550 --country cz
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto
# Bboxy w EPSG:5514 są na terytorium CZ ujemne - podaj je bez spacji po --bbox=
kartograf download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --resolution 5m

# Pokrycie terenu i gleby: BDOT10k, CORINE, SoilGrids
kartograf landcover download --source bdot10k --teryt 1465
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Hydrologic Soil Groups dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats

# Przegląd źródeł/warstw i cache metadanych
kartograf landcover list-sources
kartograf landcover list-layers --source soilgrids
kartograf cache stats
```

#### Jako biblioteka Python

```python
from pathlib import Path
from kartograf import SheetParser, DownloadManager, BBox

# Parsowanie godła i bounding box arkusza
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)                      # "1:10000"
bbox = parser.get_bbox(crs="EPSG:2180")  # lub "EPSG:4326"

# Pobieranie przez godło → ASC (OpenData); hierarchia: download_hierarchy()
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")

# Pobieranie przez bbox → GeoTIFF (WCS) - tylko NMT 1m i tylko w układzie KRON86:
# endpoint WCS dla EVRF2007 został wycofany przez GUGiK (HTTP 404 od 2026-08), więc
# download_bbox pod EVRF2007 kończy się ValidationError. Wysokości EVRF2007
# bierz z arkuszy: download_sheet() albo CLI `--bbox` (rozwijany na arkusze OpenData),
# a jako jeden GeoTIFF z arkuszy: download_pl_cutout() (niżej).
kron = DownloadManager(output_dir="./data", vertical_crs="KRON86")
area = BBox(min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180")
path = kron.download_bbox(area, "my_area.tif")

# Land Cover: BDOT10k / CORINE / SoilGrids
from kartograf import LandCoverManager
lc = LandCoverManager()
lc.download(teryt="1465")                   # BDOT10k (powiat)
lc.set_provider("corine")
lc.download(godlo="N-34-130-D", year=2018)  # CORINE

# Hydrologic Soil Groups
from kartograf import HSGCalculator
calc = HSGCalculator()
calc.calculate_hsg_by_godlo("N-34-130-D", Path("./hsg.tif"))
stats = calc.get_hsg_statistics(Path("./hsg.tif"))

# Scalony wycinek NMT PL w zadanym układzie (jeden GeoTIFF + sidecar)
from kartograf import BBox, download_pl_cutout

result = download_pl_cutout(
    BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
    "EPSG:5514",
    output_dir="./data",
    max_workers=4,
)
print(result.path)
# arkusze bez danych GUGiK (nodata); pusta krotka, gdy result.skipped (plik już
# istniał) - wtedy lista jest tylko w sidecarze extra.missing_sheets (znany błąd N4)
print(result.missing_sheets)
# Wyjątki: DownloadError (awaria pobrania arkusza - wycinek nie powstaje),
# ValidationError (żaden arkusz nie ma danych, za mało miejsca na dysku,
# nieobsługiwany parametr), TransformError (brak przypiętej operacji).
# Kroki osobno (własny provider/sesja/FileStorage):
# prepare_pl_cutout -> select_pl_cutout_sheets -> run_pl_cutout.
```

Pozostałe elementy publicznego API (m.in. `GugikNmptProvider`, `GugikOrtoProvider`,
`GugikLazProvider`, `CuzkDmrProvider`/`create_dmr_provider` dla Czech, `Parser2000`,
`ParserTM33`, `MetadataCache`, `FileStorage`) — patrz eksporty w `kartograf/__init__.py`
oraz [SCOPE.md](docs/SCOPE.md).

### Wynik pobrania

`DownloadManager.download_sheet()` zwraca **`Path`** dla arkusza 1:10000 i dla godła
PL-2000 (pobierane bezpośrednio), a **`list[Path]`** dla godła PL-1992 grubszego niż
1:10000 - takie godło jest automatycznie rozwijane do arkuszy 1:10000 przez
`download_hierarchy()` (ta zawsze zwraca `list[Path]`, a podsumowanie sukcesów/porażek
zostawia w `DownloadManager.last_result`). CLI musi obsłużyć oba warianty.
`DownloadManager.download_sheets(godla)` pobiera listę godeł (grubsze PL-1992
rozwijane do 1:10000 — `expand_sheets()`) i nie przerywa się na porażce arkusza:
porażki trafiają do `last_result.failed`, a arkusze, dla których GUGiK nie ma
danych (`NoCoverageError`, podklasa `DownloadError`), także do
`last_result.no_coverage`.

Każde udane pobranie zapisuje **dwa** pliki: dane (`.asc`, `.tif`, `.laz`, `.gpkg`)
oraz sidecar `<plik>.meta.json` ze schematem `kartograf-meta/1`:

| Pole | Znaczenie |
|---|---|
| `dataset`, `country`, `product`, `provider` | klucz deskryptora źródła i jego opis |
| `horizontal_crs` | układ poziomy pliku: PL `EPSG:2180`; CZ natywnie `EPSG:5514`, kafel TM33 pobrany godłem `EPSG:3045`, a po `--target-crs` układ docelowy (PL i CZ). Pliki PL-2000 też dostają dziś `EPSG:2180`, choć leżą w strefie 2176-2179 (znany błąd N8) |
| `vertical_crs` | kod realizacji układu pionowego: `EPSG:9651` (EVRF2007-PL), `EPSG:9650` (KRON86), `EPSG:8357` (Bpv), `EPSG:5621` (EVRF2007) |
| `vertical_source` | `native` / `ellipsoidal` / `server` |
| `nodata` | wartość pustego piksela odczytana z pliku |
| `resolution`, `request` | rozdzielczość i żądanie tego pliku (`godlo` albo `bbox` + `bbox_crs`); dla wycinków (`bbox/`) to obwiednia wyniku w jego układzie (po przycięciu do kraju i transformacji) - oryginalne żądanie niesie `extra.parent_request` |
| `license` | identyfikator, atrybucja i URL licencji źródła |
| `downloaded_at`, `kartograf_version` | znacznik czasu UTC i wersja pakietu |
| `transform` | słownik osi (klucze `horizontal`/`vertical`) z opisem użytej operacji: `pinned: <opis> (<dokładność> m)`; oś bez przeliczenia nie ma klucza, a bez żadnego przeliczenia (pliki PL pobierane godłem/arkuszami oraz wycinek `--target-crs EPSG:2180`) całe pole to `null`; wycinek PL w innym układzie niesie `pinned: ...` w osi poziomej ([ADR-027](docs/DECISIONS.md)) |
| `extra.parent_request` | oryginalny bbox, jego układ i próbowane kraje - wspólny klucz grupowania plików jednego żądania `--bbox`/`--geometry`, także po obu stronach granicy; przy `--target-crs` niosą go sidecar wycinka i sidecary arkuszy PL pobranych w tym przebiegu. **Wyjątki:** kafle LAZ mają własny przepływ i tego klucza nie niosą (ich `extra` to `godlo_kafla`/`rok`/`gestosc`/`url`); arkusze pominięte jako już pobrane zachowują poprzedni sidecar (znany błąd N4); biblioteka (`download_pl_cutout`) zapisuje go tylko, gdy wołający poda `parent_request=` |
| `extra.missing_sheets` | tylko wycinek PL (`--target-crs`, `download_pl_cutout`): posortowana lista godeł, dla których GUGiK nie ma danych - w ich miejscu wycinek ma nodata (pole jest tylko wtedy, gdy lista jest niepusta). Nie jest pełnym obrazem nodata: dziury bywają też wewnątrz pobranych arkuszy przybrzeżnych i przygranicznych |

Sidecary pisze warstwa zarządzająca (`DownloadManager`, `LandCoverManager`,
wycinek PL w bibliotece - `download/cutout.py`, CLI dla LAZ i CZ),
a `FileStorage.delete()` usuwa sidecar razem z plikiem danych.

## Znane problemy (0.7.0-dev)

Testy na żywych danych GUGiK i CUZK (2026-09-29: centrum kraju, pas morski,
pogranicza z Czechami, Niemcami, Słowacją, Ukrainą, Białorusią, Litwą i Rosją)
potwierdziły mechanikę wycinka, układu `data/` i sidecarów, ale wykazały błędy
kodu, które czekają na decyzję o naprawie przed wydaniem 0.7.0. Pełna lista
(ID, waga, dowody):
[PROGRESS.md, „Znane bledy (testy na zywo 2026-09-29)”](docs/PROGRESS.md#znane-bledy-testy-na-zywo-2026-09-29).

- **K1 - `--product laz` pobiera kafle z innego miejsca.** Zapytanie WFS
  wysyła bbox z zamienionymi osiami, więc kafle pochodzą z obszaru oddalonego
  o setki kilometrów (dla okolic Krakowa - z Lubuskiego). Nie używaj LAZ do
  czasu naprawy.
- **K2 - treść CZ po reprojekcji jest przesunięta o 1-5 m.** Przypięta
  operacja S-JTSK → ETRS89 to transformacja dla Słowacji (EPSG:4829), a nie
  dla Czech (EPSG:1622). Dotyczy kafli TM33 (godło), `--target-crs` dla CZ
  i wycinka PL do `EPSG:5514`; treść pobierana natywnie (`EPSG:5514` bez
  `--target-crs`, arkusze SM5) nie jest przesunięta.
- **K3/K4 - arkusz NMT/NMPT/orto może pochodzić ze starszej albo innej
  edycji.** Chwilowy błąd skorowidza GUGiK przy nowszej warstwie daje po cichu
  starszą kampanię (plik zostaje w cache), a wybór pliku bierze pierwszy URL
  zawierający godło - bywa to plik 0,5 m zamiast 1 m, arkusz PL-1992 pod
  godłem PL-2000 albo najstarsze zdjęcie. Sidecar nie zapisuje URL-a ani daty
  kampanii.
- **K5 - `--product orto` pobiera wariant CIR (podczerwień) zamiast RGB.**
- **K6 - duży bbox CZ w 2 m kończy się HTTP 500.** Serwer CUZK przyjmuje
  realnie ok. 8 Mpx na zapytanie (nie deklarowane 15000 × 4100 px), a klient
  tnie kafle dopiero powyżej 15000 × 4100 px, więc obszar zbliżony do kwadratu
  większy niż ok. 5,5 × 5,5 km (albo np. 10 × 5 km wydłużony W-E) nie
  przechodzi; pas N-S o szerokości do ok. 3,6 km przechodzi
  (np. 3,6 × 24,6 km).
- **S2 - tryb listy arkuszy na morzu i na granicy kończy się kodem 1.** Bez
  `--target-crs` arkusz bez danych (morze, arkusz za granicą) to błąd całego
  polecenia, a przy `--workers 1` pobieranie staje na pierwszym takim arkuszu.
  Obejście (tylko `--product nmt`, system 1992): `--target-crs EPSG:2180`
  (arkusze bez danych stają się nodata z ostrzeżeniem `Warning:`).
- **S1 - zapytania skorowidza GUGiK nie są ponawiane.** Przy zrywanych
  połączeniach wycinek (zwłaszcza z wieloma arkuszami bez danych - morze,
  granica) kończy się kodem 1 („ponów pobranie”); ponowne uruchomienie używa
  arkuszy już pobranych.

## Funkcjonalności

### NMT (Numeryczny Model Terenu)
- ✅ **Parser godeł** - Obsługa układów PL-1992 (1:1M - 1:10k) i PL-2000 (1:10k - 1:500)
- ✅ **Bounding box** - Obliczanie współrzędnych arkusza (EPSG:2180, EPSG:4326)
- ✅ **Hierarchia arkuszy** - Automatyczne określanie arkuszy nadrzędnych i podrzędnych
- ✅ **Selekcja obszaru** - Godło, bbox, plik geometrii (SHP/GPKG)
- ✅ **Pobieranie NMT** - Z retry logic i progress tracking
- ✅ **Organizacja plików** - Automatyczna struktura katalogów
  (`data/nmt/pl_1992_1m_evrf2007/`, `data/nmt/pl_1992_5m_evrf2007/`;
  pełny układ: [ARCHITECTURE.md](docs/ARCHITECTURE.md) sekcja 3)
- ✅ **Wycinek bbox** - `--target-crs` skleja arkusze i reprojektuje lokalnie
  (przypięta operacja) do jednego GeoTIFF; także z biblioteki
  (`download_pl_cutout`); arkusz bez danych GUGiK = nodata + lista w sidecarze
  (`extra.missing_sheets`); przy `EPSG:2180` wynik leży na siatce arkuszy
  (wartości 1:1; poza arkuszami 5 m o niezgodnej fazie siatki - znany błąd S5).
  Istniejący wycinek (ta sama nazwa = te same współrzędne żądania) jest
  pomijany bez sieci (`Skipped - already exists`); przebudowa: `--force`
  (pobiera ponownie także wszystkie arkusze) albo usunięcie pliku wycinka
  (arkusze z cache zostaną użyte ponownie). Nieudana przebudowa nie kasuje
  poprzedniego pliku. Przed pobraniem kontrola miejsca na dysku (dolne
  oszacowanie; brak miejsca = błąd przed siecią), `Info:` dla wycinka >= 1 GiB;
  twardego limitu rozmiaru nie ma
- ✅ **Formaty** - GeoTIFF, PNG, JPEG (WCS), ASC (OpenData)
- ⚠️ **Pobieranie przez bbox jako GeoTIFF (WCS)** - tylko 1m i tylko KRON86
  (endpoint EVRF2007 zwraca 404 od 2026-08); wysokości EVRF2007 z obszaru:
  CLI `--bbox` (arkusze OpenData) albo jeden GeoTIFF: `--target-crs` /
  `download_pl_cutout`
- ✅ **Rozdzielczości:**
  - `1m` (GRID1) - wysoka rozdzielczość, KRON86 i EVRF2007
  - `5m` (GRID5) - niższa rozdzielczość, tylko EVRF2007

### NMT Czechy (CUZK, od 0.7.0-dev)
- ✅ **DMR 5G** (2m, godło TM33 lub bbox) i **DMR 4G** (5m, godło SM5 lub bbox)
- ✅ **CLI** - `--country {pl,cz,auto}`; `auto` na pograniczu dzieli żądanie na osobne pliki PL i CZ
- ✅ **Układy** - natywnie S-JTSK/Bpv (EPSG:5514); opcjonalna reprojekcja lokalna `--target-crs` oraz `--vertical-crs EVRF2007`
- ⚠️ **Znane błędy** - reprojekcja przesuwa treść o 1-5 m (K2); obszar 2 m zbliżony do kwadratu większy niż ok. 5,5 × 5,5 km kończy się HTTP 500 (K6) - patrz [Znane problemy](#znane-problemy-070-dev)

### NMPT (Numeryczny Model Pokrycia Terenu)
- ✅ **Digital Surface Model** - Teren + obiekty powierzchniowe (drzewa, budynki)
- ✅ **Pobieranie przez godło** → ASC (OpenData)
- ✅ **Pobieranie przez bbox** → GeoTIFF (WCS) - z biblioteki (`download_bbox`); CLI `--bbox` pobiera arkusze OpenData
- ✅ **Rozdzielczość** - Tylko 1m, układy KRON86 i EVRF2007
- ✅ **Organizacja** - `data/nmpt/pl_1992_1m_evrf2007/`

### Ortofotomapa (Standard Resolution)
- ✅ **Zdjęcia lotnicze** - 25cm, format TIF
- ✅ **Pobieranie przez godło** → TIF (OpenData)
- ✅ **Pobieranie przez bbox** → GeoTIFF (WCS), także PNG i JPEG - z biblioteki (`download_bbox`); CLI `--bbox` pobiera arkusze OpenData
- ⚠️ **Znany błąd K5** - pobierany jest wariant CIR (podczerwień) zamiast RGB; w warstwie „Starsze” najstarsze zdjęcie (K4)
- ✅ **4 warstwy WMS** - 2026, 2025, 2024 + Starsze (roczniki 2018-2023 skonsolidowane)
- ✅ **Organizacja** - `data/orto/pl_1992/`

### LAZ (Chmury Punktów LIDAR)
- ⚠️ **Znany błąd K1 (krytyczny)** - discovery WFS zamienia osie, więc kafle pochodzą z innego miejsca (setki km od obszaru); nie używaj `--product laz` do czasu naprawy
- ✅ **Dane pomiarowe ALS** (.laz) z GUGiK przez WFS, selekcja obszarem (godło/bbox/geometria)
- ✅ **Filtry** - `--year`, `--min-density`; organizacja - `data/laz/pl_<układ>_<vcrs>/`
  (układ poziomy ustalany per kafel)

### Land Cover (Pokrycie Terenu)
- ✅ **BDOT10k** - Polska baza wektorowa (GUGiK), szczegółowość 1:10 000
  - 15 warstw: 12 pokrycia terenu (PT*) + 3 hydrograficzne (SW*)
  - Lasy, wody, zabudowa, tereny rolne, rzeki, kanały, rowy melioracyjne, itp.
  - Automatyczne scalanie warstw do jednego GeoPackage (z zachowaniem rtree index)
- ✅ **CORINE Land Cover** - Europejska klasyfikacja (Copernicus), 44 klasy
- ✅ **Metody selekcji** - TERYT (powiat), bbox, godło arkusza, plik geometrii (SHP/GPKG)
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
- ✅ **Statystyki pokrycia** dla każdej grupy HSG - `--stats` podaje powierzchnie
  w ha także dla rastrów w EPSG:4326 (pole liczone geodezyjnie na elipsoidzie,
  nie w stopniach kwadratowych)

Od 0.7.0 klasyfikacja tekstury używa **kanonicznych progów trójkąta USDA**
(skośne granice `silt + 1.5*clay`, `silt + 2*clay`), wspólnych dla wersji skalarnej
i tablicowej. Mapowanie tekstura → HSG jest świadomie łagodniejsze niż tabela TR-55:
`sandy_loam` = **B** (nie A), `clay_loam` i `silty_clay_loam` = **C** (nie D) -
to klasy przejściowe, których grupa zależy też od struktury gleby. Uzasadnienie
i wpływ na wynik: [ADR-025](docs/DECISIONS.md).

## Konfiguracja CLMS API (opcjonalne)

Aby pobierać dane CORINE jako **GeoTIFF z kodami klas** (zamiast podglądu PNG),
potrzebujesz konta w Copernicus Land Monitoring Service:

1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (JSON z polami `client_id`, `private_key`, `token_uri`,
   opcjonalnie `key_id` i `user_id`)
3. Ustaw je w zmiennej środowiskowej `CLMS_CREDENTIALS` - działa na każdym systemie:

```bash
export CLMS_CREDENTIALS='{
  "client_id": "...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "token_uri": "https://land.copernicus.eu/@@oauth2-token",
  "key_id": "...",
  "user_id": "..."
}'
```

Na macOS alternatywą (fallback, gdy zmiennej nie ma) jest Keychain:

```bash
security add-generic-password -a "$USER" -s "clms-token" -w '{ ... ten sam JSON ... }'
```

**Bezpieczeństwo:** Credentials czyta wyłącznie podproces Auth Proxy
(`python -m kartograf.auth.proxy`), który dziedziczy zmienne środowiskowe rodzica.
Główna aplikacja nigdy nie widzi kluczy prywatnych ani tokenu - proxy pobiera dane
samo, a token dostają wyłącznie hosty `*.copernicus.eu` i `*.eea.europa.eu`
(presigned link pobrania na innym hoście `https` jest forwardowany bez tokenu,
adres `http` odrzucany).

**Bez konfiguracji:** CORINE automatycznie pobiera podgląd PNG przez WMS
(sidecar dostaje wtedy `extra.fallback = "wms_png"`).

**Z poziomu biblioteki** można też podać credentials wprost:
`CorineProvider(clms_credentials={...})` (tryb bezpośredni, z pominięciem proxy).

## Dokumentacja

- [SCOPE.md](docs/SCOPE.md) - Zakres projektu (co JEST i czego NIE MA)
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Architektura, kontrakty danych, kanoniczny układ `data/`
- [PRD.md](docs/PRD.md) - Product Requirements Document
- [PROGRESS.md](docs/PROGRESS.md) - Status implementacji i checkpointy
- [CHANGELOG.md](docs/CHANGELOG.md) - Historia zmian
- [DECISIONS.md](docs/DECISIONS.md) - Rejestr decyzji architektonicznych (ADR)
- [DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md) - Standardy kodowania
- [IMPLEMENTATION_PROMPT.md](docs/IMPLEMENTATION_PROMPT.md) - Kontekst dla asystentow AI

## Wymagania

- Python 3.12+
- requests >= 2.31.0
- pyproj >= 3.6.0
- PyJWT[crypto] >= 2.8.0
- rasterio >= 1.3.0
- numpy >= 1.24.0
- pyshp >= 2.3.0

## Struktura Projektu

```
Kartograf/
├── kartograf/           # Kod źródłowy
│   ├── auth/            # Auth Proxy (bezpieczna autentykacja CLMS)
│   ├── cache/           # Cache metadanych (SQLite)
│   ├── core/            # Parsery godeł (PL-1992/PL-2000/TM33), BBox, geometria (SHP/GPKG)
│   ├── sources/         # Deskryptory źródeł danych + sidecar metadanych
│   ├── transform/       # Transformacje CRS (crs.py) i rastrów (raster.py - warp_to_grid)
│   ├── transport/       # Wspólny transport HTTP + mozaikowanie rastrów
│   ├── providers/       # Providery danych (pl/: GUGiK, BDOT10k; cuzk/: DMR CZ; CORINE, SoilGrids)
│   ├── download/        # Download management (NMT/NMPT/Orto/LAZ) + wycinek PL (cutout.py)
│   ├── landcover/       # Land Cover management
│   ├── hydrology/       # Hydrologic Soil Groups (HSG)
│   └── cli/             # CLI interface (moduły per komenda)
├── tests/               # Testy (1861 offline + 8 live)
├── docs/                # Dokumentacja (ARCHITECTURE.md - kanoniczny opis architektury i układu data/)
└── README.md
```

## Dla Deweloperów

### Środowisko

```bash
# Aktywuj .venv
source .venv/bin/activate

# Zależności deweloperskie (pytest, pytest-cov, ruff, mypy)
pip install -e ".[dev]"

# Przeczytaj dokumentację przed rozpoczęciem
cat CLAUDE.md
```

### Testy

```bash
# Uruchom testy (offline)
pytest tests/ -m "not live"

# Z pokryciem kodu
pytest tests/ -m "not live" --cov=kartograf --cov-report=html

# Testy sieciowe (live)
pytest tests/ -m live   # 8 testów sieciowych (WMS GUGiK) - tylko świadomie

# Formatowanie
ruff format kartograf/ tests/

# Linting
ruff check kartograf/ tests/
```

## Licencja

Projekt udostępniony na licencji MIT. Szczegóły w pliku `LICENSE`.

## Autor

[Piotr de Bever](https://www.linkedin.com/in/piotr-de-bever/)

## Status

**Wersja 0.7.0-dev** - NMT Czechy (CUZK DMR 5G/4G, `--country {pl,cz,auto}`, parser godeł TM33/SM5, sidecary metadanych `.meta.json`), układ `data/` per produkt ([ADR-026](docs/DECISIONS.md)) i `--target-crs` dla Polski w trybie `--bbox`/`--geometry` ([ADR-027](docs/DECISIONS.md)) - także jako API biblioteki `download_pl_cutout`. Wcześniej: v0.6.x (LAZ przez WFS, pobieranie równoległe `--workers`, cache metadanych SQLite, walidacja warstw WMS), v0.5.0 (PL-2000, 15 warstw BDOT10k). 1861 testów offline (+8 `live` z siecią), pokrycie 92,9%. Przed wydaniem 0.7.0: decyzja o naprawie znanych błędów z testów na żywo (patrz [Znane problemy](#znane-problemy-070-dev)). Zobacz [CHANGELOG.md](docs/CHANGELOG.md) dla szczegółów.
