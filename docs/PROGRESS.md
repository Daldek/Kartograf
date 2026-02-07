# PROGRESS — Kartograf

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| NMT (parser + pobieranie) | ✅ Gotowy | v0.1.0+ |
| Land Cover (BDOT10k) | ✅ Gotowy | v0.3.0+ |
| Land Cover (CORINE) | ✅ Gotowy | v0.3.0+ |
| SoilGrids | ✅ Gotowy | v0.3.0+ |
| HSG | ✅ Gotowy | v0.3.0+ |
| bbox → godla | ✅ Gotowy | find_sheets_for_bbox(), CLI --bbox |
| CLI | ✅ Gotowy | 5 komend + --bbox |
| Auth Proxy (CLMS) | ✅ Gotowy | v0.3.0+ |
| Pokrycie testami | ✅ Gotowy | 83%, cel 80% osiągnięty |
| Migracja na ruff | ✅ Gotowy | config + auto-fix, sesja 2026-02-03 |

<!-- Statusy: ✅ Gotowy | 🔧 W trakcie | ⏳ Zaplanowany | ❌ Wstrzymany -->

## Checkpointy

### CP1 — MVP (NMT)
- **Data:** 2026-01-17
- **Wersja:** v0.1.0
- **Zakres:** Parser godel, GugikProvider, DownloadManager, FileStorage, CLI (parse/download), 235 testow

### CP2 — Nowa architektura pobierania
- **Data:** 2026-01-18
- **Wersja:** v0.2.0
- **Zakres:** Rozdzielenie OpenData (ASC) vs WCS (GeoTIFF), SheetParser.get_bbox(), BBox, pyproj, 245 testow

### CP3 — Land Cover, SoilGrids, HSG
- **Data:** 2026-01-18
- **Wersja:** v0.3.0
- **Zakres:** BDOT10k, CORINE (+ Auth Proxy), SoilGrids, HSGCalculator, LandCoverManager, 347 testow

### CP4 — NMT resolution, QA
- **Data:** 2026-01-21
- **Wersja:** v0.3.1
- **Zakres:** Wybor rozdzielczosci NMT (1m/5m), cross-project compatibility, QA review, 365 testow

### CP5 — Storage structure, EVRF2007
- **Data:** 2026-01-21
- **Wersja:** v0.3.2
- **Zakres:** Nowa struktura katalogow (data/1m/, data/5m/), domyslny vertical_crs EVRF2007, 365 testow

## Ostatnia sesja

**Data:** 2026-02-07

### Co zrobiono
- **test: pokrycie testami 59% → 83% (cel 80% osiagniety)**
  - Nowy `tests/test_auth_client.py` — 30 testow (auth/client.py 0% → ~85%)
    - Singleton, proxy lifecycle, token management, requests, downloads, cleanup
  - Nowy `tests/test_auth_proxy.py` — 24 testy (auth/proxy.py 0% → ~70%)
    - CLMSCredentials (keychain, JWT token exchange), ProxyHandler endpoints, run_server
  - Rozszerzony `tests/test_landcover.py` — +38 testow (bdot10k 28% → ~65%, corine 33% → ~60%, manager 65% → ~85%)
    - Bdot10kProvider: download_by_teryt/godlo, TERYT lookup, retry, ZIP/GPKG extract/merge
    - CorineProvider: init, WMS download/dimensions/max_size, retry, bbox transforms
    - LandCoverManager: download dispatch (teryt/bbox/godlo), auto paths, layers/formats
  - Rozszerzony `tests/test_hsg.py` — +6 testow (hsg.py 59% → ~80%)
    - HSGCalculator: calculate_hsg_by_godlo/bbox, nodata, keep_intermediate, statistics
  - Rozszerzony `tests/test_cli.py` — +11 testow (commands.py 68% → ~78%)
    - Landcover CLI: download by teryt/godlo/bbox, source corine, list layers
    - Soilgrids CLI: hsg success/stats/error, download success
- **feat(parser): `find_sheets_for_bbox()` — reverse lookup: bbox → godla arkuszy** (wczesniej w sesji)
  - Nowe funkcje w `sheet_parser.py`: `find_sheets_for_bbox()`, `_bboxes_intersect()`, `_transform_bbox_to_wgs84()`, `_find_1m_sheets()`, `_find_200k_sheets()`, `_find_children_intersecting()`
  - Algorytm hierarchicznego przycinania: 1:1M → 1:200k (siatka 12x12) → rekurencyjne drazenie do docelowej skali
- **feat(cli): `kartograf download --bbox` — pobieranie NMT dla bbox** (wczesniej w sesji)
  - `--bbox min_x,min_y,max_x,max_y` + `--bbox-crs {EPSG:2180,EPSG:4326}`
- Testy: **507 testow**, pokrycie **83.08%**, ruff clean

### Nastepne kroki
1. Pobieranie rownolegle (v0.4+)
2. Cache metadanych (SQLite)

## Backlog

- [x] Pokrycie testami do 80% (83%, 507 testow)
- [ ] Pobieranie rownolegle (multi-threading)
- [ ] Cache metadanych (SQLite)
- [ ] Mozaikowanie arkuszy NMT
- [ ] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
