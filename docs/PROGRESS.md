# PROGRESS — Kartograf

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| NMT (parser + pobieranie) | ✅ Gotowy | v0.1.0+ |
| NMPT (Digital Surface Model) | ✅ Gotowy | v0.4.0 |
| Ortofotomapa | ✅ Gotowy | v0.4.0 |
| Land Cover (BDOT10k) | ✅ Gotowy | v0.3.0+ |
| Land Cover (CORINE) | ✅ Gotowy | v0.3.0+ |
| SoilGrids | ✅ Gotowy | v0.3.0+ |
| HSG | ✅ Gotowy | v0.3.0+ |
| bbox → godla | ✅ Gotowy | find_sheets_for_bbox(), CLI --bbox |
| CLI | ✅ Gotowy | 5 komend + --bbox + --product |
| Auth Proxy (CLMS) | ✅ Gotowy | v0.3.0+ |
| Pokrycie testami | ✅ Gotowy | 83.95%, 574 testy, cel 80% osiagniety |
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

## Ostatnia sesja

**Data:** 2026-02-07

### Co zrobiono
- **feat(providers): NMPT i Ortofotomapa — nowe produkty GUGiK**
  - `GugikNmptProvider` — dziedziczy z GugikProvider, nadpisuje endpointy NMPT/DSM
  - `GugikOrtoProvider` — osobna klasa, ortofoto Standard Resolution (25cm, TIF)
  - `FileStorage` — parametr `product` (nmpt, orto), podkatalogi `nmt_1m`/`nmt_5m`/`nmpt`/`orto`
  - `DownloadManager` — dynamiczne `_default_ext` z `provider.default_extension`
  - `BaseProvider` — nowa property `default_extension` (domyslnie `.asc`)
  - CLI `--product {nmt,nmpt,orto}` — wybor produktu w komendzie download
  - Public API: `GugikNmptProvider`, `GugikOrtoProvider` w `kartograf/__init__.py`
  - Nowy `tests/test_gugik_nmpt.py` — 21 testow
  - Nowy `tests/test_gugik_orto.py` — 25 testow
  - Rozszerzony `tests/test_cli.py` — +12 testow (product CLI)
  - Rozszerzony `tests/test_storage.py` — +8 testow (product storage)
  - Rozszerzony `tests/test_download_manager.py` — +3 testy (default_ext)
- **docs: aktualizacja SCOPE, PRD, DECISIONS, CHANGELOG, PROGRESS**
  - SCOPE.md v3.0 — dodane NMPT i Ortofoto do zakresu
  - PRD.md v3.0 — nowe features 3.2 (NMPT) i 3.3 (Ortofoto)
  - DECISIONS.md — ADR-011 (NMPT inheritance), ADR-012 (Orto separate class), ADR-013 (storage rename)
  - Wersja projektu: 0.3.2 → 0.4.0
- **Wyniki testow:**
  - **574 testow passed** (67 nowych)
  - **Pokrycie: 83.95%** (cel 80% osiagniety)
  - **Ruff: clean** (lint + format)
  - Pokrycie per-modul:
    - gugik_nmpt.py: 100%
    - gugik_orto.py: 94%
    - manager.py: 100%
    - storage.py: 93%
    - cli/commands.py: 90%
    - sheet_parser.py: 98%

### Nastepne kroki
1. Pobieranie rownolegle (v0.5+)
2. Cache metadanych (SQLite)

## Backlog

- [x] Pokrycie testami do 80% (83.95%, 574 testow)
- [x] NMPT provider (GugikNmptProvider)
- [x] Ortofotomapa provider (GugikOrtoProvider)
- [x] CLI --product {nmt,nmpt,orto}
- [ ] Pobieranie rownolegle (multi-threading)
- [ ] Cache metadanych (SQLite)
- [ ] Mozaikowanie arkuszy NMT
- [ ] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
