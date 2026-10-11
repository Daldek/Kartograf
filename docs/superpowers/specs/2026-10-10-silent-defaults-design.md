# Spec: Ciche wartosci domyslne (d) — komunikaty d1/d2 i wspolny mechanizm zapytan obszarowych d3

**Data:** 2026-10-10
**Status:** decyzje w sekcji 0 (rozmowa 2026-10-10); WDROZONY 2026-10-10 na
galezi `feat/silent-defaults` (ADR-034; raport
`docs/research/2026-10-10-silent-defaults/raport.md`), merge do `develop`
po decyzji uzytkownika
**Wersja docelowa:** 0.7.2 (galaz `feat/silent-defaults` z `develop`)
**Dokumenty zrodlowe:**
- backlog `docs/PROGRESS.md` "Do 0.7.2" pozycja (d) i "Ryzyko KRON86 3"
- pomiar `docs/research/2026-10-10-wcs-limits/raport.md` (limity, siatka,
  skladanie kawalkow, pogranicze WCS GUGiK KRON86)
- ADR-023 pkt 4-5 (prostokatne obwiednie krajow, `--country auto`),
  ADR-024 (zakaz serwerowego przesuniecia tresci, kotwica NW), ADR-027
  (wycinek PL z arkuszy), pomiary CUZK 2026-09-29 (limit exportImage
  ~8 Mpx, budzet 4 Mpx)

---

## 0. Decyzje uzytkownika (2026-10-10)

| # | Decyzja | Sekcja |
|---|---|---|
| D-U1 | **d1: tylko komunikat.** Bez zmiany domyslnego ukladu wysokosci przy `--country auto` (PL EVRF2007, CZ Bpv). Wspolny uklad domyslny — do przemyslenia w kolejnych wydaniach. | 2 |
| D-U2 | **d2: widoczne `Info:`** z wybrana warstwa, lista pozostalych i podpowiedzia `--layer`; bez zmiany wyboru (pierwsza warstwa). Wymaganie `--layer` ewentualnie w 0.8.0. | 3 |
| D-U3 | **d3: odejscie od mozaikowania plikow arkuszy, przygotowanie do WCS.** Wspolny mechanizm dzielenia zapytan obszarowych w `transport/`, wyciagniety z klienta CUZK i uzyty przez CUZK oraz GUGiK WCS. (a) wycinki PL z WCS korzysta z niego. | 4 |
| D-U4 | **Jeden spec na cale (d).** | — |
| D-U5 | **Pomiar WCS tylko KRON86** (EVRF2007 tymczasowo niedostepny). | 4.2 |
| D-U6 | **Blad NMPT `download_bbox` (RGB uint8 zamiast wysokosci) naprawiany razem z (a)**, nie w (d) (obsluga odpowiedzi multipart `image/x-aaigrid` powstaje tam raz). | 4.6 |

## 1. Kontekst i cel

Inwentaryzacja wartosci domyslnych (PROGRESS, backlog 0.7.2) znalazla trzy
miejsca, w ktorych domyslny wybor dzieje sie bez widocznego sladu:

1. `--country auto` dla obszaru PL+CZ bez `--vertical-crs` daje PL
   w EVRF2007 (EPSG:9651) i CZ w Bpv (EPSG:8357); roznica ok.
   0,11-0,15 m; w runtime brak komunikatu (tylko ARCHITECTURE 4.6,
   USAGE 1.4; sidecary oznaczaja uklad poprawnie).
2. GPKG z wieloma warstwami bez `--layer` — obszar zadania z pierwszej
   warstwy, slad tylko w `logger.info` (domyslnie niewidoczny).
3. `mosaic_and_crop(dtype=None)` bierze typ pierwszego zrodla (`merge`).
   W kodzie Kartografa ryzyko jest nieaktywne (wycinek PL podaje
   `dtype="float32"`, kafle CUZK sa float32 z jednego zapytania), ale
   uzytkownik postanowil (D-U3) przy tej okazji przygotowac grunt pod
   wycinki z WCS: dzielenie duzego zapytania do uslugi na kawalki
   i skladanie odpowiedzi ma byc jednym mechanizmem, nie kodem klienta
   CUZK.

