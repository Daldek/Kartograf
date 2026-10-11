# Wycinki PL z WCS (a) i naprawa NMPT `download_bbox` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wdrozyc w 0.7.2 spec
`docs/superpowers/specs/2026-10-11-wcs-cutouts-design.md` (decyzje
W-U1..W-U11): wycinek PL `--target-crs` (NMT i NMPT, oba uklady, tylko
1 m) z WCS GUGiK na siatce arkuszy 1 m, z maska ladu PRG (`A00 - W02 -
W03`), nazwa z data, bez skip-existing; `download_bbox` NMT EVRF2007
i NMPT zwraca wysokosci float32; API arkuszowe bez zmian (przestarzale
do 0.8.0).

**Architecture:** Jedna warstwa = jedno zadanie = jeden commit na galezi
`feat/wcs-cutouts` z `develop`. Kolejnosc: fixtury (Task 1) -> transport
ASC (Task 2) -> WCS providerow (Task 3) -> maska PRG (Task 4) -> tor
wycinka w bibliotece (Task 5) -> CLI (Task 6) -> dokumentacja (Task 7) ->
weryfikacja na zywo (Task 8) -> brama, review, merge (Task 9).
`transport/aaigrid.py` nie zna uslug; `providers/pl/prg.py` zna PRG, nie
wycinki; `download/cutout.py` sklada tor.

**Tech Stack:** Python 3.12, `pytest` (offline; `conftest` blokuje
gniazda), `rasterio` (`rasterio.features.rasterize`), `numpy`, bez nowych
zaleznosci.

**Spec:** `docs/superpowers/specs/2026-10-11-wcs-cutouts-design.md`.
Pomiary: `docs/research/2026-10-11-wcs-cutouts/raport.md`,
`docs/research/2026-10-10-wcs-limits/raport.md`.

## Global Constraints

- Python wylacznie z `.venv`: `.venv/bin/python -m pytest ...`,
  `.venv/bin/ruff ...`, `.venv/bin/python -m mypy ...`, CLI
  `.venv/bin/kartograf`.
- Brama przed KAZDYM commitem: `.venv/bin/python -m pytest tests/ -m "not live" -q`
  zielone, `.venv/bin/ruff check .` i `.venv/bin/ruff format --check .`
  czyste, `.venv/bin/python -m mypy kartograf/ tests/` bez bledow.
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
  `docs/CHANGELOG.md`, sekcja `## [0.7.2] - Unreleased`
  (`### Dodane` / `### Zmienione` z "Co zrobic" / `### Naprawione`).
- Numery linii = stan `develop` `f670d8b`; po wczesniejszych zadaniach
  przesuwaja sie — szukaj po symbolu.
- Testy offline na SUROWYCH odpowiedziach z Task 1 (nie na recznie
  skladanych imitacjach tam, gdzie liczy sie format serwera); asercje na
  fakty (wartosci pikseli, `SUBSET`, `SCALEFACTOR`, transform, nodata,
  pola sidecara), nie na cale brzmienie komunikatow.
- Testy przypinajace USUWANE zachowanie (CLI wycinka z arkuszy: lista
  arkuszy, R5 `Warning:`, W1 podpowiedz, I-1, skip istniejacego) usuwamy,
  nie przepinamy (STANDARDS 10). Testy API arkuszowego zostaja.
- Dane na zywo (Task 1, Task 8): poza repo i poza `/tmp`, jawne
  `--output`, katalog wskazuje uzytkownik (w tej sesji podany; sciezki nie
  zapisuj w repo); CLI z korzenia repo.

## Review Focus

1. **Siatka arkuszy** — kazde zapytanie wycinka i `download_bbox`
   (GTiff) na `GridSpec(1.0, 0.5, 0.5)`, zakres wyrownany na zewnatrz.
   Test: Task 3 `test_nmpt_download_bbox_on_sheet_grid_with_scalefactor`,
   Task 5 `test_wcs_cutout_2180_corner_on_sheet_grid`; Task 8 krok 2
   (bit w bit z arkuszem).
2. **Bez wyniku przy bledzie** — awaria PRG przed WCS, zly ASC, blad
   kawalka: brak pliku i brak sidecara; poprzedni plik tego samego dnia
   zostaje. Test: Task 2 `test_asc_size_mismatch_raises`, Task 5
   `test_prg_failure_makes_no_wcs_request`,
   `test_failed_rerun_keeps_previous_same_day_file`.
3. **Maska** — morze W02, wody W03, zagranica = -9999; lad, takze 0,0 =
   wartosc serwera. Test: Task 4 `test_mask_on_recorded_coast`.
4. **API bez zlamania** — sygnatury `download_pl_cutout`,
   `prepare_pl_cutout`, `run_pl_cutout`, `PlCutoutResult` tylko
   addytywnie; parametry arkuszowe `DeprecationWarning`. Test: Task 5
   `test_download_pl_cutout_sheet_params_warn`.
