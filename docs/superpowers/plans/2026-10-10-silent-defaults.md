# Ciche wartosci domyslne (d): `Info:` d1/d2 i wspolny mechanizm zapytan obszarowych d3 — Implementation Plan

**Status:** WYKONANY 2026-10-10 (Task 0-7 bez merge; odstepstwa: `docs/PROGRESS.md`,
sesja "(d) ciche wartosci domyslne — implementacja"); checkboxy nieodhaczane.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wdrozyc w 0.7.2 spec
`docs/superpowers/specs/2026-10-10-silent-defaults-design.md` (decyzje
D-U1..D-U6): `Info:` o mieszanych ukladach wysokosci pod `--country auto`
(d1), `Info:` o domyslnej warstwie GPKG (d2), modul
`kartograf/transport/chunks.py` (wyrownanie do siatki zrodla, plan
kawalkow, pobranie i skladanie) uzyty przez CUZK `export_image` (bez zmiany
zachowania) i GUGiK WCS NMT 1 m `download_bbox`, `mosaic_and_crop` z bledem
przy mieszanych typach zrodel (d3).

**Architecture:** Jedna warstwa = jedno zadanie = jeden commit na galezi
`feat/silent-defaults` z `develop`. Kolejnosc: najpierw transport (Task 1),
potem jego dwaj uzytkownicy (Task 2 CUZK — refaktor bez zmiany zachowania,
Task 3 GUGiK — zmiana zachowania), potem niezalezne komunikaty CLI (Task 4
d2, Task 5 d1), dokumentacja (Task 6), weryfikacja na zywo (Task 7).
`transport/chunks.py` nie zna uslug: dostaje funkcje `fetch(chunk, path)`.
CLI rozstrzyga warstwe GPKG raz i przekazuje dalej jawna nazwe.

**Tech Stack:** Python 3.12, `pytest` (offline; `conftest` blokuje
gniazda), `rasterio` (rastry testowe w `tmp_path`), bez nowych zaleznosci.

**Spec:** `docs/superpowers/specs/2026-10-10-silent-defaults-design.md`.
Pomiar: `docs/research/2026-10-10-wcs-limits/raport.md`.

## Global Constraints

- Python wylacznie z `.venv`: `.venv/bin/python -m pytest ...`,
  `.venv/bin/python -m ruff ...`, `.venv/bin/python -m mypy ...`, CLI
  `.venv/bin/kartograf`.
- Brama przed KAZDYM commitem: `.venv/bin/python -m pytest tests/ -m "not live" -q`
  zielone, `.venv/bin/python -m ruff check .` i
  `.venv/bin/python -m ruff format --check .` czyste,
  `.venv/bin/python -m mypy kartograf/ tests/` bez bledow.
- Commit WYLACZNIE przez straznik wzorcow:
  `F="$HOME/.config/kartograf/forbidden-patterns.txt"; test -r "$F" && ! git diff --cached -U0 | grep '^+' | grep -qiEf "$F" && git commit ...`.
  Brak pliku wzorcow = zatrzymaj sie i zapytaj. Tresci wzorcow nie
  wpisuj do repo ani nie wypisuj.
- Commity: Conventional Commits z opisem po polsku, autor
  `Daldek <git@debever.pl>`, BEZ stopki `Co-Authored-By`. Docstringi
  i komentarze po angielsku; dokumentacja po polsku bez diakrytykow
  (poza `USAGE.md`, ktory ma diakrytyki); komunikaty CLI po polsku bez
  diakrytykow; komunikaty loggera biblioteki po angielsku.
- `docs/DECISIONS.md` ma konce linii CRLF — zachowaj je (sprawdz
  `git diff --stat`: kilkadziesiat linii, nie caly plik).
- Kazde zadanie zmieniajace zachowanie dopisuje wpis do
  `docs/CHANGELOG.md`, sekcja `## [0.7.2] - Unreleased`.
- Numery linii = stan `develop` `4fa4e9c`; po wczesniejszych zadaniach
  przesuwaja sie — szukaj po symbolu.
- Asercje na fakty (wartosci pikseli, wspolrzedne `SUBSET`, nazwy warstw,
  obecnosc `EVRF2007`/`Bpv`/`--layer` w stderr), nie na cale brzmienie
  komunikatow.
