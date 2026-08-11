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
| Pokrycie testami | ✅ Gotowy | ~89%, 1381 testow (po etapie 1, galaz feature/etap1-cz-dmr) |
| Migracja na ruff | ✅ Gotowy | config + auto-fix, sesja 2026-02-03 |
| Pobieranie rownolegle | ✅ Gotowy | ThreadPoolExecutor, --workers, v0.6.0 |
| Cache metadanych (SQLite) | ✅ Gotowy | MetadataCache, WAL, TTL 7d, v0.6.0 |
| Weryfikacja BBox PL-2000 | ✅ Gotowy | 67 testow, reference values + live WMS |
| Walidacja warstw WMS | ✅ Gotowy | GetCapabilities, lazy, fallback; NMT+NMPT v0.6.1, Orto 2026-06-24 |
| Etap 0 — zrodla wielokrajowe (sources/transform/transport/providers-pl/CLI split/sidecar) | ✅ Gotowy | zmergowane do develop 2026-08-11; E2E 12/12 na realnych danych |
| Etap 1 — NMT Czechy (CUZK: DMR 5G/4G, --country/--target-crs/--vertical-crs) | ✅ Gotowy | galaz `feature/etap1-cz-dmr` (niezmergowana do develop); 21 zadan TDD, E2E 11/11; wersja `0.7.0-dev` |

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

**Data:** 2026-08-10 — 2026-08-11 (sekcje datowane ponizej; najnowsza:
"Dokumentacja etapu 1 (2026-08-11, Zad. 21)")

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

### Weryfikacja E2E na realnych danych (2026-08-11)

12 kombinacji na zywych uslugach — wszystkie z poprawnym sidecar-em
`.meta.json` (dataset/CRS-y/nodata/request): NMT 1m EVRF2007 (37M), NMT 1m
KRON86 (37M, vcrs=EPSG:9650), NMT 5m (1,5M), NMPT (37M), PL-2000 6.179.12.20
(43M), skip-existing (sidecar nienadpisywany), Orto (287M), LAZ bbox
(3 kafle = 3 sidecary, 147M najwiekszy), BDOT10k teryt 1465 (317M GPKG),
CORINE fallback PNG bez credentials (**hcrs=EPSG:3857 + fallback=wms_png** —
poprawka z final review potwierdzona na zywo), SoilGrids (EPSG:4326),
WCS bbox 1x1 km KRON86 (3,9M GeoTIFF).

**Znany problem uslugowy (poza zakresem etapu 0, kod WCS bajt-w-bajt
niezmieniony):** GUGiK usunal endpoint WCS NMT EVRF2007
(`.../WCS/DigitalTerrainModelFormatTIFFEVRF2007` → HTTP 404 na poziomie
Apache, takze GetCapabilities); endpoint KRON86 dziala i serwuje wylacznie
`DTM_PL-KRON86-NH_TIFF`. Skutek: `download_bbox` NMT 1m dziala dzis tylko
z `vertical_crs="KRON86"`. Do osobnego zgloszenia: aktualizacja
`WCS_ENDPOINTS`/`COVERAGE_IDS` w `providers/pl/gugik.py` + rozwazenie
walidacji WCS analogicznej do walidacji warstw WMS.

### Merge (2026-08-11)

Etap 0 **zmergowany do `develop`** (fast-forward, HEAD `35ddd56`); pelny
pytest na zmergowanym develop: **1142 passed**, ruff czysty. Galaz
`feature/etap0-zrodla-wielokrajowe` usunieta po merge'u. `develop` jest
lokalnie **31 commitow przed `origin/develop`** (research CZ/DE/SK + spec +
plan + etap 0) — push do decyzji uzytkownika.

### Spec etapu 1 — fundament CZ + DMR (2026-08-11)

