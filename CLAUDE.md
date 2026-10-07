# Instrukcje dla Claude Code

## Opis projektu

Kartograf — narzedzie do pobierania danych przestrzennych: NMT z GUGiK (Polska) i CUZK (Czechy), BDOT10k, CORINE z Copernicus, SoilGrids z ISRIC. Dostepny jako CLI i biblioteka Python. Czesc toolchainu hydrologicznego (Hydrograf, Hydrolog, Kartograf, IMGWTools).

Glowne funkcjonalnosci:
- **NMT (PL)** — pobieranie Numerycznego Modelu Terenu z GUGiK (1m i 5m)
- **NMT (CZ)** — DMR 5G/4G z CUZK (2m i 5m), godlo TM33/SM5 lub bbox, `--country {pl,cz,auto}` (etap 1, v0.7.0-dev)
- **NMPT** — Numeryczny Model Pokrycia Terenu / DSM z GUGiK (1m)
- **Ortofotomapa** — zdjecia lotnicze Standard Resolution (25cm, TIF) z GUGiK
- **LAZ** — chmury punktów LIDAR (dane pomiarowe ALS, .laz) z GUGiK przez WFS
- **BDOT10k** — polska baza pokrycia terenu (15 warstw: 12 PT* + 3 SW*)
- **CORINE Land Cover** — europejska klasyfikacja pokrycia terenu (44 klasy)
- **SoilGrids** — globalne dane glebowe z ISRIC (11 parametrow, 6 glebokosci)
- **HSG** — kalkulacja Hydrologic Soil Groups dla metody SCS-CN

## Srodowisko Python

Uzywaj srodowiska wirtualnego z `.venv`:
- Python: `.venv/bin/python`
- Pip: `.venv/bin/pip`
- Wymagany Python: 3.12+

Zmienne srodowiskowe (opcjonalne):
- `CLMS_CREDENTIALS` — credentials dla Copernicus CLMS API jako JSON string
  (pola `client_id`, `private_key`, `token_uri`, opcjonalnie `key_id`/`user_id`);
  potrzebne do CORINE GeoTIFF. Zmienna dziala na KAZDYM systemie: czyta ja
  wylacznie **podproces auth proxy** (`python -m kartograf.auth.proxy`), ktory
  dziedziczy srodowisko rodzica — glowny proces nie widzi kluczy ani tokenu.
  Kolejnosc zrodel w proxy: `CLMS_CREDENTIALS`, potem (tylko macOS) Keychain
  (service `clms-token`). Bez zadnego z nich `AuthProxyClient.is_available()`
  na non-macOS zwraca False bez uruchamiania podprocesu.
- `KARTOGRAF_DEBUG=1` — pelny traceback zamiast skroconego `Error: ...` z CLI
  (dla kazdego wyjatku docierajacego do bariery `main`, takze `KartografError`)

Bez credentials CLMS: CORINE automatycznie pobiera podglad PNG przez WMS (fallback,
sidecar dostaje `extra.fallback = "wms_png"`). Alternatywa z poziomu biblioteki:
`CorineProvider(clms_credentials={...})` (tryb bezposredni, z pominieciem proxy).

## katalog danych danych (od 2026-10-06)

**Wszystkie dane przestrzenne pobierane przez Claude** (testy na zywo,
weryfikacje E2E, reczne wywolania CLI, dane do analiz) zapisuj na
serwerze sieciowym `<katalog-danych>` — NIE w repo i NIE w `/tmp`.

- Udzial CIFS/SMB `<udzial>`
  zapis dla `claude-agent` (pliki 0640, katalogi 0750); przesyl szybki.
- Domyslne `--output` CLI (`./data`, `./data/landcover`, `./data/hsg`)
  wskazuja na repo — **zawsze podawaj `--output` jawnie**, np.
  `kartograf download N-34-130-D-d-2-4 -o <katalog-danych>/kartograf/data`.
- Uklad katalogow:
  - `<katalog-danych>/kartograf/data/` — kanoniczny uklad `data/`
    (ADR-026), wspolny dla kolejnych sesji (reuzycie pobranych arkuszy);
  - `<katalog-danych>/kartograf/e2e/<RRRR-MM-DD>-<cel>/` — przebiegi
    testow na zywo i weryfikacji (zastepuja dawne `e2e-data/` w repo);
  - wyniki/notatki z przebiegu (raporty `.md`) nadal trafiaja do
    `docs/research/...` w repo — na katalog danych idzie tylko ciezki raster/LAZ/GPKG.
- Cache metadanych `.kartograf_cache.db` (SQLite WAL) **zostaje lokalnie**
  (biezacy katalog = repo, gitignorowany): WAL na udziale sieciowym jest
  zawodny. Uruchamiaj CLI z korzenia repo i kieruj na katalog danych tylko `--output`.
- Montowanie jest `soft`: przy niedostepnosci serwera zapis konczy sie bledem
  I/O (nie wisi). Przed dlugim pobieraniem sprawdz `df -h <katalog-danych>`;
  gdy udzial nie jest zamontowany, zatrzymaj sie i zapytaj uzytkownika
  zamiast pisac lokalnie.
- Testy pytest nie dotycza katalog danych (offline: `tmp_path`; `live`: tylko
  zapytania o metadane, bez plikow) — bez zmian.

## Dokumentacja

**Przeczytaj w kolejnosci:**
1. `docs/PROGRESS.md` — aktualny stan projektu i zadania
2. `docs/SCOPE.md` — zakres projektu (co jest, czego nie ma)
3. `docs/ARCHITECTURE.md` — architektura, kontrakty danych, kanoniczny uklad `data/`
4. `docs/PRD.md` — wymagania produktowe
5. `docs/CHANGELOG.md` — historia zmian per-release
6. `docs/DECISIONS.md` — rejestr decyzji architektonicznych (co i dlaczego)

