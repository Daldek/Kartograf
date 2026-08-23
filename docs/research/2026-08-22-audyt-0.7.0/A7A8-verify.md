# V7 — weryfikacja ustalen A7 (dokumentacja historyczna) i A8 (jakosc testow)

Weryfikator: V7. Galaz: `fix/release-0.7.0-audit`. Data: 2026-08-22.
Repo NIE bylo modyfikowane (`git status --porcelain` przed i po: tylko istniejacy wczesniej
`?? docs/superpowers/plans/2026-08-22-release-0.7.0-audit.md`). Wszystkie mutacje i wtyczki
w scratchpadzie (`.../scratchpad/v7mut`, `v7_netblock.py`, `v7_netobs.py`).

Uwaga metodyczna: siec w tym srodowisku **jest dostepna** (GUGiK odpowiada HTTP 200 w 0,1 s),
wiec twierdzenia A8 o realnym ruchu HTTP dalo sie odtworzyc bezposrednio — obserwatorem
polaczen, a nie tylko blokada.

## Ustalenia A7

### A7-1 — Spec etapu 1 twierdzi, ze `parent_request` NIE powstaje przy jawnym `--country`
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ sed -n '495,498p' docs/superpowers/specs/2026-08-11-etap1-cz-fundament-dmr-design.md
    "Przy jawnym `--country pl|cz` i w trybie godlowym pola nie ma"
  $ sed -n '486,488p' docs/DECISIONS.md   # ADR-023 (f)1
    "`extra.parent_request` jest zapisywany **zawsze** w trybie `--bbox`/`--geometry`
     (auto I jawny `--country`), **nigdy** w trybie godlowym."
  $ grep -n "_build_parent_request" kartograf/cli/download_cmd.py
    1332:  args, bbox=bbox, parent_request=_build_parent_request(bbox, ("CZ",))
  $ .venv/bin/python -m pytest tests/test_cli.py -k "explicit_cz_bbox_gets_parent_request or geometry_explicit_cz_gets_parent_request" -q
    2 passed
  ```
- Uzasadnienie: obie strony zacytowane, kod i dwa testy potwierdzaja zachowanie zgodne
  z ADR-023, nie ze specem. Naglowkowa errata specu (l. 14-28) ma dokladnie 3 punkty
  (imageSR/sidecar `server:`, nodata 48,3%, `test_cache.py`) — zaden nie dotyczy
  `parent_request`. Plan etapu 1 (l. 32, "Rozstrzygniecia z konsultacji", pkt 1) nazywa to
  wprost "Korekta gwarancji ... z sekcji 9 specu", czyli rozjazd byl znany i nieodnotowany
  po stronie specu.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/superpowers/specs/2026-08-11-etap1-cz-fundament-dmr-design.md` —
  4. punkt naglowkowej erraty w brzmieniu zaproponowanym przez A7. Przypiete juz istniejacymi
  testami `tests/test_cli.py::TestAutoSplitBBox::test_explicit_cz_bbox_gets_parent_request`
  i `TestAutoSplitGeometry::test_geometry_explicit_cz_gets_parent_request`. Rozmiar: S;
  ryzyko regresji: niskie (sam tekst).

### A7-2 — Errata researchu CZ nie obejmuje sekcji ZABAGED (`outSR=2180`) i tabeli ograniczen
- Werdykt: CONFIRMED (z zawezeniem sily dowodu dla sekcji 5.2 B)
- Reprodukcja:
  ```
  $ grep -n "outSR=2180\|lub reprojekcja" docs/research/2026-08-10-czechy-dmr-zabaged.md
    216: - **`outSR=2180` — reprojekcja po stronie serwera dziala**
    306: Zarowno ImageServer (`imageSR=2180`) jak i MapServer (`outSR=2180`) reprojektuja same,
    365: | Transformacja pozioma | ... najlepiej 0,5 m (Helmert) lub reprojekcja serwerowa |
  $ sed -n '7,16p' docs/research/2026-08-10-czechy-dmr-zabaged.md   # errata
    "(sekcja 4.2 ..., sekcja 9 ... i wniosek 3) zostala OBALONA pomiarem tresci"
    "Wniosek metodyczny: kontrola poprawnosci reprojekcji musi mierzyc TRESC RASTRA"
  $ sed -n '731,733p' docs/DECISIONS.md   # ADR-024, Konsekwencje
    "Regula 'nie ufaj reprojekcji serwerowej' jest wiazaca takze dla przyszlych zrodel
     DE/SK sterowanych serwerowym parametrem ukladu."
  ```
