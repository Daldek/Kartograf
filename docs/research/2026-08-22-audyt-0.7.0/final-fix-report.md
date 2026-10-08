# Raport fali naprawczej F-1..F-7 (po finalnym review galezi `fix/release-0.7.0-audit`)

Implementer: opus. Data: 2026-08-23. FIX_BASE: `7e6036b`. HEAD po fali: `99f2909`.
Commity fali (5): `d6ff941`, `297e3ec`, `d3c3b0a`, `3c6c5e5`, `99f2909`.
Stan galezi: **71 commitow** od `ff145a9` (`git log --oneline ff145a9..HEAD | wc -l`).

---

## F-1 — `AuthProxyClient`: singleton pod lockiem, klasowy stan podprocesu (kod, S)

**Co:** `kartograf/auth/client.py`
- `__new__` z double-checked lockiem na `cls._lock` (+ docstring: dlaczego lock jest
  bezpieczny — `__new__` nigdy nie biegnie pod `_ensure_proxy`).
- `_proxy_process` i `_stderr_thread` zapisywane i czytane jako stan KLASOWY
  (`AuthProxyClient._...`), spojnie z `_proxy_port`; dotyczy `_start_proxy`,
  `_fail_proxy`, `_cleanup`, `_ensure_proxy`.
- `proc.wait(timeout=5)` po `proc.kill()` w `_fail_proxy` i `_cleanup`
  (`contextlib.suppress(TimeoutExpired)` — drugi timeout nie moze wysadzic sprzatania).
- `download_file`: `resp` (stream=True) zamykane w `finally` (`resp.close()`).
  Wybrano `try/finally` zamiast `with ... as resp`, bo istniejace testy podstawiaja
  `Mock()` (bez `__enter__`) — efekt identyczny, zero churnu w 6 testach.

**Pliki:** `kartograf/auth/client.py`, `tests/test_auth_client.py`, `docs/CHANGELOG.md`.

**TDD Evidence**
- RED: `pytest tests/test_auth_client.py -k "concurrent_first_instantiation or second_instance_reuses or fail_proxy_reaps or cleanup_waits_after_kill or closes_streamed"`
  -> `4 failed, 1 passed`:
  - `test_second_instance_reuses_running_proxy`: `AssertionError: Expected 'Popen' to have been called once. Called 2 times.` (dowod dwoch podprocesow)
  - `test_fail_proxy_reaps_killed_child`: `assert 1 == 2` (`wait` tylko raz)
  - `test_cleanup_waits_after_kill`: `assert 1 == 2`
  - `test_download_file_closes_streamed_response`: `Expected 'close' to have been called once. Called 0 times.`
  - test barierowy (`test_concurrent_first_instantiation_yields_one_instance`) przeszedl
    juz na RED — wyscig jest niedeterministyczny; dlatego obowiazkowy jest drugi test
    (stan klasowy), zgodnie z uwaga recenzenta o mutacji kontrolnej.
- GREEN: `pytest tests/test_auth_client.py -q` -> `40 passed`.

**Uwaga (znalezione przy okazji, w zakresie F-1):** 5 testow ustawialo `client._proxy_process`
jako atrybut INSTANCJI. Po przejsciu na stan klasowy `_start_proxy`/`_ensure_proxy` przestaly
je widziec i **uruchamialy prawdziwy podproces `python -m kartograf.auth.proxy`** (zaobserwowane:
2 osierocone procesy po przebiegu). Testy przepiete na `AuthProxyClient._proxy_process`;
po naprawie `pgrep kartograf.auth.proxy` po przebiegu jest pusty.

**Commit:** `d6ff941 fix(auth): singleton proxy pod lockiem i klasowy stan podprocesu`

---

## F-2 — `/download` bez tokena dla hosta https spoza allowlisty (kod, S; ruling kontrolera)

**Co:** `kartograf/auth/proxy.py`
- `/download` rozdziela kontrole schematu od kontroli hosta: `scheme != "https"` -> 403;
  host z allowlisty -> `Authorization: Bearer <token>`; kazdy inny host https ->
  forward BEZ naglowka (log INFO z hostem). `/proxy` bez zmian (nadal 403 poza allowlista).
- Docstring `do_POST` opisuje obie sciezki i polityke tokena; komentarz przy
  `ALLOWED_HOST_SUFFIXES` zaktualizowany.