- Dane na zywo (Task 7): poza repo i poza `/tmp`, jawne `--output`,
  katalog wskazuje uzytkownik (sciezki nie zapisuj w repo); CLI z korzenia
  repo.

## Review Focus

1. **CUZK bez zmiany zachowania** — te same zapytania (bbox, `size`),
   ten sam plik wyniku przy kawalkowaniu. Test: istniejace
   `tests/test_cuzk_client.py::TestExportImage` bez zmian w asercjach
   (Task 2) + Task 7 krok 3.
2. **Wyrownanie GUGiK na zewnatrz, nigdy do wewnatrz** — wynik zawsze
   zawiera bbox zadania. Test: Task 1 `test_align_snaps_outward_to_grid`,
   Task 3 `test_nmt_download_bbox_requests_on_source_grid`.
3. **Skladanie bit w bit** — Task 1 `test_fetch_chunks_mosaics_bit_exact`,
   Task 7 krok 1.
4. **Brak czesci `.part` po bledzie** — Task 1
   `test_fetch_chunks_cleans_parts_on_fetch_error`.
5. **Jeden `Info:` d2 na uruchomienie** — Task 4
   `test_cli_geometry_multi_layer_info_once`.

---

## Mapa plikow

| Plik | Odpowiedzialnosc | Zadanie |
|---|---|---|
| `kartograf/transport/chunks.py` (nowy) | `GridSpec`, `ChunkLimits`, `Chunk`, `align_bbox`, `plan_chunks`, `fetch_chunks` | 1 |
| `kartograf/transport/mosaic.py` | blad przy mieszanych typach (`dtype=None`), docstring modulu | 1 |
| `kartograf/providers/cuzk/client.py` | `export_image` na `transport/chunks.py`, usuniecie `_tile_grid` | 2 |
| `kartograf/providers/pl/wcs.py`, `gugik.py`, `gugik_nmpt.py`, `gugik_orto.py` | `WCS_GRID`, `WCS_CHUNK_LIMITS`, `_download_wcs`, walidacja odpowiedzi | 3 |
| `kartograf/core/geometry.py` | `LayerChoice`, `resolve_layer`, `logger.warning` | 4 |
| `kartograf/cli/download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`, `_parser.py` | `Info:` d2 (raz), `--help` `--layer`, `Info:` d1 | 4, 5 |
| `docs/DECISIONS.md` (CRLF), `docs/ARCHITECTURE.md`, `docs/USAGE.md` | ADR-034, opis | 6 |
| `docs/CHANGELOG.md`, `docs/PROGRESS.md` | wpisy | 1-7 |
| `tests/test_transport_chunks.py` (nowy), `tests/test_transport_mosaic.py`, `tests/test_cuzk_client.py`, `tests/test_gugik_provider.py`, `tests/test_gugik_nmpt.py`, `tests/test_gugik_orto.py`, `tests/test_geometry.py`, `tests/test_cli.py`, testy CLI landcover/soilgrids (znajdz po `--geometry`) | testy | 1-5 |

---

### Task 0: Galaz

- [ ] `git switch develop && git switch -c feat/silent-defaults`
  (develop czysty poza ewentualnymi zmianami dokumentacji tej sesji —
  spec, plan, raport, PROGRESS — commitowanymi najpierw na `develop`
  commitem `docs(spec): ciche wartosci domyslne (d) — spec, plan i pomiar WCS`,
  jesli uzytkownik nie zrobil tego wczesniej).

### Task 1: `transport/chunks.py` i typy zrodel w `mosaic_and_crop`

**Files:** `kartograf/transport/chunks.py` (nowy),
`kartograf/transport/mosaic.py`, `tests/test_transport_chunks.py` (nowy),
`tests/test_transport_mosaic.py`, `docs/CHANGELOG.md`.

