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
| Etap 0 — zrodla wielokrajowe (sources/transform/transport/providers-pl/CLI split/sidecar) | ✅ Gotowy | galaz feature/etap0-zrodla-wielokrajowe |

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

**Data:** 2026-08-10

### Co zrobiono
- **Research: rozszerzenie o zrodla wielokrajowe (CZ, DE, SK)** — wszystkie
  endpointy weryfikowane na zywo, nie z dokumentacji:
  - `docs/research/2026-08-10-czechy-dmr-zabaged.md` — CUZK: DMR 5G/4G, DMP,
    Ortofoto, ZABAGED (149 warstw); exportImage po bboxie z `imageSR=2180`;
    pliki openzu po przewidywalnych URL; SM5 nieobliczalne (indeks
    KladyMapovychListu), siatka TM33 2x2 km obliczalna; Bpv=EPSG:8357
  - `docs/research/2026-08-10-niemcy-dgm-atkis.md` — federacja 17 modeli;
    otwarty krajowy DGM1 nie istnieje (BKG paywall); BB/MV maja WCS, SN tylko
    kafle; basemap.de = krajowy Basis-DLM po bboxie; 25833→2180 acc 0,0;
    KRON86 dla DE niewykonalne (geoida PL maskowana → inf); ballpark przy
    braku sieci cicho zwraca identycznosc
  - `docs/research/2026-08-10-slowacja-dmr-zbgis.md` — DMR 5.0 1 m (100% SR);
    **WCS zwraca h elipsoidalne, pliki Bpv — roznica 42 m** → CRS pionowy musi
    byc per kanal; JTSK03=8353 vs 5514 (0,2-1,5 m); brak plikow per arkusz;
    ZBGIS przez ArcGIS REST (limit 1000, WAF blokuje `where=`)
- **Decyzje kierunkowe (zatwierdzone przez uzytkownika):**
  - pelna parytetowosc produktowa dla CZ; etapy: 0 refaktor → 1 fundament+DMR
    → 2 DMP/Orto/LAZ → 3 ZABAGED; DE/SK pozniej
  - dane zagraniczne domyslnie natywnie (S-JTSK/Bpv), transformacja opcjonalna
    przez reprojekcje serwerowa; KRON86 dla zagranicy = odmowa z remedium
  - `--country auto` (bbox ∩ extenty, osobne pliki per kraj); scalania brak —
    zadanie Hydrografa → sidecar metadanych obowiazkowy
  - indeks SM5 live z KladyMapovychListu + MetadataCache
  - bez nazw modulow sugerujacych ESRI (client.py, nie arcgis.py)
  - providers/pl **bez shimow zgodnosciowych** — Hydrograf/Hydrolog dostosuja
    importy (BREAKING w CHANGELOG; publiczne `from kartograf import ...` stabilne)
- **Spec etapu 0:** `docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md`
  — deskryptory zrodel + rejestr, sidecar `.meta.json`, `transform/crs.py`
  (twarda polityka: ballpark ban, probe na inf, filtr dokladnosci),
  `transport/http+mosaic`, rejestr parserow godel, unifikacja ABC,
  `providers/pl/` (bez shimow), podzial CLI; zachowanie bez zmian poza
  sidecarem i sciezkami importow providerow
- **Stan repo:** galaz `develop`, working tree czysty, commity niewypchniete:
  `1bbaf51` (research CZ), `91631a3` (research DE+SK), `9bbb6c1` (spec etapu 0)
  + aktualizacja PROGRESS

- **Plan implementacji etapu 0 (sesja 2, agent planujacy):**
  `docs/superpowers/plans/2026-08-10-etap0-zrodla-wielokrajowe.md` — 16 zadan
  (0-15) w TDD, kazde z krokami test-fail-implement-pass-commit; oparte na
  rekonesansie kodu (9 rownoleglych agentow: sygnatury, patch-targety testow,
  inwentarz CLI, pomiar API pyproj/rasterio w .venv). Kluczowe decyzje planu
  doprecyzowujace spec: filtr accuracy `< 0` zamiast `<= 0` (pyproj: -1 =
  nieznana, 0.0 = dokladna — inaczej test 25833→2180 ze specu niespelnialny);
  mechaniczna aktualizacja patch-targetow CLI po podziale commands.py; mypy
  wzgledem baseline (nie byl zainstalowany); wersja pakietu zostaje 0.6.1 do
  wydania (testy ja asertuja); regula 5m⇒EVRF2007 zostaje TAKZE w
  DownloadManager (testy) oprocz nowej fabryki
- **Implementacja etapu 0 (sesja 3, subagent-driven, galaz
  `feature/etap0-zrodla-wielokrajowe`)** — 15 commitow, `63ac66c`..`ad3fb8f`,
  zadania 1-13 kodowe + zadanie 14 (ta aktualizacja dokumentacji):
  `sources/` (descriptor, registry, sidecar), `transform/crs.py` (twarda
  polityka transformacji), `transport/` (http, mosaic), `core/parser_registry.py`
  (+ delegacje SheetParser/FileStorage), `FileStorage(subdir=...)`, unifikacja
  ABC w `providers/base.py` (DataSourceProvider, `download_by_admin_unit` +
  aliasy teryt), przenosiny `providers/gugik*`/`bdot10k.py` → `providers/pl/`
  bez shimow, fabryka `create_nmt_provider()`, sidecar `.meta.json` spiety w
  managerach i CLI LAZ, podzial `cli/commands.py` na 6 modulow per komenda +
  fasada zgodnosci. **1137 testow zielonych** (bez zmiany asercji istniejacych),
  pokrycie ~88%. Jedyna zmiana obserwowalna z zewnatrz: sidecar `.meta.json`
  po kazdym udanym pobraniu; publiczne `from kartograf import ...` bez zmian,
  BREAKING tylko dla glebokich importow providerow (ADR-022, CHANGELOG)

### Nastepne kroki
1. **Review + merge do develop** — galaz `feature/etap0-zrodla-wielokrajowe`
   gotowa (zadanie 15: koncowa weryfikacja/review), po akceptacji merge do
   `develop`
2. **Spec + plan etapu 1** (fundament CZ + DMR) — po zamknieciu etapu 0
3. Odziedziczone: (do weryfikacji) zgodnosc `get_bbox` z godlowaniem kafli LAZ
   (patrz [[gugik-laz-wfs]])

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