5. **ASC kawalek 1 Mpx** — `WCS_CHUNK_LIMITS` wybierane po formacie.
   Test: Task 3 `test_aaigrid_chunk_budget_is_one_mpx`.

---

## Mapa plikow

| Plik | Odpowiedzialnosc | Zadanie |
|---|---|---|
| `tests/fixtures/gugik_wcs/real_2026_10_11/` (nowy), `tests/fixtures/gugik_prg/land_mask_2026_10_11/` (nowy) | surowe odpowiedzi WCS (multipart AAIGrid) i PRG (GML) | 1 |
| `kartograf/transport/aaigrid.py` (nowy) | `extract_multipart_asc`, `asc_to_gtiff`, `save_multipart_asc` (dla `download_to(save=)`) | 2 |
| `kartograf/providers/pl/wcs.py`, `gugik.py`, `gugik_nmpt.py` | `WCS_HEIGHT_FORMAT`, `WCS_NATIVE_STEP`, `SCALEFACTOR`, limity per format, endpoint EVRF2007, NMPT na siatce 1 m | 3 |
| `kartograf/sources/registry.py` | kanal WCS `bbox_raster` NMT (oba uklady), NMPT | 3 |
| `kartograf/providers/pl/prg.py` | `LandMask`, `fetch_land_mask`, `LandMask.apply` | 4 |
| `kartograf/download/cutout.py`, `kartograf/__init__.py` | `PlCutout.product`, `prepare_pl_cutout(product=)`, `run_pl_wcs_cutout`, `write_pl_wcs_cutout_sidecar`, `download_pl_cutout` na WCS, `PlCutoutResult.masked_pixels/zero_pixels` | 5 |
| `kartograf/cli/download_cmd.py`, `kartograf/cli/_parser.py` | `_download_pl_cutout` na WCS, straze (nmpt, 5 m), `--help` | 6 |
| `docs/DECISIONS.md` (CRLF), `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `docs/SCOPE.md`, `docs/PRD.md` | ADR-035, opis | 7 |
| `docs/CHANGELOG.md`, `docs/PROGRESS.md` | wpisy | 3-9 |
| `tests/test_transport_aaigrid.py` (nowy), `tests/test_gugik_provider.py`, `tests/test_gugik_nmpt.py`, `tests/test_prg.py`, `tests/test_pl_cutout.py`, `tests/test_wcs_cutout.py` (nowy), `tests/test_cli.py` | testy | 2-6 |

---

### Task 0: Galaz

- [ ] `git switch develop && git switch -c feat/wcs-cutouts` (spec i raport
  scommitowane na `develop`: `f670d8b`; plan commitowany na `develop`
  przed galezia commitem `docs(plan): wycinki PL z WCS (a)`).

### Task 1: Fixtury z surowych odpowiedzi (na zywo, jednorazowo)

**Files:** `tests/fixtures/gugik_wcs/real_2026_10_11/`,
`tests/fixtures/gugik_prg/land_mask_2026_10_11/`, `README.md` w kazdym
katalogu (skad, kiedy, URL zapytania, siatka) — wzor:
`tests/fixtures/gugik_prg/`.

- [ ] **Step 1: WCS** (skrypt jednorazowy poza repo; zapis CALEJ odpowiedzi
  HTTP: cialo bajt w bajt + `Content-Type` w `*.headers.json`):
  - `nmt_evrf2007_20x20.mime` — `DTM_PL-EVRF2007-NH`, `image/x-aaigrid`,
    `SUBSET` 20 x 20 m na siatce `k + 0,5` w `M-34-64-D-d-2-3`
    (np. x 567580,5-567600,5, y 243664,5-243684,5) + ten sam obszar
    jako 4 kawalki 10 x 10 (`*_q1..q4.mime`) do testu skladania;
  - `nmpt_evrf2007_20x20_sf05.mime` — `DSM_PL-EVRF2007-NH`,
    `SCALEFACTOR=0.5`, ten sam obszar, + 4 kawalki;
  - `nmpt_kron86_20x20_sf05.mime` — `DSM_PL-KRON86-NH` w
    `M-34-2-A-b-4-3` (x 479013,5-479033,5, y 451886,5-451906,5);
  - `exception_report.xml` — zapytanie ze zlym `COVERAGEID` (OGC
    ExceptionReport z HTTP 200, jesli serwer tak odpowiada; inaczej
    pominac i opisac w README).
  - Z tych samych okien wyciac wartosci z arkuszy OpenData (`<out>/sheets/...`
    i `<out>/sheets05/...`, pobrane w pomiarze) do `*_sheet_values.npy` —
    referencja "WCS = arkusz" w testach (male tablice 20 x 20): NMT
    EVRF2007 i NMPT KRON86 — arkusz 1 m; NMPT EVRF2007 w `M-34-64-D-d-2-3`
    (jest tylko lot 0,5 m) — arkusz 0,5 m zdecymowany do pikseli
    o srodkach na pelnych metrach (raport 2026-10-11 pkt 3).
- [ ] **Step 2: PRG** — `A00_Granice_panstwa.xml.gz` (cala odpowiedz
  GetFeature, gzip; ok. 2 MB przed kompresja), `W02_..._bbox_coast.xml`,
  `W03_..._bbox_coast.xml` (okno przybrzezne Gdynia/Hel z `BBOX`, np.
  N 750000-760000, E 470000-490000), `W02_..._bbox_inland.xml` (okno
  w glebi ladu — 0 obiektow). Zapisac uzyte `BBOX` w README.
- [ ] **Step 3: Commit** `test(fixtures): surowe odpowiedzi WCS AAIGrid i PRG
  maski ladu` (bez wpisu CHANGELOG).

### Task 2: `transport/aaigrid.py` — odpowiedz multipart i ASC -> GTiff

**Files:** `kartograf/transport/aaigrid.py` (nowy),
`tests/test_transport_aaigrid.py` (nowy).

**Interfejs (spec 5.2; zamiast zmiany `download_to` — istniejacy hak
`save=`):**
```python
def extract_multipart_asc(src: Path, content_type: str, dst: Path) -> Path:
    """The image/x-aaigrid part of a multipart/related body file -> dst (stream)."""