Cel: kazdy z trzech domyslnych wyborow zostawia widoczny slad albo przestaje
byc cichy; mechanizm kawalkow istnieje w `transport/`, ma dwoch
uzytkownikow (CUZK exportImage bez zmiany zachowania, GUGiK WCS NMT 1 m)
i jest gotowy dla (a).

### 1.1 Poza zakresem

- Zmiana domyslnego ukladu wysokosci przy `--country auto` (D-U1).
- Wymaganie `--layer` (D-U2; kandydat do 0.8.0).
- Wycinki PL `--target-crs` z WCS, nodata WCS, wybor lotu WCS vs ADR-028,
  odpowiedzi multipart `image/x-aaigrid`, naprawa NMPT `download_bbox`
  (D-U6) — wszystko w (a). W (d) wycinek PL dalej sklada arkusze.
- Usuniecie parametrow arkuszowych z publicznego `mosaic_and_crop`
  (`snap_to_source_grid`, `assign_crs`) — zmiana lamiaca stabilnego API
  (`__all__`, "stable since 0.7.1"); kandydat do 0.8.0 po (a).
- Dzielenie zapytan ortofotomapy WCS (rozdzielczosc i faza siatki nie
  zmierzone; poza D-U5) i NMPT (D-U6).

## 2. d1 — `Info:` o mieszanych ukladach wysokosci pod `--country auto`

### 2.1 Stan kodu (develop `4fa4e9c`)

| Element | Dzis | Gdzie |
|---|---|---|
| Podzial obszaru | `_dispatch_area(args, bbox, filepath=None)`: kraje z `_countries_for_bbox` (prostokaty ADR-023 pkt 4), czesci `_country_bbox`, komunikaty przyciecia `_print_clipping_info` w jednym bloku PRZED pobraniem, potem petla CZ -> PL | `cli/download_cmd.py:702-822` |
| Tryby | `--bbox` (`cmd_download` :1371) i `--geometry` (`_cmd_download_geometry` :2464); godlo wyznacza kraj sam | jw. |
| Domyslny uklad PL | `_resolve_pl_sentinels`: `args.vertical_crs = ... or "EVRF2007"` na KOPII args w galezi PL | `:395` |
| Domyslny uklad CZ | `_cmd_download_cz`: `vertical_crs = args.vertical_crs or "Bpv"` | `:2349` |
| Brak flagi | argparse `--vertical-crs default=None` | `cli/_parser.py:240-243` |
| Rozstrzygniecie kraju opcja | `KRON86` (tylko PL) zamienia `auto` na `pl` (`_pl_only_flags`, `Info: --country auto -> pl (...)`) | `:736-744` |

### 2.2 Zachowanie

- Warunek: `auto` po `_pl_only_flags` (czyli nadal oba kraje), `PL` i `CZ`
  w `parts`, `args.vertical_crs is None`.
- Jeden `Info:` na stderr w bloku komunikatow przed pobraniem (po
  `_print_clipping_info`), takze z `-q` (jak pozostale `Info:`
  `_dispatch_area`):
  `Info: --country auto bez --vertical-crs: czesc PL w EVRF2007, czesc CZ
  w Bpv (rozne uklady wysokosci, roznica ok. 0,11-0,15 m); jeden uklad dla
  obu: --vertical-crs EVRF2007`
  (tresc dokladna w planie; asercje testow na fakty: `EVRF2007`, `Bpv`,
  `--vertical-crs`).
- Jawne `--vertical-crs EVRF2007` — oba kraje EVRF2007, bez komunikatu.
  Jawne `Bpv` przy PL+CZ — dzisiejsza obsluga bez zmian (`_validate_cross_country`
  / walidacja galezi PL); `KRON86` — kraj PL (istniejacy `Info:`), bez nowego.
- Kod wyjscia i pliki bez zmian.

### 2.3 Swiadomy kompromis