`docs/superpowers/specs/2026-08-11-etap1-cz-fundament-dmr-design.md` — status:
**ZAAKCEPTOWANY 2026-08-11** (review uzytkownika; w ramach review dodano
`extra.parent_request`). Zakres: `providers/cuzk/` (CuzkClient — pierwszy silnik
sterowany deskryptorem: exportImage z kafelkowaniem, query z paginacja, pliki
openzu; SheetIndex + tabela `sheet_cache` w MetadataCache; CuzkDmrProvider),
`core/parser_tm33.py` + rejestracja `cz_tm33`/`cz_sm5` w parser_registry
(PRZED fallbackiem pl1992), deskryptory `cz.cuzk.dmr5g`/`cz.cuzk.dmr4g` +
pole `endpoint` w AccessChannel, CLI `--country {pl,cz,auto}` + `--target-crs`
+ `2m`/`Bpv`, sidecary CZ z `transform`/`extra` (PODIL;
`extra.parent_request` grupujacy pliki jednego zadania `--country auto` —
fundament pod przyszle scalanie). Elementy odroczone
z etapu 0 wchodza: jawna selekcja kanalu (`build_metadata(capability=...)`),
probe pod polityka sieci.

Kluczowe decyzje sesji:
- **EVRF2007 globalnie = EPSG:5621** (decyzja uzytkownika): `vertical_crs_code`
  zmienia mapowanie (BREAKING dla tej funkcji), nowa nazwa `EVRF2007-PL` →
  9651, `Bpv` → 8357; mapa rodzina→realizacja sprawia, ze sidecary PL dalej
  niosa faktyczny kod 9651
- przeplyw CZ omija DownloadManager (precedens LAZ) — API managera nietkniete
- TM33 w trybie godlowym pobierany w EPSG:3045 (kafel zdefiniowany w 3045);
  tryb bbox natywnie 5514; asymetria bbox PL (arkusze) vs CZ (wycinek
  serwerowy) jawnie udokumentowana
- domyslne `--resolution`/`--vertical-crs` przez sentinel `None` rozwiazywany
  per kraj (PL: 1m/EVRF2007 bez zmian; CZ: 2m/Bpv)
- sekcja 12 specu: 5 faktow do potwierdzenia live PRZED implementacja
  (parametry query warstw 24/26, `noData` w exportImage, exportImage dmr4g,
  HTTP openzu, bboxSR/imageSR=3045)

### Plan implementacji etapu 1 (2026-08-11)

`docs/superpowers/plans/2026-08-11-etap1-cz-fundament-dmr.md` — **21 zadan
TDD** (kazde: test-fail-implement-pass-commit), napisany wg
superpowers:writing-plans na bazie zaakceptowanego specu + rekonesansu kodu
(inwentaryzacja testow do zmiany, sygnatury istniejacych helperow). Struktura:
zad. 1 rekonesans live (sekcja 12 specu + semantyka pyproj 8357→5621, fixtury
do `tests/fixtures/cuzk/`); zad. 2-4 rejestr pionowy (BREAKING
`vertical_crs_code`, nowa publiczna `resolve_vertical_crs`) + deskryptory CZ
(+`all_countries()`) + `build_metadata(capability=, nodata=)`; zad. 5
`transform/crs.py`; zad. 6 `ParserTM33`; zad. 7 `sheet_cache`; zad. 8-9
`CuzkClient`; zad. 10 `SheetIndex`/`Sm5Sheet`; zad. 11 rejestracja systemow;
zad. 12 `CuzkDmrProvider`; zad. 13 `DownloadManager(sidecar_extra=)`;
zad. 14-17 CLI (dyspozycja per kraj, `_cmd_download_cz`, auto-split,
`parent_request`); zad. 18 eksporty + wersja `0.7.0-dev`; zad. 19 brama
jakosci; zad. 20 E2E live (macierz akceptacyjna 11.3-11.4); zad. 21
dokumentacja (ADR-023).

**Decyzje uzytkownika z konsultacji przy planie (wiazace, sekcja
"Rozstrzygniecia z konsultacji" planu):**
- `extra.parent_request` pisany **zawsze w trybie bbox/geometry** (auto
  I jawny `--country`; nigdy w godlowym) — umozliwia dwuetapowe dociaganie
  drugiego kraju dla tego samego bboxa (klucz grupowania: identyczny
  bbox+crs); koryguje "sidecary PL bez zmian tresci" ze specu (addytywnie)
- `--target-crs` + godlo CZ → **ValidationError** (reprojekcja serwerowa
  tylko w trybie --bbox/--geometry; spojne z decyzja 13.2 specu)
