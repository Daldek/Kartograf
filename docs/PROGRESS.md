# PROGRESS — Kartograf

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| NMT (parser + pobieranie) | ✅ Gotowy | v0.1.0+ |
| Land Cover (BDOT10k) | ✅ Gotowy | v0.3.0+ |
| Land Cover (CORINE) | ✅ Gotowy | v0.3.0+ |
| SoilGrids | ✅ Gotowy | v0.3.0+ |
| HSG | ✅ Gotowy | v0.3.0+ |
| CLI | ✅ Gotowy | 5 komend |
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

**Data:** 2026-02-04

### Co zrobiono
- Migracja konfiguracji z black+flake8 na ruff (pyproject.toml)
- Usuniecie .flake8, dodanie .editorconfig
- Przepisanie CLAUDE.md (7 sekcji, ~148 linii)
- Przepisanie PROGRESS.md (4 sekcje, skondensowane z 785 linii)
- Aktualizacja README.md, CHANGELOG.md, PRD.md, SCOPE.md
- Rozbudowanie DEVELOPMENT_STANDARDS.md (722 linii, 15 sekcji wg shared/standards)
- Rozbudowanie IMPLEMENTATION_PROMPT.md (284 linii, 11 sekcji, aktualny kontekst v0.3.2)
- Utworzenie docs/DECISIONS.md — rejestr 9 decyzji architektonicznych (ADR)
- Auto-naprawa kodu przez `ruff check --fix` (63 poprawki: importy, type annotations)
- Reczna naprawa 8 bledow ruff (B904, SIM102, SIM117, E501)
- `ruff check` — 0 bledow, `pytest tests/ -v` — 365 testow przechodzi
- Wszystkie zmiany scommitowane

### Nastepne kroki
1. Pokrycie testami do 80% (priorytet: auth/, providers/bdot10k.py, providers/corine.py)
2. Pobieranie rownolegle (v0.4+)

## Backlog

- [ ] Pokrycie testami do 80% (obecnie 57%)
- [ ] Pobieranie rownolegle (multi-threading)
- [ ] Cache metadanych (SQLite)
- [ ] Mozaikowanie arkuszy NMT
- [ ] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
