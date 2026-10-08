# Final review galezi `fix/release-0.7.0-audit` (ff145a9..7e6036b, 66 commitow)

Reviewer: Senior Code Reviewer (fable), 2026-08-23. Read-only; zadnych zmian w drzewie.

### Verdict: NEEDS ONE FIX WAVE

Mala fala: **1 poprawka kodu (S)**, 1 decyzja kontrolera (kod S warunkowy), reszta to
docs/docstringi XS. Zero ustalen Critical, zero naruszen kontraktow ADR-022/023/024,
zero regresji funkcjonalnych wykrytych miedzy zadaniami. Blokuja wylacznie: falszywe
zdania w dokumentach-kontraktach (CLAUDE.md, README tabela sidecara, SCOPE, ADR-025
przypis) oraz niedomkniety fix N4-1 (wyscig `__new__` singletonu — udowodniony
snippetem, osiagalny przez publiczne `LandCoverManager.download_batch()` z domyslnym
`max_workers=4`).

### Global Constraints

| | Status | Dowod |
|---|---|---|
| (a) zero shimow | OK | `git diff ff145a9..7e6036b -- kartograf/ \| grep -i "alias\|compat\|shim"` -> jedyne trafienie to docstring `SheetParser` ("aliases are planned for the next major"); `kartograf.__all__` bez zmian (31 nazw), `kartograf/__init__.py` nie w diffie |
| (b) test przypinajacy per naprawa | OK | 27 sprawdzonych nazw testow z planu (po jednym na zadanie 1-21) — 27/27 istnieje w `tests/` (`grep -rl "def <nazwa>"`); ledger niesie RED/GREEN per zadanie |
| (c) ruff / format / mypy | OK | `ruff check kartograf/ tests/` -> `All checks passed!`; `ruff format --check` -> `83 files already formatted`; `mypy kartograf/` -> `Found 32 errors in 9 files` (baseline 33) |
| (d) ADR-022/023/024 | OK | `exportImage` wolane wylacznie z `image_sr=NATIVE_CRS` (dmr.py:278-299, oba wywolania); `ResultMetadata.schema == "kartograf-meta/1"` (`sources/sidecar.py` nie w diffie); `parent_request` budowany w `_dispatch_area` dla KAZDEGO trybu bbox/geometry, takze po `auto -> pl` (download_cmd.py:~488); `server_reprojection=False` dla obu CZ; lokalny warp `_warp_to_grid` nietkniety |
| (e) ASCII | OK (z rulingiem) | diakrytyki PL: DEVELOPMENT_STANDARDS 0->0, IMPLEMENTATION_PROMPT 0->0, PROGRESS 1->1, CLAUDE.md 2->2, DECISIONS 12->12 (base vs HEAD); SCOPE/README/CHANGELOG mialy je wczesniej (styl pliku, ruling zad. 22) |
| (f) zakres zadan | OK (ledger) | jedyne rozszerzenie zakresu (zad. 25, ADR-023 pkt 5) ma ruling |
| (g) testy offline | OK | pelna suita z wlasnym pluginem blokujacym `socket.getaddrinfo` (scratchpad, nie w repo) -> **0 prob DNS**, `pyproj.network.is_network_enabled() == False`; `-m "not live"`: 1700 passed, 8 deselected. UWAGA: bez `-m "not live"` 8 testow `live` (`test_pl2000_verification.py::TestPL2000LiveWMS`) faktycznie odpytuje GUGiK (przeszly w przebiegu 1 — sa wylaczone z blokady) |
| (h) wersja / authors | OK | `__version__ == "0.7.0-dev"`; diff `pyproject.toml`: `authors`/`license` nietkniete |
| (i) komendy | OK | jak w (c); pytest: przebieg 1 (pelny) `1708 passed in 24.13s`; przebieg 2 (swiezy `__pycache__`, `-m "not live"`) `1700 passed, 8 deselected in 23.90s`; przebieg 3 (plugin DNS) `1700 passed`; testy wspolbiezne (`test_metadata_cache`, `test_auth_client`, `test_parallel_download`) 5x pod rzad `140 passed` — suita deterministyczna |
| (j) commity | OK | 66 commitow, wszystkie Conventional Commits bez diakrytykow (`git log --oneline ff145a9..7e6036b`) |
| (k)/(l) baseline / dowody | OK (ledger) | kanoniczny przebieg po zad. 21 zgodny z moim: 1708 collected / 93% / mypy 32 |

