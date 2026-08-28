# Uklad data/ per produkt + --target-crs dla PL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nowy uklad `data/<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/...`
(szablony `{uklad}`/`{vcrs}` w deskryptorach) oraz `--target-crs` dla PL
w trybie bbox/geometry (jeden scalony wycinek: mozaika + crop + pinned warp),
z kompletem dokumentacji (nowy `docs/ARCHITECTURE.md`, ADR-026/027).

**Architecture:** `SourceDescriptor.storage_subdir` staje sie szablonem;
`resolve_subdir()` wypelnia go czesciowo (`str.replace`), a `FileStorage`
rozwiazuje `{uklad}` per godlo i waliduje zero klamer. Wycinek PL sklada sie
z istniejacych klockow: arkusze przez `DownloadManager` (cache),
`mosaic_and_crop` (rozszerzone o `dst_kwds`), nowy `transform/raster.py::
warp_to_grid` (wzorzec ADR-024 z `providers/cuzk/dmr.py`), sidecar pisze CLI.

**Tech Stack:** Python 3.12+, rasterio (merge/warp), pyproj (PinnedTransform),
pytest (offline, blokada gniazd w conftest), ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-28-uklad-data-i-target-crs-pl-design.md`
(czytaj razem z planem; plan argumentuje ze specu). Decyzje D1-D8 w sekcji 2
specu sa zatwierdzone przez uzytkownika 2026-08-28.

## Global Constraints

- Galaz: **develop** (praca bezposrednio; BREAKING dozwolony — 0.7.0 przed
  tagiem, decyzja D7). Conventional Commits. Commity czesto, po kazdym zadaniu.
- Komendy srodowiska (zawsze przez venv):
  `.venv/bin/python -m pytest tests/ -q` (testy sa OFFLINE — conftest przewraca
  kazdy test otwierajacy gniazdo poza loopbackiem; nie dodawaj testow z siecia),
  `.venv/bin/python -m ruff check kartograf/ tests/`,
  `.venv/bin/python -m ruff format kartograf/ tests/`,
  `.venv/bin/python -m mypy kartograf/`. **Baseline: 33 bledy na starcie planu**
  (zmierzone 2026-08-28), z czego jeden znika w Zad. 2:
  `download_cmd.py:1347: Unsupported operand types for "/" ("Path" and "None")`
  — `descriptor.storage_subdir` (`str | None`) zastapione przez
  `resolve_subdir()` (`str`). Docelowa brama (Zad. 12): **<= 32, zero nowych**.
  Uwaga: dokumenty repo (PROGRESS/CLAUDE.md) mowia "32" — to stan z audytu
  2026-08-23; nie traktuj ich jako pomiaru, mierz sam.
- Punkt startowy suity: **1716 testow, pokrycie 93%** (2026-08-23).
- Bez shimow zgodnosciowych (feedback uzytkownika): zmiany lamiace uklad na
  dysku ida wprost do CHANGELOG Breaking Changes; zadnych warstw kompatu.
- Dokumentacja i komentarze: polski bez znakow diakrytycznych (ASCII), jak
  reszta repo. Docstringi w istniejacych plikach: zachowaj jezyk pliku
  (storage.py/manager.py sa po angielsku — nowe fragmenty w nich tez).
- `landcover/` (bdot10k/corine/soilgrids, `storage_subdir=None`) — BEZ ZMIAN.
- Segmenty: wartosci lowercase; `{vcrs}` wypelniane z `.lower()` nazwy CLI
  (`"Bpv"` -> `"bpv"`, `"EVRF2007"` -> `"evrf2007"`, `"KRON86"` -> `"kron86"`).

## Odstepstwa od litery specu (do wiadomosci review)

1. **Sidecar wycinka PL: `capability="sheet_files"`, nie `"bbox_raster"`**
   (spec 6.1 pkt 5). Powod twardy: deskryptor `pl.gugik.nmt_5m` NIE MA kanalu
   z capability `bbox_raster` (`build_metadata(capability="bbox_raster")`
   rzuca KeyError -> best-effort wrapper polknie blad -> sidecar by NIE
   powstal), a kanal `bbox_raster` w `pl.gugik.nmt_1m` to WCS deklarujacy
   wylacznie KRON86 (`EPSG:9650`) — sidecar wycinka EVRF2007 dostalby
   `vertical_crs="EPSG:5621"` zamiast faktycznego `EPSG:9651`. Kanal
   `sheet_files` opisuje fakt (dane pochodza z arkuszy OpenData) i rozwiazuje
   pion poprawnie dla obu ukladow. Odnotowane w ADR-027 (Zad. 11).
2. **Warp PL to NOWA funkcja `kartograf/transform/raster.py::warp_to_grid`
   (sparametryzowana kopia wzorca), a nie refaktoryzacja/wspoldzielenie
   `providers/cuzk/dmr.py::_warp_to_grid`.** Powod: testy regresyjne ADR-024
   patchuja `kartograf.providers.cuzk.dmr.reproject`
   (tests/test_cuzk_dmr.py:496,527) — przeniesienie wywolania `reproject`
   z dmr.py zlamaloby patch targety; tor CZ jest zweryfikowany live i spec
   (sekcja 12) kaze go nie dotykac tuz przed wydaniem. Kopia jest mala
   (~45 linii) i dostaje wlasne testy tresci.
3. **CLAUDE.md nie zawiera dzis literalu `nmt_2000_1m`** (zweryfikowane
   grep-em 2026-08-28; spec 10.2 kaze "skorygowac nieaktualna wzmianke").
   Korekta materializuje sie jako nowa, poprawna sekcja struktury `data/`
   w CLAUDE.md (Zad. 11 Step 3); stale wzmianki `nmt_2000_1m` sa w CHANGELOG
   (wpis historyczny 0.5.0 — zostaje, ma juz uwage) i PROGRESS (A1-9 —
   domkniete w Zad. 11 Step 6).
4. **Kaskada `_laz_uklad` jest szersza niz spec 5.5 pkt 2.** Spec bramkuje
   krok "format godla" warunkiem `crs=None`; plan schodzi do formatu godla dla
   KAZDEGO nierozpoznanego `uklad_xy` (np. `"EPSG:2180"`). Powod: nierozpoznany
   string nie niesie informacji o systemie GODEL, a format godla owszem —
   twarde `2000` byloby gorszym zgadywaniem niz odczyt z identyfikatora.
   Zachowanie dla `PL-2000*`/`PL-1992*`/`None` jest dokladnie takie jak w specu.
5. **Selekcja arkuszy idzie z bboxa zadania, a crop z bboxa znormalizowanego
   do EPSG:2180** (spec 6.1 pkt 1 sugeruje jedna normalizacje przed
   `find_sheets_for_bbox`). Powod: `find_sheets_for_bbox` przyjmuje dzis bbox
   w ukladzie zadania (2180/4326) i tak dziala caly tor PL bez flagi —
   wpinanie normalizacji przed nia zmienialoby zachowanie sciezki BEZ
   `--target-crs`, czego ten plan swiadomie nie robi. Rozjazd jest nieszkodliwy:
   arkusze 1:10000 sa o rzedy wielkosci wieksze niz roznica obwiedni z dwoch
   4-naroznikowych przeliczen, a zasieg WYNIKU definiuje wylacznie bbox cropu.
6. **Walidacje 6.3 zyja w `_resolve_pl_sentinels` + galezi godlowej
   `cmd_download`, a nie w checkliscie `_dispatch_area`.** Spec 6.2 kaze
   USUNAC z dyspozycji blokade "PL + --target-crs"; nowe walidacje (produkt,
   system 2000) musza dzialac takze w trybie godlowym i LAZ, wiec ich
   naturalnym miejscem sa sentinele (wywolywane we wszystkich przeplywach PL).
   Na pograniczu produktowe flagi PL (`nmpt`/`orto`, `--system`) i tak
   rozstrzygaja kraj do `pl` PRZED pobraniem (istniejacy `_pl_only_flags`),
   wiec blad pada zanim cokolwiek pojdzie do CUZK.

## Mapa plikow

**Nowe:**
- `kartograf/transform/raster.py` — `warp_to_grid` (+ cichy filtr GDAL)
- `tests/test_transform_raster.py`
- `tests/test_pl_cutout.py`
- `docs/ARCHITECTURE.md`

**Modyfikowane (kod):**
- `kartograf/sources/descriptor.py` — `resolve_subdir` (Zad. 1) + komentarz pola (Zad. 2)
- `kartograf/sources/registry.py` — 7 wartosci `storage_subdir` (Zad. 2)
- `kartograf/download/storage.py` — `vertical_crs=`, szablony, walidacja (Zad. 2)
- `kartograf/download/manager.py` — default storage z `resolve_subdir` (Zad. 3)
- `kartograf/transport/mosaic.py` — `dst_kwds=` (Zad. 6)
- `kartograf/cli/download_cmd.py` — CZ (Zad. 2), PL storage (Zad. 4), LAZ (Zad. 5), walidacje + wycinek bbox (Zad. 8), geometry (Zad. 9)
- `kartograf/cli/_parser.py` — help `--target-crs` (Zad. 8)

**Modyfikowane (testy — churn sciezkowy):** `tests/test_storage.py`,
`tests/test_sources_registry.py`, `tests/test_cuzk_dmr.py`,
`tests/test_download_manager.py`, `tests/test_integration.py`,
`tests/test_cli.py`, `tests/test_transport_mosaic.py`.

**Modyfikowane (docs):** `CLAUDE.md`, `README.md`, `docs/SCOPE.md`,
`docs/CHANGELOG.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`.

**Tabela zamian literalow sciezkowych** (uzywana w Zad. 2 i 5; spec sekcja 3).
UWAGA: to mapa POJEC, nie recepta "znajdz i zamien" — pion segmentu zawsze
bierze sie z faktycznej wartosci providera/flagi (np. test CZ z EVRF2007
dostaje `cz_dmr5g_evrf2007`, nie `_bpv`):

| Stary literal w asercjach | Nowy literal |
|---|---|
| `nmt_1m` (sciezki, default storage PL-1992) | `nmt/pl_1992_1m_evrf2007` (w Path: `"nmt" / "pl_1992_1m_evrf2007"`) |
| `nmt_1m` (asercje `_subdir` managera/fabryki) | `nmt/pl_{uklad}_1m_evrf2007` |
| `nmt_5m` (sciezki) | `nmt/pl_1992_5m_evrf2007` |
| `nmt_5m` (asercje `_subdir`) | `nmt/pl_{uklad}_5m_evrf2007` |
| `nmpt` (asercje `_subdir`) | `nmpt/pl_{uklad}_1m_evrf2007` |
| `orto` (asercje `_subdir`) | `orto/pl_{uklad}` |
| `laz` (sciezki kafli, fixtury PL-2000:S6) | `laz/pl_2000_evrf2007` |
| `cz_dmr5g` (sciezki) | `nmt/cz_dmr5g_bpv` (w Path: `"nmt" / "cz_dmr5g_bpv"`) |
| `cz_dmr4g` (sciezki) | `nmt/cz_dmr4g_bpv` |
| `FileStorage(product="nmt_2000_1m")` | BEZ ZMIAN (nieznany product = passthrough) |
| `FileStorage(subdir="cz_dmr5g")` literal (test_storage:588) | BEZ ZMIAN (override bez klamer dziala jak dotad) |

---

### Zad. 1: `SourceDescriptor.resolve_subdir`

**Files:**
- Modify: `kartograf/sources/descriptor.py` (klasa `SourceDescriptor`, po polu `auth`, linia ~81)
- Test: `tests/test_sources_registry.py` (nowa klasa `TestResolveSubdir`)

**Interfaces:**
- Consumes: pole `storage_subdir: str | None` (istniejace).
- Produces: `SourceDescriptor.resolve_subdir(*, uklad: str | None = None,
  vertical_crs: str | None = None) -> str` — wypelnia `{uklad}`/`{vcrs}` przez
  `str.replace`; czesciowe wypelnienie legalne; `vertical_crs` normalizowane
  `.lower()`; wymiar nieobecny w szablonie = no-op; `storage_subdir is None`
  = `ValueError`. Konsumenci: Zad. 2 (CZ CLI), Zad. 3 (manager), Zad. 5 (LAZ),
  Zad. 8 (wycinek PL).

- [ ] **Step 1: Napisz padajace testy**

W `tests/test_sources_registry.py` dodaj na koncu pliku:

```python
class TestResolveSubdir:
    """ADR-026: storage_subdir jest szablonem; resolve_subdir wypelnia go."""

    def _descriptor(self, subdir):
        from kartograf.sources.descriptor import (
            AccessChannel,
            LicenseInfo,
            SourceDescriptor,
            TransportKind,
        )

        return SourceDescriptor(
            key="test.key",
            country="PL",
            product="nmt",
            name="Test",
            provider_name="Test",
            channels=(
                AccessChannel(
                    transport=TransportKind.WCS, horizontal_crs="EPSG:2180"
                ),
            ),
            tile_scheme=None,
            storage_subdir=subdir,
            default_extension=".asc",
            license=LicenseInfo(id="X", attribution="X"),
        )

    def test_full_fill(self):
        d = self._descriptor("nmt/pl_{uklad}_1m_{vcrs}")
        assert (
            d.resolve_subdir(uklad="1992", vertical_crs="EVRF2007")
            == "nmt/pl_1992_1m_evrf2007"
        )

    def test_partial_fill_leaves_uklad(self):
        d = self._descriptor("nmt/pl_{uklad}_1m_{vcrs}")
        assert (
            d.resolve_subdir(vertical_crs="KRON86") == "nmt/pl_{uklad}_1m_kron86"
        )

    def test_vcrs_lowercased(self):
        d = self._descriptor("nmt/cz_dmr5g_{vcrs}")
        assert d.resolve_subdir(vertical_crs="Bpv") == "nmt/cz_dmr5g_bpv"

    def test_unknown_dimension_is_noop(self):
        """Orto nie ma {vcrs} — podanie vertical_crs niczego nie psuje."""
        d = self._descriptor("orto/pl_{uklad}")
        assert (
            d.resolve_subdir(uklad="1992", vertical_crs="EVRF2007")
            == "orto/pl_1992"
        )

    def test_no_args_returns_template(self):
        d = self._descriptor("laz/pl_{uklad}_{vcrs}")
        assert d.resolve_subdir() == "laz/pl_{uklad}_{vcrs}"

    def test_none_subdir_raises(self):
        d = self._descriptor(None)
        with pytest.raises(ValueError, match="test.key"):
            d.resolve_subdir()
```

(`pytest` jest juz importowany w tym pliku.)

- [ ] **Step 2: Uruchom testy — musza padac**

Run: `.venv/bin/python -m pytest tests/test_sources_registry.py::TestResolveSubdir -q`
Expected: FAIL, `AttributeError: ... 'SourceDescriptor' object has no attribute 'resolve_subdir'`

- [ ] **Step 3: Implementacja**

W `kartograf/sources/descriptor.py`, wewnatrz `SourceDescriptor`, po polu
`auth: str = "none"` dodaj metode:

```python
    def resolve_subdir(
        self, *, uklad: str | None = None, vertical_crs: str | None = None
    ) -> str:
        """Wypelnij szablon ``storage_subdir`` (placeholdery {uklad}, {vcrs}).

        ``str.replace``, nie ``str.format`` — czesciowe wypelnienie jest
        legalne ({uklad} moze zostac do rozwiazania pozniej, per godlo,
        w FileStorage). Wymiar nieobecny w szablonie = no-op (orto ignoruje
        vcrs). Walidacje "zero klamer w segmencie" robi wolajacy koncowy
        (FileStorage) — ADR-026.
        """
        if self.storage_subdir is None:
            raise ValueError(f"Zrodlo '{self.key}' nie ma storage_subdir")
        subdir = self.storage_subdir
        if uklad is not None:
            subdir = subdir.replace("{uklad}", uklad)
        if vertical_crs is not None:
            subdir = subdir.replace("{vcrs}", vertical_crs.lower())
        return subdir
