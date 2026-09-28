# Zad. 12 — Obwiednia geometrii w ukladzie czeskim przez operacje przypieta (zn. 4)

## Co zrobiono

1. Dodano `_geometry_envelope(filepath: Path, layer: str | None) -> BBox` w
   `kartograf/cli/download_cmd.py` (miedzy `_resolve_cz_geometry_bbox` a
   `cmd_download`), dokladnie wg brief-u: czyta `read_source_crs(filepath,
   layer=layer)`; jesli `str(epsg) in _CZ_CRS_WKIDS` (5514/3045), liczy
   obwiednie **w ukladzie pliku** (`get_overall_bbox(..., target_crs=
   source_crs.to_wkt())` — identycznosc, zero transformacji) i etykietuje ja
   `f"EPSG:{epsg}"` (nie WKT — `wkid()` w `_country_bbox` musi rozpoznac kod);
   w przeciwnym razie — jak dotad, wprost `target_crs="EPSG:2180"`.
2. `_cmd_download_geometry`: `overall = get_overall_bbox(filepath, layer=...,
   target_crs="EPSG:2180")` zastapione `overall = _geometry_envelope(filepath,
   getattr(args, "layer", None))`, ten sam `try/except ValidationError`.
   Usuniety nieuzywany juz lokalny import `get_overall_bbox` w tej funkcji
   (zostal w `_geometry_envelope` i w `_resolve_cz_geometry_bbox`/
   `_resolve_laz_bbox`, gdzie byl juz wczesniej). Docstring `_cmd_download_geometry`
   zaktualizowany o zdanie o obwiedni w ukladzie pliku dla CRS czeskich.
3. Nowy test RED w `tests/test_cli.py::TestCountryDispatch` (dokladnie wg
   brief-u, dodany po `test_bbox_auto_stays_pl`):
   `test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl`.
4. Patch `read_source_crs` (P-03) na dokladnie 10 testach z brief-u — patrz
   sekcja "Testy" nizej.
5. CHANGELOG (`### Fixed`, przed `### Tests`, sekcja `[0.7.0] - Unreleased`).

## RED (Step 2 brief-u)

Przed implementacja, tylko nowy test:

```
.venv/bin/python -m pytest "tests/test_cli.py::TestCountryDispatch::test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl" -q
```
```
FAILED ... assert (got.min_x, got.min_y, got.max_x, got.max_y) == pytest.approx(...)
  Max absolute difference: 1.1554660703986883
  Index | Obtained           | Expected
  0     | 472811.52915002144 | 472811.57101757696 ± 1.0e-06
  1     | 208336.31373345293 | 208337.45247657038 ± 1.0e-06
  2     | 473883.87887519307 | 473883.93744563806 ± 1.0e-06
  3     | 209408.66343993135 | 209409.81890600175 ± 1.0e-06
1 failed in 0.78s
```

**Warunek sensownosci** (brief, Step 1): roznica default vs pinned na
`_write_krovak_shp` zmierzona PRZED implementacja (skrypt jednorazowy,
`get_overall_bbox(shp, target_crs="EPSG:2180")` vs
`bbox_to_crs(BBox(-447000,-1114000,-446000,-1113000,"EPSG:5514"),"EPSG:2180")`):

```
dx min -0.04186755552655086   dx max -0.05857044499134645
dy min -1.1387431174516678    dy max -1.1554660703986883
```

Zgodne co do wartosci z liczbami z brief-u/controller notes (dx -0.04/-0.06 m,
dy -1.14/-1.16 m) i >> 0,01 m — test odroznia obie sciezki.

Po implementacji ten sam test: **1 passed in 0.36s** (GREEN).

## Testy zepsute przez `read_source_crs` na plikach-atrapach (P-03)

Przed patchem produkcyjnym (z samym nowym testem + implementacja, BEZ
patchowania tych 10) `pytest tests/test_cli.py tests/test_pl_cutout.py -q`
dawalo dokladnie: **10 failed, 307 passed** — identyczna lista jak w briefie:

