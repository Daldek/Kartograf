# Review-1: zduplikowana logika i overengineering w `kartograf/` (przed 0.7.0)

Data: 2026-10-06. Galaz: `develop` @ `55070f8`. Zakres: caly pakiet
`kartograf/`, nacisk na `providers/pl/*`, `providers/cuzk/*`, `download/*`,
`transport/*`, `sources/*`, `cli/*`, `cache/*`.

Baseline zmierzony przed review (bez zmian w kodzie): `pytest -m "not live"`
= **2105 passed**, `ruff check` = OK, `mypy kartograf/` = **32 bledy** (zgodnie
z pamiecia projektu). Zaden plik kodu ani testow nie byl edytowany.

Dowody rozjazdow to cztery skrypty w `/tmp/claude-2001/review1/`
(`exp1_retry.py`, `exp2_uklad.py`, `exp3_warp.py`, `exp4_cz_bbox.py`); ich
wyniki sa wklejone ponizej przy odpowiednich znaleziskach. Wszystkie dzialaja
offline (mocki `requests.Session`, pliki w scratchu).

Wagi: **WYSOKA** = kopie juz roznia sie zachowaniem albo grozi to bledem;
**SREDNIA** = koszt utrzymania / ryzyko rozjazdu przy nastepnej zmianie;
**NISKA** = kosmetyka.

## Podsumowanie

| | WYSOKA | SREDNIA | NISKA | razem |
|---|---|---|---|---|
| Duplikacje (D) | 3 | 9 | 7 | 19 |
| Overengineering (O) | 0 | 6 | 6 | 12 |

Top 5 przed wydaniem — sekcja na koncu.

---

## Czesc 1 — zduplikowana logika

### D1. Petla retry + zapis atomowy: 6 kopii w providerach obok `transport/http.py` — WYSOKA

**Miejsca**

| Kopia | `_download_with_retry` | `_make_request` | `_save_response` |
|---|---|---|---|
| `providers/pl/gugik.py` | 491 | 559 | 565 |
| `providers/pl/gugik_orto.py` | 328 | 373 | 379 |
| `providers/pl/gugik_laz.py` | 569 | 611 | 617 |
| `providers/pl/bdot10k.py` | 479 (+`extract_from_zip`) | inline | 557 |
| `providers/corine.py` | 895 | inline | 966 |
| `providers/soilgrids.py` | 407 | inline | 478 |
| kanoniczny: `transport/http.py` | `download_to` 124, `get_with_retry` 85 | — | inline w `download_to` |

Lacznie ok. 400 linii tej samej petli (`for attempt`, `raise_for_status`,
zapis do `<plik>.<pid>_<tid>.tmp`, `rename`, `unlink` przy bledzie).

**Rozjazdy zachowania (dowod: `exp1_retry.py`, mock sesji zwracajacej 404/500,
`time.sleep` przechwycony):**

```
=== HTTP 404 ===
gugik._download_with_retry     sleeps=[]      -> DownloadError(status_code=404)
corine._download_with_retry    sleeps=[2, 4]  -> DownloadError(status_code=None)
soilgrids._download_with_retry sleeps=[2, 4]  -> DownloadError(status_code=None)
http.download_to               sleeps=[]      -> DownloadError(status_code=404)
http.get_with_retry            sleeps=[]      -> DownloadError(status_code=404)
=== HTTP 500 ===
gugik._download_with_retry     sleeps=[2, 4]  -> DownloadError(status_code=500)
corine._download_with_retry    sleeps=[2, 4]  -> DownloadError(status_code=None)
soilgrids._download_with_retry sleeps=[2, 4]  -> DownloadError(status_code=None)
http.download_to               sleeps=[1, 2]  -> DownloadError(status_code=500)
http.get_with_retry            sleeps=[1, 2]  -> DownloadError(status_code=500)
```

1. **CORINE/SoilGrids ponawiaja 404 trzykrotnie (6 s czekania) i gubia
   `status_code`** — znana luka (CLAUDE.md "Ograniczenia"), ale skutek jest
   praktyczny: `kartograf landcover download --source soilgrids` z bledna
   nazwa pokrycia (WCS odpowiada 404/400) czeka 6 s zamiast konczyc od razu, a
   konsument (Hydrolog) nie dostaje kodu HTTP w wyjatku.
2. **Wykladnik backoffu rozni sie miedzy kanonem a kopiami**: `http.py` liczy
   `2**attempt` od `attempt=0` (1 s, 2 s), providery od `attempt=1`
   (2 s, 4 s). Dokumentacja ("backoff wykladniczy") nie rozstrzyga, ktore jest
   prawda; przy `Retry-After` oba biora `max(backoff, retry_after)`, wiec dla
   429 roznica znika, dla 5xx zostaje.
3. **`Path.rename` vs `os.replace`**: kopie w providerach robia
   `temp_path.rename(output_path)` (gugik.py:586, orto:401, laz:636, bdot:573,
   corine:985, soilgrids:497, storage.py:407), kanon `os.replace`. Na POSIX to
   to samo; na Windows (`pyproject`: "OS Independent") `rename` na istniejacy
   plik rzuca `FileExistsError`, czyli `--force` na juz pobranym arkuszu
   padlby w torze GUGiK, a nie padlby w torze CUZK/`download_to`. Nie
   weryfikowane na Windows — flaguje jako rozjazd semantyki, nie
   potwierdzony blad.
4. **Komunikaty**: kanon po polsku ("bez ponowien"), kopie po angielsku
   ("not retried"); `download_to` po wyczerpaniu prob nie dopina `from
   last_error`.