```

(Frozen dataclass moze miec zwykle metody — nic wiecej nie zmieniaj.)

- [ ] **Step 4: Testy zielone**

Run: `.venv/bin/python -m pytest tests/test_sources_registry.py -q`
Expected: PASS (cala reszta pliku tez — wartosci rejestru jeszcze nietkniete)

- [ ] **Step 5: Commit**

```bash
git add kartograf/sources/descriptor.py tests/test_sources_registry.py
git commit -m "feat(sources): SourceDescriptor.resolve_subdir — szablony {uklad}/{vcrs} (ADR-026)"
```

---

### Zad. 2: Szablony segmentow — rejestr + FileStorage + CZ CLI (+ churn asercji)

Rejestr, FileStorage, testy spojnosci (`test_sources_registry.py::
TestDescriptorProviderConsistency` porownuje `d.storage_subdir` z
`storage._subdir`) ORAZ przeplywy CZ w CLI (czytaja `descriptor.
storage_subdir` doslownie — po zmianie wartosci na szablon dostalyby sciezke
z klamra `{vcrs}`) sa sprzezone przez te same wartosci — musza przejsc
w jednym zadaniu, inaczej suita bylaby czerwona miedzy commitami.

**Files:**
- Modify: `kartograf/sources/registry.py:93,114,134,153,173,264,311` (wartosci `storage_subdir`)
- Modify: `kartograf/sources/descriptor.py:76` (komentarz pola)
- Modify: `kartograf/download/storage.py` (konstruktor, `_RESOLUTION_SUBDIRS`, nowa `_PRODUCT_SUBDIRS`, `_subdir`, nowa `_resolved_subdir`, `get_path`, `get_raw_path`, `list_files`, docstringi)
- Modify: `kartograf/cli/download_cmd.py:1262` (`_cz_download_godlo`) i `:1346-1351` (`_cz_download_bbox`) — `storage_subdir` -> `resolve_subdir(vertical_crs=provider.vertical_crs)`
- Test: `tests/test_storage.py` (nowa klasa + aktualizacje), `tests/test_sources_registry.py:151,190,212,237-334`, `tests/test_cuzk_dmr.py:1016-1017`, `tests/test_download_manager.py:137,155,167,176`, `tests/test_integration.py:92`, `tests/test_cli.py` (sciezki CZ: 2825,2833,2867,2885,2892-2945,3057,3062,3074,3097,3120,3213)

**Efekt uboczny do swiadomej akceptacji:** od tego commita `_cmd_download_laz`
(wciaz `FileStorage(output_dir, product="laz")`) pisze do
`laz/pl_<uklad>_evrf2007/`, bo `{vcrs}` wypelnia DEFAULT FileStorage —
`--vertical-crs KRON86` jest w tym jednym commicie ignorowany w nazwie
segmentu. Domyka to Zad. 5 (storage per kafel z faktycznym pionem). Testy LAZ
tego nie zlapia (szukaja plikow przez `rglob`), wiec nie zwlekaj z Zad. 5.

**Interfaces:**
- Consumes: `resolve_subdir` (Zad. 1), `parser_registry.detect_system` (istniejace).
- Produces: `FileStorage.__init__(output_dir="./data", resolution="1m",
  product=None, subdir=None, vertical_crs: str | None = "EVRF2007")`;
  `FileStorage._subdir -> str` (szablon z wypelnionym `{vcrs}`, `{uklad}`
  moze zostac); sciezki (`get_path`/`get_raw_path`/`exists`/`delete`/
  `write_atomic`/`ensure_directory`) rozwiazuja `{uklad}` per identyfikator
  (system `pl2000` -> `2000`, inaczej `1992` — ta sama regula co
  `path_parts`); nierozwiazana klamra = `ValidationError` z nazwa wymiaru.
  Nieznany `product` i `subdir=` bez klamer — passthrough jak dotad.
  Zad. 3-5, 8 i 9 polegaja na tych sygnaturach.

- [ ] **Step 1: Napisz padajace testy nowego ukladu**

W `tests/test_storage.py` dodaj import (obok istniejacych):

```python
from kartograf.exceptions import ValidationError
```

i na koncu pliku nowa klase:

```python
class TestFileStorageSegments:
    """Uklad data/ 0.7.0: <produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>] (ADR-026)."""

    def test_default_pl1992_evrf2007(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m")
        assert storage.get_path("N-34-130-D-d-2-4", ".asc") == (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007"
            / "N-34" / "130" / "D" / "d" / "2" / "4" / "N-34-130-D-d-2-4.asc"
        )

    def test_kron86_segment(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="KRON86")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        assert "pl_1992_1m_kron86" in path.parts

    def test_pl2000_gets_own_segment(self, tmp_path):
        """ADR-017 domkniety: PL-2000 nie dzieli juz katalogu z PL-1992."""
        storage = FileStorage(tmp_path, resolution="1m")
        assert storage.get_path("6.179.12.20", ".asc") == (
            tmp_path / "nmt" / "pl_2000_1m_evrf2007"
            / "6" / "179" / "12" / "20" / "6.179.12.20.asc"
        )

    def test_nmt_5m_segment(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="5m")
        path = storage.get_path("N-34-130-D-d-2-4", ".asc")
        assert "pl_1992_5m_evrf2007" in path.parts

    def test_nmpt_segment(self, tmp_path):
        storage = FileStorage(tmp_path, product="nmpt")
        path = storage.get_path("N-34", ".asc")
        assert path == (
            tmp_path / "nmpt" / "pl_1992_1m_evrf2007" / "N-34" / "N-34.asc"
        )

    def test_orto_segment_no_vcrs(self, tmp_path):
        """Orto nie ma pionowego — segment bez {vcrs} takze przy None."""
        storage = FileStorage(tmp_path, product="orto", vertical_crs=None)
        assert storage.get_path("N-34", ".tif") == (
            tmp_path / "orto" / "pl_1992" / "N-34" / "N-34.tif"
        )

    def test_laz_segment_by_identifier(self, tmp_path):
        storage = FileStorage(tmp_path, product="laz")
        p1992 = storage.get_raw_path("N-33-131-B-a-1-1-4", "a.laz")
        p2000 = storage.get_raw_path("6.162.34.02.3", "b.laz")
        assert ("laz", "pl_1992_evrf2007") == tuple(p1992.parts[-10:-8])
        assert ("laz", "pl_2000_evrf2007") == tuple(p2000.parts[-8:-6])

    def test_unresolved_vcrs_raises(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs=None)
        with pytest.raises(ValidationError, match="vcrs"):
            storage.get_path("N-34-130-D-d-2-4", ".asc")

    def test_unknown_product_passthrough(self, tmp_path):
        storage = FileStorage(tmp_path, product="nmt_2000_1m")
        assert storage.get_path("6.179.12.20", ".asc") == (
            tmp_path / "nmt_2000_1m" / "6" / "179" / "12" / "20"
            / "6.179.12.20.asc"
        )

    def test_subdir_override_fills_vcrs(self, tmp_path):
        storage = FileStorage(
            tmp_path, subdir="nmt/cz_dmr5g_{vcrs}", vertical_crs="Bpv"
        )
        assert storage.get_raw_path("302_5550", "302_5550.tif") == (
            tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"
        )

    def test_list_files_spans_both_uklady(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m")
        storage.write_atomic("N-34-130-D-d-2-4", b"x", ".asc")
        storage.write_atomic("6.179.12.20", b"y", ".asc")
        assert len(storage.list_files()) == 2

    def test_delete_with_sidecar_in_new_layout(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="1m")
        path = storage.write_atomic("6.179.12.20", b"x", ".asc")
        sidecar = path.with_name(path.name + ".meta.json")
        sidecar.write_text("{}\n", encoding="utf-8")
        assert storage.delete("6.179.12.20") is True
        assert not path.exists() and not sidecar.exists()
```

Uwaga do `test_laz_segment_by_identifier`: hierarchia 1992 to
`laz/pl_1992_evrf2007/N-33/131/B/a/1/1/4/a.laz` (10 czesci od konca liczac
plik), 2000 to `laz/pl_2000_evrf2007/6/162/34/02/3/b.laz` (8 czesci) — stad
rozne indeksy. Jesli slicing okaze sie kruchy, zamien na
`assert "laz/pl_1992_evrf2007" in str(p1992)` itd.

- [ ] **Step 2: Uruchom — musza padac**

Run: `.venv/bin/python -m pytest tests/test_storage.py::TestFileStorageSegments -q`
Expected: FAIL (stare sciezki `nmt_1m/...`, brak parametru `vertical_crs`)

- [ ] **Step 3: Implementacja — `kartograf/download/storage.py`**

(a) Importy — dodaj na gorze:

```python
import re
```
oraz
```python
from kartograf.exceptions import ValidationError
```

(b) Konstruktor — nowa sygnatura i przechowanie pionu (reszta ciala bez zmian):

```python
    def __init__(
        self,
        output_dir: str | Path = "./data",
        resolution: str = "1m",
        product: str | None = None,
        subdir: str | None = None,
        vertical_crs: str | None = "EVRF2007",
    ):
```

W docstringu parametru dopisz:

```python
        vertical_crs : str, optional
            Vertical CRS filling the ``{vcrs}`` placeholder of the segment
            template (lowercased; default "EVRF2007"). ``None`` leaves the
            placeholder unresolved — path methods then raise
            ``ValidationError`` for templates that require it.
```

Na koncu ciala `__init__` dodaj:

```python
        self._vertical_crs = vertical_crs
```

(c) Mapy szablonow — zastap `_RESOLUTION_SUBDIRS` i dodaj `_PRODUCT_SUBDIRS`:

```python
    # Segment templates (ADR-026): {uklad} resolved per godlo, {vcrs} from
    # the constructor's vertical_crs.
    _RESOLUTION_SUBDIRS = {
        "1m": "nmt/pl_{uklad}_1m_{vcrs}",
        "5m": "nmt/pl_{uklad}_5m_{vcrs}",
    }
    _PRODUCT_SUBDIRS = {
        "nmpt": "nmpt/pl_{uklad}_1m_{vcrs}",
        "orto": "orto/pl_{uklad}",
        "laz": "laz/pl_{uklad}_{vcrs}",
    }
```

(d) Property `_subdir` — nowe cialo (wypelnia `{vcrs}`; `{uklad}` zostaje):

```python
    @property
    def _subdir(self) -> str:
        """Return the segment template (override, product or resolution).

        ``{vcrs}`` is already filled from ``vertical_crs``; ``{uklad}`` may
        remain — path methods resolve it per identifier.
        """
        if self._subdir_override:
            template = self._subdir_override
        elif self._product:
            template = self._PRODUCT_SUBDIRS.get(self._product, self._product)
        else:
            template = self._RESOLUTION_SUBDIRS.get(
                self._resolution, self._resolution
            )
        if self._vertical_crs is not None:
            template = template.replace("{vcrs}", self._vertical_crs.lower())
        return template
```

(e) Nowe metody prywatne (po `_subdir`):

```python
    @staticmethod
    def _ensure_resolved(subdir: str) -> str:
        """Reject a segment that still contains an unresolved placeholder."""
        if "{" in subdir:
            missing = ", ".join(re.findall(r"\{(\w+)\}", subdir))
            raise ValidationError(
                f"Nierozwiazany wymiar segmentu storage: {missing} "
                f"(subdir '{subdir}')"
            )
        return subdir

    def _resolved_subdir(self, identifier: str) -> str:
        """Segment for the identifier: {uklad} from the sheet system.

        Same rule as ``parser_registry.path_parts``: dots (system ``pl2000``)
        -> "2000", anything else (incl. the pl1992 fallback) -> "1992".
        """
        subdir = self._subdir
        if "{uklad}" in subdir:
            system = parser_registry.detect_system(identifier)
            uklad = "2000" if system is not None and system.id == "pl2000" else "1992"
            subdir = subdir.replace("{uklad}", uklad)
        return self._ensure_resolved(subdir)
```

(f) `get_path` — zamien linie `dir_path = self._output_dir / self._subdir` na:

```python
        dir_path = self._output_dir / self._resolved_subdir(normalized_godlo)
```

(g) `get_raw_path` — zamien `dir_path = self._output_dir / self._subdir` na:

```python
        dir_path = self._output_dir / self._resolved_subdir(identifier)
```

(h) `list_files` — nowe cialo (szablon z `{uklad}` obejmuje OBA uklady):

```python
        template = self._subdir
        if "{uklad}" in template:
            subdirs = [template.replace("{uklad}", u) for u in ("1992", "2000")]
        else:
            subdirs = [template]
        files: list[Path] = []
        for name in subdirs:
            root = self._output_dir / self._ensure_resolved(name)
            if root.exists():
                files.extend(root.glob(pattern))
        return files
```

(i) Docstringi struktury: w docstringu klasy podmien przyklady na

```
        data/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/nmt/pl_1992_5m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/nmpt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        data/orto/pl_1992/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif
```

a blok PL-2000 (linie ~31-36, "PL-2000 sheets share...") zastap:

```
    Directory structure example (PL-2000, own segment since 0.7.0/ADR-026 —
    the ADR-017 deferral is closed):
        data/nmt/pl_2000_1m_evrf2007/6/179/12/20/6.179.12.20.asc
```

Zaktualizuj tez przyklady w docstringach `get_path` (2 miejsca z
`nmt_1m/...`) i `get_raw_path` (`data/laz/...` ->
`data/laz/pl_1992_evrf2007/...`) — nowe segmenty jak wyzej.

- [ ] **Step 4: Implementacja — `kartograf/sources/registry.py`**

Podmien 7 wartosci `storage_subdir` (spec sekcja 4, tabela):

| Linia | Bylo | Jest |
|---|---|---|
| 93 | `storage_subdir="nmt_1m",` | `storage_subdir="nmt/pl_{uklad}_1m_{vcrs}",` |
| 114 | `storage_subdir="nmt_5m",` | `storage_subdir="nmt/pl_{uklad}_5m_{vcrs}",` |
| 134 | `storage_subdir="nmpt",` | `storage_subdir="nmpt/pl_{uklad}_1m_{vcrs}",` |
| 153 | `storage_subdir="orto",` | `storage_subdir="orto/pl_{uklad}",` |
| 173 | `storage_subdir="laz",` | `storage_subdir="laz/pl_{uklad}_{vcrs}",` |
| 264 | `storage_subdir="cz_dmr5g",` | `storage_subdir="nmt/cz_dmr5g_{vcrs}",` |
| 311 | `storage_subdir="cz_dmr4g",` | `storage_subdir="nmt/cz_dmr4g_{vcrs}",` |

W `kartograf/sources/descriptor.py:76` zamien komentarz pola:

```python
    storage_subdir: str | None  # szablon segmentu {uklad}/{vcrs} (ADR-026); None dla zrodel LandCoverManagera
```

- [ ] **Step 5: Uruchom nowe testy — zielone; caly plik test_storage — napraw churn**

Run: `.venv/bin/python -m pytest tests/test_storage.py -q`

Padajace stare asercje napraw wg tabeli zamian (Mapa plikow). PELNA lista
miejsc, ktore pekaja (zweryfikowana na repo 2026-08-28 — jesli pada cos
poza nia, to przeoczony konsument: napraw i odnotuj w PROGRESS przy Zad. 11):
- :326 `expected_parts = ["nmt_1m", "N-34", ...]` ->
  `["nmt", "pl_1992_1m_evrf2007", "N-34", ...]`
- :350 `common_parent = tmp_path / "nmt_1m" / ...` ->
  `tmp_path / "nmt" / "pl_1992_1m_evrf2007" / ...`
- :390 (`test_product_none_backward_compatible`) `assert "nmt_1m" in parts`
  -> `assert "pl_1992_1m_evrf2007" in parts`
- :397-405 (`test_product_subdir_structure`) — spacer po `expected_parts`
  zaczynajacy sie od `"orto"`: wstaw segment, czyli
  `expected_parts = ["orto", "pl_1992", "N-34", ...]`
- :434 `assert "/nmt_5m/" in str(path)` ->
  `assert "/nmt/pl_1992_5m_evrf2007/" in str(path)`
- :602-607 (`TestSubdirOverride.test_none_keeps_legacy_behavior`) — OBA
  asserty: `tmp_path / "nmt_1m" / "N-34" / "N-34.asc"` ->
  `tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "N-34" / "N-34.asc"`;
  `tmp_path / "nmpt" / ...` -> `tmp_path / "nmpt" / "pl_1992_1m_evrf2007" / ...`

Miejsca, ktore mimo pozorow NIE wymagaja zmiany (nie ruszaj):
- `TestFileStoragePL2000` — `product="nmt_2000_1m"` to passthrough nieznanego
  productu.
- `TestFileStorageProduct.test_product_nmpt_subdir` — `"nmpt" in parts` nadal
  prawdziwe (`nmpt` to teraz katalog produktu).
- `TestFileStorageGetRawPath` (:556-575) — slice'y sa liczone OD KONCA
  (`parts[-8:-1]`, `parts[-6:-1]`), a nowy segment wchodzi PRZED hierarchia
  godla, wiec indeksy sie nie zmieniaja; `"laz" in parts` tez zostaje
  prawdziwe. Przesuwanie tych indeksow zepsuloby zielone testy.
- `TestSubdirOverride.test_subdir_takes_precedence` / `test_repr_with_subdir`
  — literal `subdir="cz_dmr5g"` bez klamer dziala jak dotad.
- `TestDeleteRemovesSidecar` — sciezka przezroczysta.

- [ ] **Step 6: Napraw churn w pozostalych plikach testow**

- `tests/test_sources_registry.py`:
  - 151: `assert d.storage_subdir == "nmt/pl_{uklad}_1m_{vcrs}"`
  - 190: `assert d.storage_subdir == "nmt/cz_dmr5g_{vcrs}"`
  - 212: `assert d.storage_subdir == "nmt/cz_dmr4g_{vcrs}"`
  - ~74 (konstrukcja w test_descriptor_frozen): wartosc dowolna legalna —
    podmien na `storage_subdir="nmt/pl_{uklad}_1m_{vcrs}",`
  - `TestDescriptorProviderConsistency` (237-334) — porownania przez
    `resolve_subdir`:
    - nmt_1m (247): `assert d.resolve_subdir(vertical_crs="EVRF2007") == storage._subdir`
      (storage = `FileStorage(tmp_path, resolution="1m")`, default EVRF2007)
    - nmt_5m (279): analogicznie z `resolution="5m"`
    - nmpt (292): `assert d.resolve_subdir(vertical_crs="EVRF2007") == FileStorage(tmp_path, product="nmpt")._subdir`
    - orto (305): `assert d.resolve_subdir() == FileStorage(tmp_path, product="orto")._subdir`
    - laz (314): `assert d.resolve_subdir(vertical_crs="EVRF2007") == FileStorage(tmp_path, product="laz")._subdir`
  - 331 (`storage_subdir is None` dla landcover) — BEZ ZMIAN.
- `tests/test_cuzk_dmr.py:1016-1017`:

```python
        storage = FileStorage(tmp_path, subdir=d.resolve_subdir(vertical_crs="Bpv"))
        assert storage._subdir == "nmt/cz_dmr5g_bpv"
```

- `tests/test_download_manager.py` (manager przekazuje surowy szablon;
  FileStorage wypelnia `{vcrs}` swoim defaultem EVRF2007 — Zad. 3 doda
  przekazanie pionu):
  - 137: `assert manager._storage._subdir == "nmpt/pl_{uklad}_1m_evrf2007"`
  - 155: `assert manager._storage._subdir == "orto/pl_{uklad}"`
  - 167: `assert manager._storage._subdir == "nmt/pl_{uklad}_5m_evrf2007"`
  - 176: `assert manager._storage._subdir == "nmt/pl_{uklad}_1m_evrf2007"`
- `tests/test_integration.py:92`:
  `common_parent = test_data_dir / "nmt" / "pl_1992_1m_evrf2007" / "N-34" / "130" / "D" / "d" / "2"`

- [ ] **Step 7: Implementacja — CZ CLI na `resolve_subdir`**

W `kartograf/cli/download_cmd.py`:

(a) `_cz_download_godlo` (linia ~1262) — zamien

```python
    storage = FileStorage(args.output, subdir=descriptor.storage_subdir)
```
na
```python
    storage = FileStorage(
        args.output,
        subdir=descriptor.resolve_subdir(vertical_crs=provider.vertical_crs),
    )
```

(b) `_cz_download_bbox` (linie ~1346-1351) — zamien

```python
    target = (
        Path(args.output)
        / descriptor.storage_subdir
        / "bbox"
        / f"{coords}{descriptor.default_extension}"
    )
```
na
```python
    target = (
        Path(args.output)
        / descriptor.resolve_subdir(vertical_crs=provider.vertical_crs)
        / "bbox"
        / f"{coords}{descriptor.default_extension}"
    )
```

(`provider.vertical_crs` to `"Bpv"` albo `"EVRF2007"` — mock w testach CLI
juz ustawia `provider.vertical_crs = "Bpv"`, tests/test_cli.py:2774.)

- [ ] **Step 8: Churn sciezek CZ w `tests/test_cli.py`**

PELNA lista (zweryfikowana na repo 2026-08-28). Uwaga: pion segmentu bierze
sie z `provider.vertical_crs` mocka — domyslnie `"Bpv"`, ale JEDEN test
ustawia `EVRF2007` i dostaje inny segment. Nie stosuj tabeli zamian na slepo.

Segment `nmt/cz_dmr5g_bpv` (mock z domyslnym `vertical_crs="Bpv"`):
- 2825: `assert target == tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"`
- 2833: `sidecar = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif.meta.json"`
- 2892-2919 (`test_bbox_mode_file_in_bbox_subdir_and_parent_request`):
  `target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "bbox" / "-447000_-1114000_-446000_-1113000.tif"`
- 2939: `assert target.parent == tmp_path / "nmt" / "cz_dmr5g_bpv" / "bbox"`
- 3057 (`assert not (tmp_path / "cz_dmr5g").exists()`) — inaczej asercja staje
  sie prawdziwa TRYWIALNIE (katalog o tej nazwie juz nie powstaje):
  `assert not (tmp_path / "nmt" / "cz_dmr5g_bpv").exists()`
- 3062 (`test_skip_existing`) i 3074 (`test_force_overwrites_existing`) —
  te testy TWORZA plik pod stara sciezka, wiec bez poprawki
  `provider.download.assert_not_called()` pada:
  `target = tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif"`
- 3120 (`test_sidecar_failure_does_not_fail_download`): jak wyzej
- 3213 (sidecar z nodata): `tmp_path / "nmt" / "cz_dmr5g_bpv" / "302" / "5550" / "302_5550.tif.meta.json"`

Segment `nmt/cz_dmr4g_bpv`:
- 2867: `sidecar = tmp_path / "nmt" / "cz_dmr4g_bpv" / "CTES" / "96" / "CTES96.tif.meta.json"`
- 2885: `target = tmp_path / "nmt" / "cz_dmr4g_bpv" / "CTES" / "96" / "CTES96.tif"`

Segment `nmt/cz_dmr5g_evrf2007` (WYJATEK — `provider.vertical_crs = "EVRF2007"`
ustawione w tescie na linii ~3086):
- 3097 (`test_evrf2007_transform_lands_in_sidecar`):
  `tmp_path / "nmt" / "cz_dmr5g_evrf2007" / "302" / "5550" / "302_5550.tif.meta.json"`

Ten ostatni test pokrywa juz kryterium 13.4 (pion w segmencie) — nie dodawaj
osobnego testu EVRF2007. Dopisz tylko do jego docstringa: "segment niesie
pion providera (ADR-026)".

- [ ] **Step 9: Pelna suita + lint**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS w calosci. Jesli pada cos spoza list powyzej — to przeoczony
konsument starego literalu; napraw wg tabeli zamian (i dopisz go do notatki
w PROGRESS przy Zad. 11).
Run: `.venv/bin/python -m ruff check kartograf/ tests/ && .venv/bin/python -m ruff format --check kartograf/ tests/`

- [ ] **Step 10: Commit**

```bash
git add kartograf/sources/registry.py kartograf/sources/descriptor.py kartograf/download/storage.py kartograf/cli/download_cmd.py tests/test_storage.py tests/test_sources_registry.py tests/test_cuzk_dmr.py tests/test_download_manager.py tests/test_integration.py tests/test_cli.py
git commit -m "feat(storage): uklad data/ per produkt — szablony segmentow (rejestr, FileStorage, CZ CLI) (ADR-026)"
```

---

### Zad. 3: DownloadManager — segment z `resolve_subdir` + przekazanie pionu

Bez tej zmiany manager z `vertical_crs="KRON86"` pisalby do segmentu
`..._evrf2007` (FileStorage wypelnia `{vcrs}` swoim defaultem). Celowa
redundancja reguly 5m=>EVRF2007 (fabryka + manager) zostaje.

**Files:**
- Modify: `kartograf/download/manager.py:200-210` (`__init__`, galaz `storage is None`) + docstring parametru `storage` (:170-173)
- Test: `tests/test_download_manager.py` (nowe testy w `TestDownloadManagerStorageFromDescriptor`, obok linii 131-176)

**Interfaces:**
- Consumes: `resolve_subdir(vertical_crs=)` (Zad. 1), `FileStorage(vertical_crs=)` (Zad. 2).
- Produces: `DownloadManager(vertical_crs=...)` bez jawnego `storage=` pisze
  do segmentu z faktycznym pionem (po korekcie 5m=>EVRF2007). Sygnatura
  publiczna BEZ zmian.

- [ ] **Step 1: Napisz padajace testy**

W `tests/test_download_manager.py`, w klasie
`TestDownloadManagerStorageFromDescriptor`, dodaj (wzoruj konstrukcje mocka
na sasiednim tescie z linii ~168-176 — `Mock(spec=...)` wymaga
`PropertyMock` dla `default_extension`):

```python
    def test_default_storage_respects_kron86(self, tmp_path):
        provider = Mock(spec=GugikProvider)
        provider.descriptor_key = "pl.gugik.nmt_1m"
        type(provider).default_extension = PropertyMock(return_value=".asc")
        manager = DownloadManager(
            output_dir=tmp_path, provider=provider, vertical_crs="KRON86"
        )
        assert manager._storage._subdir == "nmt/pl_{uklad}_1m_kron86"

    def test_default_storage_5m_kron86_corrected_to_evrf(self, tmp_path):
        """Regula 5m=>EVRF2007 dziala PRZED budowa segmentu."""
        provider = Mock(spec=GugikProvider)
        provider.descriptor_key = "pl.gugik.nmt_5m"
        type(provider).default_extension = PropertyMock(return_value=".asc")
        manager = DownloadManager(
            output_dir=tmp_path,
            provider=provider,
            vertical_crs="KRON86",
            resolution="5m",
        )
        assert manager._storage._subdir == "nmt/pl_{uklad}_5m_evrf2007"
```

(Importy `Mock`, `PropertyMock`, `GugikProvider`, `DownloadManager` sa juz
w pliku.)

- [ ] **Step 2: Uruchom — musza padac**

Run: `.venv/bin/python -m pytest tests/test_download_manager.py::TestDownloadManagerStorageFromDescriptor -q`
Expected: FAIL — `_subdir` konczy sie `_evrf2007` w tescie KRON86 (default
FileStorage), bo manager nie przekazuje pionu.

- [ ] **Step 3: Implementacja**

W `kartograf/download/manager.py`, w `__init__` (linie ~200-210), zamien:

```python
            if isinstance(key, str):
                from kartograf.sources.registry import get_source

                subdir = get_source(key).storage_subdir
            storage = FileStorage(output_dir, resolution=resolution, subdir=subdir)
```
na:
```python
            if isinstance(key, str):
                from kartograf.sources.registry import get_source

                subdir = get_source(key).resolve_subdir(vertical_crs=vertical_crs)
            storage = FileStorage(
                output_dir,
                resolution=resolution,
                subdir=subdir,
                vertical_crs=vertical_crs,
            )
```

(Lokalna `vertical_crs` przeszla juz korekte 5m=>EVRF2007 w liniach 189-195
— dokladnie o to chodzi. `{uklad}` zostaje do rozwiazania per godlo.)

W docstringu parametru `storage` (linie ~170-173) zamien fragment
"comes from the provider's source descriptor (`storage_subdir`)" na
"comes from the provider's source descriptor
(`resolve_subdir(vertical_crs=...)`, `{uklad}` resolved per godlo)".

- [ ] **Step 4: Testy zielone + pelna suita**

Run: `.venv/bin/python -m pytest tests/test_download_manager.py tests/test_parallel_download.py tests/test_sidecar.py -q`
Expected: PASS (test_parallel_download uzywa `FileStorage(tmp_path)` jako
pisarza i managera jako czytelnika — oba maja teraz ten sam default
`nmt/pl_{uklad}_1m_evrf2007`, wiec przechodzi bez zmian).
Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kartograf/download/manager.py tests/test_download_manager.py
git commit -m "feat(download): DownloadManager buduje segment przez resolve_subdir z faktycznym pionem"
```

---

### Zad. 4: CLI PL — `_create_provider_and_storage` przekazuje pion

**Files:**
- Modify: `kartograf/cli/download_cmd.py:60-90` (`_create_provider_and_storage`)
- Test: `tests/test_cli.py` (testy fabryki, okolice linii 1086-1107)

**Interfaces:**
- Consumes: `FileStorage(vertical_crs=)` (Zad. 2), `create_nmt_provider` (istniejaca fabryka z korekta 5m=>EVRF2007).
- Produces: `_create_provider_and_storage(product, output_dir, vertical_crs,
  resolution)` — sygnatura bez zmian; storage nmt/nmpt dostaje pion
  FAKTYCZNY providera. Konsumenci: `cmd_download`, `_download_pl_bbox`,
  `_download_pl_geometry` (bez zmian u nich).

- [ ] **Step 1: Napisz padajace testy**

W `tests/test_cli.py`, obok istniejacych testow fabryki (linie ~1086-1107),
dodaj. UWAGA: `_create_provider_and_storage` NIE jest importowane na poziomie
modulu — sasiednie testy robia import lokalny i te tez musza (inaczej
`NameError`, a nie oczekiwana asercja):

```python
    def test_nmt_kron86_storage_segment(self, tmp_path):
        from kartograf.cli.commands import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "KRON86", "1m"
        )
        assert storage._subdir == "nmt/pl_{uklad}_1m_kron86"

    def test_nmt_5m_kron86_storage_follows_provider_correction(self, tmp_path):
        """Fabryka koryguje 5m=>EVRF2007 — segment ma niesc fakt, nie flage."""
        from kartograf.cli.commands import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmt", tmp_path, "KRON86", "5m"
        )
        assert storage._subdir == "nmt/pl_{uklad}_5m_evrf2007"

    def test_nmpt_storage_segment(self, tmp_path):
        from kartograf.cli.commands import _create_provider_and_storage

        provider, storage = _create_provider_and_storage(
            "nmpt", tmp_path, "KRON86", "1m"
        )
        assert storage._subdir == "nmpt/pl_{uklad}_1m_kron86"
