# Implementacja — pakiet A3 LAZ (K1, N7)

Data: 2026-09-29. Galaz `develop`, baza `c5b3110` (zawiera `make_gugik_session`
i `get_with_retry` z A1). Projekt: `research-orto-laz.md` sekcje K1 i N7;
rozstrzygniecia: ponowienia WYLACZNIE przez `get_with_retry` (P9, bez
`urllib3.Retry`), straz "zwrocone, zadne nie przecina" = `DownloadError`,
`FALLBACK_YEARS` usuniete. Prace rozpoczal agent `A3Laz` (`history://A3Laz`,
padl na limicie), dokonczyl `A23Finish`. Zero sieci.

## Co zmienione — `kartograf/providers/pl/gugik_laz.py`

### K1 — osie WFS
- `_query_layer`: `BBOX = {min_y},{min_x},{max_y},{max_x},urn:ogc:def:crs:EPSG::2180`
  (porzadek EPSG (Northing, Easting) dla formy `urn:`; `BBox` Kartografu to
  (E, N)). Falszywy komentarz "Verified live" usuniety.
- NOWY modulowy `_corner_xy(text, srs_name) -> (E, N)`: `srsName == "EPSG:2180"`
  (legacy, "assumption") = (E, N) jak w tekscie; `urn:`/URI OGC/brak `srsName`
  (dziedziczy ramke zadania) = (N, E) -> zamiana. `_feature_to_tile` czyta
  `srsName` z `gml:Envelope` i wola helper; semantyka `LazTile.min_x/...`
  (x = E, y = N) bez zmian.
- Straz w `_query_layer`: `returned and not kept` ->
  `DownloadError("WFS <layer>: serwer zwrocil N kafli, zaden nie przecina
  zadanego bboxa — niezgodnosc kolejnosci osi (zglos blad)")`. Docstring
  `_intersects` bez "safety net against axis-order quirks" (to straz jest
  sygnalem regresji, nie filtr).

### N7 — discovery wszystko-albo-nic
- Sesja: `self._session = session or make_gugik_session()`; ta sama sesja dla
  GetCapabilities, GetFeature i pobran kafli (`_make_request` bez
  `requests.Session()` ad hoc; dedykowana sesja GetCapabilities usunieta).
- NOWY `_get_wfs_xml(url, timeout, description) -> ET.Element`: `get_with_retry(
  retries=3)` -> `DownloadError` z dopiskiem "wynik bylby niepelny, ponow
  pobranie"; `ET.ParseError` -> `DownloadError("odpowiedz WFS nieczytelna")`;
  `ows:ExceptionReport` -> `DownloadError` z trescia `ows:ExceptionText`.
  Uzywany przez `_fetch_available_years` i kazda strone `_query_layer`.
- `FALLBACK_YEARS` USUNIETE z klasy (breaking; CHANGELOG w fali C).
  `_get_available_years`: bez fallbacku, cache pamieciowy tylko dla udanej
  odpowiedzi, pod `threading.Lock` (`_years_lock`) — bez memoizacji porazki
  (P10). `_fetch_available_years` bez typow LIDAR = `DownloadError` (dawniej
  `ValueError` polykany przez fallback).
- Docstringi `Raises`: `_fetch_available_years` (`DownloadError`),
  `discover_tiles` (`DownloadError`: awaria WFS, XML nieczytelny,
  ExceptionReport, straz osi; "Partial results are never returned").

### CLI (`kartograf/cli/download_cmd.py`) — NIE dotykane (B1)
`_cmd_download_laz` juz lapie `except (ValueError, DownloadError)` -> `Error:
<tresc>`, kod 1, wiec `DownloadError` z `discover_tiles` dziala bez zmian CLI
(dowod: `test_laz_wfs_failure_reports_network_error` przechodzi na obecnym
drzewie). Testy LAZ w `test_cli.py` NIE wymagaja zmiany tekstu "No LAZ tiles
found": `test_laz_no_tiles_found_errors` asertuje podciag `"No LAZ tiles"`,
wiec podpowiedz B1 "(sprawdz obszar/--year/--vertical-crs; wszystkie roczniki
odpowiedzialy)" moze byc dopisana bez ruszania testu. Skrocenie ostrzezen
ponowien (URL ~500 znakow) — `get_with_retry` loguje po stronie A1.