- `PinnedTransform.transform` **polimorficzne** (skalary lub tablice numpy,
  `np.isfinite`) — zamiast osobnej metody; korekta notki "bez zmian API"

Rozstrzygniecia techniczne planu (sekcja "Rozstrzygniecia techniczne"):
`--system` tez sentinel `None`; kafelkowanie exportImage wymaga
`bbox.crs == image_sr` (provider normalizuje bbox wczesniej); przycinanie
bboxa do extentu kraju tylko w auto; `tests/test_cache.py` ze specu =
`tests/test_metadata_cache.py`.

### Implementacja etapu 1 (2026-08-11, subagent-driven, galaz `feature/etap1-cz-dmr`)

27 commitow, `7e9c039`..`c693530`, zadania 1-20 (kod + rekonesans + E2E) +
zadanie 21 (ta aktualizacja dokumentacji): `providers/cuzk/` (`CuzkClient` —
pierwszy silnik sterowany deskryptorem: `query()` z paginacja i filtrem
nadmiarowego wyboru po stronie klienta, `export_image()` z kafelkowaniem
15000x4100 px + nadpisaniem CRS, `fetch_file()` z ZIP openzu; `SheetIndex`/
`SheetInfo`/`Sm5Sheet`; `CuzkDmrProvider` + `create_dmr_provider`),
`core/parser_tm33.py` (`ParserTM33`, siatka TM33 2x2 km EPSG:3045) +
rejestracja `cz_tm33`/`cz_sm5` w `parser_registry` (przed fallbackiem
pl1992), `sources/registry.py` (deskryptory `cz.cuzk.dmr5g`/`dmr4g`,
`CountryProfile` CZ, `all_countries()`, BREAKING `vertical_crs_code`
EVRF2007→5621 + nowa `resolve_vertical_crs` rodzina→realizacja),
`cache/metadata.py` (+`sheet_cache`, TTL 30d), `sources/sidecar.py`
(`build_metadata(capability=, nodata=)`), `download/manager.py`
(`sidecar_extra=`), CLI (`--country {pl,cz,auto}`, `--target-crs`, sentinele
`resolution`/`vertical-crs`/`system` per kraj, `_cmd_download_cz`,
auto-split bbox/geometrii transgranicznej, `extra.parent_request`),
eksporty publiczne + wersja `0.7.0-dev`. **1381 testow zielonych**
(+244 wzgledem stanu po etapie 0/1142), pokrycie ~89%, ruff + ruff format
czyste, mypy bez nowego dlugu wzgledem baseline (33/34 przedistniejacych
bledow, niezwiazanych z etapem 1).

Model tieringu (feedback usera "team-driven-development"): sonnet dla
zadan z gotowym kodem w planie + reviewery per-task; opus dla zadan z
integracja wieloplikowa/diagnoza bugow; fable dla finalnego review calej
galezi. **Pelny ledger kontrolera** (wszystkie rulingi K1-K9/R1-R9,
~140 minor findings odroczonych per zadanie, kontekst przekazywany miedzy
zadaniami): `.superpowers/sdd/2026-08-11-etap1-cz-fundament-dmr/progress.md`.

**Odstepstwa proceduralne od planu** (za zgoda uzytkownika, precedens
rulingow kontrolera K2-K4 "popraw wg intencji planu"):
- **Zad. 11:** `tests/test_storage.py:189-192` zmieniony POZA zamknieta
  liste planu — stara asercja byla artefaktem fallbacku pl1992 na
  placeholderze; wlasna fixtura planu (Zad. 15, l. 3232) oczekuje
  dokladnie nowej zagniezdzonej sciezki `cz_dmr5g/302/5550/302_5550.tif`.
  Uznane za pominiecie na liscie planu, nie scope creep.
- **Zad. 17:** bboxy w 7 testach SPOZA zamknietej listy planu podmienione —
  lezaly W CALOSCI w obwiedni CZ (blad zalozenia bboxow przyjetych w planie,
  nie danych zrodlowych); zmienione wylacznie literaly bboxa, zero zmian
  asercji/mockow (zweryfikowane niezaleznie przez recenzenta).