```

- [ ] **Step 2: Uruchom — musza padac**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "storage_segment or follows_provider"`
Expected: FAIL (`_kron86` vs default `_evrf2007`)

- [ ] **Step 3: Implementacja**

W `_create_provider_and_storage` zamien trzy tworzenia storage:

```python
        provider = GugikNmptProvider(vertical_crs=vertical_crs)
        storage = FileStorage(
            output_dir,
            product="nmpt",
            vertical_crs=getattr(provider, "vertical_crs", vertical_crs),
        )
```
(analogicznie dla nmt:)
```python
        provider = create_nmt_provider(vertical_crs=vertical_crs, resolution=resolution)
        storage = FileStorage(
            output_dir,
            resolution=resolution,
            vertical_crs=getattr(provider, "vertical_crs", vertical_crs),
        )
```
Orto BEZ zmian (`FileStorage(output_dir, product="orto")` — szablon nie ma
`{vcrs}`, default nie szkodzi).

- [ ] **Step 4: Testy zielone + pelna suita**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`
Expected: PASS
Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kartograf/cli/download_cmd.py tests/test_cli.py
git commit -m "feat(cli): segment storage nmt/nmpt niesie faktyczny uklad pionowy"
```

---

### Zad. 5: CLI LAZ — segment per kafel (`uklad_xy` -> `{uklad}`)

**Files:**
- Modify: `kartograf/cli/download_cmd.py:1071-1185` (`_cmd_download_laz`) + nowa funkcja `_laz_uklad` nad nia
- Test: `tests/test_cli.py` (nowa klasa `TestLazUklad` + asercje sciezek w `TestCmdDownloadLaz`, okolice 2436-2625)

**Interfaces:**
- Consumes: `LazTile` (pola `crs: str | None` — np. `"PL-2000:S6"`, `godlo: str`),
  `get_source("pl.gugik.laz").resolve_subdir(uklad=, vertical_crs=)` (Zad. 1),
  `FileStorage(subdir=...)` (Zad. 2).
- Produces: `_laz_uklad(tile) -> str` ("1992" | "2000"); kafle laduja w
  `laz/pl_<uklad>_<vcrs>/<hierarchia>/<oryginalna nazwa>.laz`; storage
  cache'owany per uklad (kafle z roznych ukladow w jednym zadaniu).

- [ ] **Step 1: Napisz padajace testy**

W `tests/test_cli.py` dodaj nowa klase (obok `TestCmdDownloadLaz`):

```python
class TestLazUklad:
    """Kaskada ukladu kafla LAZ: uklad_xy -> format godla -> 2000 (spec 5.5)."""

    def _tile(self, godlo="N-33-131-B-a-1-1-4", crs="PL-2000:S6"):
        from kartograf.providers.pl.gugik_laz import LazTile

        return LazTile(
            godlo=godlo, url="u/f.laz", year=2024, density=25, crs=crs,
            min_x=0.0, min_y=0.0, max_x=1.0, max_y=1.0,
        )

    def test_crs_pl2000_wins_over_dash_godlo(self):
        from kartograf.cli.download_cmd import _laz_uklad

        # godlo myslnikowe, ale uklad_xy mowi PL-2000 — crs wygrywa
        assert _laz_uklad(self._tile()) == "2000"

    def test_crs_pl1992(self):
        from kartograf.cli.download_cmd import _laz_uklad

        assert _laz_uklad(self._tile(crs="PL-1992")) == "1992"

    def test_none_crs_falls_back_to_dot_godlo(self):
        from kartograf.cli.download_cmd import _laz_uklad

        assert _laz_uklad(self._tile(godlo="6.162.34.02.3", crs=None)) == "2000"

    def test_none_crs_falls_back_to_dash_godlo(self):
        from kartograf.cli.download_cmd import _laz_uklad

        assert _laz_uklad(self._tile(crs=None)) == "1992"

    def test_unrecognized_crs_falls_back_to_godlo(self):
        from kartograf.cli.download_cmd import _laz_uklad

        assert _laz_uklad(self._tile(crs="EPSG:2180")) == "1992"

    def test_everything_fails_defaults_2000_with_warning(self, caplog):
        import logging

        from kartograf.cli.download_cmd import _laz_uklad

        with caplog.at_level(logging.WARNING):
            assert _laz_uklad(self._tile(godlo="XYZ99", crs=None)) == "2000"
        assert "XYZ99" in caplog.text
```

W istniejacym tescie sciezek LAZ (np. `test_laz_writes_sidecar_next_to_tile`,
~2585-2625; fixtury maja `crs="PL-2000:S6"`) dodaj asercje segmentu:

```python
        assert "pl_2000_evrf2007" in str(sidecar.parent)
```

- [ ] **Step 2: Uruchom — musza padac**

Run: `.venv/bin/python -m pytest tests/test_cli.py::TestLazUklad -q`
Expected: FAIL, `ImportError: cannot import name '_laz_uklad'`

- [ ] **Step 3: Implementacja**

Nad `_cmd_download_laz` w `kartograf/cli/download_cmd.py` dodaj:

```python
def _laz_uklad(tile) -> str:
    """Uklad poziomy kafla LAZ dla segmentu storage (spec 5.5).

    Kaskada: (1) ``uklad_xy`` kafla (``"PL-2000:*"``/``"PL-1992*"``);
    (2) format godla (kropki=2000, myslniki=1992); (3) fallback ``"2000"``
    z ostrzezeniem — wspolczesne kafle GUGiK sa ciete w ukladzie 2000.
    """
    crs = (tile.crs or "").strip()
    if crs.startswith("PL-2000"):
        return "2000"
    if crs.startswith("PL-1992"):
        return "1992"
    if "." in tile.godlo:
        return "2000"
    if "-" in tile.godlo:
        return "1992"
    import logging

    logging.getLogger(__name__).warning(
        f"Kafel {tile.godlo}: nierozpoznany uklad_xy '{tile.crs}' "
        "— przyjmuje 2000"
    )
    return "2000"
```

