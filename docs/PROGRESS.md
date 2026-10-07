# PROGRESS — Kartograf

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| NMT (parser + pobieranie) | ✅ Gotowy | v0.1.0+; wybor pliku arkusza przez `providers/pl/skorowidz.py` (filtr twardy + najnowsza kampania, ADR-028; K3/K4/S1/S4/H1/N1 naprawione 2026-09-30, live PASS) |
| NMPT (Digital Surface Model) | ✅ Gotowy | v0.4.0; warstwy z GetCapabilities wg `LAYER_PATTERN` (S4 naprawione) |
| Ortofotomapa | ✅ Gotowy | v0.4.0; RGB + najnowsza kampania (K5 naprawione, live PASS 2026-09-30) |
| LAZ (chmury punktów LIDAR) | ✅ Gotowy | WFS, area-based, --product laz; osie (N,E) + straz przeciecia (K1 naprawione, live PASS: Spytkowice -> `M-34-76-A-a-1-1-3`); awaria WFS = `DownloadError` (N7) |
| Land Cover (BDOT10k) | ✅ Gotowy | v0.3.0+, 15 warstw v0.5.0 |
| Land Cover (CORINE) | ✅ Gotowy | v0.3.0+ |
| SoilGrids | ✅ Gotowy | v0.3.0+ |
| HSG | ✅ Gotowy | v0.3.0+ |
| bbox → godla | ✅ Gotowy | find_sheets_for_bbox(), CLI --bbox |
| geometry → godla | ✅ Gotowy | find_sheets_for_geometry(), CLI --geometry |
| CLI | ✅ Gotowy | 5 komend + --bbox + --product + --system + --geometry |
| Auth Proxy (CLMS) | ✅ Gotowy | v0.3.0+ |
| PL-2000 (godlowanie) | ✅ Gotowy | Parser2000, auto-detekcja, CLI, storage; godlo PL-2000 bez pliku PL-2000 = `NoCoverageError` z podpowiedzia `--scale` (K4), sidecar EPSG:2176-2179 (N8) |
| Pokrycie testami | ✅ Gotowy | 2406 testow offline + 16 `live` (2026-10-07 po deduplikacji, parserach i LAZ ADR-029; 2216 2026-10-06 po rundzie review/E2E, w tym 28 na surowych body GUGiK; 2105 po polityce ponowien; 2058 po fali naprawczej 2026-09-30; wczesniej 1861 + 8 po fali review max 2026-09-28) |
| Migracja na ruff | ✅ Gotowy | config + auto-fix, sesja 2026-02-03 |
| Pobieranie rownolegle | ✅ Gotowy | ThreadPoolExecutor, --workers, v0.6.0 |
| Cache metadanych (SQLite) | ✅ Gotowy | MetadataCache, WAL, TTL 7d, v0.6.0; od 2026-09-30 `record_cache` (rekord skorowidza / `no_coverage` z podpowiedzia) podlaczony w torach PL (N6), `--force` = bez cache |
| Weryfikacja BBox PL-2000 | ✅ Gotowy | 67 testow, reference values + 16 testow `live` z realnymi asercjami na skorowidzu (N5) |
| Walidacja warstw WMS | ✅ Gotowy | wylacznie GetCapabilities (lock, retry), `LAYER_PATTERN` per produkt, bez zaszytych list (S4, errata ADR-020) |
| Etap 0 — zrodla wielokrajowe (sources/transform/transport/providers-pl/CLI split/sidecar) | ✅ Gotowy | zmergowane do develop 2026-08-11; E2E 12/12 na realnych danych |
| Etap 1 — NMT Czechy (CUZK: DMR 5G/4G, --country/--target-crs/--vertical-crs) | ✅ Gotowy | ZMERGOWANY do develop 2026-08-12; tor CZ odmrozony w fali 2026-09-29/30 (D1): pin EPSG:1622 (K2; live: Karkonosze PL-CZ mediana -0,15 m, przesuniecie < 1 px), budzet 4 Mpx kafli (K6; live: 29,8 Mpx w 3 min 38 s), piksel dokladnie 2 m (N3), `Warning:` przy 100 % nodata (N2); wersja `0.7.0-dev` |
| Wycinek NMT PL `--target-crs` (ADR-027) + API biblioteki `download_pl_cutout` | ✅ Gotowy | fala review max 2026-09-28 + fala naprawcza 2026-09-30: `GridMismatchError` dla 2180 z arkuszy o roznych fazach, W1 (warp per arkusz) dla 5514/3045 (S5/D3/D8), `extra.sheet_sources`, `all_nodata`, `download_pl_cutout(cache=)`; live PASS Krakow 5 m |

<!-- Statusy: ✅ Gotowy | ⚠️ Gotowy ze znanym bledem (tabela "Znane bledy", sesja 2026-09-29) | 🔧 W trakcie | ⏳ Zaplanowany | ❌ Wstrzymany -->

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

**Data:** 2026-08-10 — 2026-09-30 (sekcje datowane ponizej)

> **katalog danych DANYCH (2026-10-06):** wszystkie pobierane dane przestrzenne
> zapisujemy na `<katalog-danych>`:
> `kartograf/data/` (kanoniczny uklad) i `kartograf/e2e/<data>-<cel>/`
> (testy na zywo); zawsze jawne `--output`, cache SQLite zostaje w repo.
> Zasady: `CLAUDE.md` sekcja "katalog danych danych". `e2e-data/` (9,1 GB) w repo
> nadal czeka na decyzje: przeniesc na katalog danych czy usunac.

> **START NASTEPNEJ SESJI** (stan na koniec sesji 2026-09-30): **fala
> naprawcza ZAKONCZONA** — 21 bledow z testow na zywo (K1-K6, S1-S5,
> N1-N9, H1) naprawionych, review (5 znalezisk) domkniety, dokumentacja
> bez not "znany blad", testy na zywo 2026-09-30: 11 PASS / 0 FAIL
> (`docs/research/2026-09-29-fala-naprawcza/live-2026-09-30.md`). Nastepny
> krok: **wydanie 0.7.0** ("Nastepne kroki" pkt 13-14: bump wersji
> `0.7.0-dev` -> `0.7.0`, data w CHANGELOG, tag, push `develop`, merge do
> `main` — WYLACZNIE na polecenie uzytkownika; checklista release pkt 14:
> build sdist/wheel, zywa weryfikacja CORINE z credentials CLMS). Otwarte
> po fali (backlog): scalanie PL+CZ w jedna powierzchnie (R6, etap 2),
> rozwijanie godla PL-2000 1:10000 do potomkow z rekordami skorowidza
> (etap 2), wielokat granicy zamiast prostokata (`--country auto`,
> ADR-023), wycinek z arkuszy PL-2000 (etap 2). Stan repo: `develop`,
> 2058 testow offline (+16 `live`), ruff czysty, mypy 32 (baseline),
> 236 commitow przed origin (bez push); `e2e-data/2026-09-29-live/`
> (8,6 GB) i `e2e-data/2026-09-30-live/` (0,6 GB) gitignorowane — czekaja
> na decyzje uzytkownika o usunieciu. Modele: `task.agentModelOverrides`
> = `openai-codex/gpt-6-sol` (zapisane globalnie 2026-09-30; astra
> wyczerpuje limit po ~8 min pracy 3-4 agentow).

### ADR-030 strategie kampanii — fale 1-2 (T1-T6) zmergowane (2026-10-07)

> **START NASTEPNEJ SESJI:** fala 1 planu `docs/research/2026-10-07-plan-adr030.md`
> GOTOWA i w `develop` (merge `a187a5d` T1, `d839946` T2, `7fcd3bb` T3,
> `e5b5208` T4, `91fea75` T5) oraz fala 2 (`d6fa032` T6: providery
> `resolve_campaigns`/`download_record`/`record_source`, `supports_campaigns`).
> Brama: **2538 testow offline**, ruff czysty, mypy lista = baseline (32).
> Fala 3 (T7 `DownloadManager`: tor kampanii) — **TYLKO na polecenie
> uzytkownika**. Dla T7 z review T6: pochodzenie kampanii w torze `all` brac
> z `record_source(record)` (nie `source_info(godlo)`). Ledger SDD
> (rulingi, odlozone drobne uwagi do T11, uwagi dla T7):
> `.superpowers/sdd/2026-10-07-plan-adr030/progress.md` (gitignorowany).
> Nowe w kodzie (biblioteka, bez CLI): `download/campaigns.py` (`CampaignRef`,
> format z rekordu, `verify_file_format`), `FileStorage.get_campaign_path`/
> `list_files(campaigns=)`, `download/links.py` (dowiazanie symlink->hardlink->
> kopia, nigdy wstecz), `emit_sidecar(required=True)`, `MetadataCache`
> `campaigns_cache`, skorowidz `select_campaign_records`/`layer_upper_year`/
> `LAYER_FAMILY`/`file_format`, LAZ `campaigns="all"`/`min_year`.
> Uwaga dla T7 (decyzja uzytkownika): wyscig `ensure_standard_link` na tej
> samej sciezce — wariant A z planu (link raz na arkusz + dedup godel), bez
> blokad; ryzyko szczatkowe opisac w docstringach `ensure_standard_link`
> i `_fetch_campaigns`. Do oceny w T11: `to_source`
> zapisuje `"format": null` dla orto (wg planu 1.5).
>
> Przebieg fali 1: 5 agentow rownolegle (T2 opus, reszta sonnet), review per
> zadanie (T2, T4 opus), koordynator: brama + wlasna mutacja na kopii. T2:
> 1 runda poprawek (`campaign_key_of` bral pierwszy segment `kampanie` —
> katalog wyjsciowy z `kampanie` w sciezce wylaczal ochrone przed cofnieciem).
> Nieautoryzowane worktree z poprzedniej proby usuniete na polecenie.

- **Decyzje uzytkownika:** strategie `--campaigns {newest,all}` (domyslnie
  `newest`); `coverage`, `mosaic`, `--campaign <id>` ODRZUCONE (pokrycie
  nieznane przed pobraniem: brak HTTP Range, geometria WFS = rama arkusza;
  skladanie kampanii — narzedzie 0.7.1); `--min-year` od daty POZYSKANIA
  (`aktualnosc`); uklad B: `<segment>/kampanie/<data>_<id>/<hierarchia>/<godlo>`
  + sciezka standardowa = dowiazanie do najnowszej lokalnej kampanii
  (symlink -> hardlink -> kopia; nigdy wstecz); `newest` sprawdza nowsza
  kampanie; bez migracji starych plikow; sidecar kampanii obowiazkowy;
  format z pola `format` rekordu (`.xyz` 72675 = AAIGrid); kampanie TYLKO PL
  — CZ zawsze najnowsze, opcje kampanii dla CZ = `Error:`; aktualizacja CZ
  (flaga CLI: pelne ponowne pobranie / porownanie metadanych) — kolejne wydanie.
- **Research:** `pokrycie-kampanii.md` (8 par, 0,9-98,9 %),
  `2026-10-07-pobieraczek.md` (+ errata: WFS skorowidzow istnieje, geometria
  = rama), `2026-10-07-cuzk-kampanie.md` (CUZK bez historii; `ROK` w
  Metadata/MapServer/20), `2026-10-07-weryfikacja-planu-adr030.md` (Fable).
- **Plan:** 12 zadan, 5 fal (T1-T5 rownolegle; T6; T7; T8+T9; T10, T11) +
  T12 na zywo; tabela wlasnosci plikow bez kolizji; testy i mutacje per zadanie.

