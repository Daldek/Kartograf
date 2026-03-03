# PROGRESS — Kartograf

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| NMT (parser + pobieranie) | ✅ Gotowy | v0.1.0+ |
| NMPT (Digital Surface Model) | ✅ Gotowy | v0.4.0 |
| Ortofotomapa | ✅ Gotowy | v0.4.0 |
| Land Cover (BDOT10k) | ✅ Gotowy | v0.3.0+, 15 warstw v0.5.0 |
| Land Cover (CORINE) | ✅ Gotowy | v0.3.0+ |
| SoilGrids | ✅ Gotowy | v0.3.0+ |
| HSG | ✅ Gotowy | v0.3.0+ |
| bbox → godla | ✅ Gotowy | find_sheets_for_bbox(), CLI --bbox |
| geometry → godla | ✅ Gotowy | find_sheets_for_geometry(), CLI --geometry |
| CLI | ✅ Gotowy | 5 komend + --bbox + --product + --system + --geometry |
| Auth Proxy (CLMS) | ✅ Gotowy | v0.3.0+ |
| PL-2000 (godlowanie) | ✅ Gotowy | Parser2000, auto-detekcja, CLI, storage |
| Pokrycie testami | ✅ Gotowy | ~84%, 990 testow, cel 80% osiagniety |
| Migracja na ruff | ✅ Gotowy | config + auto-fix, sesja 2026-02-03 |
| Pobieranie rownolegle | ✅ Gotowy | ThreadPoolExecutor, --workers, v0.6.0 |
| Cache metadanych (SQLite) | ✅ Gotowy | MetadataCache, WAL, TTL 7d, v0.6.0 |
| Weryfikacja BBox PL-2000 | ✅ Gotowy | 67 testow, reference values + live WMS |

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

## Ostatnia sesja

**Data:** 2026-03-03

### Co zrobiono
- **feat(download): parallel downloads with ThreadPoolExecutor**
  - `DownloadManager(max_workers=4)` — konfigurowalny thread pool
  - `DownloadResult` — structured results (succeeded/failed/skipped)
  - `LandCoverManager.download_batch()` — parallel batch download
  - CLI: `--workers`/`-w` na `kartograf download`
  - Thread-safe temp filenames we wszystkich providerach
- **feat(cache): MetadataCache z SQLite**
  - `kartograf/cache/metadata.py` — WAL mode, TTL 7 dni, thread-safe writes
  - URL cache dla GUGiK OpenData, TERYT cache dla BDOT10k
  - `prune_expired()` — automatyczne czyszczenie
  - CLI: `kartograf cache stats|clear|path`
  - Integracja z GugikProvider, GugikNmptProvider, GugikOrtoProvider, Bdot10kProvider
- **test(pl2000): PL-2000 BBox verification**
  - 67 nowych testow: reference values, hierarchy, live WMS, edge cases
  - `@pytest.mark.live` marker dla testow integracyjnych GUGiK WMS
- **Organizacja pracy:** 3 rownolegle zespoly subagentow na git worktrees
  - Spec compliance review + code quality review po kazdym zespole
  - Sekwencyjny merge: verification → cache → parallel
- **Wyniki testow:**
  - **990 testow passed** (+155 nowych)
  - **Ruff: clean** (lint + format)

### Nastepne kroki
1. Mozaikowanie arkuszy NMT
2. Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
3. Merge develop → main (v0.6.0 release)

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
