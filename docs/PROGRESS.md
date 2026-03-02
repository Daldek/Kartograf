# PROGRESS — Kartograf

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| NMT (parser + pobieranie) | ✅ Gotowy | v0.1.0+ |
| NMPT (Digital Surface Model) | ✅ Gotowy | v0.4.0 |
| Ortofotomapa | ✅ Gotowy | v0.4.0 |
| Land Cover (BDOT10k) | ✅ Gotowy | v0.3.0+, hydro v0.4.1 |
| Land Cover (CORINE) | ✅ Gotowy | v0.3.0+ |
| SoilGrids | ✅ Gotowy | v0.3.0+ |
| HSG | ✅ Gotowy | v0.3.0+ |
| bbox → godla | ✅ Gotowy | find_sheets_for_bbox(), CLI --bbox |
| geometry → godla | ✅ Gotowy | find_sheets_for_geometry(), CLI --geometry |
| CLI | ✅ Gotowy | 5 komend + --bbox + --product + --category + --geometry |
| Auth Proxy (CLMS) | ✅ Gotowy | v0.3.0+ |
| PL-2000 (godlowanie) | ✅ Gotowy | Parser2000, auto-detekcja, CLI, storage |
| Pokrycie testami | ✅ Gotowy | 835 testow, cel 80% osiagniety |
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

### CP6 — NMPT, Ortofotomapa, nowa struktura storage
- **Data:** 2026-02-07
- **Wersja:** v0.4.0
- **Zakres:** GugikNmptProvider, GugikOrtoProvider, --product CLI, podkatalogi nmt_1m/nmt_5m/nmpt/orto, 574 testow, 83.95% pokrycie

### CP7 — BDOT10k rtree fix + hydro category + geometry selection
- **Data:** 2026-02-08
- **Wersja:** v0.4.1
- **Zakres:** _copy_rtree_index() fix, HYDRO_LAYERS/CATEGORY_FILTERS, --category CLI, geometry.py, --geometry CLI, pyshp, 636 testow

### CP8 — PL-2000 sheet naming system
- **Data:** 2026-02-24
- **Wersja:** v0.5.0 (w trakcie)
- **Zakres:** Parser2000, auto-detekcja PL-1992/PL-2000, find_sheets_2000_for_bbox, CLI --system, FileStorage PL-2000, 849 testow

## Ostatnia sesja

**Data:** 2026-03-02

### Co zrobiono
- **refactor: usunięcie filtrowania BDOT10k po kategorii**
  - Usunięto stałe `PT_LAYERS`, `HYDRO_LAYERS`, `CATEGORY_FILTERS`
  - Usunięto parametr `category` z `download_by_teryt()`, `_download_with_retry()`, `_extract_gpkg_from_zip()`
  - `_extract_gpkg_from_zip()` wyciąga i scala **wszystkie** warstwy GPKG z ZIP
  - `get_available_layers()` zwraca wszystkie 15 warstw (PT* + SW*)
  - Usunięto argument CLI `--category`
  - Zaktualizowano `cmd_landcover_list_layers` — płaska lista warstw
  - Usunięto 14 testów kategorii (849→835), zaktualizowano `test_available_layers`
  - ADR-014 zastąpiona przez ADR-016
  - Zaktualizowano docs: CHANGELOG, SCOPE, PRD, DECISIONS, CLAUDE.md

### Nastepne kroki
1. Weryfikacja z realnymi danymi GUGiK (download 6.179.12.20.asc, porownanie BBox z headerem)
2. Bump wersji do v0.5.0 i merge develop → main
3. Pobieranie rownolegle (v0.5+)
4. Cache metadanych (SQLite)

## Backlog

- [x] Pokrycie testami do 80% (849 testow)
- [x] NMPT provider (GugikNmptProvider)
- [x] Ortofotomapa provider (GugikOrtoProvider)
- [x] CLI --product {nmt,nmpt,orto}
- [x] PL-2000 godlowanie (Parser2000, auto-detekcja, CLI)
- [ ] Weryfikacja BBox PL-2000 z realnymi danymi GUGiK
- [ ] Pobieranie rownolegle (multi-threading)
- [ ] Cache metadanych (SQLite)
- [ ] Mozaikowanie arkuszy NMT
- [ ] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
