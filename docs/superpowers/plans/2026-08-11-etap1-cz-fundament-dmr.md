# Etap 1 — fundament CZ + DMR (CUZK): plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Cel:** Pierwszy zagraniczny kraj w Kartografie — Czechy (CUZK): DMR 5G (raster 2 m) i DMR 4G (GeoTIFF 5 m) przez `CuzkClient` (ArcGIS REST + pliki openzu), parsery godeł `cz_tm33`/`cz_sm5`, CLI `--country {pl,cz,auto}` z auto-podziałem bboxa transgranicznego, sidecary z `transform`/`extra.parent_request`.

**Architektura:** Przepływ CZ omija `DownloadManager` (wzór: LAZ). Deskryptory (`sources/registry.py`) niosą endpointy; `CuzkClient` wykonuje transport (nie zna godeł ani CLI); `CuzkDmrProvider` skleja klienta z deskryptorem; sidecary pisze warstwa CLI. Rejestr układów pionowych przechodzi na model rodzina→realizacja (EVRF2007 = EPSG:5621 globalnie — BREAKING dla `vertical_crs_code`).

**Stack:** Python 3.12+, requests, pyproj (TransformerGroup/allow_ballpark=False), rasterio, numpy, sqlite3 (MetadataCache), pytest + unittest.mock.

**Spec:** `docs/superpowers/specs/2026-08-11-etap1-cz-fundament-dmr-design.md` (zaakceptowany 2026-08-11).
**Research:** `docs/research/2026-08-10-czechy-dmr-zabaged.md` (endpointy zweryfikowane na żywo).

## Ograniczenia globalne (obowiązują każde zadanie)