def asc_to_gtiff(asc: Path, tif: Path, *, expect: Chunk, crs: str = "EPSG:2180") -> Path:
    """ASC -> float32 GTiff with a forced CRS; checks size and corner against expect."""
def save_multipart_asc(expect: Chunk) -> Callable[[requests.Response, Path], Path]:
    """download_to(save=...) hook: stream body to <out>.mime, extract, convert, clean."""
```

- [ ] **Step 1: testy (czerwone)** na fixturach Task 1:
  - `test_extract_and_convert_recorded_nmt_evrf2007`: wynik 20 x 20
    float32, transform (567580,5; 243684,5; 1 m), CRS EPSG:2180, `nodata`
    None, wartosci == `*_sheet_values.npy`.
  - `test_multipart_without_asc_part_raises`: cialo z sama czescia
    `.prj` -> `DownloadError` z poczatkiem tresci; plik wyniku nie
    powstaje.
  - `test_asc_size_mismatch_raises`: `expect` 21 x 20 -> `DownloadError`
    (`ncols`), brak pliku.
  - `test_asc_corner_mismatch_raises`: `expect` przesuniete o 0,25 m ->
    `DownloadError` (`xllcorner`), brak pliku.
  - `test_save_hook_cleans_intermediate_files`: po sukcesie i po bledzie
    w katalogu tylko wynik (sukces) albo nic (blad) — bez `.mime`/`.asc`.
  - `test_boundary_from_quoted_content_type`: `boundary="wcs"` w
    cudzyslowie dziala (naglowek z fixtury przerobiony tylko w tym
    miejscu).
- [ ] **Step 2: implementacja**: strumieniowe szukanie granicy w pliku
  (bufor, bez wczytywania calosci — ASC kawalka do ok. 20 MB, ale
  `download_bbox` bez limitu moze miec setki MB), naglowek czesci do
  pustej linii (CRLF albo LF), cialo do nastepnej granicy. ASC czytane
  `rasterio` (driver AAIGrid) albo parsem naglowka + `numpy.loadtxt`
  — wybor w implementacji; CRS z argumentu (ignoruj `.prj` ESRI),
  tolerancja naroznika `_GRID_TOL_PX` x krok (z `transport/mosaic.py`).
  Zapis wyniku atomowo (`<tif>.<pid>_<tid>.tmp` + `os.replace`).
- [ ] **Step 3: brama, commit** `feat(transport): odpowiedz WCS
  multipart image/x-aaigrid -> GeoTIFF float32` (bez CHANGELOG — modul
  wewnetrzny, zachowanie uzytkownika zmienia Task 3).

### Task 3: WCS providerow — EVRF2007, NMPT wysokosci, siatka arkuszy, limity ASC

**Files:** `kartograf/providers/pl/wcs.py`, `gugik.py`, `gugik_nmpt.py`,
`kartograf/sources/registry.py`, `tests/test_gugik_provider.py`,
`tests/test_gugik_nmpt.py`, testy rejestru (znajdz po `bbox_raster`),
`docs/CHANGELOG.md`.

**Zmiany (spec 3.1-3.4, 5.1):**
- `GugikWcsMixin`: `WCS_HEIGHT_FORMAT: dict[str, str]` (uklad ->
  `"GTiff"` | `"AAIGrid"`), `WCS_NATIVE_STEP: float`,
  `WCS_CHUNK_LIMITS_AAIGRID = ChunkLimits(40_000, 40_000, 1_000_000)`
  (komentarz: raport 2026-10-11 pkt 5 — pierwszy bajt 7 s przy 1 Mpx,
  25 s przy 4 Mpx, timeout odczytu 30 s). `_construct_wcs_url(bbox,
  format, scale=None)`: `FORMAT` z `WCS_FORMATS` albo
  `image/x-aaigrid`, `SCALEFACTOR=<scale>` gdy != 1.
- `_download_wcs(..., format="GTiff")`: gdy `WCS_HEIGHT_FORMAT[uklad] ==
  "AAIGrid"` — zapytanie `image/x-aaigrid`, `save=save_multipart_asc(chunk)`,
  limity `WCS_CHUNK_LIMITS_AAIGRID`; `scale = WCS_NATIVE_STEP /
  WCS_GRID.step`. PNG/JPEG bez zmian.
- `GugikProvider`: `WCS_ENDPOINTS["EVRF2007"] =
  .../NMT/GRID1/WCS/DigitalTerrainModel`, `COVERAGE_IDS["EVRF2007"] =
  "DTM_PL-EVRF2007-NH"`, `WCS_HEIGHT_FORMAT = {"KRON86": "GTiff",
  "EVRF2007": "AAIGrid"}`, `WCS_NATIVE_STEP = 1.0`,
  `WITHDRAWN_WCS_VERTICAL_CRS = ()`; docstringi `download_bbox`
  i `is_wcs_available` bez "outage".
- `GugikNmptProvider`: `WCS_GRID = GridSpec(1.0, 0.5, 0.5)`,
  `WCS_NATIVE_STEP = 0.5`, `WCS_HEIGHT_FORMAT` oba `"AAIGrid"`;
  komentarz o RGB zastapiony odnosnikiem do raportu 2026-10-11 pkt 3.
- Rejestr: `pl.gugik.nmt_1m` kanal WCS `vertical_crs_options =
  _PL_VERTICAL_BOTH`, notatka: "KRON86 GeoTIFF float32, EVRF2007 tylko
  image/x-aaigrid"; `pl.gugik.nmpt` + kanal WCS `bbox_raster` (oba,
  notatka: wysokosci tylko AAIGrid, 1 m przez SCALEFACTOR=0.5).

- [ ] **Step 1: testy (czerwone)** — sesja `Mock` jak w
  `test_gugik_provider.py` (`session.get` zwraca odpowiedz z fixtury
  Task 1: `iter_content` z bajtow, `headers` z `*.headers.json`):
  - `test_evrf2007_download_bbox_aaigrid_on_sheet_grid`: URL
    `DigitalTerrainModel`, `COVERAGEID=DTM_PL-EVRF2007-NH`,
    `FORMAT=image/x-aaigrid`, `SUBSET` na `k + 0,5`, brak `SCALEFACTOR`;
    plik float32 == wartosci arkusza.
  - `test_nmpt_download_bbox_on_sheet_grid_with_scalefactor`:
    `SCALEFACTOR=0.5`, `SUBSET` na `k + 0,5`, wynik 1 pasmo float32
    20 x 20 (dotad RGB uint8).
  - `test_aaigrid_chunk_budget_is_one_mpx`: obszar 2000 x 1000 m EVRF2007
    -> 2 zapytania (sesja zwraca syntetyczne multipart z wartoscia =
    globalna pozycja piksela, jak `test_nmt_download_bbox_chunks_large_area`);
    zlozenie bit w bit; KRON86 ten sam obszar -> 1 zapytanie (16 Mpx).
  - `test_aaigrid_chunks_stitch_bit_exact_recorded`: 4 kawalki z fixtury
    == odpowiedz 20 x 20 (NMT i NMPT ze `SCALEFACTOR`).
  - Usunac `test_download_bbox_evrf2007_raises_validation_error`
    (zachowanie usuniete); `is_wcs_available()` EVRF2007 -> True.
  - Rejestr: kanal WCS NMT ma oba uklady; NMPT ma `bbox_raster`.
- [ ] **Step 2: implementacja** wg "Zmiany".
- [ ] **Step 3: CHANGELOG** `### Naprawione`: NMPT `download_bbox`
  zwracal RGB uint8 zamiast wysokosci — teraz float32 1 m na siatce
  arkuszy; wpis WCS EVRF2007 wskazywal nieistniejacy endpoint.
  `### Zmienione`: `download_bbox` NMT EVRF2007 dziala (dotad
  `ValidationError`); NMPT `download_bbox` 1 m zamiast 0,5 m; EVRF2007
  i NMPT pobierane w kawalkach 1 Mpx (ok. 20 s/Mpx) — "Co zrobic": nic;
  kto lapal `ValidationError` EVRF2007, moze usunac obejscie.