## Struktura modulow

```
kartograf/
├── __init__.py          # Public API exports
├── exceptions.py        # KartografError, ValidationError, GridMismatchError(ValidationError), DownloadError, NoCoverageError(DownloadError)
├── core/                # Logika bazowa
│   ├── bbox.py             # BBox, validate_bbox, transform_bbox (gesta obwiednia densify 21, cache transformerow, transformer= duck typing), is_czech_crs
│   ├── sheet_parser.py     # SheetParser — parser godel map topograficznych (BBox re-eksportowany z core/bbox.py)
│   ├── parser_2000.py      # Parser2000 — parser godal PL-2000, find_sheets_2000_for_bbox
│   ├── parser_tm33.py      # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045), wzor: Parser2000
│   ├── parser_registry.py  # Rejestr systemow godel (literal SYSTEMS: pl2000, cz_tm33, cz_sm5, fallback pl1992; detect_system/path_parts ze strip(); wzorce CZ_TM33_PATTERN/CZ_SM5_PATTERN); SheetParser/FileStorage delegowane
│   ├── geometry.py         # Czytanie SHP/GPKG, find_sheets_for_geometry, get_overall_bbox
│   └── coverage.py         # Wypukle wielokaty (przeciecie/roznica/bufor) — wybor kafli LAZ (ADR-029)
├── sources/             # Deskryptory zrodel jako dane (zero IO przy imporcie)
│   ├── descriptor.py    # SourceDescriptor + resolve_subdir (szablony {uklad}/{vcrs}, ADR-026), AccessChannel (+endpoint dla silnikow sterowanych deskryptorem), TransportKind, LicenseInfo, CountryProfile
│   ├── registry.py      # Rejestr PL/CZ/EU/GLOBAL — get_source, sources_for, get_country, all_countries, vertical_crs_code, resolve_vertical_crs (rodzina->realizacja)
│   └── sidecar.py       # ResultMetadata, build_metadata (capability=, nodata=), write_sidecar (<plik>.meta.json), read_asc_nodata
├── transform/           # Transformacje CRS i rastrow
│   ├── crs.py           # PinnedTransform, pin datum EPSG:1622/1623 dla S-JTSK, bez ballpark
│   └── raster.py        # warp_to_grid — pojedyncza mozaika lub lista arkuszy (W1)
├── transport/           # Wspolny transport pobierania
│   ├── http.py          # download_to, get_with_retry, make_gugik_session, is_retryable/retry_wait
│   └── mosaic.py        # mosaic_and_crop, check_source_grid (GridMismatchError), has_valid_pixels
├── providers/           # Providery danych (abstrakcje nad API)
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider (NMT), LandCoverProvider (pokrycie terenu)
│   ├── pl/               # Providery polskie (GUGiK, BDOT10k) — landcover_base.py USUNIETY (patrz base.py)
│   │   ├── gugik.py         # GugikProvider — NMT z GUGiK (WCS + OpenData)
│   │   ├── gugik_nmpt.py    # GugikNmptProvider — NMPT/DSM z GUGiK (dziedziczy z GugikProvider)
│   │   ├── gugik_orto.py    # GugikOrtoProvider — Ortofotomapa z GUGiK (BaseProvider)
│   │   ├── gugik_laz.py     # GugikLazProvider — chmury punktów LAZ z GUGiK (WFS, area-based); select_tiles/select_newest_cover
│   │   ├── skorowidz.py     # Rekordy GetFeatureInfo, wybor najnowszego zgodnego z zadaniem, source_info
│   │   ├── bdot10k.py       # Bdot10kProvider — BDOT10k z GUGiK
│   │   └── __init__.py      # create_nmt_provider() — fabryka, jedno miejsce polskich domyslow NMT
│   ├── cuzk/             # Providery czeskie (CUZK) — etap 1 (v0.7.0-dev)
│   │   ├── client.py        # CuzkClient — silnik sterowany deskryptorem (ArcGIS REST: query/export_image + pliki openzu)
│   │   ├── sheets.py         # SheetIndex/SheetInfo — indeks arkuszy SM5/TM33 (KladyMapovychListu), filtr nadmiarowego wyboru
│   │   ├── dmr.py            # CuzkDmrProvider — DMR 5G/4G, transformacja pionowa Bpv->EVRF2007 opcjonalna
│   │   └── __init__.py       # create_dmr_provider() — fabryka, jedno miejsce czeskich domyslow (wzor: pl)
│   ├── corine.py        # CorineProvider — CORINE z Copernicus (CLMS API + WMS)
│   └── soilgrids.py     # SoilGridsProvider — dane glebowe z ISRIC (WCS)
├── cache/               # Cache metadanych
│   └── metadata.py      # MetadataCache — SQLite WAL; record_cache (7d, pozytywny/negatywny), campaigns_cache (7d, lista kampanii arkusza), sheet_cache (30d), thread-safe
├── download/            # Zarzadzanie pobieraniem NMT/NMPT/Orto
│   ├── campaigns.py     # Kampanie GUGiK (ADR-030): CampaignRef (<data>_<id>), format z rekordu, verify_file_format, validate_campaign_args
│   ├── links.py         # Dowiazanie sciezki standardowej do najnowszej kampanii (symlink -> hardlink -> kopia, nigdy wstecz), sidecar standardowy
│   ├── cutout.py        # Wycinek PL --target-crs jako API (ADR-027): R5, GridMismatchError/W1, all_nodata, sheet_sources
│   ├── laz.py           # Kafle LAZ jako API (ADR-029): download_laz_area/run_laz_download, sidecar, failed/superseded w wyniku
│   ├── manager.py       # DownloadManager(campaigns=, min_year=) — arkusze (parallel), status no_coverage, parent_requests, SheetFetch/last_sheet
│   └── storage.py       # FileStorage(vertical_crs=) — segmenty <produkt>/<kraj>_<uklad>_<vcrs> z szablonow deskryptora (ADR-026)
├── landcover/           # Zarzadzanie pobieraniem pokrycia terenu
│   └── manager.py       # LandCoverManager — dispatch do providerow
├── hydrology/           # Obliczenia hydrologiczne
│   └── hsg.py           # HSGCalculator — klasyfikacja USDA, mapowanie HSG
├── auth/                # Autentykacja CLMS (Auth Proxy)
│   ├── proxy.py         # Serwer HTTP izolujacy credentials (subprocess)
│   └── client.py        # Klient singleton, automatycznie uruchamia proxy
└── cli/                 # Interfejs wiersza polecen (podzielony na moduly per komenda)
    ├── _parser.py        # Definicja argparse (top-level + subkomendy)
    ├── parse_cmd.py      # `kartograf parse`
    ├── download_cmd.py   # `kartograf download` (godlo / bbox / geometry / LAZ)
    ├── landcover_cmd.py  # `kartograf landcover` (download / list-sources / list-layers)
    ├── soilgrids_cmd.py  # `kartograf soilgrids` (HSG)
    ├── cache_cmd.py      # `kartograf cache` (stats / clear / path)
    └── commands.py       # Fasada zgodnosci — re-eksport + entry point `main`
```

