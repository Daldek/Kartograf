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
  (potrzebne do CORINE GeoTIFF); fallback: macOS Keychain (service `clms-token`)

Bez credentials CLMS: CORINE automatycznie pobiera podglad PNG przez WMS (fallback).

## Dokumentacja

**Przeczytaj w kolejnosci:**
1. `docs/PROGRESS.md` — aktualny stan projektu i zadania
2. `docs/SCOPE.md` — zakres projektu (co jest, czego nie ma)
3. `docs/PRD.md` — wymagania produktowe
4. `docs/CHANGELOG.md` — historia zmian per-release
5. `docs/DECISIONS.md` — rejestr decyzji architektonicznych (co i dlaczego)

## Struktura modulow

```
kartograf/
├── __init__.py          # Public API exports
├── exceptions.py        # KartografError, ParseError, ValidationError, DownloadError
├── core/                # Logika bazowa
│   ├── sheet_parser.py     # SheetParser — parser godel map topograficznych, BBox
│   ├── parser_2000.py      # Parser2000 — parser godal PL-2000, find_sheets_2000_for_bbox
│   ├── parser_tm33.py      # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045), wzor: Parser2000
│   ├── parser_registry.py  # Rejestr systemow godel (pl1992, pl2000, cz_tm33, cz_sm5); SheetParser/FileStorage delegowane
│   └── geometry.py         # Czytanie SHP/GPKG, find_sheets_for_geometry, get_overall_bbox
├── sources/             # Deskryptory zrodel jako dane (zero IO przy imporcie)
│   ├── descriptor.py    # SourceDescriptor, AccessChannel (+endpoint dla silnikow sterowanych deskryptorem), TransportKind, LicenseInfo, CountryProfile
│   ├── registry.py      # Rejestr PL/CZ/EU/GLOBAL — get_source, sources_for, get_country, all_countries, vertical_crs_code, resolve_vertical_crs (rodzina->realizacja)
│   └── sidecar.py       # ResultMetadata, build_metadata (capability=, nodata=), write_sidecar (<plik>.meta.json), read_asc_nodata
├── transform/           # Transformacje CRS
│   └── crs.py           # TransformerGroup (allow_ballpark=False, filtr dokladnosci, probe pod polityka sieci, isfinite); PinnedTransform.transform polimorficzne (skalar/numpy)
├── transport/           # Wspolny transport pobierania
│   ├── http.py          # download_to — atomic write + retry z backoffem
│   └── mosaic.py        # mosaic_and_crop — merge kafli (rasterio) + przyciecie, propagacja nodata
├── providers/           # Providery danych (abstrakcje nad API)
│   ├── base.py          # DataSourceProvider (ABC), BaseProvider (NMT), LandCoverProvider (pokrycie terenu)
│   ├── pl/               # Providery polskie (GUGiK, BDOT10k) — landcover_base.py USUNIETY (patrz base.py)
│   │   ├── gugik.py         # GugikProvider — NMT z GUGiK (WCS + OpenData)
│   │   ├── gugik_nmpt.py    # GugikNmptProvider — NMPT/DSM z GUGiK (dziedziczy z GugikProvider)
│   │   ├── gugik_orto.py    # GugikOrtoProvider — Ortofotomapa z GUGiK (BaseProvider)
│   │   ├── gugik_laz.py     # GugikLazProvider — chmury punktów LAZ z GUGiK (WFS, area-based)
│   │   ├── bdot10k.py       # Bdot10kProvider — BDOT10k z GUGiK
│   │   └── __init__.py      # create_nmt_provider() — fabryka, jedno miejsce polskich domyslow NMT
│   ├── cuzk/             # Providery czeskie (CUZK) — etap 1 (v0.7.0-dev)
│   │   ├── client.py        # CuzkClient — silnik sterowany deskryptorem (ArcGIS REST: query/export_image + pliki openzu)
│   │   ├── sheets.py         # SheetIndex/SheetInfo/Sm5Sheet — indeks arkuszy SM5/TM33 (KladyMapovychListu), filtr nadmiarowego wyboru
│   │   ├── dmr.py            # CuzkDmrProvider — DMR 5G/4G, transformacja pionowa Bpv->EVRF2007 opcjonalna
│   │   └── __init__.py       # create_dmr_provider() — fabryka, jedno miejsce czeskich domyslow (wzor: pl)
│   ├── corine.py        # CorineProvider — CORINE z Copernicus (CLMS API + WMS)
│   └── soilgrids.py     # SoilGridsProvider — dane glebowe z ISRIC (WCS)
├── cache/               # Cache metadanych
│   └── metadata.py      # MetadataCache — SQLite WAL, TTL 7d (sheet_cache: 30d), thread-safe
├── download/            # Zarzadzanie pobieraniem NMT/NMPT/Orto
│   ├── manager.py       # DownloadManager — koordynacja pobierania arkuszy (parallel)
│   └── storage.py       # FileStorage — hierarchiczna struktura katalogow (subdir sterowany deskryptorem)
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

## Komendy

```bash
# Testy
.venv/bin/python -m pytest tests/ -v