- [ ] **Step 4: brama, commit** `fix(wcs): wysokosci NMPT i NMT EVRF2007
  z image/x-aaigrid na siatce arkuszy`.

### Task 4: Maska ladu PL z PRG

**Files:** `kartograf/providers/pl/prg.py`, `tests/test_prg.py`.

**Interfejs (spec 6.1):**
```python
@dataclass(frozen=True)
class LandMask:
    country: tuple[dict, ...]   # GeoJSON geometries of A00 (E,N)
    water: tuple[dict, ...]     # W02 + W03 geometries intersecting the area
    def apply(self, path: Path, nodata: float) -> tuple[int, int]:
        """In-place: pixels outside land -> nodata. Returns (masked, zero_on_land)."""

def fetch_land_mask(area: BBox, *, session=None, timeout: int = 30) -> LandMask: ...
```

- [ ] **Step 1: testy (czerwone)** na fixturach Task 1 (sesja `Mock`
  wybierajaca odpowiedz po `TYPENAMES`):
  - `test_gml_axis_order_swapped`: pierwszy wierzcholek A00 z fixtury
    (N,E) trafia do GeoJSON jako (E,N).
  - `test_mask_on_recorded_coast`: raster 2180 1 m w oknie
    przybrzeznym (siatka `k + 0,5`, wartosci 0,0 i 5,0): piksele
    w punktach kontrolnych z raportu pkt 6 (Gdynia lad / 300 m w morze,
    Hel Zatoka Pucka) -> lad zachowany (takze 0,0), woda -9999;
    zwrocone liczniki zgadzaja sie z tablica.
  - `test_inland_area_skips_empty_water_layers`: W02/W03 z 0 obiektami
    -> `water == ()`, bez bledu.
  - `test_a00_missing_raises`: A00 z 0 obiektami -> `DownloadError`.
  - `test_service_error_raises`: `ows:ExceptionReport` -> `DownloadError`.
  - `test_pixel_center_rule`: piksel przeciety granica — o
    przynaleznosci decyduje srodek (`all_touched=False`).