**Pliki:** `kartograf/auth/proxy.py`, `tests/test_auth_proxy.py`, `docs/CHANGELOG.md`, `README.md`.

**TDD Evidence**
- RED: `pytest tests/test_auth_proxy.py -k "download_foreign_https or download_allowed_host_gets_token or download_rejects_http_scheme"`
  -> `1 failed, 3 passed`:
  `test_download_foreign_https_host_forwarded_without_token`:
  `assert [{'data': {'error': 'Host not allowed: cdn.example.org'}, 'status': 403}] == []`.
  (Pozostale 3 przechodza od razu — pinuja zachowanie, ktore ma zostac.)
- GREEN: `pytest tests/test_auth_proxy.py -q` -> `37 passed`.

**Testy:** `test_download_rejects_foreign_host` zastapiony czterema:
`test_download_foreign_https_host_forwarded_without_token` (200, brak `Authorization`,
`creds.get_access_token.assert_not_called()`, cialo w `wfile`),
`test_download_allowed_host_gets_token` (`Authorization == "Bearer tok123"`),
`test_download_rejects_http_scheme_foreign_host` i `..._allowed_host` (403, `requests.get`
niewolany, token niepobierany).

**Docs:** CHANGELOG — Breaking A4-10 przeformulowany ("token trafia wylacznie do hostow
`*.copernicus.eu`/`*.eea.europa.eu`: `/proxy` i `/download` przyjmuja tylko https, a
`/proxy` odrzuca kazdy host spoza listy") = realizacja rowniez punktu F-5; nowy wpis w
Fixed opisujacy forward bez tokena. README (sekcja Bezpieczenstwo) zdanie "proxy pobiera
dane samo, wylacznie z hostow ..." bylo po tej zmianie nieprawda — poprawione.

**Commit:** `297e3ec fix(auth): /download bez tokena dla hosta https spoza allowlisty`

---

## F-6 — neutralna tresc `Warning` auto-splitu (kod, XS)

**Co:** `kartograf/cli/download_cmd.py` (~l. 514) — nowa tresc:
`Warning: nie pobrano danych z {failed} dla tego obszaru (brak pokrycia albo awaria zrodla — patrz Error wyzej) — pobrano {ok} (prostokatne obwiednie krajow, ADR-023 pkt 4-5)`.

**Pliki:** `kartograf/cli/download_cmd.py`, `tests/test_cli.py` (2 asercje), `docs/CHANGELOG.md` (A3-2).

**TDD Evidence**
- RED (asercje przepiete pierwsze): `pytest tests/test_cli.py -k "cz_failure_does_not_skip_pl_and_warns or pl_failure_with_cz_success_warns"`
  -> `2 failed`, m.in. `assert 'nie pobrano danych z CZ' in 'Warning: brak danych w CZ dla tego obszaru - pobrano PL (...)'`.
- GREEN: te same 2 testy -> `2 passed`.

**Commit:** `d3c3b0a fix(cli): neutralna tresc ostrzezenia auto-splitu`

---

## F-3 / F-4 / F-5 — dokumenty (XS, bez zmian zachowania)

**F-3 timeouty** (zdanie zgodne z kanoniczna tabela / DEVELOPMENT_STANDARDS 13.4):
- `CLAUDE.md`: "Timeouty domyslne: 30 s dla NMT/NMPT (GUGiK) i discovery WFS w LAZ;
  60 s dla Ortofoto, kafli LAZ, CORINE (bbox/godlo), CUZK i SoilGrids przez godlo;
  120 s dla BDOT10k (wszystkie tryby), CORINE przez TERYT oraz SoilGrids przez bbox i HSG".
- `docs/SCOPE.md`: analogicznie (styl pliku: z diakrytykami).
- `docs/IMPLEMENTATION_PROMPT.md:118`: BDOT10k `120s` (usuniete nieosiagalne
  "/ 30s (WMS TERYT)"); wiersz CLMS: `60s (przez TERYT: 120s)` — bez tego tabela dalej
  rozjezdzalaby sie z 13.4.

**F-4 README** (plik z diakrytykami — zachowane):
- `horizontal_crs`: "PL `EPSG:2180`; CZ natywnie `EPSG:5514`, kafel TM33 pobrany godlem
  `EPSG:3045`, a po `--target-crs` uklad docelowy" (zweryfikowane w
  `cli/download_cmd.py:1297,1372` i `meta.horizontal_crs = horizontal_crs`).