Obwiednie krajow sa prostokatne (ADR-023 pkt 4): zadanie lezace w calosci
w Polsce, ale w prostokacie CZ (np. Katowice, Opole), dostaje czesc CZ
i ten komunikat, choc czesc CZ moze byc w calosci nodata (istniejacy
`Warning:` N2 `_warn_cz_all_nodata`). Komunikat nie zgaduje tresci —
mowi o ukladach czesci, ktore zadanie faktycznie uruchamia; wiedza
o pokryciu przychodzi dopiero po pobraniu, a blok komunikatow jest przed
pobraniem (spojnie z S3). Alternatywa (komunikat po petli, tylko gdy obie
czesci maja dane) wymaga przeniesienia wyniku CZ przez `_run_cz` (dzis
`int`) — odrzucona jako wieksza zmiana dla tego samego sladu.

### 2.4 Biblioteka

Bez zmian: biblioteka nie ma podzialu `auto` (PL `DownloadManager`
i CZ `CuzkDmrProvider` wolane osobno, uklad podaje wolajacy).

## 3. d2 — widoczna informacja o domyslnej warstwie GPKG

### 3.1 Stan kodu

| Element | Dzis | Gdzie |
|---|---|---|
| Wybor | `_resolve_gpkg_layer(conn, filepath, layer)`: `layer` podany — walidacja; brak — `tables[0]` i `logger.info("Multiple layers in GPKG, using ...")` | `core/geometry.py:314-358` |
| Wolajacy | `_read_gpkg_bboxes` (:381) i `read_source_crs` (:489); przez nie `read_feature_bboxes`, `get_overall_bbox`, `find_sheets_for_geometry` | `core/geometry.py` |
| CLI | `download` (`_geometry_envelope`, `_resolve_cz_geometry_bbox`, `_build_parent_request`, `_download_pl_geometry`, tryb listy :2498), `landcover download` (:172), `soilgrids hsg` (:105); jedno uruchomienie wola 2-4 funkcje geometrii | `cli/*.py` |
| Biblioteka | `find_sheets_for_geometry` w `__all__`; `download_pl_cutout(geometry=, layer=)` | `__init__.py`, `download/cutout.py:271` |
| `--help` | "Layer name for multi-layer GPKG (default: first layer)" w 3 podkomendach | `cli/_parser.py:317-320, 401-404, 481-484` |
| SHP | jedna warstwa, bez pojecia `layer` | `_read_shp_bboxes` |

### 3.2 Zachowanie

- **Wybor bez zmian** — pierwsza tabela cech z `gpkg_contents` (D-U2).
- **CLI:** kazda podkomenda z `--geometry` rozstrzyga warstwe RAZ, przed
  praca, nowa funkcja `core.geometry.resolve_layer(filepath, layer) ->
  LayerChoice` (`name: str | None` — `None` dla SHP; `available:
  tuple[str, ...]`; `defaulted: bool`). Gdy `defaulted` i
  `len(available) > 1` — jeden `Info:` na stderr (takze z `-q`):
  `Info: <plik> ma N warstw, uzyto pierwszej '<nazwa>' (pozostale: a, b,
  ...); inna warstwa: --layer NAZWA`. Dalej CLI przekazuje JAWNA nazwe
  (`args.layer = choice.name`), wiec nizsze wywolania nie powtarzaja
  komunikatu. Bledy (`ValidationError`: brak tabel, nieznana warstwa) —
  jak dzis `Error:`, kod 1.
- **Biblioteka:** `_resolve_gpkg_layer` przy domyslnym wyborze z wielu
  warstw — `logger.warning` zamiast `logger.info` (widoczne domyslnie
  przez `logging.lastResort`, spojnie z innymi ostrzezeniami biblioteki,
  np. per arkusz "No data"). Tresc jak CLI, po angielsku (komunikaty
  loggera w bibliotece). Kazde wywolanie funkcji geometrii bez `layer`
  moze je powtorzyc — wolajacy biblioteczny podaje `layer=`, zeby go
  uniknac (docstring).