- **Zad. 20:** bbox Kroku 3 macierzy E2E podmieniony na Cieszyn — oryginalny
  bbox z briefu rozwijal sie na 24 arkusze PL bez pokrycia NMT 1m EVRF2007
  (`DownloadError` potwierdzony w zrodle, nie blad kodu); pelna diagnostyka
  doboru bboxa w `docs/research/2026-08-11-etap1-e2e.md`.

### E2E etapu 1 na zywych danych CUZK (2026-08-11)

`docs/research/2026-08-11-etap1-e2e.md` — **11/11 PASS** (6 punktow macierzy
akceptacyjnej ze specu + 5 dodatkowych, zero FAILi). Godlo TM33 `302_5550`
(dmr5g, Bpv natywnie, `--country cz`); godlo SM5 `CTES96` (dmr4g, kraj
auto-wykryty z godla, `podil=0.99`, diakrytyki UTF-8 `Český Těšín`
zachowane); bbox przygraniczny Cieszyn `--country auto` (osobne pliki
PL/CZ, wspolny `parent_request`, zero scalania — 67,2% nodata po stronie CZ
potwierdza realne przeciecie granicy); `--target-crs EPSG:2180` (reprojekcja
serwerowa, 0 pikseli nodata w wyniku); `--vertical-crs EVRF2007` (offset
Bpv→EVRF2007 zmierzony na zywo **+0,132366 m** na 64722 pikselach, std
2,22e-05 — zgodny z modelem z rekonesansu co do ~1 mm, domyka Amendment 4
z Zad. 12); `--vertical-crs KRON86` (blad z czytelnym remedium); regresja
PL bez zmian (godlo, `landcover list-sources`, `cache stats`). Odstepstwo:
bbox Kroku 3 (patrz wyzej). Obserwacje nieblokujace zebrane dla Zad. 21:
semantyka `vertical_source="native"` mimo transformacji (rozstrzygniete w
ADR-023 pkt 1), skladnia `--bbox=...` dla ujemnych wspolrzednych Krovaka
(dodana do przykladow CLAUDE.md), brak separatora przed "Remedium:" w
komunikacie KRON86 (kosmetyka, odroczona), `cache stats` `URL=0` dla PL
(stan sprzed etapu 1, cache nie jest wpiety w providery z poziomu CLI).

### Dokumentacja etapu 1 (2026-08-11, Zad. 21)

ADR-023 (`docs/DECISIONS.md`) — silnik CUZK, polityka ukladow CZ,
EVRF2007→5621, plus 4 ustalenia dodatkowe (semantyka `transform.horizontal`,
eager import `rasterio`, `parent_request.countries`=probowane/`bbox_crs`
per-tryb, prostokatne extenty krajow). CHANGELOG 0.7.0 uporzadkowany:
`### Breaking Changes` przeniesiony na gore sekcji (dwa wpisy: glebokie
sciezki importu + `vertical_crs_code`, oba z tabelkami), `### Added`
rozszerzone o `sheet_cache`/`capability=`/`nodata=`/`sidecar_extra`/
`endpoint`, `### Changed` o sentinele CLI/polimorficzny `transform`/probe
pod polityka sieci/`parent_request` w sidecarach PL. CLAUDE.md — nowe
moduly (`core/parser_tm33.py`, `providers/cuzk/`), przyklady CLI CZ
(w tym skladnia `--bbox=` dla Krovaka), sekcja ograniczen rozszerzona.
SCOPE.md — zakres CZ jako nowa sekcja 2.2 (etap 1 in-scope, etap 2/3
future), known limitations CZ w 3.2, **pelne odswiezone drzewo modulow**
(zaleglosc z etapu 0 domknieta — SCOPE nie bylo aktualizowane od 0.6.1),
liczby testow/pokrycia zsynchronizowane (1381/89%).