5. **Sesje**: gugik/orto/bdot — jedna sesja na watek (`_session_for_thread`),
   LAZ — jedna wspolna `make_gugik_session()` dla wszystkich watkow puli CLI,
   CORINE/SoilGrids — `self._session or requests.Session()` **per wywolanie**
   (nowa sesja na kazde pobranie, nigdy nie zamykana; trzy miejsca:
   corine.py:589, 927, soilgrids.py:439).
6. **Zapytania jednoprobowe poza polityka**: `CuzkClient.query`
   (`providers/cuzk/client.py:80-85`) i `Bdot10kProvider._get_teryt_for_point`
   (`bdot10k.py:302`, pojedyncze `session.get`). TERYT jest udokumentowany w
   CLAUDE.md; **`CuzkClient.query` nie jest** — a to przez niego idzie
   walidacja arkusza SM5 (`_download_sm5` -> `sheet_index.sm5_sheet`) przed
   kazdym pobraniem DMR 4G, wiec chwilowy 5xx indeksu KladyMapovychListu
   konczy cale zadanie CZ bez ponowienia, wbrew "Max 3 proby retry".

**Proponowane jedno miejsce**: `transport/http.py::download_to(session, url,
output_path, *, timeout, retries, validate=None)` — z opcjonalnym hookiem
walidacji odpowiedzi (CORINE/SoilGrids sprawdzaja `Content-Type` xml/html,
CUZK sprawdza magic TIFF po zapisie). Providery GUGiK/CORINE/SoilGrids
wolaja `download_to(self._session_for_thread(), ...)`; BDOT10k dla ZIP
(`extract_from_zip`) pobiera do tmp przez `download_to` i rozpakowuje z pliku
zamiast z `BytesIO` w pamieci (dzis caly ZIP powiatu laduje w RAM:
`bdot10k.py:607-611`). `_session_for_thread` przenosi sie do `transport/http.py`
jako `SessionPerThread` (patrz D2). `CuzkClient.query` buduje URL z
`urlencode` i idzie przez `get_with_retry`.

**Ryzyko / kiedy**: 29 odwolan w 4 plikach testow (`test_retry_policy.py`,
`test_parallel_download.py`, `test_landcover.py`, `test_soilgrids.py`) patchuje
`_download_with_retry`/`_save_response`/`_make_request` — pelna konsolidacja
to backlog po 0.7.0. **Przed wydaniem**: (a) CORINE/SoilGrids dostaja
`is_retryable`/`http_failure` (mechaniczna zmiana jak w commicie 9bcc040,
3 linie na provider), (b) `CuzkClient.query` dostaje petle z
`is_retryable`/`retry_wait`, (c) decyzja o wykladniku backoffu (jedna stala
`RETRY_BACKOFF_BASE**attempt` z tym samym zakresem) + dopisanie do CLAUDE.md.

### D2. `_session_for_thread` — dwie identyczne kopie — NISKA

`providers/pl/skorowidz.py:369-375` (mixin) i `providers/pl/bdot10k.py:471-477`
— ten sam kod co do znaku (`threading.local`, `make_gugik_session`). BDOT10k
nie dziedziczy po `SkorowidzLayersMixin`, wiec skopiowal metode.
**Propozycja**: `transport/http.py::SessionPerThread` (maly obiekt z
`get()`), uzywany przez mixin i BDOT10k. Backlog (razem z D1).

### D3. Trzy parsery `uklad_xy` GUGiK ("PL-1992" / "PL-2000:S6") — WYSOKA

**Miejsca**: `providers/pl/skorowidz.py:38` (`_horizontal_crs` -> `(uklad,
zone)`), `sources/registry.py:409` (`horizontal_crs_for_uklad` -> kod EPSG),
`providers/pl/gugik_laz.py:110` (`LazTile.uklad` -> segment storage).

**Dowod rozjazdu (`exp2_uklad.py`)**:

```
uklad_xy       skorowidz._horizontal_crs  registry.horizontal_crs_for_uklad  LazTile.uklad(segment)
'PL-1992'      ('1992', None)             EPSG:2180                          1992
'PL-2000:S6'   ('2000', 6)                EPSG:2177                          2000
'PL-2000'      (None, None)               None                               2000
'PL-2000:S9'   (None, None)               None                               2000
' PL-1992'     (None, None)               EPSG:2180                          1992
'pl-2000:s6'   (None, None)               None                               1992
```