## Testy (failing-before / passing-after)

Dowod failing-before: `git worktree add /tmp/kb HEAD` (= `c5b3110`) + tylko
nowe `tests/test_gugik_laz.py`, `tests/test_cli.py`:
`pytest tests/test_gugik_laz.py` -> 27 failed w tym pliku (z 60 lacznie dla
A2+A3); `pytest tests/test_cli.py -k TestCmdDownloadLaz` -> 2 failed. Po
zmianach: `test_gugik_laz.py` + `test_cli.py` (+ pliki A2) = **515 passed**;
ruff check + format czyste; mypy: zero bledow w `gugik_laz.py`.

| blad | test | failing-before (HEAD) | po |
|---|---|---|---|
| K1 | `TestDiscoverTiles::test_bbox_param_epsg_axis_order_north_east` | URL niosl `BBOX=530000,382000,...` (E,N) | `BBOX=382000.0%2C530000.0%2C386000.0%2C533000.0%2Curn` |
| K1 | `test_spytkowice_tile_keeps_easting_northing` (odpowiedz serwera z L1 `B3_wfs_axis_test.log:8`: `lowerCorner "234772 535830"`, bbox `536400,235100,536600,235300`) | `[] == ['M-34-76-A-a-1-1-3']` (poprawny kafel ODRZUCONY) | kafel z `min_x 535830, min_y 234772, max_x 536958, max_y 235938`, 2023, 4 p/m2, PL-1992 |
| K1 | `test_transposed_lubuskie_tile_is_filtered` (Spytkowice + `N-33-127-A-a-2-3-4` z dzisiejszej odpowiedzi) | `['N-33-127-A-a-2-3-4'] == ['M-34-76-A-a-1-1-3']` (transponowany PRZYJETY) | tylko Spytkowice |
| K1 | `test_only_transposed_tiles_raise_axis_error` | `DID NOT RAISE DownloadError` | `DownloadError` match "kolejnosci osi" |
| K1 | `test_envelope_axis_order_follows_srs_name` x5 (`urn:`, `http://…/EPSG/0/2180`, `https://…`, `EPSG:2180`, brak) | 4 x `[] == [...]` (legacy `EPSG:2180` przechodzil przypadkiem) | pass |
| K1 | helper `_feature()` emituje ramke serwera (N, E) -> istniejace `test_tile_attributes_parsed`, `test_parses_and_filters_outside_tiles`, `test_min_density_filter`, `test_newest_per_godlo_dedup`, `test_pagination_follows_pages` | `IndexError`/`[] == [...]`/`0 == 1`/`set() == {...}` | pass |
| N7 | `test_network_error_raises_download_error` (`ConnectionError`, `time.sleep` spatchowany) | `DID NOT RAISE` (dawniej `[]`) | `DownloadError` z rocznikiem |
| N7 | `test_partial_year_failure_raises_instead_of_partial_result` (2024 OK, 2023 reset) | `DID NOT RAISE` (dawniej 1 kafel, kod 0) | `DownloadError`, zaden kafel |
| N7 | `test_page_failure_raises_instead_of_partial_result`, `test_page_retry_keeps_all_tiles` | `DID NOT RAISE` / `[] == [...]` | pass (ponowienie strony trzyma komplet) |
| N7 | `test_exception_report_raises_with_server_text` (`match="Unknown type name"`), `test_unreadable_response_raises_download_error` | `DID NOT RAISE` | pass |
| N7 | `TestAvailableYears::test_capabilities_network_failure_raises_without_caching` | `DID NOT RAISE` (fallback) | `DownloadError`, brak wpisu w cache |
| N7 | `test_capabilities_recovers_after_connection_reset` | proba realnego polaczenia (straznik gniazd) — HEAD tworzyl `requests.Session()` obok mocka | pass przez `get_with_retry` |
| N7 | `test_invalid_capabilities_abort_discovery` x3 (ExceptionReport, brak LIDAR, XML nieczytelny) | `DID NOT RAISE` | pass |
| N7 | `test_fetch_years_descending` (patch `make_gugik_session` zamiast `requests.Session`) | `AttributeError: no attribute 'make_gugik_session'` | pass |
| N7 | `test_cli.py::TestCmdDownloadLaz::test_laz_wfs_failure_reports_network_error` x2 (bez/z `--year`) | `'Error: WFS' in 'Error: No LAZ tiles found ...'` | kod 1, `Error: WFS ... connection reset by peer`, bez "No LAZ tiles", 3 proby |
| N7 | `test_laz_no_tiles_found_errors` (PRZEPISANY: realna sesja z mockiem `requests.Session.get`: Capabilities + 2 puste roczniki) | pass (kontrola) | pass, `get.call_count == 3` |