### Findings

**Critical: brak.**

**Important:**

**I-1 [CROSS-TASK 10 x 9 x 4(A4-1)] `kartograf/auth/client.py:60-64` — `__new__` singletonu poza lockiem + `_proxy_process` per instancja => dwa podprocesy proxy.**
Dlaczego: `_get_auth_proxy()` (`corine.py:55-62`) tez nie ma locka, wiec rownolegly
`download_batch(max_workers=4)` (domyslne!) z CORINE woła `AuthProxyClient()` z 4 watkow
naraz przy pierwszym uzyciu. Dwie instancje => `_ensure_proxy` drugiej widzi klasowy
`_proxy_port`, ale instancyjny `_proxy_process is None` i startuje DRUGI podproces
(udowodnione snippetem offline: `popen calls: 2`, `AuthProxyClient._proxy_process: None`,
oba instancyjne `True`). Fix N4-1 (lock w `_ensure_proxy`) jest wiec niedomkniety dla
scenariusza, ktory go motywowal. Ruling odlozyl to do A4-10 (reszta) — skutek
nieprzewidziany: fala 0.7.0 deklaruje "start proxy pod lockiem" (CHANGELOG Fixed), a
wyscig zostal o jeden krok wczesniej. Naprawa: `__new__` pod `cls._lock` (double-checked)
+ `AuthProxyClient._proxy_process = proc` (stan klasowy, jak `_proxy_port`); przy okazji
`proc.wait()` po `proc.kill()` w `_fail_proxy`/`_cleanup` (zombie) i `resp.close()` w
`download_file` (stream=True). Rozmiar S. -> F-1.

**I-2 [CROSS-TASK 9 x 4(A4-1)] `kartograf/auth/proxy.py:356-361` — allowlista moze zablokowac ostatni krok toru CLMS GeoTIFF, ktory dzieki A4-1 po raz pierwszy jest osiagalny poza macOS.**
Dlaczego: `_poll_clms_task_proxy` oddaje `DownloadURL` z CLMS; jesli to link presigned
na hoscie spoza `copernicus.eu`/`eea.europa.eu` (S3/CDN — nie do ustalenia offline;
raport zad. 9 "Watpliwosci 1" to odnotowal), `/download` odpowie 403 PO udanym,
dlugim pollingu i `_download_via_clms_proxy` rzuci `DownloadError` bez fallbacku na
WMS. Ruling (Decyzja planu 13) swiadomie przyjal "glosne 403", ale nie zaadresowal, ze
wtedy CORINE GeoTIFF nie dziala NIGDZIE. Propozycja (S, do decyzji kontrolera, bo
zmienia Decyzje 13): w `/download` dla hosta spoza allowlisty NIE odrzucac, tylko
forwardowac BEZ naglowka `Authorization` (token nigdy nie opuszcza allowlisty; link
presigned niesie wlasna autoryzacje); `/proxy` bez zmian (API wymaga tokena). Test:
`test_download_foreign_https_host_forwarded_without_token` (+ przepiecie
`test_download_rejects_foreign_host` na `http://` albo na `/proxy`). Alternatywa:
wylacznie zywa weryfikacja przed tagiem (Checklista, pkt nowy) i naprawa dopiero gdy
403 sie pojawi. -> F-2 (warunkowe) + Checklista.