- [ ] **Step 2: implementacja**: zapytania przez `download_to`/wspolny
  helper GET jak `_query` w `prg.py` (ponowienia, walidacja
  `FeatureCollection`, `numberReturned`); A00 bez `BBOX`, W02/W03 z
  `BBOX` obszaru (N,E, `urn:ogc:def:crs:EPSG::2180`, jak powiaty);
  parsowanie `gml:Polygon`/`gml:MultiSurface` (`exterior`/`interior`,
  `posList`); `apply`: `rasterize([(g, 1) for g in country],
  fill=0)`, potem `rasterize(water, default_value=0)` na tym samym
  ksztalcie; zapis w miejscu przez rasterio `r+`.
- [ ] **Step 3: brama, commit** `feat(prg): maska ladu PL (A00 minus morze
  terytorialne i wody wewnetrzne)` (bez CHANGELOG — uzyta w Task 5).

### Task 5: Tor wycinka WCS w bibliotece

**Files:** `kartograf/download/cutout.py`, `kartograf/__init__.py`,
`tests/test_wcs_cutout.py` (nowy), `tests/test_pl_cutout.py`
(`TestLibraryApi` — tylko testy `download_pl_cutout`),
`docs/CHANGELOG.md`.

**Interfejs (spec 4.1-4.5):**
```python
@dataclass(frozen=True)
class PlCutout: ...; product: str = "nmt"          # new field, last
@dataclass(frozen=True)
class PlCutoutResult: ...; masked_pixels: int = 0; zero_pixels: int = 0

def prepare_pl_cutout(bbox, target_crs, *, output_dir="./data", resolution="1m",
                      vertical_crs="EVRF2007", product: str = "nmt") -> PlCutout
def run_pl_wcs_cutout(cutout: PlCutout, *, provider=None,
                      parent_request: dict | None = None,
                      today: date | None = None) -> PlCutoutResult
def download_pl_cutout(..., product: str = "nmt") -> PlCutoutResult   # WCS
```