- `transform`: slownik osi `horizontal`/`vertical`. **Odstepstwo od literalnego brzmienia
  briefu:** brief/review mowily "albo `null`" per os — kod (`download_cmd.py:1233-1243`)
  NIE wstawia `null`, tylko pomija klucz, a puste `transform` daje `null` na calym polu.
  Zapisane zgodnie z kodem.
- l. 51-52: kwalifikator "tylko na obszarze objetym obwiedniami OBU krajow; obszar w
  calosci po stronie czeskiej konczy sie bledem (etap 2)".
- Sekcja NMT PL: nowy punkt o WCS (tylko 1m, tylko KRON86; EVRF2007 404 od 2026-08;
  wysokosci EVRF2007 z obszaru przez rozwiniecie bboxa na arkusze OpenData).

**F-5 liczby i docstringi:**
- `docs/DEVELOPMENT_STANDARDS.md:323` "(1402 testy)" -> "(1716 testow)" (patrz nizej — nie 1708).
- `docs/DECISIONS.md:920` "(21 punktow)" -> "(22 punkty)"; plik ma CRLF — koncowki
  zachowane (sprawdzone `git diff | cat -A`: `^M$` po obu stronach).
- `docs/CHANGELOG.md` Breaking A4-10 — zrobione w commicie F-2 (ta sama fraza).
- `tests/test_sheet_parser.py` (3 docstringi) -> "sekcja A (wiersze 0-5, kolumny 0-5)",
  "C (wiersze 6-11, kolumny 0-5)", "D (wiersze 6-11, kolumny 6-11)"; skrocone o
  "dla skali ... w", bo pelne brzmienie z briefu lamalo limit 88 znakow (ruff E501).
- `kartograf/download/manager.py` `download_bbox` docstring `Raises` += `ValidationError`
  (odsylacz do `GugikProvider.download_bbox` / wycofany WCS EVRF2007).

**Commit:** `3c6c5e5 docs: timeouty, tabela sidecara w README i korekty liczb`

---

## F-7 — `docs/PROGRESS.md` + liczba testow (docs)

**Co:**
- Sekcja audytu: nowy akapit o finalnym review (fable, werdykt, 0 Critical) i wyliczenie
  F-1..F-7; liczba commitow **64 -> 71** (policzone: `git log --oneline ff145a9..HEAD | wc -l`
  = 71 z tym commitem), rozklad typow 40 `fix` / 21 `docs` / 3 `test` / 2 `refactor` /
  2 `feat` / 2 `chore` / 1 `perf`; kanoniczny przebieg zaktualizowany.
- Tabela statusu: "93%, 1716 testow (po fali naprawczej F-1..F-7)".
- Backlog po audycie 0.7.0 — dopisane pozycje z triage:
  `mosaic_and_crop` bez `unlink` przy bledzie `merge` (T1); rozszerzenie A2-4 o licznik
  `path is None` i duplikacje zliczania (T5); `width_px` z bboxa zrodlowego zamiast
  obwiedni 3857 (T8, dopisane do "Minor CLI ... A4-20"); walidacja bajtu kolejnosci WKB
  (T11); `--product orto --resolution 5m` cicho przechodzi (T16, do "Minor CLI");
  `TransformError` w petli krajow (T17) — **juz byl w backlogu**, zostawiony bez zmian;
  blokada sieci bez `getaddrinfo`/PROJ (T19) — **juz byla**, dopisane powiazanie z A8-7/CI
  i pomiar (0 prob DNS).
- Wpis A4-10 (reszta) przyciety o czesc naprawiona w F-1 (wyscig `__new__`,
  `_proxy_process` per instancja, `kill()` bez `wait()`), z adnotacja "naprawione w fali F-1".
- Pkt 11 "Nastepne kroki": "plus 62 z audytu" -> "plus 71".

**Commit:** `99f2909 docs(progress): backlog i podsumowanie po fali naprawczej F-1..F-7`

---

## Zmiana liczby testow 1708 -> 1716 (poza literalna lista F-n — zglaszam wprost)