## Uklad data/ (0.7.0, ADR-026)

`data/<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/...` — np.
`nmt/pl_1992_1m_evrf2007/`, `nmt/pl_2000_1m_evrf2007/`, `nmpt/pl_1992_1m_kron86/`,
`orto/pl_1992/` (RGB; CIR -> `orto/pl_1992_cir/`, B/W -> `orto/pl_1992_bw/`,
E12), `laz/pl_2000_evrf2007/`, `nmt/cz_dmr5g_bpv/` (`pl_1992` vs
`pl_2000` rozstrzyga format godla KAZDEGO pliku; wyjatek: kafle LAZ —
`uklad_xy` kafla (`LazTile.uklad`)). Podkatalog
`<segment>/bbox/<coords>.tif` dostaja wycinki: KAZDE `--bbox`/`--geometry` CZ
oraz `--bbox`/`--geometry` PL **tylko z `--target-crs`** — bez tej flagi PL
zapisuje arkusze w hierarchii godel. Kanoniczna tabela i migracja:
`docs/ARCHITECTURE.md` sekcja 3. `landcover/` bez zmian.

**Kampanie (ADR-030 + errata 2026-10-07):** prawdziwe pliki NMT/NMPT/orto PL
leza WYLACZNIE w `<segment>/kampanie/<data>_<id>/<hierarchia godla>/<godlo>.<ext>`
(+ `.meta.json`; `<data>` = `aktualnosc` rekordu, `<id>` = pierwszy segment
liczbowy nazwy pliku w URL, inaczej `u` + 8 znakow hex `sha1(URL)`).
Sciezka standardowa `<segment>/<hierarchia>/<godlo>.<ext>` jest dowiazaniem do
najnowszej LOKALNEJ kampanii (takze niepelnej); jej sidecar to zwykly plik
z `extra.link` (`symlink`/`hardlink`/`copy`) i `extra.link_target`. Brak
migracji: zwykly plik w sciezce standardowej jest nieznany — pierwsze
uruchomienie `newest` pobiera go ponownie do `kampanie/` i zastepuje
dowiazaniem. Kopiowanie `data/` wymaga `cp -rL`/`rsync -aL`.

## Komendy

Testy sa **offline**: `tests/conftest.py` przewraca kazdy test otwierajacy
gniazdo spoza loopbacku; wyjatek maja tylko testy z markerem `live`.
`pyproject.toml` ich nie odfiltrowuje (`addopts` bez `-m`), wiec domyslne
komendy ponizej podaja `-m "not live"` jawnie.

