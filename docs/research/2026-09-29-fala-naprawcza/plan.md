# Plan fali naprawczej 2026-09-29 (K1-K6, S1-S5, N1-N9, H1)

Decyzje: `decisions.md` (D1-D12 + rozstrzygniecia koordynatora). Projekty naprawy:
`research-skorowidz.md`, `research-orto-laz.md`, `research-cz.md`, `research-cli.md`.
Galaz: `develop`. Commity Conventional Commits, male, per pakiet. Testy offline
(`-m "not live"`), ruff check + format, mypy = baseline 32 (lista identyczna).

## Fale i pakiety (wlasciciel = jedyny edytor plikow pakietu w danej fali)

### Fala A (rownolegle, 3 agenty)

| Pakiet | Bledy | Pliki `kartograf/` (wlasnosc) | Testy |
|---|---|---|---|
| A1 skorowidz | K3, K4, S1, S4, H1, N1, N6 (biblioteka) | NOWY `providers/pl/skorowidz.py`; `transport/http.py` (`make_gugik_session`, `get_with_retry`) — **zrobic i zacommitowac NAJPIERW**, potem `write agent://A3Laz`; `providers/pl/gugik.py`; `providers/pl/gugik_nmpt.py`; `providers/base.py` (`source_info`); `cache/metadata.py` (`record_cache`, drop `url_cache`); `cli/cache_cmd.py`; `download/manager.py` TYLKO `_write_sidecar(..., source)`; `download/cutout.py` TYLKO `_reject_pl2000_sheets` komunikat/docstring, `download_pl_cutout(cache=)`, `extra.sheet_sources` w `write_pl_cutout_sidecar` | `tests/test_skorowidz.py` (NOWY), `tests/fixtures/gugik_skorowidz/`, `conftest.py` (`render_gfi_body`, `_STUB_LAYERS`), `test_gugik_provider.py`, `test_gugik_nmpt.py`, `test_wms_layer_validation.py`, `test_metadata_cache.py`, `test_download_manager.py` (sidecar source), `test_transport_http.py`, `test_pl_cutout.py` (tylko cache kwarg + komunikat) |
| A2 CZ | K2, K6, N3 + helper N2 | `transform/crs.py`; `providers/cuzk/client.py`; `providers/cuzk/dmr.py` (komentarze); `transport/mosaic.py` TYLKO dopisany na koncu `has_valid_pixels(path, nodata) -> bool`; `transform/raster.py` docstring `:4-7` | `test_transform_crs.py`, `test_cuzk_dmr.py`, `test_cuzk_client.py`, `test_transport_mosaic.py` (tylko test helpera), kosmetyka opisow "(3)" w `test_cli.py`/`test_pl_cutout.py` |
| A3 LAZ | K1, N7 | `providers/pl/gugik_laz.py` (osie, straz, retry przez `get_with_retry`, usuniecie `FALLBACK_YEARS`, sesja z `make_gugik_session`) | `test_gugik_laz.py`; `test_cli.py` TYLKO testy LAZ (klasa `TestCmdDownloadLaz` lub odpowiednik) |

### Fala B (po A, rownolegle, 3 agenty)