**I-3 Docs niespojne z kanoniczna tabela timeoutow (DEVELOPMENT_STANDARDS 13.4 jest poprawna, zweryfikowana z kodem):**
- `CLAUDE.md:223-224`: "60 s dla Ortofoto, LAZ, BDOT10k, Land Cover i CUZK, 120 s dla SoilGrids" — kod: BDOT10k 120 s (wszystkie `download_by_*`, bdot10k.py:154/245/399), LAZ 30 s discovery WFS (`WFS_TIMEOUT`) / 60 s kafle, SoilGrids 120 s bbox / 60 s godlo (base.py:309), CORINE TERYT 120 s (corine.py:734). To jedyna pozostala niezgodnosc w CLAUDE.md — potwierdzone.
- `docs/SCOPE.md:296-298`: "60 s ... selekcji przez godlo w Land Cover" (BDOT10k godlo = 120 s), brak CORINE TERYT 120 s.
- `docs/IMPLEMENTATION_PROMPT.md:118`: "120s / 30s (WMS TERYT)" — `_get_teryt_for_point` ma domyslne 30, ale oba wywolania (bdot10k.py:284/449) przekazuja `timeout` wywolujacego (120) — 30 s nieosiagalne.
-> F-3.

**I-4 `README.md:134-145` tabela sidecara (kontrakt dla Hydrografa) — dwie nieprawdy:**
`horizontal_crs` "CZ `EPSG:5514`" — kafel TM33 pobrany godlem ma `EPSG:3045`, a
`--target-crs` daje uklad docelowy (ADR-024); `transform` opisany jako string
"np. `pinned: ...`" — to slownik `{"horizontal": ..., "vertical": ...}`
(`ResultMetadata.transform: dict | None`). Dodatkowo `README.md:51-52` "flagi ...
same przelaczaja auto na pl" bez kwalifikatora z rulingu zad. 17 (tylko obszar w
obwiedniach OBU krajow; obszar w calosci CZ + flaga PL = nadal blad etapu 2).
-> F-4.

**I-5 Falszywe liczby / zdania w docs (XS kazde):**
- `docs/DEVELOPMENT_STANDARDS.md:323` "(1402 testy)" — stan 1708 (reszta pliku juz ma 1708).
- `docs/DECISIONS.md:919-920` (ADR-025, przypis) "`clay = 27%` ... `loam` (21 punktow)" — poprawnie **22**: dla clay=27 i 20<sand<=45 jest 25 punktow symplexu, z czego sand 24..45 (22) idzie do `loam`, a sand 21..23 (3) do `clay_loam`; 28 + 22 = 50 = 226 - 176 (rachunek przypisu sie wtedy domyka; z 21 sie nie domyka).
- `docs/CHANGELOG.md:104-107` (Breaking, A4-10): "Dodatkowo `/download` przyjmuje wylacznie hosty ..." — allowlista obejmuje `/proxy` I `/download` (proxy.py:273 i :336).
- `tests/test_sheet_parser.py:410/428/437` docstringi "sekcja A (1-36)", "C (73-108)", "D (109-144)" koduja STARA (bledna) semantyke naprawiona w zad. 2.
-> F-5.

**Minor (nieblokujace, do fali tylko jesli "przy okazji" w tym samym pliku):**
- `download_cmd.py:514-520` tresc `Warning: brak danych w PL` orzeka brak pokrycia takze wtedy, gdy PL padl przez A2-9 "WMS skorowidz unavailable" (awaria uslugi) — po rulingu A3-2 kod 0 zostaje, ale sformulowanie neutralne ("nie pobrano z PL") byloby prawdziwe; 2 asercje w `tests/test_cli.py:3974/3992` do przepiecia.
- `_resolve_pl_sentinels`: `--product orto --resolution 5m` przechodzi cicho, a CLI wypisuje "(resolution: 5m)" — ta sama klasa co V2-N1; backlog.
- `proxy.py:_host_allowed(url)` dla `url` niebedacego str (np. liczba w JSON) -> `AttributeError` w handlerze (traceback socketservera, klient dostaje reset) — tylko z localhost; backlog/DROP.

### Triage odlozonych minorow (FINAL_REVIEW_DEFERRED.md)

