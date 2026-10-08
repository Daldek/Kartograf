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
   - [1.6 Kiedy `--scale` jest niezbędne](#16-kiedy---scale-jest-niezbędne)
2. [Biblioteka Python](#2-biblioteka-python)
3. [Wynik pobrania](#3-wynik-pobrania)
4. [Kampanie GUGiK](#4-kampanie-gugik)
5. [Gleby i HSG](#5-gleby-i-hsg)
6. [Konfiguracja CLMS API (CORINE GeoTIFF)](#6-konfiguracja-clms-api-corine-geotiff)
7. [Znane problemy i ograniczenia](#7-znane-problemy-i-ograniczenia)

Domyślne `--output` CLI to `./data` (pokrycie terenu: `./data/landcover`,
HSG: `./data/hsg`) względem bieżącego katalogu — podaj własny katalog przez
`--output`, gdy dane mają trafić gdzie indziej.

---

## 1. CLI

### 1.1 NMT, NMPT, ortofotomapa, LAZ (Polska)

```bash
# Informacje o godle (auto-detekcja PL-1992 / PL-2000); --hierarchy pokazuje hierarchię
kartograf parse N-34-130-D-d-2-4
kartograf parse N-34-130-D --hierarchy

# NMT: pojedynczy arkusz albo hierarchia, opcjonalnie 5m; godło PL-1992 grubsze
# niż 1:10000 rozwija się do arkuszy 1:10000 samo — bez --scale (sekcja 1.6)
kartograf download N-34-130-D-d-2-4
kartograf download N-34-130-D --resolution 5m --workers 8 --output ./data

# Inne produkty GUGiK: NMPT (DSM), ortofotomapa, chmury punktów LAZ
kartograf download N-34-130-D-d-2-4 --product nmpt
kartograf download N-34-130-D-d-2-4 --product orto
kartograf download N-34-130-D-d-2-4 --product laz
kartograf download N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12
kartograf download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86

# PL-2000: godło albo bbox w CRS strefy; godło grubsze i bbox wymagają --scale
# zgodnej z arkuszami GUGiK (sekcja 1.6)
kartograf parse 6.179.12.20
kartograf download 6.179.12.20
kartograf download 7.171.21 --scale 1:2000
kartograf download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --system 2000 --scale 1:2000

# Kampanie GUGiK (sekcja 4): domyślnie najnowsza (newest); wszystkie kampanie
# arkusza (all); tylko kampanie z roku pozyskania >= RRRR (--min-year)
kartograf download N-34-130-D-d-2-4 --campaigns all
kartograf download N-34-130-D-d-2-4 --min-year 2024
kartograf download --bbox 530000,382000,533000,386000 --campaigns all --min-year 2022
kartograf download N-34-130-D-d-2-4 --product laz --campaigns all
kartograf download --bbox 530000,382000,533000,386000 --product laz --campaigns all
```

Pełna lista komend i opcji: `kartograf --help`, `kartograf <komenda> --help`.

LAZ: domyślnie pobierany jest najnowszy kafel dla każdego fragmentu obszaru;
starsze kafle pokryte przez nowsze są pomijane z komunikatem `Info:`
([ADR-029](DECISIONS.md), szczegóły: SCOPE 2.5 i ARCHITECTURE 4.7 "Wybór
kafli"); `--year` wybiera jeden rocznik (rocznik nieobecny w usłudze = błąd
z listą dostępnych). WFS GUGiK w EPSG:2180 używa kolejności osi (N,E).
`--min-density` i `extra.nominal_density` to gęstość **nominalna** z WFS
GUGiK — faktyczna bywa wyższa.

### 1.2 Selekcja obszaru i wybór kraju (`--country`)

```bash
kartograf download --bbox 771000,509000,772000,510000 --product orto
kartograf download --geometry area.shp
kartograf download --geometry zlewnia.gpkg --layer catchments
kartograf download --bbox 530000,382000,533000,386000 --country pl
```

- Domyślne `--bbox-crs` to `EPSG:2180`; plik geometrii: SHP albo GPKG
  (`--layer` wybiera warstwę GPKG).
- PL bez `--target-crs` zapisuje **listę arkuszy** w hierarchii godeł;
  arkusz bez danych GUGiK jest pomijany z `Warning:` (kod 0, gdy pobrano
  choć jeden arkusz).
- Domyślnie działa `--country auto`. Kraje są rozpoznawane po
  **prostokątnych** obwiedniach, nie po granicy: obszar przecinający
  obwiednię CZ (na zachód od 18,86°E i na południe od 51,06°N) trafia także
  do CUZK, a prostokąt PL (14,07–24,20°E, 49,00–54,90°N) obejmuje większość
  Czech. Dla czystej Polski użyj `--country pl`.
- Flagi bez odpowiednika czeskiego (`--product nmpt|orto`, `--system`,
  `--vertical-crs KRON86`, `--resolution 1m`) na obszarze objętym
  obwiedniami obu krajów same przełączają `auto` na PL (komunikat `Info:`).
  W Pradze czy Brnie taka flaga kieruje więc zadanie do GUGiK, który nie ma
  tam danych (błąd pobrania); błąd przed siecią dostaje dopiero obszar poza
  prostokątem PL. LAZ na obszarze sięgającym CZ wymaga jawnego `--country pl`.
- Pod `auto` przycięcie do obwiedni kraju jest komunikowane jako `Info:`;
  oryginalny bbox zachowuje `extra.parent_request`, cały bbox pobiera
  `--country pl`.
- Pełne reguły (przycinanie, kody wyjścia, częściowy sukces): SCOPE 3.2,
  ARCHITECTURE 4.6, ADR-023.

### 1.3 Jeden scalony GeoTIFF (`--target-crs`)

```bash
kartograf download --bbox 530000,382000,533000,386000 --country pl --target-crs EPSG:2180
kartograf download --bbox 530000,382000,533000,386000 --country pl --target-crs EPSG:5514
# pogranicze: dwa wycinki (PL + CZ) w tym samym układzie, wspólny parent_request
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --target-crs EPSG:2180 --vertical-crs EVRF2007
```

- Mozaika arkuszy i lokalna reprojekcja przypiętą operacją; dla PL tylko
  `--product nmt` i arkusze PL-1992 ([ADR-027](DECISIONS.md)).
- Arkusz bez danych GUGiK (morze, strona zagraniczna) to nodata w wyniku,
  `Warning:` i `extra.missing_sheets`. Na pograniczu — także z Niemcami,
  których danych nie obsługujemy — `--target-crs` daje ciągły wycinek;
  bez niego arkusz leżący za granicą po prostu nie pojawia się na liście
  plików.
- `EPSG:2180` zachowuje siatkę i wartości arkuszy 1:1; arkusze o różnych
  fazach siatki kończą się `GridMismatchError` (podpowiedź: inny
  `--target-crs`, który reprojektuje każdy arkusz osobno).
- Istniejący wycinek (ta sama nazwa = te same współrzędne żądania) jest
  pomijany bez sieci (`Skipped ... - already exists`). Przebudowa: `--force`
  (pobiera ponownie także wszystkie arkusze) albo usunięcie samego pliku
  wycinka (arkusze z dysku zostaną użyte ponownie). Nieudana przebudowa nie
  kasuje poprzedniego pliku.
- Przed pobraniem kontrola wolnego miejsca (dolne oszacowanie; brak
  miejsca = błąd przed siecią), `Info:` dla wycinka >= 1 GiB; twardego
  limitu rozmiaru nie ma.
- Wycinek zawsze składa się z najnowszych kampanii (nie przyjmuje
  `--campaigns all`/`--min-year`). Pełny opis: ARCHITECTURE 4.3.

### 1.4 Czechy (CUZK)

```bash
# DMR 5G (2 m), godło TM33 (ten kafel leży w większości w Niemczech — głównie nodata)
kartograf download 302_5550 --country cz
kartograf download CTES96                                      # DMR 4G (5 m), godło SM5, kraj z godła
kartograf download 302_5550 --country cz --vertical-crs EVRF2007   # Bpv -> EVRF2007 (EPSG:5621)
# reprojekcja CZ (tylko --bbox/--geometry, nie godło), lokalnie przypiętą operacją
kartograf download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180
# pogranicze pod auto: osobne pliki PL i CZ, wspólny extra.parent_request
# (bez --vertical-crs: PL w EVRF2007, CZ w Bpv)
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto
# bboxy w EPSG:5514 są na terytorium CZ ujemne — podaj je jako --bbox=... (bez spacji),
# inaczej argparse odczyta wartość jako nieznaną flagę
kartograf download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --resolution 5m
```

`kartograf parse` obsługuje tylko godła PL (PL-1992/PL-2000); godła CZ
(TM33, SM5) przyjmuje `kartograf download`.

- Rozdzielczość CZ: arkusz SM5 (np. `CTES96`) to gotowy plik DMR 4G,
  który istnieje tylko w 5 m — bez `--resolution` pobierany jest w 5 m,
  a jawne `--resolution 2m` jest błędem (`Error:`, kod 1, bez sieci).
  Kafel TM33 i `--bbox`/`--geometry` są wycinane z usługi: domyślnie 2 m
  (DMR 5G), `--resolution 5m` wybiera DMR 4G.

- CZ `--bbox` zawsze daje jeden plik (wycinek), PL bez `--target-crs`
  listę arkuszy.
- Porażka jednego kraju pod `auto` (brak danych albo awaria źródła) przy
  sukcesie drugiego kończy się kodem 0 i `Warning:` na stderr; kod 1, gdy
  żaden kraj nie dał wyniku albo `--country` było jawne.
- Natywnie S-JTSK/Bpv (EPSG:5514); `KRON86` dla CZ jest nieosiągalny.
  Szczegóły: SCOPE 2.2 i 3.2, ARCHITECTURE 4.4–4.6.

### 1.5 Pokrycie terenu, gleby, HSG, cache

```bash
kartograf landcover download --source bdot10k --teryt 1465
kartograf landcover download --source bdot10k --teryt 1465 --format SHP   # archiwum .zip
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D
#   -> corine_2018_godlo_N-34-130-D.tif (bez credentials CLMS: .png z WMS)
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm
#   -> soilgrids_clay_15-30cm_mean_godlo_N-34-130-D.tif
# Nazwa niesie każdy parametr treści (także domyślny), więc --property sand
# dla tego samego obszaru daje osobny plik; parametry są też w sidecarze
# (request.property/depth/stat, request.year, request.format).

# Hydrologic Soil Groups dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats

# Przegląd źródeł/warstw i cache metadanych
kartograf landcover list-sources
kartograf landcover list-layers --source soilgrids
kartograf cache stats
kartograf cache clear
kartograf cache path
```

`--teryt` dotyczy tylko BDOT10k (CORINE/SoilGrids: `--godlo`, `--bbox`,
`--geometry`). CORINE bez credentials CLMS pobiera podgląd PNG (sekcja 6).
Warstwy BDOT10k, parametry SoilGrids i lata CORINE: PRD 3.5–3.7.

### 1.6 Kiedy `--scale` jest niezbędne

`--scale` to skala **docelowa** arkuszy, które Kartograf zamawia u GUGiK
(NMT, NMPT, ortofotomapa). Musi odpowiadać skali arkuszy, w jakich GUGiK
publikuje dany produkt w danym układzie — Kartograf pobiera plik arkusza
o dokładnie tym godle (cały token), więc arkusz w innej skali nie zostanie
dopasowany. Domyślnie `1:10000`.

**Zasięg flagi:**

- godło grubsze od skali docelowej jest rozwijane do wszystkich potomków
  w tej skali (`kartograf parse <godło> --descendants <skala>` pokazuje
  listę przed pobraniem);
- `--bbox`/`--geometry` bez `--target-crs`: obszar jest rozbijany na arkusze
  w tej skali (z `--system 1992` albo `--system 2000`);
- bez flagi godło 7-członowe PL-1992 i każde godło PL-2000 (także
  1:10000, np. `7.171.21`) to pojedynczy arkusz — rozwijane jest tylko
  godło PL-1992 grubsze niż 1:10000;
- nie dotyczy LAZ (kafle wybierane z WFS) ani CZ (godło TM33/SM5 albo
  wycinek z usługi).

**PL-1992 — flaga zbędna.** Kartograf pobiera arkusze PL-1992 z 7-członowym
godłem (np. `N-34-130-D-d-2-4`), oznaczane w Kartografie jako `1:10000` —
to najdrobniejsza skala PL-1992 w Kartografie i wartość domyślna. Godło
grubsze (np. `N-34-130-D`) rozwija się do tych arkuszy samo. Uwaga na
nazewnictwo: etykiety skal Kartografu są o jeden poziom drobniejsze niż
nomenklatura GUGiK — ten sam 7-członowy arkusz skorowidz GUGiK opisuje jako
moduł archiwizacji 1:5000 (`modulArchiwizacji`). `--scale` przyjmuje
etykiety Kartografu (SCOPE 2.1).

**PL-2000 — flaga zwykle niezbędna.** Kartograf zaczyna podział PL-2000 od
arkusza 1:10000 (`strefa.pas.słup`, np. `7.171.21`), a GUGiK publikuje
arkusze PL-2000 w drobniejszych modułach. W zapisanych odpowiedziach
skorowidza NMT 1 m i ortofotomapy, na których opierają się testy
Kartografu, arkusze PL-2000 mają najczęściej moduł 1:2000 (np.
`7.171.21.23`, `5.167.25.13`), a obok nich występują też arkusze 1:1000
i 1:5000; arkusza PL-2000 1:10000 nie było w nich wcale. Dlatego dla godła 1:10000 i dla `--bbox`/`--geometry`
z `--system 2000` podaj skalę arkuszy z danymi, zwykle `--scale 1:2000`:

```bash
kartograf download 7.171.21 --scale 1:2000
kartograf download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --system 2000 --scale 1:2000
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
  godło albo `--system <układ> --scale <skala>`.

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
from kartograf import SheetParser, DownloadManager, BBox

# Parsowanie godła i bounding box arkusza
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)                      # "1:10000"
bbox = parser.get_bbox(crs="EPSG:2180")  # lub "EPSG:4326"

# Pobieranie przez godło -> ASC (OpenData); hierarchia: download_hierarchy()
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")

# Pobieranie przez bbox -> GeoTIFF (WCS) — tylko NMT 1m i tylko w układzie KRON86:
# endpoint WCS dla EVRF2007 GUGiK wycofał (HTTP 404 od 2026-08), więc
# download_bbox pod EVRF2007 kończy się ValidationError. Wysokości EVRF2007
# bierz z arkuszy (download_sheet / download_sheets), a jako jeden GeoTIFF
# z arkuszy: download_pl_cutout() (niżej).
kron = DownloadManager(output_dir="./data", vertical_crs="KRON86")
area = BBox(min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180")
path = kron.download_bbox(area, "my_area.tif")

# Land Cover: BDOT10k (domyślny provider) / CORINE / SoilGrids
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
from kartograf import download_pl_cutout, MetadataCache

result = download_pl_cutout(
    BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
    "EPSG:5514",
    output_dir="./data",
    max_workers=4,
    cache=MetadataCache(),
)
print(result.path)
# arkusze bez danych GUGiK (nodata); także gdy result.skipped — z sidecara
print(result.missing_sheets)
# Wyjątki: DownloadError (awaria pobrania arkusza — wycinek nie powstaje),
# ValidationError (żaden arkusz nie ma danych, za mało miejsca na dysku,
# nieobsługiwany parametr); GridMismatchError (różne fazy siatki przy EPSG:2180).
# Kroki osobno (własny provider/sesja/FileStorage):
# prepare_pl_cutout -> select_pl_cutout_sheets -> run_pl_cutout.
```

**Cache metadanych w bibliotece.** Bez `MetadataCache` provider NMT pyta
skorowidz GUGiK przy KAŻDYM `download_sheet`, także dla arkusza już
pobranego. Przekaż cache providerowi, a zapytania o arkusz ograniczą się do
raz na TTL cache (7 dni):

```python
from kartograf import DownloadManager, MetadataCache
from kartograf.providers.pl import create_nmt_provider

manager = DownloadManager(
    output_dir="./data",
    provider=create_nmt_provider(cache=MetadataCache()),  # albo GugikProvider(cache=...)
)
```

Pozostałe elementy publicznego API (m.in. `GugikNmptProvider`,
`GugikOrtoProvider`, `GugikLazProvider`/`download_laz_area` dla LAZ,
`CuzkDmrProvider`/`create_dmr_provider` dla Czech, `Parser2000`,
`ParserTM33`, `FileStorage`) — eksporty w `kartograf/__init__.py`, opis
w SCOPE 2.10 i PRD 5.

---

## 3. Wynik pobrania

**Wartość zwracana.** `DownloadManager.download_sheet()` zwraca `Path` dla
arkusza 1:10000 i dla godła PL-2000 (pobierane bezpośrednio), a
`list[Path]` dla godła PL-1992 grubszego niż 1:10000 — takie godło jest
rozwijane do arkuszy 1:10000 przez `download_hierarchy()` (ta zawsze zwraca
`list[Path]`). Kod wołający musi obsłużyć oba warianty.
`download_sheets(godla)` pobiera listę godeł (grubsze PL-1992 rozwijane do
1:10000 — `expand_sheets()`) i nie przerywa się na porażce arkusza.

**Podsumowania** (pola: dataclassy w kodzie, opis — ARCHITECTURE 4.1–4.3):

- `DownloadManager.last_result` (`DownloadResult`) po liście/hierarchii:
  `succeeded`, `failed`, `skipped`, `no_coverage` (arkusze, dla których
  GUGiK nie ma danych — `NoCoverageError`, podklasa `DownloadError`; są też
  w `failed`), pliki kampanii i `unverified` (sekcja 4).
- `DownloadManager.last_sheet` (`SheetFetch`) po pojedynczym arkuszu:
  `path`, `skipped`, `downloaded`, `reused`, `link`, `unverified`.
- `PlCutoutResult` (wycinek): `path`, `skipped`, `missing_sheets`,
  `off_grid_sheets`, `partial_sheets`, `all_nodata`, `unverified`.
- `LazDownloadResult` (`download_laz_area`): `downloaded`, `skipped`,
  `failed`, `superseded` (kafle pominięte jako pokryte przez nowsze).

**Sidecar.** Każde udane pobranie przez CLI albo warstwę zarządzającą
biblioteki (niżej) zapisuje dwa pliki: dane (`.asc`, `.tif`,
`.laz`, `.gpkg`, ...) i `<plik>.meta.json` (schemat `kartograf-meta/1`): układ
poziomy i pionowy pliku, nodata, żądanie, licencja, użyte transformacje,
pochodzenie (`extra.source`), a dla zadań obszarowych `extra.parent_request`
łączący pliki jednego zadania. Pełna tabela pól: ARCHITECTURE 3.2,
`parent_request`: ARCHITECTURE 3.4. Sidecary pisze warstwa zarządzająca
(`DownloadManager`, `LandCoverManager`, wycinek PL i kafle LAZ w bibliotece;
CLI dla CZ), a `FileStorage.delete()` usuwa sidecar razem z plikiem danych.
Bezpośrednie wywołanie providera (np. `CuzkDmrProvider` z biblioteki) zapisuje
sam plik danych, bez sidecara.

**Gdzie leżą pliki.** `data/<produkt>/<kraj>_<układ>[_<wariant>][_<vcrs>]/...`
— kanoniczna tabela, przykłady i migracja z 0.6.x: ARCHITECTURE 3.3.

**Pliki CZ i wycinki PL sprzed przypięcia operacji EPSG:1622/1623.** Pliki,
których sidecar w `transform.horizontal` zawiera `S-JTSK to ETRS89 (3)`, nie
są przebudowywane automatycznie; CLI drukuje `Info:` przy ich pominięciu,
a ponowne pobranie wymusza `--force`.

---

## 4. Kampanie GUGiK

GUGiK publikuje ten sam arkusz w kilku kampaniach (różne lata pozyskania).
`--campaigns newest` (domyślnie) pobiera najnowszą; `--campaigns all` —
każdą; `--min-year RRRR` odcina kampanie z `aktualnosc` sprzed danego roku
(obie strategie). Kampanie dotyczą tylko PL — dla CZ opcje dają `Error:`
(zadanie wyłącznie czeskie) albo `Info:` (obszar PL+CZ pod `auto`).

Prawdziwe pliki NMT/NMPT/orto leżą w
`data/<produkt>/<segment>/kampanie/<data>_<id>/<hierarchia godła>/<godło>.<ext>`
(`<data>` = data pozyskania, `<id>` = numer kampanii z nazwy pliku GUGiK),
a ścieżka standardowa `data/<produkt>/<segment>/<hierarchia godła>/<godło>.<ext>`
jest dowiązaniem do najnowszej lokalnej kampanii. `newest` po wygaśnięciu
cache (7 dni) sprawdza w skorowidzu, czy pojawiła się nowsza kampania.

- **Skorowidz niedostępny:** gdy skorowidz GUGiK nie odpowiada (sieć, HTTP
  429/5xx), a arkusz ma już lokalną kampanię, `newest` jej używa i drukuje
  `Warning: <godło>: skorowidz GUGiK niedostepny — uzyto lokalnej kampanii
  bez sprawdzenia nowszej (...)` (kod bez zmian, także z `-q`). Bez lokalnej
  kampanii, z `--force`, `--campaigns all` albo `--min-year` taki błąd nadal
  kończy pobranie arkusza porażką (errata 5 ADR-030). Biblioteka:
  `DownloadManager.last_sheet.unverified` / `DownloadResult.unverified`
  (treść błędu transportu).
- **Dowiązanie = hardlink:** ścieżka standardowa to dowiązanie twarde do
  pliku kampanii (ten sam plik na dysku, bez dodatkowego miejsca); Kartograf
  nie tworzy symlinków. Gdy system plików nie obsługuje hardlinków
  (exFAT/FAT, sshfs/FUSE), powstaje kopia z `Warning:` (`extra.link: copy`
  w sidecarze).
- **Kopiowanie `data/`:** użyj `rsync -aH` albo `cp -a` — bez zachowania
  hardlinków ścieżka standardowa staje się osobną kopią (duplikat danych).
- **Windows:** hardlink działa bez dodatkowych uprawnień (NTFS), a dane
  udostępnione przez SMB klient Windows widzi jako zwykłe pliki.
- **Migracja:** brak; zwykły plik NMT/NMPT/orto w starej ścieżce
  standardowej jest traktowany jak nieznany — pierwsze uruchomienie pobiera
  go ponownie do `kampanie/` i zastępuje dowiązaniem.
- **Wycinek `--target-crs`** zawsze składa się z najnowszych kampanii i nie
  przyjmuje `--campaigns all`/`--min-year`.
- **LAZ:** `--campaigns all` pobiera wszystkie kafle, których rama przecina
  obszar (bez deduplikacji ADR-029), `--min-year` to dolna granica roku
  kafla; `--min-year` i `--year` wykluczają się. LAZ nie używa dowiązań.
- Składanie kilku kampanii w jedną powierzchnię nie jest częścią 0.7.0
  (planowane na 0.7.1, SCOPE 3.1).

Reguły szczegółowe: SCOPE 2.12, ARCHITECTURE 3.3 (reguła 6), ADR-030.

---

## 5. Gleby i HSG

- SoilGrids (ISRIC): 11 parametrów, 6 głębokości, 5 statystyk,
  rozdzielczość 250 m — tabela parametrów i jednostek: PRD 3.7;
  `kartograf landcover list-layers --source soilgrids`.
- HSG (`kartograf soilgrids hsg`, `HSGCalculator`) pobiera `clay`/`sand`/
  `silt` z SoilGrids, klasyfikuje teksturę wg trójkąta USDA (12 klas)
  i mapuje ją na grupy A–D; wynik to GeoTIFF 1–4 (0 = nodata) z sidecarem
  (PRD 3.8).
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
- Gdy skorowidz dla godła PL-2000 1:10000 udostępnia tylko arkusze potomne,
  pobranie zwraca `NoCoverageError` z podpowiedzią `--scale 1:2000`; nie
  pobiera arkusza PL-1992 jako zamiennika.
- Rozpoznawanie krajów używa prostokątnych obwiedni (ADR-023), nie wielokąta
  granic; `--country auto` może odpytać CUZK poza Czechami i GUGiK
  w Czechach (sekcja 1.2).
- Arkusze NMT 5 m mogą mieć różne fazy siatki: wycinek
  `--target-crs EPSG:2180` kończy się `GridMismatchError` zamiast zwracać
  niezgodne wartości; inny `--target-crs` uruchamia warp per arkusz (W1).
- WCS NMT (`download_bbox`) działa tylko dla 1 m w KRON86 (endpoint EVRF2007
  zwraca 404 od 2026-08); wysokości EVRF2007 z obszaru: CLI `--bbox`
  (arkusze OpenData) albo jeden GeoTIFF przez `--target-crs` /
  `download_pl_cutout`.
- Uszkodzony albo nieczytelny cache metadanych (`.kartograf_cache.db`
  w bieżącym katalogu) nie przerywa pobierania: CLI drukuje jedno
  `Warning: cache metadanych nieczytelny (...)` i pracuje bez cache.
  Naprawa: `kartograf cache clear` (usuwa nieczytelny plik wraz
  z `-wal`/`-shm`) albo ręczne usunięcie pliku.

Pełna lista ograniczeń technicznych (timeouty, ponowienia, CZ, `auto`):
SCOPE 3.2; plany: SCOPE 3.1.
