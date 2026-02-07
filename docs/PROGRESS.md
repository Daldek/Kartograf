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
| Pokrycie testami | 🔧 W trakcie | 57%, cel 80% |
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
- **feat(parser): `find_sheets_for_bbox()` — reverse lookup: bbox → godla arkuszy**
  - Nowe funkcje w `sheet_parser.py`: `find_sheets_for_bbox()`, `_bboxes_intersect()`, `_transform_bbox_to_wgs84()`, `_find_1m_sheets()`, `_find_200k_sheets()`, `_find_children_intersecting()`
  - Algorytm hierarchicznego przycinania: 1:1M → 1:200k (siatka 12x12) → rekurencyjne drążenie do docelowej skali
  - Obsługa EPSG:2180 i EPSG:4326, walidacja CRS i skali
  - Eksport w `__init__.py`
- **feat(cli): `kartograf download --bbox` — pobieranie NMT dla bbox**
  - `--bbox min_x,min_y,max_x,max_y` + `--bbox-crs {EPSG:2180,EPSG:4326}`
  - `godlo` staje się opcjonalny (pozycyjny, nargs="?")
  - Walidacja: godlo XOR --bbox (oba lub żaden → error)
  - Nowa `_cmd_download_bbox()` — find sheets, iterate download
- Testy: 398 testów przechodzi (pytest tests/ -v), ruff clean
  - 18 nowych testów find_sheets_for_bbox (roundtrip, boundary, 2180/4326, invalid)
  - 11 nowych testów CLI bbox (basic, epsg4326, errors, scale, parser)

### Nastepne kroki
1. Pokrycie testami do 80% (priorytet: auth/, providers/bdot10k.py, providers/corine.py)
2. Pobieranie rownolegle (v0.4+)

## Backlog

- [ ] Pokrycie testami do 80% (obecnie 57%)
- [ ] Pobieranie rownolegle (multi-threading)
- [ ] Cache metadanych (SQLite)
- [ ] Mozaikowanie arkuszy NMT
- [ ] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