| Pozycja (skrot) | Werdykt | Uzasadnienie |
|---|---|---|
| T1: test uszkodzonego kafla nie cwiczy galezi `unlink` | DROP | sciezka produkcyjna poprawna (unlink `missing_ok`), test pinuje kontrakt widoczny dla uzytkownika |
| T1: `mosaic_and_crop` moze zostawic obciety plik przy bledzie `merge` | BACKLOG (nie ma w PROGRESS — dopisac) | jedyne wywolanie produkcyjne (`export_image`) sprzata samo; dotyczy tylko bezposrednich konsumentow biblioteki |
| T1: noqa BLE001 dekoracyjne; `dst_kwds` redundantne | DROP | kosmetyka, nieszkodliwe |
| T1: Checklista — E2E kafelkowania > 16 Mpx (sciezka chunkowana `merge(dst_path)`) | CHECKLISTA | dopisac do pkt 2 |
| T2: docstringi 3 testow ze stara numeracja | MUST-FIX (XS, F-5) | falszywa dokumentacja semantyki naprawionej w tym wydaniu |
| T2: mieszane diakrytyki w docstringach `sheet_parser.py` | DROP | styl pliku (plik ma diakrytyki) |
| T3: test probe CZ "tautologiczny" | DROP | zweryfikowalem: (-670165, -1084718) -> 15.5000E / 49.8000N; pin stalej jest wlasciwym testem |
| T3: probe dla pary raster->4326 tylko `is not None`; `not is_rectilinear` bez testu; probe ignorowany dla zbuforowanej pary | DROP | probe tylko odrzuca kandydatow, klucz cache (src,dst) poprawny; galezie defensywne |
| T4: rename `_write_lock`, docstringi | DROP | komentarz w kodzie wyjasnia, ze lock chroni odczyty |
| T5: Notes o trybie sekwencyjnym (A2-4) | BACKLOG (jest: A2-4) | sekwencyjny TEZ lapie `DownloadError` do `failed`; roznica dotyczy tylko wyjatkow spoza `DownloadError` |
| T5: completed/skipped z `path None` nie trafia do licznika; duplikacja zliczania w 2 petlach | BACKLOG (dopisac do A2-4) | nieosiagalne dzis (`_download_single` zawsze oddaje path przy completed/skipped) |
| T5: `download_bbox` nie dotyka `last_result` | DROP | docstring atrybutu mowi to wprost |
| T6: ADR-025 przypis "21 punktow" -> 22 | MUST-FIX (XS, F-5) | zweryfikowany rachunek (28+22=50=226-176); ADR ma byc arytmetycznie spojny |
| T6: 2 punkty kontrolne domkniec; anotacje `_normalize_pct`; 5151 wywolan skalara | DROP | test symplexu juz pinuje oba domkniecia; +0,5 s OK |
| T7: `rel=0.02` luzne; percent z pikseli vs area geodezyjne; linia 517 redundantna; anotacja `src` | DROP / BACKLOG(percent) | roznica procent-piksele vs procent-pole dla rastra 20 km jest < 0,5 %; percent z `area_m2` = zmiana kontraktu, nie w 0.7.0 |
| T8: `width_px` z bboxa zrodlowego (106 m/px) | BACKLOG (dopisac do pozycji "Minor CLI ... A4-20") | plan-mandated; docelowo oba wymiary z obwiedni 3857 |
| T8: `year in EEA_YEARS` w 2 miejscach | DROP | ten sam warunek, oba miejsca odsylaja do siebie komentarzem |
| T9: zywa weryfikacja CORINE GeoTIFF vs allowlista | CHECKLISTA (MUST) + F-2 warunkowe | patrz I-2 |
| T9: `resp.close()`/finally w proxy | DROP | juz zrobione (`finally: resp.close()`, proxy.py:407) |
| T9: docstring `Path` bez importu; chunked bez `request_version`; `BrokenPipeError`; testy podmieniaja `ProxyHandler.credentials` | DROP | kosmetyka / nieosiagalne / pre-existing |
| T10 [KANDYDAT]: `__new__` poza lockiem + `_proxy_process` per instancja | MUST-FIX (S, F-1) | patrz I-1 — udowodnione dwa podprocesy; jest w PROGRESS (A4-10 reszta), ale to domkniecie N4-1 z tej fali, nie nowy protokol |
| T10: `kill()` bez `wait()`; `resp` stream niezamykany | MUST-FIX (XS, w F-1) | ten sam plik, 3 linie |
| T10: `_fail_proxy` nie zeruje `_stderr_thread`; literowka commitu; test-straznik | DROP | — |
| T11: test rozjazdu endiannosci; walidacja bajtu kolejnosci WKB; fixtura 4326 | BACKLOG (dopisac 1 linie do Minor) | wariant patologiczny (bajt kolejnosci spoza {0,1}) daje smieci zamiast `None` |
| T12: duplikat `_expand_degenerate`; `<= _EDGE_TOL` celowe; CHANGELOG 2e-9 | DROP | duplikat juz usuniety (import z `sheet_parser`), reszta zrobiona |
| T13: `gugik_orto.py` brak strazy na pusta liste warstw | DROP | nieosiagalne: `_fetch_wms_layers` rzuca `ValueError` na pusta liste (gugik_orto.py:183, gugik.py:299) -> fallback na hardcoded |
| T13: czesciowa awaria bez k/n; 4xx jako transport; tresc ValidationError hardcoded | DROP / BACKLOG | plan-mandated; kosmetyka |
| T13: `DownloadManager.download_bbox` docstring `Raises` bez `ValidationError` | MUST-FIX (XS, F-5) | docstring publicznej metody klamie o wyjatkach od tej fali |
| T15: `_generate_output_path` nie roznicuje year/property/depth | BACKLOG (jest w PROGRESS) | — |
| T15: asymetria patcha `_write_sidecar` w tescie | DROP | — |
| T16: `getattr(args,"product","nmt")` martwy fallback; `ValidationError` poza `try` | DROP | barier `main()` (zad. 18) i tak lapie `KartografError` — interakcja zadan 16 x 18 zamyka te uwage |
| T16: `--product orto --resolution 5m` cicho przechodzi | BACKLOG (dopisac do Minor CLI) | ta sama klasa co V2-N1, ale bez skutku dla danych (sidecar bierze rozdzielczosc z deskryptora) |
| T16: docstring `_download_godlo_list`; kolejnosc Error/Downloaded; test rownoleglosci; no-op except-raise | DROP | — |
| T17: tresc `Warning` orzeka "brak danych" | BACKLOG-kosmetyka (opcjonalnie w fali, XS) | po A2-9 awaria GUGiK ma wlasny komunikat wyzej na stderr |
| T17: `TransformError` w petli krajow -> 1 mimo czesciowego sukcesu | BACKLOG (dopisac do Minor CLI) | pre-existing, etap 2 |
| T17: em-dash; brak testu geometry+flaga PL; sekwencja Info->Error | DROP | — |
| T18: noqa BLE001; `--teryt` help | DROP | — |
| T19 [KANDYDAT]: blokada bez `getaddrinfo` i sieci PROJ | BACKLOG (dopisac do A8-7/CI) | zmierzone: 0 prob DNS w calej suicie, PROJ network domyslnie wylaczony — dzis brak ekspozycji; utwardzenie warte 10 linii w conftest razem z CI |
| T19: `connect_ex`; snapshot `WMS_LAYERS`; A8-5 pinuja wynik; commit "21" | DROP | — |
| T22: format ID bez prefiksu; meta-uzasadnienie A6-16; etykieta A2-3 x2 | DROP | — |
| T23 [KANDYDAT]: README tabela sidecara; auto->pl bez kwalifikatora; NMT bez "(WCS: tylko KRON86)" | MUST-FIX (XS, F-4) | patrz I-4 — README jest dokumentacja kontraktu dla Hydrografa |
| T24 [KANDYDAT]: SCOPE.md:296-298; IMPLEMENTATION_PROMPT.md:118; CLAUDE.md:223-224 | MUST-FIX (XS, F-3) | patrz I-3 |
| T24: PRD §5 eksporty CZ bez sekcji 3.x; alias `download_by_teryt` w managerze | BACKLOG (alias jest w PROGRESS; PRD -> decyzja PO, Checklista pkt 7) | — |
| Rulingi (linie 3-47) | bez zastrzezen | jedyny nieprzewidziany skutek rulingu: Decyzja 13 (allowlista) x A4-1 — patrz I-2; ruling "odlozone A4-10" x N4-1 — patrz I-1 |