- Uzasadnienie: errata enumeruje trzy konkretne miejsca i nie obejmuje l. 216/231/306/365.
  Wiersz tabeli w sekcji 8 (l. 365) mowi wprost o transformacji **poziomej** przez
  reprojekcje serwerowa — jest bezposrednio uniewazniony przez ADR-024. Sekcja 5.2 B
  (l. 216/231) dotyczy `outSR` dla **wektora** (MapServer/query), czyli innego mechanizmu niz
  zmierzony `exportImage`; jej nie obalono pomiarem, a "wniosek metodyczny" erraty mowi
  o **rastrze**, wiec jej nie pokrywa. Znalezisko dotyczy kompletnosci erraty — i to jest
  prawda. Dodatkowo A7 przeoczyl l. 306, ktore laczy oba mechanizmy w jednym zdaniu i tez
  nie jest oznaczone.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/research/2026-08-10-czechy-dmr-zabaged.md` — rozszerzyc punkt 1
  erraty o "sekcja 5.2 B (`outSR` dla ZABAGED), zdanie w sekcji 7 (l. 306) i tabela w
  sekcji 8" + zdanie, ze dla wektora ZABAGED efekt NIE byl mierzony i przed etapem 3 trzeba
  go zweryfikowac wobec referencji natywnej 5514. Testem sie tego nie przypina (dokument
  badawczy). Rozmiar: S; ryzyko regresji: niskie.

### A7-3 — `2026-08-11-adr024-seam-report.md` bez zadnej adnotacji o naprawie
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ grep -cniE "errat|nieaktual|uniewazn|ADR-024|Adnotacja|naprawion" \
      docs/research/2026-08-11-adr024-seam-report.md
    0
  $ sed -n '12,17p' docs/research/2026-08-11-adr024-seam-report.md
    "**`--target-crs EPSG:2180` dla zrodel CZ zwraca raster przesuniety poziomo o ~135 m.**
     ... opisuje w sidecarze jako `transform.horizontal="server:EPSG:2180"`, bez pola dokladnosci."
  $ sed -n '330,340p' ...   "1. **`--target-crs` dla CZ nie nadaje sie obecnie do scalania.**
                             Do czasu naprawy ..." / "2. **Sidecar musi niesc dokladnosc ...**"
  $ grep -rn "server:" kartograf/
    kartograf/cli/download_cmd.py:1039  (komentarz historyczny — jedyne trafienie)
  $ sed -n '1063,1064p' kartograf/cli/download_cmd.py
    f"pinned: {pinned.description} ({pinned.accuracy_m} m)"
  ```
- Uzasadnienie: zero odwolan do ADR-024 w calym pliku (potwierdzone wlasnym grepem), a caly
  dokument — lacznie z sekcja "0. Wniosek nadrzedny (czytaj najpierw)" — opisuje w czasie
  terazniejszym blad usuniety w 0.7.0. Oba postulaty z sekcji 7 (reprojekcja lokalna,
  dokladnosc w sidecarze) sa zrealizowane, co potwierdza kod. Dokument jest przy tym
  najlatwiejszy do zlego odczytania z calego obszaru A7: jego pierwszy naglowek instruuje
  "czytaj najpierw".
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/research/2026-08-11-adr024-seam-report.md` — naglowkowa errata wg
  wzoru z `2026-08-11-etap1-e2e.md` (blok przed sekcja 0), tresc jak zaproponowal A7.
  Przypiete kodem: `kartograf/cli/download_cmd.py:1063` + `tests/test_cuzk_dmr.py::
  TestHorizontalReprojection::test_server_is_asked_only_for_native_5514`. Rozmiar: S;
  ryzyko regresji: niskie.

### A7-4 — `2026-08-11-adr024-bugfix-report.md`: nieaktualne 1,25 m i "fix nie zweryfikowany na zywo"
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ sed -n '10,11p' docs/research/2026-08-11-adr024-bugfix-report.md
    "**Odpowiedz: NIE tak samo — ... ale jest wlasne, systematyczne przesuniecie 1,25 m.**"
  $ sed -n '197,203p' ...  "1. **Fix nie zostal zweryfikowany na zywych danych.** ...
                             Rekomendacja przed mergem: powtorzyc punkty 1 i 4 macierzy E2E"
  $ sed -n '309,311p' ...  "1. **Zastrzezenie nr 1 z pierwszej rundy nadal aktualne**"
  $ sed -n '140,142p' docs/research/2026-08-11-adr024-verify-report.md
    "to **4,92 m, nie 1,25 m** — blad serwerowej sciezki 3045 jest **zmienny przestrzennie**"
  $ sed -n '12,15p' ...verify-report.md   -> punkty 1 i 4: PASS, RMS(0,0) 0,016 / 0,031 m
  $ grep -n "Zywa weryfikacja\|4,92" docs/DECISIONS.md
    629 (Korekta liczby: 4,92 m), 734 (Zywa weryfikacja fixu, oba punkty PASS)
  $ grep -niE "errat|nieaktual|uniewazn|Adnotacja" docs/research/2026-08-11-adr024-bugfix-report.md
    tylko l. 190/203/301 — tresc merytoryczna, zadnej adnotacji korygujacej
  ```