- Gałąź robocza: **develop** (feature branch od develop; Conventional Commits).
- Wszystkie dotychczasowe testy przechodzą; zmiany istniejących testów WYŁĄCZNIE z listy w sekcji „Testy istniejące do zmiany" poniżej (spec sekcja 8 + rozstrzygnięcia).
- Nowe testy offline — sieć nigdy nie jest dotykana (fixtury z Zadania 1).
- Zero IO przy imporcie modułów (deskryptory to dane; sieć/indeks dopiero w wywołaniach).
- `no_data=-9999` NIGDY nie jest pomijane w żądaniach exportImage (spec fakt #2).
- `always_xy=True` we wszystkich transformacjach; transformacje danych wyłącznie przez `build_pinned_transform` (żadnego `Transformer.from_crs` poza `transform/crs.py`).
- Po każdym zadaniu: `.venv/bin/python -m pytest tests/ -q` zielony, commit.
- Jakość końcowa: `ruff check`, `ruff format --check`, `mypy` (zero nowych błędów względem baseline ~33), pokrycie ≥ 80%.
- Komendy: `.venv/bin/python -m pytest ...`, `.venv/bin/python -m ruff ...`, `.venv/bin/python -m mypy kartograf/`.
- Timeout CUZK: 60 s (jak Land Cover). Retry/backoff: `transport/http.py` (3 próby).
- CHANGELOG aktualizowany na bieżąco w zadaniach oznaczonych „+ CHANGELOG".

## Rozstrzygnięcia z konsultacji 2026-08-11 (wiążące, doprecyzowują spec)

1. **`extra.parent_request` — zawsze w trybie bbox/geometry** (zarówno `--country auto`, jak i jawny `pl|cz`), nigdy w trybie godłowym. Zawartość: oryginalny bbox żądania (przed przycięciem per kraj), `bbox_crs`, `countries` = kraje faktycznie pobrane w TYM wywołaniu (posortowane). Umożliwia dwuetapowe dociąganie drugiego kraju (klucz grupowania: identyczny bbox+crs). Korekta gwarancji „sidecary PL bez zmian treści" z sekcji 9 specu — zmiana addytywna w `extra`, za zgodą użytkownika.
2. **`--target-crs` + godło CZ → `ValidationError`** („--target-crs działa tylko z --bbox/--geometry; tryb godłowy dostarcza dane natywne 1:1"). Spójne z decyzją 13.2 specu.
3. **`PinnedTransform.transform` staje się polimorficzne** — przyjmuje skalary LUB tablice numpy (jak pyproj); kontrola `np.isfinite` w jednym miejscu. Korekta notki „bez zmian API" dla `transform/crs.py`; bez osobnej metody `transform_grid`.

## Rozstrzygnięcia techniczne planu (wyprowadzone ze specu; do zatwierdzenia przy review planu)

- **`tests/test_cache.py` ze specu = `tests/test_metadata_cache.py`** (faktyczna nazwa pliku w repo).
- **`--system` dostaje sentinel `None`** (rozwiązywany na `"1992"` w przepływach PL) — jedyny sposób realizacji wymogu specu 5.7 „`--system` + `--country cz` → ValidationError"; test domyślnej wartości `--system` w `TestCreateParserDownloadSystem` aktualizowany (rozszerzenie listy zmian z sekcji 8 specu).
- **`all_countries()`** — nowy publiczny akcesor w `sources/registry.py` (implikowany przez spec 5.7 pkt 3: „przecięcie z extent_wgs84 wszystkich CountryProfile").
- **`resolve_vertical_crs(name, options)`** — publiczna funkcja rejestru materializująca mapowanie rodzina→realizacja (spec 5.2); konsumowana przez `build_metadata` ORAZ testy spójności deskryptor↔provider.
- **Przycinanie bboxa do extentu kraju TYLKO w trybie auto**; jawny `--country` pobiera pełny bbox (zachowanie PL bez zmian).
- **Kafelkowanie exportImage wymaga `bbox.crs == image_sr`** (kafle cięte w układzie wyjściowym — brak szwów); provider normalizuje bbox do `image_sr` przed eksportem, gdy układy się różnią (obwiednia narożników przez `core.geometry._transform_bbox`).
- **Nazwa pliku bbox CZ** używa współrzędnych finalnego żądania (po normalizacji do `image_sr`), format `format(v, 'g')`.
- **Wersja pakietu**: `__version__` → `"0.7.0-dev"`, `--version` w `_parser.py` czyta `__version__` zamiast hardkodu (Zadanie 18).
- **„Podsumowanie ok/skip/fail jak w LAZ" dla `_cmd_download_cz`** redukuje się do komunikatów per plik (`Downloaded/Skipped/Error`) — żądanie CZ daje zawsze dokładnie jeden plik (LAZ ma wiele kafli na obszar).
- **LAZ w trybie bbox/geometry z `--country auto`**: gdy obszar przecina CZ → `ValidationError` z podpowiedzią `--country pl` (konsekwencja reguły „bez cichego pomijania kraju" ze spec 5.7; LAZ dla CZ to etap 2). Tryb godłowy LAZ bez zmian — kraj wynika jednoznacznie z godła.
- **Gałąź PL w auto-split pracuje na kopii `args`** (`argparse.Namespace(**vars(args))`) — `_resolve_pl_sentinels` mutuje Namespace (None→"1m"), a wspólny obiekt zatruwałby gałąź CZ; kopia uniezależnia wynik od kolejności iteracji po krajach.

## Struktura plików (co powstaje / co się zmienia)

```
kartograf/
├── core/parser_tm33.py            # NOWY (Zad. 6)
├── core/parser_registry.py        # +cz_tm33, +cz_sm5 (Zad. 11)
├── sources/descriptor.py          # +AccessChannel.endpoint (Zad. 3)
├── sources/registry.py            # +uklady pionowe/rodzina (Zad. 2), +CZ (Zad. 3)
├── sources/sidecar.py             # resolve_vertical_crs (Zad. 2), +capability/nodata (Zad. 4)
├── transform/crs.py               # transform polimorficzne + probe pod siecia (Zad. 5)
├── cache/metadata.py              # +sheet_cache (Zad. 7)
├── providers/cuzk/__init__.py     # NOWY — create_dmr_provider (Zad. 12)
├── providers/cuzk/client.py       # NOWY — CuzkClient (Zad. 8-9)
├── providers/cuzk/sheets.py       # NOWY — SheetIndex, SheetInfo, Sm5Sheet (Zad. 10)
├── providers/cuzk/dmr.py          # NOWY — CuzkDmrProvider (Zad. 12)
├── download/manager.py            # +sidecar_extra (Zad. 13)
├── cli/_parser.py                 # +--country/--target-crs/sentinele (Zad. 14)
├── cli/cache_cmd.py               # +Sheet entries (Zad. 7)
├── cli/download_cmd.py            # +_cmd_download_cz (Zad. 15), dyspozycja (Zad. 16), auto-split (Zad. 17)
└── __init__.py                    # +eksporty CZ, wersja (Zad. 18)
tests/
├── fixtures/cuzk/                 # NOWE — realne odpowiedzi z rekonesansu (Zad. 1)
├── test_parser_tm33.py            # NOWY (Zad. 6)
├── test_cuzk_client.py            # NOWY (Zad. 8-9)
├── test_cuzk_sheets.py            # NOWY (Zad. 10)
├── test_cuzk_dmr.py               # NOWY (Zad. 12)
└── (rozszerzenia istniejących — patrz lista poniżej)
```

## Testy istniejące do zmiany (pełna lista; nic poza nią)

| Plik | Test | Zmiana | Zadanie |
|---|---|---|---|
| `tests/test_sources_registry.py` | `test_vertical_crs_code` (l.119) | nowe mapowanie: EVRF2007→5621, +EVRF2007-PL, +Bpv | 2 |
| `tests/test_sources_registry.py` | `test_nmt_1m`/`test_nmt_5m`/`test_nmpt`/`test_laz` (l.148/161/174/193) | `vertical_crs_code(n)` → `resolve_vertical_crs(n, ch.vertical_crs_options)` | 2 |
| `tests/test_sources_registry.py` | `EXPECTED_KEYS` (l.23) | +`cz.cuzk.dmr5g`, +`cz.cuzk.dmr4g` | 3 |
| `tests/test_sources_registry.py` | `test_get_source_unknown_key_lists_available` (l.100) | klucz nieistniejący `cz.cuzk.dmr5g` → `xx.none.zadne` | 3 |
| `tests/test_sources_registry.py` | `test_sources_for_filters` (l.105) | +asercja `len(sources_for(country="CZ")) == 2` | 3 |
| `tests/test_sources_registry.py` | `test_country_pl` (l.111) | `get_country("CZ")` przestaje rzucać → nieznany kod `"XX"` | 3 |
| `tests/test_sources_registry.py` | `test_access_channel_defaults` (l.54) | +asercja `endpoint == ""` | 3 |
| `tests/test_metadata_cache.py` | `test_clear` (l.245), `test_stats` (l.253) | +`sheet_cache` w asercjach | 7 |
| `tests/test_metadata_cache.py` | `test_cmd_cache_stats` (l.591) | +asercja linii `Sheet entries` | 7 |
| `tests/test_cli.py` | `TestCreateParserDownloadSystem` — test domyślnego `--system` (ok. l.1570+) | default `"1992"` → `None` (sentinel) + osobna asercja behawioralna PL | 14 |
| `tests/test_transform_crs.py` | `test_result_isfinite_guard` (l.121) | tylko jeśli asertuje fragment komunikatu ze współrzędnymi: `match` → `"nieskonczon"` (komunikat nie interpoluje tablic) | 5 |
| `tests/test_cli.py` | `test_download_geometry_basic` (l.1225), `test_download_geometry_with_layer` (l.1248), `test_download_geometry_system_2000` (l.1733), `test_download_geometry_default_system_1992` (l.1765) | +`@patch("kartograf.core.geometry.get_overall_bbox")` zwracający bbox w głębi PL — nowy przepływ geometry liczy overall bbox dla `parent_request`, a pliki stub testów nie są czytelne | 17 |
| `tests/test_cli.py` | testy `grep -n '0\.6\.1' tests/` (wersja w `--version`, jeśli asertowana; l.259) | `0.6.1` → odczyt z `__version__` | 18 |
| `tests/test_integration.py` | `test_version` (l.47-56: `assert __version__ == "0.6.1"`) | asercja → `"0.7.0-dev"` | 18 |

Wszystkie pozostałe zmiany w testach są **addytywne** (nowe testy/nowe klasy). Mocki bez osłabiania.

---

### Zadanie 1: Rekonesans live CUZK + pyproj (bez kodu produkcyjnego)

Spec sekcja 12 — weryfikacja niedomkniętych faktów PRZED kodowaniem. Wynik: fixtury z realnych odpowiedzi + notatka. Wymaga sieci (jedyne zadanie poza E2E).

**Files:**
- Create: `tests/fixtures/cuzk/klady_sm5_where_ctes96.json`
- Create: `tests/fixtures/cuzk/klady_sm5_bbox.json`
- Create: `tests/fixtures/cuzk/klady_tm33_bbox.json`
- Create: `tests/fixtures/cuzk/klady_layer24_meta.json`, `tests/fixtures/cuzk/klady_layer26_meta.json`
- Create: `docs/research/2026-08-11-etap1-rekonesans.md`

**Interfaces:**
- Produces: fixtury JSON (kształt odpowiedzi warstw 24/26 — źródło prawdy dla Zad. 10), notatka z ustaleniami (nodata w exportImage, dmr4g, openzu HTTP, semantyka pyproj 8357→5621 — źródło prawdy dla Zad. 9 i 12).

- [ ] **Krok 1: Metadane warstw 24/26 (maxRecordCount, pola)**

```bash
mkdir -p tests/fixtures/cuzk
curl -s "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/24?f=json" \
  -o tests/fixtures/cuzk/klady_layer24_meta.json
curl -s "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/26?f=json" \
  -o tests/fixtures/cuzk/klady_layer26_meta.json
python3 -c "import json; m=json.load(open('tests/fixtures/cuzk/klady_layer24_meta.json')); print(m.get('maxRecordCount'), [f['name'] for f in m.get('fields', [])])"
```
Oczekiwane: `maxRecordCount` (prawdopodobnie 2000), pola zawierają `MAPNOM`, `MAPNAME`, `PODIL` (w. 24) i `MAPNOM`, `IN_CZ` (w. 26). Zanotuj faktyczne nazwy (wielkość liter!).

- [ ] **Krok 2: Zapytanie `where=MAPNOM='CTES96'` (walidacja godła SM5)**

```bash
curl -s "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/24/query?f=json&where=MAPNOM%3D%27CTES96%27&outFields=MAPNOM,MAPNAME,PODIL&returnGeometry=true&outSR=5514" \
  -o tests/fixtures/cuzk/klady_sm5_where_ctes96.json
python3 -c "import json; d=json.load(open('tests/fixtures/cuzk/klady_sm5_where_ctes96.json')); f=d['features'][0]; print(f['attributes'], list(f['geometry'].keys()))"
```
Oczekiwane: 1 feature, `attributes.MAPNOM == "CTES96"`, `MAPNAME` ~ "Cesky Tesin 8-6", `PODIL` ~ 0.5 (arkusz przygraniczny), `geometry.rings`. Zapisz też odpowiedź dla nieistniejącego `MAPNOM='XXXX99'` (oczekiwane: `features: []`) — do notatki.

- [ ] **Krok 3: Zapytania bbox warstw 24 i 26 (paginacja, kształt)**

```bash
# okolice Czeskiego Cieszyna, EPSG:5514 (wspolrzedne ujemne!)
curl -s "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/24/query?f=json&geometry=-450000,-1105000,-440000,-1095000&geometryType=esriGeometryEnvelope&inSR=5514&spatialRel=esriSpatialRelIntersects&outFields=MAPNOM,MAPNAME,PODIL&returnGeometry=true&outSR=5514" \
  -o tests/fixtures/cuzk/klady_sm5_bbox.json
curl -s "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/26/query?f=json&geometry=744000,5540000,760000,5556000&geometryType=esriGeometryEnvelope&inSR=3045&spatialRel=esriSpatialRelIntersects&outFields=MAPNOM,IN_CZ&returnGeometry=true&outSR=3045" \
  -o tests/fixtures/cuzk/klady_tm33_bbox.json
```
Sprawdź: liczba features > 0; czy odpowiedź zawiera pole `exceededTransferLimit` (zanotuj, kiedy się pojawia — potrzebne do testu paginacji). Jeśli faktyczne parametry różnią się od powyższych (np. wymagany `geometry` jako JSON obiektu), zanotuj działającą formę — Zadanie 8 koduje wg fixtur.

- [ ] **Krok 4: exportImage z noData (dmr5g i dmr4g)**

```bash
# kafel przygraniczny (49,3% poza CZ) — weryfikacja wypelnienia noData
curl -s "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer/exportImage?f=image&format=tiff&pixelType=F32&bbox=-447000,-1114000,-446000,-1113000&bboxSR=5514&imageSR=5514&size=500,500&noData=-9999&noDataInterpretation=esriNoDataMatchAny" -o /tmp/recon_dmr5g.tif
curl -s "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr4g/ImageServer/exportImage?f=image&format=tiff&pixelType=F32&bbox=-447000,-1114000,-446000,-1113000&bboxSR=5514&imageSR=5514&size=200,200&noData=-9999&noDataInterpretation=esriNoDataMatchAny" -o /tmp/recon_dmr4g.tif
.venv/bin/python -c "
import rasterio, numpy as np
for p in ('/tmp/recon_dmr5g.tif', '/tmp/recon_dmr4g.tif'):
    with rasterio.open(p) as src:
        d = src.read(1)
        print(p, 'nodata tag:', src.nodata, 'min:', d.min(), 'ile -9999:', int((d == -9999).sum()), 'ile ==0:', int((d == 0).sum()))
"
```
Oczekiwane: oba pliki to poprawne TIFF-y; obszar poza CZ = -9999 (nie 0); tag nodata w GeoTIFF = -9999. Jeśli tag nodata NIE jest ustawiany przez serwer — zanotuj; wtedy Zadanie 9 dostaje dodatkowy krok: po pobraniu wpisać `nodata` do profilu rasterio (tryb r+). Jeśli dmr4g exportImage nie działa — zanotuj; fallback ze specu: DMR4G tylko plikowo (SM5), a `--resolution 5m` w trybie bbox CZ → ValidationError (dopisz do Zad. 12/15).

- [ ] **Krok 5: exportImage kafla TM33 w 3045**

```bash
curl -s "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer/exportImage?f=image&format=tiff&pixelType=F32&bbox=302000,5550000,304000,5552000&bboxSR=3045&imageSR=3045&size=1000,1000&noData=-9999&noDataInterpretation=esriNoDataMatchAny" -o /tmp/recon_tm33.tif
.venv/bin/python -c "
import rasterio
with rasterio.open('/tmp/recon_tm33.tif') as src:
    print(src.crs, src.bounds, src.res, src.nodata)
"
```
Oczekiwane: CRS EPSG:3045 (lub 25833 — zanotuj WKT), bounds = (302000, 5550000, 304000, 5552000), res (2, 2).

- [ ] **Krok 6: Zachowanie HTTP openzu**

```bash
curl -sI "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/epsg-5514/CTES96.zip" | head -20
curl -s -o /dev/null -w "%{http_code}\n" "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/epsg-5514/XXXX99.zip"
```
Zanotuj: kod 200/redirecty/nagłówki (Content-Length, Accept-Ranges); kod dla nieistniejącego arkusza (oczekiwany 404 — obsługa w Zad. 12).

- [ ] **Krok 7: Semantyka pyproj dla 8357→5621 (offline, w .venv)**

```bash
.venv/bin/python -c "
import numpy as np
from kartograf.transform.crs import build_pinned_transform, TransformPolicy
p = build_pinned_transform('EPSG:8357', 'EPSG:5621', TransformPolicy(min_accuracy_m=0.2))
print('op:', p.description, p.accuracy_m)
# punkt przy Cieszynie: lon 18.62, lat 49.75, h 300 m
print('skalar:', p.transform(18.62, 49.75, 300.0))
xs = np.array([18.62, 14.5]); ys = np.array([49.75, 50.9]); zs = np.array([300.0, 300.0])
print('tablice:', p._transformer.transform(xs, ys, zs))
"
```
Oczekiwane: operacja „Baltic 1957 height to EVRF2007 height (1)", accuracy 0.1; wynik z = wejście + 0,117..0,143 m; wywołanie tablicowe działa. **Zanotuj kolejność argumentów** (lon/lat vs lat/lon — `always_xy=True` powinno dawać lon, lat) i czy offset rośnie z południa na północ. Zadania 5 i 12 kodują wg tej notatki.

- [ ] **Krok 8: Notatka + commit**

Spisz ustalenia (każdy krok: co potwierdzone / co odbiega od researchu) do `docs/research/2026-08-11-etap1-rekonesans.md`. Fixtury bez modyfikacji (bajty odpowiedzi 1:1).

```bash
git add tests/fixtures/cuzk/ docs/research/2026-08-11-etap1-rekonesans.md
git commit -m "docs(research): rekonesans etapu 1 — fixtury KladyMapovychListu, exportImage noData, pyproj 8357->5621"
```

---

### Zadanie 2: Rejestr układów pionowych — EVRF2007→5621, rodzina→realizacja (BREAKING)

Decyzja użytkownika 2026-08-11: `EVRF2007` = EPSG:5621 globalnie; nowa nazwa `EVRF2007-PL` = 9651; `Bpv` = 8357. Mapowanie rodzina→realizacja w NOWEJ publicznej funkcji `resolve_vertical_crs`, od razu podpiętej do `build_metadata` (inaczej sidecary PL zaczęłyby pisać 5621 i suita by się wysypała).

**Files:**
- Modify: `kartograf/sources/registry.py:18-22` (słownik), koniec pliku (funkcja)
- Modify: `kartograf/sources/sidecar.py:16,84` (import + wywołanie)
- Test: `tests/test_sources_registry.py`

**Interfaces:**
- Produces: `vertical_crs_code(name: str) -> str` (BREAKING: `"EVRF2007"` → `"EPSG:5621"`); `resolve_vertical_crs(name: str, options: tuple[str, ...]) -> str`; `_VERTICAL_FAMILY: dict[str, tuple[str, ...]]` (prywatne).
- Consumes: nic nowego.

- [ ] **Krok 1: Zaktualizuj testy (failing)**

W `tests/test_sources_registry.py` — import `resolve_vertical_crs` obok `vertical_crs_code`; podmień `test_vertical_crs_code` i dodaj `test_resolve_vertical_crs` w `TestRegistry`:

```python
    def test_vertical_crs_code(self):
        assert vertical_crs_code("KRON86") == "EPSG:9650"
        assert vertical_crs_code("EVRF2007") == "EPSG:5621"
        assert vertical_crs_code("EVRF2007-PL") == "EPSG:9651"
        assert vertical_crs_code("Bpv") == "EPSG:8357"
        assert vertical_crs_code("EPSG:9651") == "EPSG:9651"
        with pytest.raises(KeyError):
            vertical_crs_code("Kronsztad")

    def test_resolve_vertical_crs(self):
        # rodzina EVRF2007 -> realizacja PL, gdy kanal ja oferuje
        assert resolve_vertical_crs("EVRF2007", ("EPSG:9650", "EPSG:9651")) == "EPSG:9651"
        # kanal CZ (Bpv) nie ma realizacji -> kod rodziny (cel transformacji)
        assert resolve_vertical_crs("EVRF2007", ("EPSG:8357",)) == "EPSG:5621"
        assert resolve_vertical_crs("Bpv", ("EPSG:8357",)) == "EPSG:8357"
        assert resolve_vertical_crs("KRON86", ("EPSG:9650", "EPSG:9651")) == "EPSG:9650"
        assert resolve_vertical_crs("EVRF2007-PL", ("EPSG:9650", "EPSG:9651")) == "EPSG:9651"
```

W testach spójności `test_nmt_1m` (l.157), `test_nmt_5m` (l.170), `test_nmpt` (l.181), `test_laz` (l.200) podmień mapowanie — wzór dla `test_nmt_1m`:

```python
        supported = provider.get_supported_vertical_crs_for_resolution("1m")
        for ch in d.channels:
            codes = {resolve_vertical_crs(n, ch.vertical_crs_options) for n in supported}
            assert set(ch.vertical_crs_options) == codes
```

(analogicznie w pozostałych trzech — zamiast `vertical_crs_code(n)` → `resolve_vertical_crs(n, d.channels[0].vertical_crs_options)`).

- [ ] **Krok 2: Uruchom — potwierdź FAIL**

Run: `.venv/bin/python -m pytest tests/test_sources_registry.py -q`
Oczekiwane: FAIL — `ImportError: cannot import name 'resolve_vertical_crs'`.

- [ ] **Krok 3: Implementacja w `sources/registry.py`**

Podmień słownik (l.19-22) i dodaj po `vertical_crs_code`:

```python
# Mapowanie nazw ukladow pionowych uzywanych w CLI na kody EPSG.
_VERTICAL_CRS_CODES = {
    "KRON86": "EPSG:9650",  # PL-KRON86-NH (bez zmian)
    "EVRF2007": "EPSG:5621",  # ogolnoeuropejski EVRF2007 (decyzja 2026-08-11)
    "EVRF2007-PL": "EPSG:9651",  # realizacja polska PL-EVRF2007-NH
    "Bpv": "EPSG:8357",  # Baltic 1957 (CZ)
}

# Rodzina -> realizacje krajowe; konsumowane przy budowie sidecara:
# jesli kod rodziny nie wystepuje w vertical_crs_options kanalu, ale wystepuje
# jego realizacja — sidecar zapisuje kod realizacji (fakt, nie zyczenie).
_VERTICAL_FAMILY: dict[str, tuple[str, ...]] = {"EPSG:5621": ("EPSG:9651",)}
```

```python
def resolve_vertical_crs(name: str, options: tuple[str, ...]) -> str:
    """Kod EPSG dla nazwy ukladu wzgledem opcji kanalu (rodzina -> realizacja)."""
    code = vertical_crs_code(name)
    if code in options:
        return code
    for realization in _VERTICAL_FAMILY.get(code, ()):
        if realization in options:
            return realization
    return code
```

W `sources/sidecar.py`: import `resolve_vertical_crs` zamiast `vertical_crs_code`; l.83-84:

```python
    if channel.vertical_crs_options and vertical_crs is not None:
        vertical = resolve_vertical_crs(vertical_crs, channel.vertical_crs_options)
```

- [ ] **Krok 4: Uruchom pełną suitę**

Run: `.venv/bin/python -m pytest tests/ -q`
Oczekiwane: PASS (sidecary PL nadal piszą 9651 — `test_download_manager.py::TestSidecarWritten` i `test_cli.py::test_laz_writes_sidecar_next_to_tile` zielone bez zmian).

- [ ] **Krok 5: CHANGELOG + commit**

Do `docs/CHANGELOG.md` (sekcja 0.7.0, podsekcja BREAKING):

```markdown
- **BREAKING:** `vertical_crs_code("EVRF2007")` zwraca teraz `EPSG:5621`
  (ogólnoeuropejski EVRF2007), nie `EPSG:9651`. Realizacja polska dostępna
  pod nową nazwą `EVRF2007-PL`. Sidecary PL bez zmian treści (mapowanie
  rodzina→realizacja przez `resolve_vertical_crs`). Dotyczy: Hydrograf/Hydrolog,
  jeśli wołają `vertical_crs_code` bezpośrednio.
```

```bash
git add kartograf/sources/registry.py kartograf/sources/sidecar.py tests/test_sources_registry.py docs/CHANGELOG.md
git commit -m "feat(sources)!: EVRF2007=EPSG:5621 globalnie, rodzina->realizacja (resolve_vertical_crs); +EVRF2007-PL, +Bpv"
```

---

### Zadanie 3: `AccessChannel.endpoint` + deskryptory CZ + `CountryProfile("CZ")` + `all_countries()`

**Files:**
- Modify: `kartograf/sources/descriptor.py:38-50` (pole `endpoint`)
- Modify: `kartograf/sources/registry.py` (licencja, 2 deskryptory, kraj, akcesor)
- Test: `tests/test_sources_registry.py`

**Interfaces:**
- Produces: `AccessChannel.endpoint: str = ""`; klucze `"cz.cuzk.dmr5g"`, `"cz.cuzk.dmr4g"` w `get_source`; `get_country("CZ")`; `all_countries() -> list[CountryProfile]`.
- Consumes: `LicenseInfo`, `SourceDescriptor`, `TileScheme`, `CountryProfile`, `TransportKind.ARCGIS_IMAGE`/`DIRECT_FILES` (istnieją od etapu 0).

- [ ] **Krok 1: Testy (failing)**

W `tests/test_sources_registry.py`:

(a) `EXPECTED_KEYS` (l.23) — dodaj `"cz.cuzk.dmr5g"`, `"cz.cuzk.dmr4g"`.

(b) `test_get_source_unknown_key_lists_available` (l.100) — `get_source("cz.cuzk.dmr5g")` → `get_source("xx.none.zadne")`.

(c) `test_sources_for_filters` (l.105) — dopisz na końcu:

```python
        cz = sources_for(country="CZ")
        assert {d.key for d in cz} == {"cz.cuzk.dmr4g", "cz.cuzk.dmr5g"}
```

(d) `test_country_pl` (l.111) — w `pytest.raises(KeyError)` podmień `get_country("CZ")` na `get_country("XX")`.

(e) `test_access_channel_defaults` (l.54) — dopisz asercję `assert ch.endpoint == ""` (do istniejącego obiektu z helpera `_channel`).

(f) Nowe testy w `TestRegistry`:

```python
    def test_country_cz(self):
        cz = get_country("CZ")
        assert cz.code == "CZ"
        assert cz.extent_wgs84 == BBox(12.09, 48.55, 18.86, 51.06, "EPSG:4326")
        assert cz.dataset_keys == ("cz.cuzk.dmr4g", "cz.cuzk.dmr5g")

    def test_all_countries(self):
        codes = [c.code for c in all_countries()]
        assert codes == ["CZ", "PL"]

    def test_cz_dmr5g_entry_values(self):
        d = get_source("cz.cuzk.dmr5g")
        assert d.country == "CZ"
        assert d.product == "nmt"
        assert d.resolution == "2m"
        assert d.storage_subdir == "cz_dmr5g"
        assert d.default_extension == ".tif"
        assert d.license.id == "CC-BY-4.0"
        assert len(d.channels) == 1
        ch = d.channels[0]
        assert ch.transport == TransportKind.ARCGIS_IMAGE
        assert ch.horizontal_crs == "EPSG:5514"
        assert ch.vertical_crs_options == ("EPSG:8357",)
        assert ch.server_reprojection is True
        assert ch.capabilities == frozenset({"bbox_raster"})
        assert ch.endpoint == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"
        )
        assert d.tile_scheme.kind == "computable"
        assert d.tile_scheme.crs == "EPSG:3045"
        assert (d.tile_scheme.width_m, d.tile_scheme.height_m) == (2000.0, 2000.0)

    def test_cz_dmr4g_entry_values(self):
        d = get_source("cz.cuzk.dmr4g")
        assert d.resolution == "5m"
        assert d.storage_subdir == "cz_dmr4g"
        transports = [ch.transport for ch in d.channels]
        assert transports == [TransportKind.DIRECT_FILES, TransportKind.ARCGIS_IMAGE]
        for ch in d.channels:
            assert ch.horizontal_crs == "EPSG:5514"
            assert ch.vertical_crs_options == ("EPSG:8357",)
        files_ch = d.channels[0]
        assert files_ch.capabilities == frozenset({"sheet_files"})
        assert files_ch.server_reprojection is False
        assert files_ch.endpoint == (
            "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/epsg-5514/{sheet}.zip"
        )
        image_ch = d.channels[1]
        assert image_ch.capabilities == frozenset({"bbox_raster"})
        assert image_ch.server_reprojection is True
        assert image_ch.endpoint == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr4g/ImageServer"
        )
        assert d.tile_scheme.kind == "index"
        assert d.tile_scheme.crs == "EPSG:5514"
        assert (d.tile_scheme.width_m, d.tile_scheme.height_m) == (2500.0, 2000.0)
```

Zaktualizuj importy testu (`all_countries`, `TransportKind`, `BBox` — jeśli brak).

- [ ] **Krok 2: Uruchom — FAIL**

Run: `.venv/bin/python -m pytest tests/test_sources_registry.py -q`
Oczekiwane: FAIL (`ImportError: all_countries` / brak kluczy CZ).

- [ ] **Krok 3: Implementacja**

`descriptor.py` — w `AccessChannel` po polu `notes` (usuń nieaktualny komentarz o braku endpointu, l.49-50):

```python
    endpoint: str = ""
    # URL kanalu dla silnikow sterowanych deskryptorem (etap 1: CuzkClient).
    # Wpisy PL: "" — zrodlem prawdy pozostaja stale providerow (etap 0).
```

`registry.py` — po `_SOILGRIDS_LICENSE`:

```python
_CUZK_LICENSE = LicenseInfo(
    id="CC-BY-4.0",
    attribution="Podklad: Cesky urad zememericky a katastralni (CUZK), CC BY 4.0",
    url="https://geoportal.cuzk.gov.cz",
)
```

Do krotki `_SOURCES` dopisz dwa deskryptory (rozszerz import z descriptor o `TileScheme`):

```python
        SourceDescriptor(
            key="cz.cuzk.dmr5g",
            country="CZ",
            product="nmt",
            name="DMR 5G — Digitalni model reliefu (raster 2 m z exportImage)",
            provider_name="CUZK",
            channels=(
                AccessChannel(
                    transport=TransportKind.ARCGIS_IMAGE,
                    horizontal_crs="EPSG:5514",
                    vertical_crs_options=("EPSG:8357",),
                    server_reprojection=True,
                    capabilities=frozenset({"bbox_raster"}),
                    endpoint=(
                        "https://ags.cuzk.gov.cz/arcgis2/rest/services/"
                        "dmr5g/ImageServer"
                    ),
                ),
            ),
            tile_scheme=TileScheme(
                kind="computable",
                crs="EPSG:3045",
                width_m=2000.0,
                height_m=2000.0,
                description="TM33 {E_km}_{N_km}, naroznik SW",
            ),
            storage_subdir="cz_dmr5g",
            default_extension=".tif",
            license=_CUZK_LICENSE,
            resolution="2m",
        ),
        SourceDescriptor(
            key="cz.cuzk.dmr4g",
            country="CZ",
            product="nmt",
            name="DMR 4G — Digitalni model reliefu (GeoTIFF 5 m, arkusze SM5)",
            provider_name="CUZK",
            channels=(
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    horizontal_crs="EPSG:5514",
                    vertical_crs_options=("EPSG:8357",),
                    capabilities=frozenset({"sheet_files"}),
                    endpoint=(
                        "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/"
                        "epsg-5514/{sheet}.zip"
                    ),
                ),
                AccessChannel(
                    transport=TransportKind.ARCGIS_IMAGE,
                    horizontal_crs="EPSG:5514",
                    vertical_crs_options=("EPSG:8357",),
                    server_reprojection=True,
                    capabilities=frozenset({"bbox_raster"}),
                    endpoint=(
                        "https://ags.cuzk.gov.cz/arcgis2/rest/services/"
                        "dmr4g/ImageServer"
                    ),
                ),
            ),
            tile_scheme=TileScheme(
                kind="index",
                crs="EPSG:5514",
                width_m=2500.0,
                height_m=2000.0,
                description=(
                    "SM5: 4 litery miasta + 2 cyfry; "
                    "indeks KladyMapovychListu w. 24"
                ),
            ),
            storage_subdir="cz_dmr4g",
            default_extension=".tif",
            license=_CUZK_LICENSE,
            resolution="5m",
        ),
```

Do `_COUNTRIES`:

```python
    "CZ": CountryProfile(
        code="CZ",
        name="Czechy",
        extent_wgs84=BBox(12.09, 48.55, 18.86, 51.06, "EPSG:4326"),
        dataset_keys=("cz.cuzk.dmr4g", "cz.cuzk.dmr5g"),
    ),
```

Po `get_country` dodaj:

```python
def all_countries() -> list[CountryProfile]:
    """Wszystkie profile krajow, deterministycznie po kodzie (dla --country auto)."""
    return [_COUNTRIES[code] for code in sorted(_COUNTRIES)]
```

- [ ] **Krok 4: Uruchom pełną suitę**

Run: `.venv/bin/python -m pytest tests/ -q` — oczekiwane: PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/sources/ tests/test_sources_registry.py
git commit -m "feat(sources): deskryptory cz.cuzk.dmr5g/dmr4g z endpointami, CountryProfile CZ, all_countries()"
```

---

### Zadanie 4: `build_metadata` — jawna selekcja kanału (`capability=`) i `nodata=`

Rozstrzygnięcia odroczone z etapu 0 (spec 5.8a i 5.9).

**Files:**
- Modify: `kartograf/sources/sidecar.py:58-110`
- Test: `tests/test_sidecar.py`

**Interfaces:**
- Produces: `build_metadata(descriptor, *, request, vertical_crs=None, data_path=None, transform=None, extra=None, capability: str | None = None, nodata: float | None = None) -> ResultMetadata`. `capability` podane → pierwszy kanał z tą capability (`KeyError` gdy brak); `None` → dotychczasowa heurystyka. `nodata` podane → ma pierwszeństwo przed sniffowaniem `.asc`.
- Consumes: deskryptory CZ z Zad. 3 (dmr4g ma 2 kanały — idealny do testów selekcji).

- [ ] **Krok 1: Testy (failing)** — nowa klasa w `tests/test_sidecar.py` (UWAGA: plik dotąd NIE importuje pytest — dodaj `import pytest` w nagłówku):

```python
class TestBuildMetadataCapabilityAndNodata:
    def test_capability_selects_named_channel(self):
        d = get_source("cz.cuzk.dmr4g")
        meta_files = build_metadata(
            d, request={"godlo": "CTES96"}, capability="sheet_files"
        )
        assert meta_files.horizontal_crs == "EPSG:5514"
        meta_bbox = build_metadata(
            d, request={"godlo": "CTES96"}, capability="bbox_raster"
        )
        # oba kanaly dmr4g maja 5514; rozroznia je transport — sprawdzamy,
        # ze selekcja nie uzyla heurystyki bbox (request godlo + capability bbox)
        assert meta_bbox.horizontal_crs == "EPSG:5514"

    def test_capability_unknown_raises_keyerror(self):
        d = get_source("pl.gugik.orto")
        with pytest.raises(KeyError):
            build_metadata(d, request={"godlo": "X"}, capability="bbox_raster")

    def test_nodata_param_takes_precedence_over_asc_sniff(self, tmp_path):
        asc = tmp_path / "x.asc"
        asc.write_text(
            "ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\n"
            "cellsize 1\nNODATA_value -9999\n"
        )
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"godlo": "N-34-130-D-d-2-4"},
            data_path=asc,
            nodata=-8888.0,
        )
        assert meta.nodata == -8888.0

    def test_nodata_param_for_tif(self, tmp_path):
        meta = build_metadata(
            get_source("cz.cuzk.dmr5g"),
            request={"bbox": [1.0, 2.0, 3.0, 4.0], "bbox_crs": "EPSG:5514"},
            nodata=-9999.0,
        )
        assert meta.nodata == -9999.0
        assert meta.dataset == "cz.cuzk.dmr5g"
        assert meta.license["id"] == "CC-BY-4.0"
```

Uwaga na kolizję selekcji heurystycznej: `test_capability_unknown_raises_keyerror` używa orto (kanał tylko `sheet_files`).

- [ ] **Krok 2: Uruchom — FAIL**

Run: `.venv/bin/python -m pytest tests/test_sidecar.py -q`
Oczekiwane: FAIL — `TypeError: build_metadata() got an unexpected keyword argument 'capability'`.

- [ ] **Krok 3: Implementacja** — w `sidecar.py`:

```python
def _select_channel_by_capability(
    descriptor: SourceDescriptor, capability: str
) -> AccessChannel:
    """Pierwszy kanal deklarujacy capability; KeyError gdy brak."""
    for ch in descriptor.channels:
        if capability in ch.capabilities:
            return ch
    raise KeyError(
        f"Deskryptor '{descriptor.key}' nie ma kanalu z capability '{capability}'"
    )
```

W `build_metadata` — sygnatura + początek ciała:

```python
def build_metadata(
    descriptor: SourceDescriptor,
    *,
    request: dict,
    vertical_crs: str | None = None,
    data_path: Path | None = None,
    transform: dict | None = None,
    extra: dict | None = None,
    capability: str | None = None,
    nodata: float | None = None,
) -> ResultMetadata:
    """Zbuduj metadane z deskryptora + kontekstu wywolania."""
    from kartograf import __version__  # lazy: unika cyklu importow

    if capability is not None:
        channel = _select_channel_by_capability(descriptor, capability)
    else:
        channel = _select_channel(descriptor, request)

    vertical: str | None = None
    if channel.vertical_crs_options and vertical_crs is not None:
        vertical = resolve_vertical_crs(vertical_crs, channel.vertical_crs_options)

    if nodata is None and data_path is not None and data_path.suffix.lower() == ".asc":
        nodata = read_asc_nodata(data_path)
```

(reszta ciała bez zmian — `nodata=nodata` już trafia do `ResultMetadata`).

- [ ] **Krok 4: Uruchom pełną suitę** — `.venv/bin/python -m pytest tests/ -q` → PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/sources/sidecar.py tests/test_sidecar.py
git commit -m "feat(sidecar): jawna selekcja kanalu (capability=) i jawne nodata= w build_metadata"
```

---

### Zadanie 5: `transform/crs.py` — polimorficzne `transform` + probe pod polityką sieci

Decyzja użytkownika 2026-08-11 (tablice numpy) + spec 5.8b (probe w tym samym kontekście sieci co budowa grupy).

**Files:**
- Modify: `kartograf/transform/crs.py:61-73` (PinnedTransform.transform), `118-176` (build_pinned_transform)
- Test: `tests/test_transform_crs.py`

**Interfaces:**
- Produces: `PinnedTransform.transform(x, y, z=None)` przyjmuje `float | np.ndarray` (zwraca krotkę jak pyproj); probe kandydatów wykonywany w kontekście `pyproj.network` ustawionym wg `policy.allow_network_grids`.
- Consumes: istniejące helpery testowe `_mock_transformer(accuracy, description, result)`, `_mock_group(transformers)`, `_GROUP_PATCH = "kartograf.transform.crs.TransformerGroup"`.

- [ ] **Krok 1: Testy (failing)** — do `tests/test_transform_crs.py` (reużyj istniejących helperów; dodaj `import numpy as np`):

```python
class TestTransformPolymorphic:
    def _pinned(self, transformer):
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([transformer])
            return build_pinned_transform(
                "EPSG:8357", "EPSG:5621", TransformPolicy(min_accuracy_m=0.2)
            )

    def test_transform_accepts_numpy_arrays(self):
        t = _mock_transformer(0.1, "op pionowa")
        t.transform.return_value = (
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
            np.array([300.13, 300.14]),
        )
        pinned = self._pinned(t)
        rx, ry, rz = pinned.transform(np.zeros(2), np.zeros(2), np.zeros(2))
        assert rz.tolist() == [300.13, 300.14]

    def test_transform_array_with_inf_raises(self):
        t = _mock_transformer(0.1, "op pionowa")
        t.transform.return_value = (
            np.array([1.0, np.inf]),
            np.array([3.0, 4.0]),
        )
        pinned = self._pinned(t)
        with pytest.raises(TransformError, match="nieskonczon"):
            pinned.transform(np.zeros(2), np.zeros(2))


class TestProbeUnderNetworkPolicy:
    def test_probe_runs_under_policy_network_context(self):
        """5.8b: probe wykonuje sie w kontekscie sieci wg policy,
        a nie po przywroceniu stanu globalnego."""
        before = network.is_network_enabled()
        states_during_probe = []

        t = _mock_transformer(0.5, "op z probe")

        def _probe(x, y):
            states_during_probe.append(network.is_network_enabled())
            return (x, y)

        t.transform.side_effect = _probe
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([t])
            build_pinned_transform(
                "EPSG:5514",
                "EPSG:2180",
                TransformPolicy(
                    allow_network_grids=not before, probe_point=(1.0, 2.0)
                ),
            )
        assert states_during_probe == [not before]
        assert network.is_network_enabled() == before
```

- [ ] **Krok 2: Uruchom — FAIL**

Run: `.venv/bin/python -m pytest tests/test_transform_crs.py -q`
Oczekiwane: FAIL — `test_probe_runs_under_policy_network_context` (probe biegnie po przywróceniu stanu) oraz ewentualnie `math.isfinite` na tablicy (`TypeError: only size-1 arrays...`).

- [ ] **Krok 3: Implementacja**

Nagłówek modułu: `import numpy as np` (usuń `import math`, jeśli nieużywany po zmianach — `math.isfinite` znika z obu miejsc).

`PinnedTransform.transform`:

```python
    def transform(self, x, y, z=None):
        """Transformuj punkt lub tablice numpy; wynik inf/NaN => TransformError."""
        if z is None:
            result = self._transformer.transform(x, y)
        else:
            result = self._transformer.transform(x, y, z)
        if not all(bool(np.all(np.isfinite(v))) for v in result):
            raise TransformError(
                f"Transformacja zwrocila wartosc nieskonczona [{self.description}]"
            )
        return result
```

Uwaga: jeśli istniejący `test_result_isfinite_guard` (l.121) asertuje fragment komunikatu ze współrzędnymi `({x}, {y})` — zaktualizuj jego `match` na `"nieskonczon"` (komunikat nie może interpolować tablic; to jedyna dozwolona korekta tego testu).

`build_pinned_transform` — przenieś pętlę filtrowania (w tym probe) DO bloku `try/finally` kontekstu sieci:

```python
    previous_network_enabled = network.is_network_enabled()
    network.set_network_enabled(policy.allow_network_grids)
    try:
        group = TransformerGroup(
            src_crs, dst_crs, always_xy=True, allow_ballpark=False
        )
        rejected: list[tuple[str, str]] = []
        candidates = []
        for transformer in group.transformers:
            # ... (cala dotychczasowa petla l.134-163 bez zmian merytorycznych,
            #      z probe wlacznie — teraz pod ta sama polityka sieci,
            #      w miejscu math.isfinite -> np.isfinite)
    finally:
        network.set_network_enabled(previous_network_enabled)

    if not candidates:
        ...  # bez zmian (l.165-171)
```

W pętli probe podmień `all(math.isfinite(v) for v in probe)` na `all(bool(np.all(np.isfinite(v))) for v in probe)`.

- [ ] **Krok 4: Uruchom pełną suitę** — `.venv/bin/python -m pytest tests/ -q` → PASS (w tym `test_network_state_restored` — stan globalny nadal przywracany).

- [ ] **Krok 5: Commit**

```bash
git add kartograf/transform/crs.py tests/test_transform_crs.py
git commit -m "feat(transform): polimorficzne PinnedTransform.transform (numpy) + probe pod polityka sieci (5.8b)"
```

---

### Zadanie 6: `core/parser_tm33.py` — ParserTM33 (czysta matematyka)

Wzór: `Parser2000` (bez hierarchii — TM33 ma jedną skalę). Zero IO.

**Files:**
- Create: `kartograf/core/parser_tm33.py`
- Test: `tests/test_parser_tm33.py`

**Interfaces:**
- Produces: `ParserTM33(godlo: str)` z atrybutami `godlo: str`, `uklad = "cz_tm33"`, metodą `get_bbox() -> BBox` (EPSG:3045) i staticmethod `tile_for(easting: float, northing: float) -> str`; `find_tiles_tm33_for_bbox(bbox: BBox) -> list[str]`; stałe `TM33_CRS = "EPSG:3045"`, `TILE_SIZE_M = 2000`.
- Consumes: `BBox` (NamedTuple: `min_x, min_y, max_x, max_y, crs`), `ParseError`, `ValidationError`.

- [ ] **Krok 1: Testy (failing)** — `tests/test_parser_tm33.py`:

```python
"""Testy jednostkowe dla modulu parser_tm33 (siatka CZ TM33 2x2 km)."""

import pytest

from kartograf.core.parser_tm33 import (
    TILE_SIZE_M,
    TM33_CRS,
    ParserTM33,
    find_tiles_tm33_for_bbox,
)
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError


class TestParserTM33Parsing:
    def test_valid_godlo(self):
        p = ParserTM33("302_5550")
        assert p.godlo == "302_5550"
        assert p.uklad == "cz_tm33"

    def test_whitespace_stripped(self):
        assert ParserTM33("  302_5550 ").godlo == "302_5550"

    def test_non_string_raises_parse_error(self):
        with pytest.raises(ParseError, match="stringiem"):
            ParserTM33(123)

    @pytest.mark.parametrize(
        "godlo",
        ["302-5550", "3025550", "30_5550", "302_555", "302_55501", "abc_5550", ""],
    )
    def test_invalid_format_raises(self, godlo):
        with pytest.raises(ParseError):
            ParserTM33(godlo)

    @pytest.mark.parametrize("godlo", ["303_5550", "302_5551", "301_5549"])
    def test_odd_kilometers_raise(self, godlo):
        """Kafle co 2 km — nieparzyste kilometry to nie naroznik SW."""
        with pytest.raises(ParseError, match="parzyste"):
            ParserTM33(godlo)


class TestParserTM33BBox:
    def test_bbox_research_example(self):
        """Przyklad zweryfikowany researchem: 302_5550."""
        bbox = ParserTM33("302_5550").get_bbox()
        assert bbox == BBox(302_000, 5_550_000, 304_000, 5_552_000, "EPSG:3045")

    def test_bbox_second_example(self):
        """756_5516 — kafel z openzu (DMR5G/epsg-3045)."""
        bbox = ParserTM33("756_5516").get_bbox()
        assert bbox == BBox(756_000, 5_516_000, 758_000, 5_518_000, "EPSG:3045")


class TestTileFor:
    def test_sw_corner_maps_to_itself(self):
        assert ParserTM33.tile_for(302_000.0, 5_550_000.0) == "302_5550"

    def test_interior_point(self):
        assert ParserTM33.tile_for(303_999.9, 5_551_999.9) == "302_5550"

    def test_next_tile_at_east_edge(self):
        assert ParserTM33.tile_for(304_000.0, 5_550_000.0) == "304_5550"


class TestFindTilesTM33ForBBox:
    def test_single_tile(self):
        bbox = BBox(302_500, 5_550_500, 303_500, 5_551_500, "EPSG:3045")
        assert find_tiles_tm33_for_bbox(bbox) == ["302_5550"]

    def test_two_by_two(self):
        bbox = BBox(301_000, 5_549_000, 305_000, 5_553_000, "EPSG:3045")
        assert find_tiles_tm33_for_bbox(bbox) == [
            "300_5548",
            "302_5548",
            "304_5548",
            "300_5550",
            "302_5550",
            "304_5550",
            "300_5552",
            "302_5552",
            "304_5552",
        ]

    def test_touching_edge_excluded(self):
        """max dokladnie na krawedzi kafla — kafel za krawedzia NIE wchodzi."""
        bbox = BBox(302_000, 5_550_000, 304_000, 5_552_000, "EPSG:3045")
        assert find_tiles_tm33_for_bbox(bbox) == ["302_5550"]

    def test_wrong_crs_raises(self):
        with pytest.raises(ValidationError, match="EPSG:3045"):
            find_tiles_tm33_for_bbox(BBox(0, 0, 1, 1, "EPSG:2180"))

    def test_degenerate_bbox_raises(self):
        with pytest.raises(ValidationError):
            find_tiles_tm33_for_bbox(
                BBox(302_000, 5_550_000, 302_000, 5_552_000, "EPSG:3045")
            )

    def test_constants(self):
        assert TM33_CRS == "EPSG:3045"
        assert TILE_SIZE_M == 2000
```

- [ ] **Krok 2: Uruchom — FAIL** (`ModuleNotFoundError`).

Run: `.venv/bin/python -m pytest tests/test_parser_tm33.py -q`

- [ ] **Krok 3: Implementacja** — `kartograf/core/parser_tm33.py`:

```python
"""
ParserTM33 — obliczalna siatka kafli 2x2 km ETRS89/TM33N (EPSG:3045) dla CZ.

Godlo `{E_km}_{N_km}` to naroznik SW kafla (np. "302_5550" => E 302000..304000,
N 5550000..5552000; zweryfikowane wobec georss w researchu 2026-08-10).
Czysta matematyka, zero IO — wzor: Parser2000.
"""

import math
import re

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError

TM33_CRS = "EPSG:3045"
TILE_SIZE_M = 2000

_GODLO_RE = re.compile(r"^(\d{3})_(\d{4})$")


class ParserTM33:
    """Parser godel siatki TM33 (naroznik SW, krok 2 km)."""

    uklad = "cz_tm33"

    def __init__(self, godlo: str):
        if not isinstance(godlo, str):
            raise ParseError(
                f"Godlo TM33 musi byc stringiem, otrzymano: {type(godlo).__name__}"
            )
        godlo = godlo.strip()
        match = _GODLO_RE.match(godlo)
        if not match:
            raise ParseError(
                f"Niepoprawne godlo TM33: '{godlo}' "
                f"(oczekiwano EEE_NNNN, np. 302_5550)"
            )
        e_km, n_km = int(match.group(1)), int(match.group(2))
        if e_km % 2 or n_km % 2:
            raise ParseError(
                f"Niepoprawne godlo TM33: '{godlo}' "
                f"(kafle co 2 km — kilometry musza byc parzyste)"
            )
        self.godlo = godlo
        self._west = e_km * 1000
        self._south = n_km * 1000

    def get_bbox(self) -> BBox:
        """BBox kafla w EPSG:3045."""
        return BBox(
            self._west,
            self._south,
            self._west + TILE_SIZE_M,
            self._south + TILE_SIZE_M,
            TM33_CRS,
        )

    @staticmethod
    def tile_for(easting: float, northing: float) -> str:
        """Godlo kafla zawierajacego punkt (EPSG:3045)."""
        e_km = int(math.floor(easting / TILE_SIZE_M)) * 2
        n_km = int(math.floor(northing / TILE_SIZE_M)) * 2
        return f"{e_km:03d}_{n_km:04d}"

    def __repr__(self) -> str:
        return f"ParserTM33('{self.godlo}')"


def find_tiles_tm33_for_bbox(bbox: BBox) -> list[str]:
    """Godla kafli TM33 przecinajacych bbox (EPSG:3045).

    Krawedzie stykajace sie NIE licza sie jako przeciecie (kafel wchodzi,
    gdy jego wnetrze przecina bbox). Kolejnosc: wiersze S->N, kolumny W->E.
    """
    if bbox.crs != TM33_CRS:
        raise ValidationError(
            f"find_tiles_tm33_for_bbox wymaga bbox w {TM33_CRS}, "
            f"otrzymano: {bbox.crs}"
        )
    if bbox.min_x >= bbox.max_x or bbox.min_y >= bbox.max_y:
        raise ValidationError(
            f"Niepoprawny bbox: ({bbox.min_x}, {bbox.min_y}, "
            f"{bbox.max_x}, {bbox.max_y})"
        )
    e_start = int(math.floor(bbox.min_x / TILE_SIZE_M)) * TILE_SIZE_M
    n_start = int(math.floor(bbox.min_y / TILE_SIZE_M)) * TILE_SIZE_M
    tiles: list[str] = []
    north = n_start
    while north < bbox.max_y:
        east = e_start
        while east < bbox.max_x:
            tiles.append(f"{east // 1000:03d}_{north // 1000:04d}")
            east += TILE_SIZE_M
        north += TILE_SIZE_M
    return tiles
```

- [ ] **Krok 4: Uruchom** — `.venv/bin/python -m pytest tests/test_parser_tm33.py -q` → PASS; potem pełna suita.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/core/parser_tm33.py tests/test_parser_tm33.py
git commit -m "feat(core): ParserTM33 — obliczalna siatka kafli 2x2 km EPSG:3045 (CZ)"
```

---

### Zadanie 7: `MetadataCache` — tabela `sheet_cache` + CLI `cache stats`

Trzecia tabela z własnym TTL 30 dni (indeks arkuszy praktycznie stały). Stare bazy doposażają się same (`CREATE TABLE IF NOT EXISTS` w `_create_tables`).

**Files:**
- Modify: `kartograf/cache/metadata.py` (DDL, `get_sheet`/`set_sheet`, `clear`, `stats`, `prune_expired`)
- Modify: `kartograf/cli/cache_cmd.py:41` (linia `Sheet entries`)
- Test: `tests/test_metadata_cache.py`

**Interfaces:**
- Produces: `SHEET_TTL_SECONDS = 30 * 24 * 3600` (stała modułowa); `MetadataCache.get_sheet(system: str, godlo: str) -> dict | None`; `MetadataCache.set_sheet(system: str, godlo: str, payload: dict) -> None`; `stats()` z kluczem `sheet_count`; `clear()`/`prune_expired()` obejmują `sheet_cache`.
- Consumes: nic nowego.

- [ ] **Krok 1: Testy (failing)** — do `tests/test_metadata_cache.py` nowa klasa + modyfikacje:

```python
class TestMetadataCacheSheet:
    """Tabela sheet_cache (indeks arkuszy CZ) — TTL wg SHEET_TTL_SECONDS."""

    _PAYLOAD = {
        "godlo": "CTES96",
        "name": "Cesky Tesin 8-6",
        "bbox": [-450000.0, -1105000.0, -447500.0, -1103000.0],
        "bbox_crs": "EPSG:5514",
        "podil": 0.507,
        "in_cz": None,
    }

    def test_set_and_get(self, cache):
        cache.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        assert cache.get_sheet("cz_sm5", "CTES96") == self._PAYLOAD

    def test_get_returns_none_when_missing(self, cache):
        assert cache.get_sheet("cz_sm5", "XXXX99") is None

    def test_systems_are_separate(self, cache):
        cache.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        assert cache.get_sheet("cz_tm33", "CTES96") is None

    def test_sheet_ttl_expiry(self, cache, monkeypatch):
        cache.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        monkeypatch.setattr("kartograf.cache.metadata.SHEET_TTL_SECONDS", 0)
        assert cache.get_sheet("cz_sm5", "CTES96") is None
        # wpis usuniety oportunistycznie
        row = cache._conn.execute("SELECT COUNT(*) FROM sheet_cache").fetchone()
        assert row[0] == 0

    def test_sheet_ttl_independent_from_url_ttl(self, cache_path):
        """ttl_seconds=1 (url/teryt) nie dotyczy sheet_cache (TTL 30 dni)."""
        c = MetadataCache(db_path=cache_path, ttl_seconds=1)
        c.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        time.sleep(1.1)
        assert c.get_sheet("cz_sm5", "CTES96") == self._PAYLOAD
        c.close()

    def test_prune_expired_covers_sheet_cache(self, cache, monkeypatch):
        cache.set_sheet("cz_sm5", "CTES96", self._PAYLOAD)
        monkeypatch.setattr("kartograf.cache.metadata.SHEET_TTL_SECONDS", 0)
        assert cache.prune_expired() == 1

    def test_old_database_gains_sheet_table(self, cache_path):
        """Stara baza (bez sheet_cache) doposaza sie przy otwarciu."""
        c = MetadataCache(db_path=cache_path)
        c._conn.execute("DROP TABLE sheet_cache")
        c._conn.commit()
        c._conn.close()
        c._conn = None
        c2 = MetadataCache(db_path=cache_path)
        assert c2.stats()["sheet_count"] == 0
        c2.close()
```

Modyfikacje istniejących testów:
- `test_clear` (l.245): dopisz `cache.set_sheet("cz_sm5", "CTES96", {"podil": 0.5})` przed `cache.clear()` i `assert cache.get_sheet("cz_sm5", "CTES96") is None` po.
- `test_stats` (l.253): dopisz asercje `assert st["sheet_count"] == 0` (pierwszy odczyt) oraz po `cache.set_sheet("cz_sm5", "CTES96", {"podil": 0.5})` → `assert st["sheet_count"] == 1` (drugi odczyt).
- `test_cmd_cache_stats` (l.591): dopisz asercję, że wyjście zawiera `"Sheet entries:"`.

- [ ] **Krok 2: Uruchom — FAIL**

Run: `.venv/bin/python -m pytest tests/test_metadata_cache.py -q`
Oczekiwane: FAIL — `AttributeError: 'MetadataCache' object has no attribute 'set_sheet'`.

- [ ] **Krok 3: Implementacja** — `kartograf/cache/metadata.py`:

Po `DEFAULT_TTL_SECONDS` dodaj:

```python
# TTL dla sheet_cache (indeks arkuszy CZ jest praktycznie staly): 30 dni.
SHEET_TTL_SECONDS = 30 * 24 * 3600
```

`import json` w nagłówku. W `_create_tables` trzecia tabela:

```python
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sheet_cache (
                    system    TEXT NOT NULL,
                    godlo     TEXT NOT NULL,
                    payload   TEXT NOT NULL,
                    cached_at REAL NOT NULL,
                    PRIMARY KEY (system, godlo)
                )
                """
            )
```

Nowa sekcja po TERYT cache:

```python
    # =========================================================================
    # Sheet cache (indeks arkuszy CZ: KladyMapovychListu)
    # =========================================================================

    def get_sheet(self, system: str, godlo: str) -> dict | None:
        """Zwroc zdekodowany payload arkusza albo None (brak/wygasly)."""
        cursor = self._conn.execute(
            "SELECT payload, cached_at FROM sheet_cache WHERE system=? AND godlo=?",
            (system, godlo),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        payload, cached_at = row
        if time.time() - cached_at >= SHEET_TTL_SECONDS:
            logger.debug(f"Sheet cache expired for {system}/{godlo}")
            with self._write_lock:
                self._conn.execute(
                    "DELETE FROM sheet_cache WHERE system=? AND godlo=?",
                    (system, godlo),
                )
                self._conn.commit()
            return None
        logger.debug(f"Sheet cache hit for {system}/{godlo}")
        return json.loads(payload)

    def set_sheet(self, system: str, godlo: str, payload: dict) -> None:
        """Zapisz payload arkusza (JSON) pod kluczem (system, godlo)."""
        with self._write_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO sheet_cache
                (system, godlo, payload, cached_at) VALUES (?, ?, ?, ?)
                """,
                (system, godlo, json.dumps(payload, ensure_ascii=False), time.time()),
            )
            self._conn.commit()
        logger.debug(f"Cached sheet {system}/{godlo}")
```

`clear()`: dodaj `self._conn.execute("DELETE FROM sheet_cache")`. `stats()`: `sheet_count = self._conn.execute("SELECT COUNT(*) FROM sheet_cache").fetchone()[0]` + klucz w słowniku. `prune_expired()`: po teryt dodaj:

```python
            sheet_cutoff = now - SHEET_TTL_SECONDS
            self._conn.execute(
                "DELETE FROM sheet_cache WHERE cached_at < ?", (sheet_cutoff,)
            )
            sheet_deleted = self._conn.execute("SELECT changes()").fetchone()[0]
```

i `total = url_deleted + teryt_deleted + sheet_deleted` (log rozszerz o sheet).

`cli/cache_cmd.py` — po linii `TERYT entries` (l.41):

```python
            print(f"  Sheet entries: {st['sheet_count']}")
```

- [ ] **Krok 4: Uruchom pełną suitę** — PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/cache/metadata.py kartograf/cli/cache_cmd.py tests/test_metadata_cache.py
git commit -m "feat(cache): tabela sheet_cache (TTL 30 dni) + Sheet entries w cache stats"
```

---

### Zadanie 8: `CuzkClient` — `query` (paginacja) i `fetch_file` (ZIP→TIFF+tfw)

Silnik generyczny: parametryzowany endpointem, bez wiedzy o produktach/godłach/sidecarach. Kształt odpowiedzi `/query` — wg fixtur z Zadania 1 (jeśli odbiegają od poniższego standardu ArcGIS, dostosuj implementację do fixtur; fixtura jest źródłem prawdy).

**Files:**
- Create: `kartograf/providers/cuzk/__init__.py` (na razie pusty docstring — fabryka dojdzie w Zad. 12)
- Create: `kartograf/providers/cuzk/client.py`
- Test: `tests/test_cuzk_client.py`

**Interfaces:**
- Produces: `CuzkClient(session: requests.Session | None = None, timeout: int = 60)` ze stałą klasową `QUERY_PAGE_SIZE = 2000`; `query(endpoint: str, layer: int, *, bbox: BBox | None = None, where: str | None = None, out_fields: str = "*", out_sr: str | None = None) -> list[dict]` (lista feature'ów `{"attributes": ..., "geometry": ...}`; paginacja `resultOffset`/`resultRecordCount`); `fetch_file(url: str, output_path: Path, *, unzip_single: str | None = None) -> Path`; `_wkid(crs: str) -> str` (helper modułowy).
- Consumes: `transport.http.download_to`, `DownloadError`, `BBox`.
- Patch-target testów: `_CUZK_SESSION_PATCH = "kartograf.providers.cuzk.client.requests.Session"`; dla fetch_file: `kartograf.providers.cuzk.client.download_to`.

- [ ] **Krok 1: Testy (failing)** — `tests/test_cuzk_client.py`:

```python
"""Testy CuzkClient — silnik ArcGIS REST + pliki openzu (offline)."""

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.cuzk.client import CuzkClient, _wkid

_CUZK_SESSION_PATCH = "kartograf.providers.cuzk.client.requests.Session"
_DOWNLOAD_TO_PATCH = "kartograf.providers.cuzk.client.download_to"

KLADY = "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer"


def _json_response(payload):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = payload
    return response


def _feature(mapnom="CTES96", podil=0.507):
    return {
        "attributes": {"MAPNOM": mapnom, "MAPNAME": "Cesky Tesin 8-6", "PODIL": podil},
        "geometry": {"rings": [[[-450000, -1105000], [-447500, -1105000],
                                [-447500, -1103000], [-450000, -1103000],
                                [-450000, -1105000]]]},
    }


class TestWkid:
    def test_epsg_prefix_stripped(self):
        assert _wkid("EPSG:5514") == "5514"

    def test_bare_code_passes(self):
        assert _wkid("3045") == "3045"


class TestSessionOwnership:
    def test_creates_own_session_when_none(self):
        with patch(_CUZK_SESSION_PATCH) as session_cls:
            client = CuzkClient()
        assert client._session is session_cls.return_value

    def test_injected_session_is_used(self):
        session = Mock()
        assert CuzkClient(session=session)._session is session


class TestQuery:
    def test_where_query_builds_params(self):
        session = Mock()
        session.get.return_value = _json_response({"features": [_feature()]})
        client = CuzkClient(session=session)

        features = client.query(
            KLADY, 24, where="MAPNOM='CTES96'",
            out_fields="MAPNOM,MAPNAME,PODIL", out_sr="EPSG:5514",
        )

        assert len(features) == 1
        (url,), kwargs = session.get.call_args
        assert url == f"{KLADY}/24/query"
        params = kwargs["params"]
        assert params["f"] == "json"
        assert params["where"] == "MAPNOM='CTES96'"
        assert params["outFields"] == "MAPNOM,MAPNAME,PODIL"
        assert params["outSR"] == "5514"
        assert params["resultOffset"] == "0"
        assert "geometry" not in params

    def test_bbox_query_builds_envelope(self):
        session = Mock()
        session.get.return_value = _json_response({"features": []})
        client = CuzkClient(session=session)

        client.query(KLADY, 26, bbox=BBox(744000, 5540000, 760000, 5556000, "EPSG:3045"))

        params = session.get.call_args.kwargs["params"]
        assert params["geometry"] == "744000,5540000,760000,5556000"
        assert params["geometryType"] == "esriGeometryEnvelope"
        assert params["inSR"] == "3045"
        assert params["spatialRel"] == "esriSpatialRelIntersects"

    def test_pagination_follows_exceeded_transfer_limit(self):
        session = Mock()
        page1 = {"features": [_feature("AAAA01"), _feature("AAAA02")],
                 "exceededTransferLimit": True}
        page2 = {"features": [_feature("AAAA03")]}
        session.get.side_effect = [_json_response(page1), _json_response(page2)]
        client = CuzkClient(session=session)

        features = client.query(KLADY, 24, where="1=1")

        assert [f["attributes"]["MAPNOM"] for f in features] == [
            "AAAA01", "AAAA02", "AAAA03",
        ]
        assert session.get.call_count == 2
        first_params = session.get.call_args_list[0].kwargs["params"]
        assert first_params["resultRecordCount"] == str(CuzkClient.QUERY_PAGE_SIZE)
        second_params = session.get.call_args_list[1].kwargs["params"]
        assert second_params["resultOffset"] == "2"

    def test_arcgis_error_payload_raises(self):
        session = Mock()
        session.get.return_value = _json_response(
            {"error": {"code": 400, "message": "Invalid query"}}
        )
        client = CuzkClient(session=session)
        with pytest.raises(DownloadError, match="Invalid query"):
            client.query(KLADY, 24, where="zle")

    def test_real_fixture_shape_parses(self):
        """Fixture z rekonesansu (Zad. 1) przechodzi przez query 1:1."""
        fixture = json.loads(
            Path("tests/fixtures/cuzk/klady_sm5_where_ctes96.json").read_text(
                encoding="utf-8"
            )
        )
        session = Mock()
        session.get.return_value = _json_response(fixture)
        features = CuzkClient(session=session).query(KLADY, 24, where="MAPNOM='CTES96'")
        assert features[0]["attributes"]["MAPNOM"] == "CTES96"


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestFetchFile:
    def _client_with_zip(self, tmp_path, zip_content: bytes):
        def fake_download(session, url, output_path, *, timeout, **kwargs):
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(zip_content)
            return Path(output_path)

        return fake_download

    def test_plain_download_delegates_to_download_to(self, tmp_path):
        target = tmp_path / "plik.laz"
        with patch(_DOWNLOAD_TO_PATCH) as mock_dl:
            mock_dl.return_value = target
            result = CuzkClient(session=Mock()).fetch_file("http://x/plik.laz", target)
        assert result == target
        assert mock_dl.call_count == 1

    def test_unzip_single_extracts_tif_and_tfw(self, tmp_path):
        zip_content = _zip_bytes(
            {"CTES96.tif": b"II*\x00tifdata", "CTES96.tfw": b"5\n0\n0\n-5\n1\n2\n"}
        )
        target = tmp_path / "CTES96.tif"
        with patch(_DOWNLOAD_TO_PATCH, side_effect=self._client_with_zip(tmp_path, zip_content)):
            result = CuzkClient(session=Mock()).fetch_file(
                "http://x/CTES96.zip", target, unzip_single=".tif"
            )
        assert result == target
        assert target.read_bytes() == b"II*\x00tifdata"
        assert (tmp_path / "CTES96.tfw").read_bytes().startswith(b"5\n")
        # ZIP posprzatany
        assert list(tmp_path.glob("*.zip")) == []

    def test_unzip_single_without_expected_file_raises(self, tmp_path):
        zip_content = _zip_bytes({"readme.txt": b"nic"})
        target = tmp_path / "CTES96.tif"
        with patch(_DOWNLOAD_TO_PATCH, side_effect=self._client_with_zip(tmp_path, zip_content)):
            with pytest.raises(DownloadError, match="1 pliku"):
                CuzkClient(session=Mock()).fetch_file(
                    "http://x/CTES96.zip", target, unzip_single=".tif"
                )
        assert not target.exists()

    def test_corrupted_zip_raises_download_error(self, tmp_path):
        target = tmp_path / "CTES96.tif"
        with patch(_DOWNLOAD_TO_PATCH, side_effect=self._client_with_zip(tmp_path, b"to nie zip")):
            with pytest.raises(DownloadError, match="ZIP"):
                CuzkClient(session=Mock()).fetch_file(
                    "http://x/CTES96.zip", target, unzip_single=".tif"
                )


class TestRetryPropagation:
    """Retry/backoff pochodzi z transport.download_to — spec 7:
    wyczerpanie prob => DownloadError."""

    def test_fetch_file_exhausts_retries(self, tmp_path):
        import requests as requests_lib

        session = Mock()
        session.get.side_effect = requests_lib.RequestException("padlo")
        with patch("kartograf.transport.http.time.sleep") as mock_sleep:
            with pytest.raises(DownloadError, match="3 probach"):
                CuzkClient(session=session).fetch_file(
                    "http://x/CTES96.zip", tmp_path / "CTES96.zip"
                )
        assert session.get.call_count == 3
        assert mock_sleep.call_count == 2
```

- [ ] **Krok 2: Uruchom — FAIL** (`ModuleNotFoundError: kartograf.providers.cuzk`).

Run: `.venv/bin/python -m pytest tests/test_cuzk_client.py -q`

- [ ] **Krok 3: Implementacja**

`kartograf/providers/cuzk/__init__.py`:

```python
"""Providery czeskich zrodel danych (CUZK)."""
```

`kartograf/providers/cuzk/client.py`:

```python
"""
CuzkClient — silnik zrodel CUZK: ArcGIS REST (exportImage, query) + pliki openzu.

Pierwszy silnik sterowany deskryptorem (ADR-022/ADR-023): metody sa generyczne,
parametryzowane endpointem; klient nie zna godel, produktow ani sidecarow.
Retry/backoff i atomic write pochodza z transport/http.py.
"""

import os
import threading
import zipfile
from pathlib import Path

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.transport.http import download_to

_TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


def _wkid(crs: str) -> str:
    """'EPSG:5514' -> '5514' (ArcGIS przyjmuje goly wkid)."""
    return crs.split(":", 1)[1] if ":" in crs else crs


class CuzkClient:
    """Transport CUZK: zapytania ArcGIS REST i pobieranie plikow openzu."""

    MAX_EXPORT_WIDTH = 15000
    MAX_EXPORT_HEIGHT = 4100
    QUERY_PAGE_SIZE = 2000  # maxRecordCount uslug CUZK (potwierdzone w Zad. 1)

    def __init__(self, session: requests.Session | None = None, timeout: int = 60):
        self._session = session or requests.Session()
        self._timeout = timeout

    def query(
        self,
        endpoint: str,
        layer: int,
        *,
        bbox: BBox | None = None,
        where: str | None = None,
        out_fields: str = "*",
        out_sr: str | None = None,
    ) -> list[dict]:
        """GET {endpoint}/{layer}/query (f=json) z paginacja resultOffset."""
        url = f"{endpoint}/{layer}/query"
        features: list[dict] = []
        offset = 0
        while True:
            params: dict[str, str] = {
                "f": "json",
                "outFields": out_fields,
                "returnGeometry": "true",
                "resultOffset": str(offset),
                "resultRecordCount": str(self.QUERY_PAGE_SIZE),
            }
            if where is not None:
                params["where"] = where
            if bbox is not None:
                params["geometry"] = (
                    f"{bbox.min_x},{bbox.min_y},{bbox.max_x},{bbox.max_y}"
                )
                params["geometryType"] = "esriGeometryEnvelope"
                params["inSR"] = _wkid(bbox.crs)
                params["spatialRel"] = "esriSpatialRelIntersects"
            if out_sr is not None:
                params["outSR"] = _wkid(out_sr)
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as e:
                raise DownloadError(f"Zapytanie {url} nieudane: {e}") from e
            if "error" in data:
                raise DownloadError(f"Blad ArcGIS dla {url}: {data['error']}")
            page = data.get("features", [])
            features.extend(page)
            if data.get("exceededTransferLimit") and page:
                offset += len(page)
                continue
            return features

    def fetch_file(
        self,
        url: str,
        output_path: Path,
        *,
        unzip_single: str | None = None,
    ) -> Path:
        """Pobierz plik; przy unzip_single wyciagnij jedyny plik o rozszerzeniu
        (+ towarzyszacy .tfw), zapisz atomowo, usun ZIP."""
        output_path = Path(output_path)
        if unzip_single is None:
            return download_to(
                self._session, url, output_path, timeout=self._timeout
            )

        zip_path = output_path.with_name(
            f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.zip"
        )
        download_to(self._session, url, zip_path, timeout=self._timeout)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                suffix = unzip_single.lower()
                names = [n for n in zf.namelist() if n.lower().endswith(suffix)]
                if len(names) != 1:
                    raise DownloadError(
                        f"ZIP {url}: oczekiwano dokladnie 1 pliku "
                        f"'{unzip_single}', znaleziono {len(names)}"
                    )
                _extract_member(zf, names[0], output_path)
                stem = names[0].rsplit(".", 1)[0].lower()
                tfw = next(
                    (n for n in zf.namelist() if n.lower() == f"{stem}.tfw"), None
                )
                if tfw is not None:
                    _extract_member(zf, tfw, output_path.with_suffix(".tfw"))
        except zipfile.BadZipFile as e:
            raise DownloadError(f"Uszkodzony ZIP z {url}: {e}") from e
        finally:
            zip_path.unlink(missing_ok=True)
        return output_path


def _extract_member(zf: zipfile.ZipFile, member: str, target: Path) -> None:
    """Wypakuj element ZIP do target atomowo (tmp + os.replace)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(
        f"{target.name}.{os.getpid()}_{threading.get_ident()}.tmp"
    )
    try:
        with zf.open(member) as src, open(tmp, "wb") as dst:
            while chunk := src.read(1_048_576):
                dst.write(chunk)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
```

- [ ] **Krok 4: Uruchom** — `.venv/bin/python -m pytest tests/test_cuzk_client.py -q` → PASS; pełna suita → PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/providers/cuzk/ tests/test_cuzk_client.py
git commit -m "feat(cuzk): CuzkClient.query (paginacja ArcGIS) i fetch_file (openzu ZIP->TIFF+tfw)"
```

---

### Zadanie 9: `CuzkClient.export_image` — GeoTIFF z exportImage + kafelkowanie

Reguły: `noData` NIGDY nie jest pomijane; odpowiedź nie-TIFF → `DownloadError` z początkiem treści; powyżej limitów 15000×4100 px — deterministyczna siatka kafli ciętych po pełnych pikselach + `mosaic_and_crop`. Kafelkowanie wymaga `bbox.crs == image_sr` (kafle w układzie wyjściowym — bez szwów); w przeciwnym razie `ValidationError` (provider normalizuje bbox wcześniej — Zad. 12).

**Files:**
- Modify: `kartograf/providers/cuzk/client.py`
- Test: `tests/test_cuzk_client.py`

**Interfaces:**
- Produces: `export_image(endpoint: str, bbox: BBox, *, pixel_size: float, image_sr: str, no_data: float = -9999.0, output_path: Path) -> Path`; helper modułowy `_tile_grid(bbox, pixel_size, width_px, height_px, max_w, max_h) -> list[tuple[BBox, int, int]]`.
- Consumes: `transport.mosaic.mosaic_and_crop`, `download_to`, `ValidationError`.

- [ ] **Krok 1: Testy (failing)** — do `tests/test_cuzk_client.py` (dodaj importy: `rasterio`, `numpy as np`, `ValidationError`, `from urllib.parse import parse_qs, urlparse`):

```python
DMR5G = "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"

# 4-bajtowy naglowek TIFF little-endian + smieci — wystarcza do sniffowania
_FAKE_TIFF = b"II*\x00" + b"\x00" * 16


def _write_geotiff(path: Path, bbox: BBox, width: int, height: int,
                   value: float = 100.0, nodata: float = -9999.0) -> None:
    """Syntetyczny GeoTIFF float32 pokrywajacy bbox (do testow mozaiki)."""
    from rasterio.transform import from_bounds

    transform = from_bounds(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y,
                            width, height)
    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "width": width, "height": height,
        "crs": "EPSG:3045", "transform": transform, "nodata": nodata,
    }
    data = np.full((height, width), value, dtype="float32")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


class TestExportImage:
    def test_single_shot_url_params(self, tmp_path):
        captured = {}

        def fake_download(session, url, output_path, *, timeout, **kwargs):
            captured["url"] = url
            Path(output_path).write_bytes(_FAKE_TIFF)
            return Path(output_path)

        target = tmp_path / "out.tif"
        bbox = BBox(302000, 5550000, 304000, 5552000, "EPSG:3045")
        with patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download):
            CuzkClient(session=Mock()).export_image(
                DMR5G, bbox, pixel_size=2.0, image_sr="EPSG:3045",
                output_path=target,
            )

        parsed = urlparse(captured["url"])
        assert parsed.path.endswith("/exportImage")
        params = parse_qs(parsed.query)
        assert params["f"] == ["image"]
        assert params["format"] == ["tiff"]
        assert params["pixelType"] == ["F32"]
        assert params["bbox"] == ["302000,5550000,304000,5552000"]
        assert params["bboxSR"] == ["3045"]
        assert params["imageSR"] == ["3045"]
        assert params["size"] == ["1000,1000"]
        assert params["noData"] == ["-9999"]
        assert params["noDataInterpretation"] == ["esriNoDataMatchAny"]

    def test_non_tiff_response_raises_with_content(self, tmp_path):
        def fake_download(session, url, output_path, *, timeout, **kwargs):
            Path(output_path).write_bytes(b'{"error":{"code":400,"message":"Bad"}}')
            return Path(output_path)

        target = tmp_path / "out.tif"
        bbox = BBox(0, 0, 100, 100, "EPSG:5514")
        with patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download):
            with pytest.raises(DownloadError, match="error"):
                CuzkClient(session=Mock()).export_image(
                    DMR5G, bbox, pixel_size=2.0, image_sr="EPSG:5514",
                    output_path=target,
                )
        assert not target.exists()

    def test_tiling_above_limits_mosaics(self, tmp_path):
        """Patch limitow na male wartosci: bbox 8x8 px przy limicie 4x4
        => 4 kafle 4x4, kazdy z tym samym noData, zszyte mosaic_and_crop."""
        requested = []

        def fake_download(session, url, output_path, *, timeout, **kwargs):
            params = parse_qs(urlparse(url).query)
            tile_bbox = [float(v) for v in params["bbox"][0].split(",")]
            w, h = (int(v) for v in params["size"][0].split(","))
            requested.append((tile_bbox, w, h, params["noData"][0]))
            _write_geotiff(
                Path(output_path),
                BBox(tile_bbox[0], tile_bbox[1], tile_bbox[2], tile_bbox[3],
                     "EPSG:3045"),
                w, h, value=float(len(requested)),
            )
            return Path(output_path)

        target = tmp_path / "mosaic.tif"
        bbox = BBox(0, 0, 16, 16, "EPSG:3045")  # 8x8 px przy pixel_size=2
        client = CuzkClient(session=Mock())
        with (
            patch.object(CuzkClient, "MAX_EXPORT_WIDTH", 4),
            patch.object(CuzkClient, "MAX_EXPORT_HEIGHT", 4),
            patch(_DOWNLOAD_TO_PATCH, side_effect=fake_download),
        ):
            client.export_image(
                DMR5G, bbox, pixel_size=2.0, image_sr="EPSG:3045",
                output_path=target,
            )

        assert len(requested) == 4
        assert all(nd == "-9999" for (_, _, _, nd) in requested)
        with rasterio.open(target) as src:
            assert src.width == 8 and src.height == 8
            assert src.bounds == (0.0, 0.0, 16.0, 16.0)
            assert src.nodata == -9999.0
        # pliki czastkowe posprzatane
        assert list(tmp_path.glob("*.part*.tif")) == []

    def test_tiling_with_crs_mismatch_raises(self, tmp_path):
        bbox = BBox(0, 0, 16, 16, "EPSG:5514")
        client = CuzkClient(session=Mock())
        with (
            patch.object(CuzkClient, "MAX_EXPORT_WIDTH", 4),
            patch.object(CuzkClient, "MAX_EXPORT_HEIGHT", 4),
        ):
            with pytest.raises(ValidationError, match="image_sr"):
                client.export_image(
                    DMR5G, bbox, pixel_size=2.0, image_sr="EPSG:2180",
                    output_path=tmp_path / "x.tif",
                )