| Pakiet | Bledy | Pliki (wlasnosc) | Testy |
|---|---|---|---|
| B1 CLI integrator | S2 (D2, D10, D11), S3, N2 (wiring CLI + `PlCutoutResult.all_nodata` w `run_pl_cutout`), N6 (wiring CLI: `_create_provider_and_storage(cache=)`, cykl zycia `MetadataCache` na galezi PL), K2 komunikaty `:678-682`/`:1642-1645` + `Info:` dla starego sidecara "(3)" (D12), N7 komunikat CLI "No LAZ tiles found", N4 czesc managera (`extra.parent_requests` dla pominietych) | `cli/download_cmd.py` (calosc); `download/manager.py` (`DownloadResult.hard_failures`, status `no_coverage` w `DownloadProgress`, N4 `parent_requests`); `download/cutout.py` TYLKO `run_pl_cutout` (N2 `all_nodata`) | `test_cli.py` (poza LAZ), `test_download_manager.py`, `test_pl_cutout.py` (N2, `test_without_target_crs_behaviour_unchanged`) |
| B2 mozaika/wycinek | S5 (D3, D8), N4 czesc wycinka (`missing_sheets` z sidecara przy skipped), N9 | `transport/mosaic.py` (`check_source_grid`, `GridMismatchError`, usuniecie ostrzezenia; NIE ruszac `has_valid_pixels` z A2); `exceptions.py`; `transform/raster.py` (`warp_to_grid(list[Path])` W1); `download/cutout.py` `build_pl_cutout`, `estimate/check disk` (N9), `prepare/select` (N4) — NIE `run_pl_cutout` (B1) | `test_transport_mosaic.py`, `test_pl_cutout.py` (S5/N4/N9), `test_transform_raster.py` (jesli jest) |
| B3 orto + sidecar | K5 (konsument `skorowidz.py`), N8, N5 | `providers/pl/gugik_orto.py`; `sources/sidecar.py`, `sources/registry.py` (N8); `cli/_parser.py` (usunac ostrzezenia K1/K5 z `--help`) | `test_gugik_orto.py`, `test_sidecar*.py`, `test_pl2000_verification.py` (N5: 8 testow `live` z prawdziwymi asercjami — bez uruchamiania) |

### Fala C (sekwencyjnie)
1. Brama: pelna suita offline, ruff check + format, mypy vs baseline; naprawa regresji (koordynator lub jeden agent).
2. Review calej fali (`reviewer`, dowody mutacyjne per blad: test failing-before na HEAD sprzed fali — `git stash`/`git worktree` — passing-after).
3. Dokumentacja: CHANGELOG (Fixed/Breaking), README "Znane problemy" (usunac naprawione), CLAUDE.md (Ograniczenia, `--country auto`, K1-K6/S/N noty), ARCHITECTURE (3.2 `extra`, 4.2/4.3, sekcja CZ, 5), SCOPE, PRD, DECISIONS (errata ADR-020, ADR-021, ADR-023 pkt 7, ADR-024 errata 2 — tresc w `research-cz.md` sekcja 5, ADR-027 addendum D3/D8/R5-lista, NOWY ADR "wybor rekordu skorowidza + extra.source"), PROGRESS (tabela bledow -> naprawione, backlog checkboxy).
4. Testy na zywo (tylko na polecenie uzytkownika; niska rownoleglosc): K1 Spytkowice `536400,235100,536600,235300` -> `M-34-76-A-a-1-1-3`; K2/K6 L4 (S-STYK Karkonosze CZ vs GUGiK <= ~0,4 m; 10 x 10 km 2 m przechodzi; piksel 2,000 m); K4 Szczecin 1 m / Warszawa `2023iStarsze`; K5 orto RGB; S2 Hel/Leba lista; S5 Krakow 5 m 2180 -> `GridMismatchError`, 5514 -> W1.

## Kontrakty wspolne (obowiazuja wszystkich)