```bash
# Testy (offline)
.venv/bin/python -m pytest tests/ -v -m "not live"

# Testy z pokryciem (offline)
.venv/bin/python -m pytest tests/ -m "not live" --cov=kartograf --cov-report=html

# Testy sieciowe (live)
.venv/bin/python -m pytest tests/ -m live   # 16 testow sieciowych — tylko swiadomie

# Linter
.venv/bin/python -m ruff check kartograf/ tests/

# Formatowanie
.venv/bin/python -m ruff format kartograf/ tests/

# Sprawdzenie formatowania (bez zmian)
.venv/bin/python -m ruff format --check kartograf/ tests/

# Type checking
.venv/bin/python -m mypy kartograf/

# CLI
kartograf --help
kartograf parse N-34-130-D-d-2-4
kartograf download N-34-130-D-d-2-4
kartograf download N-34-130-D-d-2-4 --product nmpt
kartograf download N-34-130-D-d-2-4 --product orto
# LAZ: WFS EPSG:2180 uzywa kolejnosci osi (N,E); discovery sprawdza przeciecie kafli;
# domyslnie najnowszy kafel per obszar (starsze pokryte -> Info:), --year wybiera rocznik
kartograf download N-34-130-D-d-2-4 --product laz
kartograf download N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12
kartograf download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86
kartograf download N-34-130-D --scale 1:10000 --resolution 5m --workers 8
# kampanie GUGiK (ADR-030): domyslnie `newest`; `all` pobiera kazda kampanie arkusza
# do <segment>/kampanie/, `--min-year` odcina kampanie z `aktualnosc` sprzed roku
kartograf download N-34-130-D-d-2-4 --campaigns all
kartograf download N-34-130-D-d-2-4 --min-year 2024
kartograf download --bbox 530000,382000,533000,386000 --campaigns all --min-year 2022
kartograf download --bbox 530000,382000,533000,386000 --product laz --campaigns all   # LAZ bez dedup ADR-029
kartograf download --geometry area.shp
kartograf download --geometry area.gpkg --layer catchments
kartograf parse 6.179.12.20
kartograf download 6.179.12.20
kartograf download --bbox 6500000,5895000,6508000,5900000 --bbox-crs EPSG:2177 --system 2000
kartograf download 302_5550 --country cz                      # DMR 5G (TM33), 2m, Bpv (kafel ~93 % nodata — Niemcy)
kartograf download CTES96 --resolution 5m                     # DMR 4G (SM5), kraj auto z godla
# bbox przygraniczny --country auto -> osobne pliki PL i CZ, wspolny extra.parent_request
# (bez --vertical-crs: PL w EVRF2007, CZ w Bpv)
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto
# reprojekcja CZ -> EPSG:2180, lokalna przypieta operacja (tylko --bbox/--geometry, nie godlo)
kartograf download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180
kartograf download 302_5550 --country cz --vertical-crs EVRF2007  # Bpv -> EPSG:5621 (przypieta operacja)
# wycinek PL: jeden scalony GeoTIFF (mozaika arkuszy + pinned warp)
kartograf download --bbox 530000,382000,533000,386000 --country pl --target-crs EPSG:5514
# pogranicze jedna komenda: dwa wycinki (PL+CZ) w tym samym ukladzie, wspolny parent_request
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --target-crs EPSG:2180 --vertical-crs EVRF2007
# Bboxy w EPSG:5514 (Krovak) sa ujemne na terytorium CZ — uzyj `--bbox=...` (bez spacji),
# inaczej argparse odczyta wartosc jako nieznana flage:
kartograf download "--bbox=-447000,-1114000,-446000,-1113000" --bbox-crs EPSG:5514 --country cz --resolution 5m
kartograf landcover download --source bdot10k --teryt 1465
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc
kartograf soilgrids hsg --godlo N-34-130-D --stats
kartograf landcover list-sources
kartograf landcover list-layers --source soilgrids
kartograf cache stats
kartograf cache clear
kartograf cache path
```

## Workflow sesji

### Poczatek sesji
1. Przeczytaj `docs/PROGRESS.md` — sekcja "Ostatnia sesja"
2. `git status` + `git log --oneline -5`
3. Sprawdz na ktorej jestes galezi (`git branch --show-current`)

### W trakcie sesji
- Commituj czesto (male zmiany)
- Aktualizuj `docs/CHANGELOG.md` na biezaco
- W razie watpliwosci — pytaj

### Koniec sesji
**OBOWIAZKOWO zaktualizuj** `docs/PROGRESS.md`:
- Co zostalo zrobione
- Co jest w trakcie (plik, linia, kontekst)
- Nastepne kroki

### Git Workflow

**Galecie:**
- **main** — stabilna wersja (tylko merge z develop)
- **develop** — aktywny rozwoj (ZAWSZE pracuj na tej galezi)

**Commity:** Conventional Commits (`feat(parser): ...`, `fix(download): ...`, `docs(readme): ...`)

## Specyfika projektu

### Zaleznosci zewnetrzne
- **requests** >= 2.31.0 — HTTP client (wymagane)
- **pyproj** >= 3.6.0 — transformacje CRS (wymagane)
- **PyJWT[crypto]** >= 2.8.0 — OAuth2 JWT dla CLMS API (wymagane)
- **rasterio** >= 1.3.0 — przetwarzanie rastrow GeoTIFF (wymagane)
- **numpy** >= 1.24.0 — operacje na tablicach (wymagane)
- **pyshp** >= 2.3.0 — czytanie plikow Shapefile (wymagane)

### Integracje
- Kartograf jest uzywany przez **Hydrograf** jako zrodlo danych GIS (NMT, Land Cover)
- Kartograf jest uzywany przez **Hydrolog** opcjonalnie (HSGCalculator, SoilGridsProvider)
- Kartograf NIE zawiera obliczen hydrologicznych (poza HSG) — to zadanie Hydrolog
- Kartograf NIE zawiera danych obserwacyjnych — to zadanie IMGWTools

### Ograniczenia
- Pobieranie rownolegle: ThreadPoolExecutor; domyslnie 4 workery w CLI
  (--workers), 1 w bibliotece (`DownloadManager(max_workers=1)`)
- NMT 5m (PL) dostepne tylko w ukladzie EVRF2007
- WCS (download_bbox) niedostepne dla NMT 5m — tylko arkusze OpenData
- WCS (download_bbox) NMT 1m dziala **wylacznie** z `vertical_crs="KRON86"` —
  endpoint EVRF2007 (`DigitalTerrainModelFormatTIFFEVRF2007`) zwraca 404 od
  2026-08, wiec deskryptor `pl.gugik.nmt_1m` deklaruje kanal WCS tylko dla
  `EPSG:9650`, a `GugikProvider.download_bbox` pod EVRF2007 konczy sie
  `ValidationError` przed wyjsciem w siec (WCS NMPT nie jest tym objety).
  Wysokosci EVRF2007 z bboxa: `--bbox` w CLI (rozwijane na arkusze OpenData)
  albo jeden GeoTIFF z arkuszy: `--target-crs` / `download_pl_cutout`