- Uzasadnienie: ADR-024 przejal obie korekty w osobnych, datowanych sekcjach; bugfix-report
  nadal podaje 1,25 m jako stala i konczy sie otwartym zastrzezeniem, ktore zostalo
  zamkniete. Pomiarow nie weryfikowalem (brak `seam/`), ale to nie jest potrzebne — sprzecznosc
  jest miedzy dwoma dokumentami repo, a ADR-024 jest strona wiazaca.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/research/2026-08-11-adr024-bugfix-report.md` — naglowkowa errata
  z dwoma punktami (liczba 4,92 m / zmiennosc przestrzenna; zamkniecie Zastrzezenia 1 z
  odeslaniem do verify-report). Przy okazji zalatwia A7-10 dla l. 4 (dopisac "kopia:
  `docs/research/2026-08-11-adr024-seam-report.md`"). Rozmiar: S; ryzyko regresji: niskie.

### A7-5 — Design PL-2000 opisuje `parser_1992.py` / `_Parser1992` / `_Parser2000`, ktore nie powstaly
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ sed -n '17,26p' docs/superpowers/plans/2026-02-24-pl2000-support-design.md
    "Wewnetrznie deleguje do `_Parser1992` lub `_Parser2000` ..."
    "├── parser_1992.py       # _Parser1992 — wyekstrahowana logika PL-1992"
  $ .venv/bin/python -c "import kartograf.core.parser_1992"
    ModuleNotFoundError: No module named 'kartograf.core.parser_1992'
  $ ls kartograf/core/  -> geometry.py parser_2000.py parser_registry.py parser_tm33.py sheet_parser.py
  $ grep -n "^class" kartograf/core/parser_2000.py  -> 49:class Parser2000:
  $ grep -niE "errat|nieaktual|Status" ...pl2000-support-design.md  -> tylko "**Status:** Zatwierdzony"
  ```
- Uzasadnienie: ADR-017 ("Decyzja: Opcja B ... deleguje do `Parser2000`") opisuje wariant
  faktycznie zrealizowany; dokument nie ma zadnej adnotacji, a jego naglowek nadal glosi
  "Status: Zatwierdzony", co czyta sie jak opis stanu aktualnego. Dodatkowo plan implementacji
  z tego samego dnia (`2026-02-24-pl2000-implementation.md`:7) mowi wprost odwrotnie —
  sprzecznosc wewnatrz pary spec/plan, nieoznaczona po zadnej stronie.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/superpowers/plans/2026-02-24-pl2000-support-design.md` — jedna linia
  naglowkowej erraty (tresc jak u A7) + zamiana "Status: Zatwierdzony" na "Status: WYKONANY
  (v0.5.0), zrealizowany wg ADR-017". Rozmiar: S; ryzyko regresji: niskie. Priorytet nizszy
  niz A7-1..A7-4 (dokument z lutego, nie dotyczy zmian 0.7.0).

### A7-6 — Spec etapu 0 dokumentuje `transform.horizontal = "server:EPSG:2180"` jako kontrakt sidecara
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ grep -n "server:" docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md
    341:  transform: dict | None  # etap 0: None; etap 1+: {"horizontal": "server:EPSG:2180",
  $ sed -n '12,23p' ...   # errata, 3 punkty: zasada #7/KNOWN_PATHS, 9651->5621, nodata 48,3%
  $ sed -n '28,30p' docs/CHANGELOG.md
    "- **Sidecary CZ: `transform.horizontal` zmienia format i zakres** (ADR-024).
       Bylo `"server:EPSG:<kod>"` (tylko przy `--target-crs`), jest ..."   [Breaking Changes]
  $ grep -rn "server:" kartograf/  -> tylko komentarz historyczny download_cmd.py:1039
  ```