Testy USUNIETE (pinowaly bledne zachowanie): `test_bbox_param_uses_native_axis_order`
(asertowal (E,N) w URL), `test_network_error_returns_empty`,
`test_exception_report_skipped`, `test_get_years_fallback_on_error`,
`test_fallback_years_distinct_per_crs`; `test_fetch_years_no_lidar_raises`
zastapiony parametryzowanym `test_invalid_capabilities_abort_discovery`
(`ValueError` -> `DownloadError`).

Kosmetyka A2 w `tests/test_cli.py` (`:2939-2940`, `:3010`, `:3137`: mock
`PinnedTransform` "(3)"/0.5 -> "(1)"/1.0) jedzie w TYM commicie, bo plik
zawiera tez nowe testy LAZ i nie da sie go rozdzielic bez `git add -p`.

## Ryzyka
- Odpornosc: przy ~50 % zrywanych polaczen GUGiK (stan 2026-09-29) discovery
  bez `--year` to 1 + ~9 zapytan x 3 proby -> kod 1 z jasnym "ponow pobranie"
  jest czestszy niz dotad cichy wynik czesciowy (swiadomie, D5/N7). Jesli test
  na zywo nadal daje kod 1 — rozwazyc `retries=5` tylko dla WFS.
- `ExceptionReport` dla rocznika z GetCapabilities = blad (nie cisza) —
  ryzyko falszywych bledow przy chwilowej niespojnosci serwera.
- Podwojne ponowienia pobran kafli: `_download_with_retry` (3) zostaje na
  wspolnej sesji bez `urllib3.Retry`, wiec maks. 3 proby (bez mnozenia).
- Straz osi opiera sie na zalozeniu "serwer filtruje BBOX po geometrii" —
  jesli GUGiK zmieni stack na (E,N) dla `urn:`, wynikiem bedzie jasny
  `DownloadError`, nie zle dane.

## Do weryfikacji na zywo (fala C pkt 4, na polecenie uzytkownika)
- **bbox Spytkowice `536400,235100,536600,235300` -> `M-34-76-A-a-1-1-3`**
  (2023, `77518_1352498_M-34-76-A-a-1-1-3.laz`, 4 p/m2):
  `kartograf download --bbox 536400,235100,536600,235300 --product laz --year 2023`.
  Przed naprawa ten sam bbox dawal `N-33-127-A-a-2-3-4` (Lubuskie, 426 km).
- Przyklad z CLAUDE.md `--bbox 530000,382000,533000,386000 --product laz` —
  kafle pod 19.45°E 51.32°N.
- `kartograf download M-34-76-A-a-1-1 --product laz` bez `--year` — komplet
  rocznikow z GetCapabilities (w tym 2026, ktorego nie bylo w `FALLBACK_YEARS`).

## Pliki (commit `fix(laz): ...`)
`kartograf/providers/pl/gugik_laz.py`, `tests/test_gugik_laz.py`,
`tests/test_cli.py` (testy LAZ + kosmetyka A2), ten raport.