### Deduplikacja z review, parsery, LAZ ADR-029, pokrycie kampanii (2026-10-07)

- **Zlecenie uzytkownika:** wskazac arkusze z istotna roznica pokrycia
  miedzy kampaniami (orto+NMT); deduplikacja kodu z review przez
  subagentow, wczesniej ocena uproszczenia parserow; naprawa LAZ.
- **Pokrycie kampanii:** `docs/research/2026-10-06-e2e-brzegowe-i-review/pokrycie-kampanii.md`
  — 8 par z pomiarem (N-34-139-C-a-3-1 0,9 %, orto M-34-90-C-b-4-4 3,2 %,
  N-34-144-C-c-2-2 17,9 %, N-34-131-D-a-3-2 23,6 % ...); flaga
  `calyArkuszWypelnionyTrescia` nie mierzy skali braku. Serwer GUGiK NIE
  obsluguje HTTP Range (zdalny odczyt piramidy niemozliwy); tanie
  przyblizenia: naglowek ASC (zasieg), `rozmiarPlikuMB` orto; rekord NMT ma
  `zrDanych` (skaning vs zdjecia) i `numerZgloszeniaPracy` (id kampanii).
- **Kod (merge do develop):** LAZ `55c55f2` (ADR-029: wybor kafli wg
  pokrycia obszaru od najnowszego roku, `download_laz_area`,
  `parent_request`); dedup providerow `e793a02` (D1 jeden `download_to`,
  backoff 2/4 s wszedzie, `os.replace`, D2, D9, D13, D19); dedup download
  `fe15fcb` (D7, D10, D11 `Info:` przy 5m+KRON86, D14, D15, D18); parsery
  `fec42d1` (`core/bbox.py`, naprawa gubienia wiersza arkuszy PL-2000 przy
  poludniku osiowym, BREAKING: usuniete `Sm5Sheet`/`register_system`/
  `parser_factory`, `get_bbox` ~170x szybsze); porzadki `425ffc7` (K6:
  wycinek PL nie gubi ~479 m na poludniu dla bboxa WGS84 przez 19E; K7b
  walidacja `--bbox` we wszystkich torach; K9, D6, sesja LAZ na watek).
  Raporty: `ocena-parserow.md`, `impl-{laz,dedup-providers,dedup-download,parsery,porzadki}.md`.
- **Brama:** 2406 testow offline, ruff czysty, mypy 32 (lista = baseline);
  `kartograf/` netto −90 linii przy +4 funkcjach naprawczych.
- **Czeka na uzytkownika:** strategia kampanii (`kartograf campaigns`,
  `--campaign`, `--campaign-strategy newest|coverage`, `--min-coverage`;
  domyslna `newest` czy `coverage`) — zastepuje otwarta decyzje o regule
  niepelnego arkusza. Potem wydanie 0.7.0.

### Runda E2E przypadkow brzegowych GUGiK + code review (2026-10-06)

- **Zlecenie uzytkownika:** runda e2e (Sonnet) nastawiona na przypadki
  brzegowe danych GUGiK (sidecary, wybor pliku arkusza, wersje/roczniki)
  + code review (Fable: duplikacje, overengineering, deklaracje vs
  dzialanie); koordynacja, zywy dokument cyklu, testy lapiace faktyczne
  problemy. Artefakty: `docs/research/2026-10-06-e2e-brzegowe-i-review/`
  — **`raport-koncowy.md`** (start), `cykl-e2e.md` (kontrakt E1–E18
  z historia), raporty e2e-a/e2e-b/review-1/review-2/impl-fala-{a,b,c}/
  impl-fixtury/live-f9. Dane: katalog danych `kartograf/e2e/2026-10-06-brzegowe/`
  (3,2 GB).
- **Wynik:** 1 FAIL e2e (orto CIR/RGB wspolna sciezka) + 3 WYSOKIE z review
  (D1 retry rozjechane, D3 parsery ukladu, D8 warp CZ kasujacy wynik) +
  N1 (BDOT SHP jako .gpkg) i kilkanascie srednich — naprawione w falach
  A/B/C (TDD, mutacje), merge `b394570`. F9 na zywo 9/9 PASS.
  2216 testow offline (+111; 28 na surowych body GUGiK), mypy 32.
- **BREAKING:** `LazTile.uklad` dla nierozpoznanego `uklad_xy` rzuca
  `ValidationError` (kafel pomijany w discovery); orto CIR/B-W w
  `orto/pl_<uklad>_cir|_bw/`; BDOT10k SHP jako `.zip`.
- **Czeka na uzytkownika:** regula wyboru niepelnego arkusza (ADR-028
  D4/D9) — rekomendacja (c) najnowsza PELNA kampania + `Info:`
  (`raport-koncowy.md` sekcja 4). Backlog: sekcja 5 raportu.
- **Nastepny krok:** decyzja z sekcji 4, potem wydanie 0.7.0 (pkt 13-14).

### Polityka ponowien HTTP + sesja BDOT10k (2026-10-06)

- **Zlecenie uzytkownika:** przed wydaniem 0.7.0 — ponawiac tylko bledy
  sieci/429/5xx (4xx konczy od razu), respektowac `Retry-After`, dac
  BDOT10k wspolna sesje GUGiK. Commit `9bcc040`.
- **Kod:** `transport/http.py` — `is_retryable`, `retry_wait`
  (`MAX_RETRY_AFTER = 60`), `http_status`, `http_failure`
  (`DownloadError.status_code`); uzyte w `get_with_retry`, `download_to`
  (wiec tez skorowidz, WFS LAZ, CUZK) i `_download_with_retry` w
  `gugik.py`/`gugik_orto.py`/`gugik_laz.py`/`bdot10k.py`.
  `Bdot10kProvider._session_for_thread()` (jak `SkorowidzLayersMixin`).
- **Brama:** 2105 testow offline PASS (+47: `tests/test_retry_policy.py`,
  `TestRetryPolicy`/`TestGetWithRetryPolicy`/`TestDownloadToPolicy`),
  ruff czysty, mypy 32 = baseline (diff listy pusty). 6 mutacji
  (zawsze-ponawiaj, ignoruj Retry-After, bez limitu 60 s, LAZ bez
  szybkiego 404, BDOT nowa sesja co wywolanie, BDOT sesja wspolna watkom)
  — kazda wykryta.
- **Poza zakresem (backlog):** globalny limit tempa zapytan do GUGiK;
  CORINE/SoilGrids nadal ponawiaja kazdy blad; zapytanie TERYT BDOT10k
  bez ponowien; zduplikowane petle `_download_with_retry` w providerach.
- **Nastepny krok bez zmian:** wydanie 0.7.0 (pkt 13-14).

### Fala naprawcza bledow z testow na zywo (2026-09-29/30)

- **Zlecenie uzytkownika:** wdrozenie napraw 21 bledow z tabeli "Znane
  bledy" (nizej); rola koordynatora = decyzje + najtrudniejsza analiza,
  reszta przez subagentow. Artefakty: `docs/research/2026-09-29-fala-naprawcza/`
  — `decisions.md` (D1-D12 uzytkownika + rozstrzygniecia koordynatora),
  `plan.md` (fale A/B/C, wlasnosc plikow, kontrakty), `research-<klaster>.md`
  x4 (przyczyny potwierdzone na kodzie i surowych body, projekty),
  `impl-<pakiet>.md` x6 (dowody failing-before/passing-after), `review-fala.md`,
  `docs-fala.md`, `live-2026-09-30.md`. Commity `6c46224..` (13 na develop).
- **Decyzje uzytkownika:** D1 tor CZ odmrozony (K2+K6); D2/D10 tryb listy
  i hierarchia godla z tolerancja R5 (kod 0 przy >= 1 pliku, `Warning:`
  z lista; kod 1 przy porazce sieci albo zerze plikow); D3/D8 wycinek 2180
  z arkuszy o roznych fazach = `GridMismatchError`, 5514/3045 = W1 (warp per
  arkusz); D4/D9 wybor rekordu skorowidza = filtr twardy (godlo jako token,
  rozdzielczosc, uklad, orto RGB) + najnowsza `aktualnosc`, koniec cichego
  fallbacku PL-2000 -> PL-1992; D5 `extra.source` w sidecarze, zerwana
  warstwa = `DownloadError`; D6 pelny zakres (z N6); D11 status
  `no_coverage` w `DownloadProgress`; D12 `Info:` przy pomijaniu pliku ze
  starym sidecarem "(3)".
- **Kluczowe ustalenia research:** K2 — hipoteza `area_of_interest`
  OBALONA (prostokat obszaru uzycia EPSG:4829 siega po Zlin/Jaworzynke;
  AOI na zachod od 14,14°E daje pusta liste dla 5514->2180), diagnoza
  ADR-024 OBALONA (roznica 1622−4829 w kaflu `302_5550` = (+4,52; +2,03) m
  = "korekta" z ADR — serwer CUZK liczyl poprawnie); naprawa = jawny pin
  `DATUM_STEP_PINS = {5514: {EPSG:1622, EPSG:1623}}`. K6 — limit to liczba
  pikseli (7,5 Mpx OK / 8,38 -> 500), budzet `MAX_EXPORT_PIXELS = 4 Mpx`.
  S5 — `rasterio.merge` przeprobkowuje "przez okno", warp z takich arkuszy
  byl rownie zly. Skorowidz — rekordy maja pola `charakterystykaPrzestrzenna`,
  `aktualnosc`, `ukladWspolrzednychPoziomych`, `godlo`; wewnatrz warstwy
  rosnaco po dacie; H1 (`.ASC`) potwierdzona.
- **Kod:** NOWY `providers/pl/skorowidz.py` (parser, `select_sheet_record`,
  `query_skorowidz_layer` z retry, `SkorowidzLayersMixin`/`SourceInfoMixin`,
  wspolna petla `_resolve_record`); `transport/http.py` (`make_gugik_session`,
  `get_with_retry`); `gugik.py`/`gugik_nmpt.py`/`gugik_orto.py` bez
  `WMS_LAYERS`, sesja per watek, leniwy mkdir; `cache/metadata.py`
  `record_cache` (`get_record/set_record`, `url_cache` usuniete);
  `transform/crs.py` pin; `cuzk/client.py` budzet + snap NW; `gugik_laz.py`
  osie (N,E) + straz + `DownloadError`, `FALLBACK_YEARS` usuniete;
  `transport/mosaic.py` `check_source_grid`/`GridMismatchError`/`has_valid_pixels`;
  `transform/raster.py` `warp_to_grid(list[Path])`; `download/cutout.py`
  (`skipped_pl_cutout`, `all_nodata`, `off_grid_sheets`, `sheet_sources`,
  `cache=`); `download/manager.py` (`hard_failures`, `no_coverage`,
  `parent_requests`, `extra.source`); `cli/download_cmd.py`
  (`_finish_pl_sheets`, `CountryPart` + `Info:` S3, `Warning:` N2, cache
  wiring, komunikaty K2/D12/N7); `sources/sidecar.py`/`registry.py` (N8).
- **Brama:** 2058 testow offline PASS (+16 `live`), ruff check/format
  czyste, mypy 32 = baseline. Review (reviewer, 5 znalezisk: `--year`
  nieistniejacy bez "ponow", falszywe `Info:` S3 w `--geometry`, podpowiedz
  `NoCoverageError` gubiona przy trafieniu cache negatywnego, duplikat petli
  skorowidza w orto, testy pinujace `LAYER_PATTERN`) — wszystkie naprawione
  (`c132241`).