**Interfejs (spec 4.3):**
```python
@dataclass(frozen=True)
class GridSpec:
    step: float
    origin_x: float = 0.0
    origin_y: float = 0.0

@dataclass(frozen=True)
class ChunkLimits:
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

- [ ] **Step 1: testy (czerwone)** — `tests/test_transport_chunks.py`:
  - `test_align_snaps_outward_to_grid` (T1): `BBox(450000, 550000,
    460000, 560000, "EPSG:2180")`, `GridSpec(1.0, 0.5, 0.5)` -> bbox
    `(449999.5, 549999.5, 460000.5, 560000.5)`, `(10001, 10001)`;
    wariant ulamkowy `450000.7..450010.2` -> `450000.5..450010.5`, 10 px.
  - `test_align_on_grid_within_tolerance_adds_nothing` (T2): bbox na
    liniach `k + 0.5` +- 1e-9 -> bez zmian, liczby pikseli dokladne.
  - `test_align_without_grid_keeps_nw_anchor_rule` (T3): przypadki
    z `tests/test_cuzk_client.py::test_tiling_fractional_height_keeps_content_aligned`
    (500 x 181.4, piksel 2) -> `max_y`, `min_x` bez zmian, `height =
    round(181.4 / 2)`, `min_y = max_y - height * 2`.
  - `test_align_rejects_pixel_size_other_than_grid_step` (T4) ->
    `ValidationError`.
  - `test_plan_chunks_respects_budget_and_covers_request` (T5) — PRZENIESIONY
    `test_tile_grid_respects_budget_and_covers_request` z
    `tests/test_cuzk_client.py` (ta sama parametryzacja), na `Chunk`;
    dodatkowo kazdy kawalek `width <= max_width`, `height <= max_height`,
    `width * height <= max_pixels`; kawalki rozlaczne i stykaja sie
    dokladnie (sasiednie `max_x == min_x`).
  - `test_plan_chunks_single_chunk_within_limits`: zadanie w limitach ->
    jeden `Chunk` = caly bbox.
  - `test_fetch_chunks_single_writes_output_directly` (T6): `fetch`
    rejestrujacy sciezki -> jedno wywolanie z `output_path`, brak plikow
    `*.part*` w katalogu.
  - `test_fetch_chunks_mosaics_bit_exact` (T7): bbox 8 x 6 px, piksel 1,
    limity 4 x 3 -> 4 kawalki; `fetch` pisze GeoTIFF float32 kawalka
    (`rasterio`, transform z `chunk.bbox`) z wartoscia `100*row + col`
    globalnego piksela; wynik == tablica referencyjna (`np.array_equal`),
    transform = bbox; brak `*.part*`.
  - `test_fetch_chunks_cleans_parts_on_fetch_error` (T8): `fetch` rzuca
    `DownloadError` przy 2. kawalku -> ten sam wyjatek, brak `*.part*`,
    brak `output_path`.
  - `test_fetch_chunks_stitch_failure_is_download_error`: `fetch` pisze
    smieci (nie-raster) -> `DownloadError` z "zszyc", brak wyniku.
  - `tests/test_transport_mosaic.py`:
    `test_mixed_source_dtypes_without_dtype_raises` (T9): kafle float32
    i int32 (helper istniejacy w pliku albo `rasterio` w `tmp_path`) ->
    `ValidationError` z `float32` i `int32`, brak pliku wyniku;
    `test_mixed_source_dtypes_with_dtype_casts` (T10): jw. z
    `dtype="float32"` -> wynik `float32`, wartosci int zachowane.
- [ ] **Step 2: implementacja.**
  - `chunks.py`: docstring modulu (konsumenci: CUZK exportImage,
    GUGiK WCS; modul nie zna uslug; kotwica NW — uzasadnienie z docstringu
    `_tile_grid`, ADR-024). `align_bbox`: bez siatki — logika
    `client.py:150-161` (szukaj `NW anchor and an integer pixel count`);
    z siatka — `math.floor((min_x - ox) / step + _GRID_TOL_PX)`,
    `math.ceil((max_x - ox) / step - _GRID_TOL_PX)` (jak `_snap_outward`
    w `mosaic.py`; `_GRID_TOL_PX` importowany z `mosaic.py`, nie
    duplikowany), `width = round((max_x' - min_x') / step)`.
    `plan_chunks`: cialo `_tile_grid` (+ warunek pojedynczego kawalka
    z `client.py:163-167`). `fetch_chunks`: nazwy czesci jak w kliencie
    CUZK (`f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.part{i}.tif"`),
    `mosaic_and_crop(parts, bbox, output_path, nodata=nodata)`, obsluga
    bledow i `finally` jak `client.py:190-220`.
  - `mosaic.py`: w petli metadanych zbierz `src.dtypes[0]`; po petli,
    gdy `dtype is None` i `len(set(dtypes)) > 1` ->
    `ValidationError(f"mosaic_and_crop: zrodla maja rozne typy pasm ({', '.join(sorted(set(dtypes)))}) — podaj dtype=")`.
    Docstring funkcji (akapit `assign_crs`/`dtype`: zdanie o "type from the
    FIRST source" zastapione regula bledu) i docstring modulu (konsumenci:
    `transport/chunks.py` i wycinek PL z arkuszy).