- [ ] **Step 1: testy (czerwone)** — `tests/test_wcs_cutout.py`; provider
  z sesja `Mock` (WCS z fixtur Task 1), `fetch_land_mask` podmieniony na
  `LandMask` z fixtur PRG albo na prostokat (test nie o masce):
  - `test_wcs_cutout_2180_corner_on_sheet_grid`: bbox `(567580.6,
    243664.7, 567600.4, 243684.3)` -> zapytanie i plik na
    `567580.5-567600.5 x 243664.5-243684.5` (okno fixtury), zakres
    zawiera bbox, wartosci == arkusz (fixtura).
  - `test_wcs_cutout_5514_uses_pinned_warp`: wycinek 5514 — wywolanie
    `warp_to_grid` z obszarem zrodlowym wyrownanym do `k + 0,5`
    (patch jak w `TestBuildPlCutout`), sidecar `transform.horizontal`
    `pinned: ...`.
  - `test_name_carries_download_date`: `today=date(2026, 10, 11)` ->
    `<wsp>_20261011.tif` w `nmt/pl_1992_1m_evrf2007/bbox/`; NMPT ->
    `nmpt/pl_1992_1m_<v>/bbox/`.
  - `test_every_run_downloads`: drugi bieg tego samego dnia -> ponowne
    zapytania WCS, plik zastapiony; `skipped is False`.
  - `test_failed_rerun_keeps_previous_same_day_file`: drugi bieg z bledem
    WCS -> `DownloadError`, poprzedni plik i sidecar bajt w bajt bez
    zmian.
  - `test_prg_failure_makes_no_wcs_request`: `fetch_land_mask` rzuca
    `DownloadError` -> zero zapytan WCS, brak pliku i katalogu `bbox/`.
  - `test_mask_counts_and_sidecar`: `masked_pixels`, `zero_pixels`
    w wyniku i w sidecarze (`extra.mask.masked_pixels`,
    `extra.zero_pixels` tylko gdy > 0); `capability="bbox_raster"`,
    `extra.source = {service, endpoint, coverage, format, composition:
    "server"}`, `nodata=-9999`; brak `sheet_sources`/`missing_sheets`.
  - `test_all_outside_land_is_all_nodata`: maska bez ladu ->
    `all_nodata=True`, plik powstaje.
  - `test_5m_rejected_before_network`: `prepare_pl_cutout(resolution=
    "5m")` + `run_pl_wcs_cutout` / `download_pl_cutout(resolution="5m")`
    -> `ValidationError` z podpowiedzia arkuszy; zero zapytan.
  - `test_download_pl_cutout_sheet_params_warn`: `scale="1:5000"`,
    `max_workers=4`, `geometry=...`, `force=True`, `cache=...`,
    `on_progress=...`, `layer=...` -> `DeprecationWarning` z nazwa
    parametru; wartosci domyslne -> brak ostrzezenia.
  - `test_run_pl_cutout_rejects_nmpt`: `run_pl_cutout` z
    `cutout.product="nmpt"` -> `ValidationError`.
  - `test_provider_mismatch_rejected`: provider NMT dla wycinka NMPT
    (albo inny uklad) -> `ValidationError` przed siecia.
  - Testy `TestLibraryApi` dla `download_pl_cutout` przypinajace tor
    arkuszowy (arkusze, `missing_sheets`, `skipped`) — usunac; testy
    `prepare/select/run_pl_cutout` i `build_cutout_from_sheets` bez zmian.
- [ ] **Step 2: implementacja**:
  - `prepare_pl_cutout(product=)`: walidacja `product in ("nmt",
    "nmpt")`; deskryptor `pl.gugik.nmpt` dla NMPT; `target_path` bez
    daty (tor arkuszowy bez zmian).
  - `run_pl_wcs_cutout`: `resolution != "1m"` -> `ValidationError`;
    provider domyslny: `create_nmt_provider(vertical_crs, "1m")` albo
    `GugikNmptProvider(vertical_crs)`; `path = dated(cutout.target_path,
    today or date.today())`; kontrola miejsca (2 x `estimated_bytes`);
    `fetch_land_mask(bbox_source_2180)` -> `provider._download_wcs(
    bbox_source_2180, tmp_2180, "GTiff", ...)` -> `mask.apply(tmp,
    PL_NODATA)` (po `apply` nodata zapisane w profilu) -> 2180:
    `os.replace(tmp, path)`; inne: `warp_to_grid(tmp, path, bbox_target,
    1.0, pinned, src_crs="EPSG:2180", nodata=PL_NODATA)`; `finally` usuwa
    `tmp`; `prune_empty_dirs` po bledzie (jak `run_pl_cutout`);
    `has_valid_pixels` -> `all_nodata`; sidecar
    `write_pl_wcs_cutout_sidecar`.
  - `download_pl_cutout`: ostrzezenia parametrow arkuszowych
    (`warnings.warn(..., DeprecationWarning, stacklevel=2)`), potem
    `prepare_pl_cutout(product=)` -> `run_pl_wcs_cutout`. Docstring:
    zrodlo WCS, kompozycja serwera (spec 6.3), arkusze 5 m przez API
    arkuszowe.
  - `run_pl_cutout`/`select_pl_cutout_sheets`/`build_cutout_from_sheets`:
    docstring "Deprecated since 0.7.2 (sheet-based cutout; removed in
    0.8.0) — use download_pl_cutout / run_pl_wcs_cutout", bez ostrzezen
    w runtime (zachowanie bez zmian, W-U6).
  - `__init__.py`: `run_pl_wcs_cutout` w `__all__`.
- [ ] **Step 3: CHANGELOG** `### Dodane`: `run_pl_wcs_cutout`,
  `product=` w `prepare_pl_cutout`/`download_pl_cutout` (NMPT),
  `PlCutoutResult.masked_pixels/zero_pixels`. `### Zmienione`:
  `download_pl_cutout` pobiera z WCS (siatka arkuszy 1 m, maska ladu,
  nazwa z data, bez skip, 5 m = `ValidationError`, parametry arkuszowe
  `DeprecationWarning`) — "Co zrobic": wycinek z arkuszy (najnowszy lot
  ADR-028, 5 m) przez `prepare_pl_cutout` -> `select_pl_cutout_sheets`
  -> `run_pl_cutout`; nie podawaj parametrow arkuszowych.