```

- [ ] **Krok 2: Uruchom — FAIL** (`AttributeError: export_image`).

Run: `.venv/bin/python -m pytest tests/test_cuzk_client.py -q`

- [ ] **Krok 3: Implementacja** — do `client.py` (dodaj importy: `math`, `from urllib.parse import urlencode`, `from kartograf.exceptions import ValidationError` obok DownloadError, `from kartograf.transport.mosaic import mosaic_and_crop`):

```python
    def export_image(
        self,
        endpoint: str,
        bbox: BBox,
        *,
        pixel_size: float,
        image_sr: str,
        no_data: float = -9999.0,
        output_path: Path,
    ) -> Path:
        """GeoTIFF float32 z {endpoint}/exportImage; kafelkowanie nad limitem.

        no_data NIGDY nie jest pomijane (obszar poza CZ bylby wypelniony
        zerami bez oznaczenia — research 2026-08-10).
        """
        output_path = Path(output_path)
        width_px = max(1, round((bbox.max_x - bbox.min_x) / pixel_size))
        height_px = max(1, round((bbox.max_y - bbox.min_y) / pixel_size))

        if width_px <= self.MAX_EXPORT_WIDTH and height_px <= self.MAX_EXPORT_HEIGHT:
            self._export_single(
                endpoint, bbox, width_px, height_px, image_sr, no_data, output_path
            )
            return output_path

        if _wkid(bbox.crs) != _wkid(image_sr):
            raise ValidationError(
                f"Kafelkowanie exportImage wymaga bbox.crs == image_sr "
                f"(bbox: {bbox.crs}, image_sr: {image_sr}) — znormalizuj bbox "
                f"do ukladu wyjsciowego przed eksportem"
            )

        tiles = _tile_grid(
            bbox, pixel_size, width_px, height_px,
            self.MAX_EXPORT_WIDTH, self.MAX_EXPORT_HEIGHT,
        )
        tile_paths: list[Path] = []
        try:
            for i, (tile_bbox, tile_w, tile_h) in enumerate(tiles):
                tile_path = output_path.with_name(
                    f"{output_path.name}"
                    f".{os.getpid()}_{threading.get_ident()}.part{i}.tif"
                )
                self._export_single(
                    endpoint, tile_bbox, tile_w, tile_h, image_sr, no_data,
                    tile_path,
                )
                tile_paths.append(tile_path)
            mosaic_and_crop(tile_paths, bbox, output_path, nodata=no_data)
        finally:
            for p in tile_paths:
                p.unlink(missing_ok=True)
        return output_path

    def _export_single(
        self,
        endpoint: str,
        bbox: BBox,
        width_px: int,
        height_px: int,
        image_sr: str,
        no_data: float,
        output_path: Path,
    ) -> None:
        params = {
            "f": "image",
            "format": "tiff",
            "pixelType": "F32",
            "bbox": f"{bbox.min_x:g},{bbox.min_y:g},{bbox.max_x:g},{bbox.max_y:g}",
            "bboxSR": _wkid(bbox.crs),
            "imageSR": _wkid(image_sr),
            "size": f"{width_px},{height_px}",
            "noData": f"{no_data:g}",
            "noDataInterpretation": "esriNoDataMatchAny",
        }
        url = f"{endpoint}/exportImage?{urlencode(params)}"
        download_to(self._session, url, output_path, timeout=self._timeout)
        with open(output_path, "rb") as f:
            head = f.read(4)
        if head not in _TIFF_MAGIC:
            with open(output_path, "rb") as f:
                snippet = f.read(500)
            output_path.unlink(missing_ok=True)
            raise DownloadError(
                f"exportImage nie zwrocil TIFF "
                f"(poczatek odpowiedzi: {snippet[:200]!r}) [{url}]"
            )


