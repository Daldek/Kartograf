# Ocena parserow: mozliwosci uproszczenia (analiza, bez zmian kodu)

Data: 2026-10-07. Galaz: `develop` @ `0f5e4f4`. Recenzent-architekt; zero
zmian w kodzie i testach, zero sieci. Baseline: pliki testow parserow
(`test_sheet_parser`, `test_parser_2000`, `test_parser_tm33`,
`test_parser_registry`, `test_cuzk_sheets`, `test_geometry`, `test_skorowidz`,
`test_pl2000_verification`, `test_sources_registry`, `test_sidecar`) =
**757 passed** w 2,7 s.

Dowody to siedem skryptow offline w `/tmp/claude-2001/parsers-eval/`
(`exp1_godla.py` … `exp7_confirm.py`, uruchamiane `.venv/bin/python -I`);
wyniki sa wklejone przy znaleziskach. Kontekst: review-1 D3/D4/D5/D12/O3/O8.

Zasada oceny: "kopia" liczy sie, gdy ta sama decyzja (wzorzec, format,
algorytm obwiedni) zyje w dwoch miejscach i moze sie rozjechac. Dwie
implementacje z roznych domen, ktore wspolna abstrakcja by pogorszyla, nie
sa duplikacja i dostaja NIE ROBIC.

## 0. Podsumowanie rekomendacji

| # | Obszar | Implementacje | Rozjazd udowodniony? | Rekomendacja |
|---|---|---|---|---|
| 1 | Obwiednie bboxa miedzy CRS (D5) | **10** (4 narozniki x6, 6 pkt x1, probki krawedzi x1, `transform_bounds` x2) | **TAK — to blad, nie kosmetyka**: `find_sheets_for_bbox(system="2000")` z bboxa WGS84 gubi cale wiersze arkuszy (82/3200 przypadkow), wycinek PL z bboxa WGS84 traci do 479 m na poludniu; `get_bbox` buduje transformer przy kazdym wywolaniu (1454 ms vs 4 ms / 200 wywolan) | **ROBIC teraz** (kroki K1-K4 bez konfliktow; K6 po zwolnieniu `download/*`, `cli/download_cmd.py`) |
| 2 | Rejestr systemow godel (O3) + martwy `Sm5Sheet` + wzorce CZ (D12) | `parser_factory`: 0 wywolan w produkcji; `Sm5Sheet`: produkuje go tylko `parser_factory`; wzorzec SM5 x2, TM33 x2 | TAK, ale bez skutku w CLI: `strip()` w 2 z 5 miejsc (exp1) | **ROBIC teraz** (K5; BREAKING: `Sm5Sheet` znika z `kartograf.providers.cuzk`) |
| 3 | Parsowanie `--bbox "x,y,x,y"` (D4) | 5 kopii (3 identyczne co do znaku) | TAK: podpowiedz na stdout w 3 z 5, brak w CZ, `ValueError` w LAZ; **zadna** kopia nie sprawdza `min<max` ani skonczonosci: `--bbox 10,10,5,5` daje 1 arkusz-smiec, `--bbox nan,1,2,3` konczy sie `Error: ValueError: cannot convert float NaN to integer`; galaz CZ `bbox is None` nieosiagalna z CLI | **ROBIC** (K7: landcover/soilgrids + helper bez konfliktu teraz; `download_cmd.py` po innych agentach) |
| 4 | Klasy parserow godel (`SheetParser`/`Parser2000`/`ParserTM33`) | 3 klasy, delegacja wg ADR-017 | NIE (rozne domeny) | **NIE ROBIC** (scalanie klas); jedynie `strip()` z pkt 2 |
| 5 | Auto-detekcja kraju/systemu z godla w CLI | 1 sciezka (`detect_system`) wolana w 5 miejscach | NIE | **NIE ROBIC** |
| 6 | `parse_skorowidz_records`, `parse_pl_uklad` (D3) | po 1 + 1-liniowy adapter `_horizontal_crs` | NIE (D3 ujednolicone 2026-10-06) | **NIE ROBIC** (adapter mozna wchlonac przy okazji) |
| 7 | WFS LAZ (GML), `read_asc_nodata`, SHP/GPKG | po 1 implementacji; nodata TIFF czytane w 2 miejscach (`_read_tif_nodata`, `dmr.py:463`) | NIE | **NIE ROBIC** (nodata: opcjonalny K8 po zwolnieniu `sidecar.py`/`download_cmd.py`) |
| 8 | Fasada `cli/commands.py` re-eksportujaca prywatne helpery (O8) | — | — | **ROBIC z zastrzezeniem** (K9, 5 min, po K7) |

Plan krokow z plikami, testami i kolejnoscia: sekcja "Plan dla implementera"
na koncu.

---

## 1. Obwiednie bboxa miedzy ukladami (review-1 D5) — ROBIC teraz

### 1.1 Inwentarz (10 implementacji)

| # | Miejsce | Kierunek | Metoda | Transformer |
|---|---|---|---|---|
| 1 | `core/sheet_parser.py:660` `SheetParser.get_bbox("EPSG:2180")` | 4326 -> 2180 | 4 narozniki | **nowy przy kazdym wywolaniu** |
| 2 | `core/sheet_parser.py:931` `_transform_bbox_to_wgs84` | 2180 -> 4326 | 4 narozniki + 2 pkt na poludniku 19E (poprawka 2026-09-28) | nowy |
| 3 | `core/parser_2000.py:575` `Parser2000._transform_bbox` | dowolny -> dowolny | 4 narozniki | nowy |
| 4 | `core/parser_2000.py:690` `_transform_bbox_to_wgs84` | dowolny -> 4326 | 4 narozniki | nowy |
| 5 | `core/parser_2000.py:728` `_transform_bbox_to_zone_crs` | 4326 -> strefa | 4 narozniki | nowy |
| 6 | `core/geometry.py:417` `_transform_bbox` | dowolny -> dowolny | 4 narozniki | nowy (takze **per obiekt** w `_read_shp_bboxes:234` / `_read_gpkg_bboxes:402`) |
| 7 | `download/cutout.py:617` `_sheet_frame_2180` | 4326 -> 2180 | kopia (1) | `functools.cache` (N9) |
| 8 | `providers/cuzk/dmr.py:489` `bbox_to_crs` | dowolny -> dowolny | 9 probek na krawedz, operacja przypieta (ADR-024) | cache w providerze / nowy w wersji modulowej |
| 9 | `providers/corine.py:870,891` `_transform_bbox_to_epsg3857/_wgs84` | 2180 -> 3857/4326 | `transform_bounds(densify_pts=21)` | nowy |
| 10 | `providers/soilgrids.py:275` `_transform_bbox_to_wgs84` | 2180 -> 4326 | `transform_bounds(densify_pts=21)` — kopia (9) co do znaku | nowy |