W `_cmd_download_laz` zamien (linia ~1125-1126):

```python
    provider = GugikLazProvider(vertical_crs=vertical_crs)
    storage = FileStorage(output_dir, product="laz")
```
na:
```python
    from kartograf.sources.registry import get_source

    provider = GugikLazProvider(vertical_crs=vertical_crs)
    descriptor = get_source("pl.gugik.laz")
    # cache per uklad: jedno zadanie moze zwrocic kafle z obu ukladow
    storages: dict[str, FileStorage] = {}

    def _storage_for(tile) -> FileStorage:
        uklad = _laz_uklad(tile)
        if uklad not in storages:
            storages[uklad] = FileStorage(
                output_dir,
                subdir=descriptor.resolve_subdir(
                    uklad=uklad, vertical_crs=vertical_crs
                ),
            )
        return storages[uklad]
```
a w `_fetch` (linia ~1145) zamien:

```python
        target = storage.get_raw_path(tile.godlo, tile.filename)
```
na:
```python
        target = _storage_for(tile).get_raw_path(tile.godlo, tile.filename)
```

Komunikat podsumowania (`to {output_dir / 'laz'}`) zostaje — to korzen
produktu, nadal prawdziwy.

- [ ] **Step 4: Testy zielone + pelna suita**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "Laz or laz"`
Expected: PASS
Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kartograf/cli/download_cmd.py tests/test_cli.py
git commit -m "feat(cli): LAZ w segmentach laz/pl_<uklad>_<vcrs> wg uklad_xy kafla"
```

---

### Zad. 6: `mosaic_and_crop` — `dst_kwds` (GTiff + CRS dla wejsc ASC)

Arkusze GUGiK to Arc/Info ASCII Grid: BEZ CRS w metadanych i ze sterownikiem
AAIGrid w profilu. `merge` bierze profil z pierwszego zrodla, wiec mozaika
ASC-ow wyszlaby jako ASC bez CRS — wycinek PL potrzebuje wymuszenia
GTiff + `EPSG:2180` w wyniku. Rozszerzenie addytywne, CZ nietkniete.

**Files:**
- Modify: `kartograf/transport/mosaic.py:19-60`
- Test: `tests/test_transport_mosaic.py`

**Interfaces:**
- Consumes: `rasterio.merge.merge(dst_kwds=)` (istniejace).
- Produces: `mosaic_and_crop(inputs, bbox, output_path, *, nodata=None,
  dst_kwds: dict | None = None) -> Path` — `dst_kwds` scalane NAD wpisem
  nodata (np. `{"driver": "GTiff", "crs": "EPSG:2180"}`). Zad. 8 wola z tym
  slownikiem.

- [ ] **Step 1: Napisz padajacy test**

W `tests/test_transport_mosaic.py` dodaj helper (na poziomie modulu, jesli
podobnego nie ma — sprawdz istniejace helpery pliku i uzyj ich zamiast
duplikowac zapis rastra GTiff; ASC-owego na pewno nie ma) i test:

```python
def _write_asc(path, xll, yll, ncols=4, nrows=4, cellsize=1.0, value=1.0):
    """Syntetyczny Arc/Info ASCII Grid (bez CRS — jak arkusze GUGiK)."""
    header = (
        f"ncols {ncols}\nnrows {nrows}\nxllcorner {xll}\nyllcorner {yll}\n"
        f"cellsize {cellsize}\nNODATA_value -9999\n"
    )
    rows = "\n".join(
        " ".join(str(value) for _ in range(ncols)) for _ in range(nrows)
    )
    path.write_text(header + rows + "\n", encoding="ascii")
    return path


def test_dst_kwds_forces_gtiff_and_crs(tmp_path):
    """Wejscia ASC (AAIGrid, brak CRS) -> wynik GTiff z wpisanym CRS."""
    a = _write_asc(tmp_path / "a.asc", 0, 0)
    b = _write_asc(tmp_path / "b.asc", 4, 0)
    out = tmp_path / "out.tif"

    mosaic_and_crop(
        [a, b],
        BBox(1, 1, 7, 3, "EPSG:2180"),
        out,
        nodata=-9999.0,
        dst_kwds={"driver": "GTiff", "crs": "EPSG:2180"},
    )

    with rasterio.open(out) as ds:
        assert ds.driver == "GTiff"
        assert ds.crs is not None and ds.crs.to_epsg() == 2180
        assert ds.nodata == -9999.0
        assert ds.bounds == (1.0, 1.0, 7.0, 3.0)
```

(Dopasuj importy do naglowka pliku — `BBox`, `mosaic_and_crop`, `rasterio`
powinny juz tam byc.)

- [ ] **Step 2: Uruchom — musi padac**

Run: `.venv/bin/python -m pytest tests/test_transport_mosaic.py -q`
Expected: FAIL, `TypeError: mosaic_and_crop() got an unexpected keyword argument 'dst_kwds'`

- [ ] **Step 3: Implementacja**

W `kartograf/transport/mosaic.py` zmien sygnature i wywolanie `merge`:

```python
def mosaic_and_crop(
    inputs: list[Path],
    bbox: BBox,
    output_path: Path,
    *,
    nodata: float | None = None,
    dst_kwds: dict | None = None,
) -> Path:
```

oraz (w miejscu dzisiejszego `merge(...)`):

```python
        kwds: dict = {}
        if nodata is not None:
            kwds["nodata"] = nodata
        if dst_kwds:
            kwds.update(dst_kwds)
        merge(
            sources,
            bounds=(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y),
            nodata=nodata,
            dst_path=str(output_path),
            dst_kwds=kwds or None,
        )
```

Do docstringa funkcji dopisz jedno zdanie: "``dst_kwds`` nadpisuje profil
wyjscia (np. driver/CRS, gdy zrodla ASC ich nie maja)."

- [ ] **Step 4: Testy zielone (mosaic + konsumenci CZ)**

Run: `.venv/bin/python -m pytest tests/test_transport_mosaic.py tests/test_cuzk_client.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kartograf/transport/mosaic.py tests/test_transport_mosaic.py
git commit -m "feat(transport): mosaic_and_crop przyjmuje dst_kwds (GTiff+CRS dla wejsc ASC)"
```

---

### Zad. 7: `kartograf/transform/raster.py` — `warp_to_grid`

Sparametryzowana kopia wzorca ADR-024 (`providers/cuzk/dmr.py::_warp_to_grid`,
linie 500-561) — patrz "Odstepstwa" pkt 2 (dlaczego kopia, nie
wspoldzielenie). Zrodlo wzorca NIE jest modyfikowane.

**Files:**
- Create: `kartograf/transform/raster.py`
- Test: `tests/test_transform_raster.py` (nowy)

**Interfaces:**
- Consumes: `PinnedTransform` (`.gdal_operation()`, `.transform`, `.description`,
  `.accuracy_m`) z `kartograf/transform/crs.py`; `BBox` z `core.sheet_parser`.
- Produces: `warp_to_grid(src_path: Path, dst_path: Path, bbox: BBox,
  pixel_size: float, pinned: PinnedTransform, *, src_crs: str,
  nodata: float) -> None` — siatka wyniku z `bbox`/`pixel_size` (`bbox.crs`
  = uklad docelowy), operacja WYMUSZONA przez `COORDINATE_OPERATION`,
  nodata maskowane po obu stronach, zapis atomowy. Zad. 8 konsumuje.

- [ ] **Step 1: Napisz padajace testy**

Utworz `tests/test_transform_raster.py`:

```python
"""Testy warp_to_grid — lokalna reprojekcja przypieta operacja (wzorzec ADR-024)."""

from unittest.mock import patch

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.transform.crs import TransformPolicy, build_pinned_transform
from kartograf.transform.raster import warp_to_grid

_NODATA = -9999.0
# EPSG:2180, okolice Cieszyna (pas przygraniczny — realny teren celu 5514)
_APEX_2180 = (530050.0, 382050.0)


def _pinned_2180_to(target_crs):
    return build_pinned_transform(
        "EPSG:2180",
        target_crs,
        TransformPolicy(
            min_accuracy_m=1.0, probe_point=_APEX_2180, allow_network_grids=False
        ),
    )


def _write_cone_tif(path, apex, size=300, pixel=1.0):
    """Stozek wokol apex w EPSG:2180 (wzorzec _server_emulator z test_cuzk_dmr)."""
    west = apex[0] - size / 2 * pixel
    north = apex[1] + size / 2 * pixel
    cols, rows = np.meshgrid(np.arange(size), np.arange(size))
    xs = west + (cols + 0.5) * pixel
    ys = north - (rows + 0.5) * pixel
    data = (1000.0 - np.hypot(xs - apex[0], ys - apex[1])).astype("float32")
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": size,
        "height": size,
        "crs": CRS.from_string("EPSG:2180"),
        "transform": from_origin(west, north, pixel, pixel),
        "nodata": _NODATA,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
    return path


def _apex_of(path):
    with rasterio.open(path) as ds:
        data = ds.read(1, masked=True)
        row, col = np.unravel_index(np.argmax(data.filled(-np.inf)), data.shape)
        return ds.xy(int(row), int(col))


class TestWarpToGrid:
    def test_content_lands_where_pyproj_says(self, tmp_path):
        """Regresja TRESCI: wierzcholek < 1 px od wzorca pyproj (2180->5514)."""
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 100, ay - 100, ax + 100, ay + 100, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        gx, gy = _apex_of(dst)
        assert abs(gx - ax) < 1.0, f"E: {gx} vs {ax}"
        assert abs(gy - ay) < 1.0, f"N: {gy} vs {ay}"

    def test_grid_matches_bbox_and_profile(self, tmp_path):
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 40, ax + 50, ay + 40, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 2.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        with rasterio.open(dst) as ds:
            assert (ds.width, ds.height) == (50, 40)
            assert ds.crs.to_epsg() == 5514
            assert ds.nodata == _NODATA
        # zapis atomowy: brak plikow tymczasowych
        assert list(tmp_path.glob("*.warp.tif")) == []

    def test_operation_is_forced(self, tmp_path):
        """COORDINATE_OPERATION musi byc podane GDAL-owi jawnie (ADR-024)."""
        from rasterio.warp import reproject as real_reproject

        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")

        with patch(
            "kartograf.transform.raster.reproject", wraps=real_reproject
        ) as warp:
            warp_to_grid(
                src, tmp_path / "dst.tif", bbox, 1.0, pinned,
                src_crs="EPSG:2180", nodata=_NODATA,
            )

        warp.assert_called_once()
        assert (
            warp.call_args.kwargs["COORDINATE_OPERATION"]
            == pinned.gdal_operation()
        )
```

- [ ] **Step 2: Uruchom — musza padac**

Run: `.venv/bin/python -m pytest tests/test_transform_raster.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'kartograf.transform.raster'`

- [ ] **Step 3: Implementacja**

Utworz `kartograf/transform/raster.py`:

```python
"""
Lokalna reprojekcja rastra na zadana siatke, WYMUSZONA operacja przypieta.

Sparametryzowana kopia wzorca `providers/cuzk/dmr.py::_warp_to_grid`
(ADR-024) dla torow PL. Celowo NIE wspoldzielona z CZ: testy regresyjne
ADR-024 patchuja `kartograf.providers.cuzk.dmr.reproject`, a tor CZ jest
zweryfikowany na zywo — nie ruszamy go tuz przed wydaniem (ADR-027).
"""

import contextlib
import logging
import os
import threading
from pathlib import Path

import rasterio
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

from kartograf.core.sheet_parser import BBox
from kartograf.transform.crs import PinnedTransform

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _quiet_transformer_only_option():
    """Wycisz jeden komunikat GDAL: `COORDINATE_OPERATION` jest opcja
    TRANSFORMERA, a `rasterio.warp.reproject` podaje kwargs takze jako opcje
    warpera — GDAL loguje wtedy ostrzezenie o nieznanej opcji (lustro filtra
    z providers/cuzk/dmr.py)."""
    gdal_logger = logging.getLogger("rasterio._env")

    class _Filter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "COORDINATE_OPERATION" not in record.getMessage()

    _filter = _Filter()
    gdal_logger.addFilter(_filter)
    try:
        yield
    finally:
        gdal_logger.removeFilter(_filter)


def warp_to_grid(
    src_path: Path,
    dst_path: Path,
    bbox: BBox,
    pixel_size: float,
    pinned: PinnedTransform,
    *,
    src_crs: str,
    nodata: float,
) -> None:
    """Zreprojektuj raster na siatke ``bbox``/``pixel_size`` (``bbox.crs``).

    Operacja jest WYMUSZONA (`COORDINATE_OPERATION`) — bez tego GDAL wybiera
    ja sam, poza polityka `transform/crs.py` (zakaz ballparku, limit
    dokladnosci, probe). `src_nodata`/`dst_nodata` maskuja piksele puste,
    zeby nodata nie weszlo do interpolacji. Zapis atomowy: plik docelowy
    powstaje dopiero z gotowej kopii tymczasowej.
    """
    width = max(1, round((bbox.max_x - bbox.min_x) / pixel_size))
    height = max(1, round((bbox.max_y - bbox.min_y) / pixel_size))
    dst_transform = from_origin(bbox.min_x, bbox.max_y, pixel_size, pixel_size)
    tmp_path = dst_path.with_name(
        f"{dst_path.name}.{os.getpid()}_{threading.get_ident()}.warp.tif"
    )
    logger.debug(
        f"Reprojekcja lokalna {src_path.name} -> {bbox.crs}: "
        f"{pinned.description} (dokladnosc {pinned.accuracy_m} m)"
    )
    try:
        with rasterio.open(src_path) as src:
            profile = {
                "driver": "GTiff",
                "dtype": "float32",
                "count": 1,
                "width": width,
                "height": height,
                "crs": CRS.from_string(bbox.crs),
                "transform": dst_transform,
                "nodata": nodata,
            }
            with (
                rasterio.open(tmp_path, "w", **profile) as dst,
                _quiet_transformer_only_option(),
            ):
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_crs=CRS.from_string(src_crs),
                    src_nodata=nodata,
                    dst_crs=CRS.from_string(bbox.crs),
                    dst_nodata=nodata,
                    resampling=Resampling.bilinear,
                    COORDINATE_OPERATION=pinned.gdal_operation(),
                )
        os.replace(tmp_path, dst_path)
    except BaseException:
        dst_path.unlink(missing_ok=True)
        raise
    finally:
        tmp_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Testy zielone + mypy nowego modulu**

Run: `.venv/bin/python -m pytest tests/test_transform_raster.py -q`
Expected: PASS (operacja 2180->5514 jest w PROJ bez siatek zewnetrznych —
KNOWN_PATHS notuje 0,5 m; test dziala offline jak lustrzane testy CZ)
Run: `.venv/bin/python -m mypy kartograf/` — liczba bledow == 32 (baseline 33
minus ten naprawiony w Zad. 2); zaden nowy blad z `transform/raster.py`

- [ ] **Step 5: Commit**

```bash
git add kartograf/transform/raster.py tests/test_transform_raster.py
git commit -m "feat(transform): warp_to_grid — wymuszona operacja przypieta dla torow PL (wzorzec ADR-024)"
```

---

### Zad. 8: `--target-crs` dla PL — walidacje 6.3 + wycinek w trybie bbox

Serce funkcji. Przeplyw (spec 6.1): walidacje -> arkusze przez
DownloadManager normalnie do swoich segmentow (cache; failed = kod 1) ->
`mosaic_and_crop` -> opcjonalny `warp_to_grid` -> sidecar CLI.

**Files:**
- Modify: `kartograf/cli/download_cmd.py` — `_validate_cross_country` (:347-401), `_resolve_pl_sentinels` (:111-166), galaz godlowa `cmd_download` (:625-626 — patrz ostrzezenie w Step 4c), `_download_pl_bbox` (:897-985), nowe funkcje i stale (nad `_download_pl_bbox`)
- Modify: `kartograf/cli/_parser.py:110-117` (help `--target-crs`)
- Test: Create `tests/test_pl_cutout.py`; Modify `tests/test_cli.py:3369-3399` i `:4191-4199`

**Interfaces:**
- Consumes: `warp_to_grid` (Zad. 7), `mosaic_and_crop(dst_kwds=)` (Zad. 6),
  `resolve_subdir` (Zad. 1), `bbox_to_crs` z `providers/cuzk/dmr` (istniejaca,
  generyczna: probkuje krawedzie, buduje wlasna operacje obwiedniowa),
  `build_pinned_transform`/`TransformPolicy`/`TransformError` z `transform/crs`,
  `build_metadata`/`write_sidecar` z `sources/sidecar`,
  `_download_godlo_list` (istniejacy: zwraca `(all_paths, failed_sheets)`;
  sciezki obejmuja tez arkusze skipniete — pelne pokrycie),
  `_print_transform_error` (istniejacy: drukuje blad + Remedium, zwraca 1).
- Produces (nowe symbole w `download_cmd.py`, konsumowane w Zad. 9):
  - `_PL_NODATA = -9999.0`, `_PL_PIXEL_SIZES = {"1m": 1.0, "5m": 5.0}`
  - `@dataclass(frozen=True) class _PlCutout` (pola: `bbox_2180: BBox`,
    `bbox_target: BBox`, `pinned: "PinnedTransform | None"`, `target_path: Path`)
  - `_prepare_pl_cutout(args, bbox: BBox, vertical_crs: str) -> _PlCutout`
    (rzuca `TransformError` — fail-fast przed siecia)
  - `_build_pl_cutout(sheet_paths: list[Path], bbox_2180: BBox,
    bbox_target: BBox, pixel_size: float, pinned, target_path: Path) -> None`
  - `_write_pl_cutout_sidecar(target, *, resolution, vertical_crs,
    bbox_target, target_crs, pinned, parent_request) -> None` (best-effort)
  - `_finalize_pl_cutout(args, cutout: _PlCutout, sheet_paths, parent_request,
    provider) -> int`

- [ ] **Step 1: Napisz padajace testy — `tests/test_pl_cutout.py`**

```python
"""Testy wycinka PL --target-crs (ADR-027): tresc, walidacje, sidecar, przeplyw."""