### Lista do JEDNEJ fali naprawczej

**F-1 `kartograf/auth/client.py` (S, ~15 linii + 1 test)**
- `__new__`: `with cls._lock: if cls._instance is None: cls._instance = super().__new__(cls)` (lock klasowy juz istnieje, `__new__` nigdy nie biegnie pod `_ensure_proxy`).
- `_start_proxy`: `AuthProxyClient._proxy_process = proc` (stan klasowy, spojnie z `_proxy_port`); `_fail_proxy`/`_cleanup`: zerowac przez klase; po `proc.kill()` dodac `proc.wait(timeout=5)`.
- `download_file`: `resp` w `try/finally` z `resp.close()` (albo `with self._session.post(..., stream=True) as resp:`).
- Test `tests/test_auth_client.py::test_concurrent_first_instantiation_yields_one_instance`: `_instance=None`, `threading.Barrier(4)` + 4 watki `AuthProxyClient()`; asercja `len({id(x) for x in results}) == 1`. Drugi test: dwa obiekty utworzone przez `object.__new__` (symulacja) -> po `_ensure_proxy` obu `Popen.call_count == 1` (pinuje stan klasowy). Mutacja kontrolna: usuniecie locka z `__new__` nie musi wywalic testu barierowego (wyscig), dlatego drugi test jest obowiazkowy.
- CHANGELOG Fixed (A4-10/N4-1): "singleton tworzony pod lockiem; stan podprocesu klasowy".