Wywolania (6): `download/cutout.py:155` (`_bbox_to_2180`),
`cli/download_cmd.py:305` (`_bbox_to_wgs84`), `:439` (`_country_bbox`),
`:1599` (`_resolve_laz_bbox`). Wywolania (8): `cutout.py:150,216,221`,
`download_cmd.py:405,438,827,1593,1980`, `dmr.py:255,323`.

Do tego decyzja "uklad czeski => operacja przypieta" w dwoch zapisach:
`cutout.py:58 _CZ_CRS` (etykiety, `strip().upper()`) i
`download_cmd.py:285 _CZ_CRS_WKIDS` (wkid, bez strip).

### 1.2 Dowody rozjazdu

**(a) Kopia (7) to dokladnie (1), tylko szybsza** (`exp3_transform.py`, A):

```
N-34-130-D-d-2-4   identical=True  maxdiff=0.000e+00
M-34-76-A-a-1      identical=True  maxdiff=0.000e+00
timing x200: get_bbox=1454 ms  _sheet_frame_2180=4 ms
```

Komentarz w `cutout.py:605` sam przyznaje, ze to obejscie kosztu
`Transformer.from_crs` (~7 ms) w `sheet_parser`. Cache nalezy do
`sheet_parser` (albo nizej), nie do `cutout`.

**(b) 2180 -> 4326, bbox 50 km przez poludnik osiowy 19E** (`exp3`, B):

```
geometry._transform_bbox (4 pkt)                 dN=-65.64 m
parser_2000._transform_bbox_to_wgs84 (4 pkt)     dN=-65.64 m
sheet_parser._transform_bbox_to_wgs84 (6 pkt)    dN=+0.00 m
transform_bounds densify 21 (corine/soilgrids)   dN=+0.00 m
dmr.bbox_to_crs (9 pkt/krawedz, pinned)          dN=+0.00 m
```

Poprawka z 2026-09-28 (6 pkt, docstring w `sheet_parser.py:933-947`)
trafila do JEDNEJ z pieciu kopii czteronaroznikowych. Trzy metody gesciejsze
zgadzaja sie co do 0,00 m — nie ma miedzy nimi czego wybierac, roznia sie
tylko kosztem.

**(c) Kierunek odwrotny 4326 -> 2180 gubi pas na POLUDNIU** (`exp5`, B;
`exp7`): rownoleznik w odwzorowaniu poprzecznym ma minimum `y` na poludniku
osiowym, wiec 4 narozniki podnosza dolna krawedz:

```
lon 18.6-19.4 lat 52.9-53.0 : dS=+74.89 m
lon 18.0-20.0 lat 50.0-50.2 : dS=+478.97 m
lon 18.9-19.1 lat 53.0-53.05: dS=+4.68 m
```

Skutek w CLI: `kartograf download --bbox 18,50,20,50.2 --bbox-crs EPSG:4326
--target-crs EPSG:2180` liczy zasieg wycinka przez `cutout._bbox_to_2180`
(kopia 6): `min_y` = 237447,4 zamiast 236968,4 — **raster wynikowy nie
obejmuje 479 m zadanego obszaru przy 19E**, a nazwa pliku `bbox/<coords>.tif`
niesie zle wspolrzedne. Tryb LISTY arkuszy PL-1992 jest odporny (0/4800
przypadkow z utrata, `exp6` A) — wylacznie dlatego, ze powrotna droga
2180 -> 4326 w `find_sheets_for_bbox` (kopia 2, 6 pkt) odzyskuje narozniki.
Odpornosc jest przypadkowa, nie projektowa.

**(d) PL-2000 z bboxa WGS84 gubi cale wiersze arkuszy** (`exp6` C, `exp7`):
kopia (5) `_transform_bbox_to_zone_crs` dla bboxa przez poludnik osiowy
strefy (18E dla strefy 6):

```
szer=0.4: dS = +18.9 m    szer=1.2: dS = +170.0 m
szer=0.8: dS = +75.6 m    szer=2.0: dS = +472.3 m
find_sheets_for_bbox(system='2000') z bboxa WGS84: ZGUBIONY arkusz w 82/3200
  szer=0.8 lat0=50.535: zgubione ['6.135.17', '6.135.18', '6.135.19']
```

Potwierdzenie pojedynczego przypadku (`exp7`): `BBox(17.6, 50.535, 18.4,
50.555, "EPSG:4326")` -> bbox strefowy z 4 naroznikow ma `min_y` =
5 600 002,5, gesty 5 599 926,1, a gorna krawedz wiersza 135 lezy na
5 600 000 -> wynik 8 arkuszy; po podmianie kopii (5) na `transform_bounds`
16 arkuszy (wiersz 6.135.* wraca). Z CLI: `kartograf download --bbox
17.6,50.535,18.4,50.555 --bbox-crs EPSG:4326 --system 2000` pobiera o jeden
wiersz arkuszy za malo i nic nie ostrzega. **To blad funkcjonalny w
publicznym `find_sheets_for_bbox` (eksport `kartograf/__init__.py`,
10 wywolan w Hydrografie), nie tylko duplikacja.**

Dla uzupelnienia: tor PL-2000 z bboxa EPSG:2180 arkuszy NIE gubi (0/1000,
`exp5` A) — wybrzuszenie strefy dominuje nad strata z pkt (b); `get_bbox`
arkuszy 1:10000 w obu systemach: 0,000 m roznicy miedzy 4 naroznikami a
gesta obwiednia; `SheetParser("N-34").get_bbox("EPSG:2180")`: dS = +468 m
(arkusz 1:1M przez 19E — nieistotne praktycznie, ale ta sama wada).

**(e) Domyslny vs przypiety transformer 2180 -> 5514 (Cieszyn)**: 0,00 m na
wszystkich krawedziach (`exp3` E) — potwierdza review-1: pyproj wybiera te
sama operacje; przypiecie jest polityka (ADR-024), nie korekta liczbowa.

**(f) `_CZ_CRS` vs `_CZ_CRS_WKIDS`** (`exp4_czcrs.py`): 3 z 8 etykiet
rozstrzygane odwrotnie (`"5514"`, `"EPSG:5514 "`, `"ESRI:5514"`). Z CLI
nieosiagalne (`--bbox-crs` ma `choices` z osmiu etykiet `EPSG:`,
`_geometry_envelope` uzywa `to_epsg()`); osiagalne tylko z biblioteki przez
`_bbox_to_2180`. NISKA, ale znika za darmo przy jednej funkcji.

### 1.3 Docelowy ksztalt

Nowy modul-lisc **`kartograf/core/bbox.py`** (zaleznosci: `pyproj`, `numpy`,
`kartograf.exceptions`; `core` nie moze importowac `transform/` wg
ARCHITECTURE "core -> nic wewnetrznego przy imporcie", wiec operacja
przypieta wchodzi przez duck typing):