- [ ] **Step 3:** CHANGELOG `### Zmienione`: `mosaic_and_crop` bez
  `dtype=` przy zrodlach roznych typow konczy sie `ValidationError`
  (dotad typ pierwszego zrodla, np. obciecie float do int bez sladu).
- [ ] **Step 4:** brama; commit
  `feat(transport): kawalki zapytan obszarowych i blad mieszanych typow mozaiki`.

### Task 2: CUZK `export_image` na `transport/chunks.py`

**Files:** `kartograf/providers/cuzk/client.py`, `tests/test_cuzk_client.py`.

- [ ] **Step 1: testy** — `tests/test_cuzk_client.py`: usun
  `test_tile_grid_respects_budget_and_covers_request` (przeniesiony w
  Task 1) i import `_tile_grid`; pozostale testy `TestExportImage` BEZ
  zmian w asercjach (patch `download_to` po
  `kartograf.providers.cuzk.client.download_to` — `_export_single` zostaje
  w kliencie, wiec sciezka patcha dziala). Uruchom je przed i po
  refaktorze — oba zielone. PRZED refaktorem pobierz na zywo wynik
  referencyjny CUZK z Task 7 krok 3 (katalog danych od uzytkownika).
- [ ] **Step 2: implementacja** `export_image`:
  ```python
  aligned, width_px, height_px = align_bbox(bbox, pixel_size)
  limits = ChunkLimits(self.MAX_EXPORT_WIDTH, self.MAX_EXPORT_HEIGHT,
                       self.MAX_EXPORT_PIXELS)
  chunks = plan_chunks(aligned, width_px, height_px, pixel_size, limits)
  if len(chunks) > 1 and wkid(aligned.crs) != wkid(image_sr):
      raise ValidationError(...)  # existing message, unchanged
  fetch_chunks(
      chunks, aligned, output_path,
      lambda c, p: self._export_single(endpoint, c.bbox, c.width, c.height,
                                       image_sr, no_data, p),
      nodata=no_data,
  )
  _overwrite_crs(output_path, image_sr)
  ```
  Usun `_tile_grid` i nieuzywane importy (`math`, `threading`, `os` —
  tylko jesli `fetch_file` ich nie potrzebuje; `fetch_file` uzywa
  `os.getpid()`/`threading`). Docstring `export_image`: kawalkowanie
  przez `transport/chunks.py`. Komunikat `DownloadError` zszycia
  pochodzi teraz z `fetch_chunks` — jesli test `match="mozaik"` (szukaj
  w `test_cuzk_client.py`) przestaje pasowac, tresc `fetch_chunks`
  zawiera "mozaik" ("nie udalo sie zszyc N kawalkow mozaiki ...") —
  NIE zmieniaj testu.
- [ ] **Step 3:** brama; commit
  `refactor(cuzk): export_image na wspolnym mechanizmie kawalkow`.
  Bez wpisu CHANGELOG (zachowanie bez zmian).

### Task 3: GUGiK WCS NMT 1 m — siatka zrodla, kawalki, walidacja

**Files:** `kartograf/providers/pl/wcs.py`, `gugik.py`, `gugik_nmpt.py`,
`gugik_orto.py`, `tests/test_gugik_provider.py`, `tests/test_gugik_nmpt.py`,
`tests/test_gugik_orto.py`, `docs/CHANGELOG.md`.