- CORINE GeoTIFF wymaga OAuth2 credentials w CLMS — bez nich fallback na PNG (WMS)
- SoilGrids: tylko WGS84 bbox (transformacja z EPSG:2180 automatyczna)
- Timeouty domyslne: 30 s dla NMT/NMPT (GUGiK) i discovery WFS w LAZ;
  60 s dla Ortofoto, kafli LAZ, CORINE (bbox/godlo), CUZK i SoilGrids przez
  godlo; 120 s dla BDOT10k (wszystkie tryby; `Bdot10kProvider.DEFAULT_TIMEOUT`,
  zapytanie TERYT 30 s) oraz SoilGrids przez bbox i HSG (CORINE i SoilGrids
  przez TERYT to `NotImplementedError`); GetCapabilities skorowidza GUGiK
  dziedziczy timeout providera (30 s NMT/NMPT, 60 s orto)
- Max 3 proby retry (nie konfigurowalne); ponawiane sa tylko bledy sieci,
  HTTP 429 i 5xx — inne 4xx (np. 404) koncza od razu z
  `DownloadError.status_code`; `Retry-After` wydluza przerwe (max 60 s).
  Jedno miejsce: `transport/http.py` — pliki wszystkich providerow
  (GUGiK NMT/NMPT/orto/LAZ/BDOT10k, CORINE, SoilGrids, CUZK) pobiera
  `download_to` (zapis atomowy `os.replace`), zapytania `get_with_retry`
  (skorowidz, WFS LAZ, TERYT BDOT10k, `CuzkClient.query`); backoff jeden
  dla wszystkich: 2 s, potem 4 s (`backoff_delay`, od 2026-10-07)
- Kazde udane pobranie tworzy sidecar `<plik>.meta.json` (metadane CRS/licencja/nodata)
- `download_sheet()` zwraca `Path` (arkusz 1:10000 albo godlo PL-2000) albo
  `list[Path]` (godlo PL-1992 grubsze niz 1:10000 — rozwijane do 1:10000);
  `download_hierarchy()` zawsze `list[Path]` + podsumowanie w `last_result`
- `find_sheets_for_bbox()`/`find_sheets_for_geometry()`: stykajace sie krawedzie
  NIE sa przecieciem (liczy sie dodatnie pole), wiec bbox rowny arkuszowi
  w EPSG:4326 zwraca tylko jego arkusze (bbox w EPSG:2180 idzie przez szersza
  obwiednie WGS84 — obwiednia arkusza 1:10000 daje 9 godel); nieznana wartosc
  `system=` to `ValidationError`
- HSG: progi tekstur to kanoniczny trojkat USDA, a `TEXTURE_TO_HSG` swiadomie
  odbiega od TR-55 (`sandy_loam`=B, `clay_loam`/`silty_clay_loam`=C) — ADR-025
- **CZ (CUZK, etap 1):** tylko `nmt` (DMR 5G/4G); `nmpt`/`orto`/`laz`
  pozostaja etapem 2. DMR 5G (godlo TM33) ma 2 m, DMR 4G (SM5) ma 5 m.
  `exportImage` pobiera natywne EPSG:5514: sufit uslugi 15000 x 4100 px,
  realna bariera ~8 Mpx; klient kafelkuje z budzetem 4 Mpx na zapytanie,
  kotwica NW, szwy bit w bit. Piksel ma dokladnie 2 m/5 m (bbox wyniku moze
  sie roznic od zadania o <= pol piksela na krawedziach E/S).
  `--target-crs` i kafel TM33 reprojektuje lokalnie przypieta operacja:
  krok S-JTSK -> ETRS89 wybiera EPSG:1622/1623 (1,0 m), nie slowacka
  EPSG:4829. Pliki sprzed poprawki z `S-JTSK to ETRS89 (3)` w sidecarze
  zostaja bez automatycznej przebudowy: CLI wypisuje `Info:` przy skip;
  odswiez je `--force`. `KRON86` dla CZ jest nieosiagalny, uzyj EVRF2007.
  CZ `--bbox` zawsze daje jeden wycinek; PL bez `--target-crs` liste arkuszy.
  Kafel TM33 to warp na siatke EPSG:3045, arkusz SM5 jest 1:1.
  `--target-crs` z godlem PL/CZ jest bledem.
  Obwiednie krajow sa prostokatne (ADR-023), nie granice wielokatowe:
  `auto` moze zapytac CUZK nad Polska/Saksonia i GUGiK w Czechach;
  wynik w calosci nodata daje `Warning:` na stderr i kod 0.