- Uzasadnienie: l. 341 to jedyne trafienie `server:` w specu i lezy w sekcji 6.3, czyli
  w kontrakcie `ResultMetadata` — jedynej obserwowalnej zmianie etapu 0. Errata etapu 0 ma
  3 punkty i zaden nie dotyczy formatu pola sidecara, mimo ze siostrzana errata specu etapu 1
  ten sam punkt wymienia wprost ("sidecar `server:EPSG:*`"). CHANGELOG klasyfikuje zmiane jako
  Breaking Change, wiec to kontrakt konsumenta (Hydrograf), nie detal. Lagodzaco: pkt 1
  erraty etapu 0 mowi juz, ze reprojekcja CZ jest "wylacznie lokalna, przypieta operacja",
  wiec uwazny czytelnik moze wywnioskowac zmiane formatu — dlatego to najslabsze z szesciu
  ustalen A7, ale nadal prawdziwe.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md` —
  4. punkt erraty (tresc jak u A7). Przypiete testami sidecara CZ w `tests/test_cli.py`
  (asercje `transform.horizontal` zaczynajace sie od `pinned:`). Rozmiar: S; ryzyko: niskie.

## Ustalenia A8

### A8-1 — 21 testow "jednostkowych" wykonuje realne zapytania HTTP do GUGiK
- Werdykt: CONFIRMED (liczba 21 potwierdzona co do jednego testu)
- Reprodukcja: wlasna wtyczka-obserwator `scratchpad/v7_netobs.py` (patch
  `socket.socket.connect` + `socket.create_connection`, **bez blokowania**, log per `nodeid`):
  ```
  $ PYTHONPATH=$SCR .venv/bin/python -m pytest tests/ -q -p no:cacheprovider -p v7_netobs
    1402 passed in 25.40s
  $ ... liczba testow z ruchem sieciowym: 29   (wszystkie -> ('91.223.135.44', 443))
  ```
  Rozbicie 29 = 8 jawnie oznaczonych `@pytest.mark.live`
  (`tests/test_pl2000_verification.py::TestPL2000LiveWMS::test_wms_query_at_bbox_center`,
  parametry 5.176.14 / 5.180.10 / 6.175.15 / 6.179.12 / 6.185.20 / 7.170.12 / 7.180.8 / 8.170.10)
  **+ 21 zwyklych testow jednostkowych**:
  - `tests/test_gugik_provider.py` (13): `TestGugikProviderDownloadGodlo::{test_download_godlo_creates_directory,
    test_download_godlo_saves_content, test_download_godlo_uses_opendata, test_download_godlo_with_timeout}`;
    `TestGugikProviderGetOpendataUrl::{test_get_opendata_url_not_found, test_get_opendata_url_success,
    test_get_opendata_url_tries_all_layers, test_get_opendata_url_uses_correct_endpoint_for_1m,
    test_get_opendata_url_uses_correct_endpoint_for_5m}`;
    `TestGugikProviderRetry::{test_download_exponential_backoff, test_download_retry_exhausted,
    test_download_retry_on_failure}`; `TestGugikProviderSession::test_uses_provided_session`
  - `tests/test_metadata_cache.py` (5): `TestGugikNmptProviderCacheIntegration::test_no_cache_backward_compat`,
    `TestGugikOrtoProviderCacheIntegration::{test_cache_miss_stores_result, test_no_cache_backward_compat}`,
    `TestGugikProviderCacheIntegration::{test_cache_miss_queries_wms_and_stores, test_no_cache_backward_compat}`
  - `tests/test_gugik_nmpt.py` (2): `TestGugikNmptProviderDownload::{test_download_uses_opendata,
    test_get_opendata_url_uses_nmpt_endpoint}`
  - `tests/test_soilgrids.py` (1): `TestSoilGridsTeryt::test_get_bbox_for_teryt_returns_bbox`
  Rozbicie zgadza sie z A8 co do pliku i co do liczby (13/5/2/1).
- Uzasadnienie: mechanizm dokladnie taki, jak opisal A8 — `_fetch_wms_layers` tworzy wlasna
  `requests.Session()` (`kartograf/providers/pl/gugik.py:268-277`), wiec wstrzykniety mock
  jej nie przechwytuje. **Korekta dla scislosci:** te testy nie *padaja* offline. Przy blokadzie
  bedacej podklasa `OSError` (czyli realistyczny stan "brak sieci") `requests` zamienia ja na
  `ConnectionError`, `_get_validated_layers` lapie wyjatek i wraca do hardcoded `WMS_LAYERS`:
  ```
  $ PYTHONPATH=$SCR .venv/bin/python -m pytest tests/ -q -p v7_netblock
    1394 passed, 8 skipped in 18.11s
  ```
  A8 dostal "29 failed", bo jego `NetworkBlocked` nie dziedziczy z `OSError` i przechodzil
  przez `requests` nieopakowany. Realny koszt jest wiec inny, niz sugeruje slowo "failed":
  ~21 zbednych zapytan do produkcyjnego serwera GUGiK przy kazdym `pytest tests/`,
  uzaleznienie wyniku od stanu serwera (patrz A8-2) i cichy fallback maskujacy fakt,
  ze mock nie dziala. To nadal Important i nadal warto naprawic.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `tests/conftest.py` — jedna autouse fixture stubujaca
  `GugikProvider._fetch_wms_layers` (wzorzec istnieje juz w repo:
  `tests/test_gugik_orto.py:19`) plus autouse fixture blokujaca `socket.socket.connect`
  poza loopbackiem dla testow bez markera `live`. Przypiete samo przez siebie: po naprawie
  ponowny przebieg z `v7_netobs.py` musi dac wylacznie 8 testow `live` na liscie.
  Rozmiar: S (fixture WMS) do M (razem z bezpiecznikiem socketowym); ryzyko regresji: niskie —
  fixture stubuje warstwe, ktora offline i tak wpada w fallback, wiec asercje sie nie zmieniaja
  (zweryfikowane: przebieg offline jest zielony).

### A8-2 — Wynik `test_get_opendata_url_tries_all_layers` zalezy od stanu zywego serwera GUGiK
- Werdykt: CONFIRMED
- Reprodukcja: wlasny snippet z oryginalnymi fixturami testu (`mock_wms_response_no_url` x2 +
  `mock_wms_response_with_url`), podstawiana liczba warstw w `provider._validated_layers`:
  ```
  warstw=4: PASS (asercje spelnione) call_count=3
  warstw=3: PASS (asercje spelnione) call_count=3
  warstw=2: FAIL DownloadError: No NMT 1m data available for N-34-130-D-d-2-4 ...
  warstw=1: FAIL DownloadError: ...
  ```
  Liczba warstw pochodzi z zywego serwera:
  ```
  $ .venv/bin/python -c "...; print(GugikProvider()._get_validated_layers('1m','EVRF2007'))"
    ['SkorowidzeNMT2026','SkorowidzeNMT2025','SkorowidzeNMT2024','SkorowidzeNMT2023iStarsze']  (4)
  ```
- Uzasadnienie: prog to dokladnie 3 warstwy. Dzis GUGiK publikuje 4 online, a offline fallback
  `WMS_LAYERS["1m"]["EVRF2007"]` ma tez 4 — dlatego test jest zielony w obie strony, ale
  z dwoch roznych powodow. Konsolidacja rocznikow po stronie GUGiK do <= 2 warstw
  (a taka juz sie zdarzyla dla ortofotomapy: `2023..2018` scalone w `...Starsze`) wywali test
  bez jednej zmiany w repo. To bezposrednia konsekwencja A8-1 i naprawia sie tym samym ruchem.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `tests/test_gugik_provider.py:481-497` — jedna linia ustawiajaca
  `provider._validated_layers[("1m","EVRF2007")] = ["L1","L2","L3"]` przed wywolaniem
  (albo `patch.object(provider, "_get_validated_layers", return_value=[...])`). Wtedy
  `call_count == 3` mierzy petle w kodzie, a nie liczbe warstw u dostawcy. Rozmiar: S;
  ryzyko regresji: niskie.

### A8-3 — Cala sciezka CORINE GeoTIFF (CLMS/OAuth2) jest bez testow
- Werdykt: CONFIRMED
- Reprodukcja: wlasna mutacja w kopii drzewa (`scratchpad/v7mut`, repo nietkniete) —
  `raise RuntimeError('V7 MUTACJA')` jako pierwsza instrukcja 8 funkcji
  (`get_credentials_from_keychain`, `save_credentials_to_keychain`, `_exchange_token`,
  `_download_via_clms`, `_download_via_clms_proxy`, `_poll_clms_task_proxy`,
  `_download_via_clms_direct`, `_poll_clms_task`), lacznie z mutacja A8-4:
  ```
  ### BASELINE offline:              1394 passed, 8 skipped in 17.88s
  ### M-A8-3+4 (corine x8 + proxy):  1394 passed, 8 skipped in 17.26s
  ```
  Pokrycie potwierdza: `kartograf/providers/corine.py 361 188 48%`, Missing 82-129, 146-193,
  209-226, 269-277, 281-329, 595-626, 638-680, 689-720, 732-779, 793-827.
- Uzasadnienie: sciezka jest krytyczna funkcjonalnie (to **glowny** produkt CORINE — GeoTIFF;
  testowany jest wylacznie fallback WMS/PNG), ale **nie jest to regresja 0.7.0**:
  `git diff --stat f9a0a0f..HEAD -- kartograf/providers/corine.py` daje 4 wstawki / 2 usuniecia,
  a hunki (`@@ -48`, `@@ -446,0`, `@@ -466`) leza **poza** niepokrytym obszarem CLMS.
  Czyli luka istnieje od co najmniej v0.6.0 i wydanie 0.7.0 jej nie pogarsza.
- Naprawa przed wydaniem 0.7.0: NIE (odlozyc)
- Zakres naprawy: n/d przed wydaniem. Do backlogu 0.7.1: `tests/test_corine_clms.py` —
  minimum `_exchange_token` (JWT -> token, 1 happy + 1 blad), `_download_via_clms_direct`
  + `_poll_clms_task` (submit 202 -> polling -> plik, 1 happy + 1 timeout) na mockowanej
  sesji. Rozmiar: **M** dla tego minimum (L dla pelnego pokrycia 8 funkcji, w tym keychain);
  ryzyko regresji: niskie (same testy) — ale to za duzo, by wpychac to w okno wydania.

### A8-4 — Handler proxy autoryzacji CLMS (`do_POST`) jest calkowicie bez testow
- Werdykt: CONFIRMED
- Reprodukcja: ta sama mutacja co wyzej — `do_POST` i `send_json` w `kartograf/auth/proxy.py`
  rzucaja `RuntimeError`, suite bez zmiany: `1394 passed, 8 skipped`. Pokrycie:
  `kartograf/auth/proxy.py 175 71 59%`, Missing 80-81, 162, 166-171, **195-301**
  (w tym doklejenie `Authorization: Bearer` i streaming `/download`).
- Uzasadnienie: sciezka krytyczna z punktu widzenia bezpieczenstwa — jedynym zadaniem tego
  komponentu jest izolacja credentials i doklejanie naglowka `Bearer`, a zaden test tego nie
  sprawdza. Ale, jak przy A8-3, **to nie jest regresja 0.7.0**:
  `git diff --stat f9a0a0f..HEAD -- kartograf/auth/proxy.py` jest **pusty** — plik nie byl
  ruszany od v0.6.0 (ostatni commit dotyczacy: `4dd5f4d`, sprzed 0.6.0).
- Naprawa przed wydaniem 0.7.0: NIE (odlozyc)
- Zakres naprawy: n/d przed wydaniem. Do backlogu: `tests/test_auth_proxy.py` — instancjonowac
  klase handlera z podstawionym `rfile`/`wfile` (BytesIO) i `credentials` jako Mock; 4 asercje
  (naglowek Bearer doklejony, 500 przy braku tokenu, 400 na zlym JSON, 404 na nieznanej sciezce).
  Rozmiar: M; ryzyko regresji: niskie.

### A8-5 — Sekwencyjna sciezka `_download_godlo_list` (`--workers 1`) nie jest testowana
- Werdykt: CONFIRMED
- Reprodukcja: mutacja w `scratchpad/v7mut` —
  `if max_workers <= 1: return []  # V7 MUTACJA` (przed `all_paths: list[Path] = []`,
  `kartograf/cli/download_cmd.py:651-653`):
  ```
  ### M-A8-5 (sekwencyjny _download_godlo_list -> []):  1394 passed, 8 skipped in 17.30s
  ```
  Identycznie z baseline. Pokrycie: `download_cmd.py` Missing zawiera `652-663`.