- [ ] **Step 1: testy (czerwone):**
  - `test_gugik_provider.py::test_nmt_download_bbox_requests_on_source_grid`
    (T12, czesc 1): `GugikProvider(resolution="1m", vertical_crs="KRON86")`,
    bbox `450000,550000,450100,550100`, patch `download_to` w
    `kartograf.providers.pl.wcs` (albo tam, gdzie `_download_wcs` go
    importuje) piszacy GeoTIFF zadanego kawalka -> jedno zapytanie,
    `SUBSET=x(449999.50,450100.50)`, `SUBSET=y(549999.50,550100.50)`;
    `validate` przekazany (kwarg niepusty).
  - `test_nmt_download_bbox_chunks_large_area` (T12, czesc 2): patch
    `GugikProvider.WCS_CHUNK_LIMITS = ChunkLimits(100, 100, 10_000)`,
    bbox 150 x 150 m -> 4 zapytania, wszystkie `SUBSET` na liniach
    `k + 0.5`, kawalki rozlaczne, wynik 151 x 151 px zlozony bit w bit
    (wartosci jak w Task 1 T7), brak `*.part*`.
  - `test_nmt_download_bbox_png_single_request_unaligned` (T13): format
    PNG -> jedno zapytanie z bboxem zadania (bez wyrownania).
  - `test_nmt_download_bbox_rejects_exception_report`: odpowiedz
    `Content-Type: text/xml` z `ows:ExceptionReport` -> `DownloadError`,
    brak pliku wyniku (mock `session.get`, nie `download_to`, zeby
    sprawdzic prawdziwy walidator).
  - `test_gugik_nmpt.py::test_nmpt_download_bbox_single_request` i
    `test_gugik_orto.py::test_orto_download_bbox_single_request` (T14):
    jedno zapytanie z bboxem zadania; `validate` przekazany.
  - Istniejace `test_download_bbox_*` w `test_gugik_provider.py`
    pinujace `SUBSET` bboxa calkowitego dla NMT GTiff — popraw na bbox
    wyrownany (spec 4.6: zmiana celowa); testy PNG/JPEG i NMPT/orto bez
    zmian w asercjach URL.
- [ ] **Step 2: implementacja.**
  - `wcs.py`: atrybuty `WCS_GRID: GridSpec | None = None`,
    `WCS_CHUNK_LIMITS = ChunkLimits(max_width=40_000, max_height=40_000,
    max_pixels=16_000_000)` z komentarzem (budzet niezawodnosci: 16 Mpx
    ok. 50 s / 64 MB, 40000 px boku zmierzone, brak limitu do 100 Mpx;
    `docs/research/2026-10-10-wcs-limits/raport.md`). Metoda
    `_download_wcs(self, bbox, output_path, format, timeout,
    description) -> Path` (sesja: `self._sessions.get()`, retries:
    `self.MAX_RETRIES` — oba atrybuty sa w trzech providerach; mypy:
    zadeklaruj w mixinie adnotacje `_sessions: SessionPerThread`,
    `MAX_RETRIES: int`):
    ```python
    validate = reject_error_document("WCS")
    grid = self.WCS_GRID
    if format != "GTiff" or grid is None:
        return download_to(session, self._construct_wcs_url(bbox, format),
                           output_path, timeout=timeout, retries=retries,
                           validate=validate, description=description)
    aligned, w, h = align_bbox(bbox, grid.step, grid)
    chunks = plan_chunks(aligned, w, h, grid.step, self.WCS_CHUNK_LIMITS)
    return fetch_chunks(chunks, aligned, Path(output_path),
        lambda c, p: download_to(session, self._construct_wcs_url(c.bbox, format),
                                 p, timeout=timeout, retries=retries,
                                 validate=validate, description=...),
        nodata=None)
    ```
  - `gugik.py`: `WCS_GRID = GridSpec(step=1.0, origin_x=0.5, origin_y=0.5)`
    z komentarzem (raport pkt 4 i 7: krawedzie `k + 0,5` m w 9 rejonach);
    `download_bbox` po walidacjach wola `_download_wcs`; docstring
    (Notes: wyrownanie na zewnatrz do siatki zrodla, kawalki > 16 Mpx,
    walidacja odpowiedzi).
  - `gugik_nmpt.py`: `WCS_GRID = None` z komentarzem (GTiff NMPT = RGB
    uint8, naprawa w (a); raport pkt 6). `download_bbox` dziedziczony
    z `GugikProvider` (NMPT go nie nadpisuje — stan `4fa4e9c`), wiec
    `WCS_GRID = None` wystarcza, by NMPT szedl jednym zapytaniem.
  - `gugik_orto.py`: `download_bbox` wola `_download_wcs` (siatka
    domyslna `None`).