```python
class BBox(NamedTuple):            # PRZENIESIONY z sheet_parser (definicja, nie kopia)
    min_x: float; min_y: float; max_x: float; max_y: float; crs: str

_DENSIFY = 21  # jak corine/soilgrids; bbox_to_crs ma dzis 9 probek/krawedz

@functools.lru_cache(maxsize=64)
def _transformer(src: str, dst: str) -> pyproj.Transformer:
    return pyproj.Transformer.from_crs(src, dst, always_xy=True)  # thread-safe od pyproj 3.1

def validate_bbox(bbox: BBox, *, crs: str | None = None) -> None:
    """ValidationError: wspolrzedna nieskonczona/NaN, min > max, albo crs != oczekiwany.
    Bbox zdegenerowany (punkt, min == max) jest DOZWOLONY (udokumentowane zachowanie
    find_sheets_for_bbox)."""

def transform_bbox(
    bbox: BBox, target_crs: str, *, transformer: Any | None = None
) -> BBox:
    """Obwiednia bboxa w ukladzie docelowym, zawsze z zageszczonych krawedzi.

    transformer=None  -> pyproj z cache, `transform_bounds(densify_pts=_DENSIFY)`;
    transformer=obj   -> obiekt z `.transform(xs, ys)` (np. PinnedTransform):
                         _DENSIFY probek na krawedz, obwiednia min/max.
    Ten sam uklad (po normalizacji etykiety) -> ten sam bbox z etykieta docelowa.
    """
```

`sheet_parser.py` robi `from kartograf.core.bbox import BBox` — wszystkie
dotychczasowe sciezki importu (`kartograf.BBox`,
`kartograf.core.sheet_parser.BBox`, **`kartograf.core.geometry.BBox` —
Hydrograf importuje tak w `backend/scripts/bootstrap.py:188,212`**) dzialaja
bez shimu, bo moduly te nadal importuja nazwe. `BBox` NIE zmienia ksztaltu.

Konsumenci po zmianie:

- `SheetParser.get_bbox`: `transform_bbox(BBox(w, s, e, n, "EPSG:4326"), crs)`;
  kopie (1) i (2) znikaja. Listy dozwolonych CRS (`EPSG:2180/4326` dla
  PL-1992, `_SUPPORTED_CRS` dla PL-2000) **zostaja** w pierwszym kroku —
  otwarcie na dowolny CRS to osobna decyzja produktowa, nie uproszczenie.
- `parser_2000.py`: kopie (3)(4)(5) -> `transform_bbox`; naprawia (d).
- `geometry.py`: `_read_shp_bboxes`/`_read_gpkg_bboxes` wolaja
  `transform_bbox` (efekt uboczny: jeden transformer na warstwe zamiast
  jednego na obiekt — plik z 1000 obiektow przestaje kosztowac ~7 s);
  `_transform_bbox` z 6 argumentami znika razem z wywolaniami w CLI/cutout
  (krok K6), do tego czasu zostaje nietkniete (nie jako shim, lecz dlatego, ze
  jego wywolania sa w plikach zajetych przez innych agentow).
- `cutout.py`: `_sheet_frame_transformer`/`_sheet_frame_2180` usuniete,
  `estimate_pl_cutout_bytes` wraca do `SheetParser(leaf).get_bbox("EPSG:2180")`
  (po K2 tak samo szybkie); `_bbox_to_2180` -> `transform_bbox(bbox,
  "EPSG:2180", transformer=pinned if is_czech_crs(bbox.crs) else None)`.
- `dmr.py`: cialo `bbox_to_crs` to przypadek `transformer=pinned`;
  `bbox_to_crs` znika, `CuzkDmrProvider._bbox_to_crs` wola
  `transform_bbox(bbox, target, transformer=self._pinned(...))`; CLI tak samo.
- `is_czech_crs(label: str) -> bool` w `core/bbox.py` (`label.strip().upper()`,
  porownanie po wkid `{"5514", "3045"}`) zastepuje `_CZ_CRS` i `_CZ_CRS_WKIDS`.
  Alternatywa "dane w `CountryProfile`" (`sources/registry`) jest ladniejsza
  architektonicznie, ale `core` nie importuje `sources` — zostawic na etap 2
  (DE/SK), gdy pojawi sie trzeci zbior ukladow.
- `corine.py`/`soilgrids.py`: metody `_transform_bbox_to_*` staja sie
  `transform_bbox(bbox, "EPSG:4326")[:4]` — opcjonalnie, osobny commit.

### 1.4 Ryzyko

- **Liczby sie zmienia** tam, gdzie 4 narozniki byly zle: bbox/arkusz
  przecinajacy poludnik osiowy ukladu docelowego (19E dla 2180, 18/21/24E dla
  stref). Dla arkuszy 1:10000 i wiekszych skal: 0,000 m (`exp5` C, D). Dla
  `N-34` (1:1M) +468 m na S. Testy z `pytest.approx`/`abs=`:
  `test_sheet_parser.py` (20 `abs=`), `test_pl2000_verification.py` (33),
  `test_parser_2000.py` (73 `approx`), `test_geometry.py` (42/12) — implementer
  ma spodziewac sie przesuniec WYLACZNIE dla arkuszy grubych przez 19E/18E;
  kazde inne przesuniecie to regresja.
- Nazwy plikow wycinkow (`bbox/<coords>.tif`) dla zadan w WGS84 przez 19E
  zmienia sie (poprawnie) — testy CLI/cutout z bboxem WGS84 (test_cli.py: 33
  wystapien `EPSG:4326`, test_pl_cutout.py: 6) do przejrzenia; zadne z nich
  nie koduje na sztywno `bbox/` z WGS84 (grep), wiec spodziewany koszt: 0-2
  asercje.
- `bbox_to_crs` 9 -> 21 probek/krawedz: obwiednie CZ moga urosnac o ulamki
  metra; testy CZ asertujace nazwe pliku po normalizacji
  (`test_cli.py:3408` i sasiednie) do sprawdzenia. Jesli ktorys asertuje
  liczby z 9 probek, zaktualizowac liczby — nie przywracac 9.
- Publiczne API: `find_sheets_for_bbox`/`find_sheets_2000_for_bbox` zwracaja
  WIECEJ (poprawnych) arkuszy dla bboxow WGS84 przez poludnik osiowy strefy —
  dla Hydrografa to naprawa, wpis `fix` w CHANGELOG. `BBox` bez zmian.
- Watki: `lru_cache` + `Transformer` sa bezpieczne od pyproj 3.1 (cutout juz
  na tym polega, N9); w repo pyproj 3.7.2.
- ADR-024/ADR-027 pozostaja w mocy: funkcja nie wybiera operacji — dostaje
  ja (`transformer=`); polityka przypinania zostaje tam, gdzie jest.

### 1.5 Rekomendacja

**ROBIC teraz.** Uzasadnienie: to jedyny obszar, w ktorym duplikacja juz
kosztuje poprawnosc (d) i (c), a dwie z czterech kopii "z poprawka" sa
zgodne co do 0,00 m z pyproj'owym `transform_bounds`, ktore juz jest
w repo (corine/soilgrids). Kroki K1-K4 nie dotykaja plikow zajetych przez
innych agentow i same naprawiaja (d) oraz koszt (a). K6 (cutout/CLI/dmr)
czeka.