**F-2 `kartograf/auth/proxy.py` (S, WARUNKOWE — decyzja kontrolera wzgledem Decyzji planu 13)**
- `/download`: `host_ok = _host_allowed(url)`; gdy `urlparse(url).scheme != "https"` -> 403 jak dotad; gdy https i `not host_ok` -> forward BEZ `Authorization` (token tylko dla allowlisty). `/proxy` bez zmian.
- Testy `tests/test_auth_proxy.py`: `test_download_foreign_https_host_forwarded_without_token` (`requests.get` wolany bez naglowka Authorization, `creds.get_access_token` NIE wolany), `test_download_rejects_http_scheme_foreign_host`; przepiac `test_download_rejects_foreign_host` na `/proxy` lub `http://`.
- CHANGELOG Breaking (A4-10): doprecyzowac ("token wylacznie do `*.copernicus.eu`/`*.eea.europa.eu`; `/download` na inny host https idzie bez tokena").
- Jesli kontroler NIE przyjmuje F-2: pkt Checklisty "zywy CORINE GeoTIFF z `CLMS_CREDENTIALS` na Linux" staje sie BLOKUJACY przed tagiem.

**F-3 timeouty — `CLAUDE.md:223-224`, `docs/SCOPE.md:296-298`, `docs/IMPLEMENTATION_PROMPT.md:118` (XS, tekst)**
- Kanoniczne zdanie (z DEVELOPMENT_STANDARDS 13.4): "Timeouty domyslne: 30 s NMT/NMPT (GUGiK) i discovery WFS w LAZ; 60 s Ortofoto, kafle LAZ, CORINE (bbox/godlo), CUZK, SoilGrids przez godlo; 120 s BDOT10k (wszystkie tryby), CORINE przez TERYT, SoilGrids przez bbox i HSG".
- IMPLEMENTATION_PROMPT.md:118: `120s` (usunac "/ 30s (WMS TERYT)").
- Bez testu (docs); kontrola: `grep -n "Timeout" CLAUDE.md docs/SCOPE.md docs/IMPLEMENTATION_PROMPT.md` spojny z tabela 13.4.

