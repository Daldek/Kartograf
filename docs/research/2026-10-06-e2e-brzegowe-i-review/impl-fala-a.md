# Fala naprawcza A — implementacja (2026-10-06)

Galaz `fix/review-2026-10-06` (worktree `Kartograf-fix`), baza `ce2ef40`.
Zrodla znalezisk: `review-1-duplikacje.md` (D1, D8), `review-2-deklaracje.md`
(N1, N5, N6, N7, N8, N9). Kazde zadanie TDD: test czerwony na kodzie bazowym
z wlasciwego powodu -> minimalna zmiana -> zielony -> mutacja (cofniecie
naprawy) -> test znow czerwony -> przywrocenie.

## Wynik koncowy

- `pytest tests/ -m "not live"`: **2125 passed** (baza 2105; +20 nowych
  przypadkow), 16 deselected (`live`).
- `ruff check kartograf/ tests/`: All checks passed; `ruff format --check`:
  90 files already formatted.
- `mypy kartograf/`: 32 bledy; lista bledow bez numerow linii (`sed
  's/:[0-9]+: /: /' | sort`) **identyczna** z baza `ce2ef40` (`diff` pusty).

## A1 (D8/N7) — tor CZ na wspolnym `warp_to_grid`

- **Zmiana:** `CuzkDmrProvider._export_raster` wola
  `transform/raster.warp_to_grid(native_path, output_path, bbox,
  self._pixel_size, pinned, src_crs=NATIVE_CRS, nodata=CUZK_NODATA)`.
  Usuniete: `dmr._warp_to_grid` (z `except BaseException: dst_path.unlink`)
  i lokalny `_quiet_transformer_only_option` (jedyny uzytkownik byl
  `_warp_to_grid`) oraz zbedne importy. Docstringi: `_export_raster`,
  modul `transform/raster.py`, filtr GDAL w `raster.py` (przejal opis
  z kopii CZ), komentarz `_tile_grid` w `cuzk/client.py`. Docs:
  ARCHITECTURE sekcja 3 pkt 3 i "Nieudana budowa a poprzedni wynik",
  ADR-027 Konsekwencje (korekta 2026-10-06).
- **Test:** `tests/test_cuzk_dmr.py::TestHorizontalReprojection::test_failed_warp_keeps_previous_output[bbox|godlo]`
  — pod sciezka wyniku lezy "poprzedni wynik", serwer (mock `export_image`)
  zwraca nieczytelny plik natywny -> `RasterioIOError`; poprzedni plik
  ma przetrwac bajt w bajt, zadnych smieci w katalogu. Awaria NIE pochodzi
  z patcha konkretnej funkcji, wiec test nie zalezy od implementacji warpu.
- **Przed:** 2 failed — `FileNotFoundError` (poprzedni plik skasowany),
  dla wycinka bbox i kafla TM33.
- **Po:** passed.
- **Swiadoma zmiana istniejacych testow:** dwa testy patchowaly
  `kartograf.providers.cuzk.dmr.reproject` (`test_failed_warp_leaves_no_output`,
  `test_warp_forces_the_pinned_operation`) — cel patcha przeniesiony na
  `kartograf.transform.raster.reproject`; asercje bez zmian.
  `test_failed_warp_leaves_no_output` sprawdza przypadek BEZ poprzedniego
  pliku (pusty katalog po awarii) — nadal prawdziwy, zostal.
- **Bit w bit:** emulator serwera z testow (`_server_emulator`) -> wycinek
  EPSG:2180 (z nodata) i kafel TM33 302_5550; SHA1 tablic, transform, CRS,
  nodata identyczne przed i po zmianie
  (`677f6134...` / `f61d803e...`).
- **Mutacja:** dopisanie `except BaseException: dst_path.unlink(missing_ok=True)`
  w `transform/raster.warp_to_grid` -> **3 failed**: oba nowe testy CZ oraz
  `test_transform_raster.py::test_failed_warp_keeps_previous_destination`.
  Przywrocone.
- **Commit:** `009589b` fix(cuzk): wspolny warp_to_grid w torze CZ, awaria nie kasuje wyniku

## A2 (D1/N9) — CORINE i SoilGrids: polityka ponowien

- **Zmiana:** `_download_with_retry` w `providers/corine.py` i
  `providers/soilgrids.py`: `is_retryable` (4xx poza 429 -> od razu
  `http_failure(..., e)` z `status_code`), `retry_wait(e, backoff)`
  (Retry-After), koncowy `http_failure(..., last_error)`. Wykladnik
  backoffu bez zmian (`RETRY_BACKOFF_BASE**attempt`, 2 s/4 s).
  CLAUDE.md "Ograniczenia" zaktualizowane.