- `--help` (3 podkomendy): "Warstwa GPKG (domyslnie pierwsza; przy wielu
  warstwach Info z lista)" — tresc w planie.
- `resolve_layer` NIE trafia do `__all__` (uzytek CLI; publiczne API bez
  zmian poza poziomem logu).

## 4. d3 — wspolny mechanizm zapytan obszarowych

### 4.1 Stan kodu

| Element | Dzis | Gdzie |
|---|---|---|
| CUZK | `CuzkClient.export_image(endpoint, bbox, *, pixel_size, image_sr, no_data, output_path)`: kotwica NW + calkowita liczba pikseli (`round`), pojedynczy eksport do `output_path` albo `_tile_grid` -> kawalki `<out>.<pid>_<tid>.part<i>.tif` -> `mosaic_and_crop(parts, bbox, out, nodata=no_data)` -> `_overwrite_crs`; czesci usuwane w `finally`; blad zszycia = `DownloadError` "nie udalo sie zszyc"; kawalkowanie wymaga `bbox.crs == image_sr` | `providers/cuzk/client.py:128-221` |
| Siatka kawalkow | `_tile_grid(bbox, pixel_size, width_px, height_px, max_w, max_h, max_px) -> list[tuple[BBox, int, int]]`: N->S, W->E, kotwica NW, kawalki bliskie kwadratu (`isqrt(max_px)`), podzial `divmod` | `client.py:284-338` |
| Limity CUZK | `MAX_EXPORT_WIDTH=15000`, `MAX_EXPORT_HEIGHT=4100`, `MAX_EXPORT_PIXELS=4_000_000` (pomiar 2026-09-29: 7,5 Mpx OK, 8,38 Mpx HTTP 500) | `client.py:36-40` |
| GUGiK WCS | `GugikWcsMixin._construct_wcs_url(bbox, format)`: jedno GetCoverage, `SUBSET` z `.2f`; `download_bbox` NMT/NMPT/orto — jedno `download_to` (`retries=MAX_RETRIES`), BEZ walidatora tresci, BEZ wyrownania bbox | `providers/pl/wcs.py`, `gugik.py:409-509`, `gugik_nmpt.py`, `gugik_orto.py:233-292` |
| Wolajacy WCS | `DownloadManager.download_bbox(bbox, filename, format)` (sidecar z `request.bbox` zadania); CLI nie wola `download_bbox` (PL `--bbox` = arkusze albo wycinek z arkuszy) | `download/manager.py:1445-1506` |
| Mozaika | `mosaic_and_crop(inputs, bbox, output_path, *, nodata, dst_kwds, snap_to_source_grid, assign_crs, dtype)`; publiczna (`__all__`); wolajacy: CUZK (kawalki), wycinek PL (arkusze) | `transport/mosaic.py:174` |
| Timeout GUGiK | `GugikProvider.DEFAULT_TIMEOUT = 30` (timeout `requests` = na polaczenie i miedzy porcjami danych, nie na cale pobranie) | `gugik.py:141` |

### 4.2 Fakty z pomiaru (`docs/research/2026-10-10-wcs-limits/raport.md`)

- WCS NMT KRON86: brak limitu rozmiaru do 100 Mpx; ok. 3 s/Mpx, 4 MB/Mpx
  (float32 bez kompresji); host niestabilny (zerwane polaczenia
  `RemoteDisconnected` / `ConnectionResetError`, ponowienie przechodzi).
- Serwer probkuje do siatki ZADANIA (najblizszy sasiad): bbox poza
  siatka zrodla = dane przesuniete o ulamek piksela bez sladu. Siatka
  zrodla NMT 1 m: krok 1 m, krawedzie `k + 0,5` m — w 9 rejonach Polski.
- Kawalki na wspolnej siatce skladaja sie bit w bit z jednym zapytaniem.
- Odpowiedz bledu WCS to `ows:ExceptionReport` (XML).

### 4.3 Nowy modul `kartograf/transport/chunks.py`

