# PROGRESS — Kartograf

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| NMT (parser + pobieranie) | ✅ Gotowy | v0.1.0+ |
| NMPT (Digital Surface Model) | ✅ Gotowy | v0.4.0 |
| Ortofotomapa | ✅ Gotowy | v0.4.0 |
| LAZ (chmury punktów LIDAR) | ✅ Gotowy | WFS, area-based, --product laz, 2026-06-24 |
| Land Cover (BDOT10k) | ✅ Gotowy | v0.3.0+, 15 warstw v0.5.0 |
| Land Cover (CORINE) | ✅ Gotowy | v0.3.0+ |
| SoilGrids | ✅ Gotowy | v0.3.0+ |
| HSG | ✅ Gotowy | v0.3.0+ |
| bbox → godla | ✅ Gotowy | find_sheets_for_bbox(), CLI --bbox |
| geometry → godla | ✅ Gotowy | find_sheets_for_geometry(), CLI --geometry |
| CLI | ✅ Gotowy | 5 komend + --bbox + --product + --system + --geometry |
| Auth Proxy (CLMS) | ✅ Gotowy | v0.3.0+ |
| PL-2000 (godlowanie) | ✅ Gotowy | Parser2000, auto-detekcja, CLI, storage |
| Pokrycie testami | ✅ Gotowy | ~84%, 1060 testow, cel 80% osiagniety |
| Migracja na ruff | ✅ Gotowy | config + auto-fix, sesja 2026-02-03 |
| Pobieranie rownolegle | ✅ Gotowy | ThreadPoolExecutor, --workers, v0.6.0 |
| Cache metadanych (SQLite) | ✅ Gotowy | MetadataCache, WAL, TTL 7d, v0.6.0 |
| Weryfikacja BBox PL-2000 | ✅ Gotowy | 67 testow, reference values + live WMS |
| Walidacja warstw WMS | ✅ Gotowy | GetCapabilities, lazy, fallback; NMT+NMPT v0.6.1, Orto 2026-06-24 |

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
- **Data:** 2026-03-02
- **Wersja:** v0.5.0
- **Zakres:** Parser2000, auto-detekcja PL-1992/PL-2000, find_sheets_2000_for_bbox, CLI --system, FileStorage PL-2000, usuniecie --category, 835 testow

### CP9 — Parallel downloads, metadata cache, PL-2000 verification
- **Data:** 2026-03-03
- **Wersja:** v0.6.0
- **Zakres:** ThreadPoolExecutor parallel downloads (--workers), SQLite MetadataCache (WAL, TTL, prune), PL-2000 BBox verification (67 testow), 990 testow

### CP10 — WMS layer validation, NMT 5m bugfix
- **Data:** 2026-03-24
- **Wersja:** v0.6.1
- **Zakres:** Naprawione nazwy warstw WMS 5m, walidacja warstw WMS przez GetCapabilities (lazy, fallback, in-memory cache), 1007 testow

## Ostatnia sesja

**Data:** 2026-06-24

### Co zrobiono
- **fix(gugik): zaktualizowane nazwy warstw WMS dla NMT 1m/EVRF2007**
  - `WMS_LAYERS["1m"]["EVRF2007"]`: `[2025, 2024, 2023, 2022iStarsze]` →
    `[2026, 2025, 2024, 2023iStarsze]`
  - Dodana `SkorowidzeNMT2026`, usuniete nieistniejace `2023` i `2022iStarsze`
  - Zweryfikowane live przez GetCapabilities 3 endpointow (KRON86, EVRF2007, 5m)
  - `1m/KRON86` i `5m/EVRF2007` bez zmian (5m endpoint nadal serwuje starsze roczniki)
  - Wykryte przy godle M-34-27-B-b-1-2 (Kielchinow)
- **fix(orto): naprawione warstwy WMS Ortofotomapy** (wykryte przy weryfikacji)
  - `WMS_LAYERS`: `[2025..2018, Starsze]` (9) → `[2026, 2025, 2024, Starsze]` (4)
  - GUGiK skonsolidowal roczniki 2023..2018 w `SkorowidzeOrtofotomapyStarsze`;
    stara lista miala 6 nieistniejacych warstw i brak `2026` → twarde bledy WMS
- **feat(orto): walidacja warstw WMS przez GetCapabilities dla GugikOrtoProvider**
  - `_fetch_wms_layers()` + `_get_validated_layers()` (dotad orto bez fallbacku)
  - Wyklucza warianty `Zasiegi*`, lazy in-memory cache, graceful fallback
- **feat(laz): nowy produkt — chmury punktów LIDAR (LAZ) przez WFS**
  - `GugikLazProvider` — discovery przez WFS GetFeature (nie WMS jak NMT/orto;
    WMS dla LAZ jest 401-gated), `url_do_pobrania` wprost z atrybutu feature
  - Area-based: godło/`--bbox`/`--geometry` → bbox EPSG:2180 → `discover_tiles()`
  - Sidestep parsera: kafle LAZ drobniejsze niż 1:10000 (godło nieparsowalne),
    traktowane jako etykieta; `FileStorage.get_raw_path()` bez `SheetParser`
  - Newest-per-tile dedup, flagi `--year`/`--vertical-crs`/`--min-density`
  - CLI `--product laz`, pobieranie równoległe `--workers`
  - Oś EPSG:2180 dla WFS zweryfikowana live; E2E: realne pliki LAZ (magic `LASF`)
  - ADR-021
- **Dokumentacja:** CHANGELOG, PROGRESS, DECISIONS (ADR-021), CLAUDE.md, SCOPE, PRD
- **Wyniki testow:**
  - **1060 testow passed** (+53: +12 WMS layers, +41 LAZ provider/CLI/storage)
  - **Ruff: clean** (lint + format)

### Nastepne kroki
1. Mozaikowanie arkuszy NMT
2. Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
3. (opcjonalnie) LAZ: pasek postępu z rozmiarami, integracja MetadataCache dla WFS

## Backlog

- [x] Pokrycie testami do 80% (~84%, 990 testow)
- [x] NMPT provider (GugikNmptProvider)
- [x] Ortofotomapa provider (GugikOrtoProvider)
- [x] CLI --product {nmt,nmpt,orto}
- [x] PL-2000 godlowanie (Parser2000, auto-detekcja, CLI)
- [x] Weryfikacja BBox PL-2000 z realnymi danymi GUGiK (67 testow)
- [x] Pobieranie rownolegle (ThreadPoolExecutor, --workers)
- [x] Cache metadanych (SQLite WAL, TTL 7d, prune)
- [ ] Mozaikowanie arkuszy NMT
- [ ] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
