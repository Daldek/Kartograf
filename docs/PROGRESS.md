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
| Pokrycie testami | ✅ Gotowy | 93%, 1716 testow (galaz fix/release-0.7.0-audit po fali naprawczej F-1..F-7, 2026-08-23) |
| Migracja na ruff | ✅ Gotowy | config + auto-fix, sesja 2026-02-03 |
| Pobieranie rownolegle | ✅ Gotowy | ThreadPoolExecutor, --workers, v0.6.0 |
| Cache metadanych (SQLite) | ✅ Gotowy | MetadataCache, WAL, TTL 7d, v0.6.0 |
| Weryfikacja BBox PL-2000 | ✅ Gotowy | 67 testow, reference values + live WMS |
| Walidacja warstw WMS | ✅ Gotowy | GetCapabilities, lazy, fallback; NMT+NMPT v0.6.1, Orto 2026-06-24 |
| Etap 0 — zrodla wielokrajowe (sources/transform/transport/providers-pl/CLI split/sidecar) | ✅ Gotowy | zmergowane do develop 2026-08-11; E2E 12/12 na realnych danych |
| Etap 1 — NMT Czechy (CUZK: DMR 5G/4G, --country/--target-crs/--vertical-crs) | ✅ Gotowy | ZMERGOWANY do develop 2026-08-12 (fast-forward do 0738ae0); 21 zadan TDD + fix ADR-024, E2E 11/11 + zywa weryfikacja tresci 3xPASS; wersja `0.7.0-dev` |

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

**Data:** 2026-08-10 — 2026-08-23 (sekcje datowane ponizej)

### Merge etapu 1 do develop (2026-08-12)
- `feature/etap1-cz-dmr` zmergowana do `develop` fast-forwardem do `0738ae0`
  (34 commity od 7e9c039); suita na zmergowanym develop: **1402 passed**;
  galaz feature usunieta (rekord = git + ten dokument + ADR-023/024).
- develop nadal NIE wypchniety na origin (71 commitow lokalnie: research +
  spec/plan etapow + etapy 0+1; wczesniejsze "67" bylo blednym sumowaniem).

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
    (pierwotnie: przez reprojekcje serwerowa — **zmienione na lokalna**,
    ADR-024, patrz sekcja "Fix po etapie 1"); KRON86 dla zagranicy = odmowa
    z remedium
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
(+239 wzgledem stanu po mergu etapu 0: 1142), pokrycie ~89%, ruff + ruff format
czyste, mypy bez nowego dlugu wzgledem baseline (33/34 przedistniejacych
bledow, niezwiazanych z etapem 1).