---

## 2. Rejestr systemow godel, `Sm5Sheet`, wzorce CZ (review-1 O3, D12) — ROBIC teraz

### 2.1 Stan

`core/parser_registry.py` (144 linie):

- `detect_system` — produkcja: `cli/download_cmd.py:897,1893`,
  `download/storage.py:206`, `providers/cuzk/dmr.py:222`,
  `core/sheet_parser.py:23` (`_is_pl2000_format`). Potrzebny.
- `path_parts` — produkcja: `download/storage.py:336`. Potrzebny.
- `SheetSystem.parser_factory` — **0 odczytow w produkcji** (grep calego
  `kartograf/`: tylko definicja i 4 rejestracje); czytany w
  `tests/test_parser_registry.py:55,59,107,112`.
- `_make_parser_pl2000/_pl1992/_cz_tm33/_cz_sm5` (`:77-106`) — istnieja tylko
  dla `parser_factory`; `_make_parser_cz_sm5` to jedyny import `core ->
  providers` (opisany jako wyjatek w `docs/ARCHITECTURE.md:118-124`).
- `register_system` — 4 wywolania w tym samym module; publiczne API bez
  zewnetrznego klienta (Hydrograf/Hydrolog nie importuja `parser_registry`).
- `providers/cuzk/sheets.py:137 Sm5Sheet` — jedyny producent w produkcji to
  `_make_parser_cz_sm5`, czyli nikt. `dmr.py` konstruuje `ParserTM33` wprost
  (`:236`) i dla SM5 w ogole nie potrzebuje bboxa (URL openzu to nazwa
  arkusza). `Sm5Sheet.get_bbox` z wlasnym cyklem `MetadataCache` (D16) jest
  kodem osiagalnym tylko z testow (`tests/test_cuzk_sheets.py:317-390`,
  klasa `TestSm5SheetParserObject`).

Wzorce godel CZ: `_CZ_TM33_PATTERN` (`parser_registry.py:89`) i `_GODLO_RE`
(`parser_tm33.py:18`, z grupami); `_CZ_SM5_PATTERN` (`parser_registry.py:90`)
i `_SM5_RE` (`sheets.py:50`). Tresc identyczna, rozni sie obsluga bialych
znakow (`exp1_godla.py`):

```
godlo           detect_system  Sm5Sheet          SheetIndex.sm5_sheet     ParserTM33          SheetParser
'CTES96'        cz_sm5         Sm5Sheet:'CTES96' (wzorzec OK)             ParseError          ParseError
' CTES96'       pl1992         Sm5Sheet:'CTES96' ValidationError(pre-net) ParseError          ParseError
'302_5550'      cz_tm33        ParseError        ValidationError          ParserTM33:'302_5550' ParseError
' 302_5550'     pl1992         ParseError        ValidationError          ParserTM33:'302_5550' ParseError
' 6.179.12.20'  pl1992         ParseError        ValidationError          ParseError          SheetParser:'6.179.12.20'
'303_5550'      cz_tm33        ParseError        ValidationError          ParseError          ParseError
```

Rozjazd: `Sm5Sheet`, `ParserTM33` i `SheetParser` robia `strip()`, rejestr
i `SheetIndex.sm5_sheet` — nie. Skutek w CLI (argparse nie obcina bialych
znakow): `kartograf download " 302_5550"` trafia do toru PL i konczy sie
mylacym `Error: Nieprawidlowe godlo PL-1992 ...` zamiast pobrania albo
komunikatu o TM33. `kartograf download 303_5550` (nieparzyste km) idzie do
CZ i `ParserTM33` zglasza `ParseError`, ktory `_run_cz` tlumaczy na
`Error:` (download_cmd.py:266-268) — poprawne. Waga NISKA; naprawa to jeden
`strip()` w `detect_system`.

### 2.2 Docelowy ksztalt

```python
# core/parser_registry.py
@dataclass(frozen=True)
class SheetSystem:
    id: str; country: str
    detect: Callable[[str], bool]
    path_parts: Callable[[str], list[str]]

CZ_TM33_PATTERN = re.compile(r"^(\d{3})_(\d{4})$")   # jedyne zrodlo; ParserTM33 importuje
CZ_SM5_PATTERN = re.compile(r"^[A-Z]{4}\d{2}$")      # jedyne zrodlo; cuzk/sheets importuje
_PL2000_PATTERN = re.compile(r"^[5-8]\.\d")

SYSTEMS: tuple[SheetSystem, ...] = (pl2000, cz_tm33, cz_sm5, pl1992)  # literal, bez register_system

def detect_system(godlo: str) -> SheetSystem:   # strip(); nigdy None (pl1992 = fallback)
def path_parts(godlo: str) -> list[str]:
```

Kierunek importow: `parser_tm33 -> parser_registry` i `cuzk/sheets ->
parser_registry` sa zgodne z warstwami (rejestr nie importuje nic z `core`
na poziomie modulu, wiec cyklu nie ma). `Sm5Sheet` usunac razem z eksportem
w `providers/cuzk/__init__.py` i klasa testow `TestSm5SheetParserObject`;
`SheetIndex.sm5_sheet` dostaje `strip()` (albo wola `CZ_SM5_PATTERN` na
`mapnom.strip()`).

`detect_system` zwracajace `SheetSystem` zamiast `SheetSystem | None`
usuwa cztery martwe galezie `if system is None` (`download_cmd.py:899-900`,
`storage.py:207-212`, `dmr.py:223`, `sheet_parser.py:24`) — komentarze w
kodzie juz przyznaja, ze `None` jest niemozliwe.

### 2.3 Ryzyko

- BREAKING (CHANGELOG): `kartograf.providers.cuzk.Sm5Sheet` znika;
  `parser_registry.register_system`/`SheetSystem.parser_factory` znikaja.
  `kartograf/__init__.py` nietkniete (`ParserTM33` zostaje eksportem).
  Hydrograf/Hydrolog: brak importow z `providers.cuzk` ani `parser_registry`
  (grep w `/home/claude-agent/workspace/Hydrograf`, `Hydrolog`).
- Dokumentacja do poprawy: `docs/ARCHITECTURE.md:118-124` (uwaga o leniwym
  imporcie `core -> providers` — przestaje byc prawdziwa, co jest zyskiem),
  `:841-843` (instrukcja "nowy kraj": rejestracja bez `parser_factory`),
  `docs/SCOPE.md:484`, `CLAUDE.md` (struktura: `sheets.py` bez `Sm5Sheet`).
- Testy: `test_parser_registry.py` — 5 testow do przepisania/usuniecia
  (`:23-29` test duplikatu `register_system`, `:55,59,107,112`
  `parser_factory`); `test_cuzk_sheets.py:317-390` do usuniecia (8 testow
  `Sm5Sheet`); `test_storage.py` bez zmian (uzywa `path_parts`).