- Uzasadnienie: sciezka krytyczna — `--workers 1` to udokumentowana opcja CLI (CLAUDE.md,
  "Ograniczenia"), a mutacja zamienia pobranie w ciche zwrocenie pustej listy: uzytkownik
  dostaje kod wyjscia sukcesu i zero plikow. Funkcja ma dwa wywolania
  (`download_cmd.py:793` — bbox, `:1417` — geometry), wiec dotyczy obu trybow obszarowych.
  Ryzyko realne, choc nie jest to nowy kod 0.7.0.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `tests/test_cli.py` — po jednym tescie w `TestCmdDownloadBbox`
  i `TestCmdDownloadGeometry` z `--workers 1`, asercja na liste zwroconych sciezek
  (obowiazkowo z przypadkiem, w ktorym `download_sheet` zwraca `list[Path]` — bo splaszczanie
  `isinstance(result, list)` to druga niepokryta galaz). Rozmiar: S (~25 linii);
  ryzyko regresji: niskie (tylko nowe testy, zero zmian w kodzie produkcyjnym).

### A8-6 — Skrot "plik juz w ukladzie zadania" w sciezce CZ `--geometry` jest bez testu
- Werdykt: CONFIRMED
- Reprodukcja: mutacja zamieniajaca osie w `_resolve_cz_geometry_bbox`
  (`kartograf/cli/download_cmd.py:459`):
  ```python
  return BBox(bbox.min_y, bbox.min_x, bbox.max_y, bbox.max_x, image_sr)  # V7 MUTACJA
  ```
  ```
  ### M-A8-6 (_resolve_cz_geometry_bbox zamiana osi):  1394 passed, 8 skipped in 17.63s
  ```
  Pokrycie: `download_cmd.py` Missing zawiera `459` i `461-466`.