def _tile_grid(
    bbox: BBox,
    pixel_size: float,
    width_px: int,
    height_px: int,
    max_w: int,
    max_h: int,
) -> list[tuple[BBox, int, int]]:
    """Deterministyczna siatka kafli cieta po pelnych pikselach (S->N, W->E)."""

    def _splits(total_px: int, max_px: int) -> list[tuple[int, int]]:
        n = math.ceil(total_px / max_px)
        base, extra = divmod(total_px, n)
        sizes = [base + (1 if i < extra else 0) for i in range(n)]
        offsets = [sum(sizes[:i]) for i in range(n)]
        return list(zip(offsets, sizes))

    tiles: list[tuple[BBox, int, int]] = []
    for row_off, row_px in _splits(height_px, max_h):
        for col_off, col_px in _splits(width_px, max_w):
            tiles.append(
                (
                    BBox(
                        bbox.min_x + col_off * pixel_size,
                        bbox.min_y + row_off * pixel_size,
                        bbox.min_x + (col_off + col_px) * pixel_size,
                        bbox.min_y + (row_off + row_px) * pixel_size,
                        bbox.crs,
                    ),
                    col_px,
                    row_px,
                )
            )
    return tiles
```

Uwaga z rekonesansu (Zad. 1 krok 4): jeśli serwer NIE wpisuje tagu nodata do GeoTIFF — dodaj na końcu `_export_single` (przed sniffem nie — po sniffie) blok wpisujący nodata do profilu:

```python
        # serwer nie zapisuje tagu nodata — uzupelnij metadane (nie dane)
        import rasterio
        with rasterio.open(output_path, "r+") as ds:
            if ds.nodata is None:
                ds.nodata = no_data
```

(decyzję podejmij na podstawie notatki z rekonesansu; jeśli tag jest — pomiń blok).

- [ ] **Krok 4: Uruchom** — `.venv/bin/python -m pytest tests/test_cuzk_client.py -q` → PASS; pełna suita → PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/providers/cuzk/client.py tests/test_cuzk_client.py
git commit -m "feat(cuzk): export_image — GeoTIFF z exportImage, deterministyczne kafelkowanie + mosaic_and_crop"
```

---

### Zadanie 10: `providers/cuzk/sheets.py` — SheetIndex + SheetInfo + Sm5Sheet

Indeks arkuszy `KladyMapovychListu` (warstwa 24 = SM5, 26 = TM33) z cache `sheet_cache`. Kształt odpowiedzi wg fixtur z Zadania 1. `sm5_sheets_for_bbox`/`tm33_tiles_for_bbox` — fundament etapu 2: zaimplementowane i przetestowane, bez konsumenta CLI w etapie 1.

**Files:**
- Create: `kartograf/providers/cuzk/sheets.py`
- Test: `tests/test_cuzk_sheets.py`

**Interfaces:**
- Produces: `SheetIndex(session=None, cache: MetadataCache | None = None, endpoint: str = KLADY_ENDPOINT)` z metodami `sm5_sheet(mapnom: str) -> SheetInfo` (ValidationError dla nieznanego MAPNOM — PRZED jakimkolwiek pobraniem), `sm5_sheets_for_bbox(bbox: BBox) -> list[SheetInfo]`, `tm33_tiles_for_bbox(bbox: BBox) -> list[SheetInfo]`; `SheetInfo(godlo, name, bbox, podil, in_cz)` (frozen dataclass); `Sm5Sheet(godlo: str, index: SheetIndex | None = None)` z `uklad = "cz_sm5"`, `godlo`, `get_bbox() -> BBox` (lazy — IO dopiero przy wywołaniu); stałe `KLADY_ENDPOINT`, `SM5_LAYER = 24`, `TM33_LAYER = 26`.
- Consumes: `CuzkClient.query` (Zad. 8), `MetadataCache.get_sheet`/`set_sheet` (Zad. 7), `ParseError`, `ValidationError`, `BBox`.

- [ ] **Krok 1: Testy (failing)** — `tests/test_cuzk_sheets.py`:

```python
"""Testy SheetIndex / Sm5Sheet — indeks arkuszy KladyMapovychListu (offline)."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from kartograf.cache import MetadataCache
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError
from kartograf.providers.cuzk.sheets import (
    KLADY_ENDPOINT,
    SM5_LAYER,
    TM33_LAYER,
    SheetIndex,
    SheetInfo,
    Sm5Sheet,
)

FIXTURES = Path("tests/fixtures/cuzk")


def _session_returning(*payloads):
    """Mock requests.Session zwracajacy kolejne payloady JSON."""
    session = Mock()
    responses = []
    for p in payloads:
        r = Mock()
        r.raise_for_status = Mock()
        r.json.return_value = p
        responses.append(r)
    session.get.side_effect = responses
    return session


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestSm5Sheet:
    def test_sm5_sheet_from_fixture(self):
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        index = SheetIndex(session=session)
        info = index.sm5_sheet("CTES96")
        assert isinstance(info, SheetInfo)
        assert info.godlo == "CTES96"
        assert info.name  # MAPNAME obecne
        assert info.podil is not None and 0.0 < info.podil <= 1.0
        assert info.in_cz is None
        assert info.bbox.crs == "EPSG:5514"
        assert info.bbox.min_x < info.bbox.max_x
        # zapytanie poszlo do warstwy 24 z where po MAPNOM
        (url,), kwargs = session.get.call_args
        assert url == f"{KLADY_ENDPOINT}/{SM5_LAYER}/query"
        assert "MAPNOM" in kwargs["params"]["where"]

    def test_unknown_mapnom_raises_validation_error(self):
        session = _session_returning({"features": []})
        index = SheetIndex(session=session)
        with pytest.raises(ValidationError, match="ZZZZ99"):
            index.sm5_sheet("ZZZZ99")

    def test_malformed_mapnom_rejected_before_network(self):
        session = Mock()
        index = SheetIndex(session=session)
        with pytest.raises(ValidationError):
            index.sm5_sheet("ctes96")  # male litery — nie przechodzi wzorca
        session.get.assert_not_called()

    def test_cache_hit_skips_network(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "c.db")
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        index = SheetIndex(session=session, cache=cache)
        first = index.sm5_sheet("CTES96")
        second = index.sm5_sheet("CTES96")
        assert first == second
        assert session.get.call_count == 1
        assert cache.stats()["sheet_count"] == 1
        cache.close()

    def test_cache_shared_between_instances(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "c.db")
        session1 = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        SheetIndex(session=session1, cache=cache).sm5_sheet("CTES96")
        session2 = Mock()
        info = SheetIndex(session=session2, cache=cache).sm5_sheet("CTES96")
        assert info.godlo == "CTES96"
        session2.get.assert_not_called()
        cache.close()


class TestBboxQueries:
    def test_sm5_sheets_for_bbox(self):
        session = _session_returning(_fixture("klady_sm5_bbox.json"))
        index = SheetIndex(session=session)
        infos = index.sm5_sheets_for_bbox(
            BBox(-450000, -1105000, -440000, -1095000, "EPSG:5514")
        )
        assert len(infos) >= 1
        assert all(i.bbox.crs == "EPSG:5514" for i in infos)
        params = session.get.call_args.kwargs["params"]
        assert params["geometryType"] == "esriGeometryEnvelope"

    def test_tm33_tiles_for_bbox(self):
        session = _session_returning(_fixture("klady_tm33_bbox.json"))
        index = SheetIndex(session=session)
        infos = index.tm33_tiles_for_bbox(
            BBox(744000, 5540000, 760000, 5556000, "EPSG:3045")
        )
        assert len(infos) >= 1
        first = infos[0]
        assert first.in_cz in (True, False)
        assert first.podil is None
        assert first.name is None
        assert first.bbox.crs == "EPSG:3045"
        (url,), _ = session.get.call_args
        assert url == f"{KLADY_ENDPOINT}/{TM33_LAYER}/query"


class TestSm5SheetParserObject:
    def test_attributes(self):
        sheet = Sm5Sheet("CTES96")
        assert sheet.godlo == "CTES96"
        assert sheet.uklad == "cz_sm5"

    def test_invalid_godlo_raises_parse_error(self):
        with pytest.raises(ParseError):
            Sm5Sheet("302_5550")

    def test_get_bbox_is_lazy_and_delegates(self):
        """Konstrukcja bez IO; get_bbox dopiero pyta indeks."""
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        index = SheetIndex(session=session)
        sheet = Sm5Sheet("CTES96", index=index)
        session.get.assert_not_called()
        bbox = sheet.get_bbox()
        assert bbox.crs == "EPSG:5514"
        assert session.get.call_count == 1
```

- [ ] **Krok 2: Uruchom — FAIL** (`ModuleNotFoundError: ...sheets`).

Run: `.venv/bin/python -m pytest tests/test_cuzk_sheets.py -q`

- [ ] **Krok 3: Implementacja** — `kartograf/providers/cuzk/sheets.py`:

```python
"""
SheetIndex — indeks arkuszy KladyMapovychListu (ArcGIS REST /query) z cache.

Warstwa 24: SM5 (MAPNOM, MAPNAME, PODIL) w EPSG:5514.
Warstwa 26: siatka TM33 2x2 km (MAPNOM, IN_CZ) w EPSG:3045.
Uwaga: host `arcgis`, nie `arcgis2`. Zero IO przy imporcie i konstrukcji.
"""

import re
from dataclasses import dataclass

from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError
from kartograf.providers.cuzk.client import CuzkClient

KLADY_ENDPOINT = (
    "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer"
)
SM5_LAYER = 24
TM33_LAYER = 26

_SM5_RE = re.compile(r"^[A-Z]{4}\d{2}$")


@dataclass(frozen=True)
class SheetInfo:
    """Jeden arkusz/kafel z indeksu KladyMapovychListu."""

    godlo: str  # MAPNOM ("CTES96" / "756_5516")
    name: str | None  # MAPNAME ("Cesky Tesin 8-6"); None dla TM33
    bbox: BBox  # EPSG:5514 (w. 24) / EPSG:3045 (w. 26)
    podil: float | None  # udzial arkusza w terytorium CZ; None dla TM33
    in_cz: bool | None  # warstwa 26; None dla SM5


class SheetIndex:
    """Indeks arkuszy z zapytaniami po MAPNOM/bbox i cache sheet_cache."""

    def __init__(
        self,
        session=None,
        cache: MetadataCache | None = None,
        endpoint: str = KLADY_ENDPOINT,
    ):
        self._client = CuzkClient(session=session)
        self._cache = cache
        self._endpoint = endpoint

    def sm5_sheet(self, mapnom: str) -> SheetInfo:
        """Arkusz SM5 po MAPNOM; ValidationError gdy nieznany (przed pobraniem)."""
        if not _SM5_RE.match(mapnom):
            raise ValidationError(
                f"Niepoprawne godlo SM5: '{mapnom}' "
                f"(oczekiwano 4 wielkich liter + 2 cyfr, np. CTES96)"
            )
        if self._cache is not None:
            cached = self._cache.get_sheet("cz_sm5", mapnom)
            if cached is not None:
                return _info_from_payload(cached)
        features = self._client.query(
            self._endpoint,
            SM5_LAYER,
            where=f"MAPNOM='{mapnom}'",
            out_fields="MAPNOM,MAPNAME,PODIL",
            out_sr="EPSG:5514",
        )
        if not features:
            raise ValidationError(
                f"Arkusz SM5 '{mapnom}' nie istnieje w indeksie "
                f"KladyMapovychListu (warstwa {SM5_LAYER})"
            )
        info = _sm5_info(features[0])
        if self._cache is not None:
            self._cache.set_sheet("cz_sm5", mapnom, _payload_from_info(info))
        return info

    def sm5_sheets_for_bbox(self, bbox: BBox) -> list[SheetInfo]:
        """Arkusze SM5 przecinajace bbox (fundament etapu 2: LAZ/Orto)."""
        features = self._client.query(
            self._endpoint,
            SM5_LAYER,
            bbox=bbox,
            out_fields="MAPNOM,MAPNAME,PODIL",
            out_sr="EPSG:5514",
        )
        return [_sm5_info(f) for f in features]

    def tm33_tiles_for_bbox(self, bbox: BBox) -> list[SheetInfo]:
        """Kafle TM33 przecinajace bbox (z atrybutem IN_CZ)."""
        features = self._client.query(
            self._endpoint,
            TM33_LAYER,
            bbox=bbox,
            out_fields="MAPNOM,IN_CZ",
            out_sr="EPSG:3045",
        )
        return [_tm33_info(f) for f in features]


class Sm5Sheet:
    """Obiekt parsera dla rejestru cz_sm5 — bbox przez SheetIndex (lazy).

    Sciezka szczesliwa pobierania SM5 nie potrzebuje bboxa (URL openzu to
    czysta nazwa arkusza) — get_bbox() to jedyne miejsce z IO.
    """

    uklad = "cz_sm5"

    def __init__(self, godlo: str, index: SheetIndex | None = None):
        if not isinstance(godlo, str) or not _SM5_RE.match(godlo.strip()):
            raise ParseError(
                f"Niepoprawne godlo SM5: '{godlo}' "
                f"(oczekiwano 4 wielkich liter + 2 cyfr, np. CTES96)"
            )
        self.godlo = godlo.strip()
        self._index = index

    def get_bbox(self) -> BBox:
        """BBox arkusza w EPSG:5514 (zapytanie do indeksu, z cache)."""
        if self._index is None:
            self._index = SheetIndex(cache=MetadataCache())
        return self._index.sm5_sheet(self.godlo).bbox

    def __repr__(self) -> str:
        return f"Sm5Sheet('{self.godlo}')"


def _rings_envelope(geometry: dict, crs: str) -> BBox:
    xs = [pt[0] for ring in geometry["rings"] for pt in ring]
    ys = [pt[1] for ring in geometry["rings"] for pt in ring]
    return BBox(min(xs), min(ys), max(xs), max(ys), crs)


def _sm5_info(feature: dict) -> SheetInfo:
    attrs = feature["attributes"]
    podil = attrs.get("PODIL")
    return SheetInfo(
        godlo=attrs["MAPNOM"],
        name=attrs.get("MAPNAME"),
        bbox=_rings_envelope(feature["geometry"], "EPSG:5514"),
        podil=float(podil) if podil is not None else None,
        in_cz=None,
    )


def _tm33_info(feature: dict) -> SheetInfo:
    attrs = feature["attributes"]
    in_cz = attrs.get("IN_CZ")
    return SheetInfo(
        godlo=attrs["MAPNOM"],
        name=None,
        bbox=_rings_envelope(feature["geometry"], "EPSG:3045"),
        podil=None,
        in_cz=bool(in_cz) if in_cz is not None else None,
    )


def _payload_from_info(info: SheetInfo) -> dict:
    return {
        "godlo": info.godlo,
        "name": info.name,
        "bbox": [info.bbox.min_x, info.bbox.min_y, info.bbox.max_x, info.bbox.max_y],
        "bbox_crs": info.bbox.crs,
        "podil": info.podil,
        "in_cz": info.in_cz,
    }


def _info_from_payload(payload: dict) -> SheetInfo:
    return SheetInfo(
        godlo=payload["godlo"],
        name=payload.get("name"),
        bbox=BBox(*payload["bbox"], payload["bbox_crs"]),
        podil=payload.get("podil"),
        in_cz=payload.get("in_cz"),
    )
```

