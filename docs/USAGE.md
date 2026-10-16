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
   - [1.9 Dane CZ: ZABAGED, Data50, Data250, RUIAN i HY-NET](#19-dane-cz-zabaged-data50-data250-ruian-i-hy-net)
   - [1.10 Nazwy geograficzne i mapy topograficzne](#110-nazwy-geograficzne-i-mapy-topograficzne)
   - [1.11 Mesh 3D, drzewa, osnowy geodezyjne i quasi-geoidy](#111-mesh-3d-drzewa-osnowy-geodezyjne-i-quasi-geoidy)
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
| `elevation` | `download`, `list-sources`, `availability` | NMT, NMPT i LAZ (PL, CZ); raport dostępności PL, CZ i `auto` |
| `imagery` | `download`, `list-sources` | ortofotomapa: arkusze PL (GUGiK) i CZ (CUZK, SM5), wycinek WCS PL (`--cutout`) |
| `landcover` | `download`, `list-sources`, `list-layers` | BDOT10k (także archiwum roczników `--year`), BDOO (PL), CORINE, ZABAGED, Data50 i Data250 (CZ) (`--source`) |
| `soil` | `download`, `hsg`, `list-sources`, `list-layers` | SoilGrids, HSG |
| `boundaries` | `download`, `list-sources` | granice jednostek: PRG (PL), RUIAN (CZ) |
| `cadastre` | `download`, `list-sources` | EGiB — działki i budynki (PL) |
| `models3d` | `download`, `list-sources` | modele 3D (PL): budynki CityGML LoD1/LoD2, drzewa CityGML, mesh miast (OBJ) |
| `hydro` | `download`, `list-sources` | sieć wód HY-NET (CZ) |
| `names` | `download`, `list-sources` | PRNG RP, polskie nazwy świata (PL), Geonames (CZ) |
| `maps` | `download`, `list-sources` | wizualizacje map BDOT10k (PL), ZTM (CZ) |
| `geodesy` | `download`, `list-sources` | osnowy geodezyjne PL (GUGiK) i CZ (Bodove pole), quasi-geoidy PL-geoid2021 i QGZU-2013 |
| `project` | `init`, `add`, `remove`, `download`, `status`, `verify` | manifest projektu i przypiete wersje z magazynu |

Poza grupami zostają `kartograf parse` i `kartograf cache`. `kartograf <grupa>
--help` wypisuje komendy grupy, `list-sources` — źródła grupy z rejestru (bez
sieci). Dawne `kartograf download`, `kartograf soilgrids` i
`landcover --source soilgrids` nie działają: kończą się błędem (kod 2)
z nazwą nowej komendy (tabela: CHANGELOG 0.8.0).

Od 0.8.0 CLI nie ma wartości domyślnych wpływających na dane: `--product`,
`--output` (także `landcover download`, `soil download` i `soil hsg`), `--country`
(z `--bbox`/`--geometry`), `--vertical-crs` (NMT, NMPT, LAZ),
`--resolution` (NMT i NMPT, gdy jest wybór; piksel wycinka ortofotomapy),
`--sheet-system` (PL `--bbox`/`--geometry`
bez `--cutout`), `--horizontal-crs` (z `--cutout`; plik krajowy ZABAGED,
Data50, Data250), `--coverage` (wycinek ortofotomapy), `--scale` (PL-2000),
`--level` (obszar `boundaries`; pod `auto` per kraj), `--lod` i `--year`
(`models3d`, gdy wydań jest kilka; rocznik BDOO), `--network`
(`geodesy --product control`) oraz `--format` z `--year`
(archiwum BDOT10k)
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

**NMT 100 m (od 0.8.0).** `--resolution 100m` to pliki województw z feedu
ATOM GUGiK (ZIP z jednym plikiem XYZ, wydanie 2019), nie arkusze:

```bash
# Kraków: plik województwa 12 (ZIP 7,6 MB); obszar na granicy województw daje dwa pliki
kartograf elevation download --product nmt --resolution 100m --country pl --bbox 564000,241000,570000,247000 --bbox-crs EPSG:2180 -o ./data
#   Info: nmt: wojewodztwa obszaru wg PRG (1): 12 (malopolskie)
#   -> nmt/pl_1992_100m/teryt/12.zip (ZIP 1:1, wersja 2019-05-14 = data wpisu feedu)
```

- Układ wysokości jest **nieznany** (GUGiK go nie deklaruje): sidecar ma
  `vertical_crs: null` i `extra.vertical_crs_note`; `--vertical-crs` to
  `Error:`. `--format XYZ` można pominąć.
- Bez arkuszy, lotów i wycinka: `--sheet-system`, `--scale`, flagi roku,
  `--all-campaigns`, `--full-sheet`, `--cutout`, `--horizontal-crs`,
  `--min-density` i `--country cz` to `Error: ... NMT 100 m to pliki
  wojewodztw z ATOM - bez arkuszy, lotow i wycinka`. `--check-updates`
  czyta tylko feedy.

**Obrazy intensywności, true orto i orto ukośna (od 0.8.0).** Arkusze
GUGiK jak ortofotomapa (kampanie, `--year`, `--all-campaigns`, sygnał
skorowidza), GeoTIFF 1:1. Plik ponad 100 MiB jest zapowiadany przed
pobraniem (`Warning: ... duzy plik <URL> - 296853152 B (ok. 297 MB)`).

```bash
# obrazy intensywności LIDAR: 1 pasmo, piksel 0,25 m; arkusze PL-1992 i PL-2000
kartograf imagery download --product intensity --sheet M-34-64-D-d-1-4 -o ./data
#   -> intensity/pl_1992/M-34/64/D/d/1/4/M-34-64-D-d-1-4.tif
# true orto wybranych miast (np. Gdańsk): godła 8-członowe PL-1992, RGB 0,05 m (ok. 300 MB)
kartograf imagery download --product true-orto --sheet N-34-50-A-c-3-2-3 -o ./data
#   -> orto/pl_1992_true/N-34/50/A/c/3/2/3/N-34-50-A-c-3-2-3.tif
# wycinek true orto z WCS: piksel 0.05m-1m, tylko EPSG:2180, bez --coverage
kartograf imagery download --product true-orto --country pl --bbox 470100,740100,470200,740200 --cutout --horizontal-crs EPSG:2180 --resolution 0.05m -o ./data
#   -> orto/pl_1992_true_0.05m/bbox/470100_740100_470200_740200.tif
# orto ukośna (Kraków, Gdańsk): arkusz = 4 pliki kierunków; --direction wybiera część
kartograf imagery download --product oblique-orto --sheet 7.125.11.08 --direction n -o ./data
#   -> orto/pl_2000_oblique/7/125/11/08/7.125.11.08_n.tif (bez flagi także _e, _s, _w)
```

- Produkt z jednym układem arkuszy (true orto: 1992, orto ukośna: 2000)
  może pominąć `--sheet-system`; orto ukośna ma arkusze 1:2000 i 1:1000,
  więc obszar wymaga `--scale`. `--full-sheet` tylko dla orto ukośnej
  (rekordy intensywności i true orto nie deklarują pełnego arkusza).
- Linie wyniku i `--check-updates` jednostki z kilkoma plikami podają nazwę
  pliku (`7.125.11.08_e.tif: do pobrania ...`).
- Pod `--country auto` produkt jednego kraju zawęża obszar do tego kraju
  (`Info: --country auto -> pl (--product intensity tylko dla PL)`).

LAZ: domyślnie pobierany jest najnowszy kafel dla każdego fragmentu obszaru;
starsze kafle pokryte przez nowsze są pomijane z komunikatem `Info:`
([ADR-029](DECISIONS.md), szczegóły: SCOPE 2.5 i ARCHITECTURE 4.7 "Wybór
kafli"); `--year`/`--min-year`/`--max-year` zawężają wybór do przedziału lat
(sekcja 4.1; rocznik spoza usługi = błąd z listą dostępnych). WFS GUGiK
w EPSG:2180 używa kolejności osi (N,E). Obszar `--sheet` to rama arkusza
(w EPSG:2180 obrócony czworokąt), nie jej obwiednia: kafel musi sięgać
w obszar głębiej niż 1 m, więc sąsiedni arkusz stykający się z ramą
krawędzią albo narożnikiem nie jest pobierany (`--sheet N-34-130-D-d-2-4`
= 4 kafle 1:5000). Tak samo `--bbox`: kafel sięgający w niego o milimetry
(zaokrąglenie ram GUGiK do 1 cm) jest pomijany.
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
- Wartości bez odpowiednika czeskiego (`--vertical-crs KRON86`,
  rozdzielczość, której CUZK nie ma, np.
  `--resolution 1m` albo `0.5m` dla NMT (NMPT `0.5m` ma odpowiednik
  DMP OK), `--format` — w zwykłej, nie per-krajowej postaci — oraz
  `--coverage` i `--resolution` wycinka ortofotomapy) na obszarze objętym
  obwiedniami obu krajów same przełączają `auto` na PL (komunikat
  `Info:`); dla LAZ także `--year`, `--min-year`, `--max-year`,
  `--all-campaigns` i `--min-density`. W Pradze czy Brnie
  taka flaga kieruje więc zadanie do GUGiK, który nie ma tam danych (błąd
  pobrania); błąd przed siecią dostaje dopiero obszar poza prostokątem PL.
  LAZ na obszarze sięgającym CZ bez tych flag pobiera pliki obu krajów
  i wymaga `--model` (sekcja 1.4); bez niego `Error:` z podpowiedzią
  `--country pl`. `--sheet-system`
  jest wymagane dla części PL zadania (bez `--cutout`), więc nie wybiera
  kraju. Ortofotomapa ma od 0.8.0 źródło CZ, więc samo `--product orto`
  nie przełącza już `auto` na PL (sekcja 1.4).
- Raster NMT/NMPT z obszaru sięgającego CZ (`--country cz` albo `auto`
  z częścią CZ) wymaga `--cutout --horizontal-crs <układ>`: CUZK nie ma
  trybu arkuszy rastra dla obszaru ([ADR-038](DECISIONS.md)). Pod `auto`
  część PL jest wtedy też wycinkiem WCS (tylko 1 m, NMT/NMPT, bez wyboru
  kampanii); arkusze PL z takiego obszaru pobiera `--country pl`. Bez
  `--cutout` — `Error:` przed siecią z tą podpowiedzią. LAZ CZ nie ma
  wycinka: obszar wybiera arkusze z indeksu CUZK (sekcja 1.4).
  Ortofotomapa obszaru CZ to arkusze SM5 (bez `--cutout`, sekcja 1.4),
  a granice i sieć wód — jeden plik obszaru na kraj (sekcja 1.9).
- Pod `auto` przycięcie do obwiedni kraju jest komunikowane jako `Info:`;
  oryginalny bbox zachowuje `extra.parent_request`, cały bbox pobiera
  `--country pl`.
- Pełne reguły (przycinanie, kody wyjścia, częściowy sukces): SCOPE 3.2,
  ARCHITECTURE 4.6, ADR-023.

### 1.3 Jeden wycinek (`--cutout`)

`--cutout` przełącza `--bbox`/`--geometry` z listy arkuszy na **jeden**
GeoTIFF obszaru; układ wyniku podaje wymagane `--horizontal-crs`
(`EPSG:2180`, `EPSG:5514`, `EPSG:3045`; ortofotomapa — tylko `EPSG:2180`,
niżej). `--horizontal-crs` bez
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
- Wycinek NMT/NMPT jest **tylko 1 m** z siatki ASC: `--resolution 1m` albo bez
  `--resolution`. Inna rozdzielczość kończy się przed siecią (kod 1)
  komunikatem `Error: wycinki PL (--cutout) sa tylko 1 m (WCS GUGiK);
  arkusze 0.5m: pomin --cutout (arkusze bez --cutout); wycinek:
  --resolution 1m albo pomin --resolution`, a archiwum (`--format`, sekcja
  1.1) — `Error: --cutout dziala tylko z siatka ASC 1m (wycinek z WCS
  GUGiK); --format TBD to pliki zrodlowe arkuszy - pomin --cutout`.
- Wybór roku (`--year`, `--min-year`, `--max-year`),
  `--all-campaigns` i `--full-sheet` z `--cutout` są
  odrzucane (`Error:`). Podobnie `--cutout` dla LAZ (ortofotomapa ma
  własny wycinek — niżej); arkusze innych rozdzielczości pobieraj bez
  `--cutout`. Szczegóły:
  [ADR-035](DECISIONS.md), [ADR-038](DECISIONS.md), ARCHITECTURE 4.3.

**Wycinek ortofotomapy (`imagery download --cutout`, od 0.8.0).** Jeden
GeoTIFF RGB obszaru PL z WCS GUGiK. Trzy wybory są wymagane, bez wartości
domyślnych: `--horizontal-crs EPSG:2180` (obraz nie jest
przepróbkowywany lokalnie, innego układu nie ma), `--coverage` (wariant
usługi) i `--resolution` (piksel wyniku: `0.1m`, `0.25m`, `0.5m`, `1m`).

```bash
# Standard, piksel 0,25 m: 500 x 500 m = 2000 x 2000 px, 9 zapytań WCS
kartograf imagery download --product orto --country pl --bbox 566000,243000,566500,243500 --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m -o ./data
#   Info: wycinek 2000 x 2000 px RGB uint8 (~11 MiB), 9 zapytan WCS GUGiK (standard 0.25m) pobieranych po kolei
#   -> orto/pl_1992_standard_0.25m/bbox/566000_243000_566500_243500.tif
# High (piksel 10 cm i mniejszy), piksel 0,1 m: 200 x 200 m = jedno zapytanie
kartograf imagery download --product orto --country pl --bbox 566000,243000,566200,243200 --cutout --horizontal-crs EPSG:2180 --coverage high --resolution 0.1m -o ./data
#   -> orto/pl_1992_high_0.1m/bbox/566000_243000_566200_243200.tif
# Ponownie: lokalna wersja bez zapytań; --force pobiera (ta sama treść = bez zmian)
kartograf imagery download --product orto --country pl --bbox 566000,243000,566200,243200 --cutout --horizontal-crs EPSG:2180 --coverage high --resolution 0.1m -o ./data --force
```

- **`standard` czy `high`.** `standard` (`Orthoimagery_StandardResolution`)
  to najnowsze dostępne ortofotomapy obszaru — kompozycja serwera z lotów
  o różnym pikselu (np. 25 cm i 10 cm); `high`
  (`Orthoimagery_High_Resolution`) zawiera tylko ortofotomapy o pikselu
  10 cm i mniejszym. Poza obszarami lotów 10 cm `high` odpowiada obrazem
  w całości czarnym (0,0,0, HTTP 200): plik powstaje, sidecar ma
  `extra.all_nodata: true`, a CLI drukuje `Warning: wycinek w calosci bez
  obrazu (piksele 0,0,0) - WCS GUGiK nie ma w tym obszarze ortofotomapy
  high (...)` (kod 0) — tam użyj `standard`. W próbkach (Kraków,
  2026-10-15/16) oba warianty dały nad tym samym obszarem te same bajty.
  Wyboru roku i lotu nie ma (`--year`, `--min-year`, `--max-year`,
  `--all-campaigns`, `--full-sheet` z `--cutout` = `Error:`); maski lądu
  PRG też nie — piksele bez zdjęć zostają 0,0,0.
- **Piksel i siatka.** Obie usługi mają krajową siatkę 0,1 m; inny piksel
  wyniku serwer liczy z `SCALEFACTOR` (np. 0,4 dla 0,25 m). Obszar jest
  rozszerzany na zewnątrz do wielokrotności piksela, a nazwa pliku niesie
  tę siatkę (EPSG:2180). Wynik jest sprawdzany (rozmiar, piksel, narożnik
  NW, 3 pasma uint8, EPSG:2180): odpowiedź na innej siatce to `Error:` bez
  nowej wersji.
- **Czas.** WCS ortofotomapy jest wolny: jedno zapytanie obejmuje
  najwyżej 200 x 200 m terenu (4 Mpx pikseli 0,1 m) niezależnie od
  piksela wyniku, więc obszar 1 x 1 km to 25 zapytań także przy `1m`.
  Pomiar 2026-10-15: 200 x 200 m przy 0,1 m (Standard) — 64 s, 100 x 100 m
  — 17 s (High 29 s); obszar 1 x 1 km to więc rząd pół godziny.
  Kartograf czeka na każdy kawałek do 300 s, pobiera kawałki po kolei
  i przed pierwszym zapytaniem drukuje `Info:` z liczbą zapytań; sprawdza
  też wolne miejsce na dysku (2 x rozmiar wyniku). Usługa Standard bywa
  przejściowo niedostępna (pomiar 2026-10-15 rano: przekroczenia czasu).
- **Złożenie kawałków.** Wycinek z kilku zapytań NIE jest bit w bit równy
  jednemu zapytaniu całego obszaru: serwer przepróbkowuje każde zapytanie
  we własnym zasięgu (pomiar 2026-10-16: 75–93 % pikseli różnych, średnio
  o 4 DN, maks. 89–120). To samo zadanie powtórzone daje te same bajty
  (`--force` = `bez zmian`), ale dwa różne obszary mogą mieć we wspólnej
  części piksele różne o kilka DN. NMT składa się bit w bit
  ([ADR-034](DECISIONS.md), errata 1).
- **Kraj.** Tylko PL: `--country cz` (albo obszar `auto` w całości w CZ)
  z `--cutout` to `Error: --cutout z --product orto dziala tylko dla PL
  ...`; pod `auto` obszar przy granicy zawęża się do PL (`Info: --country
  auto -> pl (--resolution 0.25m, --coverage standard dotyczy tylko PL)`).
  `--coverage` i `--resolution` bez `--cutout` to `Error:` (arkusze
  ortofotomapy mają piksel źródła). Wycinek jest w magazynie wersji
  (`orto/pl_1992_<coverage>_<res>/bbox/`); `--check-updates` raportuje
  `nie da sie sprawdzic bez pobrania`, nowszą treść daje `--force`.
  Szczegóły: ARCHITECTURE 4.3, [ADR-042](DECISIONS.md) D14 (errata 5).

### 1.4 Czechy (CUZK)

CZ ma rastry NMT, a od 0.8.0 także NMPT i chmury punktów LAZ. Model
rastra wybierają `--product` i `--resolution`, model LAZ —
`--model`; trasę (gotowy plik `openzu` albo usługa ImageServer) wyznaczają
wariant i godło ([ADR-041](DECISIONS.md); warianty z gotowymi flagami:
`kartograf elevation list-sources`, kolumna `WYBOR`):

| Produkt | Model (flagi) | Arkusz SM5 (np. `CTES96`) | Kafel TM33 (np. `760_5518`) | Obszar (`--bbox`/`--geometry`) |
|---|---|---|---|---|
| `nmt` | DMR 4G (`--resolution 5m`) | plik TIFF EPSG:5514, Bpv; EVRF2007 przypiętą transformacją | EVRF2007: plik TIFF EPSG:3045 (natywnie); Bpv: `exportImage` + lokalny warp | wycinek `exportImage` (`--cutout`) |
| `nmt` | DMR 5G (`--resolution 2m`) | brak (`Error:`) | `exportImage` + lokalny warp | wycinek `exportImage` (`--cutout`) |
| `nmpt` | DMP OK (`--resolution 0.5m`) | jak DMR 4G | jak DMR 4G | wycinek `exportImage` (`--cutout`) |
| `nmpt` | DMP 1G (`--resolution 2m`) | brak (`Error:`) | `exportImage` + lokalny warp | wycinek `exportImage` (`--cutout`) |
| `laz` | `--model dmr5g`, `dmr4g`, `dmp1g`, `dmpok` | `.laz` EPSG:5514, tylko `--vertical-crs Bpv` | `.laz` EPSG:3045, tylko `--vertical-crs EVRF2007` | arkusze z indeksu CUZK (Bpv: SM5, EVRF2007: TM33), bez `--cutout` |

```bash
# DMR 5G (2 m), godło TM33 (ten kafel leży w większości w Niemczech — głównie nodata)
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv -o ./data
kartograf elevation download --sheet CTES96 --product nmt --vertical-crs Bpv -o ./data # DMR 4G (5 m), godło SM5, kraj z godła
kartograf elevation download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m -o ./data # Bpv -> EVRF2007 (EPSG:5621)
# DMR 4G, kafel TM33 w EVRF2007: gotowy plik ETRS89 (EPSG:3045), bez transformacji
kartograf elevation download --sheet 760_5518 --product nmt --resolution 5m --vertical-crs EVRF2007 -o ./data
# NMPT DMP OK (0,5 m): arkusz SM5 (Bpv) i kafel TM33 (EVRF2007) z plików CUZK
kartograf elevation download --sheet CTES96 --product nmpt --resolution 0.5m --vertical-crs Bpv -o ./data
kartograf elevation download --sheet 760_5518 --product nmpt --resolution 0.5m --vertical-crs EVRF2007 -o ./data
# NMPT DMP 1G (2 m): kafel TM33 z usługi (warp)
kartograf elevation download --sheet 760_5518 --product nmpt --resolution 2m --vertical-crs Bpv -o ./data
# obszar CZ = jeden wycinek (--cutout); reprojekcja (tylko --bbox/--geometry,
# nie godło) lokalnie przypiętą operacją
kartograf elevation download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --cutout --horizontal-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv -o ./data
# pogranicze pod auto: osobne wycinki PL (WCS 1 m) i CZ, wspólny
# extra.parent_request; różne wartości dla krajów w postaci pl=...,cz=...
kartograf elevation download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:5514 --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv -o ./data
# bboxy w EPSG:5514 są na terytorium CZ ujemne — podaj je jako --bbox=... (bez spacji),
# inaczej argparse odczyta wartość jako nieznaną flagę
kartograf elevation download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --cutout --horizontal-crs EPSG:5514 --resolution 5m --product nmt --vertical-crs Bpv -o ./data
kartograf elevation download "--bbox=-447000,-1114000,-446600,-1113600" --bbox-crs EPSG:5514 --country cz --cutout --horizontal-crs EPSG:5514 --resolution 2m --product nmpt --vertical-crs Bpv -o ./data # wycinek DMP 1G
# LAZ CZ: --model wybiera model, --vertical-crs pliki (Bpv = arkusze SM5, EVRF2007 = kafle TM33)
kartograf elevation download --sheet CTES96 --product laz --model dmr5g --vertical-crs Bpv -o ./data
kartograf elevation download --sheet 760_5518 --product laz --model dmpok --vertical-crs EVRF2007 -o ./data
kartograf elevation download "--bbox=-447000,-1114000,-444000,-1113000" --bbox-crs EPSG:5514 --country cz --product laz --model dmr4g --vertical-crs Bpv -o ./data
# pogranicze pod auto: kafle LAZ PL (WFS GUGiK) i arkusze CZ, wspólny extra.parent_request
kartograf elevation download --bbox 18.615,49.740,18.640,49.755 --bbox-crs EPSG:4326 --country auto --product laz --model dmr4g --vertical-crs pl=EVRF2007,cz=Bpv -o ./data
```

`kartograf parse` obsługuje tylko godła PL (PL-1992/PL-2000); godła CZ
(TM33, SM5) przyjmują `kartograf elevation download` i (SM5)
`kartograf imagery download`. Od 0.8.0 działają też dwuliterowe godła SM5
(99 arkuszy As, `AS22`…`AS94`, np. `AS91`) — wcześniej kończyły się
błędem godła PL, także dla DMR.

**Wartości per kraj.** `--resolution` i `--vertical-crs` przyjmują jedną
wartość dla każdego kraju zadania (`--resolution 5m`) albo pary
`kraj=wartość` (`--resolution pl=1m,cz=2m`, `--vertical-crs
pl=EVRF2007,cz=Bpv`). Jedna wartość musi być dostępna w każdym kraju
zadania (wspólne: NMT `5m`, NMPT `0.5m`, `EVRF2007`; wycinek PL ma
tylko 1 m, więc wycinki PL+CZ potrzebują zwykle formy per kraj);
inaczej `Error:` przed siecią
z podpowiedzią formy per kraj. Klucz kraju spoza zadania nie jest
błędem. Zwykłe `--resolution 1m` albo `--vertical-crs KRON86` pod `auto`
wskazują PL (`Info: --country auto -> pl`), bo CZ ich nie ma.
Prostokątne obwiednie krajów mogą uruchomić CZ także dla obszaru
w Polsce (część CZ bywa wtedy w całości nodata).

- Rozdzielczość CZ: arkusz SM5 (np. `CTES96`) to gotowy plik DMR 4G
  (NMT, tylko 5 m) albo DMP OK (NMPT, tylko 0,5 m) — `--resolution` można
  pominąć, a inna wartość jest błędem (`Error:`, kod 1, bez sieci). Kafel
  TM33 i `--bbox`/`--geometry` (wycinek, `--cutout`) wymagają
  `--resolution`: NMT `2m` (DMR 5G) albo `5m` (DMR 4G), NMPT `0.5m`
  (DMP OK) albo `2m` (DMP 1G). Kafel TM33 DMR 4G i DMP OK
  z `--vertical-crs EVRF2007` to gotowy plik ETRS89 (EPSG:3045) z CUZK;
  pozostałe kafle i wycinki są wycinane z usługi ImageServer.
- Obszar CZ NMT/NMPT (`--bbox`/`--geometry`) to zawsze jeden wycinek
  i wymaga `--cutout --horizontal-crs` (natywnie `EPSG:5514`); bez
  `--cutout` `Error:` przed siecią. PL bez `--cutout` daje listę arkuszy,
  ortofoto CZ obszaru — arkusze SM5 (niżej).
- LAZ CZ (`--product laz`): `--model` wybiera model — `dmr5g` (teren,
  DMR 5G), `dmr4g` (teren, siatka 5 m), `dmp1g` (powierzchnia, DMP 1G),
  `dmpok` (powierzchnia, korelacja obrazowa) — i jest wymagane, gdy
  zadanie obejmuje CZ; z zadaniem tylko PL albo z rastrem to `Error:`.
  Plik `.laz` trafia do magazynu bajt w bajt jak w ZIP-ie CUZK, bez
  transformacji punktów, więc `--vertical-crs` wybiera pliki: `Bpv` =
  arkusze SM5 (S-JTSK, EPSG:5514), `EVRF2007` = kafle TM33 (ETRS89,
  EPSG:3045); godło drugiego systemu to `Error:` przed siecią. Obszar
  rozwija się do arkuszy indeksu CUZK tego systemu (arkusze SM5 z częścią
  w CZ, kafle TM33); `--cutout`, `--resolution`, rok, kampanie
  i `--min-density` dotyczą tylko LAZ PL (`Error:`). Plik, którego nie
  udało się pobrać, nie przerywa pozostałych (`Error:` dla arkusza,
  kod 1).
- Porażka jednego kraju pod `auto` (brak danych albo awaria źródła) przy
  sukcesie drugiego kończy się kodem 0: na stderr `Warning:` o częściowym
  sukcesie i `Error:` z przyczyną porażki; kod 1, gdy żaden kraj nie dał
  wyniku albo `--country` było jawne.
- Natywnie S-JTSK/Bpv (EPSG:5514: arkusze SM5, usługa ImageServer)
  i ETRS89/EVRF2007 (EPSG:3045/5621: pliki kafli TM33 DMR 4G i DMP OK,
  LAZ TM33); `KRON86` dla CZ jest nieosiągalny.
  Szczegóły: SCOPE 2.2 i 3.2, ARCHITECTURE 4.4–4.7.
- Magazyn wersji (0.8.0): arkusz CZ, plik LAZ CZ i wycinek CZ leżą jako
  wersje w `<segment>/versions/`, ścieżka arkusza i `bbox/<współrzędne>.tif`
  to hardlinki (segmenty `nmt/cz_dmr5g_<vcrs>`, `nmt/cz_dmr4g_<vcrs>`,
  `nmpt/cz_dmpok_<vcrs>`, `nmpt/cz_dmp1g_<vcrs>`, `laz/cz_<model>_<vcrs>`).
  Pliki `openzu` — arkusz SM5, kafel TM33 DMR 4G/DMP OK w EVRF2007
  i LAZ CZ — mają tani sygnał (`ETag`/`Last-Modified` pliku, zapisany
  w `extra.http` sidecara wersji): domyślnie jedno
  `HEAD` na plik z lokalną wersją — nowsza treść daje dopisek `; dostepna
  nowsza ... (--upgrade)`, a `--upgrade` ją pobiera; nieudane `HEAD` to
  `Warning:` i lokalna wersja (z `--upgrade` — błąd). Kafel TM33
  z ImageServer i wycinek CZ (`exportImage`) nie mają taniego sygnału:
  lokalna wersja bez sieci, ponowne pobranie tylko `--force`.
- Kafel TM33 DMR 4G w EVRF2007 zapisany w magazynie wersji przed tą
  zmianą (warp z ImageServer, bez `extra.http`) zostaje lokalną wersją
  z `Info:` (niesprawdzona); `--force` pobiera plik CUZK jako nową wersję
  i przepina dowiązanie. Zwykły plik z 0.7.x w ścieżce standardowej jest
  zastępowany przy pierwszym pobraniu.

**Ortofoto CZ (`imagery download --country cz`, od 0.8.0).** Arkusz SM5
z usługi ATOM CUZK to cztery pliki zapisane 1:1, bez konwersji pikseli:
zdjęcie JPEG i trzy pliki georeferencji (world file JGW) w układach
S-JTSK, ETRS89 / UTM 33N i ETRS89 / UTM 34N.

```bash
# arkusz SM5 (kraj z godła); godło As ma 2 litery
kartograf imagery download --product orto --sheet CTES96 -o ./data
#   -> orto/cz_sjtsk/CTES/96/: CTES96.jgw, CTES96.TM33N.jgw, CTES96.TM34N.jgw, CTES96.jpg
#      (wersja <rok>_<wydanie>, np. 2024_2025-02-06_<sha8>; ZIP CUZK 16-64 MB)
kartograf imagery download --product orto --country cz --sheet AS91 -o ./data
# obszar = arkusze SM5 z indeksu CUZK (tu CTES86 i CTES96), bez --cutout
kartograf imagery download --product orto --country cz "--bbox=-448500,-1113500,-446500,-1112500" --bbox-crs EPSG:5514 -o ./data
# pogranicze pod auto: arkusze PL (--sheet-system dla części PL) i arkusze SM5 CZ
kartograf imagery download --product orto --country auto --bbox 18.60,49.74,18.64,49.76 --bbox-crs EPSG:4326 --sheet-system 1992 -o ./data
# nowszy rocznik bez pobierania zdjęć (wydanie z feedu ATOM)
kartograf imagery download --product orto --sheet CTES96 --check-updates -o ./data
kartograf imagery list-sources   # --product orto (PL: pl.gugik.orto, CZ: cz.cuzk.ortofoto)
```

- **Układ w GIS.** Plik JGW nie niesie układu współrzędnych. GIS czyta
  georeferencję JPEG z pliku o tej samej nazwie (`CTES96.jpg` +
  `CTES96.jgw`) — przypisz warstwie układ **EPSG:5514** (S-JTSK /
  Krovak East North). `CTES96.TM33N.jgw` georeferuje ten sam obraz
  w EPSG:3045 (ETRS89 / UTM 33N), a `CTES96.TM34N.jgw` w EPSG:3046
  (ETRS89 / UTM 34N); żeby ich użyć, skopiuj JPEG poza magazyn i nadaj
  kopii pliku TM nazwę `<kopia>.jgw` (plików w magazynie nie zmieniaj —
  to dowiązania twarde do wersji). Układ każdego pliku podaje jego
  sidecar (`horizontal_crs`), a sidecar JPEG także mapę
  `extra.world_files` (`.jgw` EPSG:5514, `.TM33N.jgw` EPSG:3045,
  `.TM34N.jgw` EPSG:3046; pomiar 2026-10-16: zgodność do 3 cm). Piksel
  arkuszy w próbkach: 0,125 m.
- **Tylko aktualny rocznik.** CUZK publikuje bezpłatnie jedno, aktualne
  wydanie arkusza (archiwalne ortofoto CUZK są płatne): `--year`,
  `--min-year`, `--max-year`, `--all-campaigns`, `--full-sheet`,
  `--sheet-system`, `--scale`, `--format` i `--resolution` z `--country cz`
  to `Error:` (np. `--year dotyczy tylko PL - CUZK publikuje tylko
  aktualny rocznik arkusza ortofoto CZ (archiwalne ortofoto CUZK sa
  platne, poza zakresem)`); pod `auto` flagi roku i arkuszy dotyczą części
  PL. Kafel TM33 jako `--sheet` to `Error: ortofoto CZ ma arkusze SM5 (np.
  CTES96, AS91); kafle TM33 sa tylko dla NMT ...`; `--cutout` z CZ — `Error:`.
- **Aktualność.** Etykieta wersji to rok i data wydania z feedu ATOM
  (`2024_2025-02-06`). Domyślnie lokalne pliki są porównywane z feedem
  (nowszy rocznik = dopisek `; dostepna nowsza ... (--upgrade)`),
  `--check-updates` sprawdza wydanie bez pobierania zdjęć, `--upgrade`
  pobiera nowy rocznik (stare wersje zostają w `versions/`), `--force`
  pobiera ponownie (ta sama treść = `bez zmian`). Jeden arkusz to jedno
  pobranie ZIP i jedno sprawdzenie wydania; nieudane sprawdzenie daje
  jedno `Warning:` na arkusz. Pliki JGW są zapisywane przed JPEG, więc
  wersja zdjęcia zawsze ma pliki georeferencji.
- **Pogranicze.** Pod `--country auto` obszar przy granicy daje arkusze
  PL i arkusze SM5 CZ (dotąd `auto` zawężało ortofotomapę do PL);
  pliki obu krajów mają wspólne `extra.parent_request`. Szczegóły:
  ARCHITECTURE 4.4, [ADR-042](DECISIONS.md) D13 (errata 4).

**Warstwice CZ (`elevation download --product contours`, od 0.8.0).**
Warstwice ZABAGED CUZK: ZIP arkusza SM5 z openzu zapisany 1:1 (bez
rozpakowania), S-JTSK (EPSG:5514), wysokości Bpv.

```bash
kartograf elevation download --product contours --format SHP --sheet CTES96 -o ./data
#   -> contours/cz_zabaged_shp/CTES/96/CTES96.zip (8 plików SHP)
kartograf elevation download --product contours --format DGN --sheet CTES96 -o ./data
#   -> contours/cz_zabaged_dgn/CTES/96/CTES96.zip (3 pliki)
# obszar = arkusze SM5 z indeksu CUZK (tu CTES86 i CTES96)
kartograf elevation download --product contours --format SHP --country cz "--bbox=-448500,-1113500,-446500,-1112500" --bbox-crs EPSG:5514 -o ./data
```

- `--format SHP|DGN` jest wymagane; `--vertical-crs` można pominąć (tylko
  `Bpv`). `--resolution`, `--cutout`, `--horizontal-crs`, flagi arkuszy PL
  i lotów to `Error: ... warstwice to arkusze SM5 (wektor) - bez
  rozdzielczosci, lotow i wycinka`; kafel TM33 i `--country pl` - `Error:`.
- Aktualność: sygnał HTTP (`ETag`) - lokalna wersja po jednym `HEAD`,
  `--check-updates` bez pobierania. Sidecar ma listę plików ZIP
  (`extra.members`), `mapname` i `cz_share` z indeksu.

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

# BDOO (baza ogólnogeograficzna GUGiK, 1:250 000): paczka GML województwa
# na rocznik (--year wymagany: 2015, 2021-2026); --teryt = kod województwa
kartograf landcover download --source bdoo --teryt 12 --year 2023 -o ./data
#   landcover/pl_bdoo_2023/teryt/12.zip: nowa wersja 2023_bd431599   (ZIP 1:1, 11,5 MB)
# obszar = paczki województw jego powiatów (PRG); --layers = ZIP plików wybranych klas
kartograf landcover download --source bdoo --bbox 523000,253000,528000,258000 \
    --year 2023 --layers KUIK,PTWP -o ./data
#   Info: bdoo: wojewodztwa obszaru wg PRG (2): 12 (malopolskie), 24 (slaskie)
#   Info: bdoo PL 24: paczka nie ma plikow klas KUIK (brak takich obiektow); zapisano klasy PTWP
#   landcover/pl_bdoo_2023_kuik-ptwp/teryt/12.zip: nowa wersja 2023_830c40f8
#   landcover/pl_bdoo_2023_kuik-ptwp/teryt/24.zip: nowa wersja 2023_79659873
#   Nowe: 2, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 0 (./data)

# Hydrologic Soil Groups dla metody SCS-CN (wejścia clay/sand/silt w tym samym magazynie)
kartograf soil hsg --bbox 626000,480000,628000,482000 --depth 0-5cm --stats -o ./data
#   soil/global_soilgrids_{clay,sand,silt}_0-5cm_mean/bbox/...: nowa wersja 2.0_<sha8>
#   hsg/global_soilgrids_0-5cm_mean/bbox/626000_480000_628000_482000.tif: nowa wersja 2.0_470ef3d9
# Ponownie (także z --force, gdy treść wejść się nie zmieniła): ... uzyta ponownie 2.0

# Przegląd źródeł/warstw i cache metadanych
kartograf landcover list-sources
kartograf landcover list-layers --source zabaged   # 22 warstwy ZABAGED (sekcja 1.9)
kartograf landcover list-layers --source bdoo      # klasy BDOO każdego rocznika (--year)
kartograf soil list-layers
kartograf cache stats
kartograf cache clear
kartograf cache path
```

`--output` to katalog magazynu (wersje w `versions/`, ścieżka standardowa
= hardlink; ARCHITECTURE 3.3 reguła 8); `soil hsg -o plik.tif` to
`Error:` (plik poza magazynem: `hsg_from_rasters`). `--teryt` dotyczy
BDOT10k (powiat, 4 cyfry) i BDOO (województwo, 2 cyfry); CORINE i SoilGrids
wybierają obszar przez `--sheet`, `--bbox` albo `--geometry`. BDOT10k
z `--bbox`/`--sheet`/`--geometry` pobiera wszystkie powiaty obszaru (lista
z WFS PRG, odpowiedzi w cache metadanych — `cache stats` liczy je
w `Wpisy TERYT`); błąd jednego powiatu to `Error: <TERYT>: ...`, reszta
się pobiera, kod 1; obszar bez powiatu (morze) to `Error:`. Tryby
`--check-updates`/`--upgrade`/`--force`/`--plan`: sekcja 4.3. CORINE bez
credentials CLMS pobiera podgląd PNG (sekcja 6). Warstwy BDOT10k,
parametry SoilGrids i lata CORINE: PRD 3.5–3.7. ZABAGED, Data50 i Data250
(`--source zabaged|data50|data250`, CZ: obszar albo plik krajowy): sekcja 1.9.

**BDOO.** `--source bdoo` pobiera bazę danych obiektów ogólnogeograficznych
GUGiK (1:250 000) tak, jak ją publikuje GUGiK: paczkę GML województwa na
rocznik (`--year` wymagany; roczników 2014 i 2016–2020 nie ma — `Error:`
z listą, przed siecią). Pliku krajowego nie ma. Kod powiatu (`--teryt 1261`)
kończy się `Error:` z podpowiedzią `--teryt 12`; obszar (`--bbox`,
`--sheet`, `--geometry`) daje paczki wszystkich województw, które przecina
(lista w `Info:`; błąd jednego województwa nie zatrzymuje pozostałych,
`--workers` pobiera równolegle, na końcu linia podsumowania). `--layers`
(kody klas, np. `PTWP,SWRS`; lista: `landcover list-layers --source bdoo`)
zapisuje ZIP plików `__OT_<KOD>_<typ>` wybranych klas w osobnym segmencie
(`pl_bdoo_2023_ptwp-swrs`): pliki są bajt w bajt jak w paczce, a obiekty
złożone (`__OT_Ciek` itp.), XSD i metadane zostają tylko w pełnej paczce.
Paczki do 2023 nie mają pliku klasy, której obiektów nie ma
w województwie: brak części wybranych klas to `Info:`, brak wszystkich —
błąd tego województwa. Klasa spoza rocznika (np. `KUIK` od 2024) to
`Error:` z listą klas rocznika. Wersja ma etykietę rocznika; GUGiK nie
podaje sygnału zmian, więc `--check-updates` zgłasza „nie da się sprawdzić
bez pobrania”, a `--force` pobiera ponownie (ta sama treść = `bez zmian`).

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
GUGiK, a w Czechach (od 0.8.0) — które arkusze SM5 i kafle TM33 obszaru
mają pliki CUZK. Czyta wyłącznie skorowidz WFS (ten sam, z którego pobiera
`elevation download`) i maskę lądu PRG, a dla CZ indeks arkuszy
`KladyMapovychListu` i nagłówki plików `openzu` (`HEAD`); żadnego pliku
danych nie pobiera. Obszar wybiera się jak w `elevation download`:
`--sheet` (godło PL-1992, PL-2000 albo CZ SM5/TM33; kraj z godła),
`--bbox` (`--bbox-crs`) albo `--geometry` (`--layer`) — dwa ostatnie
z `--country pl`, `cz` albo `auto` (bez flagi `Error: --country wymagane
z --bbox/--geometry: pl (GUGiK), cz (CUZK), auto (...)`).
`--year`/`--min-year`/`--max-year` zawężają roczniki skorowidza — tylko
PL: z `--country cz` albo godłem CZ to `Error:`, pod `auto` obszar PL+CZ
zawęża się do PL (`Info:`), a obszar tylko w CZ to `Error:`.

```bash
kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000
kartograf elevation availability --product nmpt --sheet M-34-64-D-d-2-1
kartograf elevation availability --product laz --country pl --geometry zlewnia.gpkg --layer catchments --min-year 2020
kartograf elevation availability --product nmt --country pl --bbox 339000,744800,343000,747000 --details
kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000 --json > krakow.json
# Czechy i pogranicze (od 0.8.0)
kartograf elevation availability --product nmpt --sheet CTES96
kartograf elevation availability --product nmpt --country cz "--bbox=-447000,-1114000,-446600,-1113600" --bbox-crs EPSG:5514
kartograf elevation availability --product laz --country cz "--bbox=-450000,-1114000,-444000,-1113000" --bbox-crs EPSG:5514 --details
kartograf elevation availability --product nmpt --country auto --bbox 18.615,49.740,18.640,49.755 --bbox-crs EPSG:4326 --json
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
  jak arkusze `elevation download`) mierzone dokładnie; LAZ — rama
  arkusza albo obwiednia całej geometrii, jak przy pobieraniu kafli. Arkusz
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
roku istnieje — `--full-sheet`. Polecenie obszaru (albo godła) pojawia
się tylko wtedy, gdy jego pobranie planuje wyłącznie arkusze z rekordem
kombinacji. Gdy siatka obszaru ma też arkusz bez takiego rekordu (za
granicą, na morzu, bez danych z tego roku albo w tej rozdzielczości),
podpowiedź to po jednym poleceniu `--sheet` na każdy arkusz z rekordem —
żadne polecenie podpowiedzi nie kończy się `Brak danych` (kod 1); przy
więcej niż 5 poleceniach stopka podaje 5 i liczbę pozostałych
(wszystkie: `--details` albo `--json`).
Archiwa (`--format`) i LAZ mają zawsze polecenie obszaru albo godła
zadania. Bez kompletnej kombinacji stopka mówi
`Zadna kombinacja nie pokrywa calego ladu obszaru pelnymi arkuszami
(arkusze niepelne i brakujace: --details)`.

`--details` dopisuje dla każdej kombinacji godła arkuszy niepełnych, ląd
bez arkuszy i polecenia pobrania (fragment, Pomorze — siatka obszaru ma
arkusze morskie bez rekordów, więc rastry dostają polecenia `--sheet`):

```
Szczegoly kombinacji:
  2025 PL-1992 0.5m EVRF2007 ASC: nie: 4 niepelne
    arkusze niepelne (4): N-33-58-A-c-1-3, N-33-58-A-c-1-4, N-33-58-A-c-2-3, N-33-58-A-c-3-1
    kartograf elevation download --product nmt --sheet N-33-58-A-c-1-3 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
    kartograf elevation download --product nmt --sheet N-33-58-A-c-1-4 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
    kartograf elevation download --product nmt --sheet N-33-58-A-c-2-3 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
    kartograf elevation download --product nmt --sheet N-33-58-A-c-3-1 --resolution 0.5m --vertical-crs EVRF2007 --year 2025
  2023 PL-1992 5m EVRF2007 ASC: nie: brak arkuszy dla 0,88 ha
    lad bez zadnego arkusza kombinacji: 0,88 ha
    kartograf elevation download --product nmt --sheet N-33-58-A-c-1-4 --resolution 5m --vertical-crs EVRF2007 --year 2023 --full-sheet
    kartograf elevation download --product nmt --sheet N-33-58-A-c-2-3 --resolution 5m --vertical-crs EVRF2007 --year 2023 --full-sheet
    kartograf elevation download --product nmt --sheet N-33-58-A-c-3-1 --resolution 5m --vertical-crs EVRF2007 --year 2023 --full-sheet
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
`ok`, `schema`. Pola `sheets_missing` i `size_bytes` wypełnia tylko część
CZ (w PL `[]`/`null`). Początek (Kraków):

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
  daje `Brak arkuszy NMT dla obszaru w skorowidzu GUGiK` (LAZ: `kafli`;
  CZ: `Brak arkuszy NMPT dla obszaru w indeksie CUZK`)
  i kod 0. Awaria skorowidza albo PRG (sieć, strona WFS niespójna,
  raport OGC) to `Error:` i kod 1 — nigdy pusty raport; tak samo awaria
  indeksu CUZK albo `HEAD` pliku inna niż `404`. Zakres lat bez
  żadnego rocznika usługi: `Error: --year 2030: skorowidz GUGiK NMT nie
  ma rocznika ... - dostepne roczniki: ...`.
- **`Info:`** (kod `index_unsupported` w bibliotece) wymienia rekordy
  obszaru, których Kartograf nie pobiera: format rekordu niezgodny
  z plikiem, wariant spoza rejestru albo godło spoza układów PL-1992/PL-2000
  (np. 8-członowe godła ASCII NMT 10 m i części ASC 1 m, sekcja 7).
  Archiwa z rejestru nie trafiają do `Info:` — są kombinacjami.
- **Cache:** typy warstw WFS, rekordy obszaru z obrysami arkuszy i maska
  lądu PRG, a dla CZ arkusze indeksu i wyniki `HEAD` plików trafiają do
  cache metadanych (`.kartograf_cache.db`, TTL
  7 dni; `kartograf cache stats`: `Wpisy obszarow skorowidza`), więc
  ponowny raport dla tego samego obszaru nie pyta sieci (pomiar
  2026-10-15: 0,6–1,5 s zamiast ok. 5–7 s dla 16 km2). `--force`
  pomija odczyt cache, odpytuje skorowidz, PRG i CUZK ponownie i nadpisuje
  wpisy.
- **Czas:** maska lądu jest rasteryzowana na siatce 1 m w pasach po
  4 Mpx, więc raport dla dużego obszaru (np. całej zlewni) liczy się
  odpowiednio dłużej (sekcja 7).
- **Projekt:** `availability` nie jest komendą danych projektu
  (`kartograf project add NAZWA elevation availability ...` = `Error:`);
  do manifestu dodaj polecenie z linii `W projekcie` (sekcja 8).

**Czechy (CUZK).** CUZK nie publikuje lat nalotu, więc kombinacja CZ to
model i układ arkuszy z plikami w natywnym układzie wysokości: NMT —
DMR 4G (`S-JTSK` Bpv i `ETRS89-TM33` EVRF2007), NMPT — DMP OK (te same
dwa układy), LAZ — osiem kombinacji (cztery modele × dwa układy). DMR 5G
i DMP 1G nie mają plików arkuszy: raport ich nie obejmuje i mówi o tym
w `Info:` (są dostępne jako wycinek `--cutout`, kafel TM33 z usługi
i LAZ `--model`) — o ile część CZ ma choć jeden arkusz indeksu (nie ma go
np. część `auto` w głębi Polski wewnątrz prostokąta CZ). Arkusze to
arkusze indeksu w części CZ obszaru (SM5 z częścią w CZ, kafle TM33) —
te same, które pobiera LAZ dla obszaru; każdy plik sprawdza jedno `HEAD`:
`200` = plik (`PUBLIKACJA` z `Last-Modified`, `ROZMIAR` — suma
`Content-Length`; `-`, gdy żaden arkusz kombinacji nie ma pliku), `404`
= arkusz bez pliku (`ARKUSZE SA/BRAK` = z plikiem/bez pliku,
`sheets_missing`, kombinacja niekompletna, `uncovered_m2` — część
prostokąta obszaru w ramach takich arkuszy, nigdy więcej niż `area_m2`),
każda inna odpowiedź (`503`, sieć) to `Error:`, nigdy brak danych. Pole
`area_m2` części CZ to prostokąt tej części w EPSG:5514 (godło: jego
rama) — CZ nie ma maski lądu, więc przy granicy obejmuje też terytorium
PL. Pod `--country auto` raport ma osobne tabele i `areas` PL i CZ;
część, której nie udało się sprawdzić, przy sprawdzonej drugiej daje
`Warning:`, `ok: false` w JSON i kod 1 (raport drugiej części jest
wypisany). Stopka CZ podaje polecenia kompletnych kombinacji: raster —
po jednym na arkusz (`--sheet`, `--resolution`, natywne
`--vertical-crs`), LAZ — jedno polecenie obszaru z `--country cz`
i `--model` (przy godle — po jednym na arkusz); przy więcej niż
5 poleceniach kombinacji stopka podaje 5 i liczbę pozostałych
(wszystkie: `--details` albo `--json`). Do polecenia dopisz `--output
KATALOG` (w projekcie: `kartograf project add NAZWA` zamiast
`kartograf`).

Czechy (NMPT, bbox 400 x 400 m przy Czeskim Cieszynie; wydruk na żywo
2026-10-16, ok. 1,3 s, z cache 0,6 s; raport E2E:
`docs/research/2026-10-16-plan-b-e2e/raport.md`):

```
Dostepnosc NMPT CZ wg indeksu arkuszy i plikow CUZK: obszar 16,00 ha
CUZK nie publikuje lat nalotu; daty = publikacja pliku

  MODEL   UKLAD        ROZDZ.  WYSOKOSCI  FORMAT  ARKUSZE SA/BRAK  PUBLIKACJA  ROZMIAR  KOMPLET
  DMP OK  S-JTSK       0.5m    Bpv        TIFF    1/0              2025-10-10  16,7 MB  tak
  DMP OK  ETRS89-TM33  0.5m    EVRF2007   TIFF    1/0              2026-08-20  29,6 MB  tak

Kompletne kombinacje CZ (pobranie: dodaj --output KATALOG; w projekcie: kartograf project add NAZWA zamiast kartograf):
  DMP OK S-JTSK 0.5m Bpv TIFF
    kartograf elevation download --product nmpt --sheet CTES86 --resolution 0.5m --vertical-crs Bpv
  DMP OK ETRS89-TM33 0.5m EVRF2007 TIFF
    kartograf elevation download --product nmpt --sheet 760_5516 --resolution 0.5m --vertical-crs EVRF2007
```

Na stderr: `Info: DMP 1G (2m) nie ma plikow arkuszy CUZK (raport ich nie
obejmuje) - jest dla calego CZ jako wycinek (--cutout), kafel TM33
z uslugi ImageServer (--sheet, np. 302_5550) i LAZ (--product laz --model
dmp1g)`.

### 1.8 Granice, ewidencja, modele 3D budynków i archiwum BDOT10k

Grupy `boundaries` (granice PRG, `--product admin`; punkty adresowe
`addresses`; granice specjalne `special`), `cadastre` (EGiB i mapa
katastralna CZ, `--product map`; ceny RCN, `--product prices`)
i `models3d` (modele 3D budynków, `--product buildings`)
mają wspólny kształt (ADR-042): dokładnie jeden wybór — `--teryt` (paczka
jednostki), obszar `--bbox`/`--sheet`/`--geometry` (z `--country`) albo
`--whole-country` (plik krajowy; tylko `boundaries`) — oraz tryby
`--check-updates`/`--upgrade`/`--force`/`--plan`, `--workers` i `-q` jak
w pozostałych grupach. Każda grupa ma tylko swoje flagi treści (`--level`
i `--format` w `boundaries`, `--format` i `--ku` w `cadastre`,
`--lod`/`--year` w `models3d`; obca flaga to błąd parsera, kod 2).
`models3d` jest tylko dla Polski (`--country pl`); `boundaries` ma też
granice CZ (RUIAN) i jednostki geomorfologiczne CZ, `cadastre` — mapę
katastralną CZ, a sieć wód CZ — grupa `hydro` (sekcja 1.9; przykłady CZ
tego rozdziału także tam). Archiwum roczników BDOT10k jest w grupie
`landcover` (`--year`). Mesh 3D i modele drzew (`models3d`) oraz osnowy
i quasi-geoidy (grupa `geodesy`) opisuje sekcja 1.11.

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

# Punkty adresowe i ulice PRG (od 0.8.0): obszar, paczka powiatu, plik krajowy
kartograf boundaries download --product addresses --country pl --bbox 566000,243500,566500,244000 -o ./data
#   boundaries/pl_prg_addresses/bbox/566000_243500_566500_244000.gpkg: nowa wersja 2026-10-16_f8981d39
kartograf boundaries download --product addresses --teryt 1261 -o ./data
#   boundaries/pl_prg_addresses_shp/teryt/1261.zip: nowa wersja 2026-10-16_ad2e3b66
kartograf boundaries download --product addresses --country pl --whole-country --format SHP -o <katalog-danych>
#   Warning: addresses PL: plik krajowy https://opendata.geoportal.gov.pl/prg/adresy/PunktyAdresowe/POLSKA.zip - 563815148 B (ok. 564 MB)
#   boundaries/pl_prg_addresses_shp/country/pl.zip: nowa wersja 2026-10-16_957a5138

# Granice specjalne PRG: obszar (44 rodzaje, GPKG w OGC:CRS84) albo plik krajowy
kartograf boundaries download --product special --country pl --bbox 21.0,52.22,21.01,52.23 --bbox-crs EPSG:4326 -o ./data
#   Info: special: wynik obszaru bez obwodow spisowych (kolekcja GranicaObwoduSpisowego: usluga odpowiada minutami) - sa w pliku krajowym: --whole-country --format SHP|GML
#   boundaries/pl_prg_special/bbox/21_52.22_21.01_52.23.gpkg: nowa wersja 2026-10-16_07b97606
kartograf boundaries download --product special --country pl --whole-country --format SHP -o <katalog-danych>
#   Warning: special PL: plik krajowy https://opendata.geoportal.gov.pl/prg/granice/00_granice_specjalne_shp.zip - 734171465 B (ok. 734 MB)

# RCN (ceny nieruchomości): eksport powiatu (4 cyfry) albo województwa (2 cyfry)
kartograf cadastre download --product prices --teryt 1201 -o ./data
#   cadastre/pl_rcn/teryt/1201.gpkg: nowa wersja 2026-10-16_a612f064
kartograf cadastre download --product prices --teryt 1261 -o <katalog-danych>
#   Warning: prices PL 1261: duzy plik https://opendata.geoportal.gov.pl/InneDane/latest_exports/rcn_transakcje_ceny/GPKG/1261_transakcje_ceny.gpkg.zip - 301623607 B (ok. 302 MB)
#   cadastre/pl_rcn/teryt/1261.gpkg: nowa wersja 2026-10-16_ed4cc8bb

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

**Adresy PRG.** `--product addresses` (tylko PL) ma trzy wybory:
obszar (`--bbox`/`--sheet`/`--geometry` z `--country pl`) daje jeden
GeoPackage w EPSG:2180 z warstwami punktów adresowych i ulic obszaru
(usługa WFS KIN GUGiK); `--teryt` przyjmuje tylko powiat (4 cyfry) i daje
paczkę SHP 1:1 — `--teryt 12` to `Error:` z listą wyborów (paczek
województw nie ma); `--whole-country --format SHP|GML` to plik krajowy
(ok. 564 MB albo ok. 804 MB), którego rozmiar pojawia się jako `Warning:`
przed transferem. `--format` jest wymagane tylko z plikiem krajowym.

**Granice specjalne PRG.** `--product special` (tylko PL) wymaga obszaru
albo `--whole-country --format SHP|GML` (ok. 734 MB dla SHP); `--teryt` to
`Error:`. Wynik obszaru to jeden GeoPackage w OGC:CRS84 z 44 rodzajami
granic (sądy, policja, urzędy skarbowe, lasy, wody, obszary morskie, ...),
po jednej warstwie na rodzaj z obiektami przecinającymi obszar. Obszar
trwa minuty (usługa OGC API PRG jest odpytywana o każdą kolekcję osobno;
pomiar: Kraków 243 s, Warszawa 109 s), a przekroczenie limitu czasu
(120 s) jest ponawiane. Obwody spisowe (`GranicaObwoduSpisowego`) nie są
częścią wyniku obszaru — usługa odpowiada na nie od 158 do ponad 400 s —
więc każdy obszar dostaje `Info:` wskazujący plik krajowy, w którym są.

**RCN.** `--product prices` (tylko PL): `--teryt` z 4 cyframi to eksport
powiatu, z 2 cyframi — województwa, a obszar to eksport każdego powiatu
obszaru. Plik to GeoPackage w EPSG:2180 z warstwami
`transakcje_dzialki`, `transakcje_budynki` i `transakcje_lokale`,
odświeżany co dobę (plik jest podmieniany bez sygnału; nowa treść dopiero
z `--force`). Paczka jest rozpakowywana do jednego GPKG, a brak którejś
z trzech warstw to `Error:` i brak wersji. **Miejsce na dysku:** rozpakowanie
i kontrola warstw idą w lokalnym katalogu tymczasowym systemu (u autora
`/tmp` to pamięć RAM): powiat 1261 (302 MB w ZIP) rozpakowuje się do
ok. 1,1 GB, więc przy eksporcie województwa (rząd 1,8 GB) zadbaj o miejsce
w katalogu tymczasowym (`TMPDIR`). Ponad 100 MiB pojawia się `Warning:`
z rozmiarem przed pobraniem.

**Aktualność i wersje.** Paczki i obiekty usług GUGiK nie mają taniego
sygnału zmian: kolejne uruchomienie używa lokalnej wersji bez zapytań,
`--check-updates` raportuje `nie da sie sprawdzic bez pobrania`, a nową
treść daje `--force` (ta sama treść = `bez zmian`, inna = nowa wersja obok
starej). Etykieta wersji to rocznik archiwum albo rok modeli 3D, a dla PRG
i EGiB — data pobrania. Sidecar wersji niesie wybór (`request`), źródło
(`extra.source`: URL paczki albo usługa i liczba obiektów każdej
warstwy) i obszar zadania (`extra.parent_request`) — ARCHITECTURE 3.2
i 4.10.

**Limit obszaru (od 0.8.0).** Obszar (`--bbox`, `--sheet`, `--geometry`),
który pobrałby więcej niż **100 plików** albo więcej niż **10 GB**, kończy
się `Error:` (kod 1) jeszcze przed pobraniem: komunikat podaje liczbę
plików, ich rozmiar (suma z `HEAD` albo z feedu ATOM; ponad 100 plików —
szacunek z 5 plików) i co zrobić — zawęzić obszar, wybrać jednostkę
(`--teryt`, `--ku`) albo wykonać plan z częścią pozycji (`--check-updates
--plan PLIK`, edycja pliku, potem `--upgrade --plan PLIK`). Liczą się
tylko pliki do pobrania: wersje już lokalne nie (z `--force` — wszystkie).
Wybór jednostki (`--teryt`, `--ku`) i `--whole-country` nie mają limitu —
rozmiar dużego pliku pojawia się jako `Warning:` przed transferem. Limit
dotyczy wszystkich kolekcji, także ZABAGED, BDOO, Data50 i Data250
w `landcover` oraz NMT 100 m (pliki województw obszaru).

```bash
kartograf models3d download --product trees --country pl --bbox 560000,240000,575000,250000 -o <katalog-danych>
#   Info: trees: powiaty obszaru wg PRG (2): 1206, 1261
#   Error: trees: obszar daje 2 plikow do pobrania, razem ok. 13,7 GB wg HEAD - limit jednego zadania to 100 plikow i 10 GB. Zawez obszar (--bbox, --sheet, --geometry), wybierz jednostke (--teryt <4 cyfry>) albo wykonaj plan z czescia pozycji (--check-updates --plan PLIK, potem --upgrade --plan PLIK)
```

### 1.9 Dane CZ: ZABAGED, Data50, Data250, RUIAN i HY-NET

Dane wektorowe CUZK (od 0.8.0, ADR-042 D15–D17) mają kształt kolekcji
z sekcji 1.8: obszar `--bbox`/`--geometry` daje jeden GeoPackage obiektów
przecinających obszar, z pełnymi geometriami (bez przycinania), zawsze
w układzie usługi **EPSG:5514** (S-JTSK); `--whole-country` zapisuje plik
krajowy CUZK 1:1, a jego rozmiar pojawia się jako `Warning:` przed
transferem. Godło jako obszar i `--teryt` dotyczą tylko PL — obszar CZ
podaj prostokątem albo plikiem geometrii. Współrzędne EPSG:5514 są
w Czechach ujemne: podawaj je jako `--bbox=...` (bez spacji).

```bash
# ZABAGED (landcover): 22 warstwy pokrycia terenu i wód obszaru, EPSG:5514
kartograf landcover download --source zabaged "--bbox=-460000,-1120000,-450000,-1110000" --bbox-crs EPSG:5514 -o ./data
#   -> landcover/cz_zabaged/bbox/-460000_-1120000_-450000_-1110000.gpkg
kartograf landcover list-layers --source zabaged
# plik krajowy ZABAGED (5,8 GB w EPSG:5514 albo 6,7 GB w EPSG:3045) — tylko świadomie
kartograf landcover download --source zabaged --whole-country --horizontal-crs EPSG:5514 -o <katalog-danych>
#   Warning: zabaged CZ: plik krajowy https://openzu.cuzk.gov.cz/opendata/ZABAGED-GPKG/epsg-5514/ZABAGED-5514-gpkg-20261004.zip - 5805826649 B (ok. 5806 MB)
#   -> landcover/cz_zabaged_gpkg_5514/country/cz.zip (wersja 2026-10-04_<sha8>)

# Data50 i Data250 (landcover): wszystkie warstwy obiektowe modelu obszaru
# (69 / 116 warstw), EPSG:5514; bbox w EPSG:4326 -> jego obwiednia EPSG:5514
kartograf landcover download --source data50 --bbox 18.566,49.757,18.572,49.761 --bbox-crs EPSG:4326 -o ./data
#   landcover/cz_data50/bbox/-450998.7179_-1112011.026_-450531.4728_-1111532.273.gpkg: nowa wersja 2026-10-16_7000764f
kartograf landcover list-layers --source data250
# plik krajowy SHP (Data50: 516 MB w EPSG:5514 albo 757 MB w EPSG:3045; Data250: 230/320 MB)
kartograf landcover download --source data250 --whole-country --horizontal-crs EPSG:5514 -o ./data
#   Warning: data250 CZ: plik krajowy https://openzu.cuzk.gov.cz/opendata/Data250/epsg-5514/data250.zip - 230485722 B (ok. 230 MB)
#   landcover/cz_data250_shp_5514/country/cz.zip: nowa wersja 2026-05-12_ae501843
kartograf landcover download --source data250 --whole-country --horizontal-crs EPSG:5514 --check-updates -o ./data
#   landcover/cz_data250_shp_5514/country/cz.zip: aktualne (2026-05-12)

# RUIAN (boundaries --country cz): jednostki poziomu --level przecinające obszar
kartograf boundaries download --product admin --country cz --level obec "--bbox=-470000,-1130000,-440000,-1100000" --bbox-crs EPSG:5514 -o ./data
#   -> boundaries/cz_ruian_obec/bbox/-470000_-1130000_-440000_-1100000.gpkg (warstwa Obec)
# pogranicze: osobne pliki PRG (EPSG:2180) i RUIAN (EPSG:5514), poziom per kraj
kartograf boundaries download --product admin --country auto --level pl=gmina,cz=obec --bbox 18.5,49.6,18.8,49.9 --bbox-crs EPSG:4326 -o ./data
#   -> boundaries/pl_prg_gmina/bbox/<współrzędne EPSG:2180>.gpkg i boundaries/cz_ruian_obec/bbox/<współrzędne EPSG:5514>.gpkg
kartograf boundaries download --product admin --country cz --whole-country -o ./data
#   -> boundaries/cz_ruian_shp/country/cz.zip (SHP, ok. 253 MB)

# HY-NET (hydro): odcinki cieków i węzły obszaru, EPSG:5514
kartograf hydro download --product network --country cz "--bbox=-470000,-1130000,-440000,-1100000" --bbox-crs EPSG:5514 -o ./data
#   -> hydro/cz_hynet/bbox/-470000_-1130000_-440000_-1100000.gpkg (warstwy WatercourseLink, HydroNode)
kartograf hydro download --product network --country cz --whole-country -o ./data
#   -> hydro/cz_hynet_gpkg/country/cz.zip (HY-NET.gpkg w EPSG:3045, ok. 194 MB)
kartograf hydro download --product network --country cz --whole-country --check-updates -o ./data

# Jednostki geomorfologiczne CZ: poziom --level jest wymagany dla obszaru
kartograf boundaries download --product geomorphology --country cz --level celek "--bbox=-452000,-1112000,-450000,-1110000" --bbox-crs EPSG:5514 -o ./data
#   boundaries/cz_geomorphology_celek/bbox/-452000_-1112000_-450000_-1110000.gpkg: nowa wersja 2026-10-16_c7facb92

# Mapa katastralna CZ: paczka katastralniho uzemi (--ku, 6 cyfr) albo KU obszaru
kartograf cadastre download --product map --ku 623164 --format SHP -o ./data
#   cadastre/cz_km_shp/ku/623164.zip: nowa wersja 2026-10-16_aaee5b70
kartograf cadastre download --product map --country cz --format SHP "--bbox=-452000,-1112000,-450000,-1110500" --bbox-crs EPSG:5514 -o ./data
#   Info: map: katastralni uzemi obszaru wg RUIAN (3): 652954, 696137, 753521
#   cadastre/cz_km_shp/ku/652954.zip: nowa wersja 2026-10-16_223d7ce9 (i dwa kolejne KU)
kartograf cadastre download --product map --country cz --format SHP "--bbox=-452000,-1112000,-450000,-1110500" --bbox-crs EPSG:5514 --check-updates -o ./data
#   652954: aktualne (2026-10-16)   (tak samo 696137 i 753521)
kartograf hydro list-sources
```

**ZABAGED.** `--source zabaged` daje 22 warstwy pokrycia terenu
i hydrografii usługi REST `ZABAGED_POLOHOPIS` (lista: `landcover
list-layers --source zabaged`), m.in. `vodni_tok` i `brehova_cara`
(linie), `vodni_plocha`, `orna_puda_a_ostatni_dale_nespecifikovane_plochy`,
`trvaly_travni_porost`, `lesni_puda_se_stromy`,
`budova_jednotliva_nebo_blok_budov_plocha` (poligony). Nazwa warstwy GPKG
to nazwa warstwy usługi bez diakrytyków, małymi literami; opis warstwy
(`gpkg_contents.description`) — nazwa usługi z id, np. `Vodní tok (93)`.
Kartograf **nie przelicza klas ZABAGED na kody BDOT10k** (PT*, SW*):
odpowiedniki ustala konsument (tabela odpowiedników z rekonesansu
2026-08-10 ma błędy). `--whole-country` wymaga `--horizontal-crs
EPSG:5514` albo `EPSG:3045` (plik jest publikowany w dwóch układach)
i zapisuje krajowy ZIP CUZK 1:1 (w środku `ZABAGED_RESULTS.gpkg`;
Kartograf go nie rozpakowuje). Warstwy pliku krajowego to pełna baza pod
nazwami CUZK (np. `VodniPlocha_c`, `TrvalyTravniPorost_c`) — **inne niż
nazwy warstw wyniku obszaru**. Wynik obszaru jest zawsze w EPSG:5514
(`--horizontal-crs` z obszarem = `Error:`); `--teryt`, `--sheet`,
`--format`, `--layers`, `--keep-raw` i `--year` z `--source zabaged` to
`Error:`. Plik krajowy ma wydanie z feedu ATOM (etykieta np.
`2026-10-04`): `--check-updates` porównuje je bez pobierania, `--upgrade`
pobiera nowe wydanie.

**Data50 i Data250.** `--source data50` i `--source data250` to cyfrowe
modele geograficzne CUZK w skali 1:50 000 i 1:250 000. Obszar daje jeden
GeoPackage ze **wszystkimi warstwami obiektowymi** usługi REST
`DATA50`/`DATA250` (69 i 116 warstw; lista: `landcover list-layers
--source data50`; rastry reliefu Data250 nie są danymi obszaru), nazwy
warstw jak w ZABAGED (nazwa CUZK bez diakrytyków, np. `vodni_tok`, `les`,
`louka_pastvina`), bez przeliczania na kody BDOT10k; pusta warstwa zostaje
ze schematem. `--whole-country` z `--horizontal-crs EPSG:5514` albo
`EPSG:3045` zapisuje krajowy ZIP z plikami Shapefile 1:1 (Data50: katalog
`shp/`, Data250: `DATA250_<rok>_SHP/`; nazwy warstw pliku krajowego są
inne niż warstw wyniku obszaru, np. `Akvadukt.shp`, `AirfldA.shp`), z
wydaniem z feedu ATOM (`--check-updates` bez pobierania). Pozostałe zasady
jak dla ZABAGED: wynik obszaru zawsze w EPSG:5514, `--teryt`, `--sheet`,
`--year`, `--layers`, `--format` i `--keep-raw` to `Error:`.

**RUIAN.** `boundaries download --product admin --country cz` wymaga dla
obszaru `--level`: `kraj`, `okres`, `obec` albo `katastralni-uzemi`
(warstwy GPKG `VyssiUzemneSamospravnyCelek`, `Okres`, `Obec`,
`KatastralniUzemi`; m.in. pola `kod` i `nazev`). Pod `--country auto`
obszar przy granicy daje dwa pliki (PRG i RUIAN) ze wspólnym
`extra.parent_request`; poziomy krajów się różnią, więc podaj je per
kraj (`--level pl=gmina,cz=obec`; biblioteka: `{"pl": "gmina", "cz":
"obec"}`) — jedna wartość niedostępna w którymś kraju to `Error:`
z podpowiedzią `--level pl=<poziom>,cz=<poziom>`. `--whole-country
--country cz` to krajowy SHP (ok. 253 MB) z `ETag`: domyślnie jedno
`HEAD` porównuje lokalną wersję, `--check-updates` raportuje `aktualne`
albo `nowsza` bez pobierania.

**HY-NET.** Grupa `hydro` (`--product network`; tylko CZ — `--country pl`
to `Error:`, a `auto` zawęża się do CZ z `Info:`) pobiera sieć
hydrograficzną INSPIRE z WFS CUZK. Wynik obszaru ma **2 warstwy**:
`WatercourseLink` (odcinki cieków) i `HydroNode` (węzły sieci). Typu
`WatercourseSeparatedCrossing` (skrzyżowania cieków) obszar nie
obejmuje: w GML nie ma geometrii (to relacja dwóch odcinków), a usługa
dla zapytania z BBOX podaje 0 obiektów, choć je zwraca (30 x 30 km:
0 wobec 4) — kompletności nie da się sprawdzić; skrzyżowania są w pliku
krajowym. Pola warstw pochodzą z treści odpowiedzi (schemat usługi to
tylko odwołanie do zdalnego schematu INSPIRE), więc ten sam typ może
mieć w innym obszarze inne pola (strona z jednym węzłem nie ma
`hydroNodeCategory`); warstwa bez obiektów ma samo pole `gml_id`. Plik
krajowy (`--whole-country --country cz`, ok. 194 MB) to ZIP z
`HY-NET.gpkg` w **EPSG:3045** (ETRS89 / UTM 33N) — w innym układzie niż
wynik obszaru (EPSG:5514); sidecar podaje faktyczny układ, a innego
układu pliku nie ma (`--horizontal-crs` zbędne). Plik ma `ETag`:
`--check-updates` raportuje `aktualne` albo `nowsza`. Usługa przekierowuje
domyślny `User-Agent` programu `curl` na PDF z warunkami korzystania —
Kartograf wysyła własny (`kartograf/<wersja>`).

**Jednostki geomorfologiczne.** `boundaries download --product
geomorphology --country cz` wymaga dla obszaru `--level`: `subprovincie`,
`oblast`, `celek`, `podcelek`, `okrsek`, `podokrsek` albo `cast` (bez
`--level` `Error:` z listą). Wynik to jeden GeoPackage w EPSG:5514
z jednostkami tego poziomu przecinającymi obszar (pełne geometrie);
pomiar: obszar 2 x 2 km dał 1 obiekt poziomu `celek`, a obszar 20 x 20 km
9 obiektów poziomu `okrsek`.
Produkt nie ma pliku krajowego ani `--teryt`.

**Mapa katastralna CZ.** `cadastre download --product map --country cz`
pobiera paczkę katastrálního území (KU) CUZK w formacie `--format`
(`SHP`, `DXF`, `DGN` albo `VFK`; ZIP zapisany 1:1, format = osobny segment
magazynu `cadastre/cz_km_<format>/ku/`). `--ku` (6 cyfr) wybiera jedno KU
(z `--country pl` to `Error:`); obszar `--bbox`/`--geometry` daje paczkę
każdego KU obszaru wg RUIAN (z `Info:` listą KU). Brak `--format` to
`Error:` z listą formatów. KU bez paczki (np. 999999) kończy się
`Error: ... (HTTP 404)`, a pozostałe KU zadania się zapisują. Paczki mają
sygnał HTTP: kolejne uruchomienie używa lokalnej wersji po jednym `HEAD`,
a `--check-updates` raportuje `aktualne` albo `nowsza` bez pobierania.
Format VKM (wymiana katastralna) nie jest obsługiwany: jego adres
odpowiada 404 dla KU 623164 (stan 2026-10-16).

**Aktualność i rozmiar.** Obiekty obszaru (ZABAGED, RUIAN, HY-NET) nie
mają taniego sygnału zmian: lokalna wersja bez zapytań, `--check-updates`
= `nie da sie sprawdzic bez pobrania`, nowa treść — `--force`. Wynik
obszaru jest składany w pamięci (cała warstwa naraz): obszar 30 x 30 km
to tysiące obiektów na warstwę ZABAGED (rekonesans 2026-10-15: 4979
odcinków cieków), dla całego kraju użyj pliku krajowego. Szczegóły:
ARCHITECTURE 4.8 i 4.10, [ADR-042](DECISIONS.md) errata 2–3.

### 1.10 Nazwy geograficzne i mapy topograficzne

`names download` pobiera `--product geographic`: PRNG RP dla `--country pl`
albo Geonames dla `--country cz`; `--product world --country pl` oznacza
**polskie nazwy geograficzne świata**, nie obcięcie obszaru do Polski.
Obszar (`--bbox`, `--sheet` lub `--geometry`) daje GPKG z pełnymi geometriami
obiektów przecinających obszar: PRNG w OGC:CRS84 (długość, szerokość), Geonames
w EPSG:5514 (25 warstw). Duże zapytania PRNG mogą trwać ponad minutę na stronę;
do kompletu danych użyj `--whole-country`. Wyniki obszaru nie mają taniego
sygnału aktualizacji, do odświeżenia służy `--force`.

```bash
kartograf names download --product geographic --country pl --bbox 19.93,50.055,19.945,50.065 --bbox-crs EPSG:4326 -o <katalog-danych>
kartograf names download --product world --country pl --bbox=-74.02,40.69,-73.92,40.79 --bbox-crs EPSG:4326 -o <katalog-danych>
kartograf names download --product geographic --country cz --bbox=-452000,-1112000,-450000,-1110000 --bbox-crs EPSG:5514 -o <katalog-danych>
kartograf names download --product geographic --country pl --whole-country --format SHP -o <katalog-danych>
kartograf names download --product world --country pl --whole-country --format GML -o <katalog-danych>
kartograf names download --product geographic --country cz --whole-country --format GPKG --horizontal-crs EPSG:5514 -o <katalog-danych>
kartograf names download --product geographic --country cz --whole-country --format GPKG --horizontal-crs EPSG:5514 --check-updates -o <katalog-danych>
```

PRNG RP ma **dwa** pliki krajowe (`miejscowosci`, `obiekty-fizjograficzne`);
polskie nazwy świata mają jeden (`swiat`). Formaty GUGiK: `GML`, `SHP`,
`XLSX` (oryginalne archiwa ZIP). Geonames: `GPKG` albo `FGDB` w
`EPSG:5514`/`EPSG:3045`, wymagany jawny `--horizontal-crs`; plik krajowy to
oryginalne ZIP z feedu ATOM CUZK, data wydania jest etykietą wersji i sygnałem
`--check-updates`. Przed pobraniem plików krajowych pojawia się ostrzeżenie
o ich rozmiarze.

`maps download --product topographic` pobiera arkusze wizualizacji BDOT10k
(`--country pl`, skale `1:10000`, `1:25000`, `1:50000`, `1:100000`, formaty
`TIFF` i `PDF`) albo ZTM CUZK (`--country cz`, skale od `1:5000` do
`1:250000`). Zarówno `--scale`, jak i `--format` są wymagane. Arkusze BDOT10k
są gotowymi plikami TIFF/PDF, nie bazą wektorową BDOT10k; data `Stan bazy` z
indeksu jest etykietą wersji i sygnałem aktualizacji. Dla ZTM `TIFF`, `DGN`
i `SHP` pozostają oryginalnymi ZIP-ami, a `PDF` ma rozszerzenie `.pdf`.
`S-JTSK` dopuszcza `TIFF`, `PDF`, `DGN`, `SHP`, `ETRS89` — tylko `TIFF` i
`PDF`. Układ arkusza `sjtsk`/`etrs89` wynika z godła; `--sheet-system`
jest wymagany przy `--bbox`/`--geometry`. ZTM sprawdza `ETag`/`Last-Modified`
z `HEAD` bez pobierania danych.

```bash
kartograf maps download --product topographic --country pl --sheet M-34-064-D-d-1 --scale 1:10000 --format TIFF -o <katalog-danych>
kartograf maps download --product topographic --country pl --sheet M-34-064 --scale 1:100000 --format PDF -o <katalog-danych>
kartograf maps download --product topographic --country cz --sheet 0510-D-11 --scale 1:10000 --format TIFF -o <katalog-danych>
kartograf maps download --product topographic --country cz --sheet NM-34-07-1-D-15 --scale 1:10000 --format PDF -o <katalog-danych>
kartograf maps download --product topographic --country cz --sheet NM-34-07-1-D-15 --scale 1:10000 --format PDF --check-updates -o <katalog-danych>
kartograf maps list-sources
kartograf names list-sources
```

CLI i API mają tę samą walidację, `Notice`, statusy i układ magazynu
`data/names/` oraz `data/maps/`. Komendy nadają się także do manifestu
(`kartograf project add <nazwa> names download ...` /
`kartograf project add <nazwa> maps download ...`); katalog danych
pochodzi wtedy z projektu.

### 1.11 Mesh 3D, drzewa, osnowy geodezyjne i quasi-geoidy

`models3d download` ma obok budynków (sekcja 1.8) dwa produkty GUGiK
(tylko PL). `--product mesh` to modele siatkowe miast: kafle indeksu GUGiK
przecinające obszar (`--bbox`/`--sheet`/`--geometry`), każdy jako
oryginalny ZIP (OBJ, MTL i tekstury JPG, ok. 40–60 MB). Kafel to plik
jednego rekordu indeksu — ten sam moduł bywa w kilku pracach (np. mesh
ze zdjęć i ze skaningu), więc obie wersje dostajesz jako osobne pliki;
`--year R` zostawia kafle z danych roku R. Plik leży w katalogu układu
rekordu (`s5`–`s7` = PL-2000 strefy 5–7, `pl1992`): OBJ ma współrzędne tej
strefy (E z prefiksem strefy) i wysokości PL-EVRF2007-NH (sidecar
`horizontal_crs`, `vertical_crs` EPSG:9651). Etykieta wersji to data
i numer zgłoszenia pracy z rekordu, więc `--check-updates` porównuje kafel
z indeksem bez pobierania. Obszar dużego miasta to setki kafli — powyżej
100 kafli zadanie kończy się `Error:` z liczbą i szacowanym rozmiarem
(limit obszaru, sekcja 1.8). `--product trees` to modele drzew CityGML
LoD1 (wydanie 2023, pliki GML arkuszy 1:500 w EPSG:2180 bez układu
wysokości): paczka powiatu (`--teryt`) albo paczki powiatów obszaru,
0,3–25 GB każda; `--lod 1` i `--year 2023` można pominąć (inna wartość to
`Error:`), nie każdy powiat ma paczkę (`Error: <TERYT>: ... (HTTP 404)`).

```bash
kartograf models3d download --product mesh --country pl --bbox 566200,244650,566250,244700 -o <katalog-danych>
#   Info: mesh: kafle obszaru (1): s7/78944_6777_74230_55482
#   models3d/pl_mesh/s7/78944_6777_74230_55482.zip: nowa wersja 2021-10-03_DFT.7201.043.2023_7950f585
kartograf models3d download --product mesh --country pl --bbox 566200,244650,566250,244700 --check-updates -o <katalog-danych>
#   s7/78944_6777_74230_55482: aktualne (2021-10-03_DFT.7201.043.2023)
kartograf models3d download --product trees --teryt 3063 -o <katalog-danych>
#   Warning: trees PL 3063: duzy plik https://opendata.geoportal.gov.pl/InneDane/Drzewa3D/LOD1/2023/30/3063.zip - 324674789 B (ok. 325 MB)
#   models3d/pl_trees_lod1_2023/teryt/3063.zip: nowa wersja 2023_25a77518
```

`geodesy download --product control` pobiera punkty osnów geodezyjnych.
`--network` jest wymagane: PL `horizontal`, `vertical`, `gravity`,
`magnetic` (osnowa pozioma, wysokościowa, grawimetryczna i magnetyczna
GUGiK; magnetyczna także strefy izogon), `archive-1942`,
`archive-kronsztadt60` (archiwalne katalogi punktów); CZ `gnss` (stacje
CZEPOS), `horizontal`, `densification` (ZhB), `horizontal-detailed`,
`vertical`, `vertical-detailed`, `gravity` (Bodove pole CUZK). Obszar daje
jeden GeoPackage punktów sieci (PL: warstwy `fundamentalna_*`
i `bazowa_*` w EPSG:2180; CZ: warstwy sieci, np. `bod_zvbp`, w EPSG:5514 —
sieć CZ to suma jej warstw, także punktów wyznaczonych w ETRS89).
`--teryt` (powiat) daje paczkę sieci `horizontal` albo `vertical`: wykazy
współrzędnych (XLS) i opisy topograficzne (JPG). Archiwa to skany (PDF,
TIFF) arkuszy 1:100 000: `--sheet` dowolnej skali albo obszar wybiera
arkusze 1:100 000 jego zasięgu (archiwum 1942 bywa ponad 1 GB — rozmiar
w `Warning:` przed transferem). Sieć bez paczek powiatu z `--teryt` to
`Error:` ze wskazaniem obszaru. Pod `--country auto` jedna wartość
`--network` dotyczy obu krajów (wspólne: `horizontal`, `vertical`,
`gravity`); błąd podaje wartości każdego kraju.

`geodesy download --product geoid` to model quasi-geoidy jako jeden plik
krajowy, tylko z `--whole-country`: `--country pl` — PL-geoid2021 dla
PL-EVRF2007-NH (TXT: szerokość, długość, zeta w ETRF2000-PL, siatka
0,01°, 42 MB), `--country cz` — QGZU-2013 (ZIP 17 siatek TXT dla wysokości
Bpv, 58 MB; data wydania z feedu ATOM jest etykietą i sygnałem
`--check-updates`). Obszar to `Error:`. Kartograf pobiera modele jako dane
i nie stosuje ich do innych danych.

```bash
kartograf geodesy download --product control --country pl --network vertical --bbox 560000,240000,575000,250000 -o <katalog-danych>
#   geodesy/pl_control_vertical/bbox/560000_240000_575000_250000.gpkg: nowa wersja 2026-10-16_1272d195
kartograf geodesy download --product control --network horizontal --teryt 1201 -o <katalog-danych>
#   geodesy/pl_control_horizontal_package/teryt/1201.zip: nowa wersja 2026-10-16_fa3dc40c
kartograf geodesy download --product control --network gravity --teryt 1201 -o <katalog-danych>
#   Error: --network gravity: control (PL) - dostepne tylko dla --bbox/--sheet/--geometry (obiekty obszaru); dla --teryt: horizontal, vertical
kartograf geodesy download --product control --network archive-kronsztadt60 --sheet M-34-064-D -o <katalog-danych>
#   Info: control: arkusze (1): M-34-64
#   geodesy/pl_control_archive-kronsztadt60/M-34/64/M-34-64.zip: nowa wersja 2026-10-16_8211a8dc
kartograf geodesy download --product control --country cz --network vertical "--bbox=-452000,-1113000,-449000,-1110000" --bbox-crs EPSG:5514 -o <katalog-danych>
#   geodesy/cz_control_vertical/bbox/-452000_-1113000_-449000_-1110000.gpkg: nowa wersja 2026-10-16_b921641a
kartograf geodesy download --product control --country auto --network vertical --bbox 18.55,49.70,18.70,49.78 --bbox-crs EPSG:4326 -o <katalog-danych>
#   -> geodesy/cz_control_vertical/bbox/<EPSG:5514>.gpkg i geodesy/pl_control_vertical/bbox/<EPSG:2180>.gpkg
kartograf geodesy download --product geoid --country pl --whole-country -o <katalog-danych>
#   Warning: geoid PL: plik krajowy https://opendata.geoportal.gov.pl/InneDane/ModeleQuasiGeoidy/PL-geoid2021/Model_quasi-geoidy-geoid2021-PL-EVRF2007-NH.txt - 42328086 B (ok. 42 MB)
#   geodesy/pl_geoid2021_evrf2007/country/pl.txt: nowa wersja 2026-10-16_d695cf81
kartograf geodesy download --product geoid --country cz --whole-country -o <katalog-danych>
#   geodesy/cz_qgzu2013/country/cz.zip: nowa wersja 2021-02-22_aacfba6b
kartograf geodesy list-sources
```

Punkty osnów, paczki, archiwa i PL-geoid2021 nie mają taniego sygnału
świeżości (`--check-updates`: `nie da sie sprawdzic bez pobrania`; nowa
treść z `--force`). Komendy `models3d download` i `geodesy download`
nadają się do manifestu (`kartograf project add <nazwa> geodesy download
--product control --network horizontal --teryt 1201`).

---

## 2. Biblioteka Python

Każda komenda CLI ma jedną funkcję biblioteki z tymi samymi wyborami
(nazwy parametrów = nazwy flag w `snake_case`) i tym samym wynikiem
(ADR-037): `kartograf elevation download` i `kartograf imagery download` =
`download_data`/`check_data`, `landcover download` i `soil download` =
`LandCoverManager.download`/`.check`, `soil hsg` = `HSGCalculator.calculate_hsg`/`.check_hsg`,
`elevation availability` = `check_availability`,
`boundaries download`, `cadastre download`, `models3d download`, `hydro
download`, `names download` i `maps download` =
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

Kolekcje (`boundaries`, `cadastre`, `models3d`, `hydro`, `names`, `maps`,
`geodesy`; sekcje 1.8–1.11) — wynik `CollectionReport(files, failed, stale,
notices, ok)`, elementy `files` i `failed` jak w `DataReport`:

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
# = landcover download --source bdoo --teryt 12 --year 2023 --layers PTWP,SWRS
bdoo = LandCoverManager(out, "bdoo").download(
    teryt="12", year=2023, layers=["PTWP", "SWRS"], on_notice=show
)  # data/landcover/pl_bdoo_2023_ptwp-swrs/teryt/12.zip; Notice classes_absent,
#    gdy paczka nie ma pliku którejś klasy
# = names download --product world --country pl --bbox=-74.02,40.69,-73.92,40.79
world = download_collection(
    product="world", country="pl", output_dir=out,
    bbox=BBox(-74.02, 40.69, -73.92, 40.79, "EPSG:4326"),
)
# = maps download --product topographic --country cz --sheet 0510-D-11
map_sheet = download_collection(
    product="topographic", country="cz", output_dir=out,
    sheet="0510-D-11", scale="1:10000", format="TIFF",
)
map_status = check_collection(
    product="topographic", country="cz", output_dir=out,
    sheet="0510-D-11", scale="1:10000", format="TIFF",
)
# = models3d download --product mesh --country pl --bbox 566200,244650,566250,244700
mesh = download_collection(
    product="mesh", country="pl", output_dir=out,
    bbox=BBox(566200, 244650, 566250, 244700, "EPSG:2180"),
)  # data/models3d/pl_mesh/s7/78944_6777_74230_55482.zip; year= filtruje kafle
# = geodesy download --product control --network horizontal --teryt 1201
download_collection(product="control", output_dir=out, teryt="1201",
                    network="horizontal")
# = geodesy download --product control --country cz --network vertical --bbox=...
download_collection(product="control", output_dir=out, country="cz", network="vertical",
                    bbox=BBox(-452000, -1113000, -449000, -1110000, "EPSG:5514"))
# = geodesy download --product geoid --country cz --whole-country
download_collection(product="geoid", output_dir=out, country="cz",
                    whole_country=True, on_notice=show)  # QGZU, wydanie z feedu ATOM
# obszar ponad 100 plikow albo 10 GB: ValidationError przed pobraniem
# (liczba plikow, rozmiar i podpowiedz; sekcja 1.8)
```

Walidacja bez sieci (np. przed zapisaniem zadania):
`kartograf.download.collections.validate_collection_request(...)` z tymi
samymi wyborami (bez `update`, `plan`, `workers`, `cache`, `on_notice`).

Ortofoto CZ, wycinek ortofotomapy PL i dane CZ (sekcje 1.3, 1.4 i 1.9):

```python
from kartograf import (
    BBox, LandCoverManager, check_cz_orto_sheet, download_collection,
    download_cz_orto_sheet, download_data, download_orto_cutout,
)

out = "./data"
show = lambda notice: print(notice.level, notice.text)
# = imagery download --product orto --country cz --sheet CTES96
report = download_data(product="orto", country="cz", sheet="CTES96", output_dir=out)
for item in report.files:  # cztery pliki arkusza: .jgw, .TM33N.jgw, .TM34N.jgw, .jpg
    print(item.unit, item.file.path.name, item.file.label)  # CTES96 CTES96.jpg 2024_2025-02-06
# = imagery download --product orto --country cz --bbox=-448500,-1113500,-446500,-1112500 --bbox-crs EPSG:5514
download_data(product="orto", country="cz", output_dir=out,
              bbox=BBox(-448500, -1113500, -446500, -1112500, "EPSG:5514"))
# tor arkusza (CzOrtoResult: files, stale, notices) i plan bez pobierania zdjęć
sheet = download_cz_orto_sheet("AS91", output_dir=out)
plan = check_cz_orto_sheet("AS91", output_dir=out)  # tor "cz_orto", cztery pozycje
# = imagery download --product orto --country pl --bbox 566000,243000,566500,243500
#   --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m
cut = download_data(product="orto", country="pl", output_dir=out,
                    bbox=BBox(566000, 243000, 566500, 243500, "EPSG:2180"),
                    cutout=True, horizontal_crs="EPSG:2180",
                    coverage="standard", resolution="0.25m", on_notice=show)
# tor wycinka (OrtoCutoutResult: file, stale, notices); plan: check_orto_cutout
high = download_orto_cutout(BBox(566000, 243000, 566200, 243200, "EPSG:2180"),
                            horizontal_crs="EPSG:2180", output_dir=out,
                            coverage="high", resolution="0.1m")
print(high.file.path)  # data/orto/pl_1992_high_0.1m/bbox/566000_243000_566200_243200.tif

# = landcover download --source zabaged --bbox=-460000,-1120000,-450000,-1110000 --bbox-crs EPSG:5514
zabaged = LandCoverManager(out, "zabaged")
area = zabaged.download(bbox=BBox(-460000, -1120000, -450000, -1110000, "EPSG:5514"))
print(area.files[0].file.path)  # data/landcover/cz_zabaged/bbox/-460000_-1120000_-450000_-1110000.gpkg
print(zabaged.get_available_layers())  # 22 nazwy warstw obszaru
# plik krajowy (5,8 GB): Notice whole_country_size przed transferem
zabaged.download(whole_country=True, horizontal_crs="EPSG:5514", on_notice=show)
# = landcover download --source data50 --bbox 18.566,49.757,18.572,49.761 --bbox-crs EPSG:4326
data50 = LandCoverManager(out, "data50")
data50.download(bbox=BBox(18.566, 49.757, 18.572, 49.761, "EPSG:4326"))  # 69 warstw, EPSG:5514
data50.download(whole_country=True, horizontal_crs="EPSG:5514", on_notice=show)  # SHP, 516 MB
# = boundaries download --product admin --country auto --level pl=gmina,cz=obec --bbox ...
download_collection(product="admin", output_dir=out, country="auto",
                    level={"pl": "gmina", "cz": "obec"},
                    bbox=BBox(18.5, 49.6, 18.8, 49.9, "EPSG:4326"), on_notice=show)
# = hydro download --product network --country cz --bbox=... / --whole-country
download_collection(product="network", output_dir=out, country="cz",
                    bbox=BBox(-470000, -1130000, -440000, -1100000, "EPSG:5514"))
download_collection(product="network", output_dir=out, country="cz",
                    whole_country=True, on_notice=show)  # HY-NET.gpkg w EPSG:3045
```

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

# Surowy WCS poza magazynem (np. NMT KRON86 jako TIFF albo ortofotomapa;
# NMT/NMPT tylko wariant 1 m — provider.is_wcs_available()):
# provider.download_bbox(bbox, path) — NMT/NMPT: jednopasmowy float32 GeoTIFF
# na siatce 1 m EPSG:2180, ortofotomapa: RGB z jednego zapytania Standard;
# bez maski PRG i bez wersji. Wycinek NMT/NMPT w magazynie wersji:
# download_pl_cutout (niżej), ortofotomapy: download_orto_cutout (wyżej).
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
    product="nmt",
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

# Arkusz CZ: SM5 (gotowy plik DMR 4G 5m albo DMP OK 0.5m - resolution można
# pominąć) albo kafel TM33 (resolution wymagane: NMT "2m"/"5m", NMPT "0.5m"/"2m");
# product wymagany: "nmt" albo "nmpt"
from kartograf import check_cz_sheet, download_cz_sheet

sm5 = download_cz_sheet("CTES96", output_dir="./data", product="nmt", vertical_crs="Bpv")
tm33 = download_cz_sheet(
    "302_5550", output_dir="./data", product="nmt", vertical_crs="EVRF2007", resolution="2m"
)
# DMP OK, kafel TM33 w EVRF2007: gotowy plik ETRS89 (EPSG:3045) bez transformacji
dmp = download_cz_sheet(
    "760_5518", output_dir="./data", product="nmpt", vertical_crs="EVRF2007", resolution="0.5m"
)

# Sprawdzenie bez pobierania (plan kartograf-plan/1): blizniak check_* z tymi
# samymi argumentami co pobranie; plan wykonuje pobranie z update="upgrade"
plan = check_cz_sheet("CTES96", output_dir="./data", product="nmt", vertical_crs="Bpv")
print([(i.track, i.unit, i.status) for i in plan.items])
sm5 = download_cz_sheet(
    "CTES96", output_dir="./data", product="nmt", vertical_crs="Bpv",
    update="upgrade", plan=plan,
)

# LAZ CZ: model i układ wysokości (Bpv = arkusze SM5, EVRF2007 = kafle TM33);
# godło (sheet=) albo obszar (bbox= w dowolnym obsługiwanym CRS)
from kartograf import check_cz_laz, download_cz_laz

selection_cz = dict(model="dmr5g", vertical_crs="Bpv", output_dir="./data",
                    bbox=BBox(-447000, -1114000, -444000, -1113000, "EPSG:5514"))
clouds = download_cz_laz(**selection_cz)
for file in clouds.files:                  # VersionedFile na arkusz (.laz 1:1 z ZIP)
    print(file.path, file.status)
for failure in clouds.failed:              # porażka pliku nie przerywa pozostałych
    print(failure.sheet, failure.error)
plan = check_cz_laz(**selection_cz)        # pozycje toru cz_laz, jedno HEAD na plik
clouds = download_cz_laz(**selection_cz, update="upgrade", plan=plan)
```

**Cache metadanych w bibliotece.** Funkcje poziomu komendy i torów
(`download_data`, `check_data`, `download_pl_cutout`, `download_cz_*`,
`download_laz_area`, `LandCoverManager`, `HSGCalculator`) przyjmują
`cache: MetadataCache | bool = True`: domyślnie ten sam plik co CLI
(`<cwd>/.kartograf_cache.db`, TTL 7 dni), `False` = bez cache, własny
`MetadataCache` = ten. `update="force"` pomija odczyty z cache w tym
wywołaniu (jak `--force`), a funkcje sprawdzenia (`check_data`,
`check_*`, `LandCoverManager.check`) pomijają je zawsze (jak
`--check-updates`). Katalog tylko do odczytu: cache wyłączony
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

**`update="force"` a cache providera.** `force` pomija odczyty tylko
z cache, który otwiera sama funkcja (parametr `cache` funkcji poziomu
komendy; `LandCoverManager` z providerem po nazwie): rekord jest pobrany
na nowo i zapisany. Provider przekazany jako gotowa instancja
(`DownloadManager("./data", provider)`, `LandCoverManager("./data",
Bdot10kProvider(cache=...))`, `download_laz_area(..., provider=...)`)
zachowuje SWÓJ cache: `update="force"` pobiera pliki ponownie, ale rekordy
skorowidza albo odpowiedzi PRG może wziąć z tego cache (do końca TTL).
Pełne odświeżenie: utwórz provider z `MetadataCache(".kartograf_cache.db",
refresh=True)` albo wywołaj `download_data(..., update="force")`, które
tworzy provider samo.

Pozostałe elementy publicznego API (m.in. `GugikNmptProvider` —
od 0.8.0 z wymaganym `resolution=`, np. `GugikNmptProvider(vertical_crs="EVRF2007",
resolution="0.5m")`, `GugikOrtoProvider`, `GugikLazProvider`/`download_laz_area`
dla LAZ PL, `CuzkRasterProvider`/`create_cz_raster_provider` dla rastrów CZ,
`CuzkLazProvider`/`download_cz_laz` dla LAZ CZ, `Parser2000`,
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
- `CzLazResult` (`download_cz_laz`): `sheets`, `files` (wersja na
  arkusz), `failed` (`CzLazFailure(sheet, error)`), `stale`, `notices`, `ok`.
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
(PL i CZ) i arkusze CZ w bibliotece), a `FileStorage.delete()` usuwa sidecar razem z plikiem danych.
Bezpośrednie wywołanie providera (np. `CuzkRasterProvider` z biblioteki) zapisuje
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
kafli LAZ (PL i CZ), arkuszy CZ (TM33, SM5; ortofoto CZ), wycinków CZ i wycinków PL
`--cutout` (także ortofotomapy), a także `landcover download`, `soil download`, `soil hsg`
oraz `boundaries download`, `cadastre download`, `models3d download`,
`hydro download`, `names download` i `maps download`. Flagi
wykluczają się wzajemnie. Tabela niżej opisuje arkusze PL (sygnał:
skorowidz); pozostałe tory różnią się sygnałem:

| Tor | Sygnał świeżości | Uwagi |
|---|---|---|
| arkusze PL | skorowidz GUGiK (`index`) | tabela niżej |
| kafle LAZ PL | rekord WFS (`index`) | nowszy nalot to nowe pliki — pobierane domyślnie; kafel z lokalną wersją tylko `--force` (D26) |
| CZ: arkusze SM5, kafle TM33 DMR 4G/DMP OK w EVRF2007, pliki LAZ (tor planu `cz_laz`) | `ETag`/`Last-Modified` (`http`) | jedno `HEAD` na plik; inny `ETag` = `nowsza`, `--upgrade` pobiera |
| pozostałe kafle TM33 (warp z ImageServer), wycinki CZ i PL (także ortofotomapy) | brak (`none`) | domyślnie `lokalna wersja ... (bez sprawdzania; --check-updates)`; `--check-updates` = `nie da sie sprawdzic bez pobrania`; `--upgrade` = lokalna + `Info:` o `--force` |
| ortofoto CZ (arkusz SM5; tor planu `cz_orto`) | wydanie z feedu ATOM CUZK (`metadata`) | etykieta = `<rok>_<wydanie>` (`2024_2025-02-06`); jedno sprawdzenie wydania na arkusz (cztery pliki); nowszy rocznik = `dostepna nowsza ... (--upgrade)`, `--upgrade` pobiera |
| SoilGrids, CORINE CLMS | wydanie źródła (`metadata`: GetCapabilities / katalog CLMS) | etykieta wersji = wydanie (`2.0`, `V2020_20u1`); nowsze wydanie = `dostepna nowsza ... (--upgrade)`; wydanie niedostępne: bez lokalnej wersji `Error:`, z lokalną `Warning:` (z `--upgrade` `Error:`) |
| BDOT10k, podgląd CORINE | brak (`none`) | jak wycinki; `--force` przy BDOT10k odświeża też cache PRG |
| kolekcje (`boundaries`, `cadastre`, `models3d`, `hydro`; tor planu `collection`), ZABAGED obszaru i archiwum BDOT10k (`--year`) | brak (`none`) | jak wycinki; etykieta = rocznik/rok wydania albo data pobrania (sekcje 1.8, 1.9) |
| pliki krajowe RUIAN i HY-NET | `ETag`/`Last-Modified` (`http`) | jak arkusze SM5 |
| plik krajowy ZABAGED | wydanie z feedu ATOM (`metadata`) | etykieta = data wydania (`2026-10-04`); jak ortofoto CZ |
| obszary PRNG/Geonames, kraj PRNG | brak (`none`) | `--force` do sprawdzenia nowej treści; PRNG RP ma dwie paczki krajowe |
| kraj Geonames | wydanie feedu ATOM (`metadata`) | `--check-updates` porównuje datę wydania bez pobierania ZIP |
| mapy BDOT10k | data `Stan bazy` skorowidza (`index`) | data osobna dla skali, bez pobierania TIFF/PDF |
| ZTM CZ | `ETag`/`Last-Modified` (`http`) | jedno `HEAD` na arkusz |
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

`--check-updates` zawsze pyta źródło: odczyt cache metadanych (rekordy
skorowidza, odpowiedzi PRG, indeksy; TTL 7 dni) jest pomijany, a wpisy
są odświeżane — nowy lot opublikowany po ostatnim zapytaniu jest widoczny
od razu, a bez sieci sprawdzenie kończy się `Error:`. Domyślne pobieranie
korzysta z cache jak dotąd.

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
(także dla kafli LAZ PL i CZ). Arkusz CZ, plik LAZ CZ i wycinek dają jedną linię statusu
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
# LAZ CZ: download_cz_laz(..., update=, plan=) + check_cz_laz (ten sam wybór);
# wycinki i arkusze CZ: download_pl_cutout / download_orto_cutout /
# download_cz_cutout / download_cz_sheet / download_cz_orto_sheet(..., update=,
# plan=) + check_pl_cutout / check_orto_cutout / check_cz_cutout /
# check_cz_sheet / check_cz_orto_sheet (te same argumenty); land cover:
# LandCoverManager.download(..., update=, plan=) + check (te same argumenty);
# HSG: calculate_hsg(..., update=, plan=) + check_hsg; kolekcje:
# download_collection(..., update=, plan=) + check_collection; pozycje
# planu: item.track, item.unit
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
- Wycinek PL `--cutout` NMT/NMPT jest tylko 1 m: NMT/NMPT w innych
  rozdzielczościach (np. 0.5m, 5m) i archiwa pobieraj jako arkusze bez
  tej flagi (sekcja 1.3); wycinek CZ ma krok modelu (0,5 m, 2 m albo 5 m,
  sekcja 1.4). Wycinek ortofotomapy ma piksel do wyboru
  (`0.1m`–`1m`), ale tylko w EPSG:2180 i tylko dla PL.
- WCS ortofotomapy jest wolny (pomiar 2026-10-15: ok. 1 min na kawałek
  200 x 200 m; obszar 1 x 1 km = 25 kawałków niezależnie od piksela),
  a Standard bywa przejściowo niedostępny. Złożony z kawałków wycinek nie
  jest bit w bit równy jednemu zapytaniu (różnice rzędu kilku DN na
  stykach przepróbkowania serwera); `high` poza obszarami lotów 10 cm daje
  plik czarny (`Warning:`, sekcja 1.3).
- Ortofoto CZ: tylko aktualny rocznik arkusza (archiwalne zdjęcia CUZK
  są płatne); pliki JGW nie niosą układu — w GIS przypisz EPSG:5514 do
  `<godło>.jpg` z `<godło>.jgw` (sekcja 1.4).
- Ortofotomapa ukośna (`--product oblique-orto`) kampanii Kraków 2021
  (np. arkusz `7.125.11.08`, kampania 78945): GeoTIFF ma własny opis układu
  („Transverse Mercator, WGS84”) z parametrami PL-2000 strefy 7, bez kodu
  EPSG. GDAL i rasterio nie podają kodu (`to_epsg()` = `None`), a przy
  obniżonym progu pewności błędnie dopasowują EPSG:32634 (UTM 34N — obraz
  wylądowałby ok. 6900 km dalej). Układ pliku to EPSG:2178 (PL-2000
  strefa 7), jak `horizontal_crs` w sidecarze. W QGIS ustaw układ warstwy
  na EPSG:2178; narzędziu wymagającemu kodu podaj go bez zmiany pliku:
  `gdal_translate -of VRT -a_srs EPSG:2178 plik.tif plik.vrt`. Nie używaj
  `gdal_edit.py` na pliku w magazynie — zmiana bajtów łamie sumę SHA-256
  wersji i przypięcia projektu. Kampanie z kodem EPSG w pliku (np. Gdańsk
  2024, EPSG:2177) tego nie wymagają.
- ZABAGED: klasy nie są przeliczane na kody BDOT10k, a warstwy pliku
  krajowego mają inne nazwy niż wynik obszaru; HY-NET: wynik obszaru bez
  skrzyżowań cieków (tylko w pliku krajowym, EPSG:3045), pola warstw
  zależą od treści obszaru (sekcja 1.9).
- Archiwa GUGiK (`--format XYZ|ASCII-NMT|TBD|TIN|TTN|GRD|DXF|DGN`) są
  pobierane jako pliki źródłowe bez konwersji (ZIP, `.ttn`, `.grd`,
  `.dxf`, `.dgn`): Kartograf nie rozpakowuje ich, nie przelicza na
  siatkę, nie wycina i nie mierzy pokrycia — plik otwierasz programem,
  który obsługuje dany format (sekcja 1.1).
- Raport `elevation availability` ufa deklaracji skorowidza
  `calyArkuszWypelnionyTrescia`: arkusz NIE może mieć od 1 % do 99 %
  danych, a raport nie mierzy treści plików (sekcja 1.7). W CZ sprawdza
  tylko istnienie plików (`HEAD`), nie zna lat nalotu, a `area_m2` części
  CZ to prostokąt, nie ląd.
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
- Wycinki (PL, CZ) i kafle TM33 z ImageServer nie mają taniego sygnału
  świeżości: zmiana treści u źródła albo maski PRG jest niewidoczna bez
  `--force` (pliki openzu — arkusz SM5, kafel TM33 DMR 4G/DMP OK
  w EVRF2007, LAZ CZ — mają sygnał HTTP, sekcja 4.3).
- Granice PRG, EGiB, modele 3D budynków i drzew, archiwum BDOT10k, osnowy
  i obiekty obszaru CZ (ZABAGED, RUIAN, HY-NET, Bodove pole; sekcje 1.8,
  1.9 i 1.11) nie mają taniego sygnału świeżości: nowszą treść przynosi
  tylko `--force` (kafle mesh 3D porównują etykietę rekordu indeksu).
- Modele drzew 3D: paczka powiatu ma do 25 GB, a serwer GUGiK odpowiada
  na `HEAD` rozmiaru po kilku–kilkudziesięciu sekundach (ok. 3,5 s na
  GB), więc obszar kilku powiatów to około minuty pomiaru i prawie zawsze
  `Error:` limitu 10 GB — pobieraj powiat (`--teryt`). Mesh 3D obszaru
  miasta to setki kafli: powyżej 100 zawęź obszar (sekcje 1.8 i 1.11).
- Strony WFS GUGiK (obiekty obszaru PRG i EGiB) przychodzą po kilka
  sekund na stronę 1000 obiektów (na żywo 2026-10-15: 2–4 s; limit jednego
  zapytania 60 s), więc duży obszar EGiB to minuty. Wynik obszaru jest
  składany w pamięci (cała warstwa naraz) — dla całego powiatu wygodniej
  pobrać eksport (`cadastre download --teryt`), a granice województwa —
  paczkę (`boundaries download --teryt <2 cyfry>`); dla całych Czech —
  plik krajowy (`--whole-country`).
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
`imagery download` (takze ortofoto CZ i wycinek `--cutout`), `landcover
download` (takze ZABAGED), `soil download`, `soil hsg`,
`boundaries download`, `cadastre download`, `models3d download`,
`hydro download`, `names download` i `maps download`; arkusz ortofoto CZ
przypina cztery pliki (JPEG i trzy JGW);
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