- `transport/http.py` (A1): `make_gugik_session() -> requests.Session` (HTTPAdapter pool 4/8, `User-Agent: kartograf/<ver>`, BEZ `urllib3.Retry`); `get_with_retry(session, url, *, timeout: float, retries: int = 3, description: str = "") -> requests.Response` — `RequestException`/`HTTPError` -> backoff `RETRY_BACKOFF_BASE**attempt`, po wyczerpaniu `DownloadError(f"{description}: ... po {retries} probach: {e}")`; `raise_for_status()` w srodku.
- `providers/pl/skorowidz.py` (A1; B3 konsumuje): `SkorowidzRecord` (frozen: `url, godlo, aktualnosc, dt_pzgik, layer, uklad ("1992"|"2000"|None), zone, resolution_m, full_sheet, raw: dict[str,str]`, `to_source(endpoint) -> dict`), `parse_skorowidz_records(text, layer) -> list[SkorowidzRecord]` (uklad z `ukladWspolrzednychPoziomych` ALBO `ukladWspolrzednych`; rozdzielczosc z `charakterystykaPrzestrzenna` "1.00 m" ALBO `wielkoscPiksela` "0.25"; `full_sheet` z `calyArkuszWypelnionyTrescia`/`calyArkuszWyeplnionyTrescia`; URL bez filtra rozszerzenia, musi zaczynac sie od `https://`), `is_skorowidz_answer(text) -> bool` (szablon `var \w+ = [];`), `select_sheet_record(records, *, godlo, uklad, zone=None, resolution_m=None, predicate=None) -> SkorowidzRecord | None` (godlo == `SheetParser(godlo).godlo` caly token; uklad; zone; `abs(res - resolution_m) < 1e-6` gdy podane; predicate; max po `(aktualnosc, dt_pzgik, url)` — D9), `query_skorowidz_layer(session, endpoint, layer, *, query_bbox, godlo, timeout, retries=3) -> list[SkorowidzRecord]` (raport OGC / brak szablonu = `DownloadError` bez ponowien), `SourceInfoMixin` (`_remember_source(godlo, dict)` pod `threading.Lock`, `source_info(godlo) -> dict | None`).
- `providers/base.py::BaseProvider.source_info(godlo) -> dict | None` (domyslnie `None`).
- `DownloadManager._write_sidecar` dopisuje `extra["source"]` gdy `provider.source_info(godlo)` jest `dict` (A1). B1 dopisuje `extra["parent_requests"]` dla arkuszy pominietych — inna galaz kodu.
- `cache/metadata.py` (A1): `get_record(product, resolution, vertical_crs, godlo) -> dict | None`, `set_record(..., payload: dict)`; payload `{"source": {...}}` albo `{"no_coverage": true}`; `stats()["record_count"]`; `url_cache` + `get_url/set_url` USUNIETE (DROP TABLE IF EXISTS url_cache przy `_create_tables`).
- `DownloadResult.hard_failures` property; `DownloadProgress.status` += `"no_coverage"` (B1).
- `transport/mosaic.py`: A2 dopisuje `has_valid_pixels(path: Path, nodata: float | None) -> bool` NA KONCU modulu; B2 (fala B) refaktoruje `_snap_outward` -> `check_source_grid(paths) -> SourceGrid(reference: Affine, off_grid: tuple[OffGridSource(path, dx_px, dy_px), ...])` i `GridMismatchError(ValidationError)` (w `exceptions.py`, atrybut `.off_grid`).
- `PlCutoutResult.all_nodata: bool = False` (B1 w `run_pl_cutout`; `has_valid_pixels` z A2).
- `transform/crs.py` (A2): `DATUM_STEP_PINS: dict[int, frozenset[str]] = {5514: {"EPSG:1622", "EPSG:1623"}}`, `_epsg_code`, `_operation_codes`, filtr w `build_pinned_transform` po filtrze dokladnosci, przed probe; `KNOWN_PATHS` 5514<->2180 = 1.0 m + wpisy 5514->3045, 5514->4326.
- `providers/cuzk/client.py` (A2): `MAX_EXPORT_PIXELS = 4_000_000`; `_tile_grid(bbox, pixel_size, width_px, height_px, max_w, max_h, max_px)`; snap bboxa NW przed rozgalezieniem.
- Komunikaty CLI po polsku, prefiksy `Info:`/`Warning:`/`Error:` na stderr (konwencja repo). Testy: usuwac testy pinujace stare zachowanie (lista w raportach), nie re-pinowac; nowe testy failing-before/passing-after.

## Zasady wykonania
- Zadna fala nie uruchamia pelnej suity w trakcie pracy rownoleglej innych agentow — tylko wlasne pliki testow; pelna brama w fali C.
- Zero zapytan sieciowych (straznik gniazd w `tests/conftest.py`); fixtures z `docs/research/2026-09-29-live-e2e-i-audyt-docs/gfi/` i z `e2e-data/` (kopiowac do `tests/fixtures/`, bo `e2e-data/` jest gitignorowane).
- Kazdy agent konczy raportem `docs/research/2026-09-29-fala-naprawcza/impl-<pakiet>.md`: co zmienione, testy failing-before (dowod: uruchomienie nowego testu na stashu HEAD sprzed zmian albo opis mutacji), pozostale ryzyka, lista plikow.
- Commit per pakiet na koniec (agent commituje TYLKO swoje pliki: `git add <lista>`; bez `git add -A`).