- `strip()` w `detect_system` zmienia `FileStorage.get_raw_path(" x")`
  wylacznie dla identyfikatorow z bialymi znakami — nie wystepuja (LAZ
  `godlo` z WFS jest `strip()`-owane w `_feature_to_tile:452`).

### 2.4 Rekomendacja

**ROBIC teraz** (krok K5, jeden commit, bez konfliktow z innymi agentami —
dotyka `core/parser_registry.py`, `core/parser_tm33.py`,
`core/sheet_parser.py` (1 linia), `providers/cuzk/sheets.py`,
`providers/cuzk/__init__.py`, `providers/cuzk/dmr.py` (1 linia), docs).
Uwaga: `download/storage.py:206-212` tez ma martwa galaz `None`, ale plik
jest zajety — zostawic te galaz do K6 (mypy nie protestuje, bo `detect_system`
po zmianie zwraca nie-Optional i `system is not None` jest tylko zbedne).

---

## 3. Parsowanie `--bbox "x,y,x,y"` w CLI (review-1 D4, O11) — ROBIC

### 3.1 Stan i dowod

Piec kopii: `cli/download_cmd.py:1150` (`_cmd_download_bbox`), `:1579`
(`_resolve_laz_bbox`), `:1968` (`_cz_download_bbox`),
`cli/landcover_cmd.py:143`, `cli/soilgrids_cmd.py:103`. Landcover i
soilgrids sa identyczne co do znaku (diff: tylko `if`/`elif`); obie wpisuja
`"EPSG:2180"` na sztywno (brak `--bbox-crs` w `_parser.py:245,350`).

`exp2_bbox_parse.py` (te same wejscia przez wszystkie kopie, z mockami):

| wejscie | `download` | `laz` | `cz` | `landcover` | uwagi |
|---|---|---|---|---|---|
| `1,2,3` | rc=1, `Error:` na stderr + **"Expected: ..." na stdout** | `ValueError` (lapany w `_cmd_download_laz:1690`) | rc=1, bez podpowiedzi | jak download | 3 rozne zachowania |
| `a,b,c,d`, `1;2;3;4`, `1,2,3,4,` | jw. | jw. | jw. | jw. | komunikat = surowy tekst `float()` |
| ` 1, 2 ,3,4` | OK | OK | OK | OK | spojne |
| **`10,10,5,5`** | **OK** | **OK** | **OK** | **OK** | **nikt nie sprawdza min < max** |
| **`nan,1,2,3`** / `inf,1,2,3` | **OK** | **OK** | **OK** | **OK** | **nikt nie sprawdza skonczonosci** |

Skutki na koncu toru (ten sam skrypt + wywolanie `main`):

- `find_sheets_for_bbox(BBox(10, 10, 5, 5, "EPSG:2180"))` -> `['L-33-1-D-c-4-3']`
  — jeden arkusz-smiec, kod 0, zadnego ostrzezenia;
- `kartograf download --bbox nan,1,2,3 -o ... --country pl` ->
  `Error: ValueError: cannot convert float NaN to integer` + "Ustaw
  KARTOGRAF_DEBUG=1 ..." (bariera ostatniej szansy w `commands.py:103-108`),
  kod 1 — komunikat nie mowi uzytkownikowi, co zrobil zle.

Walidacja `min >= max` istnieje w repo dwa razy, tylko dla CZ:
`parser_tm33.py:78` (`find_tiles_tm33_for_bbox`, **0 wywolan w produkcji**) i
`cuzk/sheets.py:181` (`_validate_request_bbox`).

Galaz martwa (`_cz_download_bbox:1966-1975`, `if bbox is None`): jedyny
wolajacy `_cmd_download_cz` (`:2124`) jest wolany tylko z `_run_cz` (`:265`),
a `_run_cz` z `cmd_download` (tryb godla, `:912`), `_dispatch_area` (`bbox=part`,
`:758`) i `_cmd_download_geometry` (`bbox=` z `_resolve_cz_geometry_bbox`,
`:2167`). `_cmd_download_cz:2076` ustawia `has_godlo = args.godlo is not None
and bbox is None` — bez godla i bez bboxa z CLI dojsc sie nie da
(`cmd_download:873-887` wymaga jednego z trzech). Dociera tam tylko
`tests/test_cli.py:3408` (`test_bbox_string_is_normalized_to_image_sr`) i
`:3491` (`test_invalid_bbox_string_returns_1`), wolajac `_cmd_download_cz(args)`
wprost.

### 3.2 Docelowy ksztalt

```python
# cli/_parser.py  (modul juz "definicja argparse" — parsowanie wartosci argumentu tu pasuje)
def parse_bbox_arg(text: str, crs: str) -> BBox:
    """'min_x,min_y,max_x,max_y' -> BBox(crs). ValidationError (jeden komunikat:
    'Invalid bbox format: <powod>. Expected: min_x,min_y,max_x,max_y (e.g. ...)')
    dla: liczby != 4, wartosc nienumeryczna, NaN/inf, min > max (core.bbox.validate_bbox)."""
```

Wolajacy nie lapia wyjatku: `ValidationError` jest `KartografError`, wiec
`main` drukuje `Error: ...` na **stderr** i zwraca 1 (`commands.py:97-101`) —
pieciokrotne `try/except/print/return 1` znika, podpowiedz "Expected"
przestaje isc na stdout (wada z review-1 D4: `-q` jej nie tlumil, `2>` nie
lapal). `_resolve_laz_bbox` przestaje rzucac `ValueError` (klauzula
`except (..., ValueError)` w `_cmd_download_laz:1690` zostaje tylko jesli ma
inne zrodlo — sprawdzic). Galaz `bbox is None` w `_cz_download_bbox` znika,
parametr `bbox: BBox` przestaje byc Optional.

Walidacja `min <= max` i skonczonosci na poziomie biblioteki
(`core/bbox.py::validate_bbox`, sekcja 1.3) wchodzi tez do
`find_sheets_for_bbox` / `find_sheets_2000_for_bbox` (zamiast smieci i
`ValueError`) oraz zastepuje dwie kopie CZ (`find_tiles_tm33_for_bbox`,
`_validate_request_bbox`).

### 3.3 Ryzyko

- Zmiana zachowania CLI: `--bbox 10,10,5,5` i `--bbox nan,...` koncza sie
  `Error: Invalid bbox format ...` (kod 1) zamiast smieci/`ValueError`.
  Podpowiedz przenosi sie na stderr. Testy: `test_cli.py:1361-1389`
  (asertuja `"Invalid bbox format" in captured.err` — fraza zostaje),
  `test_landcover.py:341-348` (`"Invalid bbox" in captured.err` — zostaje),
  `test_cli.py:3408` i `:3491` — musza przejsc przez `cmd_download`/`main`
  zamiast `_cmd_download_cz(args)` (albo zniknac: `:3491` sprawdza martwa
  galaz). Zaden test nie asertuje "Expected" na stdout (grep).