- Uzasadnienie: **najpowazniejsze z ustalen A8**, bo to jedyne, ktore dotyczy kodu **nowego
  w 0.7.0** (sciezka CZ, etap 1) i ktore w razie bledu zawodzi cicho: uzytkownik podajacy
  geometrie juz w EPSG:5514 dostalby raster z zupelnie innego obszaru, z poprawnie
  wygladajacym sidecarem. Skrot jest przy tym scisle zwiazany z ADR-024 (zasada "zero
  transformacji, gdy uklady sa zgodne"), a caly reszta tej reguly jest twardo przypieta
  9 testami — ta jedna galaz wypadla z siatki. Galaz bledu (461-466, komunikat z `Remedium`)
  tez jest niepokryta.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `tests/test_cli.py`, klasa `TestAutoSplitGeometry` lub `TestCmdDownloadCz` —
  test z plikiem SHP majacym `.prj` w EPSG:5514 (fixture `pts.shp`/`pts.prj` da sie zbudowac
  jak w istniejacych testach geometrii) i asercja na **dokladne** wartosci
  `min_x/min_y/max_x/max_y` przekazane do `_run_cz`, plus drugi test na komunikat bledu
  z `Remedium` (podstawiony `read_source_crs` rzucajacy `TransformError`). Rozmiar: S;
  ryzyko regresji: niskie (tylko testy).

### A8-7 — Progi pokrycia z DEVELOPMENT_STANDARDS 10.1 nie sa spelnione ani egzekwowane
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ awk '/^## 10\./,/^## 11\./' docs/DEVELOPMENT_STANDARDS.md   # sekcja 10.1
    | Core (parser, providers, manager) | **>= 80%** |
    | CLI, utility, formatowanie        | **>= 60%** |
    pytest tests/ --cov=kartograf --cov-report=html --cov-fail-under=60
  $ sed -n '78,80p' pyproject.toml
    [tool.coverage.report]
    fail_under = 60
  $ ls .github/workflows   -> BRAK .github/workflows   (zero CI w repo)
  $ COVERAGE_FILE=$SCR/v7cov pytest tests/ --cov=kartograf --cov-report=term   (offline)
    kartograf/providers/corine.py   361 188 48%
    kartograf/providers/base.py      66  18 73%
    kartograf/auth/proxy.py         175  71 59%
    kartograf/providers/soilgrids.py 143 26 82%
    TOTAL 5216 545 90%
    Required test coverage of 60.0% reached. Total coverage: 89.55%
  ```
- Uzasadnienie: potwierdzone w calosci. Warstwa "providers" ma prog 80% i lamia go
  `corine.py` (48%, -32 pkt) oraz `base.py` (73%, -7 pkt); `auth/proxy.py` (59%) lamie nawet
  prog utility 60%, o wlos. Egzekwowanie to jedno globalne `fail_under = 60`, ktore przy
  89,5% calosci jest spelnione zawsze — czyli progi warstwowe ze standardu **nie sa
  egzekwowane w ogole**. Nie ma tez CI (`.github/workflows` nie istnieje), wiec jedyna brama
  jest lokalny przebieg. Drobna korekta liczb A8: w moim przebiegu `soilgrids.py` to 82%
  (nie 81%) i TOTAL 89,55% (nie 89,53%) — roznica bierze sie z trybu offline (8 testow `live`
  pominietych, jeden test soilgrids nie idzie do sieci); merytorycznie bez znaczenia.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/DEVELOPMENT_STANDARDS.md` sekcja 10.1 — dopisac wiersz "Znane
  odstepstwa (0.7.0): `providers/corine.py` 48% i `auth/proxy.py` 59% — tor CLMS/OAuth2 bez
  testow, dlug sprzed 0.6.0, backlog 0.7.1 (A8-3/A8-4)". Podniesienie `fail_under` do 85
  w `pyproject.toml` jest technicznie S i bezpieczne (zapas 4,5 pkt), ale bez CI nic nie
  egzekwuje, a moze zablokowac lokalny przebieg komus, kto uruchamia podzbior testow —
  proponuje odlozyc razem z wprowadzeniem CI. Rozmiar: S; ryzyko regresji: niskie.

## Tabela

| ID | Werdykt | Naprawa 0.7.0 | Rozmiar | Ryzyko |
|---|---|---|---|---|
| A7-1 | CONFIRMED | DOCS-ONLY | S | niskie |
| A7-2 | CONFIRMED | DOCS-ONLY | S | niskie |
| A7-3 | CONFIRMED | DOCS-ONLY | S | niskie |
| A7-4 | CONFIRMED | DOCS-ONLY | S | niskie |
| A7-5 | CONFIRMED | DOCS-ONLY | S | niskie |
| A7-6 | CONFIRMED | DOCS-ONLY | S | niskie |
| A8-1 | CONFIRMED (21 potwierdzone; korekta: testy nie padaja offline, tylko wysylaja zapytania) | TAK | S-M | niskie |
| A8-2 | CONFIRMED | TAK | S | niskie |
| A8-3 | CONFIRMED (dlug sprzed 0.6.0, nie regresja 0.7.0) | NIE (odlozyc) | M | niskie |
| A8-4 | CONFIRMED (plik nietkniety od 0.6.0) | NIE (odlozyc) | M | niskie |
| A8-5 | CONFIRMED | TAK | S | niskie |
| A8-6 | CONFIRMED (jedyne dotyczace kodu nowego w 0.7.0) | TAK | S | niskie |
| A8-7 | CONFIRMED (drobna korekta liczb: soilgrids 82%, TOTAL 89,55%) | DOCS-ONLY | S | niskie |

## Nowe ustalenia przy okazji (max 3, tylko jesli Critical/Important i z dowodem)

### N1 [Important] Jednorazowy, nieodtwarzalny przebieg z 19 bledami w testach przypinajacych ADR-024
Pierwszy pelny przebieg suite w tej sesji (z wtyczka blokujaca sockety, `v7_netblock.py`)
dal **19 failed, 1375 passed, 8 skipped**, przy czym padly dokladnie te testy, ktore pilnuja
fixu ADR-024 — m.in. `test_cuzk_dmr.py::TestHorizontalReprojection::{test_warp_forces_the_pinned_operation
[bbox-EPSG:2180], test_server_is_asked_only_for_native_5514, test_nodata_does_not_bleed_into_interpolation}`,
`test_cli.py::TestAutoSplitBBox::test_pl_part_of_cz_crs_bbox_leaves_krovak_pinned`,
`test_transform_crs.py::TestGdalOperation::test_operation_carries_datum_step`. Objaw:
```
kartograf/transform/crs.py:70: TransformError: Transformacja zwrocila wartosc nieskonczona
  [axis order change (2D) + Inverse of UTM zone 33N + ETRS89 to S-JTSK [JTSK03] (1)
   + S-JTSK [JTSK03] to S-JTSK (1) + Krovak East North (Greenwich)]
```
oraz `assert 'molobadekas' in <pipeline>` — czyli PROJ wybral **inna operacje** niz zwykle.
Pelne wyjscie: `scratchpad/v7_run1_19fail.txt`.
**Nie udalo mi sie tego odtworzyc w 4 kolejnych probach** (powtorka tego samego przebiegu
z blokada: `1394 passed, 8 skipped`; te same testy w izolacji: pass; pusty katalog PROJ
+ martwe proxy dla libcurl: pass; zapelnienie cache PROJ i odciecie sieci: pass). Hipoteze
"zaleznosc od siatek PROJ z CDN" **obalilem** — wszystkie polityki CZ maja
`allow_network_grids=False` (`kartograf/providers/cuzk/dmr.py:75,76,80`), a katalog uzytkownika
PROJ nie rosnie w trakcie suite. Mechanizm pozostaje nieustalony, ale sygnal jest powazny:
zestaw testow bedacy jedynym zabezpieczeniem najwiekszego bugfixu 0.7.0 potrafil zejsc
z zielonego na 19 bledow bez zmiany w repo. Rekomendacja przed wydaniem: uruchomic pelny
suite 3x pod rzad (najlepiej w swiezym procesie i przy pustym `__pycache__`) i potwierdzic
stabilnosc; jesli powtorzy sie choc raz — zbadac jako blokujace, bo w produkcji ten sam
`TransformError` oznacza nieudane pobranie CZ, a nie tylko czerwony test.

### N2 [Important] `docs/DEVELOPMENT_STANDARDS.md` 10.1 podaje komende, ktora nie egzekwuje wlasnych progow
Poza tym, co opisal A8-7: sama sekcja 10.1 zestawia tabele progow warstwowych (80%/60%)
z jedna komenda `pytest tests/ --cov=kartograf --cov-report=html --cov-fail-under=60`,
czyli **wlasny przyklad standardu egzekwuje tylko nizszy z dwoch progow, globalnie**.
To nie jest luka w konfiguracji (to A8-7), tylko sprzecznosc wewnatrz samego dokumentu
normatywnego — czytelnik, ktory zrobi dokladnie to, co mowi standard, nie wykryje
`corine.py` 48%. Naprawa: DOCS-ONLY, w tym samym ruchu co A8-7 (dopisac drugie wywolanie
`coverage report --include='kartograf/providers/*' --fail-under=80`). Rozmiar S, ryzyko niskie.