- **`--country auto`** dla bbox/geometrii odpytuje kazdy kraj z
  przecinajaca sie prostokatna obwiednia: oddzielne pliki ze wspolnym
  `extra.parent_request` (bez scalania PL+CZ, R6).
  Opcje tylko-PL (`--product nmpt|orto`, `--system`, `KRON86`, `1m`)
  rozstrzygaja nakladajacy sie obszar do PL z `Info:`; LAZ nadal wymaga
  jawnego `--country pl` w obszarze spornym.
  Przyciecie pod `auto` drukuje `Info:` tylko, gdy naprawde ogranicza
  pobieranie: `--geometry` bez `--target-crs` wyznacza arkusze PL z calej
  geometrii, wiec nie drukuje Info dla PL ani o utracie obszaru pobieranego
  przez PL; czesc CZ nadal bywa przycinana. Nietkniete krawedzie PL pozostaja
  oryginalne. Wycinki PL/CZ niosa przyciety zasieg w nazwie pliku i
  `request.bbox`; tryb listy `--bbox` wyznacza arkusze z przycietego bboxa,
  a ich sidecary maja `request.godlo`. Oryginalne zadanie zachowuje
  `extra.parent_request`. Jawne `--country pl` nie przycina.
  Bbox calkowicie poza obwiedniami = `Error:` kod 1 bez sieci.
  Kod 0 oznacza sukces co najmniej jednego kraju; przy porazce drugiego
  CLI daje `Warning:`, kod 1 gdy zaden kraj nie dostarczy wyniku lub
  `--country` bylo jawne. `Info:`/`Warning:` ida na stderr mimo `-q`.
  `--target-crs` dziala dla obu krajow, nie rozstrzyga wyboru kraju.
- **Kampanie (ADR-030 + errata 2026-10-07):** `--campaigns {newest,all}`
  (domyslnie `newest`), `--min-year RRRR` (1900..2100, inaczej `Error:`
  bez sieci); tylko PL (GUGiK) — CZ zawsze biezaca mozaika.
  `newest` = regula ADR-028, ale PRZY KAZDYM uruchomieniu rozwiazuje
  najnowszy rekord (siec, gdy cache `record_cache`/`campaigns_cache` 7 d
  wygasl) i pobiera tylko brakujace kampanie; ponowne uruchomienie nie jest
  juz "bez sieci" po wygasnieciu cache. `all` = KAZDY rekord po twardym
  filtrze ADR-028 ze wszystkich warstw, bez limitu liczby kampanii
  (`logger.info` z liczba kampanii arkusza). `--min-year` = granica na roku
  `aktualnosc` (nie `dt_pzgik`; rekord bez ustalonego roku nie spelnia
  granicy); `newest` z najnowsza kampania starsza od granicy =
  `NoCoverageError` z data tej kampanii (lista/hierarchia: status
  `no_coverage`). Rok z nazwy warstwy sluzy TYLKO w `all` do pominiecia
  zapytania warstwy (gorny rok < granicy); `Starsze` zawsze odpytywane,
  o wyniku decyduje `aktualnosc`. `campaigns_cache` po skanie czesciowym
  (`--min-year`) obsluguje tylko granice >= granicy skanu (nizsza = ponowny
  skan). Warstwa spoza `LAYER_PATTERN` nie jest odpytywana; nazwa z rodziny
  produktu (`LAYER_FAMILY`) daje `logger.warning`.
  Format pliku z pola `format` rekordu (nie z URL); plik zawsze z
  rozszerzeniem kanonicznym `.asc`/`.tif` (rekord 72675 z URL `.xyz` to
  AAIGrid = zwykla kampania `.asc`); po pobraniu weryfikacja tresci
  (naglowek AAIGrid / sygnatura TIFF); nieznany format albo niezgodna tresc
  = porazka kampanii (`DownloadError`, plik usuniety, nigdy ciche `.asc`).
  Sidecar pliku w `kampanie/` jest OBOWIAZKOWY (`emit_sidecar(required=True)`):
  porazka zapisu = porazka kampanii, plik danych usuniety, dowiazanie
  nieprzestawione; pozostale sidecary best-effort. Sidecar kampanii:
  `extra.campaign` = `{id, date, zgloszenie, source, full_sheet, dt_pzgik}`,
  `request.campaigns` zawsze, `request.min_year` tylko gdy podany.
  Dowiazanie: raz na arkusz po zebraniu kampanii, przestawiane tylko na klucz
  `(aktualnosc, dt_pzgik, url)` scisle wiekszy niz klucz biezacego celu (z
  sidecara, a gdy nieczytelny — z nazwy katalogu; ten sam cel = bez zmian), metoda symlink WZGLEDNY
  -> hardlink -> kopia; przy kopii `Warning:` (`dowiazanie niedostepne na tym
  systemie plikow — sciezka standardowa jest KOPIA najnowszej kampanii dla N
  arkuszy (...) (extra.link=copy)`, kod bez zmian). Kontrola istnienia
  sprawdza CEL (wiszace dowiazanie = brak pliku). Porazka dowiazania (nawet
  kopii) = porazka arkusza (kod 1, lista idzie dalej, pobrane kampanie
  zostaja). Wyscig bez blokad: rownolegle wywolania na tej samej sciezce
  moga chwilowo zostawic dowiazanie na starszej kampanii; kolejne
  `newest`/`all` je naprawia. Czesciowa porazka `all` na arkuszu (np.
  niepoprawna `aktualnosc` jednej kampanii) = kod 1, pozostale kampanie
  pobrane, dowiazanie na najnowsza poprawna. Blad pobrania pliku podaje
  nazwe pliku z URL, nie godlo (`84183_1852496_N-34-139-C-a-3-1.asc
  (OpenData): HTTP 404`). Podsumowanie `all` (bez `-q`): `Downloaded <n>
  campaign files for <m> sheets to <dir> (<k> already existed)` (n =
  pobrane, k = lokalne z `DownloadResult.reused_campaign_files`).
  `FileStorage.list_files()` domyslnie pomija `kampanie/` i wiszace
  dowiazania (`campaigns=True` = tylko `kampanie/`). Bez skanowania
  `kampanie/` w 0.7.0.
  Awaria skorowidza (I-1): `newest` (bez `--min-year`, bez `--force`) przy
  bledzie TRANSPORTU `resolve_campaigns` (siec, 429, 5xx; nie
  `NoCoverageError`, nie inne 4xx/raport OGC) i istniejacej lokalnej
  kampanii (`linked_campaign(std)`) = arkusz pominiety z lokalnej kampanii,
  `Warning: <godlo>: skorowidz GUGiK niedostepny — uzyto lokalnej kampanii
  bez sprawdzenia nowszej (...)` (lista: jedno `Warning:` z godlami), kod
  bez zmian; biblioteka: `SheetFetch.unverified`/`DownloadResult.unverified`.
  `all`/`--min-year`/brak lokalnej = blad jak dotad. Biblioteka bez
  `MetadataCache` pyta skorowidz przy kazdym `download_sheet`.
  Wycinek `--target-crs` + (`--campaigns all` lub `--min-year`) = `Error:`
  kod 1 przed siecia; wycinek zawsze `newest`, czyta arkusze przez
  dowiazania (`run_pl_cutout` nie przyjmuje `campaigns`) i jest pomijany
  po samym istnieniu pliku wyniku.
  Opcje kampanii a CZ (jedna regula, `_reject_campaign_opts_without_pl`):
  zadanie bez PL (godlo CZ takze pod `auto`, obszar/geometria z jawnym
  `--country cz`, obszar w calosci czeski pod `auto`) = `Error: CZ (CUZK)
  nie ma kampanii — --campaigns all/--min-year dotycza tylko PL`, kod 1,
  bez sieci; obszar pod `auto` z PL i CZ = jedno `Info: --campaigns/--min-year
  dotycza tylko czesci PL (CZ: biezaca wersja danych CUZK)`, CZ pobierane
  dalej (opcje kampanii nie zwezaja `auto` do PL).
  LAZ: `newest` = ADR-029; `--campaigns all` = wszystkie kafle, ktorych
  rama przecina obszar, bez deduplikacji pokryciowej (kafel przeciety tylko
  obwiednia pomijany jak dotad); `--min-year` = dolna granica `akt_rok`;
  `--min-year` i `--year` wykluczaja sie (`Error:`); LAZ bez dowiazan.
  Wynik pojedynczego godla: "Skipped" tylko gdy `manager.last_sheet.skipped`.
  Kontrola wolnego miejsca wycinka to DOLNE oszacowanie: liczy arkusze bez
  pliku w sciezce standardowej (takze wiszace dowiazanie), a pod `newest`
  arkusz z nowsza kampania zostanie pobrany mimo istniejacego dowiazania.