```python
@dataclass(frozen=True)
class GridSpec:
    """Pixel grid of a service: step and the position of one grid line."""
    step: float
    origin_x: float = 0.0
    origin_y: float = 0.0

@dataclass(frozen=True)
class ChunkLimits:
    """Per-request limits: width, height (px) and the pixel budget."""
    max_width: int
    max_height: int
    max_pixels: int

@dataclass(frozen=True)
class Chunk:
    bbox: BBox
    width: int
    height: int

def align_bbox(bbox: BBox, pixel_size: float, grid: GridSpec | None = None
               ) -> tuple[BBox, int, int]: ...
def plan_chunks(bbox: BBox, width: int, height: int, pixel_size: float,
                limits: ChunkLimits) -> list[Chunk]: ...
def fetch_chunks(chunks: Sequence[Chunk], bbox: BBox, output_path: Path,
                 fetch: Callable[[Chunk, Path], None], *,
                 nodata: float | None = None) -> Path: ...
```

- **`align_bbox`** — wspolna regula wyrownania:
  - `grid is None` (CUZK, bez zmian): kotwica NW, `width = max(1,
    round(dx / pixel_size))`, `height` analogicznie, `min_y`/`max_x`
    przeliczone z kotwicy (dzisiejsze `client.py:150-161`, przeniesione).
  - `grid` podany (GUGiK): rozszerzenie NA ZEWNATRZ do linii siatki
    (`floor`/`ceil` od `origin` co `step`, z tolerancja `_GRID_TOL_PX`
    z `mosaic.py`, zeby bbox lezacy na linii w granicach bledu
    zmiennoprzecinkowego nie dostal kolumny); `width`/`height` dokladne.
    `pixel_size != grid.step` = `ValidationError` (bez skalowania).
- **`plan_chunks`** — dzisiejsze `_tile_grid` przeniesione bez zmiany
  algorytmu (kotwica NW, N->S, W->E, kawalki bliskie kwadratu, podzial
  `divmod`); jeden kawalek, gdy zadanie miesci sie w limitach (warunek
  dzisiejszej galezi "single" przeniesiony tutaj). Zwraca `list[Chunk]`
  zamiast krotek.
- **`fetch_chunks`** — wykonanie planu:
  - jeden kawalek: `fetch(chunk, output_path)` (plik wynikowy wprost, jak
    dzisiejszy pojedynczy eksport);
  - wiele: `fetch` kazdego kawalka do `<out>.<pid>_<tid>.part<i>.tif`
    po kolei (sekwencyjnie — host GUGiK niestabilny, CUZK z budzetem
    czasu), potem `mosaic_and_crop(parts, bbox, output_path,
    nodata=nodata)`; czesci usuwane w `finally`; wyjatek `fetch`
    przechodzi bez zmian (jego `DownloadError` z ponowieniami
    `download_to`); blad zszycia (poza `ValidationError`) =
    `DownloadError` "nie udalo sie zszyc N kawalkow ..." i usuniecie
    wyniku (dzisiejsza obsluga CUZK, przeniesiona).
  - Ponowienie dotyczy kawalka (`download_to(retries=MAX_RETRIES)`
    w `fetch`), nie calego zadania.
- Modul NIE zna uslug, URL-i ani CRS — tylko geometria planu i skladanie
  (jak `CuzkClient` "nie zna godel ani produktow").
- Publiczne API: bez wpisow w `__all__` (wewnetrzny transport; eksport
  dopiero, gdy zapyta konsument — jak `check_source_grid` w 0.7.1).

### 4.4 `mosaic_and_crop` — typ zrodel (pierwotne d3)

- `dtype is None` i zrodla o roznych typach pasm -> `ValidationError`
  przed `merge`: `mosaic_and_crop: zrodla maja rozne typy pasm (float32,
  int32) — podaj dtype=` (tresc w planie). Typy z petli metadanych
  (zrodla otwierane po jednym — bez zmiany).
