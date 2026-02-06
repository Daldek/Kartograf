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

**Data:** 2026-02-06

### Co zrobiono
- Testy: 369 testow przechodzi (pytest tests/ -v)
- Pobrano komplet danych dla N-34-130-D-d-2: NMT 1m, BDOT10k, CORINE, SoilGrids, HSG
- Diagnostyka braku NMT 5m: zbadano WMS GetFeatureInfo dla endpointu SheetsGrid5mEVRF2007
  - Potwierdzono: obszar N-34-130-D-d-2 nie ma pokrycia 5m w GUGiK (brak danych we wszystkich 4 warstwach)
  - Porownanie z Warszawa: ten sam endpoint dziala poprawnie — kod jest prawidlowy
- Poprawiono komunikat bledu w GugikProvider._get_opendata_url() (gugik.py:386-391)
  - Bylo: "No ASC file found for {godlo} in any WMS layer"
  - Jest: "No NMT {resolution} data available for {godlo} ... This area may not have {resolution} coverage in GUGiK"
- Zaktualizowano test (test_gugik_provider.py:479) pod nowy komunikat
- **feat(download): automatyczne rozwijanie godel do 1:10000 w `download_sheet()`**
  - `download_sheet()` w `DownloadManager` (manager.py:171-221): dla godel wyzszych niz 1:10000 deleguje do `download_hierarchy(godlo, "1:10000")`
  - Nowy parametr `on_progress`, zwracany typ `Path | list[Path]`
  - CLI `cmd_download()` (commands.py:537-550): obsluga wyniku list[Path], wyswietlanie liczby plikow
  - 4 nowe testy w test_download_manager.py (expands 25k/50k/100k, progress callback)
  - Zaktualizowano 2 istniejace testy CLI (on_progress w assert)
  - Testy: 369 testow przechodzi, ruff clean
- **Testy pobierania na zywym API GUGiK:**
  - NMT 1m: N-34-130-D-d-2 (Bialystok) — 4/4 arkusze, 144 MB, cellsize=1.00
  - NMT 5m: N-33-130-D-d-2 (Lodzkie) — 4/4 arkusze, 4.7 MB, cellsize=5.00 (warstwa SkorowidzeNMT2021iStarsze)
  - NMT 1m+5m: M-34-76-A-a-1 (Krakow) — oba 4/4
  - skip_existing dziala poprawnie (0.00s przy ponownym uruchomieniu)
  - CLI: progress bar + "Downloaded 4 files" — OK
- Pokrycie 5m w GUGiK jest niekompletne i rozni sie od 1m — to zachowanie serwisu, nie bug

### Nastepne kroki
1. Pokrycie testami do 80% (priorytet: auth/, providers/bdot10k.py, providers/corine.py)
2. Pobieranie rownolegle (v0.4+)

## Backlog

- [ ] Pokrycie testami do 80% (obecnie 57%)
- [ ] Pobieranie rownolegle (multi-threading)
- [ ] Cache metadanych (SQLite)
- [ ] Mozaikowanie arkuszy NMT
- [ ] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