# Testy z pokryciem
.venv/bin/python -m pytest tests/ --cov=kartograf --cov-report=html

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
kartograf download N-34-130-D-d-2-4 --product laz
kartograf download N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12
kartograf download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86
kartograf download N-34-130-D --scale 1:10000 --resolution 5m --workers 8
kartograf download --geometry area.shp
kartograf download --geometry area.gpkg --layer catchments
kartograf parse 6.179.12.20
kartograf download 6.179.12.20
kartograf download --bbox 6500000,5895000,6508000,5900000 --bbox-crs EPSG:2177 --system 2000
kartograf download 302_5550 --country cz                      # DMR 5G (TM33), 2m, Bpv
kartograf download CTES96 --resolution 5m                     # DMR 4G (SM5), kraj auto z godla
# bbox przygraniczny --country auto -> osobne pliki PL i CZ, wspolny extra.parent_request
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto
# reprojekcja CZ -> EPSG:2180, lokalna przypieta operacja (tylko --bbox/--geometry, nie godlo)
kartograf download --bbox 18.55,49.60,18.60,49.65 --bbox-crs EPSG:4326 --country cz --target-crs EPSG:2180
kartograf download 302_5550 --country cz --vertical-crs EVRF2007  # Bpv -> EPSG:5621 (przypieta operacja)
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
- CORINE GeoTIFF wymaga OAuth2 credentials w CLMS — bez nich fallback na PNG (WMS)
- SoilGrids: tylko WGS84 bbox (transformacja z EPSG:2180 automatyczna)
- Timeout: 30s dla GUGiK, 60s dla Land Cover i CUZK
- Max 3 proby retry (nie konfigurowalne)
- Kazde udane pobranie tworzy sidecar `<plik>.meta.json` (metadane CRS/licencja/nodata)
- **CZ (CUZK, etap 1):** produkt w etapie 1 to wylacznie `nmt` (DMR 5G/4G) —
  `nmpt`/`orto`/`laz` dla CZ beda dostepne w etapie 2; `exportImage` ma limit
  **asymetryczny 15000x4100 px** — wieksze bboxy sa kafelkowane po stronie
  klienta i scalane (`mosaic_and_crop`); DMR 5G (godlo TM33) to zawsze 2m,
  DMR 4G (godlo SM5) to zawsze 5m — `--resolution` wybiera miedzy nimi, nie
  jest niezalezna flaga jak w PL; `KRON86` jest **nieosiagalny** dla CZ (brak
  publicznych siatek Bpv->KRON86) — uzyj `--vertical-crs EVRF2007`; tryb
  `--bbox` jest **asymetryczny wzgledem PL** — PL zwraca liste arkuszy
  OpenData (wiele plikow), CZ zwraca jeden plik (wycinek `exportImage`);
  rastry CZ sa ZAWSZE pobierane w ukladzie natywnym EPSG:5514, a reprojekcje
  (`--target-crs`, kafel TM33 w 3045) robi lokalnie `rasterio.warp` przypieta
  operacja — serwerowemu `imageSR` nie ufamy (ADR-024); `--target-crs`
  dziala tylko z `--bbox`/`--geometry`
  — z godlem CZ konczy sie `ValidationError` (godlo dostarcza produkt natywny
  1:1); obwiednia kraju CZ (`CountryProfile.extent_wgs84`) jest **prostokatna**,
  nie wielokatem granicy — `--country auto` w poludniowej Polsce (lon<18,86°E,
  lat<51,06°N) wysyla zapytanie do CUZK takze poza faktyczna granica (wynik:
  raster/sidecar same-nodata, nie blad); patrz ADR-023 i `docs/SCOPE.md`