- `dtype` podany — jak dzis (VRT z wymuszonym typem).
- Zrodla jednego typu — bez zmian (CUZK, kawalki WCS, wycinek PL).
- Docstring i CHANGELOG `### Zmienione`: dotad typ pierwszego zrodla
  (np. obciecie float do int bez sladu), teraz blad; wolajacy z mieszanymi
  typami podaje `dtype=`.
- Docstring modulu `mosaic.py`: konsumenci = skladanie kawalkow
  (`transport/chunks.py`) i wycinek PL z arkuszy (do (a)).

### 4.5 CUZK na nowym mechanizmie (zachowanie bez zmian)

- `export_image`: `align_bbox(bbox, pixel_size)` -> `plan_chunks(...,
  ChunkLimits(MAX_EXPORT_WIDTH, MAX_EXPORT_HEIGHT, MAX_EXPORT_PIXELS))` ->
  przy >1 kawalku kontrola `bbox.crs == image_sr` (jak dzis, przed
  pierwszym zapytaniem) -> `fetch_chunks(..., fetch=_export_single...,
  nodata=no_data)` -> `_overwrite_crs`.
- Stale `MAX_EXPORT_*` zostaja w `CuzkClient` (testy patchuja je przez
  `patch.object`).
- `_tile_grid` znika z `client.py` (bez aliasu); testy siatki przechodza
  na `plan_chunks` (`tests/test_transport_chunks.py`), testy
  `TestExportImage` zostaja przy `export_image` bez zmian w asercjach.

### 4.6 GUGiK WCS NMT 1 m na nowym mechanizmie

- `GugikWcsMixin` dostaje atrybuty klasy:
  - `WCS_GRID: GridSpec | None = None` — siatka zrodla; `None` = jedno
    zapytanie jak dzis (NMPT, orto — 1.1).
  - `WCS_CHUNK_LIMITS = ChunkLimits(max_width=40_000, max_height=40_000,
    max_pixels=16_000_000)` — budzet niezawodnosci, nie limit serwera
    (komentarz z odnosnikiem do raportu: 16 Mpx ok. 50 s, 64 MB; 40000 px
    boku zmierzone).
- `GugikProvider` (NMT): `WCS_GRID = GridSpec(step=1.0, origin_x=0.5,
  origin_y=0.5)` (komentarz: raport pkt 4, 7). `GugikNmptProvider`
  (dziedziczy po `GugikProvider`): jawnie `WCS_GRID = None` (D-U6 —
  `image/tiff` NMPT to RGB; naprawa w (a)). `GugikOrtoProvider`: domyslne
  `None`.
- Nowa metoda mixinu `_download_wcs(bbox, output_path, format, timeout)`
  wolana przez `download_bbox` NMT/NMPT/orto (zastepuje trzy identyczne
  bloki `download_to`):
  - `format == "GTiff"` i `WCS_GRID` podany: `align_bbox(bbox,
    WCS_GRID.step, WCS_GRID)` -> `plan_chunks` -> `fetch_chunks`; `fetch`
    = `download_to(session, _construct_wcs_url(chunk.bbox, format), path,
    timeout=timeout, retries=MAX_RETRIES, validate=reject_error_document("WCS"),
    description=...)`; `nodata=None` (WCS nie deklaruje nodata — raport
    pkt 3; nodata to temat (a)).
  - w przeciwnym razie: jedno zapytanie jak dzis, z dodanym
    `validate=reject_error_document("WCS")` (dzis `ows:ExceptionReport`
    z HTTP 200 trafilby do pliku `.tif`).
- Skutek dla uzytkownika NMT KRON86 `download_bbox` (GTiff):
  - zasieg pliku = bbox zadania rozszerzony na zewnatrz do siatki `k +
    0,5` m (< 1 px z kazdej strony) — dotad bbox poza siatka dawal tresc
    przesunieta o ulamek piksela wzgledem georeferencji (raport pkt 4);
  - obszar > 16 Mpx pobierany kawalkami i skladany bit w bit (raport
    pkt 5) — dotad jedno dlugie zapytanie, ktorego zerwanie oznaczalo
    ponowienie calosci;
  - sidecar `request.bbox` = bbox zadania (bez zmian); zasieg pliku
    wynika z pliku.