- **Testy na zywo 2026-09-30 (11 PASS / 0 FAIL):** K1 Spytkowice ->
  `M-34-76-A-a-1-1-3`; K5 RGB 2024-06-21; K4 Szczecin `80225_` 1,00 m,
  Warszawa 2025-04-27, rerun z cache 0,39 s; PL-2000 `5.167.25` ->
  `NoCoverageError` z `--scale`, kod 1, bez pliku PL-1992; S2 Leba 4 arkusze
  morskie `∅` + 8 plikow, `Warning:`, kod 0; K2 natywny res 2,000; K2
  `--target-crs 2180` sidecar "(1) 1.0 m"; K2b Karkonosze PL vs CZ mediana
  −0,15 m, brak przesuniecia >= 1 px (bylo 2,3 m); K6 29,8 Mpx (5473 x 5437)
  przez kafle w 3 min 38 s bez HTTP 500; S5 Krakow 5 m 2180 ->
  `GridMismatchError` (8/9 arkuszy), 5514 -> W1 `off_grid_sheets` 11; S3
  Rozewie `Info:` 54,90°N + obszar poza zasiegiem.
- **Modele:** GPT-6-astra padal z `usage_limit_reached` po 3-8 min przy 3-4
  agentach (dwukrotnie; czesciowa praca odzyskana z drzewa i transkryptow);
  Claude fable 429 przy 3-4 rownoleglych; skutecznie: 2 agenty naraz,
  wznawianie z `history://<id>` + `git diff`. Na polecenie uzytkownika
  `task` przelaczony na `openai-codex/gpt-6-sol` (zapis globalny), testy
  live na Haiku (effort lo).

### Testy na zywych danych + audyt dokumentacji (2026-09-29)

- **Zlecenie uzytkownika:** czy pobieranie przetestowano na realnych danych
  (centrum kraju, pas morski, pogranicza — nie tylko PL-CZ, takze PL-DE,
  gdzie danych DE nie obslugujemy, i inne) i czy zaktualizowano cala
  dokumentacje dotknieta falami 2026-08-28 i 2026-09-28. Stan przed sesja:
  po fali review max nikt nie pobieral z zywych uslug GUGiK/CUZK (tylko E2E
  offline na arkuszach 5 m z cache Hydrografu). Wykonanie: 7 agentow testow
  na zywo (L1-L7) i 2 audytorow dokumentacji (D1, D2) rownolegle, potem
  jedna fala poprawek dokumentacji. **Kod bez zmian zachowania** — bledy kodu
  zebrane i opisane, decyzja o naprawie nalezy do uzytkownika ("Nastepne
  kroki" pkt 15). Raporty (L1-L7, D1, D2, lista bledow `KNOWN-BUGS.md`,
  raport fali `DOCS-FIX-REPORT.md`, uwagi dla Hydrografa
  `hydrograf-uwagi-migracyjne.md`):
  `docs/research/2026-09-29-live-e2e-i-audyt-docs/`.

| Raport | Obszar i tryby | Wynik |
|---|---|---|
| L1 centrum-produkty | Spytkowice k. Krakowa: godla PL-1992 (1 m EVRF2007/KRON86, 5 m, rozwijanie 1:25000/1:50000), PL-2000, `--product nmpt/orto/laz`, lista `--bbox`, `pytest -m live` | 8 PASS / 5 UWAGA / 7 FAIL |
| L2 wycinki-siatka | 1 m (okolice Siemiatycz) i 5 m (okolice Wegrowa): wycinki 2180/5514/3045, bbox calkowity i ulamkowy, `--force`, biblioteka vs CLI; faza siatki 1 m w 12 miastach | 21 PASS / 5 UWAGA / 6 FAIL |
| L3 morze | Leba (5 m, 1 m, cel 5514), Hel, bbox w calosci nad morzem, Rozewie (54,90°N, offline), (j) surowe odpowiedzi skorowidza | 7 PASS / 4 UWAGA / 3 FAIL |
| L4 pogranicze PL-CZ | Cieszyn, Karkonosze, Beskid Slaski, Raciborz; godla TM33/SM5; kafelkowanie `exportImage` | 10 PASS / 4 UWAGA / 4 FAIL |
| L5 pogranicze PL-DE | Slubice, Zgorzelec, trojstyk PL-CZ-DE, Sieniawka, Osinow Dolny, Berlin | 7 PASS / 5 UWAGA / 2 FAIL |
| L6 inne granice | PL-SK (Lysa Polana), PL-UA (Medyka), PL-BY (Terespol), PL-LT (Budzisko), PL-RU (Piaski) x lista/wycinek | 9 PASS / 1 UWAGA |
| L7 duzy wycinek (offline) | N-33-118..132 (103 x 77 km) z cache Hydrografu, cel 2180/5514 x limit deskryptorow domyslny/256 | 4 PASS |
| D1 docs uzytkowe | README, CLAUDE.md, SCOPE, PRD, `--help`, `__all__` | 35 znalezisk |
| D2 docs architektura | ARCHITECTURE, DECISIONS, CHANGELOG, PROGRESS, DEVELOPMENT_STANDARDS, docstringi | 55 znalezisk (+11 w dokumentach Hydrografu) |

- **Mechanika potwierdzona na zywo:** segmenty `data/` i sidecary dla
  wszystkich produktow i ukladow (NMT 1 m/5 m EVRF2007/KRON86, PL-1992/PL-2000,
  NMPT, orto, LAZ, CZ dmr5g/dmr4g bpv/evrf2007, `bbox/`); wycinek
  `--target-crs EPSG:2180` na siatce arkuszy z wartosciami 1:1 (0 rozbieznych
  pikseli m.in. na 20 mln px w L2 i 14,3 mln w L3), cele 5514/3045 bit w bit
  z mozaika + warpem ta sama operacja; R5 na morzu i na granicach z CZ, DE,
  UA, BY, RU (arkusze bez danych -> nodata + `Warning:` + `missing_sheets`,
  nodata tylko nad morzem/za granica); `Skipped` bez sieci; nieudany `--force`
  zostawia stary plik; biblioteka == CLI bajt w bajt; pogranicze PL-CZ: dwa
  wycinki ze wspolnym `parent_request`; rozwijanie godel 1:25000/1:50000;
  duzy wycinek bez wyczerpania deskryptorow.
- **Zmierzone fakty:**
  - faza siatki arkuszy: 1 m PL-1992 (EVRF2007 2019-2025, KRON86 2011-2018)
    — jedna faza, narozniki pikseli na k + 0,5 m w 84 arkuszach (12
    lokalizacji + obszar testu), kampanie roznia sie zasiegiem o 1 px, nie
    faza — backlog `extra.off_grid_sheets` dla 1 m zbedny; 5 m — 5k + 2,5 m
    w cache Hydrografu (1977 arkuszy), pod Wegrowem (48 arkuszy kampanii
    2022/2024/2025) i w Lebie, ale arkusze 5 m kampanii 2022 pod Krakowem
    maja kazdy inna faze (9 z 9), a w Cieszynie 2 z 12 (kampania 2019) — S5;
  - styk PL/CZ (dane do R6): GUGiK wydaje dane ~200 m w glab CZ, CUZK ~118 m
    w glab PL, pas wspolny ~310-350 m bez szczeliny tam, gdzie GUGiK ma
    produkt w danej rozdzielczosci (Karkonosze 5 m: brak arkuszy GUGiK —
    dziura 5,2 km² po stronie PL); roznice wysokosci PL - CZ (oba EVRF2007)
    w pasie wspolnym: mediany -0,19..+0,14 m zaleznie od zbioru i spadku,
    trojstyk PL-CZ-DE: mediana 0,17 m; siatki PL i CZ niewspolne;
  - skorowidz GUGiK (j): pusta odpowiedz GetFeatureInfo (morze, strona czeska
    i niemiecka) = szablon HTML MapServera, HTTP 200 `text/html`, 7721 B,
    identyczny dla 1 m/5 m i wszystkich warstw, BEZ znacznikow OGC ->
    `NoCoverageError`; zla warstwa = HTTP 200 `text/xml` (554 B)
    `ServiceExceptionReport`/`LayerNotDefined` -> `DownloadError` — straz
    I-2 potwierdzona w obie strony (surowe body: `gfi/` w katalogu raportow —
    probki L3; opis odpowiedzi strony CZ i DE: L4 U12, L5 pkt (j));
  - duzy wycinek (L7, offline): 1836 (cel 2180) / 2394 (cel 5514) arkuszy
    w selekcji, 688/732 z danymi (reszta R5 = nodata): 36 s / 109 s, szczyt
    RSS ~1 GiB (1037-1039 MiB), maks. 9 otwartych deskryptorow, `ulimit -n
    256` przechodzi z wynikiem bit w bit (sha256);
  - nodata przy morzu i granicy: `missing_sheets` wymienia tylko arkusze bez
    pliku — nodata bywa tez wewnatrz pobranych arkuszy przybrzeznych
    (kampania 5 m 2025 przycina rastry do zasiegu danych) i przygranicznych
    (PL-SK: do 82 % arkusza); przy brzegu woda ma wartosci ~0 m (5 m: pas
    setek metrow, 1 m: caly arkusz przybrzezny);
  - warp GDAL (cele 5514/3045): domyslne opcje to takze przyblizony
    transformator (`tolerance` 0,125 px) — wobec dokladnego bilineara
    srednio 0,13-3,3 mm, maks. do 0,25 m (1 m) i 0,13 m (5 m, sama
    `tolerance`);
  - GUGiK zrywal 13-50 % polaczen podczas testow (L5: 39 z ~294 zapytan WMS;
    L1: ~50 % swiezych polaczen) — mozliwy wplyw 9 agentow z jednego IP;
    ta sama biblioteka na jednej sesji keep-alive z `Retry`: 72/72 zapytan
    bez bledu.

#### Znane bledy (testy na zywo 2026-09-29)

Stan: **WSZYSTKIE 21 NAPRAWIONE w fali 2026-09-29/30** (sekcja "Fala
naprawcza" wyzej; dowody `docs/research/2026-09-29-fala-naprawcza/`,
testy na zywo 2026-09-30: 11 PASS / 0 FAIL). Tabela zostaje jako zapis
historyczny; opisy i miejsca w kodzie (wg HEAD sprzed naprawy): Backlog ->
"Do naprawy — testy na zywych danych 2026-09-29 (przed wydaniem 0.7.0)".
Raporty z testow na zywo 2026-09-29: `docs/research/2026-09-29-live-e2e-i-audyt-docs/`.