- [ ] **Step 3:** CHANGELOG `### Zmienione`: NMT 1 m KRON86
  `download_bbox` (GTiff) — zasieg wyrownany na zewnatrz do siatki zrodla
  (`k + 0,5` m, < 1 px), obszar > 16 Mpx pobierany kawalkami i skladany
  bez przeprobkowania; `### Naprawione`: `download_bbox` NMT/NMPT/orto
  nie zapisuje juz raportu bledu WCS (`ows:ExceptionReport`) jako pliku
  rastra; dotad bbox poza siatka zrodla dawal tresc przesunieta o ulamek
  piksela wzgledem georeferencji.
- [ ] **Step 4:** brama; commit
  `feat(gugik): WCS NMT na siatce zrodla, kawalki i walidacja odpowiedzi`.

### Task 4: d2 — warstwa GPKG rozstrzygana raz, `Info:` w CLI

**Files:** `kartograf/core/geometry.py`, `kartograf/cli/download_cmd.py`,
`kartograf/cli/landcover_cmd.py`, `kartograf/cli/soilgrids_cmd.py`,
`kartograf/cli/_parser.py`, `tests/test_geometry.py`, `tests/test_cli.py`
(+ pliki testow CLI landcover/soilgrids — znajdz po `"--geometry"`),
`docs/CHANGELOG.md`.

**Interfejs (spec 3.2):**
```python
@dataclass(frozen=True)
class LayerChoice:
    name: str | None            # None for SHP
    available: tuple[str, ...]  # GPKG feature tables, () for SHP
    defaulted: bool             # True when layer was None and name = available[0]

def resolve_layer(filepath: Path, layer: str | None) -> LayerChoice: ...
```

- [ ] **Step 1: testy (czerwone)** (fixture `gpkg_multi_layer`
  z `tests/test_geometry.py` — przenies do `tests/conftest.py`, jesli
  potrzebny w `test_cli.py`; plik GPKG budowany sqlite jak dzis):
  - `test_geometry.py::test_resolve_layer_defaults_to_first`:
    `resolve_layer(gpkg_multi_layer, None)` -> `name == "layer_a"`,
    `available == ("layer_a", "layer_b")`, `defaulted is True`; z
    `"layer_b"` -> `defaulted is False`; nieznana -> `ValidationError`
    z lista; SHP -> `name is None`, `available == ()`.
  - `test_get_overall_bbox_multi_layer_default_logs_warning` (T19):
    `caplog` na loggerze `kartograf.core.geometry` -> rekord `WARNING`
    z `layer_a` i `layer_b`; z `layer="layer_a"` — brak rekordu.
  - `test_cli.py::test_cli_geometry_multi_layer_info_once` (T17,
    `download`): `--geometry <gpkg_multi_layer> --country pl -o tmp -q`
    z zamockowanym managerem jak `test_download_geometry_with_layer`
    (`:2496-2526`) -> stderr ma DOKLADNIE jedna linie `Info:` z `layer_a`,
    `layer_b`, `--layer`; `find_sheets_for_geometry` dostaje
    `layer="layer_a"`.
  - jw. dla `landcover download --geometry` i `soilgrids hsg --geometry`
    (wzor: istniejace testy tych podkomend z `--geometry`) — jedno
    `Info:`, `get_overall_bbox` z `layer="layer_a"`.
  - `test_cli_geometry_explicit_or_single_layer_no_info` (T18):
    `--layer layer_b`, GPKG z jedna warstwa, SHP -> brak `Info:` o
    warstwie.
  - `test_cli_geometry_unknown_layer_error`: `--layer x` -> `Error:`
    z lista warstw, kod 1 (zachowanie dzisiejsze, teraz z `resolve_layer`).