- Publiczne API: `find_sheets_for_bbox` zglasza `ValidationError` dla bboxa
  odwroconego/NaN — typ wyjatku juz udokumentowany w jego docstringu; dla
  Hydrografa odwrocony bbox byl bledem danych, ktory dotad przechodzil
  cicho. Wpis w CHANGELOG. Bbox-punkt (`min == max`) nadal dozwolony.
- Konflikty: `cli/download_cmd.py` (3 z 5 kopii + martwa galaz) — zajety.
  `cli/_parser.py`, `landcover_cmd.py`, `soilgrids_cmd.py` — wolne.

### 3.4 Rekomendacja

**ROBIC**, w dwoch commitach: K7a (helper + landcover + soilgrids + testy,
teraz), K7b (`download_cmd.py`: trzy kopie, LAZ, galaz martwa — po innych
agentach).

---

## 4. Klasy parserow godel — NIE ROBIC (scalanie)

`SheetParser` (PL-1992, 1208 linii) deleguje do `Parser2000` (ADR-017,
composition), `ParserTM33` (93 linie) to czysta siatka. Trzy rozne domeny:
litery/pasy/slupy i podzialy 2x2/3x3; metryczna siatka strefowa z podzialami
2x2 i 5x5; kafle 2 km po narozniku SW. Wspolny interfejs (`godlo`,
`get_bbox()`, `uklad`) juz istnieje nieformalnie i wystarcza wszystkim
konsumentom. Wspolna klasa bazowa dodalaby warstwe bez usuniecia zadnej
linii: `get_parent/get_children/get_all_descendants` maja rozna semantyke
(PL-2000: dwie niezalezne galezie 1:5k i 1:2k), a `ParserTM33` nie ma
hierarchii.

Pomocniki przeciec sa juz wspolne (`_axis_overlaps`, `_expand_degenerate`
importowane z `sheet_parser` do `parser_2000`; `_bboxes_intersect_2000` to
3-liniowy alias z innym epsilonem — udokumentowany, P-12). `_is_pl2000_format`
idzie przez rejestr. Nic do roboty poza `strip()` z sekcji 2.

Martwy kod w `parser_tm33.py`: `ParserTM33.tile_for` (review-1 O4) i
`find_tiles_tm33_for_bbox` — **0 wywolan w produkcji** (grep; CZ bbox idzie
prosto do `exportImage`, nie przez kafle). Czysta matematyka, 16 testow,
koszt utrzymania zerowy; mozna usunac razem z O4 albo zostawic jako
fundament etapu 2 (LAZ CZ per kafel). Nie wplywa na ocene: NIE ROBIC teraz.

---

## 5. Auto-detekcja kraju/systemu z godla w CLI — NIE ROBIC

Jedna sciezka: `cmd_download:897` `detect_system(args.godlo)` -> `country`
-> `_run_cz` albo tor PL (`SheetParser(args.godlo)` tylko waliduje, `:940`);
`_cz_download_godlo:1893` wola `detect_system` drugi raz, by odroznic SM5 od
TM33 (sidecar `capability`/`horizontal_crs`) — to odczyt z tego samego
rejestru, nie kopia logiki. `dmr.download:222` waliduje kraj godla po
stronie biblioteki (celowa redundancja: API biblioteki musi odrzucic godlo
PL bez CLI). `kartograf parse` (`parse_cmd.py:158`) zna tylko `SheetParser`
(godla CZ -> `ParseError`) — to luka zakresu (SCOPE), nie duplikacja. Jedyna
poprawka to `strip()` z sekcji 2.

---

## 6. Parsery odpowiedzi uslug — NIE ROBIC

- **`providers/pl/skorowidz.py::parse_skorowidz_records`** (`:116`) — jedna
  implementacja (regexy `_RECORD`/`_FIELD`/`_TEMPLATE`), 39 testow + fixtury
  realnych odpowiedzi (`test_real_gugik_responses.py`). `_horizontal_crs`
  (`:39`) to jednoliniowy adapter `parse_pl_uklad(v) or (None, None)` z dwoma
  wywolaniami (`:79`, `:132`) — wchlonac przy najblizszej edycji pliku,
  nie osobnym commitem.
- **`sources/registry.py::parse_pl_uklad`** (`:412`) — od 2026-10-06 jedyny
  parser `uklad_xy`; trzej konsumenci (`skorowidz._horizontal_crs`,
  `horizontal_crs_for_uklad`, `LazTile.uklad`) wolaja te sama funkcje
  (grep). D3 zamkniete; nic do roboty.
- **WFS LAZ** (`providers/pl/gugik_laz.py:436-505`, `_corner_xy:649`) —
  jedna implementacja GML, obsluga kolejnosci osi `urn:` vs `EPSG:2180`
  (potwierdzona live 2026-09-29). Plik zajety przez innego agenta; brak
  duplikacji — nie dotykac.
- **`sources/sidecar.py::read_asc_nodata`** (`:69`) — jedna implementacja
  dla ASC. Nodata z GeoTIFF czytane w `cli/download_cmd.py:1800`
  (`_read_tif_nodata`, rasterio, `None` przy bledzie) i `dmr.py:463`
  (`ds.nodata` z domyslnym `CUZK_NODATA` — inna semantyka: provider pisze,
  CLI czyta). Sidecar juz dyspozytoruje po rozszerzeniu w `_file_min_x`
  (`:75-88`), wiec `read_raster_nodata(path)` (ASC przez naglowek, TIFF przez
  rasterio) bylby naturalny — ale to 10 linii i dotyka dwoch zajetych plikow.
  Opcjonalny K8.
- **`core/geometry.py`** — jeden parser WKB/GPKG (`_point_from_wkb`,
  `_parse_gpkg_envelope`), jeden czytnik SHP (pyshp); 49 testow. Rozne formaty
  = rozne parsery; jedyna wspolna rzecz (transformacja per obiekt) jest
  objeta sekcja 1 (K4). NIE ROBIC poza tym.

---

## 7. Fasada `cli/commands.py` (review-1 O8) — ROBIC z zastrzezeniem

`commands.py:12-16,47-48` re-eksportuje prywatne `_create_provider_and_storage`
i `_resolve_laz_bbox` "dla testow". Testy juz patchuja
`kartograf.cli.download_cmd.*` (pamiec projektu); po K7b `_resolve_laz_bbox`
zmienia kontrakt (nie rzuca `ValueError`), wiec to naturalny moment, by
zostawic w fasadzie tylko `main`/`create_parser`/`cmd_*`. Zastrzezenie:
najpierw policzyc importy w `tests/` (`grep -rn "from kartograf.cli.commands
import" tests/`) i przepiac je na moduly docelowe w tym samym commicie.
K9, po K7b.

---

## Plan dla implementera