```
FAILED tests/test_cli.py::TestAreaModeHierarchyExitCode::test_geometry_coarse_scale_failure_returns_exit_1
FAILED tests/test_cli.py::TestCmdDownloadGeometry::test_download_geometry_basic
FAILED tests/test_cli.py::TestCmdDownloadGeometry::test_download_geometry_with_layer
FAILED tests/test_cli.py::TestCmdDownloadGeometry::test_geometry_workers_1_sequential_collects_all_paths
FAILED tests/test_cli.py::TestDownloadGeometrySystem::test_download_geometry_system_2000
FAILED tests/test_cli.py::TestDownloadGeometrySystem::test_download_geometry_default_system_1992
FAILED tests/test_cli.py::TestAutoSplitGeometry::test_geometry_border_splits
FAILED tests/test_cli.py::TestAutoSplitGeometry::test_geometry_pl_only_skips_cz
FAILED tests/test_cli.py::TestAutoSplitGeometry::test_geometry_outside_known_countries
FAILED tests/test_pl_cutout.py::TestGeometryCutout::test_cli_geometry_target_crs_reaches_worker
```
Bledy dokladnie jak przewidziane: `ValidationError: Missing .prj file...` dla
`.shp`-atrap (`touch()`), `sqlite3.OperationalError: no such table:
gpkg_contents` / `DatabaseError: file is not a database` dla `.gpkg`-atrap
(`touch()`/`write_bytes(b"stub")`).

Kazdemu z 10 dodano (per test, nie class-level) dekorator/context-manager
`patch("kartograf.core.geometry.read_source_crs", return_value=CRS.from_epsg(2180))`
— przez CO EPSG:2180 nie jest w `_CZ_CRS_WKIDS`, wiec `_geometry_envelope`
idzie sciezka `else` (identyczna z kodem sprzed zmiany: `get_overall_bbox(...,
target_crs="EPSG:2180")`, patchowanym przez te testy jak dotad).
Dodano `from pyproj import CRS` na gorze `tests/test_cli.py` (brakowalo);
w `tests/test_pl_cutout.py` lokalny `from pyproj import CRS` w samym tescie
(konwencja pliku — pozostale uzycia `CRS` w tym pliku tez sa lokalne).

Po patchu: `pytest tests/test_cli.py tests/test_pl_cutout.py -q -m "not live"`
→ **317 passed** (wszystkie 10 + reszta pliku).

## GREEN — pelna suita

```
.venv/bin/python -m pytest tests/ -q -m "not live"
```
```
===================== 1842 passed, 8 deselected in 28.32s ======================
```
(baseline 1841 + 1 nowy test = 1842; 0 failed). Powtorzone jeszcze raz PO
mutacji/przywroceniu (patrz nizej) — **1842 passed, 8 deselected** ponownie.

## Ruff / mypy

- `ruff check kartograf/ tests/` — najpierw 4x E501 (linie z brief-u/z mojego
  dopisania parametrow mock nie mieszcily sie w 88 znakach — zgodnie z ostrzezeniem
  w IMPLEMENTER_COMMON.md pkt 1/3, "kod z planu nie zawsze jest ruff-clean").
  Naprawione przez `ruff format kartograf/ tests/` (1 plik przeformatowany:
  `tests/test_cli.py`, zawinal dlugie sygnatury funkcji). Po tym:
  `ruff check` → **All checks passed!**, `ruff format --check` → **87 files
  already formatted**.
- `mypy kartograf/` → **32 bledy w 9 plikach** (bez zmian co do liczby).
  Diff listy (`sed -E 's/:[0-9]+: /: /' | sort`) wobec
  `.superpowers/sdd/.../mypy-baseline.txt` ograniczony do linii `error:`:
  **identyczny** (`diff` pusty, exit 0). Surowy `diff` (bez filtra do samych
  `error:`) pokazywal 3 dodatkowe linie `note: ... annotation-unchecked` w
  `kartograf/auth/proxy.py` — **zweryfikowane jako preexisting i niezwiazane
  z tym zadaniem**: `git stash` (zapisujac niezacommitowanej-juz-wtedy pracy
  nie dotyczylo, commit byl juz zlozony — stash byl uzyty tylko dla porownania
  czystego `develop` HEAD `97a5bb4` bez zadnych zmian Zad. 12) →
  `mypy kartograf/` na czystym HEAD → te same 3 `note:` linie w
  `auth/proxy.py` (plik nietkniety przez to zadanie) → `git stash pop`
  przywrocilo prace. Baseline najwyrazniej zostal przechwycony bez linii
  `note:` (tylko `error:`); liczba faktycznych bledow (`Found 32 errors`)
  jest identyczna przed i po.

## Dowod mutacyjny (Step 6 brief-u, wykonany PO commicie wg reguly 4
IMPLEMENTER_COMMON.md)