- [ ] **Step 2: implementacja.**
  - `geometry.py`: `LayerChoice`, `resolve_layer` (SHP po rozszerzeniu
    jak istniejace rozgalezienie w `read_feature_bboxes`; GPKG —
    `sqlite3` + `_get_gpkg_feature_tables` + walidacja jak
    `_resolve_gpkg_layer`; wspolny kod — `_resolve_gpkg_layer` wola
    wspolny helper, bez duplikacji listy bledow). `_resolve_gpkg_layer`:
    `logger.info` -> `logger.warning("GPKG %s has %d layers, using the first '%s' (others: %s); pass layer= to choose", ...)`.
    Docstringi `read_feature_bboxes`/`get_overall_bbox`/
    `find_sheets_for_geometry`/`read_source_crs`: `layer=None` = pierwsza
    warstwa z ostrzezeniem przy wielu.
  - CLI: wspolny helper w `download_cmd.py` (konwencja istniejaca:
    `landcover_cmd.py` importuje z niego `_cli_metadata_cache`)
    `_announce_geometry_layer(args) -> bool`: `choice =
    resolve_layer(Path(args.geometry), args.layer)`; `ValidationError` ->
    `Error:`, `False`; `choice.defaulted and len(choice.available) > 1` ->
    `print(f"Info: {path.name} ma {n} warstw, uzyto pierwszej '{name}' (pozostale: {rest}); inna warstwa: --layer NAZWA", file=sys.stderr)`;
    `args.layer = choice.name`; `True`. Wywolanie RAZ na wejsciu kazdej
    sciezki `--geometry`: `_cmd_download_geometry` (przed rozgalezieniem
    `cz`, po kontroli istnienia pliku — przenies kontrole `exists` przed
    galez `cz`, jesli dzis jej tam brak: sprawdz `_resolve_cz_geometry_bbox`),
    tryb listy (szukaj `find_sheets_for_geometry(` w `download_cmd.py`),
    `landcover_cmd.py` (przed `get_overall_bbox`), `soilgrids_cmd.py`
    (przed `get_overall_bbox`).
  - `_parser.py`: help `--layer` w 3 podkomendach: "Warstwa GPKG
    (domyslnie pierwsza; przy wielu warstwach Info z lista pozostalych)".
- [ ] **Step 3:** CHANGELOG `### Dodane`: `Info:` o domyslnej warstwie
  GPKG z wieloma warstwami (`download`, `landcover download`,
  `soilgrids hsg`); `### Zmienione`: biblioteka — ostrzezenie loggera
  (dotad `info`).
- [ ] **Step 4:** brama; recznie `.venv/bin/kartograf download --help`
  (tekst `--layer`); commit
  `feat(cli): Info o domyslnej warstwie GPKG z wieloma warstwami`.

### Task 5: d1 — `Info:` o mieszanych ukladach wysokosci pod `--country auto`

**Files:** `kartograf/cli/download_cmd.py`, `tests/test_cli.py`,
`docs/CHANGELOG.md`.

- [ ] **Step 1: testy (czerwone)** w `TestAutoSplitBBox`
  (`tests/test_cli.py`, wzor `test_border_bbox_splits_into_both_countries`,
  bbox `_BORDER`):
  - `test_auto_mixed_vertical_crs_info` (T15): bez `--vertical-crs` ->
    stderr: jedna linia `Info:` zawierajaca `EVRF2007`, `Bpv` i
    `--vertical-crs`; oba przeplywy wywolane jak dzis.
  - `test_auto_explicit_evrf2007_no_mixed_info` (T16): `--vertical-crs
    EVRF2007` -> brak tej linii (szukaj po `Bpv`).
  - `test_explicit_country_no_mixed_info`: `--country pl` -> brak.
  - `test_auto_kron86_resolves_pl_no_mixed_info`: `--vertical-crs KRON86`
    -> istniejace `Info: --country auto -> pl`, brak nowej linii.
  - `test_auto_geometry_cross_border_mixed_info`: `--geometry` (GPKG
    z obiektem przez granice — wzor: istniejace testy geometrii pod
    `auto`; jesli brak, patch `_geometry_envelope` na `_BORDER`) ->
    `Info:` jak T15.
- [ ] **Step 2: implementacja** w `_dispatch_area`, w bloku `if auto:`
  po `_print_clipping_info(...)`:
  ```python
  if {"PL", "CZ"} <= parts.keys() and getattr(args, "vertical_crs", None) is None:
      print(
          "Info: --country auto bez --vertical-crs: czesc PL w EVRF2007, "
          "czesc CZ w Bpv (rozne uklady wysokosci, roznica ok. 0,11-0,15 m); "
          "jeden uklad dla obu: --vertical-crs EVRF2007",
          file=sys.stderr,
      )
  ```
  (`parts` ma klucze krajow; po `_pl_only_flags` `auto` jest `False`, gdy
  opcja rozstrzygnela kraj — wtedy blok `if auto:` sie nie wykonuje).
  Docstring `_dispatch_area`: wzmianka o komunikacie. Komentarz: ADR-023
  pkt 4 — prostokaty; komunikat mowi o ukladach czesci, nie o tresci
  (spec 2.3).