Fala dolozyla 8 testow (5 w `test_auth_client.py`, netto 3 w `test_auth_proxy.py`), wiec
suite ma **1716 collected** (1708 passed + 8 deselected `live`). Literalne wykonanie F-5
("1402 -> 1708") zostawiloby w 8 miejscach liczbe, ktora po tej samej fali przestaje byc
prawdziwa. Zaktualizowalem wiec kazde miejsce, gdzie 1708 opisuje AKTUALNY rozmiar suity:
`README.md` (x2), `docs/PRD.md`, `docs/SCOPE.md` (x2, w tym wiersz rewizji 3.8 "liczby
1716/93%"), `docs/DEVELOPMENT_STANDARDS.md` (x2), `docs/CHANGELOG.md` (wpis Tests, z
rozbiciem "1708 po 26 zadaniach + 8 w fali"), `docs/PROGRESS.md` (x2). Liczba 1708
zostaje wylacznie tam, gdzie jest opisem stanu SPRZED fali. Jesli kontroler woli scisly
zakres — do cofniecia jest 8 linii w 6 plikach.

## Wyniki koncowe (przebieg po ostatnim commicie kodu, powtorzony po F-7)

- `pytest tests/ -q -p no:cacheprovider -m "not live"` -> **1708 passed, 8 deselected**
  (1716 collected).
- `pytest tests/ --cov=kartograf --cov-report=term -q -m "not live"` -> **93%**
  (5366 stmts / 395 miss, 92,64%).
- `ruff check kartograf/ tests/` -> `All checks passed!`; `ruff format --check` -> `83 files already formatted`.
- `mypy kartograf/` -> **32 bledy w 9 plikach** (baseline 32 — bez zmian, limit <= 32 spelniony).
- Kontrola offline (P-13): `HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9
  pytest tests/ -m "not live"` -> **1708 passed, 8 deselected** (nowe testy nie tykaja sieci).
- Stabilnosc: `test_auth_client.py + test_auth_proxy.py + test_parallel_download.py` 5x pod
  rzad -> `118 passed` za kazdym razem (test barierowy niedeterministyczny z natury,
  ale nie flakuje; kontrakt pinuje drugi test).
- Po przebiegach brak osieroconych procesow `kartograf.auth.proxy`.

## Self-review (`git diff 7e6036b..HEAD --stat`)

17 plikow, +384/-96. Kod: `auth/client.py`, `auth/proxy.py`, `cli/download_cmd.py`
(1 komunikat), `download/manager.py` (sam docstring). Testy: `test_auth_client.py`,
`test_auth_proxy.py`, `test_cli.py` (2 asercje), `test_sheet_parser.py` (3 docstringi).
Docs: CLAUDE, README, PRD, SCOPE, PROGRESS, CHANGELOG, DECISIONS, DEVELOPMENT_STANDARDS,
IMPLEMENTATION_PROMPT. Nic poza lista F-1..F-7 (wyjatki opisane wyzej: README
"Bezpieczenstwo" jako skutek F-2, przepiecie 5 testow na stan klasowy jako skutek F-1,
liczba 1716). Kontrakty ADR-022/023/024 nietkniete (sidecar, `exportImage`, lokalny warp
poza diffem). Wersja nadal `0.7.0-dev`, `pyproject.toml` niezmieniony, `.superpowers/`
niecommitowany. Konwencje znakow: CLAUDE 2->2 diakrytyki, DEVELOPMENT_STANDARDS/
IMPLEMENTATION_PROMPT 0->0, DECISIONS 23->23 + CRLF, SCOPE/README/PRD z diakrytykami.

## Watpliwosci / do decyzji kontrolera

1. **Liczba testow 1716** w 8 miejscach dokumentow (sekcja wyzej) — swiadome wyjscie poza
   litere F-5, latwe do cofniecia.
2. **`transform` w README** opisany zgodnie z KODEM (brak klucza dla osi bez przeliczenia),
   a nie zgodnie z brzmieniem review ("albo `null`").
3. **F-2 a checklista release** — punkt 3 checklisty ("zywy CORINE GeoTIFF z
   `CLMS_CREDENTIALS` na Linux") nadal wart wykonania: F-2 usuwa blokade 403, ale host
   `DownloadURL` warto zanotowac w `docs/research/` (jedyne zrodlo prawdy o allowliscie).
   Nie dopisywalem checklisty — nie ma jej w liscie F-n.
4. `test_concurrent_first_instantiation_yields_one_instance` z natury nie jest mutacyjnie
   silny (wyscig); kontrakt trzyma `test_second_instance_reuses_running_proxy`.