**Rozstrzygniecie `pyproject.toml`:** `version = "0.6.1"` **pozostaje bez
zmian** (NIE bumpowane do `0.7.0-dev`). Zbadana konwencja repo
(`git log -p -- pyproject.toml`): `pyproject.toml` jest bumpowany leniwie,
zwykle w tym samym commicie co finalizacja wydania — bump 0.5.0→0.6.1
przeskoczyl 0.6.0 w jednym commicie (`4f6a33d`), mimo ze `__init__.py` mial
`0.6.0` przez caly czas trwania tamtych prac. `pyproject.toml` NIE sledzi
kazdego przyrostu `kartograf.__version__` (ktory bywa bumpowany na starcie
prac, czasem z sufiksem `-dev`, jak teraz). Zaden test nie asertuje
wartosci z `pyproject.toml` (tylko `kartograf.__version__`, sprawdzone
`grep -rn "__version__" tests/`). Precedens z etapu 0 (ten sam projekt):
"wersja pakietu zostaje 0.6.1 do wydania". Etap 1 jeszcze nie jest
wydaniem (galaz `feature/etap1-cz-dmr` niezmergowana do `develop`, brak
tagu `v0.7.0`) — `0.6.1` zostaje az do faktycznego mergu/wydania.

### Nastepne kroki
1. **Decyzja uzytkownika: merge `feature/etap1-cz-dmr` do `develop`** —
   galaz jest zielona (1381 testow, ruff/mypy czyste), E2E 11/11 PASS,
   dokumentacja kompletna (ten wpis). Wymaga: superpowers:finishing-a-
   -development-branch albo recznego przegladu.
2. **Etap 2** (DMP/Orto/LAZ CZ + wielokat granicy administracyjnej zamiast
   prostokatnej obwiedni + ujednolicenie `extra.parent_request.bbox_crs`
   miedzy trybami jawny/auto) — spec/plan do napisania po decyzji o mergu;
   punkt wyjscia: ADR-023 (ustalenia dodatkowe 3-4) i `docs/SCOPE.md`
   (sekcje 2.2, 3.1, 3.2)
3. **Push `develop` na origin** (36+ commitow lokalnie, decyzja z etapu 0
   nadal nierozwiazana) — patrz wyzej
4. **Zgloszenie/naprawa WCS EVRF2007 GUGiK** (male, przedistniejace, poza
   etapami 0/1): aktualizacja `WCS_ENDPOINTS`/`COVERAGE_IDS` w
   `providers/pl/gugik.py` po usunieciu endpointu przez GUGiK (patrz "Znany
   problem uslugowy" wyzej); rozwazyc walidacje WCS analogiczna do
   walidacji warstw WMS
5. Odziedziczone: (do weryfikacji) zgodnosc `get_bbox` z godlowaniem kafli
   LAZ (patrz [[gugik-laz-wfs]])
6. **Minory odroczone z etapu 1** (nieblokujace; pelna lista ~140 pozycji
   w ledgerze kontrolera, `.superpowers/sdd/2026-08-11-etap1-cz-fundament-dmr/progress.md`)
   — najwazniejsze do rozwazenia przy etapie 2: eager import `rasterio`
   przy `import kartograf` (+55-65 ms, ADR-023 pkt 2 — naprawa: lazy import
   w `providers/cuzk/client.py`/`dmr.py`); `Sm5Sheet.get_bbox` traci
   memoizacje `self._index` bez wstrzknietego indeksu (regresja wydajnosciowa
   przy wielu wywolaniach); duplikacja regul walidacji sentineli miedzy
   galezia PL i CZ w CLI; brak separatora przed "Remedium:" w komunikacie
   bledu KRON86

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
- [x] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
      (etap 0: DataSourceProvider)
- [x] Etap 0 — architektura zrodel wielokrajowych (deskryptory, sidecar,
      transform/crs.py, transport/, providers/pl/, podzial CLI)
- [x] Etap 1 — NMT Czechy: CUZK DMR 5G/4G (`providers/cuzk/`, `ParserTM33`,
      `--country`/`--target-crs`/`--vertical-crs`), galaz `feature/etap1-cz-dmr`
      (merge do develop: decyzja uzytkownika, patrz "Nastepne kroki")
- [ ] Etap 2 — DMP/Orto/LAZ CZ, wielokat granicy administracyjnej CZ
      (zamiast prostokatnej obwiedni), ujednolicenie
      `extra.parent_request.bbox_crs` miedzy trybami jawny/auto
- [ ] Etap 3 — ZABAGED (wektorowa baza topograficzna CZ, 149 warstw)