- [ ] **Step 3:** CHANGELOG `### Dodane`: `Info:` przy `--country auto`
  dla obszaru PL+CZ bez `--vertical-crs` (PL EVRF2007, CZ Bpv; podpowiedz
  `--vertical-crs EVRF2007`).
- [ ] **Step 4:** brama; commit
  `feat(cli): Info o mieszanych ukladach wysokosci pod --country auto`.

### Task 6: Dokumentacja

**Files:** `docs/DECISIONS.md` (CRLF), `docs/ARCHITECTURE.md`,
`docs/USAGE.md`, `docs/SCOPE.md` (jesli opisuje kawalkowanie CZ / WCS
`download_bbox` / `--layer`), `README.md` (jesli opisuje `--layer` albo
pogranicze), `docs/CHANGELOG.md`.

- [ ] **Step 1:** ADR-034 "Wspolny mechanizm zapytan obszarowych
  (kawalki na siatce zrodla)" wg spec 5: kontekst, decyzje D-U3/D-U5/D-U6,
  regula wyrownania, budzety (GUGiK 16 Mpx, CUZK 4 Mpx), sekwencyjnie,
  ponowienie per kawalek, `dtype` w `mosaic_and_crop`; alternatywy
  odrzucone; skutki; wiersz w indeksie na poczatku pliku; dopisek
  w statusie ADR-023 (kawalkowanie CUZK w `transport/chunks.py`). CRLF
  zachowany.
- [ ] **Step 2:** ARCHITECTURE: 2 (modul `transport/chunks.py`
  w tabeli/drzewie modulow), 4.2 (`download_bbox` WCS: siatka `k + 0,5`,
  kawalki, walidacja; NMPT/orto jedno zapytanie — (a)), 4.5 (CUZK przez
  `transport/chunks.py`), 4.6 (`Info:` d1 — zastepuje zdanie "Bez
  `--vertical-crs` pogranicze daje ..." uzupelnieniem o komunikat),
  miejsce opisu `--geometry`/`--layer` (d2). USAGE (diakrytyki): 1.x
  `--geometry`/`--layer` (Info), 1.4 pogranicze (Info). SCOPE/README —
  tylko jesli opisuja te zachowania (`grep -n "layer\|Bpv\|4 Mpx\|download_bbox"`).
- [ ] **Step 3:** brama; commit
  `docs(transport): ADR-034 i opis kawalkow, Info d1/d2`.

### Task 7: Weryfikacja na zywo, review, PROGRESS

- [ ] **Step 1:** katalog danych od uzytkownika; na zywo (spec 6):
  1. NMT KRON86 `download_bbox` 6 x 6 km (np. od `480000,450000`) ->
     3 kawalki (log), wynik vs jedno zapytanie WCS wyrownanego bboxa
     (skrypt poza repo) — `np.array_equal`; zasieg na `k + 0,5`.
  2. Fragment wyniku vs arkusze OpenData KRON86 1 m (CLI `download
     --bbox ... --vertical-crs KRON86`) — bit w bit (jak raport pkt 4).
  3. CUZK `--country cz` bbox 10 x 10 km 2 m (np. `17.90,49.70,18.04,49.79`
     EPSG:4326, K6 z 2026-09-30): wynik referencyjny pobrany na `develop`
     PRZED Task 2 (osobny `--output`) vs wynik z galezi — identyczne
     piksele (`np.array_equal`) i transform. Uwaga: CUZK serwuje biezaca
     wersje DMR; roznica tresci przy roznicy dat pobrania = najpierw
     ponowic referencje, potem szukac bledu.
  4. CLI `download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326`
     (auto) -> `Info:` d1; z `--vertical-crs EVRF2007` -> brak.
  5. CLI `download --geometry <gpkg 2 warstwy>` -> jedno `Info:` d2.
  Raport `docs/research/<data>-silent-defaults/raport.md` (bez sciezki
  katalogu danych).
- [ ] **Step 2:** review galezi (reviewer) wg "Review Focus"; poprawki
  osobnym commitem.
- [ ] **Step 3:** PROGRESS (sesja, backlog (d) [x] i "Ryzyko KRON86 3"
  [x] po merge), merge `--no-ff` do `develop` po decyzji uzytkownika.