- `_construct_wcs_url` bez zmian (`.2f` wystarcza dla siatki 0,5 m;
  kawalki maja wspolrzedne na liniach siatki).

### 4.7 Zwiazek z (a)

(a) dostaje gotowe: `GridSpec`/`ChunkLimits`/`fetch_chunks`, walidacje
odpowiedzi i miejsce na siatke EVRF2007 (`WCS_GRID` per uklad, gdy
endpoint wroci). Do rozstrzygniecia w specu (a), nie tutaj: nodata WCS
(0,0 poza pokryciem i w danych waznych), kompozycja lotow serwera vs
ADR-028 (Zulawy, Terespol — raport pkt 8), odpowiedz multipart
`image/x-aaigrid` (EVRF2007, NMPT), los wycinka z arkuszy i parametrow
arkuszowych `mosaic_and_crop`.

## 5. Dokumentacja

- `docs/DECISIONS.md` (CRLF): **ADR-034 "Wspolny mechanizm zapytan
  obszarowych (kawalki na siatce zrodla)"** — kontekst (CUZK `_tile_grid`,
  GUGiK jedno zapytanie, pomiar 2026-10-10), decyzje (4.3-4.6: siatka
  zrodla + wyrownanie na zewnatrz, budzet niezawodnosci 16 Mpx GUGiK /
  4 Mpx CUZK, sekwencyjnie, ponowienie per kawalek, `dtype` w
  `mosaic_and_crop`), alternatywy odrzucone (mozaika plikow arkuszy jako
  docelowa droga wycinkow — D-U3; rownolegle kawalki — niestabilny host;
  wyrownanie do siatki uslugi CUZK — research-cz 2026-09-29 pkt 2, poza
  zakresem), skutki (NMT bbox +< 1 px, CUZK bez zmian, (a) korzysta).
  Wiersz w indeksie. Uzupelnienie ADR-023 (CUZK: kawalkowanie w
  `transport/chunks.py`).
- `docs/ARCHITECTURE.md`: 2 (modul `transport/chunks.py`), 4.2 (WCS
  `download_bbox`: siatka, kawalki, walidacja), 4.5 (CUZK: kawalkowanie
  przez `transport/chunks.py`), 4.6 (`Info:` d1), opis `--geometry`
  (d2; tam, gdzie opisany wybor warstwy).
- `docs/USAGE.md` (z diakrytykami): `--geometry`/`--layer` (Info przy
  wielu warstwach), pogranicze `--country auto` (Info d1).
- `--help`: `--layer` (3 podkomendy).
- `docs/CHANGELOG.md` `[0.7.2]`: `### Dodane` (`Info:` d1, d2;
  kawalkowanie WCS NMT), `### Zmienione` (`mosaic_and_crop` mieszane typy
  = blad; NMT `download_bbox` wyrownanie do siatki; `logger.warning`
  warstwy GPKG), `### Naprawione` (WCS bez walidacji tresci).
- `docs/PROGRESS.md`: backlog (d) [x] po merge; "Ryzyko KRON86 3" [x]
  (komunikat).

## 6. Testy i weryfikacja

Offline (konwencje istniejacych plikow; HTTP przez `patch` `download_to`
/ `session.get` jak `tests/test_cuzk_client.py`, `tests/test_gugik_provider.py`):