Mutacja (dokladnie jak w briefie: `_geometry_envelope` "zawsze zwraca
`get_overall_bbox(..., "EPSG:2180")`"): w `kartograf/cli/download_cmd.py`
zmieniono warunek galezi czeskiej na zawsze-falszywy:

```python
    if False and epsg is not None and str(epsg) in _CZ_CRS_WKIDS:  # MUTATION-TEST
```

Komenda:
```
.venv/bin/python -m pytest "tests/test_cli.py::TestCountryDispatch::test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl" -q
```
Wynik — **FAIL** (identyczne mismatche jak w RED przed implementacja):
```
E   assert (472811.52915...8.66343993135) == approx((47281...75 ± 1.0e-06))
E     Max absolute difference: 1.1554660703986883
FAILED tests/test_cli.py::TestCountryDispatch::test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl
1 failed in 0.77s
```
Przywrocenie: `git checkout -- kartograf/cli/download_cmd.py` (bezpieczne —
zadanie juz zacommitowane jako `4cf6ab9`) → `git status --short` pusty.
Ponowny focused test → **1 passed in 0.36s** (PASS). Pelna suita ponownie
**1842 passed, 8 deselected**. `git status --short` czysty poza `.superpowers/`
(nieplikowany w repo).

## Zmierzone liczby, o ktore prosi brief

- Roznica default-vs-pinned na `_write_krovak_shp`: dx -0.0419/-0.0586 m,
  dy -1.1387/-1.1555 m (>> 0,01 m — test odroznia sciezki). Zgodne z
  controller notes.
- Baseline testow offline: 1841 (potwierdzone przed zadaniem) → 1842 po
  (+1 nowy test).
- mypy: 32 bledy przed i po (identyczna lista `error:`).

## Pliki

- `kartograf/cli/download_cmd.py` — `_geometry_envelope` (nowa funkcja),
  `_cmd_download_geometry` (wywolanie + docstring), usuniety nieuzywany
  lokalny import.
- `tests/test_cli.py` — `from pyproj import CRS` (top-level), nowy test
  `TestCountryDispatch::test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl`,
  patch `read_source_crs` na 9 istniejacych testach (lista w brief-u minus
  ten z `test_pl_cutout.py`).
- `tests/test_pl_cutout.py` — patch `read_source_crs` (+ lokalny import
  `CRS`) na `TestGeometryCutout::test_cli_geometry_target_crs_reaches_worker`.
- `docs/CHANGELOG.md` — wpis `### Fixed` w `[0.7.0] - Unreleased`.

## Commit

`4cf6ab9` — `fix(cli): obwiednia geometrii w ukladzie czeskim opuszcza Krovaka przypieta operacja`
(4 files changed, 121 insertions(+), 17 deletions(-)).

## Samoocena i watpliwosci

- Implementacja i testy sa doslownie wg brief-u (kod, sygnatury, tresc testu
  RED) — nie znalazlem rozbieznosci miedzy brief-em a kodem zastanym.
- Jedyne odejscie od "kopiuj-wklej" to zawijanie linii > 88 znakow (ruff
  format), przewidziane przez IMPLEMENTER_COMMON.md pkt 1/3 jako normalne.
- `parent_request.bbox_crs` dla `--geometry` w ukladzie czeskim z
  `--country pl|auto` niesie teraz uklad PLIKU (np. `EPSG:5514`), nie
  `EPSG:2180` jak dotad milczaco (bo sciezka byla zepsuta/nieprzetestowana).
  Sprawdzilem: **zaden** istniejacy test nie zakladal `EPSG:2180` dla tej
  konkretnej kombinacji (geometry + CRS czeski + `--country pl`/`auto`) —
  jedyne testy assertujace `parent["bbox_crs"] == "EPSG:5514"` to albo
  `--bbox` w ukladzie czeskim (juz przypieta operacja sprzed tego zadania),
  albo `--geometry --country cz` (inna galaz kodu, `_resolve_cz_geometry_bbox`,
  nietkniete). To zachowanie bylo wczesniej NIEOSIAGALNE z poprawnym wynikiem
  (bug), wiec nie ma tu regresji zalozenia — tylko nowa, poprawna sciezka.
- Nie testowalem osobno galezi `epsg is None` (CRS bez rozpoznawalnego kodu
  EPSG) — brief jej nie wymagal, a zachowanie (fallback do `else`, jak dotad)
  jest identyczne z istniejacym kodem sprzed zmiany dla takiego przypadku.
- `.superpowers/` nie zostal zacommitowany (zgodnie z zasada 8 IMPLEMENTER_COMMON.md).