- [ ] **Step 4: brama, commit** `feat(cutout): wycinek PL z WCS GUGiK
  z maska ladu PRG (biblioteka)`.

### Task 6: CLI

**Files:** `kartograf/cli/download_cmd.py`, `kartograf/cli/_parser.py`,
`tests/test_pl_cutout.py` (testy CLI), `tests/test_cli.py`,
`docs/CHANGELOG.md`.

- [ ] **Step 1: inwentaryzacja testow CLI wycinka** — w
  `tests/test_pl_cutout.py` testy wolajace `main`/`cmd_download`
  z `--target-crs` (m.in. `TestDownloadPlBboxCutout`,
  `TestGeometryCutout::test_cli_geometry_target_crs_reaches_worker`,
  `TestBorderTwoCutouts`, `TestTargetCrsValidations`,
  `TestOffGridSheets::test_cli_*`, `TestMissingSheets` (CLI),
  `TestUnverifiedSheets::test_cli_*`, `TestEmptyCutoutSkip`,
  `TestPartialSheetVisibility` (CLI)). Podzial w opisie commita:
  (a) usuwane — przypinaja zachowanie toru arkuszowego w CLI (lista
  arkuszy, R5 `Warning:`, W1 podpowiedz, I-1, skip istniejacego, E13);
  (b) przepinane na tor WCS — zachowanie, ktore zostaje (dwa wycinki
  pod `--country auto`, walidacje `--target-crs`, `--geometry` ->
  obwiednia, kod 1 bez tracebacka, `all_nodata` `Warning:` kod 0).
- [ ] **Step 2: testy (czerwone)** — `tests/test_wcs_cutout.py`
  (klasa `TestCli`; `run_pl_wcs_cutout` albo provider z sesja `Mock`):
  - `test_cli_nmpt_target_crs_allowed`: `--product nmpt --target-crs
    EPSG:2180` -> kod 0, plik `nmpt/.../bbox/<wsp>_<data>.tif`.
  - `test_cli_5m_target_crs_rejected_before_network`: kod 1, stderr
    zawiera `--target-crs`, `1m`; zero zapytan.
  - `test_cli_orto_target_crs_still_rejected`: kod 1.
  - `test_cli_force_has_no_effect_and_no_message`: `--force` -> to samo
    co bez; brak dodatkowego komunikatu.
  - `test_cli_wcs_error_code_1_no_traceback`: blad WCS -> kod 1,
    `Error:`; pod `--country auto` z udanym CZ -> kod 0 + `Warning:`.
  - `test_cli_all_nodata_warning_code_0`.
  - `test_cli_no_zero_pixels_info`: `zero_pixels > 0` -> brak `Info:`
    o 0,0 (W-U11).
  - `test_cli_auto_two_cutouts_shared_parent` (przepiety z
    `TestBorderTwoCutouts`).
- [ ] **Step 3: implementacja**: `_resolve_pl_sentinels` — `--target-crs`
  z `nmpt` dozwolone (`orto`/`laz` — `Error:` z nowa trescia bez
  "0.7.0/etap 2"), `--resolution 5m --target-crs` -> `Error:` (spec
  4.3); `_download_pl_cutout`: `prepare_pl_cutout(product=)` (bledy jak
  dzis) -> `Info:` o rozmiarze (gdy >= 1 GiB, jak dzis) i liczbie
  kawalkow -> `run_pl_wcs_cutout(parent_request=)` -> `_report_pl_cutout`
  okrojony do `all_nodata` (funkcje i komunikaty R5/W1/E13/I-1 dla
  wycinka usuniete, jesli nie maja innych wolajacych — sprawdz
  referencje) -> `Downloaded to`. `--workers`, `--scale` nie
  wplywaja na wycinek. `--help` `--target-crs`: "wycinek 1 m z WCS
  GUGiK (NMT, NMPT), maska ladu PL, nazwa z data".
- [ ] **Step 4: CHANGELOG** `### Zmienione` (CLI): wycinek `--target-crs`
  z WCS, nazwa `<wsp>_<RRRRMMDD>.tif`, kazde uruchomienie pobiera,
  `--resolution 5m --target-crs` = `Error:`, nodata poza ladem PL;
  `### Dodane`: `--product nmpt --target-crs`. "Co zrobic": wycinek 5 m
  albo najnowszy lot arkuszy — pobierz arkusze (bez `--target-crs`);
  skrypty szukajace pliku po nazwie bez daty — dopasuj wzorzec.
- [ ] **Step 5: brama, commit** `feat(cli): wycinek --target-crs z WCS
  GUGiK, NMPT, nazwa z data`.

### Task 7: Dokumentacja i ADR-035