**F-4 `README.md` (XS, tekst)**
- l. 137: `horizontal_crs` -> "uklad poziomy pliku: PL `EPSG:2180`; CZ natywnie `EPSG:5514`, kafel TM33 pobrany godlem `EPSG:3045`, po `--target-crs` uklad docelowy".
- l. 144: `transform` -> "slownik `{horizontal, vertical}`; kazda os to `pinned: <opis> (<dokladnosc> m)` albo `null` (rastry CZ)".
- l. 51-52: dopisac "na obszarze spornym (obwiednie obu krajow)"; obszar w calosci CZ + flaga PL = blad etapu 2.
- l. 158-162 (Funkcjonalnosci / NMT PL): dopisac punkt "Pobieranie przez bbox -> GeoTIFF (WCS): tylko 1m, tylko KRON86 (EVRF2007: 404 od 2026-08)".

**F-5 liczby i docstringi (XS, 5 plikow, po 1-3 linie)**
- `docs/DEVELOPMENT_STANDARDS.md:323`: "(1402 testy)" -> "(1708 testow)".
- `docs/DECISIONS.md:920`: "(21 punktow)" -> "(22 punkty)".
- `docs/CHANGELOG.md:104-107`: "Dodatkowo `/download` przyjmuje" -> "Dodatkowo `/proxy` i `/download` przyjmuja" (jesli F-2 przyjete — inna tresc, patrz F-2).
- `tests/test_sheet_parser.py:410/428/437`: docstringi -> "sekcja A (wiersze 0-5, kolumny 0-5)", "C (wiersze 6-11, kolumny 0-5)", "D (wiersze 6-11, kolumny 6-11)".
- `kartograf/download/manager.py` `download_bbox` docstring `Raises`: dopisac `ValidationError` (WCS EVRF2007 wycofany — patrz `GugikProvider.download_bbox`).

**F-6 (opcjonalne, XS) `kartograf/cli/download_cmd.py:514-520`** — `Warning: nie pobrano z {failed} dla tego obszaru (brak danych albo awaria zrodla — patrz komunikaty wyzej) - pobrano {ok}`; przepiac `tests/test_cli.py:3974/3992`.

**F-7 `docs/PROGRESS.md` (XS, obowiazkowe po fali)** — "Backlog po audycie 0.7.0": dopisac pozycje z triage oznaczone "dopisac" (mosaic_and_crop unlink; A2-4 rozszerzenie; T8 width_px; T11 bajt kolejnosci WKB; T16 orto+5m; T17 TransformError w petli; T19 getaddrinfo/PROJ do A8-7/CI); zaktualizowac liczbe commitow ("64" -> stan po fali) i rozklad typow; sekcja "Ostatnia sesja": adnotacja o finalnym review (ten plik, git-ignored) i fali F-1..F-7.

Oszacowanie calej fali: kod S (F-1) + S warunkowe (F-2) + docs XS x5 — 1 implementer, 2-3 commity
(`fix(auth): ...`, `docs: ...`, ewentualnie `fix(auth): /download bez tokena poza allowlista`),
~1-2 h z testami; pelna suita + ruff + mypy (<= 32) po fali.

### Checklista release — uzupelnienia wzgledem planu