| ID | Waga | Blad (jedno zdanie) | Raport |
|---|---|---|---|
| K1 | KRYTYCZNY | LAZ: discovery WFS z zamienionymi osiami — kafle z innego miejsca (Spytkowice -> Lubuskie, 426 km) | L1 |
| K2 | WYSOKI | Operacja S-JTSK -> ETRS89 = EPSG:4829 (Slowacja) w Czechach — tresc CZ po reprojekcji i wycinek PL -> 5514 przesuniete do ~5 m (granica PL-CZ 1,1-3,4 m); diagnoza ADR-024 najpewniej bledna | L4, L2 |
| K3 | WYSOKI | Zerwane zapytanie nowszej warstwy skorowidza -> po cichu starsza kampania w cache (dwa `--force`: 21 % pikseli, do 4,2 m) | L2, L3, L5, L1 |
| K4 | WYSOKI | Wybor pliku arkusza: pierwszy URL z godlem — 0,5 m zamiast 1 m, najstarsza kampania, arkusz PL-1992 pod godlem PL-2000 | L2, L1 |
| K5 | WYSOKI | `--product orto` pobiera CIR zamiast RGB | L1 |
| K6 | WYSOKI | Realny limit `exportImage` ~8 Mpx na zapytanie (kafle ciete dopiero powyzej 15000 x 4100 px) — obszar CZ 2 m zblizony do kwadratu > ~5,5 x 5,5 km (albo 10 x 5 km W-E) = HTTP 500 | L4 |
| S1 | SREDNI | Skorowidz bez ponowien i bez wspolnej sesji — wycinki padaja przy zrywanych polaczeniach | L3, L5, L4 |
| S2 | SREDNI | Tryb listy bez tolerancji R5 — morze/granica = kod 1, `--workers 1` przerywa na pierwszym arkuszu bez danych | L3, L5, L6, L4 |
| S3 | SREDNI | `--country auto` po cichu przycina bbox do prostokata kraju | L5, L3 |
| S4 | SREDNI | NMPT EVRF2007: nieaktualna lista warstw w kodzie — bez GetCapabilities nie pobieraja sie arkusze spoza warstw 2025/2024 | L1 |
| S5 | SREDNI | Arkusze 5 m o roznych fazach siatki — wycinek 2180 z wartosciami z sasiedniego piksela | L1, L2 |
| N1 | NISKI | Puste katalogi po arkuszach bez danych | L3, L5, L4 |
| N2 | NISKI | Wynik w 100 % nodata jako sukces bez komunikatu | L4, L5 |
| N3 | NISKI | Natywny wycinek CZ: piksel 2,0004 m | L4 |
| N4 | NISKI | Pominiete arkusze/wycinek: bez `parent_request`, `missing_sheets == ()` | L1, D1 |
| N5 | NISKI | Testy `-m live` niczego nie sprawdzaja | L1 |
| N6 | NISKI | `MetadataCache` niepodlaczony w torach PL | D2, L3 |
| N7 | NISKI | LAZ: "No LAZ tiles found" przy awarii sieci | L1 |
| N8 | NISKI | Sidecar pliku PL-2000 z `horizontal_crs` EPSG:2180 | L1, L2 |
| N9 | NISKI | Oszacowanie miejsca na dysku liczone dwa razy przy jawnym `estimate_pl_cutout_bytes` | L7 |
| H1 | hipoteza | Regex URL skorowidza pomija `.ASC` wielkimi literami | L5 |

- **Fala poprawek dokumentacji (ta sesja):** kazde znalezisko D1/D2
  zweryfikowane na kodzie; wynik (tabela per znalezisko:
  `DOCS-FIX-REPORT.md` w katalogu raportow wyzej): D1 — 33 naprawione,
  2 oznaczone jako znany blad
  (N4); D2 — 50 naprawionych, 4 oznaczone (N6, K3 x2, S2), 1 pominiete
  (docstring `gugik_laz.py` — plik K1 nietykany do naprawy); 0 odrzuconych;
  11 uwag dla Hydrografa w `hydrograf-uwagi-migracyjne.md` (repo Hydrografu
  nietkniete). Zmienione: README (sekcja "Znane problemy (0.7.0-dev)"),
  CLAUDE.md, SCOPE 3.11, PRD 3.7, ARCHITECTURE, DECISIONS (errata ADR-021,
  ADR-023, ADR-024 — K2, uzupelnienia ADR-003/010/018/019/020/026/027),
  CHANGELOG (uwagi migracyjne 0.6.1 -> 0.7.0), DEVELOPMENT_STANDARDS 2.2,
  IMPLEMENTATION_PROMPT 4.2, ten dokument oraz WYLACZNIE teksty w kodzie
  (docstringi, komentarze, `--help` — AST bez docstringow bez zmian).
  Brama: 1861 testow offline PASS (+8 `live` deselected), ruff check
  + format czyste, mypy 32 = baseline (lista identyczna). Galaz nie
  pushowana.