Kolejnosc = numeracja. Kazdy krok to osobny, niezalezny commit (Conventional
Commits), po kazdym: `pytest -m "not live"`, `ruff check`, `ruff format
--check`, `mypy kartograf/` (baseline 32 bledy — porownywac LISTE, nie
liczbe). Testy nowe weryfikowac **mutacja** (zepsuc kod, test ma oblac).

Oznaczenia: **[WOLNY]** — nie dotyka plikow zajetych; **[KONFLIKT: ...]** —
dotyka `cli/download_cmd.py`, `download/*`, `sources/sidecar.py` lub
`providers/pl/gugik_laz.py` -> wykonac PO zakonczeniu pracy innych agentow,
po `git pull`/rebase.

### K1 [WOLNY] `core/bbox.py`: BBox, validate_bbox, transform_bbox z cache

- Pliki: nowy `kartograf/core/bbox.py`; `kartograf/core/sheet_parser.py`
  (definicja `BBox` zastapiona `from kartograf.core.bbox import BBox`);
  `CLAUDE.md` + `docs/ARCHITECTURE.md` (drzewo modulow: `core/bbox.py`).
- Ksztalt: sekcja 1.3 (`BBox`, `_transformer` z `lru_cache`, `validate_bbox`,
  `transform_bbox(bbox, target_crs, *, transformer=None)`, `is_czech_crs`).
  `transform_bbox` dla `transformer=None` uzywa `transform_bounds(...,
  densify_pts=21)`; dla obiektu — 21 probek na krawedz przez
  `transformer.transform(np.ndarray, np.ndarray)`; ten sam uklad -> `_replace(crs=target)`.
  NIE importowac `kartograf.transform` (warstwy).
- Testy: nowy `tests/test_core_bbox.py`:
  - tozsamosc etykiety (`"epsg:2180"` -> `"EPSG:2180"` bez transformacji);
  - 4326 -> 2180 dla `(18.0, 50.0, 20.0, 50.2)`: `min_y` ~ 236968.4 (nie
    237447.4) — mutacja "4 narozniki" musi oblac;
  - 2180 -> 4326 dla `(475000, 600000, 525000, 610000)`: `max_y` ~ 53.3551052;
  - cache: `Transformer.from_crs` wolany raz dla 200 wywolan tej samej pary
    (`patch.object(Transformer, "from_crs", wraps=...)`, jak
    `test_pl_cutout.py:1074`);
  - `transformer=` duck: obiekt z `.transform` wywolany z tablicami 84 pkt
    (4 x 21), wynik = obwiednia; `PinnedTransform` z `transform/crs.py`
    przechodzi (test moze importowac `transform`, modul nie);
  - `validate_bbox`: NaN/inf/`min > max` -> `ValidationError`; punkt OK;
    `crs=` niezgodny -> `ValidationError`.
- Importy `BBox` z `kartograf`, `kartograf.core.sheet_parser`,
  `kartograf.core.geometry` nadal dzialaja (test: trzy asercje `is`).

### K2 [WOLNY] `SheetParser.get_bbox` i `_transform_bbox_to_wgs84` przez `transform_bbox`

- Pliki: `core/sheet_parser.py` (`:621-686`, `:931-979`; import `Transformer`
  znika z modulu).
- Zachowanie: te same listy dozwolonych CRS; wyniki identyczne dla arkuszy
  1:10000 (test: `N-34-130-D-d-2-4`, `M-34-76-A-a-1` — liczby jak dzis co do
  1e-6); `N-34` (1:1M) `min_y` nizsze o ~468 m — zaktualizowac asercje, jesli
  ktoras go koduje. `find_sheets_for_bbox`: dodac `validate_bbox(bbox)` na
  wejsciu (odwrocony/NaN -> `ValidationError`; test mutacyjny: bez walidacji
  `BBox(10,10,5,5)` zwraca `['L-33-1-D-c-4-3']`).
- Testy: `test_sheet_parser.py` (144) — spodziewane poprawki tylko w
  asercjach dla arkuszy grubych przez 19E; nowy test wydajnosci "jeden
  `from_crs` na 200 `get_bbox`".
- CHANGELOG: `fix(core)` — obwiednia `get_bbox` arkuszy przez 19E, walidacja
  bboxa w `find_sheets_for_bbox` (BREAKING-light: `ValidationError` zamiast
  smieci).

### K3 [WOLNY] `parser_2000.py`: trzy kopie -> `transform_bbox`; naprawa gubienia wierszy

- Pliki: `core/parser_2000.py` (`:575-621`, `:690-761`; `Parser2000.get_bbox:310`,
  `find_sheets_2000_for_bbox:804,829`; import `Transformer` znika).
- Testy: `test_parser_2000.py`, `test_pl2000_verification.py` — spodziewane
  poprawki tylko dla bboxow/arkuszy przez 18/21/24E. **Nowy test regresji**:
  `find_sheets_for_bbox(BBox(17.6, 50.535, 18.4, 50.555, "EPSG:4326"),
  system="2000")` zawiera `"6.135.17"`, `"6.135.18"`, `"6.135.19"` (16
  arkuszy); mutacja (przywrocenie 4 naroznikow w `_transform_bbox_to_zone_crs`)
  daje 8 i oblewa. `validate_bbox` na wejsciu `find_sheets_2000_for_bbox`.
- CHANGELOG: `fix(parser_2000)` — bbox WGS84 przez poludnik osiowy strefy
  gubil wiersz arkuszy.

### K4 [WOLNY] `core/geometry.py`: czytniki SHP/GPKG przez `transform_bbox`

- Pliki: `core/geometry.py` (`_read_shp_bboxes:234`, `_read_gpkg_bboxes:402`
  -> `transform_bbox(BBox(..., source_crs.to_wkt()), target_crs)`;
  `_transform_bbox:417` ZOSTAJE do K6, bo woła go `cutout.py:155` i
  `download_cmd.py:305,439,1599` — nie tworzyc shimu, po prostu nie ruszac).
- Uwaga: `source_crs` to obiekt `CRS`; klucz cache w `core/bbox._transformer`
  jest stringiem — podac `source_crs.to_wkt()` (albo `to_string()`), nie
  obiekt. Dla pliku z 1000 obiektow: jeden transformer zamiast tysiaca.
- Testy: `test_geometry.py` (49) — bez zmian oczekiwanych poza plikami WGS84
  przez 19E (brak takich w fixturach wg grep `EPSG:4326` = 4 wystapienia,
  sprawdzic). Nowy test: `Transformer.from_crs` raz na warstwe z 3 obiektami.

### K5 [WOLNY] Rejestr bez `parser_factory`, bez `Sm5Sheet`, jeden wzorzec na system, `strip()`