**Files:** `docs/DECISIONS.md` (CRLF), `docs/ARCHITECTURE.md`,
`docs/USAGE.md`, `docs/SCOPE.md`, `docs/PRD.md`, `docs/PROGRESS.md`.

- [ ] **Step 1: ADR-035** (spec 7): kontekst (raporty WCS 2026-10-10
  i 2026-10-11), opcje (arkusze; WCS bez maski; WCS + 0,0 -> nodata;
  WCS + maska PRG — przyjete), decyzja (W-U1..W-U11: siatka arkuszy
  1 m, tylko 1 m, maska `A00 - W02 - W03`, 0,0 na ladzie zostaje, nazwa
  z data, bez skip, kawalek ASC 1 Mpx), konsekwencje (kompozycja
  serwera != ADR-028; API arkuszowe do 0.8.0). Indeks na poczatku pliku.
  ADR-027: status "czesciowo zastapiona przez ADR-035 (zrodlo wycinka
  w CLI i `download_pl_cutout`); API arkuszowe do 0.8.0". Sprawdz
  `git diff --stat` (CRLF).
- [ ] **Step 2: ARCHITECTURE** 4.3 (przepisany: tor WCS, siatka, maska,
  sidecar, nazwa), 4.2 (`download_bbox` EVRF2007/NMPT, AAIGrid, limity
  per format), 3.1 (rejestr), 3.2 (pola sidecara wycinka WCS), 2
  (`transport/aaigrid.py`, maska w `prg.py`); USAGE (wycinki: przyklady
  NMT/NMPT, data w nazwie, kompozycja serwera — wycinek moze miec inny
  lot niz arkusze, maska ladu, 0,0 na ladzie, arkusze 5 m bez
  `--target-crs`); SCOPE 2 (ograniczenia wycinkow); PRD 3.11.
- [ ] **Step 3: PROGRESS**: backlog "Do 0.8.0" — usuniecie API
  arkuszowego wycinka, parametrow arkuszowych `download_pl_cutout`
  i `snap_to_source_grid`/`assign_crs` w `mosaic_and_crop`; pozycja
  "NMPT `download_bbox`" odhaczona.
- [ ] **Step 4: commit** `docs: ADR-035 wycinki PL z WCS, opis toru`.

### Task 8: Weryfikacja na zywo

**Raport:** `docs/research/2026-10-1x-wcs-cutouts-live/raport.md`
(data wykonania w nazwie). Katalog danych: wskazany przez uzytkownika.

- [ ] **Step 1**: `download --bbox <okno 1 km w M-34-64-D-d-2-3>
  --country pl --target-crs EPSG:2180 --output <out>` (NMT EVRF2007),
  to samo `--vertical-crs KRON86` w `M-34-2-A-b-4-3`, `--product nmpt`
  (EVRF2007 i KRON86): kod 0, nazwa z data, sidecar.
- [ ] **Step 2**: porownanie piksel w piksel z arkuszami 1 m tego samego
  lotu (pobranymi CLI) — oczekiwane 100 % na pikselach waznych; NMPT
  w obszarze lotu 0,5 m — z arkuszem 0,5 m zdecymowanym (raport
  2026-10-11 pkt 3).
- [ ] **Step 3**: wycinek > 1 Mpx EVRF2007 (kawalki ASC) i NMPT —
  wynik == jedno zapytanie (bit w bit); czas.
- [ ] **Step 4**: wybrzeze (Gdynia/Hel, Mierzeja Wislana): linia maski
  wzgledem pikseli NMT (ile pikseli ladu NMT > 0 wpada w nodata, ile 0,0
  morza zostaje jako lad) — fakt do ADR-035/USAGE.
- [ ] **Step 5**: `--target-crs EPSG:5514` (pinned warp), `--country auto`
  PL+CZ (dwa wycinki), `M-33-57-C-b-4-2` przy granicy (zagranica =
  nodata, `masked_pixels`).
- [ ] **Step 6**: `download_bbox` NMPT/EVRF2007 z biblioteki — 1 pasmo
  float32.
- [ ] **Step 7**: commit raportu `docs(research): weryfikacja na zywo
  wycinkow PL z WCS`.

### Task 9: Brama, review, merge

- [ ] **Step 1**: brama (pytest offline, ruff check/format, mypy).
- [ ] **Step 2**: audyt dokumentacji wzgledem kodu galezi (CHANGELOG,
  USAGE, ARCHITECTURE, ADR-035, docstringi `download_pl_cutout`
  i API arkuszowego).
- [ ] **Step 3**: review galezi (reviewer), poprawki.
- [ ] **Step 4**: PROGRESS — backlog "Do 0.7.2" (a) i NMPT odhaczone,
  wpis sesji.
- [ ] **Step 5**: merge `--no-ff` `feat/wcs-cutouts` -> `develop` po
  zgodzie uzytkownika, usuniecie galezi.
