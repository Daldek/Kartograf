# Przewodnik użytkownika — Kartograf

Jak używać Kartografu z wiersza poleceń i jako biblioteki Python. Dokument
opisuje zachowanie widoczne dla użytkownika; szczegóły techniczne i
kontrakty leżą w dokumentach kanonicznych, do których sekcje odsyłają:
zakres i ograniczenia — [SCOPE.md](SCOPE.md), architektura, układ `data/`
i schemat sidecara — [ARCHITECTURE.md](ARCHITECTURE.md), uzasadnienia —
[DECISIONS.md](DECISIONS.md). Pełna lista opcji CLI: `kartograf <grupa> <komenda> --help`;
lista publicznego API: `kartograf/__init__.py` (`__all__`).

## Spis treści

1. [CLI](#1-cli)
   - [1.1 NMT, NMPT, ortofotomapa, LAZ (Polska)](#11-nmt-nmpt-ortofotomapa-laz-polska)
   - [1.2 Selekcja obszaru i wybór kraju (`--country`)](#12-selekcja-obszaru-i-wybór-kraju---country)
   - [1.3 Jeden wycinek (`--cutout`)](#13-jeden-wycinek---cutout)
   - [1.4 Czechy (CUZK)](#14-czechy-cuzk)
   - [1.5 Pokrycie terenu, gleby, HSG, cache](#15-pokrycie-terenu-gleby-hsg-cache)
   - [1.6 Kiedy `--scale` jest wymagane](#16-kiedy---scale-jest-wymagane)
   - [1.7 Raport dostępności (`elevation availability`)](#17-raport-dostępności-elevation-availability)
   - [1.8 Granice, ewidencja, modele 3D budynków i archiwum BDOT10k](#18-granice-ewidencja-modele-3d-budynków-i-archiwum-bdot10k)
2. [Biblioteka Python](#2-biblioteka-python)
3. [Wynik pobrania](#3-wynik-pobrania)
4. [Kampanie GUGiK](#4-kampanie-gugik)
5. [Gleby i HSG](#5-gleby-i-hsg)
6. [Konfiguracja CLMS API (CORINE GeoTIFF)](#6-konfiguracja-clms-api-corine-geotiff)
7. [Znane problemy i ograniczenia](#7-znane-problemy-i-ograniczenia)
8. [Projekt](#8-projekt)

Komendy są pogrupowane wg typu danych (`kartograf <grupa> <komenda>`, ADR-039):

| Grupa | Komendy | Dane |
|---|---|---|
| `elevation` | `download`, `list-sources`, `availability` | NMT, NMPT (PL, CZ), LAZ (PL); raport dostępności PL |
| `imagery` | `download`, `list-sources` | ortofotomapa (PL) |
| `landcover` | `download`, `list-sources`, `list-layers` | BDOT10k (także archiwum roczników `--year`), CORINE (`--source`) |
| `soil` | `download`, `hsg`, `list-sources`, `list-layers` | SoilGrids, HSG |
| `boundaries` | `download`, `list-sources` | granice jednostek administracyjnych i ewidencyjnych PRG (PL) |
| `cadastre` | `download`, `list-sources` | EGiB — działki i budynki (PL) |
| `models3d` | `download`, `list-sources` | modele 3D budynków CityGML LoD1/LoD2 (PL) |
| `project` | `init`, `add`, `remove`, `download`, `status`, `verify` | manifest projektu i przypiete wersje z magazynu |

Poza grupami zostają `kartograf parse` i `kartograf cache`. `kartograf <grupa>
--help` wypisuje komendy grupy, `list-sources` — źródła grupy z rejestru (bez
sieci). Dawne `kartograf download`, `kartograf soilgrids` i
`landcover --source soilgrids` nie działają: kończą się błędem (kod 2)
z nazwą nowej komendy (tabela: CHANGELOG 0.8.0).

Od 0.8.0 CLI nie ma wartości domyślnych wpływających na dane: `--product`,
`--output` (także `landcover download`, `soil download` i `soil hsg`), `--country`
(z `--bbox`/`--geometry`), `--vertical-crs` (NMT, NMPT, LAZ),
`--resolution` (NMT i NMPT, gdy jest wybór), `--sheet-system` (PL `--bbox`/`--geometry`
bez `--cutout`), `--horizontal-crs` (z `--cutout`), `--scale` (PL-2000),
`--level` (obszar `boundaries`), `--lod` i `--year` (`models3d`, gdy wydań
jest kilka) oraz `--format` z `--year` (archiwum BDOT10k)
podaje się jawnie. Brak wartości to `Error:` z listą
dopuszczalnych wartości (kod 1, przed siecią); listy i znaczenia wartości
podaje też `kartograf <grupa> <komenda> --help`. Domyślne zostały tylko format,
układ `--bbox-crs EPSG:2180`, przełączniki i parametry techniczne
(`--workers`).

---

## 1. CLI

### 1.1 NMT, NMPT, ortofotomapa, LAZ (Polska)

```bash
# Informacje o godle (auto-detekcja PL-1992 / PL-2000); --hierarchy pokazuje hierarchię
kartograf parse N-34-130-D-d-2-4
kartograf parse N-34-130-D --hierarchy

# NMT: pojedynczy arkusz albo hierarchia; godło PL-1992 grubsze
# niż 1:10000 rozwija się do arkuszy 1:10000 samo — bez --scale (sekcja 1.6)
kartograf elevation download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf elevation download --sheet N-34-130-D --resolution 5m --workers 8 --output ./data --product nmt --vertical-crs EVRF2007
kartograf elevation download --sheet N-33-58-A-c-1-3 --product nmt --resolution 0.5m --vertical-crs EVRF2007 -o ./data
# Rozdzielczości i układy wysokości pochodzą z rejestru wariantów (niżej);
# kombinacja spoza rejestru, np. --resolution 5m z --vertical-crs KRON86,
# kończy się Error: (kod 1, przed siecią) z listą dostępnych wartości

# NMPT (DSM) — --resolution wymagane (od 0.8.0)
kartograf elevation download --sheet M-34-64-D-d-2-1 --product nmpt --resolution 0.5m --vertical-crs EVRF2007 -o ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --product nmpt --resolution 1m --vertical-crs EVRF2007 -o ./data

# Archiwum GUGiK jako plik źródłowy (--format; bez konwersji): NMT TBD 25 m KRON86
kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TBD --resolution 25m --vertical-crs KRON86 --year 2010 -o ./data

# Inne produkty GUGiK: ortofotomapa, chmury punktów LAZ
kartograf imagery download --sheet N-34-130-D-d-2-4 --product orto -o ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --product laz --vertical-crs EVRF2007 -o ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12 --vertical-crs EVRF2007 -o ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86 --country pl -o ./data

# PL-2000: godło albo bbox w CRS strefy; godło grubsze i bbox wymagają --scale
# zgodnej z arkuszami GUGiK (sekcja 1.6)
kartograf parse 6.179.12.20
kartograf elevation download --sheet 6.179.12.20 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf elevation download --sheet 7.171.21 --scale 1:2000 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf elevation download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --sheet-system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 -o ./data

# Kampanie GUGiK (sekcja 4): domyślnie najnowsza; `--all-campaigns`
# pobiera wszystkie kampanie arkusza
kartograf elevation download --sheet N-34-130-D-d-2-4 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf elevation download --sheet N-34-139-C-a-3-1 --full-sheet --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # + najnowszy pełny lot w full_sheet/ (sekcja 4.2)
kartograf elevation download --sheet N-34-130-D-d-2-4 --product laz --all-campaigns --vertical-crs EVRF2007 -o ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --product laz --all-campaigns --country pl --vertical-crs EVRF2007 -o ./data

# Wybór roku danych (NMT, NMPT, orto, LAZ; sekcja 4.1)
kartograf elevation download --sheet N-34-130-D-d-2-4 --year 2025 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # najnowszy lot z 2025
kartograf elevation download --sheet N-34-130-D-d-2-4 --year 2025 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # wszystkie loty z 2025
kartograf imagery download --sheet N-34-130-D-d-2-4 --product orto --year 2024 -o ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --max-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --min-year 2023 --max-year 2024 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
kartograf elevation download --sheet N-34-130-D-d-2-4 --min-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # najnowsza, nie starsza niż 2024
kartograf elevation download --bbox 530000,382000,533000,386000 --all-campaigns --min-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
```

Pełna lista komend i opcji: `kartograf --help`, `kartograf <grupa> <komenda> --help`.
Jakie lata, rozdzielczości i formaty ma obszar: `kartograf elevation
availability` (sekcja 1.7).

**Warianty NMT i NMPT (rejestr, od 0.8.0).** Rozdzielczość, układ
wysokości i format arkusza PL wybiera jeden rejestr wariantów — ten sam
dla walidacji CLI i biblioteki, `--help`, `kartograf elevation
list-sources` (kolumna `WYBOR` podaje gotowe flagi każdego wariantu),
segmentu magazynu i wyboru rekordu skorowidza
([ADR-041](DECISIONS.md); biblioteka: `kartograf.sources.variants.variants()`).
Siatki ASC (bez `--format`; format produktu):

| Produkt | EVRF2007 | KRON86 |
|---|---|---|
| NMT | `0.15m`, `0.5m`, `0.6m`, `1m`, `5m`, `10m` | `0.5m`, `1m` |
| NMPT | `0.5m`, `0.6m`, `1m` | `0.5m`, `1m` |

- `--resolution` przyjmuje tylko dokładne etykiety z rejestru: `0,5m`
  albo `50cm` to `Error: PL nie ma rozdzielczosci 0,5m dla NMT - dostepne:
  EVRF2007: 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; KRON86: 0.5m, 1m`. Etykieta
  jest członem segmentu: `nmt/pl_1992_0.5m_evrf2007/`.
- `--product nmpt` wymaga `--resolution` (do 0.7.x NMPT było tylko
  1 m): bez flagi `Error: --resolution wymagane dla NMPT PL: EVRF2007:
  0.5m, 0.6m, 1m; KRON86: 0.5m, 1m` (kod 1, przed siecią) — dotychczasowe
  wywołania uzupełnij o `--resolution 1m`. Wyjątek: wycinek `--cutout`
  (tylko 1 m, sekcja 1.3) przyjmuje brak `--resolution`.
- Skorowidz GUGiK publikuje ten sam arkusz także jako archiwum (np.
  `.asc` i `.xyz.zip` tego samego zgłoszenia); bez `--format` Kartograf
  bierze wyłącznie rekord siatki ASC (format rekordu i końcówka URL
  `.asc`; wyjątek: 42 siatki NMT 2019 kampanii 72675 mają nazwę `.xyz`,
  w środku AAIGrid — zapisywane jako `.asc`), nigdy archiwum.

**Archiwa GUGiK (`--format`).** Pozostałe formaty skorowidza NMT/NMPT
(publikowane do 2020) są wariantami rejestru pobieranymi jako **pliki
źródłowe 1:1**: `XYZ` (ASCII XYZ GRID, ZIP), `ASCII-NMT` (punkty X Y Z,
ZIP), `TBD` (punkty i linie struktury, ZIP), `TIN` (ESRI TIN, ZIP),
`TTN` (Intergraph TTN), `GRD` (Intergraph GRD), `DXF` i `DGN`
(warstwice); NMPT ma archiwa `XYZ` 0.5m i 1m w KRON86. Rozdzielczości
i układy wysokości archiwów (np. TBD 1–25 m w obu układach, 30–50 m
tylko KRON86): `kartograf elevation list-sources`.

- Plik trafia do magazynu jak arkusz siatki (wersje w `versions/`,
  sidecar, kampanie, `full_sheet/`), bez konwersji, wycinka i mozaiki;
  segment niesie token formatu: `nmt/pl_1992_tbd_25m_kron86/`. Pliku
  nie otwiera Kartograf — to zadanie programu, który obsługuje format
  (sekcja 7).
- Arkusze archiwum mają różne skale (m.in. 1:25000 i 1:10000, PL-2000),
  więc wyznacza je skorowidz: rekordy wariantu z zakresu lat, których
  rama przecina obszar zadania (`--sheet` = rama godła, `--bbox`,
  obwiednie obiektów `--geometry`); arkusz stykający się z obszarem
  tylko krawędzią się nie liczy. Brak takich rekordów to `Error:
  Skorowidz GUGiK nie ma plikow ... - dostepne dane obszaru: kartograf
  elevation availability`.
- `--scale` i `--cutout` z archiwum kończą się `Error:` przed siecią;
  `--sheet-system` jest wymagane jak dla siatek. Wariant z jedną
  wartością nie wymaga `--resolution` (`TIN`, `TTN` — bez rozdzielczości;
  `GRD` — tylko `5m`).
- Treść jest sprawdzana tylko co do formatu (kompletny ZIP, sygnatura
  TTN, nagłówek Intergraph, sekcje DXF); pokrycie archiwów nie jest mierzone.

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
`--year` poza LAZ kończył się `Error:`) — tylko PL, bez `--cutout`
(sekcja 4.1).

### 1.2 Selekcja obszaru i wybór kraju (`--country`)

```bash
kartograf imagery download --bbox 771000,509000,772000,510000 --product orto --country pl --sheet-system 1992 -o ./data
kartograf elevation download --geometry area.shp --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
kartograf elevation download --geometry zlewnia.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
```

- Domyślne `--bbox-crs` to `EPSG:2180`; plik geometrii: SHP albo GPKG.
  `--layer` wybiera warstwę GPKG. Bez tej flagi GPKG z wieloma warstwami
  używa pierwszej; biblioteka emituje jeden `Notice`
  `geometry_layer_default` z wybraną warstwą, listą pozostałych
  i podpowiedzią `--layer NAZWA` (CLI: `Info:`, również przy `-q`).
  Dotyczy też `landcover download`, `soil download` i `soil hsg` (`LandCoverManager`,
  `HSGCalculator`). Niskopoziomowe funkcje `kartograf.core.geometry`
  (np. `find_sheets_for_geometry`) wywołane bez `layer=` logują
  ostrzeżenie (`logger.warning`) — podaj `layer=`, aby wskazać warstwę jawnie.
- PL bez `--cutout` zapisuje **listę arkuszy** w hierarchii godeł;
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
  `--vertical-crs KRON86`, rozdzielczość, której CUZK nie ma, np.
  `--resolution 1m` albo `0.5m`, oraz `--format` — w zwykłej, nie per-krajowej
  postaci) na obszarze objętym obwiedniami obu krajów same przełączają
  `auto` na PL (komunikat `Info:`). W Pradze czy Brnie taka flaga kieruje
  więc zadanie do GUGiK, który nie ma tam danych (błąd pobrania); błąd
  przed siecią dostaje dopiero obszar poza prostokątem PL. LAZ na
  obszarze sięgającym CZ wymaga jawnego `--country pl`. `--sheet-system`
  jest wymagane dla części PL zadania (bez `--cutout`), więc nie wybiera
  kraju.
- Obszar sięgający CZ (`--country cz` albo `auto` z częścią CZ) wymaga
  `--cutout --horizontal-crs <układ>`: CUZK nie ma trybu arkuszy dla
  obszaru ([ADR-038](DECISIONS.md)). Pod `auto` część PL jest wtedy też
  wycinkiem WCS (tylko 1 m, NMT/NMPT, bez wyboru kampanii); arkusze PL
  z takiego obszaru pobiera `--country pl`. Bez `--cutout` — `Error:`
  przed siecią z tą podpowiedzią.
- Pod `auto` przycięcie do obwiedni kraju jest komunikowane jako `Info:`;
  oryginalny bbox zachowuje `extra.parent_request`, cały bbox pobiera
  `--country pl`.
- Pełne reguły (przycinanie, kody wyjścia, częściowy sukces): SCOPE 3.2,
  ARCHITECTURE 4.6, ADR-023.

### 1.3 Jeden wycinek (`--cutout`)

`--cutout` przełącza `--bbox`/`--geometry` z listy arkuszy na **jeden**
GeoTIFF obszaru; układ wyniku podaje wymagane `--horizontal-crs`
(`EPSG:2180`, `EPSG:5514`, `EPSG:3045`). `--horizontal-crs` bez
`--cutout` i `--cutout` z `--sheet` to `Error:` przed siecią.

```bash
# NMT 1 m, wycinek WCS w układzie źródłowym lub po lokalnej reprojekcji
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --cutout --horizontal-crs EPSG:2180 --vertical-crs EVRF2007 -o ./data
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --cutout --horizontal-crs EPSG:5514 --vertical-crs EVRF2007 -o ./data
# NMPT 1 m, oba układy wysokościowe (tu KRON86); --resolution można pominąć (wycinek jest tylko 1 m)
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmpt --vertical-crs KRON86 --cutout --horizontal-crs EPSG:2180 -o ./data
# pogranicze: osobne wycinki PL + CZ, ten sam układ i parent_request
# (wycinek PL ma tylko 1 m, część CZ wymaga 2m albo 5m — wartości per kraj)
kartograf elevation download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:2180 --product nmt --resolution pl=1m,cz=2m --vertical-crs EVRF2007 -o ./data
# NMT 5 m (i każda rozdzielczość poza 1 m): arkusze OpenData, bez --cutout
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --resolution 5m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
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
- Wycinek jest **tylko 1 m** z siatki ASC: `--resolution 1m` albo bez
  `--resolution`. Inna rozdzielczość kończy się przed siecią (kod 1)
  komunikatem `Error: wycinki PL (--cutout) sa tylko 1 m (WCS GUGiK);
  arkusze 0.5m: pomin --cutout (arkusze bez --cutout); wycinek:
  --resolution 1m albo pomin --resolution`, a archiwum (`--format`, sekcja
  1.1) — `Error: --cutout dziala tylko z siatka ASC 1m (wycinek z WCS
  GUGiK); --format TBD to pliki zrodlowe arkuszy - pomin --cutout`.
- Wybór roku (`--year`, `--min-year`, `--max-year`),
  `--all-campaigns` i `--full-sheet` z `--cutout` są
  odrzucane (`Error:`). Podobnie `--cutout` dla orto/LAZ;
  arkusze innych rozdzielczości pobieraj bez `--cutout`. Szczegóły:
  [ADR-035](DECISIONS.md), [ADR-038](DECISIONS.md), ARCHITECTURE 4.3.

### 1.4 Czechy (CUZK)

```bash
# DMR 5G (2 m), godło TM33 (ten kafel leży w większości w Niemczech — głównie nodata)
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv -o ./data
kartograf elevation download --sheet CTES96 --product nmt --vertical-crs Bpv -o ./data # DMR 4G (5 m), godło SM5, kraj z godła
kartograf elevation download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m -o ./data # Bpv -> EVRF2007 (EPSG:5621)
# obszar CZ = jeden wycinek (--cutout); reprojekcja (tylko --bbox/--geometry,
# nie godło) lokalnie przypiętą operacją
kartograf elevation download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --cutout --horizontal-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv -o ./data
# pogranicze pod auto: osobne wycinki PL (WCS 1 m) i CZ, wspólny
# extra.parent_request; różne wartości dla krajów w postaci pl=...,cz=...
kartograf elevation download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:5514 --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv -o ./data
# bboxy w EPSG:5514 są na terytorium CZ ujemne — podaj je jako --bbox=... (bez spacji),
# inaczej argparse odczyta wartość jako nieznaną flagę
kartograf elevation download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --cutout --horizontal-crs EPSG:5514 --resolution 5m --product nmt --vertical-crs Bpv -o ./data
```

`kartograf parse` obsługuje tylko godła PL (PL-1992/PL-2000); godła CZ
(TM33, SM5) przyjmuje `kartograf elevation download`.

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
  i `--bbox`/`--geometry` (wycinek, `--cutout`) są wycinane z usługi:
  `--resolution` wymagane, `2m` (DMR 5G) albo `5m` (DMR 4G).

- Obszar CZ (`--bbox`/`--geometry`) to zawsze jeden wycinek i wymaga
  `--cutout --horizontal-crs` (natywnie `EPSG:5514`); bez `--cutout`
  `Error:` przed siecią. PL bez `--cutout` daje listę arkuszy.
- Porażka jednego kraju pod `auto` (brak danych albo awaria źródła) przy
  sukcesie drugiego kończy się kodem 0: na stderr `Warning:` o częściowym
  sukcesie i `Error:` z przyczyną porażki; kod 1, gdy żaden kraj nie dał
  wyniku albo `--country` było jawne.
- Natywnie S-JTSK/Bpv (EPSG:5514); `KRON86` dla CZ jest nieosiągalny.
  Szczegóły: SCOPE 2.2 i 3.2, ARCHITECTURE 4.4–4.6.
- Magazyn wersji (0.8.0): arkusz CZ i wycinek CZ leżą jako wersje
  w `<segment>/versions/`, ścieżka arkusza i `bbox/<współrzędne>.tif` to
  hardlinki. Arkusz SM5 ma tani sygnał (`ETag`/`Last-Modified` pliku
  `openzu`, zapisany w `extra.http` sidecara wersji): domyślnie jedno
  `HEAD` na plik z lokalną wersją — nowsza treść daje dopisek `; dostepna
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
kartograf soil download --bbox 626000,480000,628000,482000 --property clay --depth 0-5cm --stat mean -o ./data
#   soil/global_soilgrids_clay_0-5cm_mean/bbox/626000_480000_628000_482000.tif: nowa wersja 2.0_717f0989
# Segment niesie każdy parametr treści (lowercase), więc --property sand
# dla tego samego obszaru to osobny plik; parametry są też w sidecarze
# (request.property/depth/stat, request.year, request.format).

# Tylko wybrane warstwy BDOT10k (GPKG) + oryginalny ZIP, bbox w WGS84,
# 4 powiaty równolegle, bez linii statusu (Info:/Warning:/Error: zostają)
kartograf landcover download --source bdot10k --bbox 16.70,50.45,16.80,50.55 \
    --bbox-crs EPSG:4326 --layers SWRS,PTWP --keep-raw --workers 4 -q -o ./data
#   -> landcover/pl_bdot10k_gpkg_ptwp-swrs/teryt/<T>.gpkg
#      i landcover/pl_bdot10k_gpkg_zip/teryt/<T>.zip

# Hydrologic Soil Groups dla metody SCS-CN (wejścia clay/sand/silt w tym samym magazynie)
kartograf soil hsg --bbox 626000,480000,628000,482000 --depth 0-5cm --stats -o ./data
#   soil/global_soilgrids_{clay,sand,silt}_0-5cm_mean/bbox/...: nowa wersja 2.0_<sha8>
#   hsg/global_soilgrids_0-5cm_mean/bbox/626000_480000_628000_482000.tif: nowa wersja 2.0_470ef3d9
# Ponownie (także z --force, gdy treść wejść się nie zmieniła): ... uzyta ponownie 2.0

# Przegląd źródeł/warstw i cache metadanych
kartograf landcover list-sources
kartograf soil list-layers
kartograf cache stats
kartograf cache clear
kartograf cache path
```

`--output` to katalog magazynu (wersje w `versions/`, ścieżka standardowa
= hardlink; ARCHITECTURE 3.3 reguła 8); `soil hsg -o plik.tif` to
`Error:` (plik poza magazynem: `hsg_from_rasters`). `--teryt` dotyczy tylko
BDOT10k (CORINE/SoilGrids: `--sheet`, `--bbox`, `--geometry`). BDOT10k
z `--bbox`/`--sheet`/`--geometry` pobiera wszystkie powiaty obszaru (lista
z WFS PRG, odpowiedzi w cache metadanych — `cache stats` liczy je
w `Wpisy TERYT`); błąd jednego powiatu to `Error: <TERYT>: ...`, reszta
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

- `--bbox`/`--geometry` z `--sheet-system 2000` (bez `--cutout`): wymagane —
  obszar jest rozbijany na arkusze w tej skali;
- `--sheet` z godłem PL-2000 1:10000 (np. `7.171.21`): wymagane — godło
  jest rozwijane do potomków w tej skali (`kartograf parse <godło>
  --descendants <skala>` pokazuje listę przed pobraniem);
- drobniejsze godło PL-2000 (np. `7.171.21.23`): opcjonalne — bez flagi
  pobierany jest ten arkusz, z flagą jego potomkowie w tej skali;
- nie dotyczy LAZ (kafle wybierane z WFS), CZ (godło TM33/SM5 albo
  wycinek z usługi) ani wycinka `--cutout`.

**PL-1992 — flaga niedozwolona.** GUGiK publikuje arkusze PL-1992 tylko
z 7-członowym godłem (np. `N-34-130-D-d-2-4`), oznaczanym w Kartografie
jako `1:10000`; grubsze godło (np. `N-34-130-D`) i `--bbox`/`--geometry`
z `--sheet-system 1992` zawsze dają te arkusze, a `--scale` z zadaniem PL-1992
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
kartograf elevation download --sheet 7.171.21 --scale 1:2000 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf elevation download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --sheet-system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 -o ./data
```

**Co się dzieje przy niedopasowaniu.** Brak arkusza o zamówionym godle to
brak pokrycia (`NoCoverageError`), nigdy ciche pobranie zastępcze (np.
arkusza PL-1992). Skorowidz zwraca jednak arkusze z miejsca zapytania
(np. potomka zamówionego godła), więc Kartograf podpowiada skalę, w której
dane tam są:

- pojedyncze godło: `Error:` (kod 1), a w treści błędu np.
  `Dostepny potomek 5.167.25.13 - uzyj --scale 1:2000`;
- lista arkuszy (`--bbox`/`--geometry`, godło rozwijane): arkusze bez
  danych mają status `no_coverage` (ikona `0` na pasku postepu), na stderr `Warning: GUGiK nie ma
  danych dla N z M arkuszy ...` (kod 0, gdy pobrano choć jeden arkusz)
  albo — gdy żaden arkusz nie ma danych — `Error: GUGiK nie ma danych dla
  zadnego z M arkuszy obszaru` (kod 1); w obu przypadkach pod spodem
  podpowiedzi `Info: Dostepny potomek <godło> - uzyj --scale <skala>`;
- gdy skorowidz ma ten obszar w drugim układzie, podpowiedź wskazuje jego
  godło albo `--sheet-system <układ> --scale <skala>`;
- NMT i NMPT (od 0.7.2; od 0.8.0 ze skorowidza WFS): gdy arkusza nie ma
  w wybranym wariancie, a skorowidz GUGiK ma go w innym wariancie
  z rejestru (sekcja 1.1), podpowiedź to np. `Skorowidz GUGiK ma ten
  arkusz w NMT 1m EVRF2007 - uzyj --resolution 1m` (albo `--vertical-crs
  KRON86`, `--format XYZ`) — przy pojedynczym godle w treści `Error:`
  (kod 1), przy liście arkuszy jako `Info:`. Najpierw podpowiadane są
  inne warianty tego samego formatu (np. inna rozdzielczość siatki),
  inne formaty (archiwa) tylko wtedy, gdy takich nie ma. GUGiK ma duże
  braki pokrycia EVRF2007, także NMT 5 m (np.
  `N-34-130-D-d --resolution 5m`: 6 z 16 arkuszy tylko w 1 m).
  Inne rozdzielczości i formaty arkusza przychodzą w tej samej odpowiedzi
  WFS (bez dodatkowych zapytań); drugi układ wysokości kosztuje jedno
  zapytanie WFS do jego usługi (usługa z błędem jest pomijana do końca
  zadania); podpowiedzi trafiają do cache metadanych razem z brakiem
  pokrycia. Pełny obraz wariantów obszaru daje `kartograf elevation
  availability` (sekcja 1.7).

**Jak ustalić właściwą skalę.** Najprościej z podpowiedzi CLI: skala
w `uzyj --scale ...` to skala arkusza, który GUGiK faktycznie opublikował
(może to być 1:2000, ale też np. 1:1000). Skalę godła i jego potomków
pokazuje `kartograf parse` (`--descendants <skala>`). Jeśli różne miejsca
obszaru mają arkusze w różnych skalach, jedno wywołanie z jedną `--scale`
pobierze tylko część — pozostałe arkusze dociągnij kolejnym wywołaniem
z podpowiedzianą skalą.

### 1.7 Raport dostępności (`elevation availability`)

`kartograf elevation availability` odpowiada **przed pobraniem**, dla
jakich lat, układów arkuszy, rozdzielczości, układów wysokości i formatów
obszar ma komplet pełnych arkuszy NMT/NMPT (LAZ: kafli) według skorowidza
GUGiK. Czyta wyłącznie skorowidz WFS (ten sam, z którego pobiera
`elevation download`) i maskę lądu PRG; żadnego pliku danych nie pobiera.
Obszar wybiera się jak w `elevation download`: `--sheet` (godło PL-1992
albo PL-2000; kraj z godła), `--bbox` (`--bbox-crs`) albo `--geometry`
(`--layer`) — dwa ostatnie z `--country pl` (dziś jedyny kraj raportu;
bez flagi `Error: --country wymagane z --bbox/--geometry: pl (GUGiK)`).
`--year`/`--min-year`/`--max-year` zawężają roczniki skorowidza.

```bash
kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000
kartograf elevation availability --product nmpt --sheet M-34-64-D-d-2-1
kartograf elevation availability --product laz --country pl --geometry zlewnia.gpkg --layer catchments --min-year 2020
kartograf elevation availability --product nmt --country pl --bbox 339000,744800,343000,747000 --details
kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000 --json > krakow.json
```

Kraków (NMT, bbox 4 x 4 km; wydruk na żywo 2026-10-15):

```
Dostepnosc NMT PL wg skorowidza GUGiK: obszar 16,00 km2, w tym lad 16,00 km2

  ROK   NALOT                   UKLAD    ROZDZ.  WYSOKOSCI  FORMAT     ARKUSZE TAK/NIE  KOMPLET
  2025  2025-04-28              PL-1992  1m      EVRF2007   ASC        6/0              tak
  2024  2024-06-21..2024-07-30  PL-1992  1m      EVRF2007   ASC        6/0              tak
  2023  2023-09-08              PL-1992  1m      EVRF2007   ASC        6/0              tak
  2023  2023-03-17              PL-2000  1m      EVRF2007   ASC        15/0             tak
  2022  2022-06-03              PL-1992  1m      EVRF2007   ASC        6/0              tak
  2021  2021-10-04..2021-10-05  PL-2000  1m      EVRF2007   ASC        15/0             tak
  2019  2019-10-17              PL-1992  1m      EVRF2007   ASC        6/0              tak
  2019  2019-08-26              PL-1992  5m      EVRF2007   ASC        6/0              tak
  2019  2019-08-26              PL-1992  5m      EVRF2007   ASCII-NMT  6/0              tak
  2018  2018-04-21              PL-1992  1m      EVRF2007   XYZ        4/0              nie: brak arkuszy dla 6,66 km2
  2018  2018-04-22              PL-1992  5m      EVRF2007   XYZ        2/0              nie: brak arkuszy dla 9,34 km2
  2018  2018-04-22              PL-1992  25m     EVRF2007   TBD        2/0              nie: brak arkuszy dla 9,34 km2
  2017  2017-10-21..2017-11-05  PL-1992  1m      KRON86     ASC        6/0              tak
  2017  2017-10-21..2017-11-05  PL-1992  1m      KRON86     XYZ        6/0              tak
  2015  2015-05-29              PL-1992  1m      KRON86     XYZ        4/0              tak
  2012  2012-07-06..2012-07-07  PL-1992  1m      KRON86     ASC        6/0              tak
  2012  2012-07-06..2012-07-07  PL-1992  1m      KRON86     XYZ        6/0              tak
  2009  2009-01-01              PL-1992  15m     KRON86     TBD        4/0              tak
  2009  2009-01-01              PL-1992  -       KRON86     TIN        4/0              tak
  2009  2009-01-01              PL-1992  -       KRON86     TTN        4/0              tak

Najnowsza kompletna kombinacja: 2025 PL-1992 1m EVRF2007 ASC
  Pobranie (dodaj --output KATALOG): kartograf elevation download --product nmt --country pl --bbox 565000,242000,569000,246000 --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --year 2025
  W projekcie: kartograf project add NAZWA elevation download --product nmt --country pl --bbox 565000,242000,569000,246000 --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --year 2025
```

Pomorze (NMT, bbox 4 x 2,2 km na wybrzeżu — większość obszaru to morze):

```
Dostepnosc NMT PL wg skorowidza GUGiK: obszar 8,80 km2, w tym lad 86,38 ha

  ROK   NALOT                   UKLAD    ROZDZ.  WYSOKOSCI  FORMAT  ARKUSZE TAK/NIE  KOMPLET
  2025  2025-01-30              PL-1992  0.5m    EVRF2007   ASC     0/4              nie: 4 niepelne
  2025  2025-04-21              PL-1992  5m      EVRF2007   ASC     3/0              nie: brak arkuszy dla 0,88 ha
  2023  2023-04-06..2023-09-06  PL-1992  5m      EVRF2007   ASC     3/0              nie: brak arkuszy dla 0,88 ha
  2022  2022-09-04              PL-1992  0.5m    EVRF2007   ASC     1/3              nie: 3 niepelne
  2022  2022-06-17              PL-1992  1m      EVRF2007   ASC     3/0              nie: brak arkuszy dla 0,88 ha
  2021  2021-10-09              PL-1992  0.5m    EVRF2007   ASC     1/3              nie: 3 niepelne
  2020  2020-06-01              PL-1992  5m      EVRF2007   XYZ     3/0              nie: brak arkuszy dla 0,88 ha
  2017  2017-05-27              PL-1992  1m      KRON86     XYZ     3/0              nie: brak arkuszy dla 0,88 ha
  2011  2011-04-27              PL-1992  1m      KRON86     ASC     3/0              nie: brak arkuszy dla 0,88 ha
  2011  2011-04-27              PL-1992  1m      KRON86     XYZ     3/0              nie: brak arkuszy dla 0,88 ha
  2010  2010-07-04              PL-1992  25m     KRON86     TBD     3/0              tak
  2005  2005-01-01              PL-1992  25m     KRON86     TBD     3/0              tak
  2005  2005-01-01              PL-1992  25m     KRON86     DXF     3/0              tak
  2005  2005-01-01              PL-1992  -       KRON86     TIN     3/0              tak
  2005  2005-01-01              PL-1992  -       KRON86     TTN     3/0              tak

Najnowsza kompletna kombinacja: 2010 PL-1992 25m KRON86 TBD
  Pobranie (dodaj --output KATALOG): kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TBD --resolution 25m --vertical-crs KRON86 --year 2010
  W projekcie: kartograf project add NAZWA elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TBD --resolution 25m --vertical-crs KRON86 --year 2010
```

Jak czytać tabelę:

- **Kombinacja** = rok warstwy rocznej skorowidza, układ arkuszy
  (PL-1992/PL-2000), rozdzielczość, układ wysokości i format wariantu
  z rejestru (sekcja 1.1); archiwa (`XYZ`, `TBD`, `TIN`...) są
  kombinacjami do pobrania jak siatki ASC. `NALOT` to zakres dat
  pozyskania rekordów, `-` w `ROZDZ.` — format bez rozdzielczości
  (TIN, TTN). LAZ: kombinacja = rok, układ i układ wysokości kafli,
  `ROZDZ.` = gęstość nominalna z WFS (np. `5 pkt/m2`), `FORMAT` = `LAZ`.
- **TAK/NIE** to deklaracja skorowidza `calyArkuszWypelnionyTrescia`
  (LAZ: `czy_ark_wypelniony`): `6/0` = 6 arkuszy z pełnym rekordem
  kombinacji, 0 arkuszy wyłącznie z rekordami niepełnymi. NIE mówi tylko,
  że arkusz nie jest wypełniony w całości — brak może wynosić od 1 % do
  99 %; raport **nie mierzy treści** plików (pokrycie arkusza mierzy
  dopiero pobranie, sekcja 4.1).
- **KOMPLET** `tak` = cały ląd obszaru leży w ramach pełnych (TAK)
  arkuszy kombinacji. Ląd to granica państwa PRG (`A00`) bez morza
  terytorialnego i morskich wód wewnętrznych (`W02`, `W03`) — na
  Pomorzu 86,38 ha z 8,80 km2; morze nie wymaga arkuszy. Pomiar na
  siatce 1 m (środki pikseli), bez progu tolerancji. `nie: N niepelne`
  = N arkuszy obszaru ma w tej kombinacji tylko rekordy NIE; `nie: brak
  arkuszy dla X` = X lądu nie leży w żadnym arkuszu kombinacji (np.
  2018 w Krakowie: archiwa XYZ/TBD tylko dla części obszaru).
- Obszar jest ten sam, który pokrywa pobranie: `--sheet` = rama godła
  (pomiar pomija pas 1 m przy ramie — rama liczona z godła różni się od
  ramy GUGiK o centymetry), `--bbox` i `--geometry` (obwiednie obiektów,
  jak arkusze `elevation download`) mierzone dokładnie; LAZ — obwiednia
  arkusza albo całej geometrii, jak przy pobieraniu kafli. Arkusz
  stykający się z obszarem tylko krawędzią nie należy do kombinacji.
- Kolejność: rok malejąco, potem układ arkuszy, rozdzielczość, układ
  wysokości i format.

**Podpowiedź pobrania.** Stopka podaje najnowszą kompletną kombinację
i polecenie jej pobrania — **bez `--output`**: linię `Pobranie` wklej po
dopisaniu `--output KATALOG`, linię `W projekcie` po nazwie zadania
(manifest, sekcja 8; magazyn pochodzi z projektu). Polecenie powtarza
obszar zadania, dopisuje `--sheet-system`, wariant (`--format` dla
archiwów, `--resolution`, `--vertical-crs`) i `--year`; dla PL-2000 —
po jednym poleceniu na skalę arkuszy kombinacji (`--scale`), a gdy
w którymś arkuszu najnowszy rekord roku jest NIE, a pełny rekord tego
roku istnieje — `--full-sheet`. Bez kompletnej kombinacji stopka mówi
`Zadna kombinacja nie pokrywa calego ladu obszaru pelnymi arkuszami
(arkusze niepelne i brakujace: --details)`.

`--details` dopisuje dla każdej kombinacji godła arkuszy niepełnych, ląd
bez arkuszy i polecenie pobrania (fragment, Pomorze):

```
Szczegoly kombinacji:
  2025 PL-1992 0.5m EVRF2007 ASC: nie: 4 niepelne
    arkusze niepelne (4): N-33-58-A-c-1-3, N-33-58-A-c-1-4, N-33-58-A-c-2-3, N-33-58-A-c-3-1
    kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
  2023 PL-1992 5m EVRF2007 ASC: nie: brak arkuszy dla 0,88 ha
    lad bez zadnego arkusza kombinacji: 0,88 ha
    kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --resolution 5m --vertical-crs EVRF2007 --year 2023 --full-sheet
  2005 PL-1992 KRON86 TIN: tak
    kartograf elevation download --product nmt --country pl --bbox 339000,744800,343000,747000 --sheet-system 1992 --format TIN --vertical-crs KRON86 --year 2005
```

`--json` drukuje raport jako JSON (schemat `kartograf-availability/1`) —
dokładnie ten tekst, który zwraca `check_availability(...).to_json()`
w bibliotece (sekcja 2); pola: `request`, `checked_at`, `areas`
(`area_m2`, `land_m2`), `combinations` (m.in. `source` = klucz
deskryptora, `year`, `acquisition_dates`, `published`, `campaigns`,
`horizontal`, `resolution`, `vertical_crs`, `format`, `densities`,
`complete`, `sheets_full`, `sheets_partial`, `uncovered_m2`,
`download_hint` — polecenia bez przedrostka `kartograf `), `notices`,
`ok`, `schema`. Pola `sheets_missing` i `size_bytes` są dziś puste
(`[]`/`null`). Początek (Kraków):

```json
{
  "request": {
    "product": "nmt",
    "country": "pl",
    "bbox": [565000.0, 242000.0, 569000.0, 246000.0],
    "bbox_crs": "EPSG:2180",
    "min_year": null,
    "max_year": null
  },
  "checked_at": "2026-10-15T20:50:50+00:00",
  "areas": [
    {"country": "PL", "crs": "EPSG:2180", "bounds": [565000.0, 242000.0, 569000.0, 246000.0],
     "area_m2": 16000000.0, "land_m2": 16000000.0}
  ],
  "combinations": [
    {
      "country": "PL", "product": "nmt", "source": "pl.gugik.nmt_1m", "year": 2025,
      "acquisition_dates": ["2025-04-28", "2025-04-28"],
      "horizontal": "PL-1992", "resolution": "1m", "vertical_crs": "EVRF2007", "format": "ASC",
      "complete": true,
      "sheets_full": ["M-34-64-D-d-1-2", "M-34-64-D-d-1-4", "M-34-64-D-d-2-1", "..."],
      "sheets_partial": [], "uncovered": false, "uncovered_m2": 0.0,
      "download_hint": ["elevation download --product nmt --country pl --bbox 565000,242000,569000,246000 --sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --year 2025"]
    }
  ]
}
```

(Fragment skrócony ręcznie; prawdziwy wydruk ma wcięcie 2 spacje,
każdą wartość listy w osobnej linii i wszystkie pola.)

- **Bez danych to odpowiedź, nie błąd:** obszar bez arkuszy w skorowidzu
  daje `Brak arkuszy NMT dla obszaru w skorowidzu GUGiK` (LAZ: `kafli`)
  i kod 0. Awaria skorowidza albo PRG (sieć, strona WFS niespójna,
  raport OGC) to `Error:` i kod 1 — nigdy pusty raport. Zakres lat bez
  żadnego rocznika usługi: `Error: --year 2030: skorowidz GUGiK NMT nie
  ma rocznika ... - dostepne roczniki: ...`.
- **`Info:`** (kod `index_unsupported` w bibliotece) wymienia rekordy
  obszaru, których Kartograf nie pobiera: format rekordu niezgodny
  z plikiem, wariant spoza rejestru albo godło spoza układów PL-1992/PL-2000
  (np. 8-członowe godła ASCII NMT 10 m i części ASC 1 m, sekcja 7).
  Archiwa z rejestru nie trafiają do `Info:` — są kombinacjami.
- **Cache:** typy warstw WFS, rekordy obszaru z obrysami arkuszy i maska
  lądu PRG trafiają do cache metadanych (`.kartograf_cache.db`, TTL
  7 dni; `kartograf cache stats`: `Wpisy obszarow skorowidza`), więc
  ponowny raport dla tego samego obszaru nie pyta sieci (pomiar
  2026-10-15: 0,6–1,5 s zamiast ok. 5–7 s dla 16 km2). `--force`
  pomija odczyt cache, odpytuje skorowidz i PRG ponownie i nadpisuje
  wpisy.
- **Czas:** maska lądu jest rasteryzowana na siatce 1 m w pasach po
  4 Mpx, więc raport dla dużego obszaru (np. całej zlewni) liczy się
  odpowiednio dłużej (sekcja 7).
- **Projekt:** `availability` nie jest komendą danych projektu
  (`kartograf project add NAZWA elevation availability ...` = `Error:`);
  do manifestu dodaj polecenie z linii `W projekcie` (sekcja 8).

### 1.8 Granice, ewidencja, modele 3D budynków i archiwum BDOT10k

Grupy `boundaries` (granice PRG, `--product admin`), `cadastre` (EGiB,
`--product map`) i `models3d` (modele 3D budynków, `--product buildings`)
mają wspólny kształt (ADR-042): dokładnie jeden wybór — `--teryt` (paczka
jednostki), obszar `--bbox`/`--sheet`/`--geometry` (z `--country`) albo
`--whole-country` (plik krajowy; tylko `boundaries`) — oraz tryby
`--check-updates`/`--upgrade`/`--force`/`--plan`, `--workers` i `-q` jak
w pozostałych grupach. Każda grupa ma tylko swoje flagi treści (`--level`
w `boundaries`, `--lod`/`--year` w `models3d`; obca flaga to błąd parsera,
kod 2). Dziś wyłącznie Polska (`--country pl`; dane CZ dla tych grup dojdą
w kolejnym planie katalogu). Archiwum roczników BDOT10k jest w grupie
`landcover` (`--year`).

```bash
# Archiwum roczników BDOT10k: oryginalna paczka powiatu ZIP (GML albo SHP)
kartograf landcover download --source bdot10k --teryt 1261 --year 2024 --format SHP -o ./data
#   landcover/pl_bdot10k_shp_2024/teryt/1261.zip: nowa wersja 2024_5dbd678a
kartograf landcover download --source bdot10k --teryt 1261 --year 2022 --format SHP -o ./data
#   landcover/pl_bdot10k_shp_2022/teryt/1261.zip: nowa wersja 2022_6c64b1d3
kartograf landcover download --source bdot10k --teryt 1261 --year 2023 --format SHP -o ./data
#   landcover/pl_bdot10k_shp_2023/teryt/1261.zip: nowa etykieta 2023 (plik identyczny z 2022)
# Obszar = paczka każdego powiatu (PRG); --workers pobiera powiaty równolegle
kartograf landcover download --source bdot10k --year 2018 --format GML --bbox 557000,244000,559000,246000 --workers 2 -o ./data
#   landcover/pl_bdot10k_gml_2018/teryt/1206.zip: nowa wersja 2018_b8b23714
#   landcover/pl_bdot10k_gml_2018/teryt/1261.zip: nowa wersja 2018_f8f5ead1
#   Nowe: 2, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 0 (./data)

# Modele 3D budynków (CityGML): wydanie wybierają --lod i --year
kartograf models3d download --product buildings --lod 1 --year 2024 --teryt 1261 -o ./data
#   models3d/pl_buildings_lod1_2024/teryt/1261.zip: nowa wersja 2024_dff392bb
kartograf models3d download --product buildings --lod 2 --country pl --bbox 566000,243000,566500,243500 -o ./data
#   Info: buildings: powiaty obszaru wg PRG (1): 1261
#   models3d/pl_buildings_lod2_2017/teryt/1261.zip: nowa wersja 2017_de14ed18

# Granice PRG: jednostki poziomu --level przecinające obszar (jeden GPKG),
# paczka województwa (GML wszystkich poziomów) albo plik krajowy (SHP)
kartograf boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000 -o ./data
#   boundaries/pl_prg_gmina/bbox/550000_220000_590000_270000.gpkg: nowa wersja 2026-10-15_d8fd43e6
kartograf boundaries download --product admin --teryt 12 -o ./data
#   boundaries/pl_prg_gml/teryt/12.zip: nowa wersja 2026-10-15_919fce9d
kartograf boundaries download --product admin --country pl --whole-country -o ./data
#   Warning: admin PL: plik krajowy https://opendata.geoportal.gov.pl/prg/granice/00_jednostki_administracyjne.zip - 377419459 B (ok. 377 MB)
#   boundaries/pl_prg_shp/country/pl.zip: nowa wersja 2026-10-15_40b93870

# EGiB: eksport powiatu albo działki i budynki obszaru z usługi zbiorczej WFS
kartograf cadastre download --product map --teryt 1261 -o ./data
#   cadastre/pl_egib_gpkg/teryt/1261.gpkg: nowa wersja 2026-10-15_fd23bd6e
kartograf cadastre download --product map --country pl --bbox 565000,243000,567000,245000 -o ./data
#   cadastre/pl_egib/bbox/565000_243000_567000_245000.gpkg: nowa wersja 2026-10-15_14c95c95

# Ponownie: lokalna wersja bez zapytań; --check-updates: brak taniego sygnału
kartograf boundaries download --product admin --teryt 12 -o ./data
#   boundaries/pl_prg_gml/teryt/12.zip: lokalna wersja 2026-10-15 (bez sprawdzania; --check-updates)
kartograf boundaries download --product admin --teryt 12 --check-updates -o ./data
#   12: nie da sie sprawdzic bez pobrania (2026-10-15)

# Źródła grup (z rejestru, bez sieci)
kartograf boundaries list-sources
kartograf cadastre list-sources
kartograf models3d list-sources
```

**Archiwum BDOT10k.** `--year R` (2014–2025) to rocznik archiwum GUGiK —
stan bazy z początku roku R — a nie rok aktualności obiektów. Paczka
powiatu jest zapisywana 1:1 (bez scalania w GPKG, więc bez `--layers`
i `--keep-raw`) i wymaga `--format GML` albo `SHP` (GPKG archiwum nie ma).
Bez `--year` `landcover download` pobiera bieżące paczki jak dotąd;
`--format GML` bez `--year` to `Error:` z podpowiedzią. Kody TERYT
zmieniają się w czasie (podział i łączenie powiatów): powiat bez paczki
w danym roczniku to `Error: <TERYT>: Zrodlo nie publikuje paczki ...
(HTTP 404)`, a pozostałe powiaty obszaru się pobierają. Kolejne roczniki
bywają identyczne (GUGiK nie zmienił danych powiatu): drugi dostaje status
`nowa etykieta <rok> (plik identyczny z <rok>)` i nie zajmuje miejsca —
to dowiązanie twarde do tych samych danych.

**Modele 3D.** `--lod 1` ma wydania 2019, 2021, 2022 i 2024 (`--year`
wymagany), `--lod 2` jedno wydanie 2017 (`--year` można pominąć, inny rok
to `Error:`); wydania wymieniają `--help` i komunikat błędu. Paczka
CityGML (ZIP) jest zapisywana 1:1, a układ wysokości z danych trafia do
sidecara (`vertical_crs`): LoD1 2019 i LoD2 2017 — EPSG:9650 (KRON86),
LoD1 2021, 2022, 2024 — EPSG:9651 (EVRF2007). LoD2 nie pokrywa całego
kraju (np. Szczecin i sąsiednie powiaty): brak paczki powiatu to
`Error: <TERYT>: ... (HTTP 404)` i kod 1, pozostałe powiaty się pobierają.
Pliki krajowe modeli (3,5–4,1 GB) nie są obsługiwane.

**Granice PRG.** Obszar wymaga `--level` (`wojewodztwo`, `powiat`,
`gmina`, `jednostka-ewidencyjna`, `obreb`): wynik to jeden GeoPackage
z pełnymi geometriami jednostek tego poziomu, które przecinają obszar (bez
przycinania), w EPSG:2180, z warstwą PRG (np. `A03_Granice_gmin`) i jej
polami (m.in. `JPT_KOD_JE`). `--teryt` przyjmuje tylko województwo
(2 cyfry: paczka GML poziomów A01, A02, A03, A05, A06); granice powiatu
pobierz obszarem (`--bbox`/`--geometry`). `--whole-country --country pl`
to plik krajowy SHP (ok. 377 MB) — jego rozmiar pojawia się jako
`Warning:` przed transferem.

**EGiB.** `--teryt` (4 cyfry) to eksport powiatu GUGiK: GeoPackage
z warstwami `dzialki`, `budynki` i `transakcje` (rejestr cen
nieruchomości), odświeżany co dobę — `--force` następnego dnia zwykle daje
nową wersję. Paczka województwa (ok. 1,4 GB) nie jest obsługiwana. Obszar
to działki i budynki z usługi zbiorczej WFS GUGiK w jednym GPKG
(EPSG:2180, warstwy `dzialki` i `budynki`): powiaty, które nie
zintegrowały swojej usługi, są lukami, a atrybuty zastrzeżone mają
wartość `brak_uprawnien`. Pole `DATA` (data stanu danych powiatu) nie
trafia do pliku — jego wartości są w sidecarze
(`extra.source.dropped_fields`), więc ta sama treść pobrana innego dnia
to ta sama wersja.

**Aktualność i wersje.** Paczki i obiekty usług GUGiK nie mają taniego
sygnału zmian: kolejne uruchomienie używa lokalnej wersji bez zapytań,
`--check-updates` raportuje `nie da sie sprawdzic bez pobrania`, a nową
treść daje `--force` (ta sama treść = `bez zmian`, inna = nowa wersja obok
starej). Etykieta wersji to rocznik archiwum albo rok modeli 3D, a dla PRG
i EGiB — data pobrania. Sidecar wersji niesie wybór (`request`), źródło
(`extra.source`: URL paczki albo usługa i liczba obiektów każdej
warstwy) i obszar zadania (`extra.parent_request`) — ARCHITECTURE 3.2
i 4.10.

---

## 2. Biblioteka Python

Każda komenda CLI ma jedną funkcję biblioteki z tymi samymi wyborami
(nazwy parametrów = nazwy flag w `snake_case`) i tym samym wynikiem
(ADR-037): `kartograf elevation download` i `kartograf imagery download` =
`download_data`/`check_data`, `landcover download` i `soil download` =
`LandCoverManager.download`/`.check`, `soil hsg` = `HSGCalculator.calculate_hsg`/`.check_hsg`,
`elevation availability` = `check_availability`,
`boundaries download`, `cadastre download` i `models3d download` =
`download_collection`/`check_collection`. Błąd wejścia
to `ValidationError` z tekstem jak po `Error:` w CLI; komunikaty o danych
(CLI: `Info:`/`Warning:`) to `Notice` w polu `notices` wyniku i przez
`on_notice`.

```python
from kartograf import BBox, check_data, download_data

# = kartograf elevation download --product nmt --bbox 18.60,49.73,18.66,49.76
#   --bbox-crs EPSG:4326 --country auto --resolution pl=1m,cz=2m
#   --vertical-crs pl=EVRF2007,cz=Bpv --cutout --horizontal-crs EPSG:3045 -o ./data
selection = dict(
    product="nmt",
    output_dir="./data",
    bbox=BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326"),
    country="auto",
    resolution={"pl": "1m", "cz": "2m"},     # jedna wartość: resolution="1m"
    vertical_crs={"pl": "EVRF2007", "cz": "Bpv"},
    cutout=True,                             # jeden wycinek na kraj
    horizontal_crs="EPSG:3045",
)
report = download_data(**selection, on_notice=lambda n: print(n.level, n.text))
for item in report.files:                    # UnitFile(unit, country, file)
    print(item.country, item.unit, item.file.path, item.file.status)
for failure in report.failed:                # UnitFailure(unit, country, error, kind)
    print(failure.country, failure.error)
print(report.ok)  # kod wyjścia CLI: True = 0 (także częściowy sukces auto)

plan = check_data(**selection)               # = --check-updates, bez pobierania
report = download_data(**selection, update="upgrade", plan=plan)  # = --upgrade --plan
```

Raport dostępności (sekcja 1.7) — skorowidz i maska PRG, bez pobierania
danych; wynik `AvailabilityReport` (`request`, `checked_at`, `areas`:
`AvailabilityArea`, `combinations`: `AvailabilityCombination`, `notices`,
`ok`), `to_json()` = wydruk `--json`:

```python
from kartograf import BBox, check_availability, download_data

# = kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000
report = check_availability(
    product="nmt",                                   # "nmt" | "nmpt" | "laz"
    country="pl",                                    # wymagane z bbox=/geometry=
    bbox=BBox(565000, 242000, 569000, 246000, "EPSG:2180"),
    min_year=2020,                                   # opcjonalnie; także year=, max_year=
)                                                    # cache=True, force=False, on_notice=
print(report.areas[0].land_m2)
for c in report.combinations:                        # rok malejąco
    print(c.year, c.horizontal, c.resolution, c.vertical_crs, c.format,
          c.complete, len(c.sheets_full), len(c.sheets_partial), c.uncovered_m2)
newest = next((c for c in report.combinations if c.complete), None)
if newest is not None:
    print(newest.source, newest.download_hint)     # np. "pl.gugik.nmt_1m", ("elevation download ...",)
    # kombinacja jako argumenty download_data (PL-2000: także scale=,
    # skale podaje download_hint)
    download_data(product="nmt", output_dir="./data", country="pl",
                  bbox=BBox(565000, 242000, 569000, 246000, "EPSG:2180"),
                  sheet_system=newest.horizontal.removeprefix("PL-"),
                  format=newest.format, resolution=newest.resolution,
                  vertical_crs=newest.vertical_crs, year=newest.year)
text = report.to_json()                              # kartograf-availability/1
```

Rejestr wariantów NMT/NMPT/LAZ (ADR-041; dane bez IO) zastępuje usunięte
w 0.8.0 stałe providerów (`SUPPORTED_RESOLUTIONS`, `WFS_ENDPOINTS`,
`nmt_vertical_crs()` itd.):

```python
from kartograf.sources.variants import variants

for v in variants(product="nmpt", country="PL"):
    print(v.source, v.label, v.vertical_crs, v.format, v.source_file)
# pl.gugik.nmpt_0_5m 0.5m EVRF2007 ASC False ... pl.gugik.nmpt_xyz_1m 1m KRON86 XYZ True
print([v.label for v in variants(product="nmt", vertical_crs="KRON86", format="ASC")])
# ['0.5m', '1m']
```

Kolekcje (`boundaries`, `cadastre`, `models3d`; sekcja 1.8) — wynik
`CollectionReport(files, failed, stale, notices, ok)`, elementy `files`
i `failed` jak w `DataReport`:

```python
from kartograf import BBox, LandCoverManager, check_collection, download_collection

out = "./data"
show = lambda notice: print(notice.level, notice.text)  # = Info:/Warning: w CLI
# = boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000
gminy = download_collection(
    product="admin", output_dir=out, country="pl", level="gmina",
    bbox=BBox(550000, 220000, 590000, 270000, "EPSG:2180"),
)
print(gminy.files[0].file.path)  # data/boundaries/pl_prg_gmina/bbox/550000_220000_590000_270000.gpkg
download_collection(product="admin", output_dir=out, teryt="12")  # paczka województwa
download_collection(product="admin", output_dir=out, country="pl", whole_country=True,
                    on_notice=show)  # Notice whole_country_size przed transferem
# = cadastre download --product map --teryt 1261 / --country pl --bbox ...
download_collection(product="map", output_dir=out, teryt="1261")
download_collection(product="map", output_dir=out, country="pl",
                    bbox=BBox(565000, 243000, 567000, 245000, "EPSG:2180"))
# = models3d download --product buildings --lod 1 --year 2024 --teryt 1261
download_collection(product="buildings", output_dir=out, teryt="1261", lod=1, year=2024)
lod2 = download_collection(product="buildings", output_dir=out, lod=2, country="pl",
                           bbox=BBox(566000, 243000, 566500, 243500, "EPSG:2180"),
                           on_notice=show)  # Notice unit_list: powiaty obszaru
for failure in lod2.failed:  # kind "no_coverage" = brak paczki powiatu (HTTP 404)
    print(failure.unit, failure.kind, failure.error)
plan = check_collection(product="buildings", output_dir=out, teryt="1261", lod=1, year=2024)
print([(i.track, i.unit, i.status) for i in plan.items])  # [("collection", "1261", "unverifiable")]
# = landcover download --source bdot10k --teryt 1261 --year 2024 --format SHP
LandCoverManager(out, "bdot10k").download(teryt="1261", year=2024, format="SHP")
```

Walidacja bez sieci (np. przed zapisaniem zadania):
`kartograf.download.collections.validate_collection_request(...)` z tymi
samymi wyborami (bez `update`, `plan`, `workers`, `cache`, `on_notice`).

Niższy poziom (tory) — te same pliki i sidecary co `download_data`:

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
# Warianty z rejestru (kartograf.sources.variants.variants()); kombinacja
# spoza rejestru, np. GugikProvider(resolution="5m", vertical_crs="KRON86"),
# -> ValidationError z listą dostępnych etykiet. Archiwum: format="TBD" (sekcja 1.1)

# Surowy WCS poza magazynem (np. ortofotomapa albo NMT KRON86 jako TIFF;
# NMT/NMPT tylko wariant 1 m — provider.is_wcs_available()):
# provider.download_bbox(bbox, path) — jednopasmowy float32 GeoTIFF na
# siatce 1 m EPSG:2180, bez maski PRG i bez wersji. Wycinek NMT/NMPT
# w magazynie wersji: download_pl_cutout (niżej).
area = BBox(min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180")
kron = GugikProvider(vertical_crs="KRON86", resolution="1m")
path = kron.download_bbox(area, Path("my_area.tif"))

# Land Cover: BDOT10k / CORINE / SoilGrids do magazynu (output_dir = --output)
from kartograf import LandCoverManager
lc = LandCoverManager("./data", "bdot10k")
result = lc.download(teryt="1465")         # BDOT10k (powiat) -> LandCoverAreaResult
file = result.files[0].file
print(file.path, file.status)  # data/landcover/pl_bdot10k_gpkg/teryt/1465.gpkg new
# BDOT10k z KAŻDEGO powiatu obszaru (bbox w dowolnym układzie, sheet= albo
# geometry=), powiaty równolegle (workers=), tylko wybrane warstwy ->
# landcover/pl_bdot10k_gpkg_ptwp-swkn-swrm-swrs/teryt/<T>.gpkg;
# keep_raw=True: oryginalny ZIP GUGiK jako osobna wersja
# (landcover/pl_bdot10k_gpkg_zip/teryt/<T>.zip, pełny pakiet; tylko GPKG)
area = lc.download(
    bbox=BBox(340000, 290000, 350000, 300000, "EPSG:2180"),
    layers=["SWRS", "SWKN", "SWRM", "PTWP"],
    keep_raw=True,
    workers=4,
)
paths = [r.file.path for r in area.files]  # area.failed: powiaty z błędem
print(area.ok, area.notices)                 # ok = brak błędów i nieaktualnych pozycji
# obszar bez powiatu: NoCoverageError
lc.set_provider("corine")
lc.download(sheet="N-34-130-D", year=2018)  # CORINE (CLMS albo podgląd _preview)
lc.set_provider("soilgrids")
plan = lc.check(sheet="N-34-130-D", property="clay", depth="0-5cm", stat="mean")
lc.download(sheet="N-34-130-D", property="clay", depth="0-5cm", stat="mean",
            update="upgrade", plan=plan)    # tylko pozycje planu

# Hydrologic Soil Groups (wejścia = wersje SoilGrids "mean" w tym samym magazynie);
# wybór: sheet=, bbox= (dowolny układ) albo geometry= (obwiednia pliku)
from kartograf import HSGCalculator
calc = HSGCalculator("./data")
hsg = calc.calculate_hsg(sheet="N-34-130-D", depth="0-5cm")
print(hsg.file.status, hsg.file.label)      # new 2.0 (ponownie: reused 2.0)
plan = calc.check_hsg(sheet="N-34-130-D", depth="0-5cm")  # bez pobierania
stats = calc.get_hsg_statistics(hsg.file.path)

# HSG z gotowych rastrow clay/sand/silt (g/kg) na jawnej siatce - bez pobierania
from kartograf import BBox, hsg_from_rasters
hsg_from_rasters(
    Path("clay.tif"), Path("sand.tif"), Path("silt.tif"),
    bbox=BBox(501000, 596000, 503000, 598000, "EPSG:2180"),
    crs="EPSG:2180", pixel_m=100.0, output_path=Path("./hsg_100m.tif"),
)

# Scalony wycinek WCS NMT lub NMPT PL (GeoTIFF + sidecar)
from kartograf import check_pl_cutout, download_pl_cutout

bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
selection = dict(horizontal_crs="EPSG:5514", output_dir="./data",
                 vertical_crs="EVRF2007", product="nmpt")
result = download_pl_cutout(bbox, **selection)
print(result.file.path, result.file.status, result.masked_pixels, result.all_nodata)
for notice in result.notices:               # rozmiar wycinka, wycinek bez danych
    print(notice.level, notice.text)
# domyślnie istniejąca wersja bez zapytań PRG/WCS; update="force" pobiera ponownie
plan = check_pl_cutout(bbox, **selection)   # te same argumenty, bez pobierania
result = download_pl_cutout(bbox, **selection, update="upgrade", plan=plan)

# Zlewnia przygraniczna PL/CZ: podział obszaru na kraje i wycinek CZ
# w układzie PL (EPSG:2180 + EVRF2007); siatka CZ startuje od zadanego obszaru
from kartograf import download_cz_cutout, split_bbox_by_country

area = BBox(16.19, 50.42, 16.25, 50.45, "EPSG:4326")  # Kudowa-Zdrój / Náchod
parts = split_bbox_by_country(area, cz_crs="EPSG:2180")  # {"CZ": ..., "PL": ...}
cz = download_cz_cutout(
    parts["CZ"].bbox,
    output_dir="./data",
    horizontal_crs="EPSG:2180",
    vertical_crs="EVRF2007",
    resolution="2m",          # "2m" DMR 5G / "5m" DMR 4G
)
print(cz.file.path)           # data/nmt/cz_dmr5g_evrf2007/bbox/<coords>.tif
# all_nodata=True: część CZ bez ani jednego ważnego piksela (prostokąt
# obwiedni CZ sięga w głąb Polski) — plik powstaje, flaga też w sidecarze
print(cz.all_nodata)
# Część PL (parts["PL"].bbox) pobierz przez download_pl_cutout (wyżej).

# Arkusz CZ: SM5 (gotowy plik DMR 4G, tylko 5m - resolution można pominąć)
# albo kafel TM33 (resolution wymagane: "2m" / "5m")
from kartograf import check_cz_sheet, download_cz_sheet

sm5 = download_cz_sheet("CTES96", output_dir="./data", vertical_crs="Bpv")
tm33 = download_cz_sheet(
    "302_5550", output_dir="./data", vertical_crs="EVRF2007", resolution="2m"
)

# Sprawdzenie bez pobierania (plan kartograf-plan/1): blizniak check_* z tymi
# samymi argumentami co pobranie; plan wykonuje pobranie z update="upgrade"
plan = check_cz_sheet("CTES96", output_dir="./data", vertical_crs="Bpv")
print([(i.track, i.unit, i.status) for i in plan.items])
sm5 = download_cz_sheet(
    "CTES96", output_dir="./data", vertical_crs="Bpv", update="upgrade", plan=plan
)
```

**Cache metadanych w bibliotece.** Funkcje poziomu komendy i torów
(`download_data`, `check_data`, `download_pl_cutout`, `download_cz_*`,
`download_laz_area`, `LandCoverManager`, `HSGCalculator`) przyjmują
`cache: MetadataCache | bool = True`: domyślnie ten sam plik co CLI
(`<cwd>/.kartograf_cache.db`, TTL 7 dni), `False` = bez cache, własny
`MetadataCache` = ten. `update="force"` pomija odczyty z cache w tym
wywołaniu (jak `--force`). Katalog tylko do odczytu: cache wyłączony
z `Notice` `cache_disabled`, pobieranie idzie dalej. Provider tworzony
ręcznie (niżej) bez `MetadataCache` pyta skorowidz GUGiK przy KAŻDYM
`download_sheet`; przekaż mu cache, a zapytania o arkusz ograniczą się do
raz na TTL:

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

Pozostałe elementy publicznego API (m.in. `GugikNmptProvider` —
od 0.8.0 z wymaganym `resolution=`, np. `GugikNmptProvider(vertical_crs="EVRF2007",
resolution="0.5m")`, `GugikOrtoProvider`, `GugikLazProvider`/`download_laz_area` dla LAZ,
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
  `masked_pixels`, `zero_pixels`, `all_nodata`, `stale`, `notices`.
- `CzCutoutResult` (wycinek CZ, `download_cz_cutout`) i `CzSheetResult`
  (arkusz CZ, `download_cz_sheet`): `file`, `all_nodata`, `stale`, `notices`.
- `LazDownloadResult` (`download_laz_area`): `tiles` (wybrane kafle),
  `files` (`VersionedFile` na kafel), `failed`, `superseded` (kafle
  pominięte jako pokryte przez nowsze), `stale`, `notices`.
- `DataReport` (`download_data`, komendy `kartograf elevation download` i `kartograf imagery download`): `files`
  (`UnitFile(unit, country, file)`), `failed` (`UnitFailure(unit, country,
  error, kind)`), `stale`, `superseded`, `notices`, `ok` (kod wyjścia CLI:
  `True` = 0).
- `LandCoverAreaResult` (`LandCoverManager.download`): `files`
  (`LandCoverResult(unit, file, raw)`; `raw` = oryginalny ZIP przy
  `keep_raw`), `failed` (`LandCoverFailure(unit, error)`), `stale`,
  `notices`, `ok`; `HsgResult` (`HSGCalculator.calculate_hsg`): `unit`,
  `file`, `inputs` (wejścia clay/sand/silt), `stale`, `notices`, `ok`.
- `VersionedFile`: `path` (ścieżka standardowa = hardlink), `status`
  (`new`/`unchanged`/`relabeled`/`local`, dla HSG także `reused`), `label`, `sha256`,
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

**Pliki z 0.7.x.** Zwykły plik w ścieżce standardowej (bez sidecara
dowiązania do wersji) nie jest wersją magazynu: pierwsze uruchomienie 0.8.0
pobiera dane do `versions/` i zastępuje plik dowiązaniem (ADR-036 D24);
pliki wycinków PL z datą w nazwie (`<współrzędne>_<RRRRMMDD>.tif`) nie są
rozpoznawane (sekcja 1.3).

---

## 4. Kampanie GUGiK

GUGiK publikuje ten sam arkusz w kilku kampaniach (różne lata pozyskania).
Domyślnie (również z flagami roku) pobiera najnowszą kampanię;
`--all-campaigns` — każdą. Wybór roku (`--year`, `--min-year`,
`--max-year`) opisuje sekcja 4.1. Kampanie i rok dotyczą tylko PL — dla CZ
opcje dają `Error: CZ (CUZK) nie ma kampanii - ...` (zadanie wyłącznie
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
  Na udziale SMB/cifs klient może przejściowo raportować błędną liczbę
  dowiązań, przez co nawet `rsync -aH` skopiuje je jako osobne pliki.
  `project verify` potwierdza treść kopii, ale nie oszczędność miejsca:
  sprawdź jej zajętość; w razie potrzeby kopiuj po stronie serwera lub
  z hosta z lokalnym dostępem do systemu plików.
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
- **Wycinek `--cutout`** pochodzi z WCS GUGiK z kompozycją lotów
  serwera (nie z kampanii arkuszy, sekcja 1.3) i nie przyjmuje
  `--all-campaigns`, flag roku ani `--full-sheet`.
- **LAZ:** `--all-campaigns` pobiera wszystkie kafle, których rama przecina
  obszar (bez deduplikacji ADR-029). Kafle LAZ są wersjami z dowiązaniem
  ścieżki standardowej, bez `full_sheet/`.
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
  Error: brak danych z roku 2024 dla 2 z 4 arkuszy - nic nie pobrano:
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
  obszaru - nic nie pobrano:` z rocznikami per kafel. Zapytania WFS idą do
  wszystkich roczników usługi. Sidecar kafla ma `extra.acquisition_date`
  i `extra.full_sheet`.
- **Nie działa:** z `--cutout` (`Error: --year nie dziala z
  --cutout ...`) ani dla CZ (zadanie wyłącznie CZ = `Error:`; obszar PL+CZ
  pod `auto` wymaga `--cutout`, więc też `Error:` — arkusze PL z flagami
  roku pobiera `--country pl`).

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
kartograf elevation download --sheet N-34-139-C-a-3-1 --full-sheet --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
#   -> N-34-139-C-a-3-1: nowa wersja 2025-10-21_84183_<sha8> (i druga: najnowszy pełny lot)
kartograf imagery download --sheet M-34-90-C-b-4-4 --product orto --full-sheet -o ./data
kartograf elevation download --sheet N-34-139-C-a-3-1 --full-sheet --max-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # pełny z zakresu lat
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
  zadania`) i `pelny lot nie pobrany: ... - uzyj --full-sheet`.
- **Pełny = w granicach Polski.** Arkusz graniczny oznaczony jako pełny ma
  nodata po stronie zagranicznej ramki — to normalne. `full_sheet/` ufa
  deklaracji skorowidza, nie mierzy pokrycia.
- **Nigdy wstecz:** jak ścieżka standardowa; gdy przy flagach roku
  dowiązanie zostaje przy pełnym locie spoza zakresu, CLI podaje `Info:`
  z linią `<godło>: full_sheet/ -> dowiazanie <data>_<id>`.
- **`list_files()` / `delete()`:** `FileStorage.list_files()` pomija
  `full_sheet/` i `versions/`, `delete(godło)` usuwa oba dowiązania (wersje
  zostają).
- **Nie działa:** z `--product laz` i `--cutout` (`Error:` przed siecią);
  dla CZ jak inne opcje kampanii.
- **Biblioteka:** `DownloadManager(full_sheet=True)`;
  `DownloadResult.full_links` (godło -> ścieżka
  `full_sheet/`), `DownloadResult.without_full`,
  `DownloadResult.full_link_outside_range`.


### 4.3 Wersje, tryby i plan aktualizacji (`--check-updates`, `--upgrade`, `--force`)

Dotyczy każdego toru `kartograf elevation download` i `kartograf imagery download`: arkuszy PL NMT/NMPT/orto,
kafli LAZ, arkuszy CZ (TM33, SM5), wycinków CZ i wycinków PL
`--cutout`, a także `landcover download`, `soil download`, `soil hsg`
oraz `boundaries download`, `cadastre download` i `models3d download`. Flagi
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
| kolekcje (`boundaries`, `cadastre`, `models3d`; tor planu `collection`) i archiwum BDOT10k (`--year`) | brak (`none`) | jak TM33; etykieta = rocznik/rok wydania albo data pobrania (sekcja 1.8) |
| HSG (`soil hsg`) | sha256 wejść | ta sama treść wejść = `uzyta ponownie` (bez liczenia); w planie pozycja `hsg` obok trzech pozycji `landcover` |

Pod `--country auto` `--check-updates --plan PLIK` zapisuje JEDEN plan
z pozycjami PL i CZ (pole `track`), a `--upgrade --plan PLIK` wykonuje
pozycje każdego toru.

| Sytuacja | domyślnie | `--check-updates` | `--upgrade` | `--force` |
|---|---|---|---|---|
| lokalna wersja aktualna | lokalna wersja | `aktualne` | lokalna wersja | pobiera ponownie |
| w skorowidzu nowsza kampania | lokalna wersja + `Info:` | `nowsza: <etykieta> (lokalna <etykieta>)` | pobiera nowszą | pobiera |
| brak lokalnej wersji | pobiera | `do pobrania` | pobiera | pobiera |

`--check-updates` niczego nie pobiera; z `--plan PLIK` zapisuje plan JSON
(`kartograf-plan/1`), który `--upgrade --plan PLIK` wykonuje później —
pozycja, której źródło zmieniło się od planu, kończy się `Error:` bez
pobrania, a pozycje usunięte z pliku nie są wykonywane. `--force` pobiera
ponownie i odświeża cache metadanych, ale nie nadpisuje: ta sama treść =
`bez zmian`, inna = nowa wersja.

```bash
kartograf elevation download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
#   N-34-139-C-a-3-1: nowa wersja 2025-10-21_84183_4de1eac7
kartograf elevation download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data --check-updates --plan plan.json
#   N-34-139-C-a-3-1: aktualne (2025-10-21_84183)
kartograf elevation download --sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data --upgrade --plan plan.json
```

Wynik: jedna linia na plik — `nowa wersja <etykieta>_<sha8>`, `nowa
etykieta <etykieta> (plik identyczny z <etykieta>)` (GUGiK opublikował pod
nowym rekordem plik bajtowo identyczny z najnowszą istniejącą wersją; nowy
katalog wersji to dowiązanie, bez dodatkowego miejsca na dysku;
w bibliotece `VersionedFile.same_as`), `bez zmian <etykieta>`,
`lokalna wersja <etykieta>`
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
# LAZ: download_laz_area(..., update=, plan=) + check_laz_area (te same argumenty);
# wycinki i arkusz CZ: download_pl_cutout / download_cz_cutout /
# download_cz_sheet(..., update=, plan=) + check_pl_cutout / check_cz_cutout /
# check_cz_sheet (te same argumenty); land cover: LandCoverManager.download(...,
# update=, plan=) + check (te same argumenty); HSG: calculate_hsg(...,
# update=, plan=) + check_hsg; kolekcje: download_collection(..., update=,
# plan=) + check_collection; pozycje planu: item.track, item.unit
```

---

## 5. Gleby i HSG

- SoilGrids (ISRIC): 11 parametrów, 6 głębokości, 5 statystyk,
  rozdzielczość 250 m — tabela parametrów i jednostek: PRD 3.7;
  `kartograf soil list-layers`.
- HSG (`kartograf soil hsg`, `HSGCalculator(output_dir)`) bierze
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
- Godło PL-2000 1:10000 wymaga w CLI i `download_data` jawnego `--scale`
  (sekcja 1.6); provider/`DownloadManager` wywołany bez skali, gdy
  skorowidz ma tylko arkusze potomne, zwraca `NoCoverageError`
  z podpowiedzią `--scale 1:2000`. Arkusz PL-1992 nigdy nie jest pobierany
  jako zamiennik.
- Rozpoznawanie krajów używa prostokątnych obwiedni (ADR-023), nie wielokąta
  granic; `--country auto` może odpytać CUZK poza Czechami i GUGiK
  w Czechach (sekcja 1.2).
- Wycinek `--cutout` jest tylko 1 m: NMT/NMPT w innych
  rozdzielczościach (np. 0.5m, 5m) i archiwa pobieraj jako arkusze bez
  tej flagi (sekcja 1.3).
- Archiwa GUGiK (`--format XYZ|ASCII-NMT|TBD|TIN|TTN|GRD|DXF|DGN`) są
  pobierane jako pliki źródłowe bez konwersji (ZIP, `.ttn`, `.grd`,
  `.dxf`, `.dgn`): Kartograf nie rozpakowuje ich, nie przelicza na
  siatkę, nie wycina i nie mierzy pokrycia — plik otwierasz programem,
  który obsługuje dany format (sekcja 1.1).
- Raport `elevation availability` ufa deklaracji skorowidza
  `calyArkuszWypelnionyTrescia`: arkusz NIE może mieć od 1 % do 99 %
  danych, a raport nie mierzy treści plików (sekcja 1.7). Raport jest
  dziś tylko dla PL (`--country pl`).
- Godła 8-członowe PL-1992 (wszystkie arkusze ASCII NMT 10 m i część
  arkuszy ASC 1 m w skorowidzu GUGiK) są poza układem godeł Kartografu:
  nie są pobierane, a raport dostępności wymienia je w `Info:`.
- Raport dostępności rasteryzuje ląd obszaru na siatce 1 m (pasy po
  4 Mpx): dla dużych obszarów liczy się długo, ponowny raport tego
  samego obszaru korzysta z cache metadanych (sekcja 1.7).
- `provider.download_bbox` (WCS: NMT KRON86 TIFF, NMT EVRF2007
  i NMPT ASC multipart) daje wysokości float32 w rozdzielczości
  1 m poza magazynem wersji, bez maski lądu PRG i bez sidecara;
  maskę i wersję dostaje wycinek `--cutout` /
  `download_pl_cutout`. Kompozycja serwera może różnić się
  od wyboru kampanii arkusza.
- Wycinki (PL, CZ) i kafle TM33 nie mają taniego sygnału świeżości:
  zmiana treści u źródła albo maski PRG jest niewidoczna bez `--force`.
- Granice PRG, EGiB, modele 3D i archiwum BDOT10k (sekcja 1.8) nie mają
  taniego sygnału świeżości: nowszą treść przynosi tylko `--force`.
- Strony WFS GUGiK (obiekty obszaru PRG i EGiB) przychodzą po kilka
  sekund na stronę 1000 obiektów (na żywo 2026-10-15: 2–4 s; limit jednego
  zapytania 60 s), więc duży obszar EGiB to minuty. Wynik obszaru jest
  składany w pamięci (cała warstwa naraz) — dla całego powiatu wygodniej
  pobrać eksport (`cadastre download --teryt`), a granice województwa —
  paczkę (`boundaries download --teryt <2 cyfry>`).
- GeoPackage wyniku obszaru ma te same bajty dla tej samej treści tylko
  w obrębie jednej wersji GDAL (`pyogrio`): po aktualizacji GDAL `--force`
  może zapisać nową wersję tej samej treści.
- EGiB obszaru pochodzi z usługi zbiorczej powiatowych WFS: powiat bez
  integracji to luka w wyniku (bez błędu), atrybuty zastrzeżone mają
  wartość `brak_uprawnien`. LoD2 modeli 3D nie pokrywa całego kraju.
- Uszkodzony albo nieczytelny cache metadanych (`.kartograf_cache.db`
  w bieżącym katalogu) nie przerywa pobierania: CLI drukuje jedno
  `Warning: cache metadanych nieczytelny (<plik>): ...` i pracuje bez cache.
  Naprawa: `kartograf cache clear` (usuwa nieczytelny plik wraz
  z `-wal`/`-shm`) albo ręczne usunięcie pliku.

Pełna lista ograniczeń technicznych (timeouty, ponowienia, CZ, `auto`):
SCOPE 3.2; plany: SCOPE 3.1.

---

## 8. Projekt

Projekt zapisuje w `kartograf-project.json` **zadania** (komendy danych
z opcjami) i **przypiete wersje plikow** (pelne sumy SHA-256). Jeden
projekt wskazuje jeden magazyn `--output`; wiele projektow moze korzystac
z tego samego magazynu, bez kopiowania danych do katalogow projektow.
Sciezka standardowa w magazynie moze wskazywac nowsza wersje, ale
przypiecie pozostaje przy konkretnych bajtach. Plik manifestu mozna
przechowywac razem ze skryptami projektu w systemie kontroli wersji.

### Pierwsze pobranie i sprawdzenie

```bash
mkdir -p ~/projekty/wisla
cd ~/projekty/wisla
kartograf project init --output ~/dane/kartograf
kartograf project add teren elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 --year 2022
kartograf project add pokrycie landcover download --source bdot10k --teryt 1465
kartograf project add gleby soil hsg --sheet N-34-130-D --depth 0-5cm
kartograf project download
kartograf project status
kartograf project verify
```

`init` wymaga jawnego `--output`; tworzy manifest i katalog magazynu,
jesli ich nie ma. `add` przyjmuje po nazwie zadania te same komendy
i flagi wyboru danych co zwykle `kartograf elevation download`,
`imagery download`, `landcover download`, `soil download`, `soil hsg`,
`boundaries download`, `cadastre download` i `models3d download`;
sprawdza wybory bez sieci i bez pobierania. W zadaniu nie zapisuje sie
`--output` ani trybow `--upgrade`/`--force`: magazyn pochodzi z projektu,
a tryb wybiera sie przy `project download`. `remove NAZWA` usuwa
zadanie i przypiecia z manifestu, **nie usuwa plikow** z magazynu.
Nazwy zadan mozna podac pozycyjnie w `download`, `status` i `verify`;
bez nazw polecenie obejmuje wszystkie zadania. `--project KATALOG`
pozwala pracowac bez `cd` (domyslnie projekt jest w biezacym katalogu):

```bash
kartograf project verify --project ~/projekty/wisla
```

Pierwsze `download` przypina komplet plikow zadania dopiero po pelnym
sukcesie; wynik HSG przypina rowniez trzy pliki wejsciowe SoilGrids.
Ponowne `download` **nie zmienia przypiec** ani nie odpytuje zrodla,
gdy przypiete pliki sa obecne. Gdy ich brakuje, probuje odtworzyc
zadanie: akceptuje tylko te same sumy SHA-256. Inna tresc u zrodla
oznacza blad, nigdy cicha zamiane; odzyskaj kopie magazynu lub jawnie
wybierz `--upgrade`. `status` bez sieci szybko sprawdza istnienie
wersji i rozmiary; `verify` bez sieci czyta cale pliki i porownuje
SHA-256 oraz sidecary wersji. Zaden z nich nie zmienia manifestu.

### Swiezosc i wariant danych

```bash
kartograf project download --check-updates
kartograf project download --upgrade teren
kartograf project download --force pokrycie
```

`--check-updates` odpytuje zrodlo bez pobierania i porownuje stan
**z przypieciem**, nie z najnowsza lokalna wersja magazynu; nie zmienia
manifestu. `--upgrade` jawnie przepina cale zadanie na nowsza wersje,
jesli jest sygnal zmiany, rowniez gdy nowa wersja juz jest w magazynie.
`--force` ponawia pobranie nawet bez taniego sygnalu; przepiecie
nastepuje po pelnym sukcesie zadania. Inne projekty zachowuja swoje
przypiecia, stare wersje nadal sa w magazynie.

**Zalecenie dla odtwarzalnosci:** wybieraj jawny wariant w zadaniu
(np. `--year`, odpowiednie `--resolution` i `--vertical-crs`), gdy
produkt to umozliwia. Bez `--year` wybierasz najnowszy lot w chwili
pobrania; po opublikowaniu nowego lotu odtworzenie na pustym
magazynie moze zwrocic inna sume i zakonczyc sie bledem. Nawet
jawny rok nie zastepuje kopii magazynu, jesli zrodlo wycofa albo
podmieni plik. Nie ma `project availability`: przed `project add`
uzyj `kartograf elevation availability ...`, aby poznac dostepne
kompletne warianty obszaru (lata, uklady, rozdzielczosci, formaty), i podaj
wybrane flagi zadania — raport drukuje gotowa linie `W projekcie:
kartograf project add NAZWA elevation download ...` bez `--output`
(sekcja 1.7; archiwum z `--format`, w manifescie opcja `format`).
`availability` odpowiada na pytanie *jakie
warianty sa dostepne*, a `project download --check-updates` — *czy
przypiete pliki sa aktualne dla wybranego wariantu*. Wybor
`--year` pozostaje aktualny dla danego roku nawet po wydaniu
nowszego rocznika.

### Przenoszenie projektu i magazynu

Sciezki `output_dir` i `options.geometry` podane wzglednie sa zapisane
wzgledem katalogu projektu (nie biezacego katalogu odczytu).
Sciezki podane bezwzglednie pozostaja bezwzgledne. Przypiete `path`
i `version` sa zawsze wzgledne do magazynu.

| Sytuacja | Co zrobic |
|---|---|
| Przenosisz projekt z magazynem, zachowujac ich wzajemne polozenie (`output_dir` wzgledny) | Nic; `kartograf project verify` potwierdzi stan. |
| Przenosisz sam projekt, magazyn pozostaje pod ta sama sciezka bezwzgledna | Nic. |
| Przenosisz sam projekt, a `output_dir` jest wzgledny | Zmien `output_dir` w `kartograf-project.json`. |
| Przenosisz lub kopiujesz magazyn | Kopiuj razem z sidecarami i dowiazaniami twardymi (`rsync -aH`), popraw `output_dir`, uruchom `kartograf project verify`. |
| Otwierasz projekt z pustym magazynem | Utworz katalog magazynu (albo wskaz w `output_dir` istniejacy), uruchom `kartograf project download`, potem `kartograf project verify`; odtworzenie wymaga zgodnosci SHA-256. |

Na udziale SMB/cifs `rsync -aH` może nie zachować wszystkich dowiązań
twardych (sekcja 4); `verify` nie wykrywa nadmiarowych kopii.

Plik geometrii obszaru warto trzymac przy manifeście i podawac wzglednie:
przenosi sie z projektem. Zmiana jego bajtow od chwili przypiecia
blokuje zwykle odtworzenie; jawne `--upgrade`/`--force` moze przyjac
zmieniony obszar. Pozostale komendy wymagaja istniejacego katalogu
magazynu (brak zamontowanego udzialu nie spowoduje pobrania do
pustego katalogu).

### Biblioteka Python

```python
from pathlib import Path
from kartograf import (
    add_project_task, check_project, download_project, init_project,
    project_status, verify_project,
)

project_dir = Path.home() / "projekty" / "wisla"
init_project(project_dir, output_dir=Path.home() / "dane" / "kartograf")
add_project_task(
    project_dir,
    name="teren",
    command="elevation download",
    options={
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "year": 2022,
    },
)
report = download_project(project_dir)
print(report.ok, [(task.name, task.outcome) for task in report.tasks])
print(project_status(project_dir).ok, verify_project(project_dir).ok)
check = check_project(project_dir)  # sonda zrodla; bez pobierania i zapisu
print([(item.task, item.status) for item in check.files])
download_project(project_dir, tasks=["teren"], update="upgrade")
```

`init_project` i `add_project_task` zwracaja `Project`,
`download_project` zwraca `ProjectReport` (`tasks`, `notices`, `ok`),
a `check_project`, `project_status` i `verify_project` zwracaja
`ProjectCheck` (`files`, `not_downloaded`, `notices`, `ok`).
`open_project(project_dir)` czyta i waliduje manifest; API udostepnia
takze `remove_project_task`. Operacje projektu domyslnie dzialaja bez
cache SQLite (`cache=False`); `cache=True` tworzy cache w biezacym
katalogu, wiec uzywaj go tylko lokalnie. Kontrakt formatu i zapisu:
[ARCHITECTURE.md, sekcja 3.5](ARCHITECTURE.md#35-manifest-projektu-kartograf-project1).