- **LAZ wybor kafli (ADR-029):** bez `--year` kafle ida zachlannie od
  najnowszego `akt_rok` (w roku nowsza `akt_data`); starszy kafel jest
  pomijany, gdy jego czesc wspolna z obszarem pokrywaja wybrane juz kafle
  (ramy `msGeometry` w EPSG:2180, osie N,E; kazda rama +1 m tolerancji,
  `COVERAGE_TOLERANCE_M`). Tak PL-1992 i PL-2000 tego miejsca sie nie
  dubluja (w2: tylko 2025/PL-1992, bez 2022/PL-2000:S7). Kafel wnoszacy
  niepokryty kawalek zostaje (caly). `--year` = tylko ten rok, dedup
  pokryciowy w roku. Pokrywa tylko kafel `czy_ark_wypelniony` != `NIE`,
  rama albo tym samym godlem — nigdy obwiednia; kafel z rama poza obszarem
  (tylko obwiednia go przecina) jest pomijany. Pominiete: `Info:` na stderr
  (takze z `-q`), w bibliotece `superseded`. Pobieranie i sidecar sa
  w bibliotece (`download_laz_area` / `select_tiles` + `run_laz_download`);
  porazki kafli w `result.failed`, CLI: `Error:` + pelna lista, kod 1.
  Sidecar kafla niesie `extra.parent_request` w trybie `--bbox`/`--geometry`.
- **LAZ --year:** jawny rok jest sprawdzany wobec GetCapabilities danej
  uslugi wysokosciowej przed GetFeature; nieistniejacy rok zglasza
  `rocznik ... nie istnieje w usludze ... (dostepne: ...)`, bez sugestii
  ponowienia. Blad sieci/rocznika opublikowanego nadal daje `DownloadError`
  z informacja o niekompletnym wyniku. Porazka pobrania choc jednego kafla
  = `Error:` z PELNA lista nieudanych kafli i kod 1 (pobrane kafle zostaja).
  Sidecar `request` zapisuje `year`/`min_density` (gdy podane);
  `extra.gestosc` i `--min-density` to gestosc NOMINALNA z WFS GUGiK —
  faktyczna bywa kilkukrotnie wyzsza (E16).