- **Test:** parametryzacja `PROVIDERS` w `tests/test_retry_policy.py`
  rozszerzona o `corine` i `soilgrids` (ta sama sygnatura
  `_download_with_retry(url, output_path, timeout, description)`):
  `test_not_found_is_not_retried`, `test_throttled_download_waits_retry_after`,
  `test_exhausted_server_errors_keep_status`.
- **Przed:** 6 failed (404 ponawiany 3x ze sleep [2,4] i `status_code=None`;
  Retry-After ignorowane — sleep(2) zamiast sleep(11); 503 bez
  `status_code`).
- **Po:** 24 passed.
- **Mutacja 1:** `if False and not is_retryable(e)` (przywrocone ponawianie
  404) -> 2 failed (`test_not_found_is_not_retried[corine|soilgrids]`).
- **Mutacja 2:** `retry_wait(...)` -> sam backoff (ignorowanie Retry-After)
  -> 2 failed (`test_throttled_download_waits_retry_after[corine|soilgrids]`).
  Przywrocone.
- **Commit:** `982c42d` fix(landcover): polityka ponowien 429/5xx i Retry-After w CORINE i SoilGrids

## A3 (N5) — `CuzkClient.query` i TERYT BDOT10k przez `get_with_retry`

- **Zmiana:** `transport/http.get_with_retry` dostaje opcjonalne
  `params=` (przekazywane do `session.get` tylko, gdy podane — istniejace
  wywolania bez zmian). `CuzkClient.query` wola
  `get_with_retry(self._session, url, timeout=..., params=params,
  description=f"Zapytanie {url}")`; blad JSON (`ValueError`) nadal
  `DownloadError("Zapytanie ... nieudane: ...")` bez ponowien.
  `Bdot10kProvider._get_teryt_for_point` wola `get_with_retry(...,
  description="zapytanie TERYT")`, a `DownloadError` opakowuje w
  `"WMS GetFeatureInfo failed: ..."` z zachowanym `status_code`
  (istniejacy test dopasowuje ten prefiks). CLAUDE.md zaktualizowane.
- **Test:** `tests/test_retry_policy.py::TestSingleQueryRetries`:
  `test_connection_error_is_retried[cuzk_query|bdot10k_teryt]`
  (ConnectionError -> 2. proba sukces, sleep(1)),
  `test_not_found_is_not_retried[...]` (404 -> 1 proba, bez sleep,
  `status_code=404`, komunikat `HTTP 404`),
  `test_cuzk_invalid_json_is_not_retried`.
- **Przed:** 4 failed — ConnectionError od razu `DownloadError` (1 proba);
  404 bez `HTTP 404`/`status_code`. (Liczba prob przy 404 juz byla 1 —
  test 404 pada na braku kodu HTTP w bledzie.)
- **Po:** passed.
- **Zmiana istniejacego testu:** `test_landcover.py::test_get_teryt_for_point_network_error`
  dostal `@patch("kartograf.transport.http.time.sleep")` — bez tego
  ConnectionError jest teraz ponawiany z prawdziwym sleep (3 s); asercja
  (`DownloadError`, "WMS GetFeatureInfo failed") bez zmian.
  Testy `test_cuzk_client.py` (params przez `kwargs["params"]`) bez zmian.
- **Mutacja 1:** `retries=1` w obu wywolaniach -> 2 failed
  (`test_connection_error_is_retried[...]`).
- **Mutacja 2:** `is_retryable` zawsze True (ponawianie 404) -> 2 failed
  (`test_not_found_is_not_retried[...]`). Przywrocone.
- **Commit:** `df99268` fix(transport): CuzkClient.query i TERYT BDOT10k przez get_with_retry

## A4 (N1) — BDOT10k `--format SHP` jako `.zip`

- **Zmiana:** `Bdot10kProvider.download_by_admin_unit` dla `format="SHP"`
  zamienia rozszerzenie sciezki na `.zip` (symetrycznie do GPKG, gdzie
  `_extract_gpkg_from_zip` nadaje `.gpkg`). Dotyczy tez bbox/godlo (oba
  koncza w `download_by_admin_unit`). `LandCoverManager` pisze sidecar
  obok zwroconej sciezki, CLI drukuje zwrocona sciezke — bez zmian w
  managerze. Docs: ARCHITECTURE 4.8, README (Formaty), docstring.
- **Test:** `tests/test_landcover.py::TestBdot10kShpFormat`:
  `test_cli_saves_shp_package_as_zip` (koncowy: `kartograf landcover
  download --source bdot10k --teryt 1465 --format SHP -o tmp`, mock sesji
  przez `make_gugik_session`; URL `/SHP/14/1465_SHP.zip`, plik
  `bdot10k_teryt_1465.zip` zaczyna sie od `PK`, sidecar
  `bdot10k_teryt_1465.zip.meta.json`, w katalogu nic wiecej, stdout
  `Downloaded to: .../bdot10k_teryt_1465.zip`) i
  `test_provider_returns_zip_path_for_shp` (biblioteka).