import argparse
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
import rasterio

from kartograf.cli.commands import main
from kartograf.cli.download_cmd import (
    _build_pl_cutout,
    _download_pl_bbox,
    _prepare_pl_cutout,
)
from kartograf.core.sheet_parser import BBox
from kartograf.transform.crs import (
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)

_NODATA = -9999.0
_APEX = (530050.0, 382050.0)  # EPSG:2180, pas przygraniczny


def _write_sheet_asc(path, west, south, size=100, pixel=1.0, apex=None):
    """Syntetyczny 'arkusz' AAIGrid: stozek wokol apex albo plaski 100.0."""
    cols, rows = np.meshgrid(np.arange(size), np.arange(size))
    xs = west + (cols + 0.5) * pixel
    ys = (south + size * pixel) - (rows + 0.5) * pixel
    if apex is None:
        data = np.full((size, size), 100.0, dtype="float32")
    else:
        data = (1000.0 - np.hypot(xs - apex[0], ys - apex[1])).astype("float32")
    header = (
        f"ncols {size}\nnrows {size}\nxllcorner {west}\nyllcorner {south}\n"
        f"cellsize {pixel}\nNODATA_value {_NODATA}\n"
    )
    body = "\n".join(" ".join(f"{v:.3f}" for v in row) for row in data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body + "\n", encoding="ascii")
    return path


def _pinned_2180_to(target_crs):
    return build_pinned_transform(
        "EPSG:2180",
        target_crs,
        TransformPolicy(
            min_accuracy_m=1.0, probe_point=_APEX, allow_network_grids=False
        ),
    )


class TestBuildPlCutout:
    """Spec 8a-c: regresja tresci, mozaika z nodata, crop bez warpa."""

    def test_target_5514_content_lt_1px(self, tmp_path):
        """Mozaika 2 arkuszy + warp: wierzcholek tam, gdzie mowi pyproj."""
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        west = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000, apex=_APEX)
        east = _write_sheet_asc(tmp_path / "b.asc", 530100, 382000, apex=_APEX)
        bbox_2180 = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX))
        bbox_target = bbox_to_crs(bbox_2180, "EPSG:5514")
        target = tmp_path / "out" / "cut.tif"

        _build_pl_cutout(
            [west, east], bbox_2180, bbox_target, 1.0, pinned, target
        )

        with rasterio.open(target) as ds:
            assert ds.crs.to_epsg() == 5514
            data = ds.read(1, masked=True)
            row, col = np.unravel_index(
                np.argmax(data.filled(-np.inf)), data.shape
            )
            gx, gy = ds.xy(int(row), int(col))
        assert abs(gx - ax) < 1.0, f"E: {gx} vs {ax}"
        assert abs(gy - ay) < 1.0, f"N: {gy} vs {ay}"
        assert list(target.parent.glob("*.mosaic.tif")) == []  # sprzatanie tmp

    def test_nodata_seam_between_sheets(self, tmp_path):
        """Mozaika arkuszy z przerwa: pas nodata w wyniku, nigdy zero."""
        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        b = _write_sheet_asc(tmp_path / "b.asc", 530120, 382000)  # 20 m przerwy
        bbox = BBox(530010, 382010, 530210, 382090, "EPSG:2180")
        target = tmp_path / "cut.tif"

        _build_pl_cutout([a, b], bbox, bbox, 1.0, None, target)

        with rasterio.open(target) as ds:
            assert ds.nodata == _NODATA
            data = ds.read(1)
        # przerwa 530100..530120 = kolumny 90..109 (min_x 530010, piksel 1 m)
        assert (data[:, 90:110] == _NODATA).all()
        assert not (data == 0.0).any()

    def test_target_2180_crop_only(self, tmp_path):
        """EPSG:2180: sam crop — GeoTIFF z wpisanym CRS, zasieg = bbox."""
        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        bbox = BBox(530010, 382010, 530090, 382090, "EPSG:2180")
        target = tmp_path / "cut.tif"

        _build_pl_cutout([a], bbox, bbox, 1.0, None, target)

        with rasterio.open(target) as ds:
            assert ds.crs is not None and ds.crs.to_epsg() == 2180
            assert ds.bounds == (530010.0, 382010.0, 530090.0, 382090.0)