- **Skorowidz GUGiK:** NMT/NMPT/orto pobieraja rekordy z warstw
  GetCapabilities (bez listy zaszytych warstw). Odpowiedz transportowa ma
  do trzech prob z backoffem (siec, 429, 5xx; inne 4xx bez ponowien)
  i jedna sesje na watek; awaria warstwy albo
  niespodziewany szablon = `DownloadError` (bez cichego zejscia do starszej
  kampanii). Dopasowanie godla jest calym tokenem; uklad, rozdzielczosc
  1 m/5 m oraz RGB orto sa filtrowane twardo. W pierwszej pasujacej
  warstwie wygrywa najnowsza `aktualnosc`, potem `dt_pzgik`, URL,
  niezaleznie od flagi pelnego arkusza. Brak zgodnego rekordu to
  `NoCoverageError` z podpowiedzia, dla PL-2000 1:10000 z dostepnymi
  potomkami: `--scale 1:2000` (bez cichego fallbacku PL-1992).
  `extra.source` arkusza i `extra.sheet_sources` wycinka podaja pochodzenie.
  Rekord niepelnego arkusza (`full_sheet: false`) nadal wygrywa, gdy jest
  najnowszy (ADR-028), ale CLI drukuje `Warning:` (tor godla, listy
  i wycinka, takze przy skip), a `extra.source.full_sheet` /
  `extra.sheet_sources[].full_sheet` / `PlCutoutResult.partial_sheets` to
  zapisuja; pusty wycinek z takich arkuszy ostrzega o niepelnej kampanii,
  nie o braku danych GUGiK (E13).
  GUGiK publikuje czesc arkuszy PL-2000 (zaobserwowane: strefa 7, np.
  `7.125.11.19`, `7.173.21.01`) we wspolrzednych EPSG:2180 z niecalkowitym
  `cellsize` (np. 0,99937 m). Sidecar zapisuje faktyczny uklad PLIKU
  (`horizontal_crs: EPSG:2180`), deklaracje rekordu w `extra.source.uklad`
  (`PL-2000:S7`), a plik lezy w segmencie wg godla (`nmt/pl_2000_...`,
  ADR-026). CLI drukuje `Warning: N arkuszy GUGiK opublikowano w innym
  ukladzie niz wskazuje godlo: <godlo> (godlo: EPSG:2178, plik: EPSG:2180)`
  na stderr (tor godla, listy `--bbox`/`--geometry` i hierarchii, takze przy
  skip i `-q`; fakt czytany z sidecara), kod wyjscia bez zmian. Biblioteka
  loguje to samo przez logger `kartograf.sources.sidecar` (bez handlerow
  CLI trafia on rowniez na stderr). Wycinek `--target-crs` nie dotyczy:
  bierze tylko arkusze PL-1992 (E17; testy `tests/test_sidecar.py`,
  `tests/test_cli.py::TestSheetCrsMismatchWarning`).
  `MetadataCache` przechowuje rekord lub potwierdzony brak pokrycia wraz
  z trescia podpowiedzi (TTL 7d; `get_record/set_record`,
  `stats()["record_count"]`); cache hit odtwarza ten sam `NoCoverageError`.
  CLI podpina go w torach PL, `kartograf cache stats` drukuje `Record entries`.
  `--force` omija ODCZYT cache rekordow, ale zapisuje swiezy wybor
  (`MetadataCache(refresh=True)`; kolejny przebieg bez `--force` dostaje
  nowy rekord, E14), `download_pl_cutout(cache=)` udostepnia go
  bibliotece. Tor CZ ma te sama semantyke `--force`: indeks arkuszy SM5
  (`sheet_cache`, TTL 30 d) jest odpytywany na nowo i zapisywany (D16). Orto domyslnie wybiera RGB; `GugikOrtoProvider(color="CIR")`
  wybiera podczerwien na zadanie.
- **Wycinek PL `--target-crs` (ADR-027):** tylko `nmt` i PL-1992,
  jeden GeoTIFF w `nmt/pl_1992_<res>_<vcrs>/bbox/`. Biblioteka udostepnia
  `download_pl_cutout` albo `prepare_pl_cutout` ->
  `select_pl_cutout_sheets` -> `run_pl_cutout`. Brak arkusza GUGiK to
  nodata, `Warning:` i `extra.missing_sheets`; inna awaria pobrania = kod 1.
  `PlCutoutResult.all_nodata=True` i `Warning:` dla wyniku calkowicie pustego
  mimo pobranych arkuszy; sidecar zapisuje `extra.all_nodata: true`, a skip
  odtwarza flage z sidecara (bez czytania rastra) i CLI powtarza `Warning:`
  (E15). Skip pojedynczego godla drukuje `Skipped <godlo> - already exists`,
  nie `Downloaded to`.
  `EPSG:2180` zachowuje siatke i wartosci 1:1; arkusze o innej fazie
  powoduja `GridMismatchError(ValidationError)` i kod 1 z podpowiedzia
  innego `--target-crs`. Dla innego celu W1 reprojektuje kazdy arkusz
  oddzielnie, `extra.off_grid_sheets` zapisuje odchylenia fazy.
  Nie miesza sie arkuszy starych PL-2000 w cache PL-1992: usun stary plik
  z cache i ponow. Wycinek `--geometry` obejmuje cala obwiednie bez maski,
  nieudany zapis pozostawia poprzedni plik. Kontrola wolnego miejsca
  przed siecia wykorzystuje wstepnie policzone brakujace arkusze.
  Pominiety wycinek zwraca `PlCutoutResult(skipped=True)` z
  `missing_sheets`/`off_grid_sheets` odczytanymi z sidecara; CLI ponawia
  ostrzezenie o brakach. `--force` pobiera ponownie takze arkusze;
  tanszy rebuild: usun sam wycinek. Reuzyte arkusze dopisuja
  `extra.parent_requests` bez utraty oryginalnego `parent_request`.
- **Lista arkuszy PL** (`--bbox`/`--geometry` bez `--target-crs`, takze
  hierarchia godla): tolerancja R5 probuje WSZYSTKIE arkusze niezaleznie
  od `--workers`; `NoCoverageError` daje `Warning:` i status
  `DownloadProgress.status == "no_coverage"` (`∅` w CLI).
  >= 1 plik i tylko braki pokrycia -> kod 0; wszystkie bez danych -> kod 1;
  kazda twarda awaria pobrania -> kod 1 z pelna lista porazek.
  Pojedynczy arkusz bez danych -> kod 1. Pod `auto` koncowy kod
  zalezy od sukcesu drugiego kraju wedlug reguly powyzej.