Model tieringu (feedback usera "team-driven-development"): sonnet dla
zadan z gotowym kodem w planie + reviewery per-task; opus dla zadan z
integracja wieloplikowa/diagnoza bugow; fable dla finalnego review calej
galezi. **Pelny ledger kontrolera** (wszystkie rulingi K1-K9/R1-R9,
~140 minor findings odroczonych per zadanie, kontekst przekazywany miedzy
zadaniami): `.superpowers/sdd/2026-08-11-etap1-cz-fundament-dmr/progress.md`.
**UWAGA (2026-08-18): ledger utracony** — katalog `.superpowers/sdd/` jest
poza gitem, na dysku zostaly tylko dwa diffy review; z listy ~140 minorow
przetrwaly wylacznie pozycje cytowane w tym dokumencie i w ADR-023.

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
potwierdza realne przeciecie granicy); `--target-crs EPSG:2180` (wowczas
reprojekcja serwerowa, 0 pikseli nodata w wyniku — pozniej okazalo sie, ze
tresc byla przesunieta o 135 m, patrz "Fix po etapie 1"); `--vertical-crs EVRF2007` (offset
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

### Fix po etapie 1: reprojekcja CZ lokalnie zamiast serwerowo (2026-08-11)

**Zgloszenie:** analiza szwu PL/CZ na Olzie wykryla, ze `--target-crs
EPSG:2180` dla CZ zwraca raster przesuniety o **135 m**. Winna reprojekcja
serwerowa CUZK (`exportImage&imageSR=2180` bez transformacji datum
S-JTSK→ETRS89); nasza kontrola przypietych operacji obejmowala tylko
OBWIEDNIE zadania (zgodna do 0,07 m), a tresc pikseli szla obok niej.

**Diagnoza zakresu (na zywo, `758_5514`/`760_5514` kolo Cieszyna;
dopasowanie przez minimum RMS wzgledem danych natywnych 5514
zreprojektowanych lokalnie):**

| sciezka | minimum RMS | przesuniecie tresci |
|---|---|---|
| `imageSR=2180` (`--target-crs`) | 0,041 m przy (−119,0; −64,5) | **135 m** (= ballpark wg pyproj: dE 118,8 / dN 64,4) |
| `imageSR=3045` (godlo TM33) | 0,034 m przy (0; +1,25) | **1,25 m** na poludnie (2 niezalezne kafle) |
| kontrola: natywny vs natywny | 0,045 m przy (0; 0) | 0 |

Czyli 3045 **nie** ma bledu datum (serwer go stosuje), ale ma wlasne,
niewyjasnione 1,25 m — 0,6 piksela DMR 5G.

**Naprawa (ADR-024, commit `6bf5e2b`):** serwer dostaje zadania rastrowe
wylacznie w ukladzie natywnym `EPSG:5514`; reprojekcje tresci robi lokalnie
`rasterio.warp.reproject` z **wymuszonym** pipeline'em przypietej operacji
(`PinnedTransform.gdal_operation()` → `COORDINATE_OPERATION`). Objete obie
sciezki: `--target-crs` i domyslna godlowa TM33. Kafelkowanie/mozaikowanie
zostaja po stronie natywnej (przed warpem). Sidecar: `transform.horizontal`
= `"pinned: <opis> (<acc> m)"` zamiast `"server:EPSG:<kod>"` (BREAKING),
takze dla kafla TM33 (dotad `transform: null`). Fail-fast operacji poziomej
w konstruktorze providera.

**Pulapka do zapamietania:** GDAL podaje operacji wspolrzedne w kolejnosci
osi **autorytatywnej**, a `PinnedTransform` powstaje z `always_xy=True` —
dla celu northing-first (2180, 3045) brak `step proj=axisswap order=2,1`
daje raster **w calosci nodata**, bez zadnego bledu. Sprawdzone i odrzucone
alternatywy: `to_wkt()` operacji (to samo — cale nodata) oraz dopasowanie
autorytatywnej wersji operacji po opisie w `TransformerGroup(always_xy=
False)` (opis rozni sie o "+ axis order change").

**Testy:** 1399 zielonych (+18), ruff/format czyste, mypy 33 (baseline).
Regresja tresci: syntetyczny "serwer" oddaje raster z wbudowanym
przesunieciem ballparku, a test sprawdza, gdzie **wyladowal wierzcholek**
(< 1 px od wzorca pyproj) — na starym kodzie failowal z bledem 134,5 m.

### Zywa weryfikacja fixu ADR-024 (2026-08-11)

Bugfix ADR-024 zweryfikowany **live 3xPASS** na danych CUZK+GUGiK, galaz
`feature/etap1-cz-dmr @ 2dd8dae` (commity `6bf5e2b`, `fd5c5b0`, `2dd8dae`
+ ten commit dokumentacyjny), metoda kontroli TRESCI (dopasowanie do
referencji natywnej 5514, minimum RMS w skanie przesuniec) — zamyka luke
odnotowana w E2E (punkty 1 i 4 sprawdzaly wtedy tylko bounds/CRS/res, nie
georeferencje pikseli). Wyniki: godlo TM33 (`302_5550`, EPSG:3045) —
RMS(0,0) = 0,016 m; bbox `--target-crs EPSG:2180` — RMS(0,0) = 0,031 m;
oba minima skanu dokladnie w (0,0). Szew z NMT PL (Olza): mediana
CZ−PL = −0,086 m, korelacja 0,998 (potwierdza diagnoze: −0,083 m).
Korekta liczby z ADR-024: dawny blad sciezki godlowej TM33 nie byl stala
1,25 m — pomiar na innym kaflu (E2E, zachodnie Czechy) dal 4,92 m; blad
serwerowej reprojekcji 5514→3045 byl zmienny przestrzennie. Pelny raport:
`docs/research/2026-08-11-etap1-e2e.md` (adnotacja) i ADR-024 w
`docs/DECISIONS.md`. Dwa nowe koszty lokalnego warpu odnotowane jako
backlog etapu 2 (patrz "Nastepne kroki" nizej): utrata rzadkiego/tiled
ukladu TIFF serwera przy zapisie, halo interpolatora bilinear ~1 px na
krawedzi waznosci.

### Przeglad spojnosci calej dokumentacji + uproszczenie README (2026-08-18)

Audyt aktualnosci i wewnetrznej spojnosci wszystkich .md (4 rownolegle agenty
read-only: README+CLAUDE.md vs kod; SCOPE/PRD/DEVELOPMENT_STANDARDS/
IMPLEMENTATION_PROMPT; PROGRESS/CHANGELOG/DECISIONS vs git; research+specy/
plany superpowers), nastepnie naprawa wszystkich znalezisk. Najwazniejsze:
- **README**: sekcja uzycia uproszczona (24 -> 16 przykladow CLI, sekcja
  Python skrocona) i zaktualizowana o LAZ/CZ/cache; naglowek, Funkcjonalnosci
  (nowe podsekcje NMT CZ i LAZ, orto 9->4 warstwy WMS), drzewo projektu,
  Status (0.5.0/835 -> 0.7.0-dev/1402), CLMS_CREDENTIALS jako alternatywa
  dla Keychain
- **CLAUDE.md**: fikcyjne zmienne CLMS_CLIENT_ID/SECRET -> faktyczna
  CLMS_CREDENTIALS (JSON, `corine.py`); workery CLI 4 vs biblioteka 1;
  timeout CUZK 60s
- **Liczby commitow skorygowane**: develop jest 71 commitow przed origin
  (nie "67"/"36+"); merge etapu 1 = 34 commity od 7e9c039 (nie 36);
  delta testow etapu 1 = +239 wzgledem 1142 (nie +244)
- **Artefakty sesyjne**: ledger kontrolera `.superpowers/sdd/.../progress.md`
  (lista ~140 minorow) UTRACONY bezpowrotnie (nigdy niecommitowany, brak
  kopii). `seam/verify/verify-report.md` poczatkowo uznany za utracony,
  ale tego samego dnia ODZYSKANY ze scratchpada sesji w /tmp (tmpfs —
  przepadlby przy restarcie): trzy raporty skopiowane do
  `docs/research/2026-08-11-adr024-{seam,bugfix,verify}-report.md`,
  a pelne dane przeniesione do korzenia repo — `seam/` (588M; analiza szwu,
  weryfikacja, `probe-gdal/` z diagnostyka pulapki osi GDAL) i `e2e-data/`
  (58M; m.in. CTES96.tif, kafle dmr5g); oba katalogi dodane do .gitignore
- **CHANGELOG**: 0.5.0 "849 testow" -> 835 (ADR-016 usunal 14 w tej samej
  wersji, +199 nie +213); Tests 0.7.0 -> 1402; wpis Added `--target-crs`
  "reprojekcja serwerowa" skorygowany na lokalna (ADR-024)
- **DECISIONS**: adnotacja przy ADR-023(c) (exportImage w 3045 zastapione
  przez ADR-024), separator ADR-023/024, oznaczenia niewersjonowanych zrodel
- **SCOPE 3.7**: status mergu, naglowek sekcji 2 (0.5.0->0.7.0), `cache` w
  CLI 2.9, brakujace eksporty w 2.10 (GugikLazProvider/LazTile/MetadataCache/
  DownloadResult), 1402 testy
- **PRD 3.5**: snapshot v0.6.1 bez wewnetrznych sprzecznosci (parallel/cache
  odhaczone, LAZ w §5+diagramie, "resumable downloads" -> skip-existing,
  coverage ~89%); zakres CZ celowo nieopisany do wydania 0.7.0 (nota)
- **DEVELOPMENT_STANDARDS 2.1**: mypy bez `--strict` + baseline 33; struktura
  7.1 odswiezona (30 plikow testowych, nie 15 z listy); przyklad
  landcover_base.py -> gugik_nmpt.py
- **IMPLEMENTATION_PROMPT 4.0**: usuniete twarde bledy (BDOT10k "WFS" ->
  OpenData ZIP, nieistniejaca `_init_providers()` -> slownik PROVIDERS,
  komendy CLI z `cache`, 5m OpenData = ASC), architektura i Public API
  aktualne, zniesione fikcyjne ograniczenia (parallel/cache/mozaika)
- **Erraty w dokumentach historycznych** (specy/plany etapow 0-1, research
  CZ/SK, rekonesans, stary spec WMS): reprojekcja serwerowa -> ADR-024,
  EVRF2007 9651 -> 5621 (ADR-023d), statusy "WYKONANY" na planach,
  domkniecie sekcji 12 specu etapu 1

### Audyt przedwydaniowy 0.7.0 (2026-08-22 — 2026-08-23)

**Faza A (audyt, 2026-08-22):** 9 rownoleglych agentow audytu (read-only,
cala baza kodu + docs) + 7 agentow weryfikacyjnych (kontrprobka ustalen na
zywym kodzie/testach) — wynik: **C=19 / I=59 / M=61** (Critical/Important/
Minor), **0 ustalen obalonych** (REFUTED) przy weryfikacji. Plan napraw:
`docs/superpowers/plans/2026-08-22-release-0.7.0-audit.md` — 26 zadan,
tabela "Ustalenie -> Zadanie" jest trwalym sladem, ktore ustalenie trafilo
do ktorego zadania albo zostalo swiadomie odlozone (ruling "odlozone":
A2-4, A2-7, A4-12, A5-3, A5-4, A5-5, A5-6, A5-7, A8-3, A8-4, A4-10 —
patrz nowa sekcja "Backlog po audycie 0.7.0" nizej).

**Faza B (naprawa, 2026-08-22 — 2026-08-23):** wykonanie 26 zadan (TDD,
subagent-driven) na galezi `fix/release-0.7.0-audit` (odgalezionej od
`develop` @ `f432403`, tej samej co merge etapu 1 wyzej) plus fala
naprawcza po finalnym review calej galezi (nizej) — **71 commitow na
moment zamkniecia fali** (stan koncowy galezi:
`git log --oneline f432403..HEAD`), w tym ta aktualizacja
`PROGRESS.md`. Rozklad wg typu Conventional Commits: 40 `fix`,
21 `docs`, 3 `test`, 2 `refactor`, 2 `feat`, 2 `chore`, 1 `perf`.

**Wynik na koniec fazy B (kanoniczny przebieg, po fali naprawczej
F-1..F-7):** `pytest tests/ --cov=kartograf --cov-report=term -q
-p no:cacheprovider -m "not live"` → **1716 testow** (1716 collected,
1708 passed + 8 deselected `live`), pokrycie **93%** (5366 stmts /
395 miss, 92,64% w mierze zaokraglonej), `ruff check` i
`ruff format --check` czyste, `mypy kartograf/` **32 bledy w 9 plikach**
(baseline byl 33 -> nowy baseline **32**, zero nowego dlugu). Przed fala
bylo 1708 testow (5349 stmts / 397 miss, 92,58%) — fala dolozyla 8 testow
(auth proxy: singleton, reap podprocesu, zamkniecie strumienia, polityka
tokena na `/download`).

**Finalny review calej galezi (fable, 2026-08-23, `f432403..f10388c`):**
werdykt "NEEDS ONE FIX WAVE" — 0 ustalen Critical, kontrakty
ADR-022/023/024 nienaruszone, Global Constraints (a)-(l) spelnione, suita
deterministyczna w 3 przebiegach (0 prob DNS). Jedna fala naprawcza
F-1..F-7 (5 commitow, 2026-08-23):
- **F-1** (kod) — domkniecie N4-1: `AuthProxyClient.__new__` pod lockiem,
  `_proxy_process`/`_stderr_thread` jako stan klasowy (dwa watki startowaly
  dwa podprocesy proxy), `wait()` po `kill()`, zamykanie strumienia
  `/download`.
- **F-2** (kod, ruling kontrolera zmieniajacy Decyzje 13 planu) — `/download`
  forwarduje host `https` spoza allowlisty BEZ naglowka `Authorization`
  zamiast konczyc 403: presigned `DownloadURL` z CLMS bywa na hoscie CDN, a
  403 blokowalo caly tor CORINE GeoTIFF (`http` nadal 403, `/proxy` bez
  zmian).
- **F-6** (kod) — neutralna tresc `Warning` auto-splitu (awaria zrodla nie
  jest juz opisywana jako "brak danych").
- **F-3/F-4/F-5** (docs) — timeouty w CLAUDE.md/SCOPE/IMPLEMENTATION_PROMPT
  zgodne z tabela DEVELOPMENT_STANDARDS 13.4, tabela sidecara w README
  (`horizontal_crs` z kaflem TM33/`--target-crs`, `transform` jako slownik
  osi), kwalifikator przy `auto -> pl`, WCS tylko KRON86, liczby (1708 ->
  1716 testow, przypis ADR-025 "22 punkty") i 3 docstringi testow
  `get_parent()`.
- **F-7** — ten wpis + backlog nizej.

Raport review i raport fali sa w `.superpowers/sdd/2026-08-22-release-0.7.0-audit/`
(katalog git-ignored, jak reszta materialow audytu).

Pelne raporty per-zadanie (implementer + kontroler, TDD Evidence: RED/GREEN,
self-review) sa w `.superpowers/sdd/2026-08-22-release-0.7.0-audit/` —
katalog **git-ignored, NIE w repo** (jak ledger etapu 1, patrz adnotacja
2026-08-18 wyzej — swiadoma decyzja tym razem, nie utrata). Trwaly slad w
repo: tabela "Ustalenie -> Zadanie" w planie, ten wpis w PROGRESS.md,
commity per zadanie i wpisy CHANGELOG/ADR dotkniete po drodze.

### Nastepne kroki
1. ~~Merge `feature/etap1-cz-dmr` do `develop`~~ — **WYKONANE 2026-08-12**
   (fast-forward do 0738ae0, suita 1402 passed na wyniku, galaz usunieta).
2. **Etap 2** (DMP/Orto/LAZ CZ + wielokat granicy administracyjnej zamiast
   prostokatnej obwiedni + ujednolicenie `extra.parent_request.bbox_crs`
   miedzy trybami jawny/auto) — spec/plan do napisania po decyzji o mergu;
   punkt wyjscia: ADR-023 (ustalenia dodatkowe 3-4) i `docs/SCOPE.md`
   (sekcje 2.2, 3.1, 3.2). Do backlogu etapu 2, z zywej weryfikacji
   ADR-024 (`seam/verify/verify-report.md`, Zastrzezenia 1-3 — raport
   odzyskany 2026-08-18: `docs/research/2026-08-11-adr024-verify-report.md`): (a)
   kompresja/`tiled=True` w profilu zapisu lokalnego warpu CZ (kafel
   brzegowy 93% nodata: 527 KB serwerowy → 4,0 MB lokalny, 7,6x); (b)
   maskowanie przed interpolacja bilinear na krawedzi waznosci (halo
   ~1 px, ~0,5% pikseli); (c) przestroga: blad serwerowej reprojekcji
   CUZK bywa zmienny przestrzennie (1,25 m kolo Cieszyna, 4,92 m w
   zachodnich Czechach) — nie zakladac stalego offsetu przy podobnych
   diagnozach w przyszlosci.
3. **Push `develop` na origin** (148 commitow lokalnie po mergu audytu
   0.7.0: 73 sprzed audytu — wczesniejsze "71" nie liczylo 2 doc-commitow
   z 2026-08-18 — plus 75 z galezi audytu; pomiar
   `git rev-list --count origin/develop..develop` 2026-08-28; decyzja
   z etapu 0 nadal nierozwiazana) — patrz wyzej
4. **Zgloszenie/naprawa WCS EVRF2007 GUGiK** (male, przedistniejace, poza
   etapami 0/1): aktualizacja `WCS_ENDPOINTS`/`COVERAGE_IDS` w
   `providers/pl/gugik.py` po usunieciu endpointu przez GUGiK (patrz "Znany
   problem uslugowy" wyzej); rozwazyc walidacje WCS analogiczna do
   walidacji warstw WMS
5. Odziedziczone: (do weryfikacji) zgodnosc `get_bbox` z godlowaniem kafli
   LAZ (patrz [[gugik-laz-wfs]])
6. **Minory odroczone z etapu 1** (nieblokujace; pelna lista ~140 pozycji
   byla w ledgerze kontrolera — plik utracony, patrz adnotacja przy sekcji
   implementacji etapu 1 wyzej; ponizsze wyliczenie to zachowany zapis
   najwazniejszych)
   — najwazniejsze do rozwazenia przy etapie 2: eager import `rasterio`
   przy `import kartograf` (+55-65 ms, ADR-023 pkt 2 — naprawa: lazy import
   w `providers/cuzk/client.py`/`dmr.py`); `Sm5Sheet.get_bbox` traci
   memoizacje `self._index` bez wstrzknietego indeksu (regresja wydajnosciowa
   przy wielu wywolaniach); duplikacja regul walidacji sentineli miedzy
   galezia PL i CZ w CLI; brak separatora przed "Remedium:" w komunikacie
   bledu KRON86
7. ~~Audyt przedwydaniowy 0.7.0 — finalny review calej galezi~~ —
   **WYKONANY 2026-08-23** (fable, werdykt "NEEDS ONE FIX WAVE" + fala
   F-1..F-7 zamknieta; patrz sekcja "Audyt przedwydaniowy 0.7.0" wyzej).
8. **Fala naprawcza minorow** z audytu — patrz nowa sekcja "Backlog po
   audycie 0.7.0" nizej.
9. ~~Merge `fix/release-0.7.0-audit` do `develop`~~ — **WYKONANY
   2026-08-28** (fast-forward `f432403..d327f0c`, 75 commitow; suita na
   zmergowanym develop: 1708 passed + 8 deselected `live`, pokrycie
   92,64%, ruff/format czyste, mypy 32 = baseline; galaz usunieta).
10. ~~Zadanie licencyjne uzytkownika~~ — **WYKONANE 2026-08-28**: `authors`
    w `pyproject.toml` = `Piotr de Bever <git@debever.pl>` (konwencja
    z IMGWTools); na decyzje uzytkownika licencja zmigrowana na wyrazenie
    SPDX wg PEP 639 (`license = "MIT"` + `license-files`, klasyfikator
    licencyjny usuniety, floor `setuptools>=77.0.3` bez `wheel`) —
    zweryfikowane buildem sdist+wheel: `Metadata-Version: 2.4`,
    `License-Expression: MIT`, LICENSE w `dist-info/licenses/`;
    szczegoly i konsekwencje w CHANGELOG [0.7.0] Changed.
11. **Bump wersji + wydanie 0.7.0**: `kartograf.__version__`/
    `pyproject.toml` `0.7.0-dev` -> `0.7.0`, data w CHANGELOG, tag
    `v0.7.0`, push `develop` na origin (patrz pkt 3 wyzej — 148 commitow
    niewypchnietych po zmergowaniu galezi audytu 0.7.0).
12. **Checklista release** (z planu audytu 0.7.0): build sdist/wheel
    (`setuptools`); zywa weryfikacja CORINE GeoTIFF z prawdziwymi
    credentials CLMS vs allowlista hostow (Auth Proxy); E2E kafelkowania
    `exportImage` przy wyniku >16 Mpx (sciezka chunkowana
    `mosaic_and_crop(dst_path=...)`) — nigdy nie uruchomione na zywo;
    3 przebiegi pelnej suity testow pod rzad (kontrola stabilnosci/flakow).

## Backlog

- [x] Pokrycie testami do 80% (~84%, 990 testow)
- [x] NMPT provider (GugikNmptProvider)
- [x] Ortofotomapa provider (GugikOrtoProvider)
- [x] CLI --product {nmt,nmpt,orto}
- [x] PL-2000 godlowanie (Parser2000, auto-detekcja, CLI)
- [x] Weryfikacja BBox PL-2000 z realnymi danymi GUGiK (67 testow)
- [x] Pobieranie rownolegle (ThreadPoolExecutor, --workers)
- [x] Cache metadanych (SQLite WAL, TTL 7d, prune)
- [ ] Mozaikowanie arkuszy NMT (PL; mechanizm `transport/mosaic.py` istnieje
      i skleja kafle CZ — brakuje spiecia dla arkuszy PL; scalanie
      transgraniczne PL/CZ pozostaje poza zakresem — zadanie Hydrografa)
- [x] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
      (etap 0: DataSourceProvider)
- [x] Etap 0 — architektura zrodel wielokrajowych (deskryptory, sidecar,
      transform/crs.py, transport/, providers/pl/, podzial CLI)
- [x] Etap 1 — NMT Czechy: CUZK DMR 5G/4G (`providers/cuzk/`, `ParserTM33`,
      `--country`/`--target-crs`/`--vertical-crs`) — zmergowany do develop
      2026-08-12 (fast-forward do 0738ae0, galaz feature usunieta)
- [ ] Etap 2 — DMP/Orto/LAZ CZ, wielokat granicy administracyjnej CZ
      (zamiast prostokatnej obwiedni), ujednolicenie
      `extra.parent_request.bbox_crs` miedzy trybami jawny/auto
- [ ] Etap 3 — ZABAGED (wektorowa baza topograficzna CZ, 149 warstw)

#### Backlog po audycie 0.7.0

Wpisy swiadomie odlozone rulingiem audytu przedwydaniowego 0.7.0
(2026-08-22/23, plan `docs/superpowers/plans/2026-08-22-release-0.7.0-audit.md`)
+ dodatkowe znaleziska zebrane przy review poszczegolnych zadan. Oznaczenia
`A<n>-<m>` odsylaja do tabeli "Ustalenie -> Zadanie" w planie (slad decyzji,
ktore ustalenie trafilo do ktorego zadania albo zostalo odlozone).

- [ ] A2-4 — rozjazd obslugi wyjatkow spoza `DownloadError` miedzy trybem
      sekwencyjnym a rownoleglym `DownloadManager.download_hierarchy`
      (sekwencyjny przerywa hierarchie, `last_result` wtedy `None`;
      rownolegly izoluje blad do pojedynczego zadania) — wymaga ADR o
      polityce wyjatkow; `OSError` (np. brak miejsca na dysku) POWINIEN
      przerywac oba tryby. Razem z tym: wynik `completed`/`skipped` bez
      sciezki (`path is None`) nie trafia do licznika (dzis nieosiagalne —
      `_download_single` zawsze oddaje sciezke) i zliczanie jest
      zduplikowane w dwoch petlach (sekwencyjnej i rownoleglej).
- [ ] A2-7 — fallback `urls[0]` w `_get_opendata_url` moze scache'owac URL
      innej warstwy niz zamierzona (Minor) — podniesc log do `warning`,
      rozwazyc weryfikacje zasiegu przy `FEATURE_COUNT>1`.
- [ ] A5-4 — regula "5m => EVRF2007" zaimplementowana w 3 miejscach
      (walidacja w `GugikProvider`, cicha korekta w `DownloadManager`,
      fabryka `create_nmt_provider`) — swiadome warstwowanie z etapu 0;
      sprzatanie razem z A5-5.
- [ ] A5-5 — hierarchia wyjatkow: providery PL rzucaja `ValueError`/
      `KeyError` zamiast `ValidationError` (37 miejsc w kodzie, 30 asercji
      `pytest.raises(ValueError)` w 11 plikach testowych, CHANGELOG
      dokumentuje `ValueError` jako kontrakt publiczny) — BREAKING, osobna
      zmiana z przejsciowym `class ValidationError(KartografError, ValueError)`.
- [ ] A5-7 — `GugikLazProvider.download(url, ...)` lamie LSP wzgledem
      `BaseProvider.download(godlo, ...)` (Minor — LAZ ma i tak osobny
      przeplyw CLI, omija ten kontrakt) — zmiana nazwy na `download_tile`
      razem z etapem 2 (LAZ CZ).
- [ ] A8-3 — testy toru CORINE GeoTIFF (CLMS/OAuth2): `_exchange_token`,
      `_download_via_clms_direct`, `_poll_clms_task` (happy + blad) — dlug
      sprzed 0.6.0, czesciowo pokryty e2e (zad. 9); `providers/corine.py`
      dzis 54% pokrycia (patrz DEVELOPMENT_STANDARDS 10.1) — M.
- [ ] A8-4 — testy `ProxyHandler.do_POST` (Bearer doklejony, 500 bez
      tokenu, 400 zly JSON, 404) — dlug sprzed 0.6.0, czesciowo pokryty
      e2e (zad. 9); `auth/proxy.py` jest juz >= 80% pokrycia calosciowo,
      ale sam handler HTTP pozostaje bez testow jednostkowych — M.
- [ ] A4-10 (reszta) — sekret wspoldzielony rodzic-dziecko (`X-Proxy-Auth`,
      uwierzytelnienie klienta wobec proxy) + SIGKILL-safe lifecycle
      podprocesu (dzis `atexit`) — zmiana protokolu + ADR. (Wyscig
      `__new__`/`_proxy_process` per-instancja i `kill()` bez `wait()`
      naprawione w fali F-1, 2026-08-23.)
- [ ] A5-3 — 6 providerow PL/EU ma wlasne kopie pobierania z retry zamiast
      wspolnego `transport.download_to` (spec etapu 0 sekcja 6.5 swiadomie
      odlozyl migracje); skutek uboczny przyszlej zmiany: backoff
      2s/4s -> 1s/2s.
- [ ] A5-6 — polityka zero-ballpark z `transform/crs.py` obowiazuje dzis
      tylko na sciezce CZ — 9 miejsc (w tym `core/geometry.py:_transform_bbox`,
      CRS z pliku uzytkownika) uzywa surowego `Transformer.from_crs`
      (mozliwy cichy ballpark dla obcych datow typu DHDN/Stereo70) — spec
      etapu 0 swiadomie odlozyl migracje na `build_pinned_transform`.
- [ ] A1-9 — rozdzielenie katalogow PL-2000 (`nmt_2000_<res>` wg ADR-017)
      odlozone — zmienilaby uklad katalogow istniejacych uzytkownikow
      (`skip_existing` polega na dzisiejszych sciezkach); dzis wspolny
      `nmt_2000_1m`.
- [ ] A1-8 — aliasy etykiet skal PL-1992 zgodne z nomenklatura GUGiK
      (1:5000 dla godla 7-czlonowego) — BREAKING, dopiero w nastepnej
      wersji major.
- [ ] Minor CLI (A3-8/A3-9/A3-11/A3-12/A3-13/A4-20, opcjonalne): ostrzezenie
      o mieszanych ukladach pionowych w auto-splicie; `parent_request` w
      sidecarach LAZ; CORINE WMS cap 4096 px bez korekty proporcji bboxa
      (lamie proporcje per os) — dodatkowo `width_px` liczone z bboxa
      ZRODLOWEGO, nie z obwiedni w EPSG:3857 (docelowo oba wymiary z
      obwiedni); `--scale`/`--resolution 5m` z godlem TM33 bez walidacji;
      `--product orto --resolution 5m` przechodzi cicho, a CLI wypisuje
      "(resolution: 5m)" (bez skutku dla danych — sidecar bierze
      rozdzielczosc z deskryptora); odwrocony bbox CZ.
- [ ] A8-7 / CI — egzekwowanie progow warstwowych pokrycia (core >= 80%,
      patrz DEVELOPMENT_STANDARDS 10.1) + pipeline CI (GitHub Actions)
      uruchamiajacy testy z `-m "not live"`.
- [ ] `_generate_output_path` w `LandCoverManager` nie roznicuje
      year/property/depth/format parametrow pobrania — ryzyko kolizji
      nazw plikow przy roznych parametrach tego samego zrodla/obszaru
      (pre-existing, poza rulingiem audytu, zebrane przy review).
- [ ] Deskryptor `pl.gugik.nmpt` nie deklaruje kanalu WCS mimo dzialajacego
      `GugikNmptProvider.download_bbox` — rozjazd deskryptor/provider, do
      wyrownania.
- [ ] `LandCoverManager` wola zdeprecjonowany alias `download_by_teryt`
      zamiast kanonicznego `download_by_admin_unit` — kosmetyka po A4-12
      (ktory jako niespojnosc funkcjonalna jest juz zamkniety, patrz
      raport zadania 26), ale nazwa wywolania w managerze wciaz wskazuje
      na alias, nie kanoniczna metode.
- [ ] `percent` w `get_hsg_statistics` liczony w pikselach, `area_ha`
      geodezyjnie — niespojne dla rastrow w ukladach geograficznych
      (rozny rozmiar piksela na siatce vs w metrach).
- [ ] Blokada sieci w `tests/conftest.py` nie obejmuje `socket.getaddrinfo`
      ani sieci PROJ (`pyproj.network`) — hartowanie izolacji offline
      (~10 linii w `conftest.py`, do zrobienia razem z A8-7/CI; dzis brak
      ekspozycji: zmierzone 0 prob DNS w calej suicie, siec PROJ domyslnie
      wylaczona).
- [ ] `TransformError` w petli krajow `_dispatch_area` konczy caly proces
      kodem 1 mimo czesciowego sukcesu (np. PL pobrane, CZ nie) — do
      etapu 2 (auto-split wielokrajowy).
- [ ] E2E kafelkowania `exportImage` (wynik >16 Mpx, sciezka chunkowana
      `mosaic_and_crop(dst_path=...)`) nigdy nie uruchomione na zywo — do
      checklisty release / etapu 2.
- [ ] `mosaic_and_crop(dst_path=...)` moze zostawic obciety plik wynikowy,
      gdy `merge` padnie w trakcie zapisu (brak `unlink` w obsludze bledu) —
      jedyne wywolanie produkcyjne (`export_image`) sprzata po sobie samo,
      wiec dotyczy to tylko bezposrednich konsumentow biblioteki.
- [ ] `core/geometry.py`: bajt kolejnosci WKB spoza `{0, 1}` nie jest
      walidowany — zamiast `None` (odrzucenie geometrii) daje smieciowe
      wspolrzedne z blednym rozpakowaniem struct.