- Pliki: `core/parser_registry.py` (sekcja 2.2), `core/parser_tm33.py`
  (`_GODLO_RE` -> `CZ_TM33_PATTERN` z rejestru), `core/sheet_parser.py:21-24`
  (`detect_system(...).id == "pl2000"`), `providers/cuzk/sheets.py`
  (`_SM5_RE` -> `CZ_SM5_PATTERN`, `sm5_sheet` ze `strip()`, usuniecie
  `Sm5Sheet`), `providers/cuzk/__init__.py` (eksport), `providers/cuzk/dmr.py:222-227`
  (bez `system is None`), `docs/ARCHITECTURE.md:118-124,841-843`,
  `docs/SCOPE.md:484`, `CLAUDE.md` (struktura), `docs/CHANGELOG.md` (BREAKING:
  `Sm5Sheet`, `register_system`, `parser_factory`).
- Testy: `test_parser_registry.py` — usunac `:23-29` (duplikat
  `register_system`) i 4 testy `parser_factory`; dodac `detect_system(" CTES96").id
  == "cz_sm5"` i `detect_system("302_5550 ").id == "cz_tm33"` (mutacja: bez
  `strip()` -> `pl1992`); `test_cuzk_sheets.py:317-390` usunac
  (`TestSm5SheetParserObject`); dodac test, ze `SheetIndex.sm5_sheet(" CTES96 ")`
  nie rzuca przed siecia (mock klienta).
- `download/storage.py:206-212` (martwa galaz `None`) — zostawic do K6.

### K6 [KONFLIKT: download/cutout.py, cli/download_cmd.py, download/storage.py] Jedna obwiednia w cutout/CLI/dmr

- Pliki: `download/cutout.py` (`_CZ_CRS:58`, `_bbox_to_2180:133-162`,
  `:197-221` `bbox_to_crs` -> `transform_bbox(..., transformer=pinned)`,
  `_sheet_frame_transformer`/`_sheet_frame_2180:601-636` USUNAC,
  `estimate_pl_cutout_bytes:662` -> `SheetParser(leaf).get_bbox("EPSG:2180")`),
  `cli/download_cmd.py` (`_CZ_CRS_WKIDS:285`, `_bbox_to_wgs84:288-312`,
  `_country_bbox:399-455`, `_resolve_laz_bbox:1584-1606`,
  `_geometry_envelope:850`, `_cz_download_bbox:1977-1980`),
  `providers/cuzk/dmr.py` (`bbox_to_crs:489-521` USUNAC, `_bbox_to_crs:390`
  -> `transform_bbox`; `_EDGE_SAMPLES` znika), `core/geometry.py`
  (`_transform_bbox:417-467` USUNAC), `download/storage.py:206-212`
  (bez galezi `None`).
- `is_czech_crs` z `core/bbox.py` zastepuje oba zbiory.
- Testy: `test_pl_cutout.py:1073` (`cache_clear` na usunietym obiekcie ->
  `kartograf.core.bbox._transformer.cache_clear()`); testy CZ z normalizacja
  bboxa (`test_cli.py:3408`, `test_cuzk_dmr.py`) — jesli koduja liczby z 9
  probek, zaktualizowac na 21; nowy test CLI: `--bbox 18,50,20,50.2 --bbox-crs
  EPSG:4326 --target-crs EPSG:2180` daje nazwe pliku z `min_y` ~ 236968
  (mutacja: 4 narozniki -> 237447). `test_cli.py` 33 wystapien `EPSG:4326` —
  przejrzec po uruchomieniu.
- CHANGELOG: `fix(download)` — wycinek PL z bboxa WGS84 przez 19E tracil pas
  na poludniu; `refactor` — jedna obwiednia.

### K7a [WOLNY] `parse_bbox_arg` + landcover/soilgrids

- Pliki: `cli/_parser.py` (nowa funkcja; sekcja 3.2), `cli/landcover_cmd.py:141-152`,
  `cli/soilgrids_cmd.py:101-112` (bez `try/except`; `bbox =
  parse_bbox_arg(args.bbox, "EPSG:2180")`).
- Testy: `test_landcover.py:341-348` (fraza zostaje; dodac asercje, ze
  `captured.out` NIE zawiera "Expected"); nowe: `10,10,5,5` i `nan,1,2,3` ->
  `Error: Invalid bbox format` na stderr, kod 1, bez "ValueError" w tekscie
  (mutacja: usuniecie `validate_bbox` z helpera -> test oblewa). Analogicznie
  dla `soilgrids hsg`.

### K7b [KONFLIKT: cli/download_cmd.py] Trzy kopie w download_cmd + martwa galaz CZ

- Pliki: `cli/download_cmd.py:1149-1157`, `:1578-1582` (`_resolve_laz_bbox`
  przestaje rzucac `ValueError`; przejrzec `except (..., ValueError)`
  w `_cmd_download_laz:1690`), `:1966-1975` (galaz `bbox is None` USUNAC;
  sygnatura `bbox: BBox`).
- Testy: `test_cli.py:1361-1389` (fraza zostaje, podpowiedz na stderr),
  `:3408` -> przez `cmd_download(args)`/`main([...])`, `:3491` usunac albo
  przepisac na `main(["download", "--bbox", "invalid", "--country", "cz"])`.

### K8 [KONFLIKT: sources/sidecar.py, cli/download_cmd.py] (opcjonalny) `read_raster_nodata`

- `sidecar.py`: `read_raster_nodata(path)` (ASC: `_read_asc_header`, TIFF:
  rasterio, `None` przy bledzie); `download_cmd.py:1800 _read_tif_nodata`
  znika; `dmr.py:463` zostaje (inna semantyka — domyslna wartosc zapisu).
- Testy: `test_sidecar.py` + jeden test CLI CZ dla TIFF bez tagu.

### K9 [KONFLIKT: cli/download_cmd.py posrednio — po K7b] Fasada `commands.py`

- Usunac re-eksport `_create_provider_and_storage`, `_resolve_laz_bbox`;
  przepiac importy w `tests/` na `kartograf.cli.download_cmd`. CHANGELOG
  (BREAKING dla importow z fasady — tylko testy).

### Czego NIE robic (zeby implementer nie poszedl za daleko)

- Nie scalac `SheetParser`/`Parser2000`/`ParserTM33` w hierarchie (sekcja 4).
- Nie przenosic `BBox` poza `core` ani nie zmieniac jej ksztaltu (Hydrograf:
  `kartograf.core.geometry.BBox`, `kartograf.BBox`; 6 konstrukcji `BBox(`).
- Nie otwierac `get_bbox` na dowolny CRS w ramach K2/K3 (osobna decyzja).
- Nie przenosic `is_czech_crs` do `CountryProfile` przed etapem 2 (DE/SK).
- Nie zmieniac `parse_skorowidz_records`, GML LAZ, WKB/GPKG — jedna
  implementacja, pokryte fixturami realnych odpowiedzi.
- Nie dodawac `--bbox-crs` do `landcover`/`soilgrids` w K7a (zmiana zakresu,
  nie uproszczenie; SoilGrids i tak transformuje do WGS84 sam).