- **Niezalezny przeglad fali dokumentacji (opus, ta sesja):** kod bez
  zmian zachowania potwierdzony (AST bez docstringow identyczne,
  w `_parser.py` tylko teksty pomocy), pliki K1/K2/K6 nietkniete, 21 ID
  w backlogu "Do naprawy" dokladnie raz; 15 usterek (1 blokujaca:
  "`auto` == `pl`" na granicach z krajami spoza rejestru przeczylo
  przycinaniu S3; 2 wazne: zakres K2 w ARCHITECTURE, S4 "NMPT nie
  pobiera sie wcale") naprawione w f52593a; re-review rundy: 2 resztki
  (dolna granica K2 — na Morawach roznica operacji to 0,1-1,0 m;
  odsylacze w notce K2) poprawione w fb3cede. Raporty:
  `DOCS-REREVIEW-REPORT.md` i `sdd-ledger.md` w katalogu raportow wyzej.

### Fala naprawcza po review max + wycinek PL w bibliotece (2026-09-28)

- Plan: `docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md`
  (18 zadan, team-driven SDD: pre-flight planu, review per zadanie z dowodami
  mutacyjnymi, finalny review calej fali, fala finalna + re-review); spec:
  raport review max
  `docs/research/2026-08-28-uklad-data-target-crs-pl/2026-08-30-code-review-max.md`
  (15 znalezisk). Artefakty procesu (ledger ze WSZYSTKIMI rulingami kontrolera,
  pre-flight, raporty zadan, finalny review i fala finalna, skrypty E2E):
  `docs/research/2026-09-28-fala-review-max/`.
- **Rozstrzygniecia uzytkownika (wiazace):** R1 wycinek `--target-crs EPSG:2180`
  lezy na SIATCE ARKUSZY GUGiK (obszar rozszerzony na zewnatrz do pelnych
  pikseli arkuszy, wartosci 1:1, `transform: null`, nazwa pliku = wspolrzedne
  zadania); R2 zn. 15 (rzadka geometria wieloobiektowa) poza zakresem, bez
  zmian; R3 wycinek PL jako API biblioteki juz w 0.7.0 (Hydrograf); R4
  wykonanie team-driven; R5 arkusz bez danych GUGiK (`NoCoverageError`) =
  nodata + `Warning:` + `extra.missing_sheets`, kazda inna porazka pobrania =
  kod 1 (chwilowy blad nie zostawia trwalej dziury); R6 scalanie PL+CZ w jedna
  powierzchnie przygraniczna = backlog / etap 2.
- **Zamkniete: 14 z 15 znalezisk** (zn. 15 — R2), w tym trzy krytyczne
  (przesuniecie tresci o ulamek piksela, arkusz bez danych wetujacy caly
  wycinek, wyczerpanie deskryptorow > 1024 arkuszy), **+ 5 defektow wykrytych
  przy planowaniu pomiarem realnych arkuszy**: przesuniecie o 0,5 px takze dla
  bboxow CALKOWITYCH (realne arkusze GUGiK 5 m maja narozniki pikseli na
  5k + 2,5 m — 1977 arkuszy zmierzonych); mozaika Int32, gdy pierwszy arkusz
  ASC ma same liczby calkowite; `CRS mismatch` przy arkuszach z `.prj`
  Hydrografu obok arkuszy bez niego; selekcja gubiaca pas przy gornej krawedzi
  bboxa na poludniku 19°E (6 arkuszy dla bboxa szerokiego na 20 km); cicha
  dziura nodata dla arkuszy 1 m wydanych przez GUGiK w ukladzie PL-2000 pod
  godlem PL-1992 (teraz glosny blad; reprojekcja takich arkuszy = etap 2).
- Kod: `transport/mosaic.py` (leniwe zrodla; `snap_to_source_grid=` — siatka
  wiekszosci + ostrzezenie; `assign_crs=`/`dtype=` — zrodla w VRT w `/vsimem/`);
  `NoCoverageError(DownloadError)` + `DownloadResult.no_coverage` +
  `DownloadManager.download_sheets()/expand_sheets()`; NOWY
  `kartograf/download/cutout.py` (`download_pl_cutout`; kroki
  `prepare_pl_cutout` -> `select_pl_cutout_sheets` -> `run_pl_cutout`; kontrola
  dysku, `Info:` >= 1 GiB, kompresja pliku posredniego, sprzatanie pustych
  `bbox/`); CLI `--target-crs` PL jako cienka nakladka; obwiednia geometrii
  w ukladzie czeskim przez operacje przypieta; `LazTile.uklad` +
  `FileStorage.get_raw_path(uklad=)`; szablony segmentow z rejestru;
  `resolve_subdir` odrzuca pusty wymiar. Tor CZ (`providers/cuzk/*`)
  i `transform/raster.py` bez zmian.
- **E2E offline na realnych arkuszach 5 m** (cache Hydrografu tylko do odczytu,
  provider kopiujacy pliki, zero patchy poza straznikiem sieci): EPSG:2180 —
  faza siatki 2,5, **0 / 80 601** (bbox calkowity) i **0 / 79 799** (ulamkowy)
  pikseli rozbieznych z arkuszem zawierajacym srodek piksela, mieszany `.prj`
  = bez `.prj`; EPSG:5514 — bit w bit = mozaika + `warp_to_grid`, wobec
  niezaleznego warpu GDAL per arkusz srednio 2,7 mm / maks. 0,15 m poza szwem
  (z `XSCALE=YSCALE=1`: 0,03 mm / 3,2 mm — wlasnosc zamrozonego warpu,
  backlog); brak arkusza -> `missing_sheets` + 33 775 px nodata wylacznie
  w jego miejscu; ponowne uzycie cache = 0 wywolan providera; kompresja pliku
  posredniego 2,12x.
- **Finalny review calej fali (fable) + fala finalna (opus) + re-review
  (opus) — ZAMKNIETE.** 0 Critical / 2 Important / 11 Minor, oba Important
  niewidoczne per zadanie: (1) wiazanie `--force`/`--workers` z CLI do
  biblioteki bez testu — mutacja `force=False` przechodzila 312/312, a
  `--force` na istniejacym wycinku bylby cichym no-opem akurat tam, gdzie
  CHANGELOG kaze go uzyc; (2) odpowiedz 2xx skorowidza z raportem wyjatku OGC
  (np. "Invalid layer(s)" przy nieaktualnej nazwie warstwy, gdy GetCapabilities
  sie nie udal) liczona jako brak pokrycia -> pod R5 trwala dziura nodata;
  teraz blad warstwy (straz WYLACZNIE negatywna — URL w odpowiedzi zawsze
  wygrywa). Plus: uklad czeski bboxa w API bez wzgledu na wielkosc liter,
  docstringi `last_result`/`NoCoverageError`, komendy testow offline
  (`-m "not live"`) w CLAUDE.md/README, precyzja ARCHITECTURE 4.3. Re-review:
  6/6 naprawione, 4 drobiazgi zaparkowane z rulingami (backlog nizej).
- **Stan koncowy (pomiar 2026-09-28, HEAD bbd1cd4 + commit zamykajacy): 1861
  testow offline PASS** (+8 `live` deselected), pokrycie **92,92 %**, ruff
  check + format czyste, **mypy 32 = baseline** (lista identyczna), drzewo
  czyste. 30 commitow fali na `develop` (od 8cf1e5a, razem z raportem, planem
  i commitem zamykajacym); galaz swiadomie NIE pushowana ani nie mergowana do
  `main` — wydanie czeka na checkliste live (pkt 12-14 nizej).

### Uklad data/ per produkt + --target-crs PL (2026-08-28)

- Spec: `docs/superpowers/specs/2026-08-28-uklad-data-i-target-crs-pl-design.md`
  (D1-D8); plan: `docs/superpowers/plans/2026-08-28-uklad-data-i-target-crs-pl.md`
- Segmenty `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]` (ADR-026):
  szablony w deskryptorach (`resolve_subdir`), FileStorage(vertical_crs=),
  manager/CLI PL/CZ/LAZ na resolve_subdir; ADR-017 domkniety
- `--target-crs` dla PL (ADR-027): wycinek `nmt/pl_1992_<res>_<vcrs>/bbox/`,
  mozaika (`mosaic_and_crop(dst_kwds=)`) + `transform/raster.warp_to_grid`
  (wymuszona operacja przypieta); pogranicze `--country auto` = dwa wycinki,
  wspolny `parent_request`; errata ADR-023
- Wycinek w trybie `--geometry` obejmuje CALA obwiednie geometrii (bez
  maskowania do obiektow); `nodata` tylko tam, gdzie nie siega zaden pobrany
  arkusz. Selekcja arkuszy z zapasem (`_PL_WARP_MARGIN_PX = 4` px):
  w `--bbox` zawsze, w `--geometry` z warpem jako suma godel z geometrii
  i z bboxa z zapasem (dla celu `EPSG:2180` zapas jest zerowy, wiec sumy
  nie ma — arkusze wyznacza sama geometria)
- Dokumentacja: NOWY `docs/ARCHITECTURE.md` (kanoniczny uklad data/),
  CHANGELOG Breaking z tabela migracji, ADR-026/027 + korekty 013/017/023
- Stan po zadaniu dokumentacyjnym (pomiar 2026-08-28): **1775 testow PASS**,
  ruff check/format czyste, **mypy 32** (brama `<= 32` z weryfikacji planu
  spelniona — 33. blad znikl razem z `descriptor.storage_subdir`)
- **Brama jakosci (Zad. 12, 2026-08-28) — ZAMKNIETA:** powtorzony pomiar na
  develop daje **1775 passed**, pokrycie **93%** (92,63% total), ruff
  check + format czyste, **mypy 32 bledy w 9 plikach** (baseline 33 → 32,
  zero nowych). Kryteria akceptacji specu 13.1-13.8: **siedem SPELNIONYCH
  offline** (sciezki 13.2-13.5 sprawdzone realnym `FileStorage`
  i uruchomieniem `main()` z zamockowana warstwa pobierania, nie odczytem
  z dokumentacji), 13.5 z jednym zastrzezeniem: zgodnosc tresci wycinka
  potwierdzona syntetycznie (`test_pl_cutout.py::TestBuildPlCutout::
  test_target_5514_content_lt_1px`, `test_transform_raster.py::TestWarpToGrid`),
  a **weryfikacja na zywych danych GUGiK zostaje pozycja checklisty release**
  (pkt 12 „Nastepne kroki") — offline nie da sie jej odhaczyc.
- **Finalny review calej galezi + fala naprawcza (2026-08-28) — ZAMKNIETE.**
  Review 23 commitow wykryl defekt MIEDZYZADANIOWY, niewidoczny per zadanie:
  zapas zrodla (`_PL_WARP_MARGIN_PX`) nie wplywal na selekcje arkuszy
  w trybie `--geometry` (8,4 % pikseli `nodata` przy 0 % w torze `--bbox`;
  powrot obwiedni celu do 2180 rosnie o ~7,5 % boku na strone, dla 20 km
  = 1512 m), a w torze `--bbox` nie bronil go zaden test — mutacja usuwajaca
  poszerzony bbox z selekcji przechodzila 1775/1775. Jedna fala zamknela
  11 pozycji (21 dowodow mutacyjnych), m.in.: `DownloadManager` budowal
  segment z wlasnego pionu zamiast z providera (KRON86 i EVRF2007 tego
  samego arkusza znow w jednym katalogu — osiagalne z API biblioteki);
  `FileStorage(vertical_crs="")` dawal cichy segment `nmt/pl_1992_1m_`;
  brak wpisow `KNOWN_PATHS` dla dwoch nowych par (2180→5514 acc 0,5,
  2180→3045 acc 0,0 — zmierzone); caly przeplyw 5 m byl niebroniony
  (4 mutacje przechodzily); atomowosc zapisu i sprzatanie po awarii
  nieprzetestowane (3 mutacje przechodzily).
- **Nieudana budowa wycinka nie niszczy poprzedniego wyniku** — zbedne
  kasowanie pliku docelowego zdjete z `_build_pl_cutout` ORAZ
  z `transform/raster.py::warp_to_grid` (zapis jest atomowy przez
  `os.replace`, wiec `unlink` chronil przed niczym, a kasowal stary,
  poprawny raster). Gwarancja obowiazuje caly tor PL, takze
  `--target-crs EPSG:5514`/`EPSG:3045`; tor CZ ma wlasne `unlink` jako
  udokumentowany wyjatek (ADR-024).
- **Stan koncowy sesji: 1787 testow PASS** (start planu 1716), pokrycie
  92,7 %, **mypy 32** (start 33), ruff check + format czyste, drzewo czyste.
  23 commity na `develop`; galaz swiadomie NIE pushowana ani nie mergowana
  do `main` — wydanie (bump 0.7.0, tag, push) czeka na checkliste live.

### Plan: uklad data/ per produkt + --target-crs dla PL (2026-08-28)

**Stan: SPEC + PLAN gotowe** (zapis sprzed wdrozenia; implementacja opisana
w sekcji wyzej).

- Spec (commit 635c6e1): `docs/superpowers/specs/2026-08-28-uklad-data-i-target-crs-pl-design.md`
  — decyzje D1-D8 zatwierdzone w rozmowie 2026-08-28.
- Plan (commit 6cb662d): `docs/superpowers/plans/2026-08-28-uklad-data-i-target-crs-pl.md`
  — 12 zadan TDD / 74 kroki, kolejnosc dobrana tak, by suita byla zielona
  po KAZDYM commicie (stad Zad. 2 laczy rejestr + FileStorage + CZ CLI:
  dziela te same wartosci `storage_subdir`).
- Zakres: (1) `data/<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/` —
  szablony `{uklad}`/`{vcrs}` w deskryptorach + `resolve_subdir()`,
  `FileStorage(vertical_crs=)`; domkniecie odroczonego ADR-017 (PL-2000
  dostaje wlasne segmenty, backlog A1-9); (2) `--target-crs` dla PL
  w bbox/geometry = jeden scalony wycinek (arkusze jako cache ->
  `mosaic_and_crop` -> lokalny warp przypieta operacja); (3) nowy
  `docs/ARCHITECTURE.md` + aktualizacja calego `docs/` (ADR-026, ADR-027,
  korekty ADR-013/017, addendum ADR-023).
- **Wchodzi do 0.7.0 PRZED tagiem** (D7) — poprzedza bump 0.7.0
  ("Nastepne kroki" pkt 13).

**Weryfikacja planu przed implementacja** (3 niezaleznych recenzentow
adwersarialnych: kotwice kodu / pokrycie specu / wykonalnosc techniczna):
17 defektow, wszystkie naprawione w commicie planu. Najpowazniejszy: bledna
kotwica wstawienia walidacji `--target-crs` trafiala w galaz `if
has_geometry:` zamiast godlowej, co odrzucaloby flage dla KAZDEGO zadania
`--geometry` (takze CZ). Pozostale: niekompletne listy asercji do poprawy
(8 miejsc), jedna instrukcja odwrotna do prawdy (slice'y `parts[-8:-1]`
liczone od konca NIE zmieniaja sie po wstawieniu segmentu), brak lokalnego
importu w nowych testach, ADR-y ladujace wewnatrz komentarza HTML
(`DECISIONS.md:923`), kolizja wersji SCOPE 3.8.

**Pomiary wykonane przy weryfikacji (offline, do wykorzystania przy wdrozeniu):**
- `mypy kartograf/` na develop = **33 bledy**, nie 32 jak podaja ten dokument
  i CLAUDE.md (stan z audytu). Trzydziesty trzeci to
  `cli/download_cmd.py:1347` (`Path / (str | None)` z `descriptor.storage_subdir`)
  i znika sam po ADR-026 — brama po wdrozeniu: `<= 32`.
- `rasterio.merge.merge(dst_kwds={"driver":"GTiff","crs":...})` nadpisuje
  profil wyjscia takze dla wejsc AAIGrid bez CRS (rasterio 1.5.0) — to
  przesadza o wykonalnosci wycinka PL z arkuszy `.asc`.
- `build_pinned_transform` offline: 2180->5514 = 0,5 m, 2180->3045 = 0,0 m;
  `gdal_operation()` dla 2180->5514 zaczyna sie od `axisswap` (2180 jest
  northing-first) i niesie `molobadekas`.
- Prototyp mozaika+warp postawil wierzcholek **0,496 m** od wzorca pyproj
  (< 1 px) — najbardziej ryzykowna czesc planu sprawdzona przed kodowaniem.

**Ograniczenie do zapamietania:** warp PL ma byc OSOBNA funkcja
(`kartograf/transform/raster.py::warp_to_grid`), nie refaktorem
wspoldzielonym z `providers/cuzk/dmr.py::_warp_to_grid` — testy ADR-024
patchuja `kartograf.providers.cuzk.dmr.reproject`
(`tests/test_cuzk_dmr.py:496,527`), a tor CZ jest zweryfikowany live.

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
   miedzy trybami jawny/auto; od 2026-09-28 takze: scalanie PL+CZ w jedna
   ciagla powierzchnie przygraniczna — R6, po checkliscie live pkt 12 (h) —
   i wycinek PL z arkuszy wydanych przez GUGiK w ukladzie PL-2000) —
   spec/plan do napisania po decyzji o mergu;
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
   diagnozach w przyszlosci. **Errata 2026-09-29:** te wartosci to
   najpewniej roznica operacji EPSG:1622 - EPSG:4829, czyli blad lokalnej,
   slowackiej operacji przypietej, nie serwera (znany blad K2, errata
   ADR-024).
3. **Push `develop` na origin** (**223 commity** lokalnie — pomiar
   `git rev-list --count origin/develop..develop` 2026-09-29 po commicie
   zamykajacym sesje testow na zywo; wczesniej 208 po fali review max
   2026-09-28 i 148 po mergu audytu 0.7.0 2026-08-28; decyzja z etapu 0 nadal
   nierozwiazana) — patrz wyzej
4. **Zgloszenie/naprawa WCS EVRF2007 GUGiK** (male, przedistniejace, poza
   etapami 0/1): aktualizacja `WCS_ENDPOINTS`/`COVERAGE_IDS` w
   `providers/pl/gugik.py` po usunieciu endpointu przez GUGiK (patrz "Znany
   problem uslugowy" wyzej); rozwazyc walidacje WCS analogiczna do
   walidacji warstw WMS (czesciowo zrobione w audycie A1-4:
   `download_bbox` z EVRF2007 konczy sie `ValidationError` przed siecia,
   a kanal WCS deskryptora deklaruje tylko KRON86; zostaje zgloszenie do
   GUGiK i ewentualna walidacja WCS)
5. Odziedziczone: (do weryfikacji) zgodnosc `get_bbox` z godlowaniem kafli
   LAZ (patrz ADR-021 i `providers/pl/gugik_laz.py`) — obserwacja
   "godlo -> kafle z innego arkusza" okazala sie objawem znanego bledu K1
   (zamienione osie WFS, testy na zywo 2026-09-29); do ponownej oceny po
   naprawie K1
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
11. ~~**Uklad data/ per produkt + `--target-crs` dla PL** (ADR-026/027)~~ —
    **WYKONANE 2026-08-28** (12 zadan TDD z
    `docs/superpowers/plans/2026-08-28-uklad-data-i-target-crs-pl.md`;
    segmenty ADR-026, wycinek PL ADR-027, `docs/ARCHITECTURE.md`).
12. ~~**E2E live sciezek nowego ukladu `data/` + wycinka `--target-crs` PL**~~
    — **WYKONANE 2026-09-29** (7 raportow na zywo, sekcja "Testy na zywych
    danych + audyt dokumentacji" wyzej; raporty
    `docs/research/2026-09-29-live-e2e-i-audyt-docs/`). Status pozycji:
    (a) godlo PL x KRON86/EVRF2007 -> `nmt/pl_<uklad>_<res>_<vcrs>/` —
    PL-1992 PASS (1 m obu pionow, 5 m, rozwijanie 1:25000/1:50000, ponowne
    uruchomienie bez sieci); PL-2000: sciezka poprawna, tresc — arkusz PL-1992
    podstawiony po cichu (K4, N8); KRON86 x PL-2000 nieuruchamiane (L1);
    (b) `--product nmpt|orto|laz` -> segmenty poprawne; NMPT PASS (S4 przy
    awarii GetCapabilities); orto FAIL — CIR zamiast RGB (K5), najstarsze
    zdjecie w "Starsze" (K4); LAZ FAIL — kafle z innego miejsca (K1); "kafle
    z obu ukladow w jednym zadaniu" nie wykazane (L1);
    (c) CZ godlo TM33/SM5 i bbox -> `nmt/cz_dmr{5g,4g}_<vcrs>/[bbox/]` —
    PASS (sciezki, sidecary, EVRF2007); tresc obciaza K2, piksel natywnego
    wycinka N3 (L4, L5);
    (d) wycinek PL do EPSG:5514/3045 na realnych arkuszach 1 m i 5 m —
    mechanika PASS (bit w bit z wlasna mozaika + ta sama operacja, wobec
    niezaleznej interpolacji srednio 0,13-3,3 mm), ale tresc zalezy od
    wyboru pliku arkusza (K3/K4: dwa `--force` — 21 % pikseli), a cel 5514 —
    od K2 (L2, L3);
    (e) pogranicze `--country auto --target-crs EPSG:2180` — PASS w Cieszynie
    i na trojstyku PL-CZ-DE (dwa wycinki, wspolny `parent_request`, nodata PL
    po stronie CZ, `missing_sheets`, `Warning:`, kod 0); Karkonosze 5 m: CLI
    3/3 porazki przez S1, a udany wycinek PL = 100 % nodata (brak 5 m, N2)
    (L4, L5);
    (f) siatka 1 m — jedna faza, narozniki k + 0,5 m w 84 arkuszach (1 m:
    `extra.off_grid_sheets` zbedne); 5 m nie zawsze 5k + 2,5 — S5 (L2, L1,
    L4);
    (g) arkusze PL-2000 pod godlem PL-1992 — rzadkie (KRON86 1/12 miast,
    EVRF2007 0/12), wycinek odmawia glosno (PASS), ale plik zostaje w cache
    PL-1992, a remedium `--system 2000` daje arkusz-dziecko (K4, N8);
    grozniejszy kuzyn luki "URL innego arkusza": plik 0,5 m w skorowidzu
    1 m (K4) (L2);
    (h) styk PL/CZ zmierzony (GUGiK ~200 m w glab CZ, CUZK ~118 m w glab PL,
    pas wspolny ~310-350 m, roznice -0,19..+0,14 m, trojstyk 0,17 m) — dane
    wejsciowe do R6 (L4, L5);
    (i) duzy wycinek (1836/2394 arkuszy): 36 s / 109 s, ~1 GiB RSS, 9
    deskryptorow, `ulimit -n 256` bit w bit — PASS (L7; N9);
    (j) surowe odpowiedzi skorowidza zapisane (morze, strona CZ i DE, zla
    warstwa) — straz I-2 dziala w obie strony, PASS (L3, L4, L5; kontrola
    pozytywna szablonu mozliwa, nie wdrozona);
    (k) **dopisane i WYKONANE:** pogranicze PL-DE (Slubice, Zgorzelec,
    trojstyk, Sieniawka, Osinow, Berlin) — wycinek PASS (arkusze niemieckie
    w `missing_sheets`, nodata tylko za Odra/Nysa, 1:1), tryb listy kod 1
    (S2), ciche przyciecie `auto` na zachod od 14,07°E (S3), plik CZ 100 %
    nodata nad Saksonia (N2) (L5);
    (l) **dopisane i WYKONANE:** granice PL-SK, PL-UA, PL-BY, PL-LT, PL-RU —
    wycinek PASS (R5; `auto` odpytal tylko PL — bboxy testu nie siegaly za
    krawedzie prostokata PL, CUZK nieodpytany), PL-LT niedokonczony
    przez niestabilnosc GUGiK (poprawnie kod 1 "ponow"); tryb listy kod 1
    i jeden zgloszony arkusz (S2); PL-SK: nodata wewnatrz opublikowanych
    arkuszy (do 82 %) bez `missing_sheets`; 5 m brak w rejonie Sejn (L6).
13. **Bump wersji + wydanie 0.7.0** — **czeka na fale naprawcza (pkt 15)**:
    `kartograf.__version__` `0.7.0-dev` -> `0.7.0` (pyproject czyta wersje
    dynamicznie), data w CHANGELOG, tag `v0.7.0`, push `develop` na origin
    (patrz pkt 3 wyzej).
14. **Checklista release** (z planu audytu 0.7.0): build sdist/wheel
    (`setuptools`); zywa weryfikacja CORINE GeoTIFF z prawdziwymi
    credentials CLMS vs allowlista hostow (Auth Proxy); ~~E2E kafelkowania
    `exportImage` przy wyniku >16 Mpx~~ — WYKONANE 2026-09-29 (L4: pas
    22 Mpx z 3 kafli, szwy bit w bit, chunked merge dziala), ale realny limit
    serwera ~8 Mpx (K6); 3 przebiegi pelnej suity testow pod rzad (kontrola
    stabilnosci/flakow).
15. ~~**Fala naprawcza bledow z testow na zywo przed wydaniem 0.7.0**~~ —
    **WYKONANE 2026-09-29/30** (sekcja "Fala naprawcza" w "Ostatnia
    sesja"): 21 bledow naprawionych, review domkniety, dokumentacja bez
    not "znany blad", testy na zywo 11 PASS. Odblokowuje pkt 13.

## Backlog

#### Do naprawy — testy na zywych danych 2026-09-29 (przed wydaniem 0.7.0)

Bledy kodu wykryte testami na zywo (sesja 2026-09-29, tabela "Znane bledy"
wyzej). **Wszystkie naprawione w fali 2026-09-29/30** (commity `6c46224..`,
dowody failing-before/passing-after w `docs/research/2026-09-29-fala-naprawcza/impl-*.md`,
decyzje D1-D12 w `decisions.md`). Linie kodu ponizej wg HEAD SPRZED naprawy
(fala dokumentacji 2026-09-29) — nieaktualne, zachowane jako opis objawu.
Raporty: `docs/research/2026-09-29-live-e2e-i-audyt-docs/<raport>`. Oznaczenia wag:
K = wysoki/krytyczny (zle dane po cichu), S = sredni (odpornosc/UX),
N = niski, H = hipoteza.

- [x] **K1** (KRYTYCZNY, sprzed fal — LAZ od 2026-06-24) — discovery WFS
      wysyla `BBOX` w kolejnosci (E, N), a `urn:ogc:def:crs:EPSG::2180`
      wymaga (N, E); envelope kafla jest czytany tak samo odwrotnie, wiec
      filtr przeciecia przechodzi, a kafle pochodza z miejsca o zamienionych
      wspolrzednych (Spytkowice -> Lubuskie, 426 km; przyklad LAZ
      z dokumentacji z bboxem `530000,382000,...` szuka ~209 km dalej,
      a z godlem `N-34-130-D-d-2-4` — ~370 km). Kod:
      `providers/pl/gugik_laz.py:363-369` (zapytanie), `:464-465`
      (envelope), `:482-497` (`_intersects`). Raport:
      `L1-centrum-produkty-report.md` (BUG-L1-1); errata ADR-021.
      Przy naprawie: komentarz `gugik_laz.py:363-365` ("... Verified live.")
      jest falszywy; usunac ostrzezenie K1 z pomocy `--product`
      (`cli/_parser.py:176-177`) i noty "znany blad K1" z dokumentacji.
- [x] **K2** (WYSOKI, etap 1 + ADR-027) — przypieta operacja S-JTSK ->
      ETRS89 to EPSG:4829 (obszar uzycia: Slowacja, 0,5 m), a w Czechach
      wlasciwa jest EPSG:1622 (1,0 m): tresc CZ po reprojekcji przesunieta
      do ~5 m (roznica EPSG:1622 - EPSG:4829 policzona pyproj: 0,1-1,0 m
      na Morawach — Zlin 0,14, Brno 0,98, Ostrawa 1,04 m — do ~5,0 m na
      zachodzie — kafel `302_5550`; wzdluz granicy PL-CZ 1,1-3,4 m; na zywo
      Karkonosze: 2,3 m
      wobec NMT GUGiK 1 m, z EPSG:1622 — 0,38 m), sidecar deklaruje 0,5 m;
      dotyczy kafli TM33, `--target-crs` CZ, wycinka PL -> EPSG:5514
      i `bbox_to_crs`; diagnoza ADR-024 (1,25/4,92 m "bledu serwera")
      najpewniej bledna. Kod:
      `transform/crs.py:192` (`TransformerGroup` bez `area_of_interest`),
      `:236` (`min` po dokladnosci), `KNOWN_PATHS`;
      `providers/cuzk/dmr.py` (`_HORIZONTAL_POLICY`, `bbox_to_crs`).
      **Wymaga odmrozenia toru CZ (ADR-024) — decyzja uzytkownika.** Raport:
      `L4-pogranicze-cz-report.md` (BUG-L4-1), `L2-wycinki-siatka-report.md`
      (BUG-L2-4); errata ADR-024. Przy naprawie: komunikat
      `cli/download_cmd.py:1643-1644` ("tryb godlowy dostarcza dane natywne
      1:1" przy godle CZ z `--target-crs`) jest falszywy dla TM33 (warp
      5514 -> 3045); nieaktualne komentarze `providers/cuzk/dmr.py:86-88`
      ("Znane operacje z Krovaka ... maja 0,5 m"), `transform/crs.py:142-149`
      (`KNOWN_PATHS` 2180 -> 5514: "Inverse of S-JTSK to ETRS89 (3)", 0,5 m)
      i `:159` (Bpv->EVRF2007 "+0,12..+0,14 m"; zmierzone 0,11-0,15 m);
      "5514->3045 przesuwa tresc o 1,25 m" w `providers/cuzk/dmr.py:55-56`
      i `:271` — diagnoza ADR-024 do weryfikacji razem z K2. Zdanie o serwerze
      gubiacym datum shift przy `imageSR=2180` (~135 m; `transform/crs.py:134-140`,
      `providers/cuzk/dmr.py:55`, `:270-271`) pozostaje prawdziwe.
- [x] **K3** (WYSOKI, sprzed fal) — zerwane zapytanie o nowsza warstwe
      skorowidza -> po cichu URL starszej kampanii (NMT/NMPT/orto; LAZ
      pomija caly rocznik); arkusz zostaje w cache (`skip_existing`) i trafia
      do kolejnych wycinkow, a sidecar nie niesie URL-a ani daty kampanii;
      dwa przebiegi `--force` tego samego wycinka roznily sie w 21 % pikseli
      (do 4,2 m; wydmy do 5,2 m); zgloszone tez przez Hydrograf (92 arkusze
      Opolskiego). Kod: `providers/pl/gugik.py:643-647` (`RequestException`
      -> `continue`), `:604-622` (pierwszy znaleziony URL wygrywa bez
      sprawdzenia bledow nowszych warstw); LAZ
      `providers/pl/gugik_laz.py:385-388`. Raport:
      `L2-wycinki-siatka-report.md` (BUG-L2-1), `L3-morze-report.md` (B2),
      `L5-pogranicze-de-report.md` (B5), `L1-centrum-produkty-report.md`
      (BUG-L1-5).
- [x] **K4** (WYSOKI, sprzed fal) — wybor URL arkusza: pierwszy URL
      zawierajacy godlo jako podciag, bez wzgledu na rozdzielczosc, date
      i zasieg — plik 0,5 m jako "1 m" (Szczecin: wycinek w 0,5 m, jeden
      w 100 % nodata z kodem 0), w warstwie zbiorczej najstarsza kampania
      (2019 zamiast 2023; orto — zdjecie z 2003), godlo PL-2000 dostaje po
      cichu arkusz PL-1992 (lista `--system 2000`: kod 0, 0 % pokrycia),
      a remedium `--system 2000` z komunikatu PL-2000 daje arkusz-dziecko
      1:2000; plik PL-2000 z fallbacku zostaje w segmencie PL-1992 i blokuje
      kolejne wycinki. Kod: `providers/pl/gugik.py:599-622` (regex, podciag
      `:607`, fallback `:612-622`), orto `providers/pl/gugik_orto.py:376-384`.
      Raport: `L2-wycinki-siatka-report.md` (BUG-L2-2, BUG-L2-3),
      `L1-centrum-produkty-report.md` (BUG-L1-3, BUG-L1-4). Przy naprawie:
      remedium w komunikacie `download/cutout.py:306-311` ("pobierz obszar
      jako arkusze ..., np. z --system 2000") prowadzi dzis do arkusza-dziecka
      — poprawic razem z wyborem pliku.
- [x] **K5** (WYSOKI, sprzed fal) — `--product orto` pobiera wariant CIR
      zamiast RGB (w kampaniach 2024/2025 wpis CIR poprzedza RGB); sidecar
      nie ma koloru ani URL-a. Kod: `providers/pl/gugik_orto.py:376-384`
      (brak wyboru po `kolor`/`aktualnosc`). Raport:
      `L1-centrum-produkty-report.md` (BUG-L1-2). Przy naprawie: usunac
      ostrzezenie K5 z pomocy `--product` (`cli/_parser.py:176-177`).
- [x] **K6** (WYSOKI dla bbox CZ, etap 1) — realny limit `exportImage` CUZK
      to ~8 Mpx na zapytanie (deklarowane 15000 x 4100), a klient tnie kafle
      dopiero, gdy wymiar przekroczy 15000 x 4100 px: obszar CZ 2 m zblizony
      do kwadratu wiekszy niz ~5,5 x 5,5 km (albo np. 10 x 5 km wydluzony
      W-E) konczy sie HTTP 500; pas N-S szerokosci do ~3,6 km przechodzi
      (kafle maja najwyzej 4100 px wysokosci; 3,6 x 24,6 km = 3 kafle po
      7,4 Mpx; mechanizm kafli dziala: 22 Mpx, szwy bit w bit). Kod:
      `providers/cuzk/client.py:36-37` (`MAX_EXPORT_WIDTH/HEIGHT`), `:142`
      (warunek tylko per wymiar),
      `_tile_grid` (brak budzetu pikseli). **Wymaga odmrozenia toru CZ
      (ADR-024) — decyzja uzytkownika.** Raport: `L4-pogranicze-cz-report.md`
      (BUG-L4-2).
- [x] **S1** (SREDNI, sprzed fal; skutek zaostrzony przez R5) — zapytania
      skorowidza GetFeatureInfo bez ponowien i bez wspolnej sesji (nowe
      polaczenie per arkusz): przy zrywanych polaczeniach GUGiK wycinki
      padaja (Hel CLI 4/4, Karkonosze 3/3; ta sama biblioteka na jednej
      sesji keep-alive z `Retry`: 72/72 OK; czesc zerwan mogla wynikac z 9
      agentow z jednego IP). Kod: `providers/pl/gugik.py:541`
      (`self._session or requests.Session()`), `:594` (`session.get` bez
      ponowien), `:300` (GetCapabilities). Raport: `L3-morze-report.md`
      (B1), `L5-pogranicze-de-report.md` (B3), `L4-pogranicze-cz-report.md`
      (BUG-L4-4).
- [x] **S2** (SREDNI, sprzed fal) — tryb listy arkuszy (bez `--target-crs`)
      bez tolerancji R5: morze/granica = kod 1; `--workers 1` przerywa na
      pierwszym arkuszu bez danych (zmierzone: 0 plikow, gdy byl pierwszy na
      liscie); `--workers > 1` zglasza tylko
      pierwszy blad (moze zgubic sygnal "niepewny, ponow"); pod `auto`
      mylace "nie pobrano danych z PL", choc arkusze sa na dysku. Kod:
      `cli/download_cmd.py:863-919` (`_download_godlo_list`: petla
      sekwencyjna `:869`, `raise` w puli `:918-919`), `:540-550`
      (`_dispatch_area`, komunikat z samego kodu wyjscia), `:1159-1161`.
      Raport: `L3-morze-report.md` (B3), `L5-pogranicze-de-report.md`
      (B1, B2), `L6-inne-granice-report.md` (BUG-1, BUG-1b),
      `L4-pogranicze-cz-report.md` (BUG-L4-3).
- [x] **S3** (SREDNI, etap 1) — `--country auto` po cichu przycina bbox do
      prostokata kraju (np. na zachod od 14,07°E, na polnoc od 54,90°N;
      pozostale krawedzie poszerzone o 40-110 m) — inny zasieg i nazwa
      pliku niz zadanie, bez `Info:`. Kod: `cli/download_cmd.py:284-344`
      (`_country_bbox`, przyciecie `:322-327`), wolane w `_dispatch_area`
      `:517`. Raport: `L5-pogranicze-de-report.md` (B4),
      `L3-morze-report.md` (B5).
- [x] **S4** (SREDNI, sprzed fal) — NMPT EVRF2007: lista warstw w kodzie
      nieaktualna (2025..2022iStarsze wobec 2026..2023iStarsze), a kazde
      pobranie drukuje ostrzezenie. Gdy GetCapabilities zawiedzie, dwie
      zaszyte warstwy nie istnieja (`LayerNotDefined` = awaria warstwy):
      arkusze z edycja w 2025/2024 nadal sie pobieraja (majace takze edycje
      2026 — po cichu te starsza), a arkusz spoza nich (tylko w 2026 i/lub
      2023iStarsze, np. `M-34-76-A-a-1-1`, a takze arkusz bez danych — morze,
      granica) konczy sie "brak pokrycia niepewny" (symulacja offline
      2026-09-29, przeglad fali dokumentacji). Kod:
      `providers/pl/gugik_nmpt.py:83-86`. Raport:
      `L1-centrum-produkty-report.md` (BUG-L1-9).
- [x] **S5** (SREDNI, fala review max — R1) — arkusze 5 m kampanii 2022
      (okolice Krakowa) maja rozne fazy siatki -> wycinek EPSG:2180 bierze
      wartosc z sasiedniego piksela (do 0,88 px) i ma 766 px nodata tam, gdzie
      dane sa; komunikat "najblizszym sasiadem" nieprawdziwy (1 m: jedna
      faza k + 0,5 w 84 arkuszach; 5 m w cache Hydrografu i w Lebie:
      5k + 2,5). Kod: `transport/mosaic.py:324` (`merge` przy zrodlach poza
      siatka), `:265-271` (komunikat `logger.warning` "... przepisana
      najblizszym sasiadem" — poprawic razem z naprawa). Raport:
      `L1-centrum-produkty-report.md` (BUG-L1-7), `L2-wycinki-siatka-report.md`
      (S24).
- [x] **N1** (NISKI, sprzed fal) — puste katalogi po arkuszach bez danych
      (`mkdir` przed zapytaniem skorowidza; `prune_empty_dirs` sprzata tylko
      `bbox/`). Kod: `providers/pl/gugik.py:455`. Raport:
      `L3-morze-report.md` (B4), `L5-pogranicze-de-report.md` (B6),
      `L4-pogranicze-cz-report.md` (BUG-L4-7).
- [x] **N2** (NISKI, etap 1 / fala) — wynik w 100 % nodata przyjmowany jako
      sukces bez komunikatu (plik CZ nad DE/PL w prostokacie CZ; wycinek PL,
      gdy pobrane arkusze nic nie wnosza). Kod: `download/cutout.py:609`
      (sprawdzane tylko `sheet_paths`), tor CZ w `cli/download_cmd.py`
      (`_cz_download_bbox`). Raport: `L4-pogranicze-cz-report.md`
      (BUG-L4-5, U4), `L5-pogranicze-de-report.md` (H).
- [x] **N3** (NISKI, etap 1) — natywny wycinek CZ (EPSG:5514, jedno
      zapytanie) ma piksel 2,0004 m zamiast 2 m (bbox bez dociagniecia do
      calkowitej liczby pikseli). Kod: `providers/cuzk/client.py:139-147`.
      Raport: `L4-pogranicze-cz-report.md` (BUG-L4-6).
- [x] **N4** (NISKI, fale) — arkusze pominiete (juz na dysku) nie dostaja
      `extra.parent_request` nowego zadania; przy pominietym wycinku
      `PlCutoutResult.missing_sheets == ()` mimo dziur w rastrze (lista tylko
      w sidecarze). Kod: `download/manager.py:329`, `:516`, `:548` (skip
      przed `_write_sidecar`), `download/cutout.py:568`, `:714`. Raport:
      `L1-centrum-produkty-report.md` (BUG-L1-6),
      `D1-docs-uzytkownik-report.md` (ID 5).
- [x] **N5** (NISKI, sprzed fal) — testy `pytest -m live` (8) niczego nie
      sprawdzaja: odpytuja nieistniejaca warstwe i asertuja tylko HTTP 200.
      Kod: `tests/test_pl2000_verification.py:456-457`, `:474`, `:482`.
      Raport: `L1-centrum-produkty-report.md` (BUG-L1-10).
- [x] **N6** (NISKI, sprzed fal) — `MetadataCache` nie jest podlaczony
      w zadnym torze PL (CLI, `DownloadManager`, `download_pl_cutout`:
      `_cache is None`). Kod: `cli/download_cmd.py:86`,
      `download/manager.py:211`, `download/cutout.py:572`, `:705`. Raport:
      `D2-docs-architektura-report.md` (D2-01), `L3-morze-report.md`.
- [x] **N7** (NISKI, sprzed fal) — LAZ: przy awarii sieci komunikat
      "No LAZ tiles found" zamiast bledu sieci (a przy czesciowej awarii
      wynik niepelny z kodem 0). Kod: `cli/download_cmd.py:1324-1326`,
      `providers/pl/gugik_laz.py:385-388`. Raport:
      `L1-centrum-produkty-report.md` (BUG-L1-8).
- [x] **N8** (NISKI, sprzed fal) — sidecar pliku PL-2000 deklaruje
      `horizontal_crs` EPSG:2180 (pole z kanalu deskryptora, nie z pliku);
      dotyczy tez kafli LAZ `PL-2000:*`. Kod: `sources/sidecar.py:112`,
      `sources/registry.py:77`. Raport: `L1-centrum-produkty-report.md`
      (BUG-L1-11), `L2-wycinki-siatka-report.md` (BUG-L2-3).
- [x] **N9** (NISKI, wydajnosc, fala review max) — oszacowanie miejsca na
      dysku kosztuje ~7 ms na arkusz nieobecny w cache; wolajacy, ktory sam
      wola `estimate_pl_cutout_bytes` przed `run_pl_cutout`, placi dwa razy
      (13-21 % czasu duzego wycinka). Kod: `download/cutout.py:482`
      (`estimate_pl_cutout_bytes`), `:581` (`check_pl_cutout_disk_space`
      w `run_pl_cutout`). Raport: `L7-duzy-wycinek-report.md`.
- [x] **H1** (hipoteza — POTWIERDZONA i naprawiona) — regex URL skorowidza
      `url:"(https://opendata[^"]+\.asc)"` pomija `.ASC` wielkimi literami
      (warstwa `SkorowidzeNMT2022iStarsze` ma takie rekordy); arkusz, ktorego
      JEDYNY rekord ma `.ASC`, zostalby uznany za brak danych. Kod:
      `providers/pl/gugik.py:599-602`. Raport:
      `L5-pogranicze-de-report.md` (H1).

#### Backlog ogolny (etapy i funkcje)

- [x] Pokrycie testami do 80% (~84%, 990 testow)
- [x] NMPT provider (GugikNmptProvider)
- [x] Ortofotomapa provider (GugikOrtoProvider)
- [x] CLI --product {nmt,nmpt,orto}
- [x] PL-2000 godlowanie (Parser2000, auto-detekcja, CLI)
- [x] Weryfikacja BBox PL-2000 z realnymi danymi GUGiK (67 testow)
- [x] Pobieranie rownolegle (ThreadPoolExecutor, --workers)
- [x] Cache metadanych (SQLite WAL, TTL 7d, prune)
- [x] Mozaikowanie arkuszy NMT (PL) — WYKONANE 2026-08-28 (ADR-027: wycinek
      `--bbox`/`--geometry` z `--target-crs`), poprawione 2026-09-28 (fala
      review max: siatka arkuszy, R5, API biblioteki `download_pl_cutout`);
      scalanie transgraniczne PL+CZ w jedna powierzchnie — decyzja
      uzytkownika R6 (2026-09-28): backlog etapu 2 Kartografa (wczesniej
      zapisane jako "zadanie Hydrografa")
- [x] Ujednolicenie interfejsow providerow (BaseProvider vs LandCoverProvider)
      (etap 0: DataSourceProvider)
- [x] Etap 0 — architektura zrodel wielokrajowych (deskryptory, sidecar,
      transform/crs.py, transport/, providers/pl/, podzial CLI)
- [x] Etap 1 — NMT Czechy: CUZK DMR 5G/4G (`providers/cuzk/`, `ParserTM33`,
      `--country`/`--target-crs`/`--vertical-crs`) — zmergowany do develop
      2026-08-12 (fast-forward do 0738ae0, galaz feature usunieta)
- [ ] Etap 2 — DMP/Orto/LAZ CZ, wielokat granicy administracyjnej CZ
      (zamiast prostokatnej obwiedni), ujednolicenie
      `extra.parent_request.bbox_crs` miedzy trybami jawny/auto, scalanie
      PL+CZ w jedna powierzchnie przygraniczna (R6, 2026-09-28)
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
      innego arkusza (Minor) — log podniesiony do `warning` 2026-09-28
      (cc10773); zostaje weryfikacja zasiegu przy `FEATURE_COUNT>1` -> K4
      (wybor pliku arkusza, testy na zywo 2026-09-29).
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
- [x] A1-9 — rozdzielenie katalogow PL-2000 — WYKONANE 2026-08-28 (ADR-026,
      segmenty `pl_2000_*`); zmiana ukladu katalogow istniejacych uzytkownikow
      przyjeta swiadomie jako BREAKING 0.7.0 (`skip_existing` polega na
      sciezkach, wiec stare pliki przestaja byc widziane jako pobrane;
      historycznie: wspolny `nmt_<res>/`).
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
- [x] E2E kafelkowania `exportImage` (wynik >16 Mpx, sciezka chunkowana
      `mosaic_and_crop(dst_path=...)`) — WYKONANE na zywo 2026-09-29 (pas
      22 Mpx, szwy bit w bit); realny limit serwera ~8 Mpx -> K6.
- [ ] `mosaic_and_crop(dst_path=...)` moze zostawic obciety plik wynikowy,
      gdy `merge` padnie w trakcie zapisu (brak `unlink` w obsludze bledu) —
      jedyne wywolanie produkcyjne (`export_image`) sprzata po sobie samo,
      wiec dotyczy to tylko bezposrednich konsumentow biblioteki.
- [ ] `core/geometry.py`: bajt kolejnosci WKB spoza `{0, 1}` nie jest
      walidowany — zamiast `None` (odrzucenie geometrii) daje smieciowe
      wspolrzedne z blednym rozpakowaniem struct.

#### Backlog etapu 2 — dopisany przy ukladzie data/ i target-crs PL (2026-08-28)

- [ ] `find_downloaded(product=, bbox=, vertical_crs=)` — inwentarz pobran
      po sidecarach (klucz: `parent_request` / przeciecie bbox)
- [ ] `--target-crs` dla `nmpt`/`orto` (razem z odpowiednikami CZ etapu 2)
- [ ] Wycinek PL dla `--system 2000` (mozaika miedzystrefowa: warp per
      strefa 2176-2179 przed sklejeniem)
- [ ] Ujednolicenie `parent_request.bbox_crs` miedzy trybami jawny/auto
      (pozycja istniejaca — powiazac z `find_downloaded`)
- [ ] `harmonize_dem(files, target_crs, resolution)` na bazie
      `kartograf.transform.crs.PinnedTransform` (NIE golego pyproj — lekcja
      ADR-024), wejscie z sidecarow — po R6 (2026-09-28) kandydat do API
      Kartografa razem ze scalaniem PL+CZ (etap 2), nie tylko nota dla
      Hydrografa; wybor operacji S-JTSK -> K2

#### Backlog po fali review max (2026-09-28)

Rulingi i pelne uzasadnienia: `docs/research/2026-09-28-fala-review-max/`
(`sdd-ledger.md`, `final-review-report.md` sekcja "Triaz ledgera",
`final-rereview-report.md`).

- [ ] **R6 — scalanie PL+CZ** w jedna ciagla powierzchnie przygraniczna
      (wspolna siatka, EVRF2007 po obu stronach, regula zakladki) — etap 2,
      po checkliscie live pkt 12 (h). Razem z tym: podwojna obwiednia, gdy
      uklad zadania = `--target-crs` (bbox i cel EPSG:5514: siatka
      11,51 x 11,51 km zamiast 10 x 10 km).
- [ ] Wycinek PL z arkuszy wydanych przez GUGiK w ukladzie PL-2000 pod
      godlem PL-1992 (reprojekcja per arkusz) — dzis glosny `ValidationError`.
- [ ] Tryby CLI bez `--target-crs` na `DownloadManager.download_sheets`
      (dzis `_download_godlo_list` w trybie rownoleglym rzuca pierwsza
      porazka, pozostale gina) + tolerancja braku pokrycia (`NoCoverageError`)
      poza wycinkiem -> S2.
- [ ] Warp (`warp_to_grid` PL i `_warp_to_grid` CZ): wymiary siatki
      `max(1, round(...))` od naroznika NW — krawedz E/S do 0,5 px od obwiedni
      (E2E: 1,61 m / 0,76 m przy 5 m); skala resamplingu GDAL `XSCALE`/`YSCALE`
      liczona per kawalek — piksele zaleza lekko od zasiegu mozaiki (E2E:
      srednio 2,7 mm, maks. 0,15 m poza szwem; z `XSCALE=YSCALE=1` < 3,2 mm).
      Oba zamrozone do wydania; test porownawczy + checklista live. Na zywo
      2026-09-29: domyslny warp uzywa tez przyblizonego transformatora
      (`tolerance` 0,125 px; przy 5 m do 0,13 m) — ARCHITECTURE 4.3 krok 6.
- [ ] Obwiednia WGS84 z 4 naroznikow takze w
      `core/parser_2000._transform_bbox_to_wgs84` (poludniki osiowe stref) —
      sprawdzic pod katem faktu 8 (pas przy gornej krawedzi na poludniku
      osiowym); `corine`/`soilgrids` licza `transform_bounds(densify_pts=21)`
      (A4-7) — potwierdzic, ze blad jest pomijalny.
- [ ] API wycinka: `download_pl_cutout(provider=, storage=)` addytywnie
      (Hydrograf wstrzyknie wlasny provider/cache; dzis przez trzy kroki —
      obejscie S1/N6 po stronie wolajacego),
      walidacja wstrzyknietej `storage` w `run_pl_cutout`,
      `estimate_pl_cutout_bytes` z rozszerzeniem providera zamiast stalego
      `.asc`.
- [ ] Arkusze spoza siatki wiekszosci: dzis tylko `logger.warning` — dodac
      `extra.off_grid_sheets` + `Warning:` w CLI, jesli pkt 12 (f) pokaze
      mieszane fazy kampanii 1 m. Pkt 12 (f): 1 m — jedna faza (zbedne);
      5 m kampanii 2022 — mieszane fazy i bledna tresc mozaiki -> S5.
- [ ] Z odmrozeniem toru CZ: `bbox_to_crs` z `providers/cuzk/dmr.py` do
      `transform/` (tor PL go importuje) i wspolny helper obwiedni geometrii
      w ukladzie pliku (`_geometry_envelope` / `_resolve_cz_geometry_bbox`);
      ta sama operacja S-JTSK -> K2.
- [ ] Pobranie ASC bez kontroli `Content-Type`: strona bledu HTML z HTTP 200
      zapisana jako `.asc` zostaje w cache — mozaika pada kodem 1, ale kolejne
      przebiegi pomijaja plik jako istniejacy az do recznego usuniecia.
- [ ] Walidacja `--bbox`: NaN/inf przechodza `float()` (wycinek konczy sie
      `ValueError` w barierze `main()` albo mylacym `TransformError`),
      min > max przechodzi prepare/select wycinka.
- [ ] Straz I-2 (raport wyjatku OGC w odpowiedzi 2xx): test "URL wygrywa"
      takze dla odpowiedzi fallbackowej (URL innego arkusza + znacznik OGC);
      ograniczyc regex wyciagu komunikatu (`(.{0,2000}?)</` albo prefiks
      body — patologiczne body 360 KB bez `</` = 49 s).
- [ ] Drobne: komentarz testu "Cieszyn (PL)" w `tests/test_pl_cutout.py`
      (bbox lezy po stronie CZ); `_same_projection` ~25 ms/zrodlo dla `.prj`
      WKT1_ESRI (`lru_cache` po tekscie WKT); WKT1 z `TOWGS84[0,...]`
      odrzucany; testy lustrzane tolerancji przyciagania i remisu siatki;
      podwojne parsowanie lisci w `download_sheets`; komunikat bledu PL-2000
      w bibliotece wspomina flagi CLI (a jego remedium `--system 2000` daje
      dzis arkusz-dziecko -> K4).