Uwaga: jeśli fixtury z Zadania 1 pokazują inne nazwy pól (np. `podil` małymi literami) — dostosuj `out_fields` i odczyt atrybutów do fixtur.

- [ ] **Krok 4: Uruchom** — `.venv/bin/python -m pytest tests/test_cuzk_sheets.py -q` → PASS; pełna suita → PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/providers/cuzk/sheets.py tests/test_cuzk_sheets.py
git commit -m "feat(cuzk): SheetIndex (KladyMapovychListu w.24/26, cache sheet_cache) + Sm5Sheet"
```

---

### Zadanie 11: Rejestracja systemów `cz_tm33` i `cz_sm5` w `parser_registry`

Dwa wpisy POMIĘDZY `pl2000` a fallbackiem `pl1992` (fallback ma `detect=lambda godlo: True` — kolejność krytyczna). `SheetParser` NIE jest generalizowany; `find_sheets_for_bbox(system=...)` nie dostaje systemów CZ.

**Files:**
- Modify: `kartograf/core/parser_registry.py` (wpisy między rejestracjami pl2000 i pl1992)
- Test: `tests/test_parser_registry.py`

**Interfaces:**
- Produces: `detect_system("302_5550").id == "cz_tm33"`, `detect_system("CTES96").id == "cz_sm5"`, oba z `country == "CZ"`; `path_parts("302_5550") == ["302", "5550"]`, `path_parts("CTES96") == ["CTES", "96"]`; `parser_factory` → `ParserTM33` / `Sm5Sheet` (importy lazy w fabrykach).
- Consumes: `ParserTM33` (Zad. 6), `Sm5Sheet` (Zad. 10).

- [ ] **Krok 1: Testy (failing)** — do `tests/test_parser_registry.py` (addytywnie):

```python
class TestCzechSystems:
    """Systemy cz_tm33/cz_sm5 — pomiedzy pl2000 a fallbackiem pl1992."""

    def test_cz_tm33_detected(self):
        system = detect_system("302_5550")
        assert system.id == "cz_tm33"
        assert system.country == "CZ"

    def test_cz_sm5_detected(self):
        system = detect_system("CTES96")
        assert system.id == "cz_sm5"
        assert system.country == "CZ"

    def test_pl_godla_still_detected_first(self):
        assert detect_system("6.179.12.20").id == "pl2000"
        assert detect_system("N-34-130-D-d-2-4").id == "pl1992"

    def test_fallback_still_catches_everything_else(self):
        # opaque godlo LAZ — musi dalej trafiac do pl1992 (get_raw_path)
        assert detect_system("N-33-131-B-a-1-1-4").id == "pl1992"
        assert detect_system("cokolwiek").id == "pl1992"

    @pytest.mark.parametrize(
        "godlo,parts",
        [
            ("302_5550", ["302", "5550"]),
            ("756_5516", ["756", "5516"]),
            ("CTES96", ["CTES", "96"]),
            ("BENE09", ["BENE", "09"]),
        ],
    )
    def test_cz_path_parts(self, godlo, parts):
        assert path_parts(godlo) == parts

    def test_cz_tm33_factory(self):
        parser = detect_system("302_5550").parser_factory("302_5550")
        assert parser.uklad == "cz_tm33"
        assert parser.get_bbox().crs == "EPSG:3045"

    def test_cz_sm5_factory_no_io_at_construction(self):
        parser = detect_system("CTES96").parser_factory("CTES96")
        assert parser.uklad == "cz_sm5"
        assert parser.godlo == "CTES96"
        # get_bbox() wymaga indeksu (IO) — NIE wolamy go tutaj

    def test_no_pattern_collisions(self):
        """Wzorce CZ nie przechwytuja godel PL i odwrotnie."""
        assert detect_system("30_5550").id == "pl1992"  # za krotkie na TM33
        assert detect_system("CTES9").id == "pl1992"  # za krotkie na SM5
        assert detect_system("CTES961").id == "pl1992"  # za dlugie na SM5
```

- [ ] **Krok 2: Uruchom — FAIL**

Run: `.venv/bin/python -m pytest tests/test_parser_registry.py -q`
Oczekiwane: FAIL — `detect_system("302_5550").id == "pl1992"`.

- [ ] **Krok 3: Implementacja** — w `parser_registry.py`, po definicjach PL-helperów, PRZED `register_system(... pl1992 ...)` (kolejność rejestracji: pl2000 → cz_tm33 → cz_sm5 → pl1992):

```python
_CZ_TM33_PATTERN = re.compile(r"^\d{3}_\d{4}$")
_CZ_SM5_PATTERN = re.compile(r"^[A-Z]{4}\d{2}$")


def _make_parser_cz_tm33(godlo: str) -> Any:
    from kartograf.core.parser_tm33 import ParserTM33

    return ParserTM33(godlo)


def _make_parser_cz_sm5(godlo: str) -> Any:
    from kartograf.providers.cuzk.sheets import Sm5Sheet

    return Sm5Sheet(godlo)
```

i między istniejącymi wywołaniami `register_system` (po pl2000, przed pl1992):

```python
register_system(
    SheetSystem(
        id="cz_tm33",
        country="CZ",
        detect=lambda godlo: bool(_CZ_TM33_PATTERN.match(godlo)),
        parser_factory=_make_parser_cz_tm33,
        path_parts=lambda godlo: godlo.split("_"),
    )
)
register_system(
    SheetSystem(
        id="cz_sm5",
        country="CZ",
        detect=lambda godlo: bool(_CZ_SM5_PATTERN.match(godlo)),
        parser_factory=_make_parser_cz_sm5,
        path_parts=lambda godlo: [godlo[:4], godlo[4:]],
    )
)
```

- [ ] **Krok 4: Uruchom pełną suitę** — PASS (w szczególności `TestPathParts::test_golden_values` i testy LAZ — fallback nietknięty).

- [ ] **Krok 5: Commit**

```bash
git add kartograf/core/parser_registry.py tests/test_parser_registry.py
git commit -m "feat(core): rejestracja systemow godel cz_tm33 i cz_sm5 (przed fallbackiem pl1992)"
```

---

### Zadanie 12: `CuzkDmrProvider` + fabryka `create_dmr_provider`

Provider skleja klienta z deskryptorem: endpointy WYŁĄCZNIE z `get_source(...).channels[..].endpoint`. Transformacja pionowa wyłącznie na jawne żądanie (`vertical_crs="EVRF2007"`); KRON86 → `TransformUnavailableError` w konstruktorze (fail-fast). Naprawa metadanych DMR4G-TIFF (CRS 5514). Semantyka wywołania transformera pionowego (lon, lat, z) — potwierdzona w rekonesansie (Zad. 1 krok 7); jeśli notatka mówi inaczej, dostosuj `_apply_vertical_shift`.

**Files:**
- Create: `kartograf/providers/cuzk/dmr.py`
- Modify: `kartograf/providers/cuzk/__init__.py` (fabryka + eksporty)
- Test: `tests/test_cuzk_dmr.py`

**Interfaces:**
- Produces: `CuzkDmrProvider(resolution: str = "2m", session=None, cache: MetadataCache | None = None, target_crs: str | None = None, vertical_crs: str = "Bpv")` — `BaseProvider` z `descriptor_key` (`"cz.cuzk.dmr5g"` dla 2m / `"cz.cuzk.dmr4g"` dla 5m), `default_extension == ".tif"`, `vertical_crs` (property, nazwa CLI), `sheet_index` (property, współdzielony `SheetIndex`), `vertical_transform` (property: `PinnedTransform | None` — None gdy Bpv), `download(godlo, output_path, timeout=60) -> Path`, `download_bbox(bbox, output_path, format="GTiff", timeout=60) -> Path`; stała `CUZK_NODATA = -9999.0`; `create_dmr_provider(resolution="2m", session=None, cache=None, target_crs=None, vertical_crs="Bpv") -> CuzkDmrProvider`.
- Consumes: `CuzkClient` (Zad. 8-9), `SheetIndex` (Zad. 10), `detect_system` (Zad. 11), `get_source` + deskryptory CZ (Zad. 3), `build_pinned_transform`/`TransformPolicy`/`REMEDIES`/`TransformUnavailableError` + polimorficzne `transform` (Zad. 5), `ParserTM33` (Zad. 6).
- Patch-targety testów: `kartograf.providers.cuzk.dmr.CuzkClient`, `kartograf.providers.cuzk.dmr.SheetIndex`, `kartograf.providers.cuzk.dmr.build_pinned_transform`.

- [ ] **Krok 1: Testy (failing)** — `tests/test_cuzk_dmr.py`:

```python
"""Testy CuzkDmrProvider — dispatch SM5/TM33/bbox, CRS, transformacja pionowa."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.providers.cuzk import create_dmr_provider
from kartograf.providers.cuzk.dmr import CUZK_NODATA, CuzkDmrProvider
from kartograf.providers.cuzk.sheets import SheetInfo
from kartograf.sources.registry import get_source
from kartograf.transform.crs import TransformUnavailableError

_CLIENT_PATCH = "kartograf.providers.cuzk.dmr.CuzkClient"
_INDEX_PATCH = "kartograf.providers.cuzk.dmr.SheetIndex"
_PINNED_PATCH = "kartograf.providers.cuzk.dmr.build_pinned_transform"


def _write_tif(path: Path, *, crs, bounds=(0, 0, 20, 20), size=(10, 10),
               value=100.0, nodata=CUZK_NODATA):
    transform = from_bounds(*bounds, size[0], size[1])
    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "width": size[0], "height": size[1],
        "crs": crs, "transform": transform, "nodata": nodata,
    }
    data = np.full((size[1], size[0]), value, dtype="float32")
    data[0, 0] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


def _ctes96_info():
    return SheetInfo(
        godlo="CTES96", name="Cesky Tesin 8-6",
        bbox=BBox(-450000, -1105000, -447500, -1103000, "EPSG:5514"),
        podil=0.507, in_cz=None,
    )


class TestConstruction:
    def test_resolution_selects_descriptor(self):
        assert CuzkDmrProvider(resolution="2m").descriptor_key == "cz.cuzk.dmr5g"
        assert CuzkDmrProvider(resolution="5m").descriptor_key == "cz.cuzk.dmr4g"

    def test_default_extension(self):
        assert CuzkDmrProvider().default_extension == ".tif"

    def test_invalid_resolution_rejected_by_factory(self):
        with pytest.raises(ValidationError, match="2m, 5m"):
            create_dmr_provider(resolution="1m")

    def test_kron86_raises_with_remedy(self):
        with pytest.raises(TransformUnavailableError) as exc:
            CuzkDmrProvider(vertical_crs="KRON86")
        assert exc.value.remedy  # remedium z REMEDIES (siatki niepubliczne)

    def test_unknown_vertical_rejected(self):
        with pytest.raises(ValidationError):
            CuzkDmrProvider(vertical_crs="NAP")


class TestDownloadDispatch:
    def test_tm33_godlo_exports_native_3045(self, tmp_path):
        target = tmp_path / "302_5550.tif"
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value

            def fake_export(endpoint, bbox, *, pixel_size, image_sr, no_data,
                            output_path):
                _write_tif(Path(output_path), crs="EPSG:3045")
                return Path(output_path)

            client.export_image.side_effect = fake_export
            provider = CuzkDmrProvider(resolution="2m")
            result = provider.download("302_5550", target)

        assert result == target
        kwargs = client.export_image.call_args.kwargs
        assert kwargs["pixel_size"] == 2.0
        assert kwargs["image_sr"] == "EPSG:3045"
        assert kwargs["no_data"] == CUZK_NODATA
        called_endpoint, called_bbox = client.export_image.call_args.args[:2]
        assert called_endpoint == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"
        )
        assert called_bbox == BBox(302000, 5550000, 304000, 5552000, "EPSG:3045")

    def test_sm5_godlo_validates_fetches_and_repairs_crs(self, tmp_path):
        target = tmp_path / "CTES96.tif"
        with patch(_CLIENT_PATCH) as client_cls, patch(_INDEX_PATCH) as index_cls:
            index_cls.return_value.sm5_sheet.return_value = _ctes96_info()
            client = client_cls.return_value

            def fake_fetch(url, output_path, *, unzip_single=None):
                # DMR4G-TIFF: crs=None (georeferencja tylko w .tfw)
                _write_tif(Path(output_path), crs=None)
                return Path(output_path)

            client.fetch_file.side_effect = fake_fetch
            provider = CuzkDmrProvider(resolution="5m")
            provider.download("CTES96", target)

        index_cls.return_value.sm5_sheet.assert_called_once_with("CTES96")
        url = client.fetch_file.call_args.args[0]
        assert url == (
            "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/epsg-5514/CTES96.zip"
        )
        assert client.fetch_file.call_args.kwargs["unzip_single"] == ".tif"
        with rasterio.open(target) as src:
            assert src.crs is not None and src.crs.to_epsg() == 5514

    def test_sm5_with_2m_resolution_rejected(self, tmp_path):
        provider = CuzkDmrProvider(resolution="2m")
        with pytest.raises(ValidationError, match="5m"):
            provider.download("CTES96", tmp_path / "CTES96.tif")

    def test_non_cz_godlo_rejected(self, tmp_path):
        provider = CuzkDmrProvider()
        with pytest.raises(ValidationError, match="CZ"):
            provider.download("N-34-130-D-d-2-4", tmp_path / "x.tif")


class TestDownloadBbox:
    def test_native_5514(self, tmp_path):
        target = tmp_path / "area.tif"
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value
            client.export_image.side_effect = (
                lambda e, b, **kw: _write_tif(Path(kw["output_path"]),
                                              crs="EPSG:5514")
                or Path(kw["output_path"])
            )
            CuzkDmrProvider(resolution="2m").download_bbox(bbox, target)
        assert client.export_image.call_args.kwargs["image_sr"] == "EPSG:5514"
        assert client.export_image.call_args.args[1] == bbox

    def test_target_crs_via_server_reprojection(self, tmp_path):
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CLIENT_PATCH) as client_cls:
            client = client_cls.return_value
            client.export_image.side_effect = (
                lambda e, b, **kw: _write_tif(Path(kw["output_path"]),
                                              crs="EPSG:2180")
                or Path(kw["output_path"])
            )
            provider = CuzkDmrProvider(resolution="2m", target_crs="EPSG:2180")
            provider.download_bbox(bbox, tmp_path / "area.tif")
        kwargs = client.export_image.call_args.kwargs
        assert kwargs["image_sr"] == "EPSG:2180"
        # bbox znormalizowany do ukladu wyjsciowego (kafelkowanie bez szwow)
        assert client.export_image.call_args.args[1].crs == "EPSG:2180"


class TestVerticalTransform:
    def _pinned_fakes(self):
        """side_effect dla build_pinned_transform: OSOBNE fake'i dla operacji
        pionowej 8357->5621 (3-argumentowa, przesuwa z o +0.13) i pomocniczej
        poziomej raster_crs->4326 (2-argumentowa, identycznosc) —
        _apply_vertical_shift buduje obie przez te sama funkcje."""
        vertical = MagicMock()
        vertical.description = "Baltic 1957 height to EVRF2007 height (1)"
        vertical.accuracy_m = 0.1
        vertical.transform.side_effect = (
            lambda x, y, z: (x, y, np.asarray(z) + 0.13)
        )
        horizontal = MagicMock()
        horizontal.transform.side_effect = lambda x, y: (x, y)

        def factory(src_crs, dst_crs, policy):
            return vertical if src_crs == "EPSG:8357" else horizontal

        return factory, vertical

    def test_bpv_native_no_transform(self):
        provider = CuzkDmrProvider()  # vertical_crs="Bpv"
        assert provider.vertical_transform is None

    def test_evrf2007_builds_8357_to_5621(self):
        factory, _ = self._pinned_fakes()
        with patch(_PINNED_PATCH, side_effect=factory) as pinned_mock:
            provider = CuzkDmrProvider(vertical_crs="EVRF2007")
            assert provider.vertical_transform is not None
        assert pinned_mock.call_args.args[:2] == ("EPSG:8357", "EPSG:5621")

    def test_evrf2007_shifts_values_and_keeps_nodata(self, tmp_path):
        target = tmp_path / "302_5550.tif"
        factory, vertical = self._pinned_fakes()
        with patch(_CLIENT_PATCH) as client_cls, \
             patch(_PINNED_PATCH, side_effect=factory):
            client = client_cls.return_value
            client.export_image.side_effect = (
                lambda e, b, **kw: _write_tif(Path(kw["output_path"]),
                                              crs="EPSG:3045")
                or Path(kw["output_path"])
            )
            provider = CuzkDmrProvider(resolution="2m", vertical_crs="EVRF2007")
            provider.download("302_5550", target)

        with rasterio.open(target) as src:
            data = src.read(1)
        assert data[5, 5] == pytest.approx(100.13, abs=1e-4)
        assert data[0, 0] == CUZK_NODATA  # nodata NIE jest transformowane
        assert vertical.transform.called


class TestDescriptorProviderConsistency:
    """Wzor: TestDescriptorProviderConsistency z test_sources_registry."""

    def test_dmr5g(self, tmp_path):
        from kartograf.download.storage import FileStorage

        d = get_source("cz.cuzk.dmr5g")
        provider = create_dmr_provider(resolution="2m")
        assert provider.descriptor_key == d.key
        assert provider.default_extension == d.default_extension
        storage = FileStorage(tmp_path, subdir=d.storage_subdir)
        assert storage._subdir == d.storage_subdir
        for ch in d.channels:
            assert ch.vertical_crs_options == ("EPSG:8357",)
            assert ch.endpoint  # silnik jest sterowany deskryptorem

    def test_dmr4g(self, tmp_path):
        d = get_source("cz.cuzk.dmr4g")
        provider = create_dmr_provider(resolution="5m")
        assert provider.descriptor_key == d.key
        capabilities = [set(ch.capabilities) for ch in d.channels]
        assert {"sheet_files"} in capabilities
        assert {"bbox_raster"} in capabilities
```

- [ ] **Krok 2: Uruchom — FAIL** (`ImportError: create_dmr_provider`).

Run: `.venv/bin/python -m pytest tests/test_cuzk_dmr.py -q`

- [ ] **Krok 3: Implementacja** — `kartograf/providers/cuzk/dmr.py`:

```python
"""
CuzkDmrProvider — DMR 5G (2 m, exportImage) i DMR 4G (5 m, pliki openzu + exportImage).