1. (do pkt 1) Przebieg `pytest tests/` BEZ `-m "not live"` wykonuje 8 realnych zapytan WMS do GUGiK (`TestPL2000LiveWMS`) — to zamierzone, ale w srodowisku bez sieci te testy sie SKIPuja (lapiac `RequestException`), wiec "1708 passed" wymaga sieci; w CI uzywac `-m "not live"` (1700).
2. (do pkt 2) Po E2E kafelkowania sprawdzic dodatkowo wariant > 16 Mpx (np. bbox 8,5 x 8,5 km przy 2 m) — tylko wtedy `merge(dst_path=)` wchodzi w sciezke chunkowana (`mem_limit`); asercje jak w planie + brak pliku `*.native.tif` po `--target-crs`.
3. (NOWY, po pkt 3) **Zywy tor CORINE GeoTIFF z `CLMS_CREDENTIALS` na Linux** (pierwszy raz osiagalny dzieki A4-1): `kartograf landcover download --source corine --year 2018 --godlo N-34-130-D` z ustawiona zmienna; oczekiwany `.tif` (nie `.png`) i sidecar bez `extra.fallback`. Jesli wynik to `DownloadError: Failed to download file via proxy` i w logu proxy `Host not allowed: <host>` — to I-2: wdrozyc F-2 PRZED tagiem. Zanotowac host `DownloadURL` w `docs/research/` (jedna linia), bo to jedyne zrodlo prawdy dla allowlisty.
4. (do pkt 4) `python -m build` w srodowisku z `setuptools>=61`: oprocz `unzip -l dist/*.whl | grep -c tests/ == 0` sprawdzic `grep Version dist/*/METADATA` == `0.7.0` (normalizacja PEP 440 z literalu `__version__`) i ze `import kartograf` NIE byl potrzebny do zbudowania (setuptools czyta literal statycznie — build w izolowanym srodowisku bez rasterio musi przejsc).
5. (do pkt 7) `docs/PROGRESS.md` liczba commitow na galezi i "64 commity" -> stan po fali (tekst sam to zapowiada).
6. (do pkt 9) W pelnej weryfikacji koncowej dodac przebieg `HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 pytest -m "not live"` (P-13) — dzis zielony (sprawdzone rownowaznym pluginem DNS); ma zostac zielony po fali.
7. (do pkt 10) Przed merge do `develop`: `git diff develop...fix/release-0.7.0-audit --stat` musi pokazac `requirements*.txt` jako usuniete i `docs/superpowers/plans/2026-08-22-release-0.7.0-audit.md` jako dodany (plan jest sladem w repo); `.superpowers/` pozostaje git-ignored.

### Strengths

- Interakcje miedzy zadaniami w `download_cmd.py` (5 x 16 x 17 x 18) sa spojne: `last_result` czytany tylko tam, gdzie jest ustawiany (hierarchia), listy z rozwinieciem ida sekwencyjnie (koniec `workers^2`), `auto -> pl` dzieje sie PRZED `_validate_cross_country`, a bariera `main()` domyka nieosiagalne `ValidationError` z `_create_provider_and_storage`.
- Zadanie 2 x 12: `get_children()` (blok 6x6) i `find_sheets_for_bbox(..., "1:200000")` daja identyczne 36 arkuszy dla A/B/D (sprawdzone snippetem) — dwie niezalezne sciezki zgadzaja sie po obu naprawach.
- Zadanie 6 x 7: maska nodata liczona ze zrodla, a nie z wyniku — poprawnie omija `default=loam` klasyfikatora; reguly USDA partycjonuja symplex (test na 5151 punktach).
- Zadanie 9: ramkowanie chunked po stronie proxy + surowe bajty (`decode_content=False`) to jedyne rozwiazanie spojne z kontrola `Content-Length` klienta (zad. 10); test socket-level pinuje to naprawde.
- Zadanie 19: blokada sieci dziala — pomiar niezaleznym pluginem: 0 prob DNS w 1700 testach; suita deterministyczna w 3 pelnych przebiegach + 5 przebiegach testow wspolbieznych.
- Docs: CHANGELOG 0.7.0 ma dokladnie 6 naglowkow (Breaking/Added/Changed/Removed/Fixed/Tests), kazdy wpis z ID ustalenia; ADR-023 addendum, ADR-024 i ADR-025 zgodne z kodem; liczby 1708/93 %/mypy 32 spojne w README, SCOPE, PROGRESS, DEVELOPMENT_STANDARDS (poza jedna linia 323).
