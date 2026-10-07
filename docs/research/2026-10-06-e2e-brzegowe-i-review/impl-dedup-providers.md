# Implementacja deduplikacji: providery i transport (2026-10-07)

Galaz `refactor/dedup-providers` (od `develop` 0f5e4f4). Zrodlo:
`review-1-duplikacje.md`, zakres D1, D2, D6, D9, D13, D19. Bez sieci.

Bramki: suita offline 2216 -> **2227 passed** (16 `live` odznaczonych),
`ruff check` + `ruff format --check` czyste, mypy **32 bledy — lista bez
numerow linii identyczna z baseline** (zmienia sie tylko "checked 54 -> 56
source files": nowe `transform/bbox.py`, `providers/pl/wcs.py`).

## Aktualnosc znalezisk na starcie

| D | Stan na 0f5e4f4 | Decyzja |
|---|---|---|
| D1 | aktualne: 6 kopii petli; po 2026-10-06 wszystkie z `is_retryable`/`retry_wait`/`http_failure`, ale nadal skopiowane; rozjazdy 2-5 z review nadal prawdziwe (pkt 1 i 6 naprawione 2026-10-06) | zrobione |
| D2 | aktualne: `skorowidz.py:370-376`, `bdot10k.py:483-489` | zrobione |
| D6 | aktualne: helper `cli/download_cmd.py:273` + 2 reczne kopie (`:831`, `:2111`) | **nie zrobione** — w calosci w `cli/*` (zakaz) |
| D9 | aktualne: `cuzk/dmr.py:86,89` vs `download/cutout.py:53,56` | zrobione po stronie CZ; `cutout.py` poza zakresem |
| D13 | aktualne (linie jak w review +-10) | zrobione |
| D19 | aktualne: `corine.py:853,876`, `soilgrids.py:255` | zrobione |

## D1 — petla pobierania pliku (commit 9c7aaa9)

**Przed:** 6 kopii `_download_with_retry` + 3 `_make_request` + 6
`_save_response`: `gugik.py:491-589`, `gugik_orto.py:339-414`,
`gugik_laz.py:574-641`, `bdot10k.py:491-587`, `corine.py:901-1000`,
`soilgrids.py:413-512` (ok. 520 linii) obok kanonu
`transport/http.py::download_to`.

**Po:** jeden `download_to(session, url, path, *, timeout, retries,
description, validate=None, save=None)`; providery wolaja go bezposrednio
(gugik 2 miejsca, orto 2, LAZ 1, BDOT10k 1, CORINE 2, SoilGrids 1).
Nowe w transporcie: `MAX_RETRIES`, `backoff_delay`, `reject_error_document`,
`_write_atomic`. `kartograf/`: +177 / -678.

**Rozjazdy kopii i rozstrzygniecia:**

1. Backoff: providery 2 s/4 s (`2**attempt`, attempt od 1), transport
   1 s/2 s (od 0). **Wybrano 2 s/4 s** dla wszystkich (`backoff_delay`,
   takze `get_with_retry`): ten wykladnik obslugiwal dotad caly ruch
   plikow, przeciazony serwer 5xx GUGiK/ISRIC potrzebuje dluzszej
   przerwy, a +3 s w najgorszym przypadku jest pomijalne wobec timeoutow
   30-120 s; przy `Retry-After` liczy sie i tak `max(backoff, retry_after)`.
   Zaktualizowane asercje: `test_transport_http` (1 -> 2, [1,2] -> [2,4]),
   `TestSingleQueryRetries` (1 -> 2). Zdanie w CLAUDE.md "Ograniczenia"
   zastapione opisem jednego miejsca polityki.
2. `Path.rename` (kopie) vs `os.replace` (kanon): wybrano `os.replace`
   (Windows: `rename` na istniejacy plik = `FileExistsError`, `--force`
   padal). Dotyczy tez `Bdot10kProvider._merge_gpkg_files`. Nowe testy
   z semantyka Windows (`Path.rename` podmienione):
   `test_redownload_overwrites_existing_file[7 providerow]` — **padaja na
   kazdej z 7 starych kopii** (sprawdzone `git stash` kodu przy nowych
   testach: 7 failed), oraz
   `test_merge_overwrites_existing_gpkg_like_windows` (pada na starym
   `bdot10k.py`).
3. Komunikaty: angielskie kopie -> polski kanon ("HTTP 404 (bez
   ponowien)", "po 3 probach"), `from last_error` po wyczerpaniu prob.
   Zaden kod w pakiecie nie dopasowywal tresci; asercje `after 3 attempts`
   w `test_landcover` -> `po 3 probach`.
4. Sesje CORINE/SoilGrids: `self._session or requests.Session()` przy
   KAZDYM pobraniu (nigdy nie zamykana) -> `SessionPerThread(session,
   factory=requests.Session)`; `_download_via_clms_direct` tez. LAZ
   zostaje przy jednej sesji `make_gugik_session()` (dotkniecie
   `_get_wfs_xml` = teren agenta LAZ; patrz "Czego nie zrobilem").
5. Katalog docelowy: kanon robil `mkdir` przed zapytaniem, gugik/orto po
   odpowiedzi, LAZ/BDOT10k przed. Wybrano "po udanej odpowiedzi" (blad HTTP
   nie zostawia pustego katalogu; tak dokumentowal orto).
6. Walidacja tresci CORINE/SoilGrids (Content-Type xml/html -> 
   `DownloadError` bez ponowien) -> hak `validate=reject_error_document(...)`
   z tym samym komunikatem "WMS/WCS returned error response". CLMS GeoTIFF
   nadal walidowany jak dotad (etykieta "WMS" bez zmian).
7. BDOT10k GPKG (`extract_from_zip`) -> hak `save=self._extract_gpkg_from_zip`;
   przerwany strumien (`RequestException`) nadal ponawiany. Rozpakowanie
   nadal z `BytesIO` (zmiana na plik tymczasowy z review = osobna decyzja).

Usuniete: atrybuty `RETRY_BACKOFF_BASE` szesciu providerow (martwe);
`MAX_RETRIES` klas = `transport.http.MAX_RETRIES`.

**Testy przeniesione** (bez oslabiania): `test_retry_policy` — 3 testy
parametryzowane po 7 providerach ida teraz przez WLASNY tor providera
(`download` z rekordem skorowidza, `download(url)` LAZ,
`download_by_admin_unit(SHP)`, `_download_via_wms`, `_download_via_wcs`),
nie przez usunieta metode; doszla asercja sleepow [2, 4] i "brak resztek
.tmp". `test_landcover` (BDOT10k/CORINE) i `test_soilgrids` — przez
`download_by_admin_unit`/`_download_via_wms`/`_download_via_wcs`
z sesja w konstruktorze; testy WMS URL patchuja
`kartograf.providers.corine.download_to`.

**Mutacje helpera** (pelna suita, po kazdej przywrocenie pliku):

| Mutacja `transport/http.py` | Padniete |
|---|---|
| `download_to` ponawia 404 (`if not is_retryable` -> `if False`) | 8: `test_not_found_is_not_retried[nmt,nmpt,orto,laz,bdot10k,corine,soilgrids]` + transport |
| `_write_atomic`: `temp_path.rename` zamiast `os.replace` | 8: `test_redownload_overwrites_existing_file[x7]` + transport |
| `backoff_delay` = `2**attempt` (1/2 s) | 13: `test_exhausted_server_errors_keep_status[x7]`, `TestSingleQueryRetries[cuzk_query,bdot10k_teryt]`, gugik/orto `test_download_exponential_backoff`, 2x transport |
| hak `validate` pominiety | CORINE `test_download_via_wms_error_response`, SoilGrids `test_download_via_wcs_xml_error` |
| hak `save` pominiety | BDOT10k `test_download_by_admin_unit_returns_existing_gpkg_path` |

Kazda z 7 dawnych kopii (NMT, NMPT, orto, LAZ, BDOT10k, CORINE,
SoilGrids) pada pod mutacjami 1-3 — wszystkie przeszly przez helper.

## D2 — sesja na watek (commit e9a1d3c)

**Przed:** 2 kopie co do znaku (`skorowidz.py:370-376`,
`bdot10k.py:483-489`) + `self._local = threading.local()` x2.
**Po:** `transport.http.SessionPerThread(injected=None, factory=None)`
z `.get()` i `.injected`; fabryka rozwiazywana przy pierwszym `get()`
w watku (patch w jednym miejscu: `kartograf.transport.http.make_gugik_session`).
Providery: `self._sessions` zamiast `self._session`. Testy: sciezki patcha
`...skorowidz.make_gugik_session`/`...bdot10k.make_gugik_session` ->
`kartograf.transport.http.make_gugik_session`; `provider._session = x` po
konstrukcji -> `provider._sessions.injected = x`; 3 nowe testy
`TestSessionPerThread`. Roznic zachowania brak.

**Mutacje:** (a) jedna sesja na instancje zamiast na watek -> padaja
`test_separate_session_per_thread` NMT i orto, BDOT10k
`test_threads_get_separate_sessions`, transport; (b) ignorowanie sesji
wstrzyknietej -> 143 testy (NMT, NMPT, orto, BDOT10k, skorowidz, cache,
WMS) — wszystkie trzy dawne miejsca uzycia.

## D19 — obwiednia bboxa EPSG:2180 (commit 8a2a4d1)

**Przed:** 3 metody: `corine.py:853` (`->3857`), `corine.py:876` i
`soilgrids.py:255` (`->4326`, identyczne). **Po:**
`transform/bbox.py::envelope_from_2180(bbox, target_crs)` — ta sama
operacja (`transform_bounds`, `densify_pts=21`, `always_xy=True`); wynik
bez zmian. Testy "obwiednia obejmuje wszystkie naroza" przepiete na tor
providera (BBOX z URL GetMap CORINE EEA 2018 / DLR 1990, `bbox_wgs84`
przekazany przez `SoilGridsProvider.download_by_bbox`).
**Mutacje:** `always_xy=False` -> CORINE `test_wms_dlr_bbox_covers_all_corners`,
`test_wms_eea_bbox_covers_all_corners`, SoilGrids
`test_download_by_bbox_sends_envelope_covering_all_corners` (+2 testy
helpera); `densify_pts=0` -> CORINE DLR (URL, wysokosc, naroza) i SoilGrids.
Szersze D5 (geometry/sheet_parser/cutout) poza zakresem.

## D13 — WCS GUGiK i walidacja godla (commit 6c39b8b)

**Przed:** `WCS_FORMATS` x2 (`gugik.py:134`, `gugik_orto.py:84`),
`_construct_wcs_url` x2 (`:454`, `:319`), `get_supported_formats` x2,
`validate_godlo` x2 (`:626`, `:422`), `GugikProvider.FORMAT_EXTENSIONS`
(`:141`) + `get_file_extension` (`:620`) = kopia `BaseProvider`.
**Po:** `providers/pl/wcs.py::GugikWcsMixin` (`WCS_FORMATS`,
`_construct_wcs_url`, `get_supported_formats`; provider podaje
`_wcs_target()` -> (endpoint, coverage)); `validate_godlo` w
`SkorowidzLayersMixin`; kopia `get_file_extension` usunieta (dziedziczy
`BaseProvider`). Publiczne metody zostaja na klasach (O4 — usuwanie
martwego API — poza zakresem). `kartograf/`: +65 / -109, testy bez zmian.
**Mutacje:** COVERAGEID w mixinie -> NMT, NMPT, orto `download_bbox`;
`validate_godlo` zawsze True -> NMT `TestGugikProviderValidation`, orto
`TestGugikOrtoProviderInfo`.

## D9 — stale polityk transformacji (commit 8f3a995, czesc CZ)

**Przed:** `dmr.py:86 _HORIZONTAL_POLICY`, `:89 _WARP_MARGIN_PX` i lustro
`cutout.py:53 WARP_MARGIN_PX`, `:56 _HORIZONTAL_POLICY`.
**Po:** `transform.crs.CONTENT_POLICY`, `transform.crs.WARP_MARGIN_PX`;
`dmr.py` importuje. **`download/cutout.py` nietkniety** (zakaz) — lustro
zostaje do przepiecia przez agenta `download/*`:
`from kartograf.transform.crs import CONTENT_POLICY, WARP_MARGIN_PX`,
usunac dwie definicje, `_HORIZONTAL_POLICY` -> `CONTENT_POLICY` w
`cutout.py:214`, poprawic komentarz "lustro ... toru CZ".
**Mutacje:** `CONTENT_POLICY` 0,5 m -> 19 testow `test_cuzk_dmr`;
`WARP_MARGIN_PX = 0` **przechodzilo cala suite** — dodany
`test_native_request_has_warp_margin_of_four_pixels` (pada pod mutacja).
Wycinek PL pod tymi mutacjami nie pada, bo ma jeszcze wlasna kopie.

## Czego nie zrobilem i dlaczego

- **D6** — wszystkie 3 miejsca w `cli/download_cmd.py` (`:273` helper,
  `:831`, `:2111`); `cli/*` = zakaz. Do zrobienia przez agenta CLI:
  zamienic oba f-stringi na `_print_transform_error(e)` (w `:2111`
  komunikat jest skladany do zmiennej `message` — sprawdzic, czy idzie
  dalej niz stderr).
- **D9 strona PL** (`download/cutout.py`) — zakaz `download/*`; patrz wyzej.
- **Sesja LAZ na watek** — LAZ nadal dzieli jedna `make_gugik_session()`
  miedzy watki puli CLI (rozjazd pkt 5 review). Zmiana wymaga przepiecia
  `_get_wfs_xml` (discovery = teren agenta LAZ); `download` LAZ uzywa
  `self._session` jak dotad.
- **BDOT10k ZIP przez plik zamiast `BytesIO`** (propozycja review) —
  zmiana zuzycia pamieci, nie deduplikacja; hak `save=` to umozliwia.
- `storage.py:407` `rename` (rozjazd pkt 3) — `download/*`.
- Historyczne wzmianki `_download_with_retry` w `docs/DECISIONS.md`
  (ADR z 2026-02/03) i `docs/PROGRESS.md` — zapis historii, bez zmian.

## Bilans linii (`git diff --stat 0f5e4f4..8f3a995`)

```
kartograf/: 12 files changed, 340 insertions(+), 898 deletions(-)   netto -558
tests/:     14 files changed, 310 insertions(+), 208 deletions(-)   netto +102
```

| Commit | D | kartograf/ | tests/ |
|---|---|---|---|
| e9a1d3c | D2 | +47 / -31 | +57 / -32 |
| 9c7aaa9 | D1 | +177 / -678 | +208 / -157 |
| 8a2a4d1 | D19 | +38 / -75 | +32 / -18 |
| 6c39b8b | D13 | +65 / -109 | 0 |
| 8f3a995 | D9 | +18 / -10 | +14 / -2 |