Zasada natywnosci: wynik exportImage to pochodna serwera (GeoTIFF); pliki
openzu to bajty CUZK 1:1 — modyfikowany jest wylacznie tag CRS w GeoTIFF
bez CRS (naprawa metadanych). Transformacja pionowa wylacznie na jawne
zadanie (vertical_crs="EVRF2007").
"""

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import xy as _pixel_xy
from rasterio.windows import Window

from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_registry import detect_system
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.cuzk.client import CuzkClient, _wkid
from kartograf.providers.cuzk.sheets import SheetIndex
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import get_source
from kartograf.transform.crs import (
    REMEDIES,
    PinnedTransform,
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)

logger = logging.getLogger(__name__)

CUZK_NODATA = -9999.0

_RESOLUTION_KEYS = {"2m": "cz.cuzk.dmr5g", "5m": "cz.cuzk.dmr4g"}
_PIXEL_SIZES = {"2m": 2.0, "5m": 5.0}
_SUPPORTED_VERTICAL = ("Bpv", "EVRF2007")
# blad poziomy 2 m zmienia offset pionowy o ~1e-6 m — z zapasem ponizej 0,1 m
_LONLAT_POLICY = TransformPolicy(min_accuracy_m=2.0)
_VERTICAL_POLICY = TransformPolicy(min_accuracy_m=0.2)
_CHUNK_ROWS = 512


class CuzkDmrProvider(BaseProvider):
    """Provider NMT dla Czech (CUZK): DMR 5G / DMR 4G."""

    def __init__(
        self,
        resolution: str = "2m",
        session=None,
        cache: MetadataCache | None = None,
        target_crs: str | None = None,
        vertical_crs: str = "Bpv",
    ):
        if resolution not in _RESOLUTION_KEYS:
            raise ValidationError(
                f"Nieobslugiwana rozdzielczosc CZ: '{resolution}' "
                f"(dostepne: 2m, 5m)"
            )
        if vertical_crs == "KRON86":
            raise TransformUnavailableError(
                "Brak transformacji Bpv (EPSG:8357) -> KRON86 (EPSG:9650) "
                "— siatki GUGiK nie sa publiczne",
                remedy=REMEDIES["EPSG:9650"],
            )
        if vertical_crs not in _SUPPORTED_VERTICAL:
            raise ValidationError(
                f"Nieobslugiwany uklad pionowy dla CZ: '{vertical_crs}' "
                f"(dostepne: {', '.join(_SUPPORTED_VERTICAL)})"
            )
        self.descriptor_key = _RESOLUTION_KEYS[resolution]
        self._resolution = resolution
        self._pixel_size = _PIXEL_SIZES[resolution]
        self._target_crs = target_crs
        self._vertical_crs = vertical_crs
        self._client = CuzkClient(session=session)
        self._sheet_index = SheetIndex(session=session, cache=cache)
        self._pinned_vertical: PinnedTransform | None = None
        self._lonlat_transforms: dict[str, PinnedTransform] = {}
        descriptor = get_source(self.descriptor_key)
        self._image_endpoint = next(
            ch.endpoint
            for ch in descriptor.channels
            if ch.transport == TransportKind.ARCGIS_IMAGE
        )
        self._files_endpoint = next(
            (
                ch.endpoint
                for ch in descriptor.channels
                if ch.transport == TransportKind.DIRECT_FILES
            ),
            None,
        )

    @property
    def name(self) -> str:
        return f"CUZK DMR ({self._resolution})"

    @property
    def base_url(self) -> str:
        return self._image_endpoint

    @property
    def default_extension(self) -> str:
        return ".tif"

    @property
    def resolution(self) -> str:
        return self._resolution

    @property
    def vertical_crs(self) -> str:
        """Nazwa CLI ukladu pionowego wyniku ("Bpv" albo "EVRF2007")."""
        return self._vertical_crs

    @property
    def sheet_index(self) -> SheetIndex:
        """Wspoldzielony indeks arkuszy (walidacja SM5, PODIL do sidecara)."""
        return self._sheet_index

    @property
    def vertical_transform(self) -> PinnedTransform | None:
        """Przypieta operacja 8357->5621 (None, gdy pobieranie natywne Bpv)."""
        if self._vertical_crs != "EVRF2007":
            return None
        if self._pinned_vertical is None:
            self._pinned_vertical = build_pinned_transform(
                "EPSG:8357", "EPSG:5621", _VERTICAL_POLICY
            )
        return self._pinned_vertical

    def download(self, godlo: str, output_path: Path, timeout: int = 60) -> Path:
        """Pobierz kafel TM33 (exportImage w 3045) lub arkusz SM5 (openzu)."""
        output_path = Path(output_path)
        system = detect_system(godlo)
        if system is None or system.country != "CZ":
            raise ValidationError(
                f"Godlo '{godlo}' nie nalezy do zadnego systemu CZ "
                f"(TM33: 302_5550, SM5: CTES96)"
            )
        if system.id == "cz_sm5":
            if self._resolution != "5m":
                raise ValidationError(
                    f"Arkusze SM5 sa dostepne tylko dla --resolution 5m "
                    f"(DMR 4G); dla 2m uzyj godla TM33 albo --bbox "
                    f"[godlo: {godlo}]"
                )
            self._sheet_index.sm5_sheet(godlo)  # walidacja przed pobraniem
            url = self._files_endpoint.format(sheet=godlo)
            try:
                self._client.fetch_file(url, output_path, unzip_single=".tif")
            except DownloadError as e:
                # spec sekcja 7: 404 z openzu -> podpowiedz weryfikacji godla
                raise DownloadError(
                    f"{e} — zweryfikuj godlo w indeksie KladyMapovychListu "
                    f"(arkusz moze byc znany indeksowi, ale plik openzu "
                    f"niedostepny)"
                ) from e
            _assign_crs(output_path, "EPSG:5514")
        else:  # cz_tm33
            bbox = ParserTM33(godlo).get_bbox()
            self._client.export_image(
                self._image_endpoint,
                bbox,
                pixel_size=self._pixel_size,
                image_sr="EPSG:3045",
                no_data=CUZK_NODATA,
                output_path=output_path,
            )
        if self.vertical_transform is not None:
            self._apply_vertical_shift(output_path)
        return output_path

    def download_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = 60,
    ) -> Path:
        """Jeden wycinek serwerowy (exportImage) dla dowolnego bboxa."""
        if format != "GTiff":
            raise ValidationError(
                f"CuzkDmrProvider.download_bbox obsluguje tylko GTiff "
                f"(zadano: {format})"
            )
        output_path = Path(output_path)
        image_sr = self._target_crs or "EPSG:5514"
        if _wkid(bbox.crs) != _wkid(image_sr):
            bbox = _bbox_to_crs(bbox, image_sr)
        self._client.export_image(
            self._image_endpoint,
            bbox,
            pixel_size=self._pixel_size,
            image_sr=image_sr,
            no_data=CUZK_NODATA,
            output_path=output_path,
        )
        if self.vertical_transform is not None:
            self._apply_vertical_shift(output_path)
        return output_path

    def _lonlat(self, raster_crs: str) -> PinnedTransform:
        if raster_crs not in self._lonlat_transforms:
            self._lonlat_transforms[raster_crs] = build_pinned_transform(
                raster_crs, "EPSG:4326", _LONLAT_POLICY
            )
        return self._lonlat_transforms[raster_crs]

    def _apply_vertical_shift(self, path: Path) -> None:
        """Przelicz wartosci rastra przypieta operacja 8357->5621 (per piksel).

        Operacja pionowa wymaga wspolrzednych poziomych (lon, lat) —
        semantyka potwierdzona w rekonesansie (Zad. 1 krok 7). Piksele
        nodata NIE sa transformowane.
        """
        pinned = self.vertical_transform
        assert pinned is not None
        with rasterio.open(path, "r+") as ds:
            horizontal = self._lonlat(str(ds.crs))
            nodata = ds.nodata if ds.nodata is not None else CUZK_NODATA
            for row_start in range(0, ds.height, _CHUNK_ROWS):
                rows = min(_CHUNK_ROWS, ds.height - row_start)
                window = Window(0, row_start, ds.width, rows)
                data = ds.read(1, window=window)
                mask = data != nodata
                if not mask.any():
                    continue
                row_idx, col_idx = np.nonzero(mask)
                xs, ys = _pixel_xy(
                    ds.window_transform(window), row_idx, col_idx, offset="center"
                )
                lon, lat = horizontal.transform(
                    np.asarray(xs, dtype="float64"),
                    np.asarray(ys, dtype="float64"),
                )
                _, _, shifted = pinned.transform(
                    lon, lat, data[mask].astype("float64")
                )
                data[mask] = np.asarray(shifted, dtype=data.dtype)
                ds.write(data, 1, window=window)


def _assign_crs(path: Path, crs: str) -> None:
    """Naprawa metadanych DMR4G-TIFF: wpisz CRS (georeferencja jest w .tfw)."""
    with rasterio.open(path, "r+") as ds:
        if ds.crs is None:
            ds.crs = rasterio.crs.CRS.from_string(crs)


def _bbox_to_crs(bbox: BBox, target_crs: str) -> BBox:
    """Obwiednia bboxa w ukladzie docelowym (do normalizacji zadan exportImage)."""
    from pyproj import CRS

    from kartograf.core.geometry import _transform_bbox

    return _transform_bbox(
        bbox.min_x,
        bbox.min_y,
        bbox.max_x,
        bbox.max_y,
        CRS.from_user_input(bbox.crs),
        target_crs,
    )
```

`kartograf/providers/cuzk/__init__.py` — zastąp docstring pełną zawartością:

```python
"""Providery czeskich zrodel danych (CUZK)."""

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.exceptions import ValidationError
from kartograf.providers.cuzk.client import CuzkClient
from kartograf.providers.cuzk.dmr import CuzkDmrProvider
from kartograf.providers.cuzk.sheets import SheetIndex, SheetInfo, Sm5Sheet

__all__ = [
    "CuzkClient",
    "CuzkDmrProvider",
    "SheetIndex",
    "SheetInfo",
    "Sm5Sheet",
    "create_dmr_provider",
]


def create_dmr_provider(
    resolution: str = "2m",
    session: requests.Session | None = None,
    cache: MetadataCache | None = None,
    target_crs: str | None = None,
    vertical_crs: str = "Bpv",
) -> CuzkDmrProvider:
    """Fabryka providera DMR — jedno miejsce czeskich domyslow (wzor: pl)."""
    if resolution not in {"2m", "5m"}:
        raise ValidationError(
            f"Nieobslugiwana rozdzielczosc CZ: '{resolution}' (dostepne: 2m, 5m)"
        )
    return CuzkDmrProvider(
        resolution=resolution,
        session=session,
        cache=cache,
        target_crs=target_crs,
        vertical_crs=vertical_crs,
    )
```

Uwaga z rekonesansu: jeśli exportImage na `dmr4g` NIE działa (Zad. 1 krok 4) — w `download_bbox` dodaj na początku: `if self._resolution == "5m": raise ValidationError("Tryb bbox dla DMR 4G niedostepny — uzyj godla SM5 (CTES96)")` i pomiń kanał ARCGIS_IMAGE w deskryptorze dmr4g (wróć do Zad. 3 i usuń ten kanał + zaktualizuj testy deskryptora).

- [ ] **Krok 4: Uruchom** — `.venv/bin/python -m pytest tests/test_cuzk_dmr.py -q` → PASS; pełna suita → PASS.

- [ ] **Krok 5: CHANGELOG + commit**

Do `docs/CHANGELOG.md` (0.7.0, Added): `CuzkDmrProvider + create_dmr_provider — DMR 5G/4G (CUZK), godla TM33/SM5, bbox przez exportImage, opcjonalna transformacja Bpv->EVRF2007`.

```bash
git add kartograf/providers/cuzk/ tests/test_cuzk_dmr.py docs/CHANGELOG.md
git commit -m "feat(cuzk): CuzkDmrProvider (TM33/SM5/bbox, naprawa CRS DMR4G, pionowa 8357->5621) + fabryka"
```

---

### Zadanie 13: `DownloadManager` — addytywny parametr `sidecar_extra`

Jedyna zmiana managera w etapie 1 (spec 5.9): opcjonalny `sidecar_extra` scalany do `extra` każdego sidecara. Domyślnie `None` — treść sidecarów PL bez zmian.

**Files:**
- Modify: `kartograf/download/manager.py:139-186` (konstruktor), `663-680` (`_write_sidecar`)
- Test: `tests/test_download_manager.py`

**Interfaces:**
- Produces: `DownloadManager(..., sidecar_extra: dict | None = None)`; `_write_sidecar` przekazuje kopię `sidecar_extra` jako `extra=` do `build_metadata`.
- Consumes: `build_metadata(extra=...)` (istniejące).

- [ ] **Krok 1: Testy (failing)** — do `tests/test_download_manager.py`, klasa `TestSidecarWritten` (reużyj helpera `_mock_provider` z tej klasy):

```python
    def test_sidecar_extra_merged_into_extra(self, tmp_path):
        import json

        parent = {
            "bbox": [530000.0, 382000.0, 533000.0, 386000.0],
            "bbox_crs": "EPSG:2180",
            "countries": ["CZ", "PL"],
        }
        manager = DownloadManager(
            output_dir=tmp_path,
            provider=self._mock_provider(),
            sidecar_extra={"parent_request": parent},
        )
        result = manager.download_sheet("N-34-130-D-d-2-4")
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"]["parent_request"] == parent

    def test_sidecar_extra_none_keeps_extra_empty(self, tmp_path):
        import json

        manager = DownloadManager(
            output_dir=tmp_path, provider=self._mock_provider()
        )
        result = manager.download_sheet("N-34-130-D-d-2-4")
        payload = json.loads(
            (result.parent / f"{result.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"] == {}
```

- [ ] **Krok 2: Uruchom — FAIL** (`TypeError: unexpected keyword argument 'sidecar_extra'`).

Run: `.venv/bin/python -m pytest tests/test_download_manager.py -q`

- [ ] **Krok 3: Implementacja** — konstruktor: parametr `sidecar_extra: dict | None = None` (na końcu listy), `self._sidecar_extra = sidecar_extra`; docstring: „Dodatkowe pola scalane do `extra` każdego sidecara (etap 1: `parent_request` w trybie bbox/geometry)". W `_write_sidecar` do wywołania `build_metadata` dodaj:

```python
                extra=dict(self._sidecar_extra) if self._sidecar_extra else None,
```

- [ ] **Krok 4: Uruchom pełną suitę** — PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/download/manager.py tests/test_download_manager.py
git commit -m "feat(download): DownloadManager(sidecar_extra=) — parent_request w sidecarach trybu bbox/geometry"
```

---

### Zadanie 14: CLI `_parser.py` — `--country`, `--target-crs`, sentinele, nowe choices

Sentinel `None` dla `--resolution`/`--vertical-crs`/`--system` — rozwiązywane per kraj w Zad. 16 (PL: 1m/EVRF2007/1992; CZ: 2m/Bpv). Zachowanie obserwowalne PL bez zmian (asertowane w Zad. 16).

**Files:**
- Modify: `kartograf/cli/_parser.py:75-172` (sekcja download)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `args.country` (`"pl"|"cz"|"auto"`, default `"auto"`), `args.target_crs` (`None` | jeden z `EPSG:2180/5514/3045`), `args.resolution` (`None|"1m"|"5m"|"2m"`), `args.vertical_crs` (`None|"KRON86"|"EVRF2007"|"Bpv"`), `args.system` (`None|"1992"|"2000"`), `args.bbox_crs` (+`EPSG:5514`, `EPSG:3045`).
- Consumes: nic nowego.

- [ ] **Krok 1: Testy (failing)** — do `tests/test_cli.py` nowa klasa (przy `TestCreateParserDownload`):

```python
class TestCreateParserCountry:
    def test_country_default_auto(self):
        args = create_parser().parse_args(["download", "X"])
        assert args.country == "auto"

    def test_country_choices(self):
        for value in ("pl", "cz", "auto"):
            args = create_parser().parse_args(["download", "X", "--country", value])
            assert args.country == value

    def test_country_invalid_rejected(self):
        with pytest.raises(SystemExit):
            create_parser().parse_args(["download", "X", "--country", "de"])

    def test_target_crs_default_none_and_choices(self):
        args = create_parser().parse_args(["download", "X"])
        assert args.target_crs is None
        for value in ("EPSG:2180", "EPSG:5514", "EPSG:3045"):
            args = create_parser().parse_args(
                ["download", "X", "--target-crs", value]
            )
            assert args.target_crs == value
        with pytest.raises(SystemExit):
            create_parser().parse_args(["download", "X", "--target-crs", "EPSG:4326"])

    def test_sentinel_defaults(self):
        """Domyslne --resolution/--vertical-crs/--system to None (per kraj)."""
        args = create_parser().parse_args(["download", "X"])
        assert args.resolution is None
        assert args.vertical_crs is None
        assert args.system is None

    def test_new_choices_accepted(self):
        args = create_parser().parse_args(
            ["download", "X", "--resolution", "2m", "--vertical-crs", "Bpv"]
        )
        assert args.resolution == "2m"
        assert args.vertical_crs == "Bpv"

    def test_bbox_crs_extended_with_cz(self):
        for value in ("EPSG:5514", "EPSG:3045"):
            args = create_parser().parse_args(
                ["download", "--bbox", "1,2,3,4", "--bbox-crs", value]
            )
            assert args.bbox_crs == value
```

Zmiana istniejącego testu (lista dozwolonych): w `TestCreateParserDownloadSystem` test domyślnej wartości `--system` — asercja `args.system == "1992"` → `args.system is None`.

- [ ] **Krok 2: Uruchom — FAIL**.

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "Country or System"`

- [ ] **Krok 3: Implementacja** — w sekcji download `_parser.py`:

```python
    download_parser.add_argument(
        "--country",
        choices=["pl", "cz", "auto"],
        default="auto",
        help="Kraj zrodla danych: pl (GUGiK), cz (CUZK) lub auto — wykrywany "
        "z godla/bboxa; bbox przecinajacy oba kraje pobiera osobne pliki "
        "per kraj (default: auto)",
    )
    download_parser.add_argument(
        "--target-crs",
        choices=["EPSG:2180", "EPSG:5514", "EPSG:3045"],
        default=None,
        help="Reprojekcja serwerowa wyniku (tylko CZ, tylko tryb --bbox/"
        "--geometry; PL pobiera natywnie w EPSG:2180)",
    )
```

Modyfikacje istniejących argumentów:
- `--vertical-crs`: `choices=["KRON86", "EVRF2007", "Bpv"]`, `default=None`, help: `"Uklad pionowy: PL default EVRF2007 (lub KRON86); CZ default Bpv (natywny) lub EVRF2007 (transformacja +0,12..0,14 m)"`.
- `--resolution`: `choices=["1m", "5m", "2m"]`, `default=None`, help: `"Rozdzielczosc siatki: PL 1m/5m (default 1m), CZ 2m/5m (default 2m)"`.
- `--system`: `default=None`, help: `"System godlowania dla --bbox/--geometry — tylko PL (default: 1992)"`.
- `--bbox-crs`: dopisz `"EPSG:5514"`, `"EPSG:3045"` do choices.
- help `download` (opis subkomendy): dopisz zdanie o asymetrii bbox: `"Dla PL --bbox rozwija sie na arkusze zrodlowe; dla CZ --bbox zwraca jeden wycinek serwerowy (exportImage) — dane zrodlowe 1:1 daje tryb godlowy (TM33/SM5)."`.

- [ ] **Krok 4 (OBOWIĄZKOWY): Tymczasowe rozwiązanie sentineli**

Bez tego kroku suita będzie czerwona: `getattr(args, "resolution", "1m")` zwraca `None` (atrybut ISTNIEJE z wartością None), która leci do `create_nmt_provider(resolution=None)` → `ValueError: Unsupported resolution: 'None'` (zweryfikowane; np. `test_download_bbox_basic` patchuje tylko `DownloadManager`, nie fabrykę). Na POCZĄTKU `cmd_download` (przed dyspozycją LAZ) wstaw:

```python
    # TYMCZASOWE (Zad. 14): sentinele -> polskie domysly; Zad. 16 zastapi
    # to pelna dyspozycja per kraj (_resolve_pl_sentinels)
    args.resolution = args.resolution or "1m"
    args.vertical_crs = args.vertical_crs or "EVRF2007"
    args.system = getattr(args, "system", None) or "1992"
```

- [ ] **Krok 5: Uruchom pełną suitę** — PASS (zachowanie obserwowalne PL bez zmian).

- [ ] **Krok 6: Commit**

```bash
git add kartograf/cli/_parser.py kartograf/cli/download_cmd.py tests/test_cli.py
git commit -m "feat(cli): --country/--target-crs, sentinele resolution/vertical-crs/system, bbox-crs 5514/3045"
```

---

### Zadanie 15: CLI — `_cmd_download_cz` (godło + bbox) i sidecary CZ

Samodzielna funkcja (wzór `_cmd_download_laz` — poza `DownloadManager`), testowana bezpośrednio przez `argparse.Namespace`. Podpięcie do `cmd_download` — Zadanie 16. Uwaga: „podsumowanie ok/skip/fail jak w LAZ" ze specu redukuje się tu do komunikatów per plik (`Downloaded to .../Skipped .../Error: ...`), bo żądanie CZ daje zawsze dokładnie jeden plik (LAZ ma wiele kafli na obszar).

**Files:**
- Modify: `kartograf/cli/download_cmd.py` (nowe funkcje na końcu pliku)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `_cmd_download_cz(args: argparse.Namespace, bbox: BBox | None = None, parent_request: dict | None = None) -> int` (bbox podany = tryb bbox z pominięciem parsowania `args.bbox` — używane przez auto-split); helpery `_cz_download_godlo(args, provider, *, quiet, skip_existing) -> int`, `_cz_download_bbox(args, provider, bbox, parent_request, *, quiet, skip_existing) -> int`, `_write_cz_sidecar(provider, target, *, request, capability, horizontal_crs, nodata, server_crs=None, extra=None) -> None`, `_read_tif_nodata(path: Path) -> float | None`.
- Consumes: `create_dmr_provider` (Zad. 12; import lokalny — patch-target `kartograf.providers.cuzk.create_dmr_provider`), `detect_system` (Zad. 11), `FileStorage(subdir=...)` + `get_raw_path`, `build_metadata(capability=, nodata=, transform=, extra=)` (Zad. 4), `MetadataCache` (Zad. 7), `provider.vertical_transform`/`sheet_index` (Zad. 12), `_bbox_to_crs` (Zad. 12).

- [ ] **Krok 1: Testy (failing)** — do `tests/test_cli.py`:

```python
def _cz_args(tmp_path, **overrides):
    """Namespace dla bezposrednich wywolan _cmd_download_cz."""
    base = dict(
        godlo="302_5550", bbox=None, bbox_crs="EPSG:2180", geometry=None,
        layer=None, scale=None, output=str(tmp_path), force=False, quiet=True,
        vertical_crs=None, resolution=None, product="nmt", system=None,
        country="cz", target_crs=None, workers=1, year=None, min_density=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _cz_provider_mock(resolution="2m"):
    """Mock CuzkDmrProvider dla przeplywu CLI."""
    provider = Mock()
    provider.descriptor_key = (
        "cz.cuzk.dmr5g" if resolution == "2m" else "cz.cuzk.dmr4g"
    )
    provider.resolution = resolution
    provider.vertical_crs = "Bpv"
    provider.vertical_transform = None

    def fake_download(godlo, target, timeout=60):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"II*\x00dane")
        return target

    provider.download.side_effect = fake_download
    provider.download_bbox.side_effect = (
        lambda bbox, target, **kw: fake_download("x", target)
    )
    return provider


_CZ_FACTORY_PATCH = "kartograf.providers.cuzk.create_dmr_provider"


class TestCmdDownloadCz:
    def test_tm33_godlo_saves_under_cz_dmr5g(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider) as factory:
            result = _cmd_download_cz(_cz_args(tmp_path))

        assert result == 0
        assert factory.call_args.kwargs["resolution"] == "2m"
        assert factory.call_args.kwargs["vertical_crs"] == "Bpv"
        target = provider.download.call_args.args[1]
        assert target == tmp_path / "cz_dmr5g" / "302" / "5550" / "302_5550.tif"

    def test_tm33_godlo_writes_sidecar(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        with patch(_CZ_FACTORY_PATCH, return_value=_cz_provider_mock()):
            _cmd_download_cz(_cz_args(tmp_path))

        sidecar = (
            tmp_path / "cz_dmr5g" / "302" / "5550" / "302_5550.tif.meta.json"
        )
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "cz.cuzk.dmr5g"
        assert payload["country"] == "CZ"
        assert payload["horizontal_crs"] == "EPSG:3045"  # faktyczny uklad kafla
        assert payload["vertical_crs"] == "EPSG:8357"  # Bpv natywnie
        assert payload["license"]["id"] == "CC-BY-4.0"
        assert payload["request"] == {"godlo": "302_5550"}
        assert payload["transform"] is None  # pobrano natywnie
        assert "parent_request" not in payload["extra"]  # tryb godlowy bez pola

    def test_sm5_godlo_enriches_extra_with_podil(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz
        from kartograf.providers.cuzk.sheets import SheetInfo

        provider = _cz_provider_mock(resolution="5m")
        provider.sheet_index.sm5_sheet.return_value = SheetInfo(
            godlo="CTES96", name="Cesky Tesin 8-6",
            bbox=BBox(-450000, -1105000, -447500, -1103000, "EPSG:5514"),
            podil=0.507, in_cz=None,
        )
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(
                _cz_args(tmp_path, godlo="CTES96", resolution="5m")
            )

        assert result == 0
        sidecar = tmp_path / "cz_dmr4g" / "CTES" / "96" / "CTES96.tif.meta.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["horizontal_crs"] == "EPSG:5514"
        assert payload["extra"]["mapname"] == "Cesky Tesin 8-6"
        assert payload["extra"]["podil"] == 0.507

    def test_sm5_index_failure_after_download_keeps_file(self, tmp_path):
        """Blad indeksu przy PODIL: warning, plik i sidecar bez podil zostaja."""
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock(resolution="5m")
        provider.sheet_index.sm5_sheet.side_effect = DownloadError("siec padla")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(
                _cz_args(tmp_path, godlo="CTES96", resolution="5m")
            )

        assert result == 0
        target = tmp_path / "cz_dmr4g" / "CTES" / "96" / "CTES96.tif"
        assert target.exists()
        payload = json.loads(
            (target.parent / "CTES96.tif.meta.json").read_text(encoding="utf-8")
        )
        assert "podil" not in payload["extra"]

    def test_bbox_mode_flat_file_and_parent_request(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        parent = {
            "bbox": [530000.0, 382000.0, 533000.0, 386000.0],
            "bbox_crs": "EPSG:2180",
            "countries": ["CZ", "PL"],
        }
        bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(
                _cz_args(tmp_path, godlo=None), bbox=bbox, parent_request=parent
            )

        assert result == 0
        target = tmp_path / "cz_dmr5g_-447000_-1114000_-446000_-1113000.tif"
        assert provider.download_bbox.call_args.args[1] == target
        payload = json.loads(
            (tmp_path / f"{target.name}.meta.json").read_text(encoding="utf-8")
        )
        assert payload["extra"]["parent_request"] == parent
        assert payload["horizontal_crs"] == "EPSG:5514"

    def test_target_crs_with_godlo_rejected(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        result = _cmd_download_cz(
            _cz_args(tmp_path, target_crs="EPSG:2180")
        )
        assert result == 1
        assert "--target-crs" in capsys.readouterr().err

    def test_resolution_1m_rejected(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        result = _cmd_download_cz(_cz_args(tmp_path, resolution="1m"))
        assert result == 1
        assert "2m" in capsys.readouterr().err

    def test_product_nmpt_rejected(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz

        result = _cmd_download_cz(_cz_args(tmp_path, product="nmpt"))
        assert result == 1
        assert "etap 2" in capsys.readouterr().err

    def test_kron86_prints_remedy(self, tmp_path, capsys):
        from kartograf.cli.download_cmd import _cmd_download_cz
        from kartograf.transform.crs import TransformUnavailableError

        with patch(
            _CZ_FACTORY_PATCH,
            side_effect=TransformUnavailableError(
                "brak operacji", remedy="uzyj EVRF2007 (EPSG:5621)"
            ),
        ):
            result = _cmd_download_cz(
                _cz_args(tmp_path, vertical_crs="KRON86")
            )
        assert result == 1
        err = capsys.readouterr().err
        assert "EVRF2007" in err

    def test_skip_existing(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        target = tmp_path / "cz_dmr5g" / "302" / "5550" / "302_5550.tif"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"stare")
        provider = _cz_provider_mock()
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            result = _cmd_download_cz(_cz_args(tmp_path))
        assert result == 0
        provider.download.assert_not_called()

    def test_evrf2007_transform_lands_in_sidecar(self, tmp_path):
        from kartograf.cli.download_cmd import _cmd_download_cz

        provider = _cz_provider_mock()
        provider.vertical_crs = "EVRF2007"
        pinned = Mock()
        pinned.description = "Baltic 1957 height to EVRF2007 height (1)"
        pinned.accuracy_m = 0.1
        provider.vertical_transform = pinned
        with patch(_CZ_FACTORY_PATCH, return_value=provider):
            _cmd_download_cz(_cz_args(tmp_path, vertical_crs="EVRF2007"))

        payload = json.loads(
            (tmp_path / "cz_dmr5g" / "302" / "5550" / "302_5550.tif.meta.json")
            .read_text(encoding="utf-8")
        )
        assert payload["vertical_crs"] == "EPSG:5621"
        assert payload["transform"]["vertical"] == (
            "pinned: Baltic 1957 height to EVRF2007 height (1) (0.1 m)"
        )
```

Wymagane importy w test_cli.py (jeśli brak): `json`, `argparse`, `BBox`, `DownloadError`.

- [ ] **Krok 2: Uruchom — FAIL** (`ImportError: _cmd_download_cz`).

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "Cz"`

- [ ] **Krok 3: Implementacja** — na końcu `kartograf/cli/download_cmd.py`:

```python
def _read_tif_nodata(path: Path) -> float | None:
    """Nodata z tagu GeoTIFF (None gdy brak/nieczytelny)."""
    try:
        import rasterio

        with rasterio.open(path) as src:
            return src.nodata
    except Exception:  # noqa: BLE001 — metadane wzbogacone < dane
        return None


def _write_cz_sidecar(
    provider,
    target: Path,
    *,
    request: dict,
    capability: str,
    horizontal_crs: str,
    nodata: float | None,
    server_crs: str | None = None,
    extra: dict | None = None,
) -> None:
    """Best-effort sidecar dla wyniku CZ (blad nie przerywa pobrania)."""
    import logging

    try:
        from kartograf.sources.registry import get_source
        from kartograf.sources.sidecar import build_metadata, write_sidecar

        transform: dict = {}
        if server_crs is not None:
            transform["horizontal"] = f"server:{server_crs}"
        pinned = provider.vertical_transform
        if pinned is not None:
            transform["vertical"] = (
                f"pinned: {pinned.description} ({pinned.accuracy_m} m)"
            )
        meta = build_metadata(
            get_source(provider.descriptor_key),
            request=request,
            vertical_crs=provider.vertical_crs,
            capability=capability,
            nodata=nodata,
            transform=transform or None,
            extra=extra,
        )
        # faktyczny uklad wyniku (kafel TM33: 3045; --target-crs: uklad serwera)
        meta.horizontal_crs = horizontal_crs
        write_sidecar(target, meta)
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        logging.getLogger(__name__).warning(
            f"Nie udalo sie zapisac sidecara dla {target}: {e}"
        )


def _cz_download_godlo(args, provider, *, quiet: bool, skip_existing: bool) -> int:
    """Godlo CZ: TM33 (exportImage) lub SM5 (openzu) do FileStorage."""
    import logging

    from kartograf.core.parser_registry import detect_system
    from kartograf.download.storage import FileStorage
    from kartograf.sources.registry import get_source

    godlo = args.godlo
    system = detect_system(godlo)
    descriptor = get_source(provider.descriptor_key)
    storage = FileStorage(args.output, subdir=descriptor.storage_subdir)
    target = storage.get_raw_path(godlo, f"{godlo}{descriptor.default_extension}")

    if skip_existing and target.exists():
        if not quiet:
            print(f"Skipped {godlo} - already exists at {target}")
        return 0

    if not quiet:
        print(f"Downloading {godlo} (CZ, resolution: {provider.resolution})...")
    try:
        provider.download(godlo, target)
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    extra: dict = {}
    if system.id == "cz_sm5":
        try:
            info = provider.sheet_index.sm5_sheet(godlo)
            if info.name is not None:
                extra["mapname"] = info.name
            if info.podil is not None:
                extra["podil"] = info.podil
        except Exception as e:  # noqa: BLE001 — dane wazniejsze niz metadane
            logging.getLogger(__name__).warning(
                f"Sidecar {godlo} bez PODIL (blad indeksu): {e}"
            )
    horizontal = "EPSG:3045" if system.id == "cz_tm33" else "EPSG:5514"
    capability = "sheet_files" if system.id == "cz_sm5" else "bbox_raster"
    _write_cz_sidecar(
        provider,
        target,
        request={"godlo": godlo},
        capability=capability,
        horizontal_crs=horizontal,
        nodata=_read_tif_nodata(target),
        extra=extra or None,
    )
    if not quiet:
        print(f"Downloaded to {target}")
    return 0


def _cz_download_bbox(
    args, provider, bbox: BBox | None, parent_request: dict | None,
    *, quiet: bool, skip_existing: bool,
) -> int:
    """Bbox CZ: jeden wycinek serwerowy plasko w katalogu wyjsciowym."""
    from kartograf.providers.cuzk.dmr import CUZK_NODATA, _bbox_to_crs

    if bbox is None:
        try:
            parts = [float(x.strip()) for x in args.bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("BBOX must have 4 values")
            bbox = BBox(parts[0], parts[1], parts[2], parts[3], args.bbox_crs)
        except ValueError as e:
            print(f"Error: Invalid bbox format: {e}", file=sys.stderr)
            return 1

    image_sr = args.target_crs or "EPSG:5514"
    if bbox.crs != image_sr:
        bbox = _bbox_to_crs(bbox, image_sr)

    product_dir = "dmr5g" if provider.resolution == "2m" else "dmr4g"
    filename = (
        f"cz_{product_dir}_{bbox.min_x:g}_{bbox.min_y:g}"
        f"_{bbox.max_x:g}_{bbox.max_y:g}.tif"
    )
    target = Path(args.output) / filename

    if skip_existing and target.exists():
        if not quiet:
            print(f"Skipped - already exists at {target}")
        return 0

    if not quiet:
        print(f"Downloading CZ bbox ({provider.resolution}, {image_sr})...")
    try:
        provider.download_bbox(bbox, target)
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    nodata = _read_tif_nodata(target)
    extra = {"parent_request": parent_request} if parent_request else None
    _write_cz_sidecar(
        provider,
        target,
        request={
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": bbox.crs,
        },
        capability="bbox_raster",
        horizontal_crs=image_sr,
        nodata=nodata if nodata is not None else CUZK_NODATA,
        server_crs=args.target_crs,
        extra=extra,
    )
    if not quiet:
        print(f"Downloaded to {target}")
    return 0


def _cmd_download_cz(
    args: argparse.Namespace,
    bbox: BBox | None = None,
    parent_request: dict | None = None,
) -> int:
    """Przeplyw CZ (wzor: _cmd_download_laz — poza DownloadManager)."""
    from kartograf.cache import MetadataCache
    from kartograf.providers.cuzk import create_dmr_provider
    from kartograf.transform.crs import TransformError

    resolution = args.resolution or "2m"
    vertical_crs = args.vertical_crs or "Bpv"
    has_godlo = args.godlo is not None and bbox is None

    if resolution == "1m":
        print(
            "Error: CZ nie ma rozdzielczosci 1m — dostepne: 2m (DMR 5G), "
            "5m (DMR 4G)",
            file=sys.stderr,
        )
        return 1
    if getattr(args, "product", "nmt") != "nmt":
        print(
            f"Error: --product {args.product} dla CZ bedzie dostepny w etapie 2 "
            f"— teraz tylko nmt",
            file=sys.stderr,
        )
        return 1
    if getattr(args, "system", None) is not None:
        print(
            "Error: --system dotyczy tylko PL (godla CZ wykrywane wzorcem)",
            file=sys.stderr,
        )
        return 1
    if has_godlo and args.target_crs is not None:
        print(
            "Error: --target-crs dziala tylko z --bbox/--geometry; "
            "tryb godlowy dostarcza dane natywne 1:1",
            file=sys.stderr,
        )
        return 1

    cache = MetadataCache()
    try:
        try:
            provider = create_dmr_provider(
                resolution=resolution,
                cache=cache,
                target_crs=None if has_godlo else args.target_crs,
                vertical_crs=vertical_crs,
            )
        except TransformError as e:
            remedy = getattr(e, "remedy", None)
            message = f"Error: {e}" + (f" Remedium: {remedy}" if remedy else "")
            print(message, file=sys.stderr)
            return 1
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        quiet = args.quiet
        skip_existing = not args.force
        if has_godlo:
            return _cz_download_godlo(
                args, provider, quiet=quiet, skip_existing=skip_existing
            )
        return _cz_download_bbox(
            args, provider, bbox, parent_request,
            quiet=quiet, skip_existing=skip_existing,
        )
    finally:
        cache.close()
```

- [ ] **Krok 4: Uruchom** — `.venv/bin/python -m pytest tests/test_cli.py -q -k "Cz"` → PASS; pełna suita → PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/cli/download_cmd.py tests/test_cli.py
git commit -m "feat(cli): _cmd_download_cz — godlo TM33/SM5 i bbox exportImage z sidecarami CZ"
```

---

### Zadanie 16: CLI — dyspozycja per kraj w `cmd_download` (`_resolve_pl_sentinels`, konflikty)

Godło → kraj z rejestru systemów; jawny `--country` sprzeczny z krajem systemu → błąd. Sentinele PL rozwiązywane w jednym miejscu. Tryb bbox/geometry z `--country auto` zachowuje się w tym zadaniu jak dotychczas (PL) — pełny auto-split w Zadaniu 17.

**Files:**
- Modify: `kartograf/cli/download_cmd.py:88-212` (`cmd_download`) + nowy helper
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `_resolve_pl_sentinels(args) -> int` (0 = OK, 1 = błąd wypisany na stderr; ustawia `args.resolution/vertical_crs/system` na polskie domyślne, waliduje `2m`/`Bpv`/`--target-crs` dla PL); dyspozycja: godło CZ → `_cmd_download_cz`, konflikt godło/kraj → exit 1.
- Consumes: `detect_system` (Zad. 11), `_cmd_download_cz` (Zad. 15).

- [ ] **Krok 1: Testy (failing)** — do `tests/test_cli.py`:

```python
class TestCountryDispatch:
    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_cz_godlo_routes_to_cz_flow(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(["download", "302_5550", "-o", str(tmp_path), "-q"])
        assert result == 0
        mock_cz.assert_called_once()

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_sm5_godlo_auto_detected(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            ["download", "CTES96", "--resolution", "5m", "-o", str(tmp_path), "-q"]
        )
        assert result == 0
        mock_cz.assert_called_once()

    def test_cz_godlo_with_country_pl_conflicts(self, tmp_path, capsys):
        result = main(["download", "CTES96", "--country", "pl", "-o", str(tmp_path)])
        assert result == 1
        assert "cz_sm5" in capsys.readouterr().err

    def test_pl_godlo_with_country_cz_conflicts(self, tmp_path, capsys):
        result = main(
            ["download", "N-34-130-D-d-2-4", "--country", "cz", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "pl" in capsys.readouterr().err.lower()

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_godlo_sentinels_resolved_to_defaults(self, mock_manager_class,
                                                     tmp_path):
        """Zachowanie obserwowalne PL bez zmian: None -> 1m/EVRF2007."""
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"])
        assert result == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["resolution"] == "1m"

    def test_pl_godlo_with_2m_rejected(self, tmp_path, capsys):
        result = main(
            ["download", "N-34-130-D-d-2-4", "--resolution", "2m",
             "-o", str(tmp_path)]
        )
        assert result == 1
        assert "2m" in capsys.readouterr().err

    def test_pl_godlo_with_bpv_rejected(self, tmp_path, capsys):
        result = main(
            ["download", "N-34-130-D-d-2-4", "--vertical-crs", "Bpv",
             "-o", str(tmp_path)]
        )
        assert result == 1
        assert "Bpv" in capsys.readouterr().err

    def test_pl_godlo_with_target_crs_rejected(self, tmp_path, capsys):
        result = main(
            ["download", "N-34-130-D-d-2-4", "--target-crs", "EPSG:2180",
             "-o", str(tmp_path)]
        )
        assert result == 1
        assert "natywnie" in capsys.readouterr().err

    def test_laz_with_country_cz_rejected(self, tmp_path, capsys):
        result = main(
            ["download", "302_5550", "--product", "laz", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "etap 2" in capsys.readouterr().err
```

- [ ] **Krok 2: Uruchom — FAIL**.

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "CountryDispatch"`

- [ ] **Krok 3: Implementacja**

Helper (przy pozostałych helperach `download_cmd.py`):

```python
def _resolve_pl_sentinels(args: argparse.Namespace) -> int:
    """Rozwiaz sentinele None na polskie domysly; walidacje PL. 0=OK, 1=blad."""
    args.resolution = args.resolution or "1m"
    args.vertical_crs = args.vertical_crs or "EVRF2007"
    args.system = getattr(args, "system", None) or "1992"
    if args.resolution == "2m":
        print(
            "Error: PL nie ma rozdzielczosci 2m — dostepne: 1m, 5m "
            "(2m to DMR 5G w CZ)",
            file=sys.stderr,
        )
        return 1
    if args.vertical_crs == "Bpv":
        print(
            "Error: Bpv to uklad czeski — dla PL dostepne: KRON86, EVRF2007",
            file=sys.stderr,
        )
        return 1
    if getattr(args, "target_crs", None) is not None:
        print(
            "Error: --target-crs dziala tylko dla CZ — PL pobiera natywnie "
            "w EPSG:2180",
            file=sys.stderr,
        )
        return 1
    return 0
```

W `cmd_download` — po walidacji trybów (l.102-119), PRZED dyspozycją LAZ, wstaw:

```python
    from kartograf.core.parser_registry import detect_system

    country_flag = getattr(args, "country", "auto")

    if has_godlo:
        system = detect_system(args.godlo)
        if country_flag != "auto" and country_flag.upper() != system.country:
            print(
                f"Error: Godlo '{args.godlo}' nalezy do systemu {system.id} "
                f"(kraj {system.country}), a podano --country {country_flag}",
                file=sys.stderr,
            )
            return 1
        if system.country == "CZ":
            if getattr(args, "product", "nmt") != "nmt":
                print(
                    f"Error: --product {args.product} dla CZ bedzie dostepny "
                    f"w etapie 2 — teraz tylko nmt",
                    file=sys.stderr,
                )
                return 1
            return _cmd_download_cz(args)
        if _resolve_pl_sentinels(args):
            return 1
```

Dyspozycja LAZ (l.121-123) zostaje po tym bloku (godło CZ + laz kończy się błędem „etap 2" powyżej); w gałęziach `--bbox`/`--geometry` (Zad. 17 je przebuduje) na razie: `--country cz` → `return _cmd_download_cz(args)`; `pl`/`auto` → `_resolve_pl_sentinels(args)` + dotychczasowy przepływ. W `_cmd_download_laz`: na początku dodaj `if getattr(args, "country", "auto") == "cz": print("Error: --product laz dla CZ bedzie dostepny w etapie 2 — teraz tylko nmt", file=sys.stderr); return 1` oraz `_resolve_pl_sentinels(args)` zamiast dotychczasowych `getattr(...)` z defaultami. Usuń tymczasowe rozwiązanie sentineli z Zadania 14 Krok 4 (zastępuje je `_resolve_pl_sentinels` w każdej gałęzi PL).

- [ ] **Krok 4: Uruchom pełną suitę** — PASS (regresja PL: wszystkie istniejące `TestCmdDownload*` zielone bez modyfikacji).

- [ ] **Krok 5: Commit**

```bash
git add kartograf/cli/download_cmd.py tests/test_cli.py
git commit -m "feat(cli): dyspozycja per kraj (godlo->rejestr systemow), sentinele PL, konflikty country/product"
```

---

### Zadanie 17: CLI — auto-split bboxa/geometrii + `parent_request` (PL i CZ)

Decyzja z konsultacji: `parent_request` przy KAŻDYM pobraniu bbox/geometry (auto i jawnym `--country`); w auto bbox przycinany do extentów krajów; wymóg rozwiązywalności `--resolution`/`--vertical-crs` dla KAŻDEGO przeciętego kraju (bez cichego pomijania).

**Files:**
- Modify: `kartograf/cli/download_cmd.py` (`_cmd_download_bbox`, `_cmd_download_geometry` + helpery)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `_countries_for_bbox(bbox: BBox) -> tuple[str, ...]` (kody krajów, posortowane); `_country_bbox(bbox: BBox, code: str, *, auto: bool) -> BBox` (auto: przycięcie w WGS84 + konwersja do 2180/5514; jawnie: bbox bez zmian); `_validate_cross_country(args, countries) -> int` (product/resolution/vertical-crs/system/target-crs — PRZED jakimkolwiek pobraniem); `_build_parent_request(bbox: BBox, countries) -> dict`; `_download_pl_bbox(args, bbox: BBox, parent_request: dict) -> int` (dotychczasowe ciało `_cmd_download_bbox` z managerem budowanym z `sidecar_extra={"parent_request": ...}`); guard LAZ+auto w `_cmd_download_laz` (obszar przecinający CZ → błąd z podpowiedzią `--country pl`).
- Consumes: `all_countries`/`get_country` (Zad. 3), `_cmd_download_cz(bbox=, parent_request=)` (Zad. 15), `DownloadManager(sidecar_extra=)` (Zad. 13), `core.geometry._transform_bbox`, `_resolve_pl_sentinels` (Zad. 16).

- [ ] **Krok 1: Testy (failing)** — do `tests/test_cli.py`:

```python
class TestAutoSplitBBox:
    _BORDER = ["download", "--bbox", "18.4,49.55,18.8,49.75",
               "--bbox-crs", "EPSG:4326", "-q"]
    _PL_ONLY = ["download", "--bbox", "21.0,52.0,21.2,52.2",
                "--bbox-crs", "EPSG:4326", "-q"]

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_border_bbox_splits_into_both_countries(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(self._BORDER + ["-o", str(tmp_path)])

        assert result == 0
        expected_parent = {
            "bbox": [18.4, 49.55, 18.8, 49.75],
            "bbox_crs": "EPSG:4326",
            "countries": ["CZ", "PL"],
        }
        # PL: manager dostal sidecar_extra z parent_request
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["sidecar_extra"] == {"parent_request": expected_parent}
        # CZ: przeplyw wywolany z tym samym parent_request i przycietym bboxem
        cz_kwargs = mock_cz.call_args.kwargs
        assert cz_kwargs["parent_request"] == expected_parent
        assert cz_kwargs["bbox"].crs == "EPSG:5514"

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_pl_only_bbox_no_cz_flow_but_parent_request_present(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        mock_find.return_value = ["N-34-138-A-b-1-1"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager

        result = main(self._PL_ONLY + ["-o", str(tmp_path)])

        assert result == 0
        mock_cz.assert_not_called()
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs["sidecar_extra"]["parent_request"]["countries"] == ["PL"]

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    def test_explicit_cz_bbox_gets_parent_request(self, mock_cz, tmp_path):
        mock_cz.return_value = 0
        result = main(
            ["download", "--bbox", "-447000,-1114000,-446000,-1113000",
             "--bbox-crs", "EPSG:5514", "--country", "cz",
             "-o", str(tmp_path), "-q"]
        )
        assert result == 0
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["countries"] == ["CZ"]
        assert parent["bbox_crs"] == "EPSG:5514"
        # jawny kraj: bbox bez przycinania (przekazany oryginal)
        assert mock_cz.call_args.kwargs["bbox"] == BBox(
            -447000, -1114000, -446000, -1113000, "EPSG:5514"
        )

    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_godlo_mode_has_no_parent_request(self, mock_manager_class, tmp_path):
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        result = main(["download", "N-34-130-D-d-2-4", "-o", str(tmp_path), "-q"])
        assert result == 0
        kwargs = mock_manager_class.call_args.kwargs
        assert kwargs.get("sidecar_extra") is None

    def test_border_bbox_with_1m_unresolvable_for_cz(self, tmp_path, capsys):
        result = main(
            self._BORDER + ["--resolution", "1m", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "--country" in capsys.readouterr().err  # podpowiedz jawnego kraju

    def test_border_bbox_with_kron86_unresolvable_for_cz(self, tmp_path, capsys):
        result = main(
            self._BORDER + ["--vertical-crs", "KRON86", "-o", str(tmp_path)]
        )
        assert result == 1
        assert "--country" in capsys.readouterr().err

    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.cli.download_cmd.find_sheets_for_bbox")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_resolution_5m_resolvable_for_both(
        self, mock_manager_class, mock_find, mock_cz, tmp_path
    ):
        """5m istnieje po obu stronach — auto-split przechodzi."""
        mock_find.return_value = ["M-34-86-D"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0
        result = main(
            self._BORDER + ["--resolution", "5m", "-o", str(tmp_path)]
        )
        assert result == 0
        assert mock_cz.called

    def test_bbox_outside_known_countries(self, tmp_path, capsys):
        result = main(
            ["download", "--bbox", "2.0,40.0,2.5,40.5",
             "--bbox-crs", "EPSG:4326", "-o", str(tmp_path), "-q"]
        )
        assert result == 1
        assert "kraju" in capsys.readouterr().err

    def test_laz_bbox_border_auto_rejected(self, tmp_path, capsys):
        """LAZ (PL-only) + bbox przecinajacy CZ + auto => blad z podpowiedzia,
        zamiast cichego pobrania tylko czesci PL (spec 5.7: bez cichego
        pomijania kraju)."""
        result = main(
            ["download", "--bbox", "18.4,49.55,18.8,49.75",
             "--bbox-crs", "EPSG:4326", "--product", "laz",
             "-o", str(tmp_path), "-q"]
        )
        assert result == 1
        assert "--country pl" in capsys.readouterr().err


class TestAutoSplitGeometry:
    @patch("kartograf.cli.download_cmd._cmd_download_cz")
    @patch("kartograf.core.geometry.get_overall_bbox")
    @patch("kartograf.core.geometry.find_sheets_for_geometry")
    @patch("kartograf.cli.download_cmd.DownloadManager")
    def test_geometry_border_splits(
        self, mock_manager_class, mock_find, mock_overall, mock_cz, tmp_path
    ):
        geometry_file = tmp_path / "area.shp"
        geometry_file.write_bytes(b"stub")
        # overall bbox w 2180 przecinajacy oba kraje (okolice Cieszyna)
        mock_overall.return_value = BBox(
            520000.0, 130000.0, 560000.0, 170000.0, "EPSG:2180"
        )
        mock_find.return_value = ["M-34-86-D-d-4-3"]
        mock_manager = Mock()
        mock_manager.download_sheet.return_value = tmp_path / "x.asc"
        mock_manager_class.return_value = mock_manager
        mock_cz.return_value = 0

        result = main(
            ["download", "--geometry", str(geometry_file), "-o", str(tmp_path), "-q"]
        )

        assert result == 0
        parent = mock_cz.call_args.kwargs["parent_request"]
        assert parent["bbox"] == [520000.0, 130000.0, 560000.0, 170000.0]
        assert parent["bbox_crs"] == "EPSG:2180"
        assert mock_manager_class.call_args.kwargs["sidecar_extra"] == {
            "parent_request": parent
        }
```

Uwaga do współrzędnych: `BBox(520000, 130000, 560000, 170000, "EPSG:2180")` to okolice Cieszyna — przed zapisaniem testu zweryfikuj przecięcie z extentem CZ jednorazowo w konsoli: `python -c "from kartograf.core.geometry import _transform_bbox; from pyproj import CRS; print(_transform_bbox(520000,130000,560000,170000, CRS.from_user_input('EPSG:2180'), 'EPSG:4326'))"` — oczekiwane lon ~18.2-18.8, lat ~49.4-49.8 (przecina CZ: max_lat < 51.06, min_lon > 12.09 i lat < 51.06 … kluczowe: min_y WGS84 < 51.06 i > 48.55). Jeśli nie przecina — dobierz współrzędne tak, by przecinało oba extenty.

- [ ] **Krok 2: Uruchom — FAIL**.

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "AutoSplit"`

- [ ] **Krok 3: Implementacja** — helpery w `download_cmd.py`:

```python
def _countries_for_bbox(bbox: BBox) -> tuple[str, ...]:
    """Kody krajow, ktorych extent_wgs84 przecina bbox (posortowane)."""
    from pyproj import CRS

    from kartograf.core.geometry import _transform_bbox
    from kartograf.sources.registry import all_countries

    if bbox.crs == "EPSG:4326":
        wgs = bbox
    else:
        wgs = _transform_bbox(
            bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y,
            CRS.from_user_input(bbox.crs), "EPSG:4326",
        )
    hits = []
    for profile in all_countries():
        e = profile.extent_wgs84
        if (
            wgs.min_x < e.max_x and wgs.max_x > e.min_x
            and wgs.min_y < e.max_y and wgs.max_y > e.min_y
        ):
            hits.append(profile.code)
    return tuple(sorted(hits))


def _country_bbox(bbox: BBox, code: str, *, auto: bool) -> BBox:
    """Czesc bboxa dla kraju: auto = przycieta do extentu (WGS84) i podana
    w ukladzie roboczym kraju; jawny --country = caly bbox bez zmian."""
    from pyproj import CRS

    from kartograf.core.geometry import _transform_bbox
    from kartograf.sources.registry import get_country

    if not auto:
        return bbox
    if bbox.crs == "EPSG:4326":
        wgs = bbox
    else:
        wgs = _transform_bbox(
            bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y,
            CRS.from_user_input(bbox.crs), "EPSG:4326",
        )
    extent = get_country(code).extent_wgs84
    clipped_wgs = BBox(
        max(wgs.min_x, extent.min_x),
        max(wgs.min_y, extent.min_y),
        min(wgs.max_x, extent.max_x),
        min(wgs.max_y, extent.max_y),
        "EPSG:4326",
    )
    target = "EPSG:2180" if code == "PL" else "EPSG:5514"
    return _transform_bbox(
        clipped_wgs.min_x, clipped_wgs.min_y,
        clipped_wgs.max_x, clipped_wgs.max_y,
        CRS.from_user_input("EPSG:4326"), target,
    )


def _build_parent_request(bbox: BBox, countries: tuple[str, ...]) -> dict:
    """Grupowanie plikow jednego zadania bbox/geometry (klucz: bbox+crs)."""
    return {
        "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
        "bbox_crs": bbox.crs,
        "countries": list(countries),
    }


def _validate_cross_country(args, countries: tuple[str, ...]) -> int:
    """Opcje musza byc rozwiazywalne dla KAZDEGO kraju. 0=OK, 1=blad."""
    hint = "uzyj jawnie --country pl albo --country cz"
    product = getattr(args, "product", "nmt")
    if "CZ" in countries and product != "nmt":
        print(
            f"Error: --product {product} jest dostepny tylko dla PL; {hint}",
            file=sys.stderr,
        )
        return 1
    if "CZ" in countries and args.resolution == "1m":
        print(
            f"Error: --resolution 1m nie istnieje dla CZ (dostepne 2m/5m); "
            f"{hint}",
            file=sys.stderr,
        )
        return 1
    if "PL" in countries and args.resolution == "2m":
        print(
            f"Error: --resolution 2m nie istnieje dla PL (dostepne 1m/5m); "
            f"{hint}",
            file=sys.stderr,
        )
        return 1
    if "CZ" in countries and args.vertical_crs == "KRON86":
        print(
            f"Error: KRON86 nie jest osiagalny dla CZ (siatki GUGiK "
            f"niepubliczne); {hint}",
            file=sys.stderr,
        )
        return 1
    if "PL" in countries and args.vertical_crs == "Bpv":
        print(f"Error: Bpv to uklad czeski; {hint}", file=sys.stderr)
        return 1
    if "CZ" in countries and getattr(args, "system", None) is not None:
        print(f"Error: --system dotyczy tylko PL; {hint}", file=sys.stderr)
        return 1
    if "PL" in countries and getattr(args, "target_crs", None) is not None:
        # walidacja PRZED jakimkolwiek pobraniem — inaczej czesc CZ pobralaby
        # sie, a galaz PL dopiero potem odrzucila zadanie (czesciowe wykonanie)
        print(
            f"Error: --target-crs dziala tylko dla CZ — PL pobiera natywnie "
            f"w EPSG:2180; {hint}",
            file=sys.stderr,
        )
        return 1
    return 0
```

Przebudowa `_cmd_download_bbox`: po sparsowaniu bboxa (l.306-314):

```python
    country_flag = getattr(args, "country", "auto")
    auto = country_flag == "auto"
    countries = (
        _countries_for_bbox(bbox) if auto else (country_flag.upper(),)
    )
    if not countries:
        print(
            "Error: bbox nie przecina zasiegu zadnego znanego kraju (PL, CZ)",
            file=sys.stderr,
        )
        return 1
    if _validate_cross_country(args, countries):
        return 1
    parent_request = _build_parent_request(bbox, countries)

    exit_codes = []
    for code in countries:
        part = _country_bbox(bbox, code, auto=auto)
        if code == "CZ":
            exit_codes.append(
                _cmd_download_cz(args, bbox=part, parent_request=parent_request)
            )
        else:
            # KOPIA args: _resolve_pl_sentinels mutuje Namespace (None->"1m"),
            # co zatrulo by galaz CZ; kopia uniezaleznia od kolejnosci krajow
            pl_args = argparse.Namespace(**vars(args))
            exit_codes.append(_download_pl_bbox(pl_args, part, parent_request))
    return max(exit_codes)
```

`_download_pl_bbox(args, bbox, parent_request) -> int` — dotychczasowe ciało `_cmd_download_bbox` od `target_scale = ...` (l.316) do końca, ze zmianami: (a) na początku `if _resolve_pl_sentinels(args): return 1`; (b) jeśli `bbox.crs` in `("EPSG:5514", "EPSG:3045")` — przetransformuj do `EPSG:2180` przez `_transform_bbox` (jak w `_resolve_laz_bbox`); (c) `DownloadManager(...)` dostaje dodatkowo `sidecar_extra={"parent_request": parent_request}`.

Przebudowa `_cmd_download_geometry` — analogicznie: po walidacji pliku wylicz `overall = get_overall_bbox(filepath, layer=layer, target_crs="EPSG:2180")` (import lokalny z `kartograf.core.geometry` — patch-target `kartograf.core.geometry.get_overall_bbox`), potem `countries`/`_validate_cross_country`/`parent_request = _build_parent_request(overall, countries)`; pętla po `countries`: `CZ` → `_cmd_download_cz(args, bbox=_country_bbox(overall, "CZ", auto=auto), parent_request=parent_request)`, `PL` → dotychczasowe ciało (find_sheets_for_geometry + manager z `sidecar_extra=...`) wywołane na KOPII args (`pl_args = argparse.Namespace(**vars(args))` — jak w pętli bbox). Tryb godłowy w `cmd_download`: bez zmian (manager BEZ `sidecar_extra` — default None).

**Guard LAZ (bbox/geometry + auto):** w `_cmd_download_laz`, zaraz po udanym `_resolve_laz_bbox` i TYLKO gdy żądanie nie jest godłowe (`args.godlo is None` — kraj godła PL jest jednoznaczny), dodaj:

```python
    if getattr(args, "country", "auto") == "auto" and args.godlo is None:
        countries = _countries_for_bbox(bbox)
        if "CZ" in countries:
            print(
                "Error: --product laz jest dostepny tylko dla PL, a obszar "
                "przecina CZ (LAZ dla CZ: etap 2); uzyj jawnie --country pl",
                file=sys.stderr,
            )
            return 1
```

**Aktualizacja 4 istniejących testów geometrii** (z tabeli „Testy istniejące do zmiany"): `test_download_geometry_basic` (l.1225), `test_download_geometry_with_layer` (l.1248), `test_download_geometry_system_2000` (l.1733), `test_download_geometry_default_system_1992` (l.1765) tworzą pusty plik-stub i NIE mockują `get_overall_bbox` — nowy przepływ zawsze go woła (parent_request), a na stubie rzuca on ValidationError („Missing .prj file..."). Do każdego z tych testów dodaj dekorator `@patch("kartograf.core.geometry.get_overall_bbox")` (jako NAJNIŻSZY dekorator → PIERWSZY parametr metody, przed dotychczasowymi mockami) z:

```python
        mock_overall.return_value = BBox(
            455000.0, 350000.0, 465000.0, 360000.0, "EPSG:2180"
        )  # glebia PL — auto-split nie dotknie CZ
```

Asercje tych testów pozostają bez zmian.

- [ ] **Krok 4: Uruchom pełną suitę** — PASS (istniejące `TestCmdDownloadBBox`/`TestDownloadBBoxSystem` zielone bez modyfikacji — mockują `DownloadManager` i `find_sheets_for_bbox`, a ich bboxy 2180 leżą w głębi PL; nowy kwarg `sidecar_extra` nie psuje `Mock`ów; 4 testy geometrii zaktualizowane jak wyżej).

- [ ] **Krok 5: CHANGELOG + commit**

Do `docs/CHANGELOG.md` (0.7.0, Added): `--country {pl,cz,auto} z auto-podzialem bboxa transgranicznego; extra.parent_request w sidecarach trybu bbox/geometry (grupowanie plikow jednego zadania)`.

```bash
git add kartograf/cli/download_cmd.py tests/test_cli.py docs/CHANGELOG.md
git commit -m "feat(cli): auto-split bboxa/geometrii per kraj + extra.parent_request w trybie bbox/geometry"
```

---

### Zadanie 18: Eksporty publiczne + wersja pakietu

**Files:**
- Modify: `kartograf/__init__.py` (importy, `__all__`, `__version__`)
- Modify: `kartograf/cli/_parser.py:26-30` (`--version` z `__version__`)
- Test: `tests/test_cli.py` lub nowy test w istniejącym pliku testów API

**Interfaces:**
- Produces: `from kartograf import CuzkDmrProvider, ParserTM33, create_dmr_provider`; `__version__ == "0.7.0-dev"`; `kartograf --version` drukuje wersję z `__version__`.
- Consumes: Zad. 6 i 12.

- [ ] **Krok 1: Test (failing)** — do `tests/test_cli.py` (lub `tests/test_init.py`, jeśli istnieje test eksportów):

```python
class TestPublicApiCz:
    def test_cz_exports_available(self):
        from kartograf import CuzkDmrProvider, ParserTM33, create_dmr_provider

        assert ParserTM33("302_5550").get_bbox().crs == "EPSG:3045"
        assert callable(create_dmr_provider)
        assert CuzkDmrProvider.__name__ == "CuzkDmrProvider"

    def test_version_bumped(self):
        from kartograf import __version__

        assert __version__ == "0.7.0-dev"
```

- [ ] **Krok 2: Uruchom — FAIL**; dodatkowo sprawdź, czy inne testy nie przybijają starej wersji:

```bash
grep -rn "0\.6\.1" tests/ kartograf/
```
Każde trafienie poza `docs/` zaktualizuj w Kroku 3 (w `_parser.py` wersja przechodzi na odczyt z `__version__`, więc testy asertujące literał wymagają zmiany na odczyt z `kartograf.__version__` — to jedyna dozwolona modyfikacja).

- [ ] **Krok 3: Implementacja**

`kartograf/__init__.py`: `__version__ = "0.7.0-dev"`; importy `from kartograf.core.parser_tm33 import ParserTM33`, `from kartograf.providers.cuzk import CuzkDmrProvider, create_dmr_provider`; do `__all__` (sekcja Providers): `"CuzkDmrProvider"`, `"create_dmr_provider"`; (sekcja Core): `"ParserTM33"`.

`kartograf/cli/_parser.py` — na górze `from kartograf import __version__`, a w `add_argument("--version", ...)`: `version=f"%(prog)s {__version__}"`.

- [ ] **Krok 4: Uruchom pełną suitę** — PASS.

- [ ] **Krok 5: Commit**

```bash
git add kartograf/__init__.py kartograf/cli/_parser.py tests/
git commit -m "feat(api): eksporty CuzkDmrProvider/ParserTM33/create_dmr_provider; wersja 0.7.0-dev"
```

---

### Zadanie 19: Brama jakości — pełna suita, ruff, mypy, pokrycie

**Files:** poprawki punktowe wynikające z narzędzi (bez zmian zachowania).

- [ ] **Krok 1: Pełna suita + pokrycie**

```bash
.venv/bin/python -m pytest tests/ -q --cov=kartograf --cov-report=term | tail -30
```
Oczekiwane: 0 failed; pokrycie łączne ≥ 80% (baza: ~88% przy 1142 testach po etapie 0 — nowe moduły CZ nie mogą jej zbić poniżej progu; jeśli któryś moduł CZ ma < 80%, dopisz brakujące testy w odpowiednim pliku testowym z tego planu).

- [ ] **Krok 2: Ruff**

```bash
.venv/bin/python -m ruff check kartograf/ tests/
.venv/bin/python -m ruff format --check kartograf/ tests/
```
Oczekiwane: czysto. Poprawki formatowania: `.venv/bin/python -m ruff format kartograf/ tests/`.

- [ ] **Krok 3: Mypy**

```bash
.venv/bin/python -m mypy kartograf/ 2>&1 | tail -5
```
Oczekiwane: liczba błędów ≤ baseline sprzed etapu (ok. 33, wyłącznie w starych modułach). ZERO nowych błędów w `kartograf/providers/cuzk/`, `kartograf/core/parser_tm33.py` i modyfikowanych plikach.

- [ ] **Krok 4: Commit poprawek (jeśli były)**

```bash
git add -A && git commit -m "chore: poprawki ruff/mypy po etapie 1 (bez zmian zachowania)"
```

---

### Zadanie 20: E2E na żywych danych (macierz akceptacyjna, spec sekcja 11.3-11.4)

Wymaga sieci. Wyniki (ścieżki, rozmiary, fragmenty sidecarów) zapisz do `docs/research/2026-08-11-etap1-e2e.md`. Katalog roboczy: `/tmp/kartograf-e2e-etap1` (poza repo).

- [ ] **Krok 1: Godło TM33**

```bash
cd /home/claude-agent/workspace/Kartograf && OUT=/tmp/kartograf-e2e-etap1
.venv/bin/kartograf download 302_5550 --country cz -o $OUT
.venv/bin/python - <<'EOF'
import json, rasterio
p = "/tmp/kartograf-e2e-etap1/cz_dmr5g/302/5550/302_5550.tif"
with rasterio.open(p) as src:
    assert src.crs.to_epsg() in (3045, 25833), src.crs
    assert src.res == (2.0, 2.0), src.res
    assert src.bounds == (302000.0, 5550000.0, 304000.0, 5552000.0), src.bounds
    assert src.nodata == -9999.0, src.nodata
meta = json.load(open(p + ".meta.json"))
assert meta["license"]["id"] == "CC-BY-4.0"
assert meta["vertical_crs"] == "EPSG:8357"
assert meta["horizontal_crs"] == "EPSG:3045"
print("OK TM33")
EOF
```

- [ ] **Krok 2: Godło SM5 (kraj auto-wykryty)**

```bash
.venv/bin/kartograf download CTES96 --resolution 5m -o $OUT
.venv/bin/python - <<'EOF'
import json, rasterio
p = "/tmp/kartograf-e2e-etap1/cz_dmr4g/CTES/96/CTES96.tif"
with rasterio.open(p) as src:
    assert src.crs is not None and src.crs.to_epsg() == 5514, src.crs
    assert src.nodata == -9999.0
meta = json.load(open(p + ".meta.json"))
assert 0.0 < meta["extra"]["podil"] <= 1.0
print("OK SM5, podil =", meta["extra"]["podil"])
EOF
```

- [ ] **Krok 3: Bbox przygraniczny `--country auto` (osobne pliki PL i CZ, wspólny parent_request)**

```bash
.venv/bin/kartograf download --bbox 18.55,49.60,18.65,49.70 --bbox-crs EPSG:4326 -o $OUT/auto
.venv/bin/python - <<'EOF'
import json, pathlib
metas = list(pathlib.Path("/tmp/kartograf-e2e-etap1/auto").rglob("*.meta.json"))
assert metas, "brak sidecarow"
parents = {json.dumps(json.load(open(m))["extra"]["parent_request"], sort_keys=True) for m in metas}
countries = {json.load(open(m))["country"] for m in metas}
assert len(parents) == 1, "parent_request musi byc identyczny we wszystkich sidecarach"
assert countries == {"PL", "CZ"}, countries
parent = json.loads(next(iter(parents)))
assert parent["countries"] == ["CZ", "PL"]
print("OK auto-split:", len(metas), "plikow")
EOF
```
Uwaga: jeśli GUGiK nie ma NMT 1m dla tego obszaru (znany problem pokrycia), dobierz bbox przygraniczny z pokryciem po stronie PL (sprawdź WMS skorowidzów) — bez zmiany logiki testu.

- [ ] **Krok 4: `--target-crs EPSG:2180`**

```bash
.venv/bin/kartograf download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180 -o $OUT/reproj
.venv/bin/python - <<'EOF'
import glob, json, rasterio
p = glob.glob("/tmp/kartograf-e2e-etap1/reproj/cz_dmr5g_*.tif")[0]
with rasterio.open(p) as src:
    assert src.crs.to_epsg() == 2180, src.crs.to_wkt()
meta = json.load(open(p + ".meta.json"))
assert meta["transform"]["horizontal"] == "server:EPSG:2180"
assert meta["horizontal_crs"] == "EPSG:2180"
print("OK target-crs")
EOF
```

- [ ] **Krok 5: `--vertical-crs EVRF2007` i KRON86**

```bash
.venv/bin/kartograf download 302_5550 --country cz --vertical-crs EVRF2007 -o $OUT/evrf --force
.venv/bin/python - <<'EOF'
import json, rasterio, numpy as np
p_bpv = "/tmp/kartograf-e2e-etap1/cz_dmr5g/302/5550/302_5550.tif"
p_evrf = "/tmp/kartograf-e2e-etap1/evrf/cz_dmr5g/302/5550/302_5550.tif"
meta = json.load(open(p_evrf + ".meta.json"))
assert meta["vertical_crs"] == "EPSG:5621"
assert meta["transform"]["vertical"].startswith("pinned: ")
with rasterio.open(p_bpv) as a, rasterio.open(p_evrf) as b:
    da, db = a.read(1), b.read(1)
mask = (da != -9999) & (db != -9999)
diff = (db - da)[mask]
assert 0.10 < float(diff.mean()) < 0.16, diff.mean()  # +0,117..0,143 m
print("OK EVRF2007, sredni offset:", float(diff.mean()))
EOF
# KRON86 -> czytelny blad z remedium (exit code 1)
.venv/bin/kartograf download 302_5550 --country cz --vertical-crs KRON86 -o $OUT; echo "exit=$?"
```
Oczekiwane na końcu: komunikat błędu zawiera remedium (siatki niepubliczne / EVRF2007) i `exit=1`.

- [ ] **Krok 6: Regresja PL**

```bash
.venv/bin/kartograf download N-34-130-D-d-2-4 -o $OUT/pl
.venv/bin/kartograf landcover list-sources
.venv/bin/kartograf cache stats
```
Oczekiwane: NMT PL pobiera się jak dotąd (plik + sidecar z `vertical_crs = "EPSG:9651"`); `cache stats` drukuje `URL/TERYT/Sheet entries`.

- [ ] **Krok 7: Notatka + commit**

```bash
git add docs/research/2026-08-11-etap1-e2e.md
git commit -m "docs(research): wyniki E2E etapu 1 na zywych danych CUZK + regresja PL"
```

---

### Zadanie 21: Dokumentacja — ADR-023, CHANGELOG, CLAUDE.md, SCOPE.md, PROGRESS.md

**Files:**
- Modify: `docs/DECISIONS.md` (nowy wpis ADR-023 wg szablonu `ADR-XXX` z l.399)
- Modify: `docs/CHANGELOG.md` (finalizacja sekcji 0.7.0)
- Modify: `CLAUDE.md`, `docs/SCOPE.md`, `docs/PROGRESS.md`

- [ ] **Krok 1: ADR-023** — tytuł: „Silnik CUZK, polityka układów CZ i EVRF2007→5621 (etap 1)". Treść musi pokrywać (po jednym akapicie): (a) `CuzkClient` jako pierwszy silnik sterowany deskryptorem (`AccessChannel.endpoint`), ekstrakcja do `transport/` odroczona do drugiego konsumenta (DE/SK); (b) przepływ CZ omija `DownloadManager` (precedens LAZ; godło CZ = zawsze jeden plik); (c) TM33 w trybie godłowym w EPSG:3045, asymetria trybu bbox PL/CZ (arkusze vs wycinek serwerowy); (d) decyzja EVRF2007=EPSG:5621 globalnie + mapa rodzina→realizacja (BREAKING ograniczony do `vertical_crs_code`); (e) `Bpv`=EPSG:8357 (Baltic 1957, nie 1977), pionowa 8357→5621 przypiętą operacją 0,1 m, KRON86 nieosiągalny (siatki niepubliczne); (f) rozstrzygnięcia z konsultacji 2026-08-11: `parent_request` zawsze w trybie bbox/geometry (klucz grupowania bbox+crs, scenariusz dwuetapowego dociągania), `--target-crs` w trybie godłowym = ValidationError, polimorficzne `PinnedTransform.transform`; (g) sentinele `None` dla `--resolution`/`--vertical-crs`/`--system` rozwiązywane per kraj.

- [ ] **Krok 2: CHANGELOG 0.7.0** — uporządkuj sekcję: BREAKING (`vertical_crs_code` — wpis z Zad. 2, z tabelką starego/nowego mapowania), Added (CZ: providery, parsery, CLI, `sheet_cache`, `parent_request`, `capability=`/`nodata=`, `sidecar_extra`, `endpoint`), Changed (sentinele CLI, polimorficzne `transform`, probe pod polityką sieci, sidecary PL w trybie bbox/geometry dostają `extra.parent_request`).

- [ ] **Krok 3: CLAUDE.md** — (a) sekcja „Struktura modulow": dodaj `core/parser_tm33.py`, `providers/cuzk/` (4 pliki z jednolinijkowymi opisami), zaktualizuj opisy `descriptor.py` (+endpoint), `registry.py` (+CZ, +resolve_vertical_crs), `metadata.py` (+sheet_cache); (b) sekcja „Komendy": dodaj przykłady `kartograf download 302_5550 --country cz`, `kartograf download CTES96 --resolution 5m`, `kartograf download --bbox ... --country auto`, `--target-crs EPSG:2180`, `--vertical-crs Bpv|EVRF2007`; (c) sekcja „Ograniczenia": dopisz limity CZ (exportImage 15000×4100 px → kafelkowanie; SM5 tylko 5m; KRON86 nieosiągalny dla CZ; asymetria bbox PL/CZ).

- [ ] **Krok 4: SCOPE.md** — dopisz zakres CZ (DMR 5G/4G — co jest; DMP/Orto/LAZ CZ i ZABAGED — etapy 2-3) ORAZ zaległe z etapu 0: aktualne drzewo modułów (skopiuj strukturę z sekcji „Struktura plików" tego planu + istniejące moduły z CLAUDE.md).

- [ ] **Krok 5: PROGRESS.md** — sekcja „Ostatnia sesja": etap 1 zaimplementowany (lista zadań planu), macierz E2E z Zad. 20, następne kroki (etap 2: DMP/Orto/LAZ CZ; obserwacja WCS EVRF2007 GUGiK).

- [ ] **Krok 6: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: ADR-023 (silnik CUZK, uklady CZ, EVRF2007->5621), CHANGELOG 0.7.0, CLAUDE/SCOPE/PROGRESS"
```

---

## Mapowanie kryteriów akceptacji specu (sekcja 11) na zadania

| Kryterium | Pokrycie |
|---|---|
| 1. Pełny pytest zielony (zmiany istniejących testów tylko z listy) | Zad. 2-18 (TDD per zadanie) + Zad. 19; lista zmian: sekcja „Testy istniejące do zmiany" |
| 2. ruff / ruff format / mypy czyste | Zad. 19 |
| 3a. `download 302_5550 --country cz` → `cz_dmr5g/302/5550/302_5550.tif` + sidecar CC-BY-4.0/Bpv | Zad. 20 krok 1 |
| 3b. `download CTES96 --resolution 5m` → `cz_dmr4g/CTES/96/CTES96.tif` z EPSG:5514 + `podil` | Zad. 20 krok 2 |
| 3c. bbox przygraniczny auto → osobne pliki PL/CZ, wspólny `parent_request`, zero scalania | Zad. 20 krok 3 |
| 3d. `--target-crs EPSG:2180` → WKT 2180 + `transform.horizontal="server:EPSG:2180"` | Zad. 20 krok 4 |
| 3e. `--vertical-crs EVRF2007` → sidecar 5621 + opis operacji; KRON86 → błąd z remedium | Zad. 20 krok 5 |
| 4. Zachowanie PL niezmienione (próbka regresyjna) | Zad. 16 (testy dispatch), Zad. 20 krok 6 |
| 5. Deskryptory CZ kompletne + test spójności deskryptor↔provider | Zad. 3, Zad. 12 (`TestDescriptorProviderConsistency`) |
| 6. Dokumentacja (ADR, CHANGELOG BREAKING, CLAUDE.md, SCOPE.md z drzewem, PROGRESS) | Zad. 2/12/17 (CHANGELOG na bieżąco), Zad. 21 |

## Kolejność i zależności

`1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 20 → 21`

Zadania 5, 6, 13 są niezależne od łańcucha CUZK (mogą iść równolegle po Zad. 2-4), ale kolejność liniowa jest bezpieczna i zalecana przy wykonaniu subagentami. Zadanie 1 (rekonesans) MUSI poprzedzać 8-12 (fixtury i semantyka pyproj); Zadanie 11 wymaga 6 i 10; Zadanie 12 wymaga 3, 5, 8-11; Zadania 15-17 wymagają 12-14.
