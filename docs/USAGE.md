# Przewodnik użytkownika — Kartograf

Jak używać Kartografu z wiersza poleceń i jako biblioteki Python. Dokument
opisuje zachowanie widoczne dla użytkownika; szczegóły techniczne i
kontrakty leżą w dokumentach kanonicznych, do których sekcje odsyłają:
zakres i ograniczenia — [SCOPE.md](SCOPE.md), architektura, układ `data/`
i schemat sidecara — [ARCHITECTURE.md](ARCHITECTURE.md), uzasadnienia —
[DECISIONS.md](DECISIONS.md). Pełna lista opcji CLI: `kartograf <komenda> --help`;
lista publicznego API: `kartograf/__init__.py` (`__all__`).

## Spis treści

1. [CLI](#1-cli)
   - [1.1 NMT, NMPT, ortofotomapa, LAZ (Polska)](#11-nmt-nmpt-ortofotomapa-laz-polska)
   - [1.2 Selekcja obszaru i wybór kraju (`--country`)](#12-selekcja-obszaru-i-wybór-kraju---country)
   - [1.3 Jeden scalony GeoTIFF (`--target-crs`)](#13-jeden-scalony-geotiff---target-crs)
   - [1.4 Czechy (CUZK)](#14-czechy-cuzk)
   - [1.5 Pokrycie terenu, gleby, HSG, cache](#15-pokrycie-terenu-gleby-hsg-cache)
   - [1.6 Kiedy `--scale` jest wymagane](#16-kiedy---scale-jest-wymagane)
2. [Biblioteka Python](#2-biblioteka-python)
3. [Wynik pobrania](#3-wynik-pobrania)
4. [Kampanie GUGiK](#4-kampanie-gugik)
5. [Gleby i HSG](#5-gleby-i-hsg)
6. [Konfiguracja CLMS API (CORINE GeoTIFF)](#6-konfiguracja-clms-api-corine-geotiff)
7. [Znane problemy i ograniczenia](#7-znane-problemy-i-ograniczenia)

Od 0.8.0 CLI nie ma wartości domyślnych wpływających na dane: `--product`,
`--output` (także `landcover download` i `soilgrids hsg`), `--country`
(z `--bbox`/`--geometry`), `--vertical-crs` (NMT, NMPT, LAZ),
`--resolution` (NMT, gdy jest wybór), `--system` (PL `--bbox`/`--geometry`)
i `--scale` (PL-2000) podaje się jawnie. Brak wartości to `Error:` z listą
dopuszczalnych wartości (kod 1, przed siecią); listy i znaczenia wartości
podaje też `kartograf <komenda> --help`. Domyślne zostały tylko format,
układ `--bbox-crs EPSG:2180`, przełączniki i parametry techniczne
(`--workers`).

---

## 1. CLI

### 1.1 NMT, NMPT, ortofotomapa, LAZ (Polska)

```bash
# Informacje o godle (auto-detekcja PL-1992 / PL-2000); --hierarchy pokazuje hierarchię
kartograf parse N-34-130-D-d-2-4
kartograf parse N-34-130-D --hierarchy

# NMT: pojedynczy arkusz albo hierarchia, opcjonalnie 5m; godło PL-1992 grubsze
# niż 1:10000 rozwija się do arkuszy 1:10000 samo — bez --scale (sekcja 1.6)
kartograf download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-130-D --resolution 5m --workers 8 --output ./data --product nmt --vertical-crs EVRF2007
# NMT 5 m istnieje tylko w EVRF2007: --resolution 5m z --vertical-crs KRON86
# kończy się Error: (kod 1, przed siecią) — użyj --vertical-crs EVRF2007
# albo --resolution 1m dla KRON86

# Inne produkty GUGiK: NMPT (DSM), ortofotomapa, chmury punktów LAZ
kartograf download --sheet N-34-130-D-d-2-4 --product nmpt --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --product orto -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --product laz --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12 --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86 --country pl -o ./data

# PL-2000: godło albo bbox w CRS strefy; godło grubsze i bbox wymagają --scale
# zgodnej z arkuszami GUGiK (sekcja 1.6)
kartograf parse 6.179.12.20
kartograf download --sheet 6.179.12.20 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf download --sheet 7.171.21 --scale 1:2000 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 -o ./data

# Kampanie GUGiK (sekcja 4): domyślnie najnowsza; `--all-campaigns`
# pobiera wszystkie kampanie arkusza
kartograf download --sheet N-34-130-D-d-2-4 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf download --sheet N-34-139-C-a-3-1 --full-sheet --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # + najnowszy pełny lot w full_sheet/ (sekcja 4.2)
kartograf download --sheet N-34-130-D-d-2-4 --product laz --all-campaigns --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --product laz --all-campaigns --country pl --vertical-crs EVRF2007 -o ./data

# Wybór roku danych (NMT, NMPT, orto, LAZ; sekcja 4.1)
kartograf download --sheet N-34-130-D-d-2-4 --year 2025 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # najnowszy lot z 2025
kartograf download --sheet N-34-130-D-d-2-4 --year 2025 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # wszystkie loty z 2025
kartograf download --sheet N-34-130-D-d-2-4 --product orto --year 2024 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --max-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --min-year 2023 --max-year 2024 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --sheet N-34-130-D-d-2-4 --min-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # najnowsza, nie starsza niż 2024
kartograf download --bbox 530000,382000,533000,386000 --all-campaigns --min-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
```

Pełna lista komend i opcji: `kartograf --help`, `kartograf <komenda> --help`.

LAZ: domyślnie pobierany jest najnowszy kafel dla każdego fragmentu obszaru;
starsze kafle pokryte przez nowsze są pomijane z komunikatem `Info:`
([ADR-029](DECISIONS.md), szczegóły: SCOPE 2.5 i ARCHITECTURE 4.7 "Wybór
kafli"); `--year`/`--min-year`/`--max-year` zawężają wybór do przedziału lat
(sekcja 4.1; rocznik spoza usługi = błąd z listą dostępnych). WFS GUGiK
w EPSG:2180 używa kolejności osi (N,E).
`--min-density` i `extra.nominal_density` to gęstość **nominalna** z WFS
GUGiK — faktyczna bywa wyższa.

`--min-density` działa **tylko z `--product laz`**. Z `nmt`, `nmpt` i `orto`
kończy się `Error:` i kodem 1 przed jakimkolwiek
zapytaniem do sieci (do 0.7.0 był po cichu pomijany). `--year`, `--min-year`
i `--max-year` działają dla NMT, NMPT, orto i LAZ (od 0.7.2; wcześniej
`--year` poza LAZ kończył się `Error:`) — tylko PL, bez `--target-crs`
(sekcja 4.1).

### 1.2 Selekcja obszaru i wybór kraju (`--country`)

```bash
kartograf download --bbox 771000,509000,772000,510000 --product orto --country pl --system 1992 -o ./data
kartograf download --geometry area.shp --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --geometry zlewnia.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --country pl --product nmt --resolution 1m --vertical-crs EVRF2007 --system 1992 -o ./data
```

- Domyślne `--bbox-crs` to `EPSG:2180`; plik geometrii: SHP albo GPKG.
  `--layer` wybiera warstwę GPKG. Bez tej flagi GPKG z wieloma warstwami
  używa pierwszej; CLI wypisuje jeden `Info:` z wybraną warstwą, listą
  pozostałych i podpowiedzią `--layer NAZWA` (również przy `-q`).
  Dotyczy też `landcover download` i `soilgrids hsg`; biblioteka przy
  domyślnym wyborze z wielu warstw emituje `logger.warning` przy każdym
  rozstrzygnięciu — podaj `layer=`, aby wskazać warstwę jawnie.
- PL bez `--target-crs` zapisuje **listę arkuszy** w hierarchii godeł;
  arkusz bez danych GUGiK jest pomijany z `Warning:` (kod 0, gdy pobrano
  choć jeden arkusz).
- `--country` jest wymagane z `--bbox`/`--geometry` (`pl`, `cz` albo
  `auto`; z `--sheet` kraj wynika z godła). Pod `auto` kraje są
  rozpoznawane po **prostokątnych** obwiedniach, nie po granicy: obszar
  przecinający obwiednię CZ (na zachód od 18,86°E i na południe od
  51,06°N) trafia także do CUZK, a prostokąt PL (14,07–24,20°E,
  49,00–54,90°N) obejmuje większość Czech. Dla czystej Polski użyj
  `--country pl`.
- Wartości bez odpowiednika czeskiego (`--product nmpt|orto`,
  `--vertical-crs KRON86`, `--resolution 1m` — w zwykłej, nie per-krajowej
  postaci) na obszarze objętym obwiedniami obu krajów same przełączają
  `auto` na PL (komunikat `Info:`). W Pradze czy Brnie taka flaga kieruje
  więc zadanie do GUGiK, który nie ma tam danych (błąd pobrania); błąd
  przed siecią dostaje dopiero obszar poza prostokątem PL. LAZ na
  obszarze sięgającym CZ wymaga jawnego `--country pl`. `--system` jest
  wymagane dla części PL zadania, więc nie wybiera kraju.
- Pod `auto` przycięcie do obwiedni kraju jest komunikowane jako `Info:`;
  oryginalny bbox zachowuje `extra.parent_request`, cały bbox pobiera
  `--country pl`.
- Pełne reguły (przycinanie, kody wyjścia, częściowy sukces): SCOPE 3.2,
  ARCHITECTURE 4.6, ADR-023.

### 1.3 Jeden scalony GeoTIFF (`--target-crs`)

```bash
# NMT 1 m, wycinek WCS w układzie źródłowym lub po lokalnej reprojekcji
kartograf download --bbox 530000,382000,533000,386000 --country pl --product nmt --target-crs EPSG:2180 --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 530000,382000,533000,386000 --country pl --product nmt --target-crs EPSG:5514 --vertical-crs EVRF2007 -o ./data
# NMPT 1 m, oba układy wysokościowe (tu KRON86)
kartograf download --bbox 530000,382000,533000,386000 --country pl --product nmpt --vertical-crs KRON86 --target-crs EPSG:2180 -o ./data
# pogranicze: osobne wycinki PL + CZ, ten sam układ i parent_request
# (wycinek PL ma tylko 1 m, część CZ wymaga 2m albo 5m — wartości per kraj)
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --target-crs EPSG:2180 --product nmt --resolution pl=1m,cz=2m --vertical-crs EVRF2007 -o ./data
# NMT 5 m: arkusze OpenData, bez --target-crs
kartograf download --bbox 530000,382000,533000,386000 --country pl --product nmt --resolution 5m --vertical-crs EVRF2007 --system 1992 -o ./data
```

- PL: WCS GUGiK daje wysokości NMT/NMPT 1 m w jednym GeoTIFF
  `<segment>/bbox/<współrzędne>.tif`. Przed zapytaniem
  WCS pobierana jest maska lądu PRG (`A00 - W02 - W03`): morze
  i obszar poza Polską to nodata `-9999`, **0,0 na lądzie zostaje
  danymi**. Wynik w całości nodata daje `Warning:` i kod 0. Na
  wybrzeżu (pomiar 2026-10-11: Gdynia, Hel, Mierzeja Wiślana) poza
  maską zostaje woda o wysokości WCS ok. 0–0,3 m; linia PRG nie odcina
  lądu wyższego niż 5 m, ale wąski pas brzegu i nabrzeży (do ok. 2 m)
  może trafić w nodata, a niska plaża po stronie lądu zostaje.
- Zakres jest rozszerzany na zewnątrz do siatki arkuszy 1 m
  EPSG:2180 (krawędzie `k + 0,5` m), potem dla innych CRS
  lokalnie reprojektowany przypiętą operacją. WCS pokazuje
  kompozycję serwera (najnowszy lot obszaru bez wypełniania
  starszymi); wycinek może pokazywać inny lot niż pobrane
  arkusze dokładnie 1 m. Nad lotem 0,5 m wynik 1 m to
  decymacja, nie uśrednienie.
- Wynik to dowiązanie `<segment>/bbox/<współrzędne>.tif` (bez daty) do
  wersji w `<segment>/versions/bbox/<RRRR-MM-DD>_<sha8>/`. Domyślnie
  i z `--upgrade` istniejąca wersja jest używana bez zapytań PRG i WCS
  (linia `... lokalna wersja ... (bez sprawdzania; --check-updates)`);
  `--force` pobiera ponownie — ta sama treść to „bez zmian” (wycinki są
  bajtowo powtarzalne, pomiar 2026-10-12), inna to nowa wersja obok
  starej. Nieudane pobranie nie rusza poprzedniej wersji ani dowiązania.
  Pliki `<współrzędne>_<RRRRMMDD>.tif` z 0.7.x nie są rozpoznawane (usuń
  je ręcznie). `--workers` i `--scale` nie zmieniają wycinka WCS.
  `Info:` podaje liczbę żądań przy więcej niż jednym kawałku lub wyniku
  >= 1 GiB (tylko gdy wycinek będzie pobierany).
- Wycinki 5 m, wybór roku (`--year`, `--min-year`, `--max-year`),
  `--all-campaigns` i `--full-sheet` z `--target-crs` są
  odrzucane (`Error:`). Podobnie `--target-crs` dla orto/LAZ;
  arkusze 5 m pobieraj bez `--target-crs`. Szczegóły:
  [ADR-035](DECISIONS.md), ARCHITECTURE 4.3.

### 1.4 Czechy (CUZK)

```bash
# DMR 5G (2 m), godło TM33 (ten kafel leży w większości w Niemczech — głównie nodata)
kartograf download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv -o ./data
kartograf download --sheet CTES96 --product nmt --vertical-crs Bpv -o ./data # DMR 4G (5 m), godło SM5, kraj z godła
kartograf download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m -o ./data # Bpv -> EVRF2007 (EPSG:5621)
# reprojekcja CZ (tylko --bbox/--geometry, nie godło), lokalnie przypiętą operacją
kartograf download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv -o ./data
# pogranicze pod auto: osobne pliki PL i CZ, wspólny extra.parent_request;
# różne wartości dla krajów w postaci pl=...,cz=...
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv --system 1992 -o ./data
# bboxy w EPSG:5514 są na terytorium CZ ujemne — podaj je jako --bbox=... (bez spacji),
# inaczej argparse odczyta wartość jako nieznaną flagę
kartograf download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --resolution 5m --product nmt --vertical-crs Bpv -o ./data
```

`kartograf parse` obsługuje tylko godła PL (PL-1992/PL-2000); godła CZ
(TM33, SM5) przyjmuje `kartograf download`.

**Wartości per kraj.** `--resolution` i `--vertical-crs` przyjmują jedną
wartość dla każdego kraju zadania (`--resolution 5m`) albo pary
`kraj=wartość` (`--resolution pl=1m,cz=2m`, `--vertical-crs
pl=EVRF2007,cz=Bpv`). Jedna wartość musi być dostępna w każdym kraju
zadania (wspólne: `5m`, `EVRF2007`); inaczej `Error:` przed siecią
z podpowiedzią formy per kraj. Klucz kraju spoza zadania nie jest
błędem. Zwykłe `--resolution 1m` albo `--vertical-crs KRON86` pod `auto`
wskazują PL (`Info: --country auto -> pl`), bo CZ ich nie ma.
Prostokątne obwiednie krajów mogą uruchomić CZ także dla obszaru
w Polsce (część CZ bywa wtedy w całości nodata).

- Rozdzielczość CZ: arkusz SM5 (np. `CTES96`) to gotowy plik DMR 4G,
  który istnieje tylko w 5 m — `--resolution` można pominąć, a inne niż
  `5m` jest błędem (`Error:`, kod 1, bez sieci). Kafel TM33
  i `--bbox`/`--geometry` są wycinane z usługi: `--resolution` wymagane,
  `2m` (DMR 5G) albo `5m` (DMR 4G).

- CZ `--bbox` zawsze daje jeden plik (wycinek), PL bez `--target-crs`
  listę arkuszy.
- Porażka jednego kraju pod `auto` (brak danych albo awaria źródła) przy
  sukcesie drugiego kończy się kodem 0 i `Warning:` na stderr; kod 1, gdy
  żaden kraj nie dał wyniku albo `--country` było jawne.
- Natywnie S-JTSK/Bpv (EPSG:5514); `KRON86` dla CZ jest nieosiągalny.
  Szczegóły: SCOPE 2.2 i 3.2, ARCHITECTURE 4.4–4.6.
- Magazyn wersji (0.8.0): arkusz CZ i wycinek CZ leżą jako wersje
  w `<segment>/versions/`, ścieżka arkusza i `bbox/<współrzędne>.tif` to
  hardlinki. Arkusz SM5 ma tani sygnał (`ETag`/`Last-Modified` pliku
  `openzu`, zapisany w `extra.http` sidecara wersji): domyślnie jedno
  `HEAD` na plik z lokalną wersją — nowsza treść daje dopisek `; dostępna
  nowsza ... (--upgrade)`, a `--upgrade` ją pobiera; nieudane `HEAD` to
  `Warning:` i lokalna wersja (z `--upgrade` — błąd). Kafel TM33 i wycinek
  CZ (`exportImage`) nie mają taniego sygnału: lokalna wersja bez
  sieci, ponowne pobranie tylko `--force`.

### 1.5 Pokrycie terenu, gleby, HSG, cache

```bash
kartograf landcover download --source bdot10k --teryt 1465 -o ./data
#   landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: nowa wersja 2026-10-12_f3550257
kartograf landcover download --source bdot10k --teryt 1465 --format SHP -o ./data
#   landcover/pl_bdot10k_shp/teryt/1465.zip: nowa wersja ...  (archiwum .zip)
# Obszar z dwóch powiatów (TERYT z WFS PRG): pakiet KAŻDEGO powiatu, osobny plik
kartograf landcover download --source bdot10k --bbox 626000,480000,628000,482000 -o ./data
#   landcover/pl_bdot10k_gpkg/teryt/1421.gpkg: nowa wersja 2026-10-12_38da4056
#   landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: lokalna wersja 2026-10-12 (bez sprawdzania; --check-updates)
#   Nowe: 1, nowa etykieta: 0, bez zmian: 0, lokalne: 1, bledy: 0 (./data)
#   (ścieżka zawsze teryt/<TERYT> — pakiet to cały powiat; obszar żądania
#    w sidecarze extra.parent_request; to samo dla --sheet i --geometry)
kartograf landcover download --source corine --year 2018 --sheet N-34-130-D -o ./data
#   z CLMS_CREDENTIALS: landcover/eu_corine_2018/N-34/130/D/N-34-130-D.tif: nowa wersja V2020_20u1_<sha8>
#   bez: Info: CORINE 2018: podglad WMS ...
#        landcover/eu_corine_2018_preview/N-34/130/D/N-34-130-D.png: nowa wersja 2026-10-12_<sha8>
kartograf landcover download --source soilgrids --bbox 626000,480000,628000,482000 --property clay --depth 0-5cm --stat mean -o ./data
#   soil/global_soilgrids_clay_0-5cm_mean/bbox/626000_480000_628000_482000.tif: nowa wersja 2.0_717f0989
# Segment niesie każdy parametr treści (lowercase), więc --property sand
# dla tego samego obszaru to osobny plik; parametry są też w sidecarze
# (request.property/depth/stat, request.year, request.format).

# Hydrologic Soil Groups dla metody SCS-CN (wejścia clay/sand/silt w tym samym magazynie)
kartograf soilgrids hsg --bbox 626000,480000,628000,482000 --depth 0-5cm --stats -o ./data
#   soil/global_soilgrids_{clay,sand,silt}_0-5cm_mean/bbox/...: nowa wersja 2.0_<sha8>
#   hsg/global_soilgrids_0-5cm_mean/bbox/626000_480000_628000_482000.tif: nowa wersja 2.0_470ef3d9
# Ponownie (także z --force, gdy treść wejść się nie zmieniła): ... uzyta ponownie 2.0

# Przegląd źródeł/warstw i cache metadanych
kartograf landcover list-sources
kartograf landcover list-layers --source soilgrids
kartograf cache stats
kartograf cache clear
kartograf cache path
```

`--output` to katalog magazynu (wersje w `versions/`, ścieżka standardowa
= hardlink; ARCHITECTURE 3.3 reguła 8); `soilgrids hsg -o plik.tif` to
`Error:` (plik poza magazynem: `hsg_from_rasters`). `--teryt` dotyczy tylko
BDOT10k (CORINE/SoilGrids: `--sheet`, `--bbox`, `--geometry`). BDOT10k
z `--bbox`/`--sheet`/`--geometry` pobiera wszystkie powiaty obszaru (lista
z WFS PRG, odpowiedzi w cache metadanych — `cache stats` liczy je
w `TERYT entries`); błąd jednego powiatu to `Error: <TERYT>: ...`, reszta
się pobiera, kod 1; obszar bez powiatu (morze) to `Error:`. Tryby
`--check-updates`/`--upgrade`/`--force`/`--plan`: sekcja 4.3. CORINE bez
credentials CLMS pobiera podgląd PNG (sekcja 6). Warstwy BDOT10k,
parametry SoilGrids i lata CORINE: PRD 3.5–3.7.

### 1.6 Kiedy `--scale` jest wymagane

`--scale` to skala **docelowa** arkuszy PL-2000, które Kartograf zamawia
u GUGiK (NMT, NMPT, ortofotomapa). Musi odpowiadać skali arkuszy, w jakich
GUGiK publikuje dany produkt — Kartograf pobiera plik arkusza o dokładnie
tym godle (cały token), więc arkusz w innej skali nie zostanie dopasowany.
Wartości: `1:5000`, `1:2000`, `1:1000`, `1:500`. Od 0.8.0 nie ma wartości
domyślnej.

**Kiedy:**

- `--bbox`/`--geometry` z `--system 2000` (bez `--target-crs`): wymagane —
  obszar jest rozbijany na arkusze w tej skali;
- `--sheet` z godłem PL-2000 1:10000 (np. `7.171.21`): wymagane — godło
  jest rozwijane do potomków w tej skali (`kartograf parse <godło>
  --descendants <skala>` pokazuje listę przed pobraniem);
- drobniejsze godło PL-2000 (np. `7.171.21.23`): opcjonalne — bez flagi
  pobierany jest ten arkusz, z flagą jego potomkowie w tej skali;
- nie dotyczy LAZ (kafle wybierane z WFS), CZ (godło TM33/SM5 albo
  wycinek z usługi) ani wycinka `--target-crs`.

**PL-1992 — flaga niedozwolona.** GUGiK publikuje arkusze PL-1992 tylko
z 7-członowym godłem (np. `N-34-130-D-d-2-4`), oznaczanym w Kartografie
jako `1:10000`; grubsze godło (np. `N-34-130-D`) i `--bbox`/`--geometry`
z `--system 1992` zawsze dają te arkusze, a `--scale` z zadaniem PL-1992
kończy się `Error:` (kod 1, przed siecią). Uwaga na nazewnictwo: etykiety
skal Kartografu są o jeden poziom drobniejsze niż nomenklatura GUGiK — ten
sam 7-członowy arkusz skorowidz GUGiK opisuje jako moduł archiwizacji
1:5000 (`modulArchiwizacji`).

**PL-2000 — skala publikacji.** Kartograf zaczyna podział PL-2000 od
arkusza 1:10000 (`strefa.pas.słup`, np. `7.171.21`), a GUGiK publikuje
arkusze PL-2000 w drobniejszych modułach. W zapisanych odpowiedziach
skorowidza NMT 1 m i ortofotomapy, na których opierają się testy
Kartografu, arkusze PL-2000 mają najczęściej moduł 1:2000 (np.
`7.171.21.23`, `5.167.25.13`), a obok nich występują też arkusze 1:1000
i 1:5000; arkusza PL-2000 1:10000 nie było w nich wcale. Zwykle więc
`--scale 1:2000`:

```bash
kartograf download --sheet 7.171.21 --scale 1:2000 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 -o ./data
```

**Co się dzieje przy niedopasowaniu.** Brak arkusza o zamówionym godle to
brak pokrycia (`NoCoverageError`), nigdy ciche pobranie zastępcze (np.
arkusza PL-1992). Skorowidz zwraca jednak arkusze z miejsca zapytania
(np. potomka zamówionego godła), więc Kartograf podpowiada skalę, w której
dane tam są:

- pojedyncze godło: `Error:` (kod 1), a w treści błędu np.
  `Dostepny potomek 5.167.25.13 — uzyj --scale 1:2000`;
- lista arkuszy (`--bbox`/`--geometry`, godło rozwijane): arkusze bez
  danych mają status `no_coverage` (`∅`), na stderr `Warning: GUGiK nie ma
  danych dla N z M arkuszy ...` (kod 0, gdy pobrano choć jeden arkusz)
  albo — gdy żaden arkusz nie ma danych — `Error: GUGiK nie ma danych dla
  zadnego z M arkuszy obszaru` (kod 1); w obu przypadkach pod spodem
  podpowiedzi `Info: Dostepny potomek <godło> — uzyj --scale <skala>`;
- gdy skorowidz ma ten obszar w drugim układzie, podpowiedź wskazuje jego
  godło albo `--system <układ> --scale <skala>`;
- NMT i NMPT (od 0.7.2): gdy arkusza nie ma w wybranej rozdzielczości albo
  układzie wysokości, a skorowidz GUGiK ma go w innym wariancie, podpowiedź
  to np. `Skorowidz GUGiK ma ten arkusz w NMT 1m EVRF2007 — uzyj
  --resolution 1m` (albo `--vertical-crs KRON86`) — przy pojedynczym
  godle w treści `Error:` (kod 1), przy liście arkuszy jako `Info:`.
  GUGiK ma duże braki pokrycia EVRF2007, także NMT 5 m (np.
  `N-34-130-D-d --resolution 5m`: 6 z 16 arkuszy tylko w 1 m).
  Sprawdzenie kosztuje jedno zapytanie
  skorowidza na wariant i brakujący arkusz; wynik trafia do cache
  metadanych razem z brakiem pokrycia.

**Jak ustalić właściwą skalę.** Najprościej z podpowiedzi CLI: skala
w `uzyj --scale ...` to skala arkusza, który GUGiK faktycznie opublikował
(może to być 1:2000, ale też np. 1:1000). Skalę godła i jego potomków
pokazuje `kartograf parse` (`--descendants <skala>`). Jeśli różne miejsca
obszaru mają arkusze w różnych skalach, jedno wywołanie z jedną `--scale`
pobierze tylko część — pozostałe arkusze dociągnij kolejnym wywołaniem
z podpowiedzianą skalą.

---

## 2. Biblioteka Python

```python
from pathlib import Path
from kartograf import SheetParser, DownloadManager, BBox, GugikProvider

# Parsowanie godła i bounding box arkusza
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)                      # "1:10000"
bbox = parser.get_bbox(crs="EPSG:2180")  # lub "EPSG:4326"

# Od 0.8.0 każdy wybór danych jest jawny: katalog, provider (produkt),
# układ wysokości i rozdzielczość (TypeError, gdy brak)
# Pobieranie przez godło -> ASC (OpenData); hierarchia: download_hierarchy()
provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
manager = DownloadManager("./data", provider)
result = manager.download_sheet("N-34-130-D-d-2-4")
path = result.files["N-34-130-D-d-2-4"][0].version_path
# NMT 5 m tylko w EVRF2007: GugikProvider(resolution="5m", vertical_crs="KRON86")
# -> ValueError (create_nmt_provider: ValidationError)

# Surowy WCS poza magazynem (np. ortofotomapa albo NMT KRON86 jako TIFF):
# provider.download_bbox(bbox, path) — jednopasmowy float32 GeoTIFF na
# siatce 1 m EPSG:2180, bez maski PRG i bez wersji. Wycinek NMT/NMPT
# w magazynie wersji: download_pl_cutout (niżej).
area = BBox(min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180")
kron = GugikProvider(vertical_crs="KRON86", resolution="1m")
path = kron.download_bbox(area, Path("my_area.tif"))

# Land Cover: BDOT10k / CORINE / SoilGrids do magazynu (output_dir = --output)
from kartograf import LandCoverManager
lc = LandCoverManager("./data", "bdot10k")
result = lc.download(teryt="1465")         # BDOT10k (powiat)
print(result.file.path, result.file.status)  # data/landcover/pl_bdot10k_gpkg/teryt/1465.gpkg new
# BDOT10k z KAŻDEGO powiatu obszaru (bbox w dowolnym układzie, albo sheet=),
# tylko wybrane warstwy -> landcover/pl_bdot10k_gpkg_ptwp-swkn-swrm-swrs/teryt/<T>.gpkg;
# keep_raw=True: oryginalny ZIP GUGiK jako osobna wersja
# (landcover/pl_bdot10k_gpkg_zip/teryt/<T>.zip, pełny pakiet; tylko GPKG)
area = lc.download_all_counties(
    bbox=BBox(340000, 290000, 350000, 300000, "EPSG:2180"),
    layers=["SWRS", "SWKN", "SWRM", "PTWP"],
    keep_raw=True,
)
paths = [r.file.path for r in area.files]  # area.failed: powiaty z błędem
# lc.download(bbox=...) dla BDOT10k: jeden powiat albo ValidationError z listą
# kodów (kilka powiatów) / NoCoverageError (żaden)
lc.set_provider("corine")
lc.download(sheet="N-34-130-D", year=2018)  # CORINE (CLMS albo podgląd _preview)
lc.set_provider("soilgrids")
plan = lc.check(sheet="N-34-130-D", property="clay", depth="0-5cm", stat="mean")
lc.download(sheet="N-34-130-D", property="clay", depth="0-5cm", stat="mean",
            update="upgrade", plan=plan)    # tylko pozycje planu

# Hydrologic Soil Groups (wejścia = wersje SoilGrids w tym samym magazynie)
from kartograf import HSGCalculator
calc = HSGCalculator("./data")
hsg = calc.calculate_hsg_by_sheet("N-34-130-D", depth="0-5cm", stat="mean")
print(hsg.file.status, hsg.file.label)      # new 2.0 (ponownie: reused 2.0)
stats = calc.get_hsg_statistics(hsg.file.path)

# HSG z gotowych rastrow clay/sand/silt (g/kg) na jawnej siatce - bez pobierania
from kartograf import BBox, hsg_from_rasters
hsg_from_rasters(
    Path("clay.tif"), Path("sand.tif"), Path("silt.tif"),
    bbox=BBox(501000, 596000, 503000, 598000, "EPSG:2180"),
    crs="EPSG:2180", pixel_m=100.0, output_path=Path("./hsg_100m.tif"),
)

# Scalony wycinek WCS NMT lub NMPT PL (GeoTIFF + sidecar)
from kartograf import download_pl_cutout, prepare_pl_cutout, run_pl_wcs_cutout

bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
result = download_pl_cutout(
    bbox, "EPSG:5514", output_dir="./data", vertical_crs="EVRF2007", product="nmpt",
)
print(result.file.path, result.file.status, result.masked_pixels, result.all_nodata)
# domyślnie istniejąca wersja bez zapytań PRG/WCS; update="force" pobiera ponownie
# osobne kroki przy własnym providerze; maska PRG pobierana przed WCS
cutout = prepare_pl_cutout(
    bbox, "EPSG:2180", output_dir="./data", vertical_crs="EVRF2007", product="nmt"
)
result = run_pl_wcs_cutout(cutout)

# Zlewnia przygraniczna PL/CZ: podział obszaru na kraje i wycinek CZ
# w układzie PL (EPSG:2180 + EVRF2007); siatka CZ startuje od zadanego obszaru
from kartograf import download_cz_cutout, split_bbox_by_country

area = BBox(16.19, 50.42, 16.25, 50.45, "EPSG:4326")  # Kudowa-Zdrój / Náchod
parts = split_bbox_by_country(area, cz_crs="EPSG:2180")  # {"CZ": ..., "PL": ...}
cz = download_cz_cutout(
    parts["CZ"].bbox,
    output_dir="./data",
    target_crs="EPSG:2180",
    vertical_crs="EVRF2007",
    resolution="2m",          # "2m" DMR 5G / "5m" DMR 4G
)
print(cz.file.path)           # data/nmt/cz_dmr5g_evrf2007/bbox/<coords>.tif
# all_nodata=True: część CZ bez ani jednego ważnego piksela (prostokąt
# obwiedni CZ sięga w głąb Polski) — plik powstaje, flaga też w sidecarze
print(cz.all_nodata)
# Część PL (parts["PL"].bbox) pobierz przez download_pl_cutout (wyżej).
# Własny provider: run_cz_cutout(provider, bbox, output_dir=, image_crs=).

# Sprawdzenie bez pobierania (plan kartograf-plan/1) dla każdego toru:
from kartograf import check_cz_cutout, check_laz_updates, check_pl_cutout
plan = check_pl_cutout(cutout)          # status "unverifiable"/"missing"
print([(i.track, i.unit, i.status) for i in plan.items])
```

**Cache metadanych w bibliotece.** Bez `MetadataCache` provider NMT pyta
skorowidz GUGiK przy KAŻDYM `download_sheet`, także dla arkusza już
pobranego. Przekaż cache providerowi, a zapytania o arkusz ograniczą się do
raz na TTL cache (7 dni):

```python
from kartograf import DownloadManager, MetadataCache
from kartograf.providers.pl import create_nmt_provider

manager = DownloadManager(
    "./data",
    create_nmt_provider(
        vertical_crs="EVRF2007", resolution="1m", cache=MetadataCache(".kartograf_cache.db")
    ),  # albo GugikProvider(..., cache=...)
)
# Land cover: cache dla providera tworzonego po nazwie (BDOT10k: odpowiedzi PRG)
lc = LandCoverManager("./data", "bdot10k", cache=MetadataCache(".kartograf_cache.db"))
```

Pozostałe elementy publicznego API (m.in. `GugikNmptProvider`,
`GugikOrtoProvider`, `GugikLazProvider`/`download_laz_area` dla LAZ,
`CuzkDmrProvider`/`create_dmr_provider` dla Czech, `Parser2000`,
`ParserTM33`, `FileStorage`) — eksporty w `kartograf/__init__.py`, opis
w SCOPE 2.10 i PRD 5.

---

## 3. Wynik pobrania

**Wartosc zwracana.** `download_sheet`, `download_hierarchy` i
`download_sheets` zwracaja `DownloadResult`. Godlo PL-1992 grubsze niz
1:10000 rozwija sie na arkusze 1:10000 (`expand_sheets`); porazki
pojedynczych arkuszy listy i hierarchii nie przerywaja pozostalych.
`result.files[godlo]` zawiera krotke `VersionedFile`: `path` to sciezka
standardowa, `version_path` to plik wersji, `label` i `status` opisuja
wybrana wersje.

**Podsumowanie:** `succeeded`, `failed`, `skipped`, `no_coverage` (arkusze,
dla ktorych GUGiK nie ma danych; podzbior `failed`), `campaign_files`,
`reused_campaign_files`, statusy `new`/`relabeled`/`unchanged`/`local`,
`newer`, `unverified` i `no_coverage_hints`. `stale` zawiera nieaktualne
pozycje planu, `notices` komunikaty o danych przekazywane rowniez przez
`on_notice`. Pozostaja pola `better_coverage`, `link_outside_range`,
`full_links`, `full_link_outside_range` i `without_full` (sekcje 4.1 i 4.2).

- `PlCutoutResult` (wycinek WCS): `file` (`VersionedFile`),
  `masked_pixels`, `zero_pixels`, `all_nodata`, `stale`.
- `CzCutoutResult` (wycinek CZ, `download_cz_cutout`/`run_cz_cutout`):
  `file`, `all_nodata`, `stale`.
- `LazDownloadResult` (`download_laz_area`): `files` (`VersionedFile` na
  kafel), `failed`, `superseded` (kafle pominięte jako pokryte przez
  nowsze), `stale`.
- `VersionedFile`: `path` (ścieżka standardowa = hardlink), `status`
  (`new`/`unchanged`/`relabeled`/`local`), `label`, `sha256`,
  `version_path`, `newer` (źródło ma nowszą treść, tryb domyślny),
  `unverified` (`"none"` — brak taniego sygnału, `"check_failed: ..."`).
  `file` wyników jednoplikowych jest `None` tylko z `plan=`, gdy plan nie
  wykonuje tego pliku i nie ma wersji lokalnej.

**Sidecar.** Każde udane pobranie przez CLI albo warstwę zarządzającą
biblioteki (niżej) zapisuje dwa pliki: dane (`.asc`, `.tif`,
`.laz`, `.gpkg`, ...) i `<plik>.meta.json` (schemat `kartograf-meta/1`): układ
poziomy i pionowy pliku, nodata, żądanie, licencja, użyte transformacje,
pochodzenie (`extra.source`), a dla zadań obszarowych `extra.parent_request`
łączący pliki jednego zadania. Pełna tabela pól: ARCHITECTURE 3.2,
`parent_request`: ARCHITECTURE 3.4. Sidecary pisze warstwa zarządzająca
(`DownloadManager`, `LandCoverManager`, wycinki PL i CZ oraz kafle LAZ
i arkusze CZ w bibliotece), a `FileStorage.delete()` usuwa sidecar razem z plikiem danych.
Bezpośrednie wywołanie providera (np. `CuzkDmrProvider` z biblioteki) zapisuje
sam plik danych, bez sidecara.

**Gdzie leżą pliki.** `data/<produkt>/<kraj>_<układ>[_<wariant>][_<vcrs>]/...`
— kanoniczna tabela, przykłady i migracja z 0.6.x: ARCHITECTURE 3.3.

**Starsze pliki CZ.** Pliki, których sidecar w
`transform.horizontal` zawiera `S-JTSK to ETRS89 (3)`, nie są
przebudowywane automatycznie; przy pominięciu istniejącego pliku
CLI drukuje `Info:`, a ponowne pobranie wymusza `--force`.
Wycinki PL WCS nie są pomijane — każdy przebieg pobiera na nowo.

---

## 4. Kampanie GUGiK

GUGiK publikuje ten sam arkusz w kilku kampaniach (różne lata pozyskania).
Domyślnie (również z flagami roku) pobiera najnowszą kampanię;
`--all-campaigns` — każdą. Wybór roku (`--year`, `--min-year`,
`--max-year`) opisuje sekcja 4.1. Kampanie i rok dotyczą tylko PL — dla CZ
opcje dają `Error: CZ (CUZK) nie ma kampanii — ...` (zadanie wyłącznie
czeskie) albo `Info:` (obszar PL+CZ pod `auto`, CZ w bieżącej wersji).

Prawdziwe pliki NMT/NMPT/orto leżą jako **wersje** w
`data/<produkt>/<segment>/versions/<hierarchia godła>/<data>_<id>_<sha8>/<godło>.<ext>`
(`<data>` = data pozyskania, `<id>` = numer kampanii z nazwy pliku GUGiK,
`<sha8>` = początek sumy SHA-256 treści), a ścieżka standardowa
`data/<produkt>/<segment>/<hierarchia godła>/<godło>.<ext>` jest
dowiązaniem twardym do najnowszej lokalnej wersji
([ADR-036](DECISIONS.md)). Wersji nic nie nadpisuje: ponowne pobranie tej
samej treści to „bez zmian”, inna treść to nowa wersja obok starej.
Szczegóły trybów: sekcja 4.3.

- **Skorowidz niedostepny:** gdy skorowidz GUGiK nie odpowiada (siec, HTTP
  429/5xx), a arkusz ma juz lokalna wersje, tryb domyslny jej uzywa (kazda
  strategia) i drukuje ostrzezenie o lokalnej wersji bez sprawdzenia nowszej
  (kod bez zmian, takze z `-q`). Z flaga roku: gdy KAZDY arkusz zadania
  ma lokalna wersje z zakresu lat — lokalne wersje z ostrzezeniem,
  inaczej cale zadanie konczy sie bledem bez pobran. Bez lokalnej wersji,
  z `--upgrade` albo `--force` blad konczy pobranie porazka. Biblioteka:
  `DownloadResult.unverified` (tresc bledu transportu) i `notices` z kodem
  `UNVERIFIED_LOCAL`.
- **Wymagane hardlinki:** ścieżka standardowa to dowiązanie twarde do pliku
  wersji (ten sam plik na dysku, bez dodatkowego miejsca); Kartograf nie
  tworzy symlinków ani kopii. System plików bez hardlinków (exFAT/FAT,
  sshfs/FUSE) kończy pobranie arkusza błędem. Na udziale SMB montowanym
  bez `serverino` (niestabilne numery i-węzłów) dowiązanie jest
  potwierdzane sumą SHA-256 (jeden odczyt pliku przy każdym uruchomieniu).
- **Kopiowanie `data/`:** użyj `rsync -aH` albo `cp -a` — bez zachowania
  hardlinków ścieżka standardowa staje się osobną kopią (duplikat danych).
  Treść wersji jest nieskompresowana (suma SHA-256 z bajtów) — przy dużych
  zbiorach warto włączyć kompresję systemu plików.
- **Windows:** hardlink działa bez dodatkowych uprawnień (NTFS), a dane
  udostępnione przez SMB klient Windows widzi jako zwykłe pliki.
- **Migracja z 0.7.x:** brak; katalog `kampanie/` nie jest czytany (CLI
  raz drukuje `Info: katalog kampanie/ z wersji 0.7.x nie jest uzywany ...`),
  a potrzebne kampanie są pobierane ponownie do `versions/`; zwykły plik albo
  kopia w ścieżce standardowej jest zastępowana dowiązaniem.
- **Układ wysokości rekordu:** rekord skorowidza NMT/NMPT musi deklarować
  zadany układ (`ukladWspolrzednychPionowych`: `PL-KRON86-NH` dla KRON86,
  `PL-EVRF2007-NH` dla EVRF2007); inna wartość kończy kampanię błędem przed
  pobraniem pliku (arkusz: `Error:`/porażka wg listy, w `all` pozostałe
  kampanie są pobierane). Rekord bez tego pola jest przyjmowany.
- **Wycinek `--target-crs`** pochodzi z WCS GUGiK z kompozycją lotów
  serwera (nie z kampanii arkuszy, sekcja 1.3) i nie przyjmuje
  `--all-campaigns`, flag roku ani `--full-sheet`.
- **LAZ:** `--all-campaigns` pobiera wszystkie kafle, których rama przecina
  obszar (bez deduplikacji ADR-029). LAZ nie używa dowiązań.
  `--min-density` jest tylko dla LAZ (z innymi produktami: `Error:`,
  sekcja 1.1).
- Składanie kilku kampanii w jedną powierzchnię nie jest częścią
  Kartografu (plany: SCOPE 3.1).

Reguły szczegółowe: SCOPE 2.12, ARCHITECTURE 3.3 (reguły 6 i 7), ADR-030,
ADR-033.

### 4.1 Wybór roku danych (`--year`, `--min-year`, `--max-year`)

Rok danych to rok pozyskania: `aktualnosc` rekordu skorowidza (NMT, NMPT,
orto) albo `akt_rok` kafla LAZ — nie data przyjęcia do PZGiK. Granice są
domknięte; `--year RRRR` to skrót `--min-year RRRR --max-year RRRR`
([ADR-032](DECISIONS.md)).

- **Flagi roku wyznaczają tylko dopuszczalne lata, `--all-campaigns` — liczbę
  lotów na arkusz.** Domyślnie pobierany jest
  jeden, najnowszy lot z zakresu; `--all-campaigns` pobiera wszystkie loty
  z zakresu do `versions/`. Ta sama reguła dla każdej flagi roku i każdego
  produktu. Przykład (arkusz z lotami 2019, 2023, 2025-04, 2025-10):
  `--year 2025` = lot 2025-10; `--year 2025 --all-campaigns` = oba loty
  2025; `--max-year 2024` = lot 2023; `--min-year 2024` = lot 2025-10.
- **Ścieżka standardowa** wskazuje najnowszy lokalny lot i nigdy nie cofa się
  na starszy. Gdy wcześniej pobrano nowszy lot, a teraz zakres go wyklucza
  (np. `--max-year 2022`), wybrany lot trafia do `versions/`, dowiązanie
  zostaje przy nowszym, a CLI podaje `Info: N dowiazan wskazuje lokalny lot
  spoza tego zadania ...` z linią `<godło>: sciezka standardowa -> dowiazanie
  <data>_<id>` (to samo dla `full_sheet/`, sekcja 4.2).
- **Najpierw sprawdzenie, potem pobranie.** Gdy któryś arkusz ma dane tylko
  z innych lat, zadanie kończy się `Error:` i kodem 1 przed pobraniem
  czegokolwiek (także z pozostałych arkuszy):

  ```
  Error: brak danych z roku 2024 dla 2 z 4 arkuszy — nic nie pobrano:
    N-34-139-C-a-3-1: dostepne roczniki 2019, 2023, 2025
    N-34-139-C-a-3-3: dostepne roczniki 2019, 2025
  Podpowiedz: --min-year 2024 (rok 2024 i nowsze) albo --max-year 2024 (rok 2024 i starsze)
  ```

  Arkusz bez żadnych danych (morze, obszar za granicą) jest pomijany
  z `Warning:` jak dotąd. Awaria skorowidza przy sprawdzaniu przerywa całe
  zadanie (`Error: nie udalo sie sprawdzic roku danych ...`) — ponów pobranie.
- **Kilka lotów w przedziale (`--all-campaigns`):** każdy lot niepełny ma
  w sidecarze wersji pokrycie zmierzone przy zapisie (udział ważnych pikseli,
  `extra.coverage`); gdy najnowszy lot jest niepełny, a starszy ma większe
  pokrycie (lot pełny liczy się jako pokryty w całości), Kartograf drukuje
  `Info:` (stderr, także z `-q`) i zapisuje `extra.flights`
  i `extra.better_coverage` w sidecarze ścieżki standardowej. Dowiązanie
  nadal wskazuje najnowszy lot; starszy leży w `versions/`.
- **Sidecar:** `request.min_year`/`max_year` (gdy podane), `request.year`
  (gdy równe), `request.campaigns` (strategia faktycznie użyta),
  `extra.available_years` (wszystkie lata arkusza w skorowidzu).
- **LAZ:** wybór ADR-029 w obrębie przedziału. Kafel, który bez flag roku
  zostałby wybrany, a ma rok spoza przedziału, musi być pokryty kaflami
  z przedziału; inaczej `Error: brak kafli LAZ z roku ... dla N z M kafli
  obszaru — nic nie pobrano:` z rocznikami per kafel. Zapytania WFS idą do
  wszystkich roczników usługi. Sidecar kafla ma `extra.acquisition_date`
  i `extra.full_sheet`.
- **Nie działa:** z `--target-crs` (`Error: --year nie dziala z
  --target-crs ...`), dla CZ (zadanie wyłącznie CZ = `Error:`, obszar PL+CZ
  pod `auto` = `Info:`, CZ w bieżącej wersji).

### 4.2 Najnowszy pełny lot (`full_sheet/`, `--full-sheet`)

Najnowszy lot bywa niepełny: skorowidz deklaruje
`calyArkuszWypelnionyTrescia = NIE` i plik może mieć od 1 % do 99 % danych.
Ścieżka standardowa nadal wskazuje najnowszy lot, a obok niej Kartograf
utrzymuje drugie dowiązanie do najnowszego **lokalnego** lotu, który skorowidz
deklaruje jako pełny ([ADR-033](DECISIONS.md)):

```
data/nmt/pl_1992_1m_evrf2007/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc             # najnowszy lot
data/nmt/pl_1992_1m_evrf2007/full_sheet/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc  # najnowszy pełny
```

```bash
# arkusz z niepełnym najnowszym lotem: pobiera najnowszy i najnowszy pełny
kartograf download --sheet N-34-139-C-a-3-1 --full-sheet --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
#   -> N-34-139-C-a-3-1: nowa wersja 2025-10-21_84183_<sha8> (i druga: najnowszy pełny lot)
kartograf download --sheet M-34-90-C-b-4-4 --product orto --full-sheet -o ./data
kartograf download --sheet N-34-139-C-a-3-1 --full-sheet --max-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # pełny z zakresu lat
```

- **Bez flagi** `full_sheet/` powstaje tylko z lotów, które zadanie i tak
  ma lokalnie: domyślnie, gdy najnowszy lot jest pełny (oba dowiązania to
  ten sam plik, bez dodatkowego miejsca), a z `--all-campaigns` — najnowszy
  pełny spośród pobranych lotów. Pierwsze uruchomienie po aktualizacji tworzy
  `full_sheet/` także dla danych już pobranych.
- **`--full-sheet`** pobiera najwyżej jeden dodatkowy lot na arkusz i tylko
  wtedy, gdy najnowszy lot z zakresu lat nie jest pełny; z `--all-campaigns`
  nic nie dodaje. Sidecar takiej kampanii ma `request.full_sheet: true`.
- **Brak pełnego lotu:** w `full_sheet/` nie ma pliku. `Warning:` o niepełnej
  najnowszej kampanii dzieli arkusze na: `pelny lot w <segment>/full_sheet/`,
  `brak pelnego lotu w skorowidzu` (przy flagach roku: `... w zakresie lat
  zadania`) i `pelny lot nie pobrany ... — uzyj --full-sheet`.
- **Pełny = w granicach Polski.** Arkusz graniczny oznaczony jako pełny ma
  nodata po stronie zagranicznej ramki — to normalne. `full_sheet/` ufa
  deklaracji skorowidza, nie mierzy pokrycia.
- **Nigdy wstecz:** jak ścieżka standardowa; gdy przy flagach roku
  dowiązanie zostaje przy pełnym locie spoza zakresu, CLI podaje `Info:`
  z linią `<godło>: full_sheet/ -> dowiazanie <data>_<id>`.
- **`list_files()` / `delete()`:** `FileStorage.list_files()` pomija
  `full_sheet/` i `versions/`, `delete(godło)` usuwa oba dowiązania (wersje
  zostają).
- **Nie działa:** z `--product laz` i `--target-crs` (`Error:` przed siecią);
  dla CZ jak inne opcje kampanii.
- **Biblioteka:** `DownloadManager(full_sheet=True)`;
  `SheetFetch.full_link`, `DownloadResult.full_links` (godło -> ścieżka
  `full_sheet/`), `DownloadResult.without_full`,
  `DownloadResult.full_link_outside_range`.


### 4.3 Wersje, tryby i plan aktualizacji (`--check-updates`, `--upgrade`, `--force`)

Dotyczy każdego toru `kartograf download`: arkuszy PL NMT/NMPT/orto,
kafli LAZ, arkuszy CZ (TM33, SM5), wycinków CZ i wycinków PL
`--target-crs`, a także `landcover download` i `soilgrids hsg`. Flagi
wykluczają się wzajemnie. Tabela niżej opisuje arkusze PL (sygnał:
skorowidz); pozostałe tory różnią się sygnałem:

| Tor | Sygnał świeżości | Uwagi |
|---|---|---|
| arkusze PL | skorowidz GUGiK (`index`) | tabela niżej |
| kafle LAZ | rekord WFS (`index`) | nowszy nalot to nowe pliki — pobierane domyślnie; kafel z lokalną wersją tylko `--force` (D26) |
| arkusze SM5 (CZ) | `ETag`/`Last-Modified` (`http`) | jedno `HEAD` na plik; inny `ETag` = `nowsza`, `--upgrade` pobiera |
| kafle TM33, wycinki CZ i PL | brak (`none`) | domyślnie `lokalna wersja ... (bez sprawdzania; --check-updates)`; `--check-updates` = `nie da sie sprawdzic bez pobrania`; `--upgrade` = lokalna + `Info:` o `--force` |
| SoilGrids, CORINE CLMS | wydanie źródła (`metadata`: GetCapabilities / katalog CLMS) | etykieta wersji = wydanie (`2.0`, `V2020_20u1`); nowsze wydanie = `dostepna nowsza ... (--upgrade)`; wydanie niedostępne: bez lokalnej wersji `Error:`, z lokalną `Warning:` (z `--upgrade` `Error:`) |
| BDOT10k, podgląd CORINE | brak (`none`) | jak TM33; `--force` przy BDOT10k odświeża też cache PRG |
| HSG (`soilgrids hsg`) | sha256 wejść | ta sama treść wejść = `uzyta ponownie` (bez liczenia); w planie pozycja `hsg` obok trzech pozycji `landcover` |

Pod `--country auto` `--check-updates --plan PLIK` zapisuje JEDEN plan
z pozycjami PL i CZ (pole `track`), a `--upgrade --plan PLIK` wykonuje
pozycje każdego toru.

| Sytuacja | domyślnie | `--check-updates` | `--upgrade` | `--force` |
|---|---|---|---|---|
| lokalna wersja aktualna | lokalna wersja | `aktualne` | lokalna wersja | pobiera ponownie |
| w skorowidzu nowsza kampania | lokalna wersja + `Info:` | `nowsza: <etykieta>` | pobiera nowszą | pobiera |
| brak lokalnej wersji | pobiera | `do pobrania` | pobiera | pobiera |

`--check-updates` niczego nie pobiera; z `--plan PLIK` zapisuje plan JSON
(`kartograf-plan/1`), który `--upgrade --plan PLIK` wykonuje później —
pozycja, której źródło zmieniło się od planu, kończy się `Error:` bez
pobrania, a pozycje usunięte z pliku nie są wykonywane. `--force` pobiera
ponownie i odświeża cache metadanych, ale nie nadpisuje: ta sama treść =
`bez zmian`, inna = nowa wersja.

```bash
kartograf download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
#   N-34-139-C-a-3-1: nowa wersja 2025-10-21_84183_4de1eac7
kartograf download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data --check-updates --plan plan.json
#   N-34-139-C-a-3-1: aktualne (2025-10-21_84183)
kartograf download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data --upgrade --plan plan.json
```

Wynik: jedna linia na plik — `nowa wersja <etykieta>_<sha8>`, `nowa
etykieta <etykieta> (ta sama tresc)` (GUGiK opublikował tę samą treść pod
nowym rekordem), `bez zmian <etykieta>`, `lokalna wersja <etykieta>`
(z dopiskiem `; dostepna nowsza <etykieta> (--upgrade)`), po liście
podsumowanie `Nowe: N, nowa etykieta: N, bez zmian: N, lokalne: N, bledy: N`
(także dla kafli LAZ). Arkusz CZ i wycinek dają jedną linię statusu
(jednostka: godło albo ścieżka wycinka pod `--output`).

Biblioteka:

```python
from kartograf import DownloadManager, GugikProvider, UpdatePlan

godlo = "N-34-139-C-a-3-1"
manager = DownloadManager(
    "./data", GugikProvider(vertical_crs="EVRF2007", resolution="1m")
)
result = manager.download_sheet(godlo)
print(result.files[godlo][0].status, result.files[godlo][0].label)
plan = manager.check_sheets([godlo])  # niczego nie pobiera
report = manager.download_sheets(
    [godlo], update="upgrade", plan=UpdatePlan.from_json(plan.to_json())
)
print(report.stale, report.files.get(godlo, ()))
# LAZ / CZ / wycinki: run_laz_download(..., update=, plan=), check_laz_updates,
# run_cz_cutout(..., update=, plan=), check_cz_cutout, run_pl_wcs_cutout(...,
# update=, plan=), check_pl_cutout; land cover: LandCoverManager.download(...,
# update=, plan=), check, check_all_counties; HSG: calculate_hsg_by_*(...,
# update=, plan=), check_hsg_by_*; pozycje planu: item.track, item.unit
```

---

## 5. Gleby i HSG

- SoilGrids (ISRIC): 11 parametrów, 6 głębokości, 5 statystyk,
  rozdzielczość 250 m — tabela parametrów i jednostek: PRD 3.7;
  `kartograf landcover list-layers --source soilgrids`.
- HSG (`kartograf soilgrids hsg`, `HSGCalculator(output_dir)`) bierze
  `clay`/`sand`/`silt` jako wersje SoilGrids z tego samego magazynu
  (pobiera brakujące), klasyfikuje teksturę wg trójkąta USDA (12 klas)
  i mapuje ją na grupy A–D; wynik to wersja GeoTIFF 1–4 (0 = nodata)
  w `hsg/global_soilgrids_<głębokość>_<stat>/` z sidecarem
  (`extra.source_files`: ścieżki wersji i sha256 wejść; PRD 3.8). Te same
  wejścia = wersja użyta ponownie, bez liczenia.
- `hsg_from_rasters(clay, sand, silt, *, bbox, crs, pixel_m, output_path)`
  robi to samo z gotowych rastrow (g/kg) na siatce o zadanym ukladzie
  i pikselu, bez wartosci domyslnych. Nodata wejscia tylko z jego tagu,
  a piksele poza zasiegiem wejscia dostaja `0`; sidecar zawiera skroty
  SHA-256 plikow wejsciowych (`extra.source_files`: `name`, `file`,
  `sha256`; `extra.source_layers` to jak w HSG lista nazw warstw).
- Klasyfikacja używa **kanonicznych progów trójkąta USDA** (skośne granice
  `silt + 1.5*clay`, `silt + 2*clay`), wspólnych dla wersji skalarnej
  i tablicowej. Mapowanie tekstura → HSG jest świadomie łagodniejsze niż
  tabela TR-55: `sandy_loam` = **B** (nie A), `clay_loam`
  i `silty_clay_loam` = **C** (nie D) — to klasy przejściowe, których grupa
  zależy też od struktury gleby ([ADR-025](DECISIONS.md)).
- `--stats` podaje powierzchnie grup w ha także dla rastrów w EPSG:4326
  (pole komórki liczone geodezyjnie na elipsoidzie, nie w stopniach
  kwadratowych).

---

## 6. Konfiguracja CLMS API (CORINE GeoTIFF)

Aby pobierać CORINE jako **GeoTIFF z kodami klas** (zamiast podglądu PNG),
potrzebne jest konto w Copernicus Land Monitoring Service:

1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (JSON z polami `client_id`, `private_key`,
   `token_uri`, opcjonalnie `key_id` i `user_id`)
3. Ustaw je w zmiennej środowiskowej `CLMS_CREDENTIALS` — działa na każdym
   systemie:

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

**Bezpieczeństwo:** credentials czyta wyłącznie podproces Auth Proxy
(`python -m kartograf.auth.proxy`), który dziedziczy zmienne środowiskowe
rodzica. Główna aplikacja nigdy nie widzi kluczy prywatnych ani tokenu —
proxy pobiera dane samo, a token dostają wyłącznie hosty `*.copernicus.eu`
i `*.eea.europa.eu` (presigned link pobrania na innym hoście `https` jest
forwardowany bez tokenu, adres `http` odrzucany). Szczegóły: PRD 3.6,
DEVELOPMENT_STANDARDS 14.3.

**Bez konfiguracji:** CORINE automatycznie pobiera podgląd PNG przez WMS
(sidecar dostaje wtedy `extra.fallback = "wms_png"`).

**Z poziomu biblioteki** można też podać credentials wprost:
`CorineProvider(clms_credentials={...})` (tryb bezpośredni, z pominięciem
proxy).

---

## 7. Znane problemy i ograniczenia

- Kartograf nie scala rastrów PL i CZ w jedną powierzchnię przygraniczną
  (R6); wyniki są osobne, powiązane przez `extra.parent_request`.
- Land cover i HSG (od 0.8.0): poprawkę danych w obrębie tego samego
  wydania SoilGrids/CORINE (bez zmiany etykiety wydania) wykrywa tylko
  `--force`; BDOT10k i podgląd CORINE nie mają taniego sygnału świeżości.
  Pobranie CORINE z CLMS (z `CLMS_CREDENTIALS`) nie było sprawdzone na
  żywo w 0.8.0 (odczyt wydania z katalogu CLMS — tak). Pliki land cover
  i HSG z 0.7.x (`bdot10k_teryt_*.gpkg`, `soilgrids_*.tif`,
  `hsg_*.tif`) nie są rozpoznawane — pobierz ponownie do magazynu.
- Gdy skorowidz dla godła PL-2000 1:10000 udostępnia tylko arkusze potomne,
  pobranie zwraca `NoCoverageError` z podpowiedzią `--scale 1:2000`; nie
  pobiera arkusza PL-1992 jako zamiennika.
- Rozpoznawanie krajów używa prostokątnych obwiedni (ADR-023), nie wielokąta
  granic; `--country auto` może odpytać CUZK poza Czechami i GUGiK
  w Czechach (sekcja 1.2).
- NMT 5 m nie obsługuje `--target-crs`: pobieraj arkusze
  bez tej flagi.
- `provider.download_bbox` (WCS: NMT KRON86 TIFF, NMT EVRF2007
  i NMPT ASC multipart) daje wysokości float32 w rozdzielczości
  1 m poza magazynem wersji, bez maski lądu PRG i bez sidecara;
  maskę i wersję dostaje wycinek `--target-crs` /
  `download_pl_cutout`. Kompozycja serwera może różnić się
  od wyboru kampanii arkusza.
- Wycinki (PL, CZ) i kafle TM33 nie mają taniego sygnału świeżości:
  zmiana treści u źródła albo maski PRG jest niewidoczna bez `--force`.
- Uszkodzony albo nieczytelny cache metadanych (`.kartograf_cache.db`
  w bieżącym katalogu) nie przerywa pobierania: CLI drukuje jedno
  `Warning: cache metadanych nieczytelny (...)` i pracuje bez cache.
  Naprawa: `kartograf cache clear` (usuwa nieczytelny plik wraz
  z `-wal`/`-shm`) albo ręczne usunięcie pliku.

Pełna lista ograniczeń technicznych (timeouty, ponowienia, CZ, `auto`):
SCOPE 3.2; plany: SCOPE 3.1.