Skutki w jednym przebiegu LAZ (`cli/download_cmd.py:1593` + `:1496`): kafel z
`uklad_xy="PL-2000"` (bez strefy) laduje w segmencie `laz/pl_2000_...`
(`LazTile.uklad`), a jego sidecar dostaje `horizontal_crs` kanalu, czyli
`EPSG:2180` (`horizontal_crs_for_uklad` -> `None` -> kanal). Konsument
(Hydrograf) czyta wtedy wspolrzedne strefowe jako PL-1992. W torze skorowidza
wartosc ze spacja na poczatku/koncu odrzuca rekord ("bez ukladu lub
rozdzielczosci", skorowidz.py:189-195) i konczy `NoCoverageError`, podczas gdy
rejestr te sama wartosc akceptuje. Czy GUGiK publikuje takie wartosci — nie
wiadomo (fixtury maja czyste); rozjazd jest po naszej stronie.

**Propozycja**: jedna funkcja `sources/registry.py::parse_pl_uklad(value) ->
tuple[uklad, zone] | None` (strip + fullmatch, jak dzis `_horizontal_crs`),
na niej `horizontal_crs_for_uklad` i `LazTile.uklad` (ktory dalej robi
fallback na format godla, ale z TEJ samej odpowiedzi). **Przed wydaniem**
(maly zakres, kontrakt sidecara jest publiczny; 10 testow
`horizontal_crs_for_uklad` + testy `LazTile.uklad` pokrywaja regresje).

### D4. Parsowanie `--bbox "x,y,x,y"` — 5 kopii w CLI — SREDNIA

`cli/download_cmd.py:1128` (`_cmd_download_bbox`), `:1444`
(`_resolve_laz_bbox`), `:1804` (`_cz_download_bbox`),
`cli/landcover_cmd.py:143`, `cli/soilgrids_cmd.py:103`.

Rozjazdy: (1) `_cmd_download_bbox` i landcover/soilgrids drukuja podpowiedz
"Expected: ..." na **stdout** (nie stderr) — `-q` jej nie tlumi, a `2>` jej
nie lapie; `_cz_download_bbox` nie drukuje podpowiedzi; `_resolve_laz_bbox`
rzuca `ValueError` z innym tekstem. (2) landcover/soilgrids nie maja
`--bbox-crs` i wpisuja `EPSG:2180` na sztywno (zgodne z parserem argow, ale
to trzecia kopia tej decyzji). (3) Kopia w `_cz_download_bbox` (`if bbox is
None`, 1802-1810) jest z CLI **nieosiagalna** — `_dispatch_area` zawsze
przekazuje gotowy bbox, a `_run_cz(args)` bez bboxa to tryb godla; dociera do
niej tylko `tests/test_cli.py:3408`.
**Propozycja**: `cli/_args.py::parse_bbox_arg(text, crs) -> BBox` rzucajacy
`ValidationError` z jednym komunikatem; wszystkie piec miejsc wola ja, a
martwa galaz CZ znika. Backlog (kosmetyka), ale tani.

### D5. Przeliczanie obwiedni bboxa — 5 implementacji — SREDNIA

1. `core/geometry.py:417 _transform_bbox` — 4 narozniki, domyslny transformer
   pyproj (ballpark dozwolony); wolana z 4 miejsc z identyczna 6-argumentowa
   sygnatura (`cutout.py:151`, `download_cmd.py:299`, `:433`, `:1464`).
2. `providers/cuzk/dmr.py:564 bbox_to_crs` — 9 probek na krawedz, operacja
   przypieta (ADR-024).
3. `core/sheet_parser.py:658-681 SheetParser.get_bbox("EPSG:2180")` — 4
   narozniki, nowy `Transformer.from_crs` przy KAZDYM wywolaniu.
4. `download/cutout.py:575-609 _sheet_frame_2180` — to samo co (3) z
   transformerem w `functools.cache` (N9: 1221 arkuszy 9 s -> 0,2 s).
   Komentarz w kodzie przyznaje, ze to kopia `get_bbox` zrobiona z powodu
   wydajnosci — naprawa nalezy do `sheet_parser`, nie do `cutout`.
5. `providers/corine.py:847/870` i `providers/soilgrids.py:249` —
   `transform_bounds(densify_pts=21)`; `_transform_bbox_to_wgs84` jest
   identyczne w obu plikach co do znaku.

Dodatkowo decyzja "uklad czeski => operacja przypieta" zyje w dwoch zapisach:
`cutout.py:58 _CZ_CRS` (zbior napisow, `strip().upper()`) i
`download_cmd.py:279 _CZ_CRS_WKIDS` (zbior wkid, `wkid()` bez strip).
`exp4_cz_bbox.py`: etykieta `"5514"` -> cutout bierze transformer domyslny, CLI
przypiety; `"EPSG:5514 "` -> odwrotnie. Wynik liczbowy dla `"5514"` byl
identyczny (dx = dy = 0,00 m — pyproj wybral te sama operacje), wiec to nie
jest potwierdzony blad, tylko dwa rozne testy tej samej decyzji.
**Propozycja**: `transform/bbox.py::transform_bbox(bbox, target, *,
pinned=None, samples=2)` — jedna funkcja, probkowanie krawedzi parametrem,
jeden cache transformerow per para ukladow; `SheetParser.get_bbox` korzysta z
tego cache (znika `_sheet_frame_2180`), `is_czech_crs(label)` w jednym
miejscu (`wkid` po `strip`). Backlog — zmiana dotyka torow, ktore przeszly
testy na zywo; przed wydaniem tylko przeniesienie cache transformera do
`sheet_parser` (zero zmiany wyniku, usuwa 35 linii z `cutout.py`).

### D6. Komunikat `TransformError` z remedium — 3 kopie — NISKA

`cli/download_cmd.py:267 _print_transform_error` istnieje, ale
`_resolve_cz_geometry_bbox` (`:823-826`) i `_cmd_download_cz` (`:1944-1946`)
skladaja ten sam f-string recznie. Zamienic na wywolanie helpera. Backlog,
5 minut.

### D7. Pisanie sidecara — 5 opakowan "best-effort" + 2 kopie formatu `transform` + 2 kopie nazwy pliku `bbox/<coords>.tif` — SREDNIA

Opakowania `try: build_metadata(...); write_sidecar(...) except Exception:
logger.warning("Nie udalo sie zapisac sidecara dla ...")`:
`download/manager.py:871`, `landcover/manager.py:417`,
`download/cutout.py:492`, `cli/download_cmd.py:1478` (LAZ), `:1668` (CZ).
`write_sidecar` sam juz lapie `OSError` (sidecar.py:349-353), wiec kazde
opakowanie dubluje polityke "nigdy nie przerywaj pobrania", a kazde inaczej:
manager zwraca cicho, gdy `descriptor_key` nie jest `str`; LAZ podstawia
`"pl.gugik.laz"`; CZ i cutout **nadpisuja** `meta.horizontal_crs` po
`build_metadata` zamiast podac `horizontal_crs=` (parametr istnieje od N8,
`sidecar.py:293`).
Format opisu operacji `f"pinned: {pinned.description} ({pinned.accuracy_m}
m)"` — `cutout.py:544` i `download_cmd.py:1709`. Nazwa wycinka
`"_".join(format(v, ".10g") ...)` — `cutout.py:230` i `download_cmd.py:1820`
(trzecia, pokrewna kopia w `cuzk/client.py:229` dla parametru URL).
**Propozycja**: `sources/sidecar.py::emit_sidecar(descriptor_key, data_path,
*, request, vertical_crs, horizontal_crs=None, transform=None, extra=None)`
— jedyne miejsce z `try/except` i logiem; `PinnedTransform.sidecar_label`
(wlasnosc); `cutout_filename(bbox)` w `download/cutout.py` uzywany tez przez
tor CZ. Backlog; ryzyko niskie (testy sidecarow sprawdzaja tresc JSON, nie
sciezke wywolania).

### D8. `cuzk/dmr.py::_warp_to_grid` vs `transform/raster.py::warp_to_grid` (+ `_quiet_transformer_only_option` x2) — WYSOKA

`transform/raster.py:127` powstal jako "sparametryzowany wzorzec
`providers/cuzk/dmr.py::_warp_to_grid`" (docstring modulu), ale oryginal
(`dmr.py:500-561`) zostal i obie kopie juz sie rozjechaly:

| | `dmr._warp_to_grid` | `raster.warp_to_grid` |
|---|---|---|
| awaria warpu | **kasuje `dst_path`** (`:558`) | zostawia poprzedni plik (`:226-228`) |
| zgodnosc pary ukladow z `pinned` | brak kontroli | `TransformError` (`:164-171`) |
| zrodlo bez CRS / Int32 | brak owijania w VRT | VRT z wymuszonym SRS i Float32 |
| nodata | stala `CUZK_NODATA` | parametr |
| lista zrodel (W1) | nie | tak |

**Dowod (`exp3_warp.py`, nieistniejace zrodlo, pod `dst` lezy "poprzedni
wynik")**:

```
dmr._warp_to_grid      awaria=RasterioIOError  poprzedni plik istnieje po awarii: False
raster.warp_to_grid    awaria=RasterioIOError  poprzedni plik istnieje po awarii: True
```

Praktycznie: `kartograf download --bbox ... --country cz --target-crs
EPSG:2180 --force` z awaria w trakcie warpu (np. brak miejsca, przerwany
GDAL) **usuwa poprzedni, poprawny wycinek**, podczas gdy ten sam scenariusz
po stronie PL go zachowuje — a pomoc `--force` obiecuje "nieudana przebudowa
zostawia poprzedni plik" (`cli/_parser.py:146-148`; formalnie o PL, ale
uzytkownik nie rozroznia). `_quiet_transformer_only_option` jest skopiowane
1:1 (`dmr.py:479`, `raster.py:47`, drugi z komentarzem "lustro").
**Propozycja**: w `_export_raster` (`dmr.py:306`) wywolac
`warp_to_grid(native_path, output_path, bbox, self._pixel_size, pinned,
src_crs=NATIVE_CRS, nodata=CUZK_NODATA)` i usunac `_warp_to_grid` oraz lokalny
filtr GDAL (ok. 90 linii). **Przed wydaniem**: zmiana jednej linii + usuniecie
kopii; testy `test_cuzk_dmr.py` (warp, nodata nie wchodzi w interpolacje,
`test_bbox_target_crs_puts_content_where_pyproj_says`) sa niezalezne od
nazwy funkcji — po zmianie uruchomic je i porownac bit w bit wynik kafla
TM33 z fixtura, jesli taka istnieje.

### D9. Stale polityk transformacji "lustrzane" — NISKA

`cutout.py:53 WARP_MARGIN_PX` = `dmr.py:92 _WARP_MARGIN_PX`;
`cutout.py:56 _HORIZONTAL_POLICY` = `dmr.py:89 _HORIZONTAL_POLICY`; obie
z komentarzem "lustro". Wartosci identyczne, wiec bez bledu — ale komentarz
zamiast importu to zaproszenie do rozjazdu. Przeniesc do `transform/crs.py`
(`CONTENT_POLICY`, `WARP_MARGIN_PX`). Backlog.

### D10. `DownloadManager`: tresc "pobierz jeden arkusz" w trzech miejscach — SREDNIA

`download_sheet` (`manager.py:342-355`), `_download_single_sheet_task`
(`:530-547`), `_download_hierarchy_sequential` (`:563-639`). Trzecia kopia
NIE korzysta z drugiej, choc parallel tak robi; w efekcie tryb sekwencyjny
emituje `DownloadProgress(status="downloading")`, a rownolegly nie, i tryb
sekwencyjny przepuszcza `OSError`, a rownolegly go polyka jako "failed"
(udokumentowane w docstringu, ale to skutek kopii, nie decyzja). Do tego
`_download_hierarchy_parallel` buduje `DownloadProgress` w trzech
rownoleglych galeziach `if status == ...` (`:711-740`), ktore roznia sie tylko
`message`. **Propozycja**: `_download_hierarchy_sequential` wola
`_download_single_sheet_task` i jeden `_emit(on_progress, i, total, godlo,
status, message)`; obie petle dziela te sama funkcje raportujaca. Backlog
(testy `test_parallel_download.py` sprawdzaja sekwencje statusow — do
zaktualizowania swiadomie).

### D11. Regula "5 m => EVRF2007" w 4 miejscach z 3 roznymi skutkami — SREDNIA

`providers/pl/gugik.py:174-181` -> `ValueError`;
`providers/pl/__init__.py:36-41` -> warning + podmiana;
`download/manager.py:220-225` -> warning + podmiana ("celowa redundancja" wg
pamieci projektu); `download/cutout.py:190-191` -> `ValidationError`.
Skutek dla uzytkownika CLI: `--resolution 5m --vertical-crs KRON86` nie konczy
sie bledem, tylko logiem (niewidocznym bez konfiguracji logowania) i plikiem w
segmencie `..._evrf2007` — podczas gdy ten sam KRON86 dla CZ to twardy blad
(`_validate_cross_country`, `CuzkDmrProvider.__init__`). To rozjazd polityki
"nie zgaduj za uzytkownika" (ADR-023 pkt 5 odrzuca ciche pomijanie).
**Propozycja**: jedna regula w fabryce (`create_nmt_provider`), manager i
cutout ja tylko wolaja; CLI drukuje `Info:` na stderr o podmianie (jak
`--country auto -> pl`). Przed wydaniem rozwazyc choc `Info:` (3 linie);
reszta backlog.

### D12. Wzorce godel CZ i walidacja bboxa — po dwie kopie — NISKA

`core/parser_registry.py:89-90` (`_CZ_TM33_PATTERN`, `_CZ_SM5_PATTERN`) vs
`providers/cuzk/sheets.py:50` (`_SM5_RE`) i `core/parser_tm33.py:18`
(`_GODLO_RE`). `Sm5Sheet.__init__` robi `strip()` przed dopasowaniem,
`SheetIndex.sm5_sheet` i rejestr — nie. Walidacja "min >= max" +
"zly CRS": `parser_tm33.py:68-84` (`!=` doslowne) vs `sheets.py:173-185`
(`strip().upper()`). Jedno zrodlo wzorcow w `core/parser_tm33.py` /
`core/parser_sm5.py` i jedna `validate_bbox(bbox, crs)` w `core/sheet_parser`.
Backlog.

### D13. `_construct_wcs_url`, `WCS_FORMATS`, `validate_godlo`, `FORMAT_EXTENSIONS` — gugik vs orto vs base — NISKA

`gugik.py:454` i `gugik_orto.py:308` roznia sie tylko zrodlem endpointu i
coverage id; `WCS_FORMATS` identyczny slownik w obu; `validate_godlo`
(`gugik.py:626`, `gugik_orto.py:411`) identyczne; `GugikProvider.FORMAT_EXTENSIONS`
(`:141`) i `get_file_extension` (`:620`) to doslowna kopia
`BaseProvider.get_file_extension` (`base.py:158`). Zadne z tych nie ma
wywolan poza testami (patrz O4). Usunac razem z O4. Backlog.

### D14. Podpowiedzi `NoCoverageError` — NISKA

`gugik.py:319-349` i `gugik_orto.py:212-247` powtarzaja petle "potomek
PL-2000 -> `--scale`" i "inny uklad -> `--system`". Wyodrebnic
`skorowidz.py::coverage_hints(parser, records)`; roznica (rozdzielczosc u NMT,
warianty koloru u orto) zostaje w providerze. Backlog.

### D15. "Found N sheets ... Sheets: ..." — 2 kopie w CLI — NISKA

`cli/download_cmd.py:1278-1287` i `:1383-1393` (ten sam skrot `[:3] + ['...']
+ [-2:]`). Jedna `_print_sheet_list(godla, scale, what, label)`. Backlog.

### D16. Cykl zycia `MetadataCache` — 3 wzorce, rozna semantyka `--force` — SREDNIA

PL: `_pl_metadata_cache` (`download_cmd.py:122`) — `--force` => brak cache
(ani odczyt, ani zapis; udokumentowane N6/P4). CZ: `_cmd_download_cz`
(`:1934-1967`) otwiera `MetadataCache()` zawsze — `--force` pobiera plik na
nowo, ale indeks arkuszy SM5 nadal idzie z cache (TTL 30 d). Trzeci wzorzec:
`Sm5Sheet.get_bbox` (`sheets.py:152-167`) otwiera i zamyka wlasny cache na
jedno zapytanie (osiagalny tylko przez `parser_factory`, ktorego produkcja nie
wola — patrz O3). Ta sama flaga znaczy co innego po obu stronach granicy.
**Propozycja**: jeden kontekst `metadata_cache(args)` dla obu krajow (CZ tez
honoruje `--force` = `None`). Przed wydaniem jako decyzja (albo 5 linii
kodu, albo zdanie w CLAUDE.md, ze CZ nie omija cache indeksu).

### D17. Trzy pule watkow z wlasnym protokolem wynikow — SREDNIA

`download/manager.py:649-748` (krotki `(godlo, path, status, message)`),
`cli/download_cmd.py:1592-1615` (LAZ: krotki `("ok"|"skip"|"fail", ...)`),
`landcover/manager.py:357-392` (`Path | None`). Pula LAZ zyje w CLI, wiec
biblioteka NIE udostepnia rownoleglego pobierania kafli LAZ ani sidecarow
LAZ (`_write_laz_sidecar` tez jest w CLI) — wbrew zasadzie z `cutout.py`
("CLI jest nakladka na modul biblioteczny"). Hydrograf, chcac LAZ, musi
powielic `_cmd_download_laz`. **Propozycja**: `download/laz.py::download_laz_tiles(
tiles, storage, provider, *, max_workers, skip_existing, on_progress)`
zwracajacy `DownloadResult`; CLI drukuje. Backlog (etap 2 i tak dotyka LAZ).

### D18. Storage providera budowany w 4 miejscach — NISKA

`cli/download_cmd.py:72-118 _create_provider_and_storage` buduje
`FileStorage(product=..., vertical_crs=getattr(provider, "vertical_crs", ...))`,
`DownloadManager.__init__` (`manager.py:239-253`) zbudowalby identyczny z
deskryptora, `run_pl_cutout` (`cutout.py:744-749`) i `estimate_pl_cutout_bytes`
(`:623-627`) buduja `FileStorage(resolution=..., vertical_crs=...)`.
Sprawdzilem, ze dla NMT/NMPT/orto szablony wychodza te same (brak rozjazdu).
Jedna fabryka `storage_for(provider, output_dir)` w `download/storage.py`.
Backlog.

### D19. `_transform_bbox_to_wgs84` / `_transform_bbox_to_epsg3857` — NISKA

`corine.py:870` i `soilgrids.py:249` identyczne; `corine.py:847` rozni sie
tylko kodem docelowym. Wchodzi w D5. Backlog.

---

## Czesc 2 — overengineering i martwy kod

Metoda: `grep` wywolan w `kartograf/` z wykluczeniem definicji i docstringow;
liczby "tests=" to odwolania w `tests/`.

### O1. `FileStorage`: 6 publicznych metod bez ani jednego wywolania w pakiecie — SREDNIA

`download/storage.py`: `ensure_directory` (322), `exists` (340),
`write_atomic` (358), `delete` (416), `list_files` (442), `get_size` (472).
Dowod: `grep -rn "\.write_atomic(\|\.ensure_directory(\|\.get_size(\|\.list_files(\|storage\.delete(\|_storage\.exists(" kartograf/`
= 0 trafien poza docstringiem (`exists` ma jedno — w `get_missing_sheets`,
ktory sam jest martwy, O2). `write_atomic` to siodma kopia zapisu atomowego
(D1) z 41 odwolaniami w testach. Koszt: 170 linii + testy utrzymywane dla API,
ktorego nie uzywa ani CLI, ani `DownloadManager`, ani cutout.
**Propozycja**: usunac (bez shima — decyzja projektu); przed usunieciem
`grep` w Hydrografie/Hydrologu, bo to API publiczne (`from kartograf import
FileStorage`). Backlog — zmiana BREAKING do CHANGELOG 0.7.0 albo 0.8.0.

### O2. Martwe API `DownloadManager`/`DownloadResult`/`DownloadProgress` — NISKA

`DownloadManager.get_missing_sheets` (`manager.py:821-849`, 0 wywolan),
`DownloadResult.all_paths` (`:99-102`, 0 — trafienia `all_paths` w CLI to
zmienna lokalna), `DownloadProgress.progress_percent` (`:57-62`, 0; CLI liczy
pasek sam, `download_cmd.py:43`). Usunac. Backlog.

### O3. `core/parser_registry.py`: rejestr wtyczek z `register_system`/`parser_factory`, ktorych produkcja nie wola — SREDNIA

`parser_factory` (`:22`) jest ustawiane w 4 rejestracjach i czytane
**wylacznie** w `tests/test_parser_registry.py:55-112`; cztery leniwe fabryki
`_make_parser_*` (`:77-106`) wraz z komentarzem o unikaniu cyklu importow
istnieja tylko po to. `register_system` jest API publicznym, ale wywolanym 4
razy w tym samym module, bez trzeciego kraju w planie 0.7.0. Produkcja uzywa
rejestru do dwoch rzeczy: `detect_system` (kraj + id) i `path_parts`.
Uboczny skutek: `Sm5Sheet.get_bbox` z wlasnym cyklem cache (D16) jest kodem
osiagalnym tylko z testow. **Propozycja**: zostawic `SheetSystem(id, country,
detect, path_parts)` i `detect_system`; usunac `parser_factory`, fabryki i
`Sm5Sheet.get_bbox` (ParserTM33/Sm5Sheet dalej konstruowane wprost tam, gdzie
potrzebne: `dmr.py:236`). Backlog.

### O4. API klas bazowych i aliasy "deprecated" bez wywolan — SREDNIA

- `BaseProvider.get_supported_formats`/`get_file_extension`/`validate_godlo`
  (`base.py:147-196`): jedyne wywolanie `get_supported_formats` to
  `LandCoverManager.get_supported_formats` (`landcover/manager.py:465`), ktore
  samo nie ma wywolan; `get_file_extension`/`validate_godlo` — 0.
- `GugikProvider.get_supported_resolutions` (`gugik.py:595`),
  `get_supported_vertical_crs_for_resolution` (`:599`), `is_wcs_available`
  (`:634`), `CorineProvider.get_clc_classes` (`corine.py:1008`),
  `ParserTM33.tile_for` (`parser_tm33.py`), `registry.sources_for` — 0 wywolan
  poza testami. `_get_opendata_url` (`gugik.py:294`, `gugik_orto.py:192`) to
  dwulinijkowe opakowanie `_resolve_sheet(...).url` z **79** odwolaniami w
  testach i zerem w produkcji — testy cwicza martwy wrapper.
- `LandCoverProvider.source_url`, `download_by_teryt`, `validate_teryt`
  (`base.py:240, 297, 406`) sa opisane jako "deprecated alias" — wbrew decyzji
  "bez shimow zgodnosciowych". Alias jest tu jednak API **faktycznym**:
  `LandCoverManager` wola `download_by_teryt` (`landcover/manager.py:198,
  243`), a CORINE/SoilGrids nadpisuja `download_by_teryt` (`corine.py:730`,
  `soilgrids.py:379`) zamiast kanonicznego `download_by_admin_unit` (ktore w
  bazie i tak rzuca `NotImplementedError` — nadpisania roznia sie tylko
  trescia komunikatu). Polowiczna zmiana nazwy: dwie nazwy, jedna
  semantyka.
**Propozycja**: zdecydowac o JEDNEJ nazwie (sugestia: `download_by_teryt`,
bo tylko PL ma jednostki administracyjne w 0.7.0 i tak nazywa to CLI), usunac
druga i trzy aliasy; usunac metody bez wywolan. Backlog, wpis BREAKING.

### O5. Deskryptory jako dokumentacja-w-kodzie: pola bez konsumenta — SREDNIA

Pola `SourceDescriptor`/`AccessChannel`/`CountryProfile` bez odczytu w
pakiecie (odczyty sa tylko w `tests/test_sources.py`): `tile_scheme` +
klasa `TileScheme` (`descriptor.py:56-64`), `server_reprojection`, `auth`,
`notes`, `CountryProfile.dataset_keys`; czlonkowie `TransportKind.ARCGIS_QUERY`,
`OGC_API_FEATURES` (DE/SK, poza zakresem 0.7.0); `KNOWN_PATHS`/`KnownPath`
(`transform/crs.py:125-183`, "w etapie 0 konsumowana w testach" — nadal
tylko tam). Konsumowane realnie: `storage_subdir`, `default_extension`,
`license`, `resolution`, `country`, `product`, `provider_name`, `channels[].{
transport, horizontal_crs, vertical_crs_options, vertical_source,
capabilities, endpoint}`. Dla PL `endpoint=""` — prawdziwe URL-e zyja w
stalych providerow, wiec dla PL deskryptor i provider to dwa zrodla prawdy
(udokumentowane w `descriptor.py:52-53`, ale to koszt: zmiana endpointu WMS
nie dotyka deskryptora, a test spojnosci tego nie zlapie). To decyzja
ADR-022 (dane dla etapow 2-3) — nie postuluje jej cofania; postuluje
**oznaczyc** pola bez konsumenta jednym komentarzem "etap 2+" i przeniesc
`KNOWN_PATHS` do `tests/` (tabela referencyjna testow nie musi byc w
pakiecie). Backlog.

### O6. Parametry konstruktorow, ktorych nikt nie przekazuje / ktore sa ignorowane — NISKA

- `GugikLazProvider(cache=)` — docstring: "Unused placeholder for API
  symmetry"; `_CACHE_PRODUCT = "laz"` (`gugik_laz.py:181`) — 0 uzyc.
- `SoilGridsProvider(cache=)` — "Currently unused ... accepted for API
  consistency" (`soilgrids.py:142`).
- `DownloadManager(vertical_crs=, resolution=)` sa nadpisywane przez
  `provider.vertical_crs` i uzywane tylko do domyslnego storage — a CLI
  (`download_cmd.py:954-964`, `:1399-1410`) i `run_pl_cutout`
  (`cutout.py:751-759`) przekazuja **i** provider, **i** storage, **i** oba
  parametry (z komentarzem, ze to po to, "zeby manager nie ostrzegal drugi
  raz"). Trzy argumenty opisuja jedna rzecz.
- `CuzkDmrProvider._client_for(timeout)` buduje nowego klienta dla
  niedomyslnego timeoutu, ale `download(timeout=)` nie jest nigdzie
  przekazywany z CLI ani managera.
**Propozycja**: usunac `cache=` z LAZ/SoilGrids (fabryki CLI i tak go nie
podaja), uprosic `DownloadManager(provider=None, storage=None, *, output_dir,
max_workers, sidecar_extra)` z wyprowadzaniem `vertical_crs`/`resolution`
z providera. Backlog.

### O7. `LandCoverManager`: trzy metody-dublety i nieuzywane pole — NISKA

`download_by_teryt/bbox/godlo` (`landcover/manager.py:217-312`) powtarzaja
cialo `download()` (ta sama walidacja, ten sam sidecar) i nie maja wywolan
(CLI uzywa `download(...)`). `self._storage = FileStorage(output_dir)`
(`:85`) jest przypisywane i nigdy czytane. Usunac. Backlog.

### O8. `cli/commands.py` "fasada zgodnosci" i `providers/__init__.py` "historical subset" — NISKA

`cli/commands.py:336-368` re-eksportuje prywatne `_create_provider_and_storage`
i `_resolve_laz_bbox` "dla testow"; `providers/__init__.py` re-eksportuje
czesc providerow z przyznaniem w docstringu, ze lista jest niepelna. Oba sa
shimami, ktorych decyzja projektu zakazuje; testy moga importowac z modulow
docelowych (pamiec projektu juz to robi: patchuja `kartograf.cli.download_cmd.*`).
Zostawic w `commands.py` wylacznie `main`/`create_parser`. Backlog.

### O9. `MetadataCache._create_tables`: `DROP TABLE IF EXISTS url_cache` przy kazdym otwarciu — NISKA

`cache/metadata.py:93` — migracja po usunietym `url_cache`, wykonywana przy
kazdym `MetadataCache()` (kazde zadanie CLI). Nieszkodliwe; usunac w 0.8.0
po jednym cyklu wydan. Backlog.

### O10. `download_pl_cutout` waliduje to, co zaraz zwaliduje `prepare_pl_cutout` — NISKA

`cutout.py:894-899` powtarza kontrole `resolution`/`vertical_crs` z
`:184-191`. `PlCutoutSheets` (`:101-105`) to dataclass z jednym polem
`godla: tuple[str, ...]` — opakowanie krotki bez zachowan. Usunac
powtorzenie; `PlCutoutSheets` zostawic tylko, jesli etap 2 doda do niego
pola. Backlog.

### O11. `_cz_download_bbox`: galaz `if bbox is None` osiagalna tylko z testow — NISKA

Patrz D4 pkt 3 (`download_cmd.py:1802-1810`, test `test_cli.py:3408`).
Usunac galaz i test; sygnatura `_cz_download_bbox(args, provider, bbox: BBox,
...)` bez `None`. Backlog.

### O12. `BaseProvider.download_bbox(format=)` i formaty PNG/JPEG WCS — NISKA

`WCS_FORMATS` z PNG/JPEG (`gugik.py:134`, `gugik_orto.py:85`) i parametr
`format` w `DownloadManager.download_bbox` — jedyna sciezka produkcyjna
(`cli/download_cmd.py:1840`, tor CZ) wola `download_bbox(bbox, target)` z
domyslnym GTiff; `CuzkDmrProvider.download_bbox` odrzuca inne formaty.
Biblioteczny `DownloadManager.download_bbox` (WCS KRON86) jest legalny, ale
PNG/JPEG NMT nikt nie konsumuje. Zostawic do decyzji; nie postuluje usuwania
przed wydaniem.

---

## Odrzucone hipotezy (sprawdzone, bez znaleziska)

- `_save_response` w LAZ/BDOT/CORINE/SoilGrids nie robi `mkdir` (gugik/orto
  robia) — ale kazdy wolajacy (`gugik_laz.py:556`, `bdot10k.py:199`,
  `corine.py:~410`, `soilgrids.py:~300`) tworzy katalog wczesniej; brak bledu.
- `DownloadManager.expand_sheets` powtarza regule "PL-2000 albo 1:10000 =
  lisc" z `download_sheet` — 2 linie, ta sama semantyka, nie warto
  wyodrebniac.
- `DownloadManager.download_bbox` bez wywolan w CLI — to swiadome API
  biblioteczne (WCS KRON86), udokumentowane; nie jest martwe.
- Wspolna `requests.Session` miedzy watkami puli LAZ (`gugik_laz.py:185`) —
  praktyka powszechna, `pool_maxsize=8`; bez dowodu bledu nie flaguje.
- Etykieta `"5514"` w `cutout._bbox_to_2180` (transformer domyslny) vs CLI
  (przypiety): wynik liczbowo identyczny (`exp4`), wiec to tylko D5, nie blad.
- `_HORIZONTAL_POLICY`/`WARP_MARGIN_PX` — lustra maja te same wartosci (D9,
  NISKA), nie rozjazd.
- `SkorowidzRecord.full_sheet` parsowane, nieuzywane w selekcji — trafia do
  `extra.source` sidecara, wiec ma konsumenta.
- `has_valid_pixels`, `read_asc_nodata`, `_read_tif_nodata` — rozne formaty,
  nie duplikaty.
- Walidacja warstw WMS (`_fetch_wms_layers`) — jedna implementacja w mixinie
  od 2026-06, orto juz z niej korzysta; duplikacja z pamieci projektu
  nieaktualna.

---

## Rekomendacje przed wydaniem 0.7.0 (max 5)

1. **D8** — `cuzk/dmr.py::_export_raster` przelaczyc na
   `transform/raster.warp_to_grid` i usunac `_warp_to_grid` +
   `_quiet_transformer_only_option` z `dmr.py`. Naprawia realny rozjazd
   (`--force` + awaria warpu kasuje poprzedni wycinek CZ), zmniejsza kod o
   ~90 linii, testy CZ zostaja bez zmian. Ryzyko: niskie; po zmianie
   uruchomic `tests/test_cuzk_dmr.py` i jeden przebieg na zywo kafla TM33.
2. **D1 (a)+(b)** — CORINE i SoilGrids: `is_retryable`/`retry_wait`/
   `http_failure` jak w 9bcc040 (zero czekania na 404, `status_code` w
   wyjatku); `CuzkClient.query` z ta sama petla (indeks SM5 przed kazdym
   DMR 4G). Ryzyko: niskie; `test_retry_policy.py` jest sparametryzowany po
   klasach — dopisac corine/soilgrids/CuzkClient do parametryzacji.
3. **D1 (c)** — jeden wykladnik backoffu (`http.py` 1/2 s vs providery
   2/4 s): wybrac, ujednolicic, zapisac w CLAUDE.md "Ograniczenia". Ryzyko:
   zerowe funkcjonalnie; testy z `time.sleep` zamockowanym sprawdzaja wartosci
   — poprawic w jednym miejscu.
4. **D3** — jeden parser `uklad_xy` (`registry.parse_pl_uklad`), uzyty przez
   `horizontal_crs_for_uklad`, `skorowidz._horizontal_crs` i `LazTile.uklad`.
   Zamyka rozjazd "segment PL-2000, sidecar EPSG:2180" dla kafla bez strefy.
   Ryzyko: niskie (10 + ~8 testow pokrywaja obie strony).
5. **D16** — decyzja o `--force` dla CZ: albo `_cmd_download_cz` uzywa
   `_pl_metadata_cache`-podobnego kontekstu (cache = None pod `--force`),
   albo jedno zdanie w CLAUDE.md, ze CZ nie omija cache indeksu arkuszy.
   Ryzyko: zerowe.

Reszta (D4, D5, D7, D10, D11, D17 i wszystkie O) — backlog po wydaniu, z
jedna uwaga porzadkowa: O1/O4 to API publiczne pakietu, wiec ich usuniecie
wymaga grepa w Hydrografie/Hydrologu i wpisu BREAKING, a nie shima.