| # | Scenariusz | Oczekiwane |
|---|---|---|
| T1 | `align_bbox` z `GridSpec(1, 0.5, 0.5)`, bbox calkowity (450000..) | rozszerzony do 449999.5/460000.5, `width` = 10001 |
| T2 | jw., bbox na liniach siatki +- 1e-9 | bez dodatkowej kolumny/wiersza |
| T3 | `align_bbox` bez siatki, wysokosc ulamkowa | kotwica NW, wynik identyczny z dzisiejsza regula CUZK |
| T4 | `align_bbox`, `pixel_size != grid.step` | `ValidationError` |
| T5 | `plan_chunks` (przeniesione `test_tile_grid_respects_budget_and_covers_request`) | suma pikseli = zadanie, kotwica NW, kazdy kawalek w limitach |
| T6 | `fetch_chunks` 1 kawalek | `fetch` raz z `output_path`, brak plikow `.part` |
| T7 | `fetch_chunks` 4 kawalki rastrow o znanych wartosciach | wynik = zlozenie bit w bit; czesci usuniete |
| T8 | `fetch_chunks`, `fetch` rzuca na 2. kawalku | wyjatek przechodzi, czesci usuniete, brak wyniku |
| T9 | `mosaic_and_crop`, zrodla float32 + int32, `dtype=None` | `ValidationError` z oboma typami, brak pliku |
| T10 | jw. z `dtype="float32"` | wynik float32 (jak dzis) |
| T11 | `TestExportImage` CUZK (istniejace) | bez zmian w asercjach |
| T12 | NMT `download_bbox` 3000x3000 m przy patchowanym `WCS_CHUNK_LIMITS` (np. 4 Mpx) | 4 zapytania z `SUBSET` na liniach `k + 0,5`, wynik zlozony, `reject_error_document` w `validate` |
| T13 | NMT `download_bbox` PNG | jedno zapytanie, bbox bez wyrownania |
| T14 | NMPT, orto `download_bbox` | jedno zapytanie (bez wyrownania); `validate` podany |
| T15 | CLI `--bbox` PL+CZ, `--country auto`, bez `--vertical-crs` | stderr `Info:` z `EVRF2007`, `Bpv`, `--vertical-crs`; kod jak dzis |
| T16 | jw. z `--vertical-crs EVRF2007` / `--country pl` / bbox tylko PL | brak tego `Info:` |
| T17 | CLI `--geometry` GPKG 2 warstwy bez `--layer` (`download`, `landcover download`, `soilgrids hsg`) | jeden `Info:` z nazwa pierwszej, druga na liscie, `--layer`; dalsze wywolania dostaja jawne `layer` |
| T18 | jw. z `--layer layer_b` / GPKG 1 warstwa / SHP | brak `Info:` |
| T19 | biblioteka `get_overall_bbox(gpkg_multi_layer)` | `logger.warning` (caplog), wybrana pierwsza |

Istniejace testy pinujace dzisiejsze URL-e WCS z bboxem calkowitym
(`test_gugik_provider.py::test_download_bbox_*`) — aktualizacja na bbox
wyrownany (zachowanie zmienione celowo, 4.6).

Na zywo (probki: katalog wskazany przez uzytkownika; sciezki nie w repo):

1. NMT KRON86 `DownloadManager(vertical_crs="KRON86").download_bbox`
   6 x 6 km (36 Mpx -> 3 kawalki przy 16 Mpx) vs jedno zapytanie WCS tego
   samego wyrownanego bboxa — bit w bit; zasieg na siatce `k + 0,5`.
2. Ten sam obszar vs arkusze OpenData (jak raport pkt 4) — bit w bit tam,
   gdzie arkusz jest lotem WCS.
3. CUZK `--country cz` bbox 10 x 10 km 2 m (25 Mpx -> kawalki 4 Mpx) —
   wynik identyczny z wynikiem sprzed zmiany (ten sam bbox z `develop`).
4. CLI `--country auto` Cieszyn (`18.60,49.752,18.65,49.768`, EPSG:4326)
   — `Info:` d1; z `--vertical-crs EVRF2007` — brak.
5. CLI `--geometry` GPKG z 2 warstwami — `Info:` d2.

Raport `docs/research/<data>-silent-defaults/raport.md`.

## 7. Pytania otwarte

Brak blokujacych. Do ewentualnej korekty przy przegladzie uzytkownika:
- budzet 16 Mpx / kawalek (4.6) — z pomiaru, ale wybor miedzy dlugoscia
  zapytania a liczba zapytan jest arbitralny;
- tresc komunikatow d1/d2 (2.2, 3.2).