class TestPreparePlCutout:
    def _args(self, tmp_path, **overrides):
        base = dict(
            output=str(tmp_path),
            target_crs="EPSG:5514",
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_target_2180_no_pinned_and_native_name(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = _prepare_pl_cutout(
            self._args(tmp_path, target_crs="EPSG:2180"), bbox, "EVRF2007"
        )
        assert cut.pinned is None
        assert cut.bbox_target is cut.bbox_2180
        assert cut.target_path == (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
            / "530010_382010_530190_382090.tif"
        )

    def test_target_5514_builds_pinned_and_names_in_target(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = _prepare_pl_cutout(self._args(tmp_path), bbox, "EVRF2007")
        assert cut.pinned is not None and cut.pinned.accuracy_m <= 1.0
        assert cut.bbox_target.crs == "EPSG:5514"
        # nazwa niesie wspolrzedne w ukladzie WYNIKU (Krovak: ujemne)
        assert cut.target_path.name.startswith("-")
        assert cut.target_path.parent == (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        )

    def test_vertical_kron86_lands_in_kron86_segment(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = _prepare_pl_cutout(
            self._args(tmp_path, target_crs="EPSG:2180"), bbox, "KRON86"
        )
        assert "pl_1992_1m_kron86" in cut.target_path.parts

    def test_wgs84_bbox_normalized_to_2180(self, tmp_path):
        bbox = BBox(18.60, 49.75, 18.65, 49.77, "EPSG:4326")
        cut = _prepare_pl_cutout(
            self._args(tmp_path, target_crs="EPSG:2180"), bbox, "EVRF2007"
        )
        assert cut.bbox_2180.crs == "EPSG:2180"
        assert 400000 < cut.bbox_2180.min_x < 700000  # rzad wielkosci 2180

    def test_unavailable_operation_raises_transform_error(self, tmp_path):
        """Fail-fast: brak operacji -> TransformError PRZED siecia (spec 6.3)."""
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with patch(
            "kartograf.transform.crs.build_pinned_transform",
            side_effect=TransformUnavailableError("brak operacji", remedy="R"),
        ):
            with pytest.raises(TransformUnavailableError):
                _prepare_pl_cutout(self._args(tmp_path), bbox, "EVRF2007")


_DL = "kartograf.cli.download_cmd"


def _pl_args(tmp_path, **overrides):
    """Namespace jak z argparse dla bezposrednich wywolan _download_pl_bbox."""
    base = dict(
        godlo=None,
        bbox="530010,382010,530190,382090",
        bbox_crs="EPSG:2180",
        geometry=None,
        layer=None,
        scale=None,
        output=str(tmp_path),
        force=False,
        quiet=True,
        vertical_crs=None,
        resolution=None,
        product="nmt",
        system=None,
        country="pl",
        target_crs="EPSG:2180",
        workers=1,
        year=None,
        min_density=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


_PARENT = {
    "bbox": [530010.0, 382010.0, 530190.0, 382090.0],
    "bbox_crs": "EPSG:2180",
    "countries": ["PL"],
}


class TestDownloadPlBboxCutout:
    """Spec 8: przeplyw wycinka na poziomie workera PL (mockowane pobranie)."""

    def _run(self, tmp_path, args, sheets, failed=()):
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch(f"{_DL}.find_sheets_for_bbox", return_value=["N-1", "N-2"]),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_DL}.DownloadManager"),
            patch(
                f"{_DL}._download_godlo_list",
                return_value=(list(sheets), list(failed)),
            ) as dl,
        ):
            rc = _download_pl_bbox(args, bbox, _PARENT)
        return rc, dl

    def test_creates_cutout_and_sidecar(self, tmp_path):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, _ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        target = (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        assert target.exists()
        payload = json.loads(
            (target.parent / f"{target.name}.meta.json").read_text("utf-8")
        )
        assert payload["dataset"] == "pl.gugik.nmt_1m"
        assert payload["horizontal_crs"] == "EPSG:2180"
        assert payload["transform"] is None  # 2180 = sam crop (spec 6.1)
        assert payload["nodata"] == _NODATA
        assert payload["vertical_crs"] == "EPSG:9651"  # EVRF2007-PL, kanal arkuszy
        assert payload["request"]["bbox_crs"] == "EPSG:2180"
        assert payload["extra"]["parent_request"] == _PARENT

    def test_target_5514_sidecar_has_pinned_transform(self, tmp_path):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, _ = self._run(
            tmp_path, _pl_args(tmp_path, target_crs="EPSG:5514"), sheets
        )

        assert rc == 0
        cut_dir = tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        tifs = list(cut_dir.glob("*.tif"))
        assert len(tifs) == 1
        payload = json.loads(
            (cut_dir / f"{tifs[0].name}.meta.json").read_text("utf-8")
        )
        assert payload["horizontal_crs"] == "EPSG:5514"
        assert payload["transform"]["horizontal"].startswith("pinned: ")
        assert payload["request"]["bbox_crs"] == "EPSG:5514"

    def test_failed_sheet_returns_1_and_no_cutout(self, tmp_path):
        """Spec 6.1: wycinek wymaga kompletu pokrycia."""
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, _ = self._run(tmp_path, _pl_args(tmp_path), sheets, failed=["N-2"])

        assert rc == 1
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()

    def test_skip_existing_short_circuits_before_download(self, tmp_path):
        target = (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        target.parent.mkdir(parents=True)
        target.write_bytes(b"II*\x00")
        rc, dl = self._run(tmp_path, _pl_args(tmp_path), sheets=[])

        assert rc == 0
        dl.assert_not_called()

    def test_without_target_crs_behaviour_unchanged(self, tmp_path):
        """Bez flagi: lista arkuszy jak dotad, zero wycinka (spec 6.1)."""
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, _ = self._run(tmp_path, _pl_args(tmp_path, target_crs=None), sheets)

        assert rc == 0
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()


class TestTargetCrsValidations:
    """Spec 6.3 przez main() — czytelne bledy, kod 1."""

    _BBOX = ["--bbox", "530010,382010,530190,382090", "--country", "pl"]

    def test_pl_godlo_rejected(self, tmp_path, capsys):
        rc = main(
            ["download", "N-34-130-D-d-2-4", "--target-crs", "EPSG:2180",
             "-o", str(tmp_path)]
        )
        assert rc == 1
        assert "--bbox/--geometry" in capsys.readouterr().err

    @pytest.mark.parametrize("product", ["nmpt", "orto", "laz"])
    def test_non_nmt_rejected(self, product, tmp_path, capsys):
        rc = main(
            ["download", *self._BBOX, "--product", product,
             "--target-crs", "EPSG:2180", "-o", str(tmp_path)]
        )
        assert rc == 1
        assert "--product nmt" in capsys.readouterr().err

    def test_system_2000_rejected_with_remedy(self, tmp_path, capsys):
        rc = main(
            ["download", *self._BBOX, "--system", "2000",
             "--target-crs", "EPSG:2180", "-o", str(tmp_path)]
        )
        assert rc == 1
        assert "1992" in capsys.readouterr().err
```

- [ ] **Step 2: Zaktualizuj stare testy walidacji w `tests/test_cli.py`**

- `test_pl_godlo_with_target_crs_rejected` (:3369-3381): asercje
  `assert "natywnie" in ...` zamien na `assert "--bbox/--geometry" in ...`
  (komunikat ujednolicony z CZ).
- `test_pl_bbox_with_target_crs_rejected` (:3383-3399): USUN caly test —
  PL bbox + target-crs to teraz legalny przeplyw wycinka; jego pokrycie
  przejmuje `tests/test_pl_cutout.py` (`TestDownloadPlBboxCutout`).
- `test_border_bbox_with_target_crs_rejected_before_any_download`
  (:4191-4199, klasa TestAutoSplitBBox) — PODMIEN na test pozytywny
  (walidacja krzyzowa target-crs znika w Step 4a; zachowaj dekoratory
  patchujace klasy — `mock_cz` jak w sasiednich testach):

```python
    def test_border_bbox_with_target_crs_runs_both_countries(
        self, mock_cz, tmp_path
    ):
        """ADR-027/errata ADR-023: target-crs nie jest juz flaga czeska —
        pogranicze jedna komenda daje dwa wycinki ze wspolnym parent_request."""
        mock_cz.return_value = 0
        with patch(
            "kartograf.cli.download_cmd._download_pl_bbox", return_value=0
        ) as mock_pl:
            result = main(
                self._BORDER
                + ["--target-crs", "EPSG:2180", "--vertical-crs", "EVRF2007",
                   "-o", str(tmp_path)]
            )

        assert result == 0
        mock_cz.assert_called_once()
        mock_pl.assert_called_once()
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent == mock_pl.call_args.args[2]
        # czesc CZ jedzie w ukladzie WYNIKU (cz_crs = target), nie w Krovaku
        assert mock_cz.call_args.kwargs["bbox"].crs == "EPSG:2180"
```

- [ ] **Step 3: Uruchom — nowe musza padac**

Run: `.venv/bin/python -m pytest tests/test_pl_cutout.py -q`
Expected: FAIL, `ImportError: cannot import name '_build_pl_cutout'`

- [ ] **Step 4: Implementacja — walidacje**

(a) `_validate_cross_country` (:347-401) — USUN z checklisty krotke
(main()-owe testy walidacji z tego zadania ida trybem bbox przez
`_dispatch_area`, wiec stara blokada musi zniknac JUZ TERAZ, nie w Zad. 9):

```python
        (
            "PL" in countries and getattr(args, "target_crs", None) is not None,
            "--target-crs dziala tylko dla CZ — PL pobiera natywnie w EPSG:2180",
        ),
```

(b) `_resolve_pl_sentinels` (`kartograf/cli/download_cmd.py:111-166`):

USUN blok:

```python
    if getattr(args, "target_crs", None) is not None:
        print(
            "Error: --target-crs dziala tylko dla CZ — PL pobiera natywnie w EPSG:2180",
            file=sys.stderr,
        )
        return 1
```

DODAJ przed podstawieniem domyslnych (`args.resolution = ... or "1m"`),
obok istniejacych walidacji par produkt/flaga:

```python
    target_crs = getattr(args, "target_crs", None)
    if target_crs is not None and product in ("nmpt", "orto", "laz"):
        print(
            "Error: --target-crs w 0.7.0 dziala tylko z --product nmt "
            "(nmpt/orto — etap 2; laz to chmura punktow, nie raster)",
            file=sys.stderr,
        )
        return 1
    if target_crs is not None and getattr(args, "system", None) == "2000":
        print(
            "Error: --target-crs nie dziala z --system 2000 — bbox "
            "wielostrefowy dalby arkusze w roznych CRS (2176-2179), "
            "mozaika miedzystrefowa to etap 2; uzyj domyslnego --system 1992",
            file=sys.stderr,
        )
        return 1
```

Zaktualizuj docstring funkcji: usun ze zdania o walidacjach sugestie
"target-crs tylko CZ", dopisz "oraz wylaczen --target-crs (produkt != nmt,
system 2000 — ADR-027)".

(c) `cmd_download`, galaz GODLOWA PL — DODAJ.

**UWAGA na miejsce wstawienia (zweryfikowane 2026-08-28):** chodzi o blok
`if _resolve_pl_sentinels(args): return 1` WEWNATRZ `if has_godlo:`
(download_cmd.py:625-626, wciecie 8 spacji), a NIE o ktorykolwiek z dalszych
`return` w okolicy 632-634 — tam zaczyna sie galaz `if has_geometry:`.
Wstawienie w zla galaz odrzucaloby `--target-crs` dla KAZDEGO zadania
`--geometry` (takze CZ) i wywrocilo zielony dzis
`tests/test_cli.py::TestCountryDispatch::test_geometry_cz_target_crs_in_one_hop`
oraz cale Zad. 9. Zakotwicz sie na unikalnym snippecie:

```python
        if _resolve_pl_sentinels(args):
            return 1
```
i dopisz BEZPOSREDNIO pod nim (to samo wciecie):

```python
        if getattr(args, "target_crs", None) is not None:
            print(
                "Error: --target-crs dziala tylko z --bbox/--geometry; "
                "tryb godlowy dostarcza dane natywne 1:1",
                file=sys.stderr,
            )
            return 1
```

(Ten sam tekst co ValidationError CZ — spec 6.3 pkt 1.)

(d) `kartograf/cli/_parser.py:110-117` — nowy help `--target-crs`:

```python
    download_parser.add_argument(
        "--target-crs",
        choices=["EPSG:2180", "EPSG:5514", "EPSG:3045"],
        default=None,
        help="Reprojekcja wyniku, wykonywana lokalnie przypieta operacja "
        "(tylko tryb --bbox/--geometry, tylko --product nmt; PL: jeden "
        "scalony wycinek GeoTIFF, CZ: wycinek exportImage)",
    )
```

- [ ] **Step 5: Implementacja — wycinek**

W `kartograf/cli/download_cmd.py`:

(a) Importy na gorze pliku — dodaj:

```python
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kartograf.transform.crs import PinnedTransform
```

(b) Nad `_download_pl_bbox` dodaj stale i cztery funkcje:

```python
# Wycinek PL --target-crs (ADR-027): nodata arkuszy ASC GUGiK i piksel siatki.
_PL_NODATA = -9999.0
_PL_PIXEL_SIZES = {"1m": 1.0, "5m": 5.0}


@dataclass(frozen=True)
class _PlCutout:
    """Przygotowany (fail-fast) kontekst wycinka PL --target-crs."""

    bbox_2180: BBox
    bbox_target: BBox
    pinned: "PinnedTransform | None"  # None dla EPSG:2180 (sam crop)
    target_path: Path


def _prepare_pl_cutout(
    args: argparse.Namespace, bbox: BBox, vertical_crs: str
) -> _PlCutout:
    """Fail-fast przygotowanie wycinka: operacja, bbox-y i sciezka wyniku.

    Rzuca ``TransformError``, gdy dla pary EPSG:2180 -> ``--target-crs``
    nie ma przypietej operacji — PRZED jakimkolwiek ruchem sieciowym
    (ADR-024/ADR-027). ``vertical_crs`` to wartosc FAKTYCZNA providera
    (po korekcie 5m=>EVRF2007 w fabryce), nie surowa flaga CLI.

    Wycinek jest zawsze GeoTIFF (``.tif``) — ``default_extension``
    deskryptora (``.asc``) dotyczy arkuszy, nie wycinka.
    """
    from pyproj import CRS

    from kartograf.core.geometry import _transform_bbox
    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.sources.registry import get_source
    from kartograf.transform.crs import TransformPolicy, build_pinned_transform

    if bbox.crs == "EPSG:2180":
        bbox_2180 = bbox
    else:
        # uklady czeskie opuszczaja Krovaka wczesniej, przypieta operacja
        # (_country_bbox/_dispatch_area); tu zostaja PL/WGS84 — swiadomie
        # domyslny transformer, jak w reszcie przeplywu PL
        bbox_2180 = _transform_bbox(
            bbox.min_x,
            bbox.min_y,
            bbox.max_x,
            bbox.max_y,
            CRS.from_user_input(bbox.crs),
            "EPSG:2180",
        )

    pinned = None
    bbox_target = bbox_2180
    if args.target_crs != "EPSG:2180":
        center = (
            (bbox_2180.min_x + bbox_2180.max_x) / 2,
            (bbox_2180.min_y + bbox_2180.max_y) / 2,
        )
        # polityka jak _HORIZONTAL_POLICY toru CZ + probe w srodku zadania
        # (siatka nie pokrywajaca obszaru danych odpada od razu)
        pinned = build_pinned_transform(
            "EPSG:2180",
            args.target_crs,
            TransformPolicy(
                min_accuracy_m=1.0,
                probe_point=center,
                allow_network_grids=False,
            ),
        )
        bbox_target = bbox_to_crs(bbox_2180, args.target_crs)

    key = "pl.gugik.nmt_5m" if args.resolution == "5m" else "pl.gugik.nmt_1m"
    subdir = get_source(key).resolve_subdir(uklad="1992", vertical_crs=vertical_crs)
    coords = "_".join(
        format(v, ".10g")
        for v in (
            bbox_target.min_x,
            bbox_target.min_y,
            bbox_target.max_x,
            bbox_target.max_y,
        )
    )
    target_path = Path(args.output) / subdir / "bbox" / f"{coords}.tif"
    return _PlCutout(bbox_2180, bbox_target, pinned, target_path)


def _build_pl_cutout(
    sheet_paths: list[Path],
    bbox_2180: BBox,
    bbox_target: BBox,
    pixel_size: float,
    pinned: "PinnedTransform | None",
    target_path: Path,
) -> None:
    """Zszyj arkusze, przytnij do ``bbox_2180``; opcjonalny lokalny warp.

    Mozaika wymusza GTiff + EPSG:2180 (arkusze ASC nie niosa CRS).
    ``pinned is None`` = cel EPSG:2180: sam crop (atomowy ``os.replace``).
    """
    import os
    import threading

    from kartograf.transport.mosaic import mosaic_and_crop

    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_path.with_name(
        f"{target_path.name}.{os.getpid()}_{threading.get_ident()}.mosaic.tif"
    )
    try:
        mosaic_and_crop(
            sheet_paths,
            bbox_2180,
            tmp,
            nodata=_PL_NODATA,
            dst_kwds={"driver": "GTiff", "crs": "EPSG:2180"},
        )
        if pinned is None:
            os.replace(tmp, target_path)
        else:
            from kartograf.transform.raster import warp_to_grid

            warp_to_grid(
                tmp,
                target_path,
                bbox_target,
                pixel_size,
                pinned,
                src_crs="EPSG:2180",
                nodata=_PL_NODATA,
            )
    except BaseException:
        target_path.unlink(missing_ok=True)
        raise
    finally:
        tmp.unlink(missing_ok=True)


def _write_pl_cutout_sidecar(
    target: Path,
    *,
    resolution: str,
    vertical_crs: str,
    bbox_target: BBox,
    target_crs: str,
    pinned: "PinnedTransform | None",
    parent_request: dict | None,
) -> None:
    """Best-effort sidecar wycinka PL (blad nie przerywa pobrania).

    ``capability="sheet_files"``: dane pochodza z arkuszy OpenData — kanal
    ``bbox_raster`` nie istnieje dla 5m, a dla 1m deklaruje wylacznie KRON86
    (ADR-027, odstepstwo od litery spec 6.1 pkt 5).
    """
    import logging

    try:
        from kartograf.sources.registry import get_source
        from kartograf.sources.sidecar import build_metadata, write_sidecar

        key = "pl.gugik.nmt_5m" if resolution == "5m" else "pl.gugik.nmt_1m"
        meta = build_metadata(
            get_source(key),
            request={
                "bbox": [
                    bbox_target.min_x,
                    bbox_target.min_y,
                    bbox_target.max_x,
                    bbox_target.max_y,
                ],
                "bbox_crs": target_crs,
            },
            vertical_crs=vertical_crs,
            capability="sheet_files",
            nodata=_PL_NODATA,
            extra={"parent_request": parent_request} if parent_request else None,
        )
        meta.horizontal_crs = target_crs
        meta.transform = (
            {"horizontal": f"pinned: {pinned.description} ({pinned.accuracy_m} m)"}
            if pinned is not None
            else None
        )
        write_sidecar(target, meta)
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        logging.getLogger(__name__).warning(
            f"Nie udalo sie zapisac sidecara dla {target}: {e}"
        )


def _finalize_pl_cutout(
    args: argparse.Namespace,
    cutout: _PlCutout,
    sheet_paths: list[Path],
    parent_request: dict | None,
    provider,
) -> int:
    """Zbuduj wycinek z pobranych arkuszy i zapisz sidecar (ADR-027)."""
    from kartograf.transform.crs import TransformError

    if not args.quiet:
        print(
            f"Building cutout from {len(sheet_paths)} sheets "
            f"({args.target_crs})..."
        )
    try:
        _build_pl_cutout(
            sheet_paths,
            cutout.bbox_2180,
            cutout.bbox_target,
            _PL_PIXEL_SIZES[args.resolution],
            cutout.pinned,
            cutout.target_path,
        )
    except (ValidationError, TransformError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    _write_pl_cutout_sidecar(
        cutout.target_path,
        resolution=args.resolution,
        vertical_crs=getattr(provider, "vertical_crs", args.vertical_crs),
        bbox_target=cutout.bbox_target,
        target_crs=args.target_crs,
        pinned=cutout.pinned,
        parent_request=parent_request,
    )
    if not args.quiet:
        print(f"Downloaded to {cutout.target_path}")
    return 0
```

(c) `_download_pl_bbox` — wpleç wycinek. Po bloku tworzacym
`provider, storage = _create_provider_and_storage(...)` (a PRZED
`manager = DownloadManager(...)`) dodaj — oraz przenies `skip_existing =
not args.force` nad ten blok:

```python
    cutout: _PlCutout | None = None
    if args.target_crs is not None:
        from kartograf.transform.crs import TransformError

        try:
            # fail-fast: operacja przypieta budowana PRZED jakakolwiek siecia
            cutout = _prepare_pl_cutout(
                args, bbox, getattr(provider, "vertical_crs", vertical_crs)
            )
        except TransformError as e:
            return _print_transform_error(e)
        if skip_existing and cutout.target_path.exists():
            if not args.quiet:
                print(f"Skipped - already exists at {cutout.target_path}")
            return 0
```

a koncowke funkcji (od `# komunikat wypisal juz _download_godlo_list...`)
zamien na:

```python
    # komunikat wypisal juz `_download_godlo_list` — tu zostaje kod wyjscia
    if failed_sheets:
        # z --target-crs: wycinek wymaga kompletu pokrycia (spec 6.1 pkt 1)
        return 1

    if cutout is not None:
        return _finalize_pl_cutout(args, cutout, all_paths, parent_request, provider)

    return 0
```

Do docstringa `_download_pl_bbox` dopisz akapit:

```
    Z ``--target-crs`` (ADR-027) arkusze pobieraja sie normalnie do swoich
    segmentow (dzialaja jako cache), a wynikiem jest JEDEN scalony wycinek
    ``nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif``.
```

- [ ] **Step 6: Testy zielone**

Run: `.venv/bin/python -m pytest tests/test_pl_cutout.py tests/test_cli.py -q`
Expected: PASS (w tym podmieniony test graniczny i caly TestAutoSplitBBox —
usuniecie blokady krzyzowej nie psuje testow `test_auto_with_*_resolves_to_pl`,
bo `_pl_only_flags` nigdy nie zawieral target-crs)
Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 7: Lint + mypy**

Run: `.venv/bin/python -m ruff check kartograf/ tests/ && .venv/bin/python -m ruff format --check kartograf/ tests/`
Run: `.venv/bin/python -m mypy kartograf/` — bledy == baseline 32

- [ ] **Step 8: Commit**

```bash
git add kartograf/cli/download_cmd.py kartograf/cli/_parser.py tests/test_pl_cutout.py tests/test_cli.py
git commit -m "feat(cli): --target-crs dla PL — scalony wycinek mozaika+pinned warp w trybie bbox (ADR-027)"
```

---

### Zad. 9: Wycinek w trybie geometry

Odblokowanie auto-split (usuniecie blokady krzyzowej + test graniczny
"dwa wycinki, wspolny parent_request") wykonalo juz Zad. 8 — tu zostaje
symetria trybu `--geometry`.

**Files:**
- Modify: `kartograf/cli/download_cmd.py` — `_dispatch_area` (:497-498), `_download_pl_geometry` (:1533-1620)
- Test: `tests/test_pl_cutout.py` (nowa klasa `TestGeometryCutout`)

**Interfaces:**
- Consumes: `_prepare_pl_cutout`/`_finalize_pl_cutout`/`_PlCutout` (Zad. 8),
  `find_sheets_for_geometry` (istniejaca, import lokalny z `core.geometry`),
  `part` z `_dispatch_area` (bbox czesci PL, przyciety pod auto).
- Produces: `_download_pl_geometry(args, filepath, parent_request,
  bbox: BBox | None = None) -> int` (nowy addytywny parametr) — z
  `--target-crs` buduje wycinek croppowany po obwiedni `bbox`; obszary
  miedzy rozlacznymi obiektami geometrii wypelnia nodata (spec 6.1 + 6.2).

- [ ] **Step 1: Napisz padajace testy**

Do `tests/test_pl_cutout.py` dodaj:

```python
class TestGeometryCutout:
    def test_geometry_mode_builds_cutout(self, tmp_path):
        from kartograf.cli.download_cmd import _download_pl_geometry

        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        geom = tmp_path / "area.gpkg"
        geom.write_bytes(b"stub")  # sciezka nieuzywana: discovery zamockowane
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        args = _pl_args(tmp_path, bbox=None, geometry=str(geom))

        with (
            # import lokalny w _download_pl_geometry -> patch u zrodla
            # (ta sama konwencja co testy geometry w test_cli.py)
            patch(
                "kartograf.core.geometry.find_sheets_for_geometry",
                return_value=["N-1", "N-2"],
            ),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_DL}.DownloadManager"),
            patch(
                f"{_DL}._download_godlo_list", return_value=(sheets, [])
            ),
        ):
            rc = _download_pl_geometry(args, geom, _PARENT, bbox=bbox)

        assert rc == 0
        assert (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
            / "530010_382010_530190_382090.tif"
        ).exists()
```

- [ ] **Step 1b: Napisz test DWOCH wycinkow na pograniczu (kryterium 13.6)**

Test graniczny z Zad. 8 dowodzi dyspozycji i wspoldzielenia `parent_request`,
ale patchuje OBA workery — nie powstaje w nim ani jeden plik. Kryterium 13.6
("dwa wycinki PL+CZ, wspolny parent_request, kod 0") wymaga testu, w ktorym
oba tory realnie zapisuja wynik. Dodaj do `tests/test_pl_cutout.py`:

```python
class TestBorderTwoCutouts:
    """Spec 13.6 / 8(e): jedna komenda -> dwa wycinki w tym samym ukladzie."""

    # maly prostokat przecinajacy PROSTOKATNE obwiednie obu krajow
    # (CZ: 12.09..18.86E / 48.55..51.06N, PL: 14.07..24.20E / 49.00..54.90N)
    _BBOX = "18.80,49.70,18.801,49.7005"

    def _cz_provider(self):
        """Stub CuzkDmrProvider: zapisuje plik i udaje operacje przypieta."""
        provider = Mock()
        provider.descriptor_key = "cz.cuzk.dmr4g"
        provider.resolution = "5m"
        provider.vertical_crs = "EVRF2007"
        provider.vertical_transform = None

        def fake_horizontal(target_crs):
            pinned = Mock()
            pinned.description = f"S-JTSK to ETRS89 (3) -> {target_crs}"
            pinned.accuracy_m = 0.5
            return pinned

        provider.horizontal_transform.side_effect = fake_horizontal

        def fake_bbox(bbox, target, **kw):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"II*\x00dane")
            return target

        provider.download_bbox.side_effect = fake_bbox
        return provider

    def test_two_cutouts_share_parent_request(self, tmp_path):
        from pyproj import CRS

        from kartograf.core.geometry import _transform_bbox

        # jeden syntetyczny arkusz pokrywajacy polska czesc zadania
        b = _transform_bbox(
            18.80, 49.70, 18.801, 49.7005,
            CRS.from_user_input("EPSG:4326"), "EPSG:2180",
        )
        sheet = _write_sheet_asc(
            tmp_path / "sheet.asc",
            b.min_x - 100, b.min_y - 100, size=60, pixel=5.0,
        )
        provider = SimpleNamespace(vertical_crs="EVRF2007")

        with (
            patch(
                "kartograf.providers.cuzk.create_dmr_provider",
                return_value=self._cz_provider(),
            ),
            patch(f"{_DL}.find_sheets_for_bbox", return_value=["N-34-130-D"]),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_DL}.DownloadManager"),
            patch(f"{_DL}._download_godlo_list", return_value=([sheet], [])),
        ):
            rc = main(
                ["download", "--bbox", self._BBOX, "--bbox-crs", "EPSG:4326",
                 "--resolution", "5m", "--target-crs", "EPSG:2180",
                 "--vertical-crs", "EVRF2007", "-o", str(tmp_path)]
            )

        assert rc == 0
        pl = list((tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox").glob("*.tif"))
        cz = list((tmp_path / "nmt" / "cz_dmr4g_evrf2007" / "bbox").glob("*.tif"))
        assert len(pl) == 1 and len(cz) == 1
        parents = []
        for f in (*pl, *cz):
            payload = json.loads(
                (f.parent / f"{f.name}.meta.json").read_text("utf-8")
            )
            assert payload["horizontal_crs"] == "EPSG:2180"
            parents.append(payload["extra"]["parent_request"])
        assert parents[0] == parents[1]
        assert parents[0]["countries"] == ["CZ", "PL"]
```

UWAGI wykonawcze: (1) `--resolution 5m` jest celowe — `1m` rozstrzygaloby
`--country auto` do samego PL (`_pl_only_flags`), a przy 5 m plik wynikowy
jest maly; (2) `5m` wymusza EVRF2007 po obu stronach, wiec segmenty sa
przewidywalne; (3) jesli patch `create_dmr_provider` nie zadziala pod tym
sciezkowaniem, uzyj tego, ktorego uzywa `tests/test_cli.py`
(`_CZ_FACTORY_PATCH = "kartograf.providers.cuzk.create_dmr_provider"`).

- [ ] **Step 2: Uruchom — musza padac**

Run: `.venv/bin/python -m pytest tests/test_pl_cutout.py::TestGeometryCutout tests/test_pl_cutout.py::TestBorderTwoCutouts -q`
Expected: FAIL — `TypeError: _download_pl_geometry() got an unexpected keyword
argument 'bbox'` (geometry) oraz brak pliku PL w segmencie (border: bez
przekazania obwiedni czesci PL wycinek nie powstaje w oczekiwanym miejscu).
Jesli `TestBorderTwoCutouts` przechodzi juz po Zad. 8 — dobrze, zostaw go
jako regresje i przejdz dalej.

- [ ] **Step 3: Implementacja**

(a) `_download_pl_geometry` — sygnatura:

```python
def _download_pl_geometry(
    args: argparse.Namespace,
    filepath: Path,
    parent_request: dict,
    bbox: BBox | None = None,
) -> int:
```

Do docstringa dodaj: "``bbox`` — obwiednia zadania PL (przycieta pod auto);
potrzebna wylacznie dla wycinka ``--target-crs``: crop idzie po tej
obwiedni, a obszary miedzy rozlacznymi obiektami wypelnia nodata."

Wpleç wycinek dokladnie jak w `_download_pl_bbox` (Zad. 8 Step 5c):
- przenies `skip_existing = not args.force` przed tworzenie providera,
- po `provider, storage = _create_provider_and_storage(...)` ten sam blok
  `cutout = ...` — z jedna roznica: `_prepare_pl_cutout(args, bbox, ...)`
  dostaje parametr `bbox` funkcji (nie obwiednie liczona na nowo),
- koncowka: `if failed_sheets: return 1` + `if cutout is not None: return
  _finalize_pl_cutout(args, cutout, all_paths, parent_request, provider)`.

(b) `_dispatch_area` (:497-498) — przekaz obwiednie czesci PL:

```python
            if filepath is not None:
                rc = _download_pl_geometry(pl_args, filepath, parent_request, bbox=part)
```

- [ ] **Step 4: Testy zielone + pelna suita**

Run: `.venv/bin/python -m pytest tests/test_pl_cutout.py tests/test_cli.py -q`
Expected: PASS (TestAutoSplitGeometry bez zmian — nowy parametr jest
addytywny, stare wywolania pozycyjne dzialaja)
Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kartograf/cli/download_cmd.py tests/test_pl_cutout.py
git commit -m "feat(cli): wycinek --target-crs takze w trybie --geometry (ADR-027)"
```

---

### Zad. 10: `docs/ARCHITECTURE.md` (nowy, kanoniczny)

**Files:**
- Create: `docs/ARCHITECTURE.md`

**Interfaces:** dokument-kontrakt; README/CLAUDE.md/SCOPE (Zad. 11) beda
ODSYLAC do jego sekcji 3 zamiast duplikowac tabele ukladu `data/`.

- [ ] **Step 1: Napisz dokument wg konspektu spec 10.1**

Struktura obowiazkowa (naglowki `##` numerowane 1-6). Tresc per sekcja:

**Naglowek:** tytul "Architektura Kartografa", data, zdanie "Dokument
kanoniczny: README/CLAUDE.md/SCOPE odsylaja tutaj; przy sprzecznosci
rozstrzyga ARCHITECTURE.md + DECISIONS.md."

**1. Przeglad i zasady projektowe** — 4 akapity (po 3-5 zdan):
deskryptory-jako-dane (zero IO przy imporcie; `sources/registry.py` zrodlem
prawdy dla subdir/rozszerzen/licencji/capabilities); sidecar obowiazkowy
przy KAZDYM udanym pobraniu (`<plik>.meta.json`, schema `kartograf-meta/1`,
pisza go managery/CLI — nigdy providery; blad zapisu = warning); polityka
transformacji ADR-024 (ballpark ban, `TransformerGroup(allow_ballpark=
False)`, filtr accuracy, probe, przypiete operacje + wymuszanie
`COORDINATE_OPERATION` w warpach, pulapka osi northing-first/axisswap);
brak scalania miedzykrajowego (kontrakt z Hydrografem: Kartograf dostarcza
osobne pliki per kraj + sidecary, scala konsument).

**2. Warstwy i zaleznosci modulow** — diagram tekstowy (ASCII) warstw:

```
cli ──> download / landcover / hydrology
download ──> providers, sources, transport, transform, core, cache
landcover ──> providers, sources, core, cache
providers ──> sources, transport, transform, transport/mosaic, core, cache, auth
transport / transform / sources ──> core
core ──> (nic wewnetrznego)
```

plus lista jednozdaniowa modulow (skopiuj z drzewa w CLAUDE.md "Struktura
modulow", z aktualizacja: `transform/raster.py`, szablony w descriptor).

**3. Kontrakty danych** — trzy podsekcje:
- `SourceDescriptor` — pola + SZABLONY `storage_subdir` (tabela wartosci
  z rejestru, `resolve_subdir`, kto wypelnia ktory placeholder: `{vcrs}`
  konstruktor FileStorage / resolve_subdir, `{uklad}` FileStorage per godlo
  albo jawnie CLI LAZ/wycinek).
- Schema sidecara `kartograf-meta/1` — tabela pol (przenies/rozszerz tabele
  z README:136-147, dodaj wiersz o wycinku PL: `capability` kanalu
  sheet_files, `transform.horizontal="pinned: ..."`).
- **Kanoniczna tabela ukladu `data/`** — wklej drzewo ze spec sekcji 3
  (blok ```...``` z `data/nmt/pl_1992_1m_evrf2007/...` itd.), reguly
  segmentow (4 punkty ze spec sekcji 3 "Reguly") ORAZ tabele migracji
  0.6.x -> 0.7.0 (8 wierszy ze spec sekcji 3) z nota o `<vcrs>` z sidecara
  i plikach bez sidecarow (re-download).
- `extra.parent_request` — akapit: wspolny klucz grupowania plikow jednego
  zadania `--bbox`/`--geometry` (takze transgranicznego); to po nim
  konsument (Hydrograf, przyszly `find_downloaded`) skleja wynik.

**4. Przeplywy per produkt** — po JEDNYM akapicie + sciezka wynikowa dla:
godlo PL (parser -> WMS skorowidz -> OpenData -> `nmt/pl_1992_1m_evrf2007/
N-34/.../*.asc` + sidecar); bbox PL bez target-crs (find_sheets -> lista
arkuszy, wiele plikow); bbox PL z `--target-crs` (arkusze jako cache ->
mosaic_and_crop -> warp_to_grid -> `nmt/pl_1992_<res>_<vcrs>/bbox/
<coords>.tif`, failed arkusz = kod 1); CZ godlo (TM33 exportImage natywnie
5514 + lokalny warp na siatke 3045 / SM5 openzu -> `nmt/cz_dmr5g_<vcrs>/
302/5550/302_5550.tif`); CZ bbox (`.../bbox/<coords>.tif`, kafelkowanie
15000x4100); LAZ (WFS discovery -> kafle -> `laz/pl_<uklad>_<vcrs>/...`,
uklad per kafel z `uklad_xy`); landcover (bez zmian, wlasny `--output`).

**5. Jak dodac nowe zrodlo/kraj** — checklist na przykladzie DE
(Brandenburgia DGM1): (1) deskryptor w `sources/registry.py`
(`storage_subdir="nmt/de_bb_dgm1_{vcrs}"` — zero zmian w kodzie sciezek);
(2) `CountryProfile` DE (extent + dataset_keys); (3) parser godel/kafli
w `core/` + rejestracja w `parser_registry` (jesli kraj ma system godel);
(4) provider w `providers/de/` (silnik sterowany deskryptorem, wzor
`CuzkClient`); (5) dyspozycja CLI (`_countries_for_bbox` bierze kraje
z rejestru automatycznie); (6) testy: fixtury z realnych odpowiedzi,
deskryptor-provider consistency, KNOWN_PATHS dla transformacji.

**6. Indeks ADR** — lista `ADR-001`..`ADR-027`: numer + tytul (skopiuj
naglowki z `docs/DECISIONS.md` — pelna lista jest w raporcie rekonesansu,
linie DECISIONS.md:8-925) + jedno zdanie streszczenia kazdy; przy ADR-013
i ADR-017 dopisek "(zastapiona/domknieta przez ADR-026)".

- [ ] **Step 2: Weryfikacja odsylaczy**

Run: `grep -n "ARCHITECTURE" docs/ARCHITECTURE.md README.md CLAUDE.md docs/SCOPE.md`
Expected: plik istnieje; odsylacze z innych plikow doda Zad. 11.
Przejrzyj tresc: sekcja 3 zawiera drzewo `data/` i tabele migracji 1:1 ze
spec (zadnych rozbieznosci wartosci segmentow z rejestrem — porownaj
z `kartograf/sources/registry.py`).

- [ ] **Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs(architecture): kanoniczny opis warstw, kontraktow i ukladu data/ (ADR-026/027)"
```

---

### Zad. 11: Pozostala dokumentacja — ADR-y, CHANGELOG, CLAUDE, README, SCOPE, PROGRESS

**Files:**
- Modify: `docs/DECISIONS.md` (ADR-026, ADR-027, korekty ADR-013/017, addendum ADR-023)
- Modify: `docs/CHANGELOG.md:8-518` (sekcja [0.7.0] Unreleased)
- Modify: `CLAUDE.md`, `README.md`, `docs/SCOPE.md`, `docs/PROGRESS.md`

**Interfaces:** teksty ponizej sa TRESCIA docelowa (wklej, dostosowujac
wciecia otoczenia); tabela migracji identyczna jak w ARCHITECTURE.md (Zad. 10).

- [ ] **Step 1: `docs/DECISIONS.md`**

(a) Na koncu rejestru dodaj. **Miejsce wstawienia: PRZED linia 923
(`<!-- Szablon nowej decyzji:`)** — naglowek `## ADR-XXX` z linii 925 lezy
JUZ WEWNATRZ tego komentarza HTML, wiec wstawienie "przed ADR-XXX" pogrzebaloby
oba nowe ADR-y w komentarzu (niewidoczne w renderze i w indeksie z Zad. 10):

```markdown
## ADR-026: Uklad data/ per produkt — segmenty i szablony w deskryptorach

**Data:** 2026-08-28
**Status:** Przyjeta (domyka odroczenie z ADR-017; zastepuje uklad ADR-013)

**Kontekst:** Plaski uklad `data/` nie kodowal kraju ani ukladow (`nmt_1m/`
obok `cz_dmr5g/`; PL-2000 dzielil katalog z PL-1992; ten sam arkusz w KRON86
i EVRF2007 mial JEDNA sciezke — drugie pobranie: skip albo nadpisanie).
Federacja niemiecka (kilkanascie zrodel DEM, research 2026-08-10) rozsadzilaby
korzen katalogu.

**Decyzja (D1-D8 zatwierdzone przez uzytkownika 2026-08-28):**
`data/<produkt>/<segment>/...`, segment = `<kraj>_<uklad>[_<wariant>][_<vcrs>]`
lowercase. Uklad poziomy PL zawsze jawnie (`pl_1992`/`pl_2000`); pionowy
zawsze jawnie (`kron86`/`evrf2007`/`bpv`; jedynym produktem bez pionowego
jest orto); CZ bez dopisku poziomego (nazwa datasetu wyznacza uklad 1:1,
natywnie 5514); rozdzielczosc tylko tam, gdzie jest parametrem API
(NMT/NMPT). `SourceDescriptor.storage_subdir` staje sie SZABLONEM
z placeholderami `{uklad}`/`{vcrs}`; `resolve_subdir()` wypelnia przez
`str.replace` (czesciowe wypelnienie legalne, vcrs lowercased), FileStorage
rozwiazuje `{uklad}` per godlo (regula `path_parts`: kropki=2000, inaczej
1992) i waliduje zero klamer (`ValidationError` z nazwa wymiaru). Wycinki
`--bbox` lada w `<segment>/bbox/<coords><ext>` (konwencja d68be23, wspolna
PL/CZ). `landcover/` bez zmian.

**Konsekwencje:** BREAKING na dysku (tabela migracji: CHANGELOG 0.7.0
i ARCHITECTURE.md sekcja 3). Nowe zrodlo (np. DE) = nowy wpis deskryptora,
zero zmian w kodzie sciezek. Konsument czytajacy `storage_subdir` wprost
dostaje szablon — pole bylo de facto wewnetrzne; uzyj `resolve_subdir()`.
FileStorage: nowy parametr `vertical_crs` (default "EVRF2007"); nieznany
`product` nadal passthrough (np. testowe `nmt_2000_1m`).

## ADR-027: --target-crs dla PL — scalony wycinek bbox (mozaika + pinned warp)

**Data:** 2026-08-28
**Status:** Przyjeta (errata do ADR-023: target-crs przestaje byc flaga czeska)

**Kontekst:** `--target-crs` istnial tylko dla CZ; scenariusz "obszar
zainteresowania w jednym kraju + dociagniecie danych z drugiego" wymagal
warpa PL po stronie konsumenta — asymetria bez powodu innego niz historia
implementacji.

**Decyzja:** `--bbox`/`--geometry` + `--country pl` + `--target-crs`
(produkt nmt) zwraca JEDEN plik `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`:
arkusze pobieraja sie normalnie do swoich segmentow (dzialaja jako cache,
skip-existing standardowo), potem `mosaic_and_crop` (GTiff+CRS wymuszone —
ASC ich nie niesie) + lokalny warp `warp_to_grid` z WYMUSZONA operacja
`PinnedTransform.gdal_operation()` (maszyneria i pulapki ADR-024, w tym
axisswap dla celow northing-first). `EPSG:2180` = sam crop
(`transform: null`). Fail-fast operacji przed siecia; kazdy failed arkusz =
blad calosci (kod 1). Nazwa pliku niesie wspolrzedne w ukladzie WYNIKU.
Sidecar pisze CLI: `horizontal_crs=target`, `transform.horizontal=
"pinned: ..."`, `nodata=-9999`, `extra.parent_request`; kanal
`sheet_files` (fakt: dane z arkuszy OpenData — kanal `bbox_raster` nie
istnieje dla 5m, a dla 1m deklaruje wylacznie KRON86). Wylaczenia 0.7.0:
godlo (produkt natywny 1:1), `--product nmpt|orto` (etap 2), `laz` (chmura
punktow), `--system 2000` (mozaika miedzystrefowa — etap 2). Na obszarze
transgranicznym `--country auto --target-crs` daje DWA wycinki (PL+CZ)
w tym samym ukladzie, wspolny `extra.parent_request`.

**Konsekwencje:** Symetria PL/CZ w trybie bbox; domkniety zalegly punkt
backlogu "Mozaikowanie arkuszy NMT PL". Warp PL to osobna funkcja
`transform/raster.warp_to_grid` — sparametryzowana kopia wzorca CZ, celowo
niewspoldzielona (testy ADR-024 patchuja `providers.cuzk.dmr.reproject`,
tor CZ zweryfikowany live tuz przed wydaniem).
```

(b) Korekta ADR-013 — na koncu sekcji ADR-013 (po linii ~230) dopisz:

```markdown
**Korekta (2026-08-28):** uklad `nmt_1m`/`nmt_5m` zastapiony segmentami
`nmt/pl_<uklad>_<res>_<vcrs>` — patrz ADR-026.
```

(c) Korekta ADR-017 — na koncu sekcji (po "Konsekwencje", linia ~299) dopisz:

```markdown
**Korekta (2026-08-28, ADR-026):** zapowiedziany tu podkatalog `nmt_2000_1m`
nigdy nie powstal (arkusze PL-2000 ladowaly w `nmt_<res>/` obok PL-1992 —
patrz uwaga w CHANGELOG 0.5.0). Odroczenie domkniete w ADR-026: PL-2000 ma
wlasne segmenty `pl_2000_*`.
```

(d) Addendum ADR-023 — punkt 5 ZACZYNA sie na linii 597 i ciagnie do konca
ADR-023 (~633); wstaw nowy punkt na SAMYM KONCU tej listy, bezposrednio przed
naglowkiem `## ADR-024:` (linia 635), zeby nie rozciac punktu 5 w polowie:

```markdown
6. **Addendum 2026-08-28 (ADR-027): `--target-crs` przestaje byc flaga
   wylacznie czeska.** W trybie `--bbox`/`--geometry` dziala tez dla PL
   (jeden scalony wycinek), a na pograniczu `--country auto --target-crs`
   daje dwa wycinki w tym samym ukladzie ze wspolnym
   `extra.parent_request`. Lista "opcji nierozwiazywalnych" z pkt 5
   przestaje obejmowac `--target-crs` z PL.
```

- [ ] **Step 2: `docs/CHANGELOG.md`** (sekcja `## [0.7.0] - Unreleased`)

(a) Do `### Breaking Changes` (linia 10, na poczatek listy) dodaj:

```markdown
- **Nowy uklad `data/` — segmenty `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]`**
  (ADR-026, decyzje D1-D8; kanoniczny opis: `docs/ARCHITECTURE.md` sekcja 3).
  Kazdy segment koduje jawnie kraj, uklad poziomy (PL: 1992/2000 — domkniecie
  odroczonego ADR-017) i pionowy (kron86/evrf2007/bpv; orto bez pionowego).
  Tabela migracji:

  | Stara sciezka | Nowa sciezka |
  |---|---|
  | `nmt_1m/` (godla 1992) | `nmt/pl_1992_1m_<vcrs>/` |
  | `nmt_1m/` (godla kropkowe 2000) | `nmt/pl_2000_1m_<vcrs>/` |
  | `nmt_5m/` | `nmt/pl_1992_5m_evrf2007/` |
  | `nmpt/` | `nmpt/pl_<uklad>_1m_<vcrs>/` |
  | `orto/` | `orto/pl_1992/` |
  | `laz/` | `laz/pl_<uklad>_<vcrs>/` |
  | `cz_dmr5g/` (tylko 0.7.0-dev) | `nmt/cz_dmr5g_<vcrs>/` |
  | `cz_dmr4g/` (tylko 0.7.0-dev) | `nmt/cz_dmr4g_<vcrs>/` |

  `<vcrs>` przy migracji recznej odczytaj z sidecara (`vertical_crs`);
  pliki sprzed etapu 0 nie maja sidecarow — wtedy re-download albo wiedza
  wlasna uzytkownika. `landcover/` bez zmian.
- **`SourceDescriptor.storage_subdir` zmienia semantyke: literal -> szablon**
  z placeholderami `{uklad}`/`{vcrs}` (ADR-026). Konsument czytajacy pole
  wprost dostanie szablon — uzywaj `resolve_subdir()`.
```

(b) Do `### Added` (linia 126, na poczatek) dodaj:

```markdown
- **`--target-crs` dla PL w trybie `--bbox`/`--geometry`** (ADR-027): jeden
  scalony wycinek `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif` (mozaika
  arkuszy + crop + lokalny warp przypieta operacja; `EPSG:2180` = sam crop,
  `transform: null`; failed arkusz = kod 1). Na pograniczu `--country auto
  --target-crs` daje dwa wycinki PL+CZ ze wspolnym `extra.parent_request`.
  Wylaczenia (czytelne bledy): godlo, `--product nmpt|orto|laz`,
  `--system 2000`.
- `SourceDescriptor.resolve_subdir(uklad=, vertical_crs=)` — wypelnianie
  szablonu segmentu (czesciowe legalne; vcrs lowercased)
- `FileStorage(vertical_crs=)` — nowy parametr (default `"EVRF2007"`);
  `{uklad}` rozwiazywany per godlo (kropki=2000, myslniki=1992),
  nierozwiazany placeholder = `ValidationError`
- `kartograf.transform.raster.warp_to_grid` — lokalna reprojekcja rastra
  z wymuszona operacja przypieta (wzorzec ADR-024 dla torow PL)
- `mosaic_and_crop(dst_kwds=)` — wymuszenie sterownika/CRS wyniku
  (wejscia ASC bez CRS -> GeoTIFF z EPSG:2180)
- `docs/ARCHITECTURE.md` — kanoniczny opis architektury, kontraktow
  i ukladu `data/`
```

(c) Do `### Changed` (linia 244): w PIERWSZYM wpisie (wycinki bbox CZ,
d68be23, linie 245-250) podmien przyklad sciezki
`data/cz_dmr5g/bbox/-447000_-1114000_-446000_-1113000.tif` na
`data/nmt/cz_dmr5g_bpv/bbox/-447000_-1114000_-446000_-1113000.tif`
i dopisz na koncu wpisu: "(segment wg ADR-026)". Nastepnie dodaj wpis:

```markdown
- LAZ: segment storage wyznaczany per kafel z `uklad_xy`
  (`laz/pl_<uklad>_<vcrs>/`); fallback: format godla, ostatecznie `2000`
  z ostrzezeniem w logu
```

(d) **Stare sciezki WEWNATRZ niewydanej sekcji `[0.7.0]`** — te wpisy opisuja
zmiany, ktore wyjda razem z tym wydaniem, wiec nie sa "historia" i musza
zgadzac sie z faktem. Popraw trzy miejsca:
- :122 "pisze do `nmpt/`, nie do `nmt_1m/`" ->
  "pisze do `nmpt/pl_<uklad>_1m_<vcrs>/`, nie do segmentu NMT"
- :215 "pliki w `laz/<hierarchia godla>/<oryginalna nazwa>.laz`" ->
  "pliki w `laz/pl_<uklad>_<vcrs>/<hierarchia godla>/<oryginalna nazwa>.laz`"
- :430 "bylo: zawsze `nmt_1m`, wiec NMPT pisal do katalogu NMT" ->
  "bylo: zawsze segment NMT 1m, wiec NMPT pisal do katalogu NMT"

Wpisy w sekcjach `[0.6.1]` i starszych (m.in. `nmt_2000_1m` w 0.5.0, linie
595-599) sa historia wydanych wersji — NIE ruszaj ich.

- [ ] **Step 3: `CLAUDE.md`**

(a) Sekcja "Dokumentacja" — wstaw po pozycji 2 (SCOPE.md):
`3. docs/ARCHITECTURE.md — architektura, kontrakty danych, kanoniczny uklad data/`
(przenumeruj kolejne).

(b) Sekcja "Komendy" — po istniejacym przykladzie `--target-crs` CZ dodaj:

```bash
# wycinek PL: jeden scalony GeoTIFF (mozaika arkuszy + pinned warp)
kartograf download --bbox 530000,382000,533000,386000 --country pl --target-crs EPSG:5514
# pogranicze jedna komenda: dwa wycinki (PL+CZ) w tym samym ukladzie, wspolny parent_request
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --target-crs EPSG:2180 --vertical-crs EVRF2007
```

(c) "Struktura modulow" — linie descriptor/registry/storage uzupelnij:
descriptor.py o `resolve_subdir (szablony {uklad}/{vcrs}, ADR-026)`;
storage.py o `vertical_crs=, segmenty <produkt>/<kraj>_<uklad>_<vcrs>`;
dodaj linie `│   └── raster.py  # warp_to_grid — wymuszona operacja przypieta (ADR-027)`
pod `transform/crs.py`.

(d) Nowa krotka sekcja po "Struktura modulow":

```markdown
## Uklad data/ (0.7.0, ADR-026)

`data/<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/...` — np.
`nmt/pl_1992_1m_evrf2007/`, `nmt/pl_2000_1m_evrf2007/`, `nmpt/pl_1992_1m_kron86/`,
`orto/pl_1992/`, `laz/pl_2000_evrf2007/`, `nmt/cz_dmr5g_bpv/`; wycinki
`--bbox`/`--target-crs` w `<segment>/bbox/<coords>.tif`. Kanoniczna tabela
i migracja: `docs/ARCHITECTURE.md` sekcja 3. `landcover/` bez zmian.
```

(e) "Ograniczenia" — w bloku CZ zdanie "`--target-crs` dziala tylko z
`--bbox`/`--geometry` — z godlem CZ konczy sie `ValidationError` (godlo
dostarcza produkt natywny 1:1)" uogolnij: "`--target-crs` dziala tylko
z `--bbox`/`--geometry` (PL i CZ) — z godlem konczy sie bledem (godlo
dostarcza produkt natywny 1:1)". Dodaj nowy punkt listy:

```markdown
- **`--target-crs` dla PL (ADR-027):** tylko `--product nmt` i system 1992
  (nmpt/orto — etap 2; laz to chmura punktow; mozaika miedzystrefowa 2000 —
  etap 2); wynik to JEDEN GeoTIFF `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`,
  failed arkusz = kod 1; `EPSG:2180` = sam crop (`transform: null`)
```

- [ ] **Step 4: `README.md`**

- Linia 160: `data/nmt_1m/`, `data/nmt_5m/` ->
  `data/nmt/pl_1992_1m_evrf2007/`, `data/nmt/pl_1992_5m_evrf2007/`
  (i dopisek "pelny uklad: docs/ARCHITECTURE.md").
- Linia 179: `data/nmpt/` -> `data/nmpt/pl_1992_1m_evrf2007/`.
- Linia 186: `data/orto/` -> `data/orto/pl_1992/`.
- Linia 190: `data/laz/` -> `data/laz/pl_<uklad>_<vcrs>/`.
- Do listy funkcji NMT dodaj punkt:
  `- ✅ **Wycinek bbox** - \`--target-crs\` skleja arkusze i reprojektuje lokalnie (przypieta operacja) do jednego GeoTIFF`
- Tabela sidecara (wiersz dla wycinka PL — spec 10.3): wiersz
  `horizontal_crs` (linia 139) — po "a po `--target-crs` układ docelowy"
  dopisz "(PL i CZ)"; wiersz `transform` (linia 146) — fraze "bez żadnego
  przeliczenia (pliki PL) całe pole to `null`" doprecyzuj na "bez żadnego
  przeliczenia (pliki PL pobierane godłem/arkuszami oraz wycinek
  `--target-crs EPSG:2180`) całe pole to `null`; wycinek PL w innym
  układzie niesie `pinned: ...` w osi poziomej (ADR-027)". Zadnych nowych
  wierszy — sidecar nie ma pola `capability`.
- Sekcja struktury projektu (294-312): dodaj `raster.py` pod transform
  oraz linijke o ARCHITECTURE.md w opisie docs.
- Stopka (353): bez zmian liczby testow tutaj — zaktualizuje ja Zad. 12
  po pomiarze.

- [ ] **Step 5: `docs/SCOPE.md`**

- 2.1 (NMT PL, In Scope) — dodaj punkt:
  `- Wycinek bbox z reprojekcją lokalną: \`--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}\` w trybie \`--bbox\`/\`--geometry\` — jeden scalony GeoTIFF (mozaika arkuszy + pinned warp, ADR-027)`
- 2.2 (CZ) linia 92-93: usun "tylko w trybie" nie — zostaje; ale
  ujednolic z PL: dopisz "(symetrycznie do PL od 0.7.0)".
- Po sekcji 2.10 dodaj:

```markdown
### 2.11 Uklad danych na dysku - IN SCOPE

- `data/<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/...` (ADR-026);
  kanoniczna tabela segmentow i migracja 0.6.x->0.7.0:
  `docs/ARCHITECTURE.md` sekcja 3
- Wycinki `--bbox` w `<segment>/bbox/<coords><ext>` (PL i CZ)
- `landcover/` bez zmian (wlasny default `--output`)
```

- 3.2 (Ograniczenia techniczne) — do bloku CZ/target-crs dopisz:
  `- --target-crs dla PL: tylko nmt i system 1992 (nmpt/orto — etap 2; mozaika miedzystrefowa PL-2000 — etap 2); failed arkusz = kod 1`
- Sekcja 4 (drzewo modulow): dodaj `raster.py` pod `transform/` —
  podrzewo jest na liniach **371-372** (`├── transform/` / `│   └── crs.py`),
  NIE przy 396 (tam jest `storage.py` pod `download/`). Zaktualizuj tez opis
  `_parser.py` (405) o "(--target-crs PL/CZ)".
- Historia zmian (tabela konczy sie wierszem `| 2026-08-22 | 3.8 | ...`
  na linii ~488): dodaj wiersz z wersja **3.9** (3.8 jest zajete):
  `| 2026-08-28 | 3.9 | Uklad data/ per produkt (ADR-026), --target-crs dla PL (ADR-027), sekcja 2.11 |`
  i zbij stopke dokumentu (linie ~492-493): `**Wersja dokumentu:** 3.9`,
  `**Data ostatniej aktualizacji:** 2026-08-28`.

- [ ] **Step 6: `docs/PROGRESS.md`**

- W "Ostatnia sesja" dodaj sekcje datowana:

```markdown
### Uklad data/ per produkt + --target-crs PL (2026-08-28)

- Spec: `docs/superpowers/specs/2026-08-28-uklad-data-i-target-crs-pl-design.md`
  (D1-D8); plan: `docs/superpowers/plans/2026-08-28-uklad-data-i-target-crs-pl.md`
- Segmenty `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]` (ADR-026):
  szablony w deskryptorach (`resolve_subdir`), FileStorage(vertical_crs=),
  manager/CLI PL/CZ/LAZ na resolve_subdir; ADR-017 domkniety
- `--target-crs` dla PL (ADR-027): wycinek `nmt/pl_1992_<res>_<vcrs>/bbox/`,
  mozaika (`mosaic_and_crop(dst_kwds=)`) + `transform/raster.warp_to_grid`
  (wymuszona operacja przypieta); pogranicze `--country auto` = dwa wycinki,
  wspolny `parent_request`; errata ADR-023
- Dokumentacja: NOWY `docs/ARCHITECTURE.md` (kanoniczny uklad data/),
  CHANGELOG Breaking z tabela migracji, ADR-026/027 + korekty 013/017/023
```

- W backlogu A1-9 (linie ~683-686) oznacz jako wykonane:
  `- [x] A1-9 — rozdzielenie katalogow PL-2000 — WYKONANE 2026-08-28 (ADR-026, segmenty pl_2000_*)`
  i skoryguj przy okazji blednza fraze "dzis wspolny nmt_2000_1m" na
  "(historycznie: wspolny `nmt_<res>/`)".
- Do "Nastepne kroki" (przed punktem o bumpie 0.7.0) dodaj punkt:
  `E2E live sciezek nowego ukladu data/ + wycinka --target-crs PL — pozycja checklisty release (spec 12)`.
- Do sekcji `## Backlog` dodaj podsekcje:

```markdown
#### Backlog etapu 2 — dopisany przy ukladzie data/ i target-crs PL (2026-08-28)

- [ ] `find_downloaded(product=, bbox=, vertical_crs=)` — inwentarz pobran
      po sidecarach (klucz: `parent_request` / przeciecie bbox)
- [ ] `--target-crs` dla `nmpt`/`orto` (razem z odpowiednikami CZ etapu 2)
- [ ] Wycinek PL dla `--system 2000` (mozaika miedzystrefowa: warp per
      strefa 2176-2179 przed sklejeniem)
- [ ] Ujednolicenie `parent_request.bbox_crs` miedzy trybami jawny/auto
      (pozycja istniejaca — powiazac z `find_downloaded`)
- [ ] Nota dla Hydrografa: `harmonize_dem(files, target_crs, resolution)`
      na bazie `kartograf.transform.crs.PinnedTransform` (NIE golego pyproj
      — lekcja ADR-024); wejscie z sidecarow
```

- [ ] **Step 7: Weryfikacja spojnosci dokumentow**

Run: `grep -rn "nmt_1m\|nmt_5m\|cz_dmr5g\b\|cz_dmr4g\b" README.md CLAUDE.md docs/SCOPE.md docs/ARCHITECTURE.md | grep -v "pl_1992\|pl_2000\|cz_dmr5g_\|cz_dmr4g_"`
Expected: jedyne dozwolone trafienie to klucz deskryptora `pl.gugik.nmt_1m`
w CLAUDE.md ("deskryptor `pl.gugik.nmt_1m` deklaruje kanal WCS...") — to nazwa
zrodla, nie sciezka.

Run: `sed -n '8,519p' docs/CHANGELOG.md | grep -n "nmt_1m\|nmt_5m\|cz_dmr5g\b\|laz/<"`
Expected: zero trafien — sekcja `[0.7.0] - Unreleased` nie moze opisywac
starego ukladu (Step 2d). Sekcje `[0.6.1]` i starsze zostaja nietkniete.

- [ ] **Step 8: Commit**

```bash
git add docs/DECISIONS.md docs/CHANGELOG.md CLAUDE.md README.md docs/SCOPE.md docs/PROGRESS.md
git commit -m "docs: ADR-026/027, tabela migracji data/, aktualizacja CLAUDE/README/SCOPE/PROGRESS"
```

---

### Zad. 12: Brama jakosci + kryteria akceptacji

**Files:**
- Modify (tylko w razie znalezisk): dowolne z powyzszych
- Modify: `README.md:353`, `docs/PROGRESS.md` (liczba testow po pomiarze)

- [ ] **Step 1: Pelna brama (spec 8 "Brama jakosci", 13.1)**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m ruff check kartograf/ tests/
.venv/bin/python -m ruff format --check kartograf/ tests/
.venv/bin/python -m mypy kartograf/
```

Expected: suita zielona w calosci; ruff bez uwag; mypy z liczba bledow
**<= 32** (baseline; zadnego nowego dlugu). Zanotuj koncowa liczbe testow.

- [ ] **Step 2: Walkthrough kryteriow akceptacji (spec sekcja 13)**

Przejdz liste i wskaz test/artefakt dowodowy (wszystko offline):
1. Brama — Step 1.
2. Sciezki godla PL (1992/2000, KRON86/EVRF2007) —
   `tests/test_storage.py::TestFileStorageSegments`, testy fabryki (Zad. 4).
3. nmpt/orto/laz segmenty — `TestFileStorageSegments` + asercje LAZ (Zad. 5).
4. CZ godlo/bbox + EVRF2007 — testy CZ w `tests/test_cli.py` (Zad. 2).
5. Wycinek PL 5514 (<1 px) i 2180 (crop, `transform: null`) —
   `tests/test_pl_cutout.py::TestBuildPlCutout`, `TestDownloadPlBboxCutout`;
   warstwa warp osobno `tests/test_transform_raster.py`.
6. Pogranicze: dwa wycinki, wspolny `parent_request`, kod 0 —
   `tests/test_pl_cutout.py::TestBorderTwoCutouts` (Zad. 9 Step 1b; realnie
   powstaja dwa pliki) + `test_border_bbox_with_target_crs_runs_both_countries`
   (Zad. 8 Step 2; dyspozycja i wspoldzielenie `parent_request`).
7. Walidacje 6.3 — `TestTargetCrsValidations` (Zad. 8).
8. Dokumentacja — `docs/ARCHITECTURE.md` istnieje wg konspektu; CHANGELOG
   z tabela migracji; pozostale wg Zad. 11.

Kazdy brak = wroc do wlasciwego zadania, dopisz/napraw, powtorz Step 1.

- [ ] **Step 3: Aktualizacja liczb**

Wpisz zmierzona liczbe testow/pokrycie do `README.md:353` (stopka) oraz
do sekcji sesji w `docs/PROGRESS.md` (Zad. 11 Step 6). Pokrycie zmierz:
`.venv/bin/python -m pytest tests/ --cov=kartograf --cov-report=term | tail -5`.
Sprawdz tez `docs/DEVELOPMENT_STANDARDS.md`: jesli wymienia liczbe plikow
testowych, dolicz `test_transform_raster.py` i `test_pl_cutout.py`
(spec 10.8 — "ewentualnie"); merytorycznie DS i PRD bez zmian.

- [ ] **Step 4: Commit koncowy**

```bash
git add -A
git commit -m "chore(release): brama jakosci po ukladzie data/ i target-crs PL (testy/ruff/mypy<=32)"
```

(Jesli Step 1-3 niczego nie zmienily — pomiń commit.)

---

## Poza zakresem planu (swiadomie)

- Bump wersji 0.7.0, tag i push — checklista release w PROGRESS
  ("Nastepne kroki" pkt 11-12), nie ten plan.
- E2E live nowego ukladu — pozycja checklisty release (spec sekcja 12);
  ten plan konczy sie na pelnej weryfikacji offline.
- Migracja danych uzytkownikow na dysku — swiadomie reczna (tabela
  w CHANGELOG); zadnego skryptu migracyjnego (YAGNI, uklad 0.6.x mial
  malo instalacji, a cz_* nigdy nie wyszedl poza dev).