- **Przed:** 2 failed (plik zapisany jako `.gpkg`).
- **Po:** passed.
- **Mutacja:** usuniecie `with_suffix(".zip")` -> 2 failed. Przywrocone.
- **Commit:** `69ac07c` fix(bdot10k): paczka --format SHP zapisywana jako .zip, nie .gpkg

## A5 (N8) — bledne opcje `landcover download` = blad uzytkownika

- **Zmiana:** `cmd_landcover_download` lapie `ValueError` (po
  `ParseError`/`ValidationError`): `Error: <tresc>`, kod 1.
- **Test:** `tests/test_landcover.py::TestLandCoverInvalidOptions::test_invalid_option_is_user_error`
  — 4 przypadki: SoilGrids `--property foo`, `--depth 1-2cm`,
  `--stat median`, CORINE `--year 1999`; kod 1, `Error: ` + tresc, brak
  `ValueError` i `KARTOGRAF_DEBUG` w stderr; offline (blokada gniazd
  z conftest — proba sieci wywrocilaby test).
- **Przed:** 4 failed (`Error: ValueError: ...` + podpowiedz DEBUG).
- **Po:** passed.
- **Mutacja:** `except ValueError` -> `except ZeroDivisionError` -> 4 failed.
  Przywrocone.
- **Commit:** `3de8504` fix(cli): bledne opcje landcover download jako blad uzytkownika

## A6 (N6) — LAZ: porazka kafli jako `Error:` z pelna lista

- **Zmiana:** `_cmd_download_laz`: `Error: N z M kafli LAZ nie pobrano
  (blad pobrania): <godla> — ponow pobranie` + linia szczegolow dla
  KAZDEGO nieudanego kafla (posortowane po godle/URL, bo `as_completed`
  daje kolejnosc niedeterministyczna); kod 1 bez zmian. CLAUDE.md (LAZ)
  i ARCHITECTURE 4.7: zdanie o kodzie wyjscia pobierania kafli.
- **Test:** `tests/test_cli.py::TestCmdDownloadLaz::test_laz_tile_failures_are_error_with_full_list`
  — 8 kafli, 7 pada `DownloadError`; kod 1, brak `Warning:`, jest
  `Error: 7 z 8 kafli LAZ nie pobrano`, wszystkie 7 godel w stderr,
  udany kafel nie jest wymieniony.
- **Przed:** failed (`Warning: 7 tiles failed to download`, 5 kafli).
- **Po:** passed.
- **Mutacja 1:** prefiks `Warning:` zamiast `Error:` -> failed.
- **Mutacja 2:** obciecie listy do `failed[:5]` (podsumowanie i szczegoly)
  -> failed. Przywrocone.
- **Commit:** `d1fb580` fix(laz): porazka kafli jako Error z pelna lista nieudanych kafli

## Tabela mutacji

| Zadanie | Mutacja | Wynik nowych testow |
|---|---|---|
| A1 | `except BaseException: dst.unlink` w `warp_to_grid` | 3 failed (2 CZ + 1 raster) |
| A2 | ponawianie 404 (`if False and not is_retryable`) | 2 failed |
| A2 | ignorowanie Retry-After | 2 failed |
| A3 | `retries=1` (CUZK query, TERYT) | 2 failed |
| A3 | `is_retryable` zawsze True | 2 failed |
| A4 | bez `with_suffix(".zip")` | 2 failed |
| A5 | bez `except ValueError` | 4 failed |
| A6 | `Warning:` zamiast `Error:` | 1 failed |
| A6 | lista obcieta do 5 | 1 failed |

## Odstepstwa / uwagi

- A3: zamiast budowac URL z `urlencode` (propozycja review-1) dodano
  `params=` do `get_with_retry` — testy `test_cuzk_client.py` sprawdzaja
  parametry przez `session.get.call_args.kwargs["params"]` i zostaly bez
  zmian.
- A4: rozszerzenie nadaje provider, nie `LandCoverManager._generate_output_path`
  (manager nie zna formatu; provider dziala tez dla sciezek podanych
  przez biblioteke). Przy SHP z wlasna `output_path` biblioteka dostaje
  sciezke z `.zip` w miejsce rozszerzenia z argumentu.
- A5: `except ValueError` jest szeroki — `ValueError` z innego miejsca toru
  landcover (np. blad wewnetrzny) tez dostanie krotkie `Error: <tresc>`
  bez podpowiedzi DEBUG. Alternatywa (providery rzucaja `ValidationError`)
  zostawiona na backlog; review dopuszczal oba warianty.
- Wykladnik backoffu (2 s/4 s providery vs 1 s/2 s transport) swiadomie
  NIE ujednolicony (polecenie fali); CLAUDE.md opisuje rozjazd.
