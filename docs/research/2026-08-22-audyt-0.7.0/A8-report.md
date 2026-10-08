# A8 — Jakosc testow i pokrycie

Zakres: `tests/conftest.py`, `tests/test_transform_crs.py`, `tests/test_sidecar.py`,
`tests/test_transport_http.py`, `tests/test_parser_tm33.py`, `tests/test_sources_registry.py`
(przeczytane w calosci); `tests/test_cli.py`, `tests/test_cuzk_client.py`, `tests/test_cuzk_dmr.py`,
`tests/test_cuzk_sheets.py`, `tests/test_gugik_laz.py`, `tests/test_gugik_provider.py`,
`tests/test_gugik_orto.py`, `tests/test_landcover.py`, `tests/test_metadata_cache.py`,
`tests/test_pl2000_verification.py`, `tests/test_storage.py`, `tests/test_soilgrids.py`,
`tests/test_hsg.py`, `tests/test_auth_client.py`, `tests/test_wms_layer_validation.py`
(przeczytane fragmenty istotne dla zadania); `tests/fixtures/cuzk/*`; `pyproject.toml`
(sekcje `[tool.pytest.ini_options]`, `[tool.coverage.*]`); `docs/DEVELOPMENT_STANDARDS.md` sekcja 10;
`kartograf/providers/base.py`, `kartograf/providers/corine.py`, `kartograf/auth/proxy.py`,
`kartograf/cli/download_cmd.py`, `kartograf/providers/pl/gugik.py`, `kartograf/hydrology/hsg.py`
(fragmenty wskazane przez kolumne Missing).

Metoda:
- jeden przebieg pokrycia: `pytest tests/ -q -p no:cacheprovider --cov=kartograf --cov-report=term-missing --cov-report=json` (1402 passed, 89.53%); `.coverage` usuniety po przebiegu, `git status` czysty;
- **mutacje w scratchpadzie** (kopia drzewa `kartograf/` + `tests/` do `/tmp/.../scratchpad/mut`, repo NIE tykane): 9 mutacji, po kazdej pelny przebieg suite;
- **wtyczka pytest blokujaca sniady TCP** (`scratchpad/blocknet.py`, `blocknet2.py`, ladowana przez `-p`) — identyfikacja testow siegajacych do sieci;
- **wtyczki sledzace IO** (`scratchpad/trackdir.py`, `trackfile.py`) — identyfikacja testow piszacych poza `tmp_path`;
- analiza AST calego `tests/` (testy bez asercji, identyczne cialka, kolizje nazw);
- grep: `pytest.skip|xfail|skipif|importorskip`, `autouse`, `requests.get|Session()`, literaly sciezek;
- przebieg suite w odwroconej kolejnosci plikow (zaleznosci od kolejnosci).

Nie sprawdzono:
- `tests/test_parser_2000.py`, `tests/test_sheet_parser.py`, `tests/test_geometry.py`,
  `tests/test_parallel_download.py`, `tests/test_integration.py`, `tests/test_auth_proxy.py`,
  `tests/test_download_manager.py` — czytane wybiorczo (grep/AST/coverage), nie linia po linii;
  te pliki maja pokrycie modulow >=95% i przeszly mutacje, ktore ich dotyczyly.
- Testy nie byly uruchamiane pod `pytest-randomly` (brak w `.venv`) — zaleznosc od kolejnosci
  sprawdzona tylko dla odwroconej kolejnosci plikow.
- Nie audytowano poprawnosci merytorycznej asercji geodezyjnych (wartosci bboxow, EPSG) — to obszar innych audytorow.

## Ustalenia

### A8-1 [Important] 21 testow "jednostkowych" wykonuje realne zapytania HTTP do GUGiK
- Plik: `tests/test_gugik_provider.py:436-545`, `tests/test_gugik_nmpt.py:222`, `tests/test_metadata_cache.py:370+`
- Twierdzenie: `GugikProvider._fetch_wms_layers()` tworzy **wlasna** `requests.Session()`, wiec wstrzykniecie mocka przez `GugikProvider(session=mock)` go nie przechwytuje — testy tych klas wychodza do `mapy.geoportal.gov.pl` przy kazdym `pytest tests/`.
- Dowod (`kartograf/providers/pl/gugik.py:268-277`):
  ```python
  # Use a dedicated session to avoid interfering with the main
  # session's mock side_effects in tests or download state
  session = requests.Session()
  ...
  response = session.get(wms_endpoint, params=params, timeout=timeout)
  ```
  Traceback z przebiegu z zablokowanym socketem:
  ```
  tests/test_gugik_provider.py:464: in test_get_opendata_url_success
      url = provider._get_opendata_url("N-34-130-D-d-2-4")
  kartograf/providers/pl/gugik.py:486: in _get_opendata_url
      wms_layers = self._get_validated_layers(...)
  kartograf/providers/pl/gugik.py:277: in _fetch_wms_layers
      response = session.get(wms_endpoint, params=params, timeout=timeout)
  E   NetworkBlocked: NETWORK BLOCKED: connect to ('91.223.135.44', 443)
  ```
- Weryfikacja: wtyczka `scratchpad/blocknet.py` (patch `socket.socket.connect`) — `29 failed, 1373 passed`; z tego 8 to jawnie oznaczone `@pytest.mark.live`, pozostale **21** to zwykle testy jednostkowe: `test_gugik_provider.py` (13), `test_metadata_cache.py` (5), `test_gugik_nmpt.py` (2), `test_soilgrids.py::TestSoilGridsTeryt::test_get_bbox_for_teryt_returns_bbox` (1). Wzorzec poprawny istnieje juz w repo — `tests/test_gugik_orto.py:19` ma autouse fixture stubujaca `_fetch_wms_layers`, a `tests/test_gugik_laz.py:19` stala `_LAZ_SESSION_PATCH`.
- Proponowana naprawa: dodac do `tests/conftest.py` autouse fixture stubujaca `GugikProvider._fetch_wms_layers` (analogicznie do `test_gugik_orto.py`) oraz — jako bezpiecznik — autouse fixture blokujaca `socket.socket.connect` dla wszystkiego poza `-m live` i loopbackiem.
- Pewnosc: wysoka

### A8-2 [Important] Wynik `test_get_opendata_url_tries_all_layers` zalezy od stanu zywego serwera GUGiK
- Plik: `tests/test_gugik_provider.py:481-497`
- Twierdzenie: test ustawia `side_effect` z 3 odpowiedziami i asercjonuje `call_count == 3`, ale liczba iteracji petli pochodzi z `_get_validated_layers()`, ktore przy dostepnej sieci zwraca liste warstw **odkryta na zywo**; gdy GUGiK opublikuje mniej niz 3 warstwy `Skorowidze`, test zacznie padac bez zadnej zmiany w kodzie.
- Dowod (uruchomiony snippet, `.venv/bin/python`, podstawiona liczba warstw do `provider._validated_layers`):
  ```
  warstw=4: OK, call_count=3
  warstw=2: DownloadError: No NMT 1m data available for N-34-130-D-d-2-4 (vertical_crs=EVRF2007).
  ```
- Weryfikacja: snippet powyzej + przebieg offline (fallback na `WMS_LAYERS`, 4 warstwy) vs. przebieg z siecia — oba obecnie zielone, ale z roznych powodow.
- Proponowana naprawa: w tym tescie jawnie ustawiac liste warstw (`provider._validated_layers[("1m","EVRF2007")] = [...3 warstwy...]`) albo patchowac `_get_validated_layers`; wtedy `call_count == 3` mierzy zachowanie kodu, nie serwera.
- Pewnosc: wysoka

### A8-3 [Important] Cala sciezka CORINE GeoTIFF (CLMS/OAuth2) jest bez testow — mutacja przezywa suite
- Plik: `kartograf/providers/corine.py:82-329, 595-827` (pokrycie pliku 48%)
- Twierdzenie: osiem funkcji obslugujacych glowny produkt CORINE (GeoTIFF przez CLMS) mozna zastapic `raise RuntimeError` i cala suite (1402 testy) przechodzi — testowany jest wylacznie fallback WMS/PNG.
- Dowod: zmutowane w kopii `get_credentials_from_keychain`, `save_credentials_to_keychain`, `_exchange_token`, `_download_via_clms`, `_download_via_clms_proxy`, `_poll_clms_task_proxy`, `_download_via_clms_direct`, `_poll_clms_task` (wstrzykniete `raise RuntimeError('MUTACJA')` jako pierwsza instrukcja):
  ```
  zmutowano 8 funkcji
  ### M7b corine: wszystkie sciezki CLMS/keychain rzucaja:
  1394 passed, 8 skipped, 3 warnings in 18.76s
  ```
- Weryfikacja: mutacja w `/tmp/.../scratchpad/mut` (repo nietkniete), pelny przebieg pytest po mutacji.
- Proponowana naprawa: dodac testy `_download_via_clms_direct` i `_poll_clms_task` na mockowanej sesji (submit -> 202 -> polling -> plik) oraz test `_exchange_token` (JWT -> token) — minimum jeden happy path i jeden blad na kazda z dwoch wariantow (proxy/direct).
- Pewnosc: wysoka

### A8-4 [Important] Handler proxy autoryzacji CLMS (`do_POST`) jest calkowicie bez testow
- Plik: `kartograf/auth/proxy.py:162-301` (pokrycie pliku 59%)
- Twierdzenie: komponent, ktorego jedynym zadaniem jest izolacja credentials i doklejanie `Authorization: Bearer`, nie ma ani jednego testu; `do_POST` i `send_json` mozna zastapic `raise RuntimeError` bez skutku dla suite.
- Dowod: niepokryte m.in. `headers["Authorization"] = f"Bearer {token}"` (linia 226), obsluga `token is None` (222-224), streaming `/download` (279-298), oraz mutacja:
  ```
  ### M8 auth proxy do_POST/send_json rzucaja:
  1394 passed, 8 skipped, 3 warnings in 18.48s
  ```
  `tests/test_auth_proxy.py` testuje wylacznie `CLMSCredentials` (keychain, token), nie `http.server`-owy handler.
- Weryfikacja: mutacja w scratchpadzie + kolumna Missing z raportu coverage.
- Proponowana naprawa: testy handlera bez podnoszenia procesu — instancjonowac klase handlera z podstawionym `rfile`/`wfile` (BytesIO) i `credentials` jako Mock, albo uruchomic `ThreadingHTTPServer` na porcie 0 w fixture; sprawdzic co najmniej: doklejenie naglowka Bearer, 500 gdy brak tokenu, 400 na niepoprawnym JSON, 404 na nieznanej sciezce.
- Pewnosc: wysoka

### A8-5 [Important] Sekwencyjna sciezka `_download_godlo_list` (`--workers 1`) nie jest testowana
- Plik: `kartograf/cli/download_cmd.py:651-663`
- Twierdzenie: galaz `if max_workers <= 1:` mozna zamienic na `return []` i cala suite przechodzi — mimo ze `--workers 1` to udokumentowana opcja CLI, a `DownloadManager` w bibliotece domyslnie ma `max_workers=1`.
- Dowod:
  ```python
  if max_workers <= 1:
      return []  # MUTACJA: sekwencyjna sciezka nic nie pobiera
      all_paths: list[Path] = []
  ```
  ```
  ### M6 sekwencyjna sciezka _download_godlo_list zwraca []:
  1394 passed, 8 skipped, 3 warnings in 18.79s
  ```
  Zgodne z raportem coverage (linie 652-663 w kolumnie Missing).
- Weryfikacja: mutacja w scratchpadzie + pelny przebieg pytest.
- Proponowana naprawa: dodac do `TestCmdDownloadBbox`/`TestCmdDownloadGeometry` po jednym tescie z `--workers 1` asercjonujacym liste zwroconych sciezek (w tym splaszczenie wyniku `list[Path]` z `download_sheet`).
- Pewnosc: wysoka

### A8-6 [Important] Skrot "plik juz w ukladzie zadania" w sciezce CZ `--geometry` jest bez testu
- Plik: `kartograf/cli/download_cmd.py:459`
- Twierdzenie: galaz zwracajaca bbox bez transformacji (gdy CRS pliku == CRS zadania) jest niepokryta; podmiana kolejnosci osi w konstruktorze `BBox` nie psuje zadnego testu, a uzytkownikowi dalaby cicho zly zasieg pobrania.
- Dowod (mutacja):
  ```python
  return BBox(bbox.min_y, bbox.min_x, bbox.max_y, bbox.max_x, image_sr)  # MUTACJA
  ```
  ```
  ### M9 _resolve_cz_geometry_bbox zamiana osi:
  1394 passed, 8 skipped, 3 warnings in 22.26s
  ```
  Ta sama funkcja ma niepokryta rowniez galaz bledu (461-466, komunikat z `Remedium`).
- Weryfikacja: mutacja w scratchpadzie + pelny przebieg pytest.
- Proponowana naprawa: w `TestAutoSplitGeometry`/`TestCmdDownloadCz` dodac test z plikiem SHP majacym `.prj` w EPSG:5514 i asercja na dokladne wspolrzedne przekazane do providera; osobny test na komunikat bledu z `Remedium`.
- Pewnosc: wysoka

### A8-7 [Important] Progi pokrycia z DEVELOPMENT_STANDARDS 10.1 nie sa spelnione ani egzekwowane
- Plik: `docs/DEVELOPMENT_STANDARDS.md` sekcja 10.1 vs `pyproject.toml:78-80`
- Twierdzenie: standard wymaga >=80% dla warstwy "Core (parser, providers, manager)" i >=60% dla CLI/utility, ale brama w repo to pojedyncze globalne `fail_under = 60`, przez co trzy pliki ponizej progu przechodza niezauwazone.
- Dowod: `kartograf/providers/corine.py` **48%** i `kartograf/providers/base.py` **73%** (prog 80% dla providerow); `kartograf/auth/proxy.py` **59%** (prog 60%). Konfiguracja:
  ```toml
  [tool.coverage.report]
  fail_under = 60
  ```
  wynik przebiegu: `Required test coverage of 60.0% reached. Total coverage: 89.53%`.
- Weryfikacja: jeden przebieg `pytest --cov` (tabela ponizej).
- Proponowana naprawa: podniesc globalne `fail_under` do ~85% (obecny stan 89,5% daje zapas) i dodac egzekwowanie per-plik dla warstwy providerow (np. `coverage report --include='kartograf/providers/*' --fail-under=80` jako drugie wywolanie), albo swiadomie odnotowac `corine.py`/`proxy.py` jako wyjatki w DEVELOPMENT_STANDARDS.
- Pewnosc: wysoka

### A8-8 [Minor] Marker `live` nie jest domyslnie odfiltrowany, a testy live nie moga zawiesc
- Plik: `pyproject.toml:69-72`, `tests/test_pl2000_verification.py:426-482`
- Twierdzenie: `addopts = "-v --tb=short"` nie zawiera `-m "not live"`, wiec `pytest tests/` wykonuje 8 zapytan do `mapy.geoportal.gov.pl`; dodatkowo test lapie `requests.RequestException` (nadklasa m.in. `HTTPError`) i konczy `pytest.skip`, wiec nigdy nie zaraportuje awarii uslugi.
- Dowod:
  ```python
  except (requests.ConnectionError, requests.Timeout, requests.RequestException) as e:
      pytest.skip(f"WMS not reachable: {e}")
  ```
  Przebieg z siecia: `1402 passed, 0 skipped` (testy live faktycznie sie wykonaly); przebieg offline: `1394 passed, 8 skipped`.
- Weryfikacja: dwa przebiegi suite (z siecia i z wtyczka `blocknet2` udajaca `ConnectionRefusedError`).
- Proponowana naprawa: `addopts = "-v --tb=short -m 'not live'"`; testy live uruchamiane swiadomie przez `-m live`. Rozwazyc zwezenie `except` do `ConnectionError`/`Timeout`.
- Pewnosc: wysoka

### A8-9 [Minor] `tests/test_cuzk_client.py:142` uzywa sciezki wzglednej — test pada gdy CWD != korzen repo
- Plik: `tests/test_cuzk_client.py:141-144`
- Twierdzenie: fixtura ladowana jest przez `Path("tests/fixtures/...")` zamiast `Path(__file__).parent`, przez co test wiaze sie z katalogiem uruchomienia (`tests/test_cuzk_sheets.py:28` robi to poprawnie).
- Dowod:
  ```python
  fixture = json.loads(
      Path("tests/fixtures/cuzk/klady_sm5_where_ctes96.json").read_text(encoding="utf-8")
  )
  ```
  Uruchomienie z `os.chdir('/tmp')`:
  ```
  E   FileNotFoundError: [Errno 2] No such file or directory: 'tests/fixtures/cuzk/klady_sm5_where_ctes96.json'
  1 failed, 18 deselected in 0.32s
  ```
- Weryfikacja: `pytest.main` uruchomiony z podmienionym CWD (wynik powyzej).
- Proponowana naprawa: uzyc `FIXTURES = Path(__file__).parent / "fixtures" / "cuzk"` — tak jak w `tests/test_cuzk_sheets.py`.
- Pewnosc: wysoka

### A8-10 [Minor] 10 testow tworzy katalog `./data/landcover` w biezacym katalogu zamiast w `tmp_path`
- Plik: `tests/test_landcover.py:223,228,234,240,244,250,262,268,274`, `tests/test_soilgrids.py:298`
- Twierdzenie: `LandCoverManager()` bez `output_dir` wykonuje `self._output_dir.mkdir(parents=True, exist_ok=True)` na domyslnym `./data/landcover`, wiec testy zasmiecaja katalog, z ktorego uruchomiono pytest (w repo maskuje to `.gitignore:59 data/`).
- Dowod (wtyczka sledzaca `Path.mkdir`, pelny przebieg suite):
  ```
  File ".../tests/test_landcover.py", line 223, in test_init_default_provider
  ### MKDIR /home/claude-agent/workspace/Kartograf/data/landcover
  ...
  File ".../tests/test_soilgrids.py", line 298, in test_manager_soilgrids_provider
  ```
  Katalog `data/landcover` powstal o 12:35 podczas pierwszego przebiegu pokrycia.
- Weryfikacja: `scratchpad/trackdir.py` (patch `pathlib.Path.mkdir` + stacktrace) na pelnym przebiegu; potwierdzone usunieciem katalogu i ponownym przebiegiem `tests/test_landcover.py`.
- Proponowana naprawa: autouse fixture `monkeypatch.chdir(tmp_path)` na klasach `TestLandCoverManager`/`TestSoilGridsManager` — wzorzec `_isolate_cache` z `tests/test_cli.py:2232` juz jest w repo.
- Pewnosc: wysoka

### A8-11 [Minor] RuntimeWarning z `hsg.py` nie jest ani stlumiony w kodzie, ani asercjonowany w tescie
- Plik: `kartograf/hydrology/hsg.py:215-217`, `tests/test_hsg.py:416`
- Twierdzenie: `np.where` liczy obie galezie, wiec `clay / total` dla `total == 0` daje NaN i trzy `RuntimeWarning: invalid value encountered in divide`; wynik jest poprawny (maska `valid` odrzuca NaN), ale ostrzezenie jest halasem, a przy `np.seterr(all="raise")` u konsumenta (Hydrograf/Hydrolog) stalo by sie wyjatkiem.
- Dowod:
  ```python
  total = clay + sand + silt
  valid = total > 0
  clay_n = np.where(valid, clay / total * 100, 0)
  ```
  Wyjscie pytest: `3 warnings` — wszystkie z `test_calculate_hsg_nodata_handling`. `grep -rn "errstate\|seterr" kartograf/` nie zwraca nic; `pyproject.toml` nie ma `filterwarnings`.
- Weryfikacja: pelny przebieg pytest (sekcja "warnings summary") + grep.
- Proponowana naprawa: owinac normalizacje w `with np.errstate(invalid="ignore", divide="ignore"):` (albo uzyc `np.divide(..., out=np.zeros_like(clay), where=valid)`), a w `pyproject.toml` dodac `filterwarnings = ["error"]`, zeby przyszly halas byl bledem. Nie uzywac `pytest.warns` — to utrwaliloby ostrzezenie jako kontrakt.
- Pewnosc: wysoka

### A8-12 [Minor] Asercja sprzatania w `test_exhausted_retries_...` jest trywialnie prawdziwa
- Plik: `tests/test_transport_http.py:60-72`
- Twierdzenie: `assert list(tmp_path.iterdir()) == []` nie moze zawiesc, bo `session.get` rzuca `ConnectionError` zanim plik `.tmp` powstanie — sprzatanie po `RequestException` w `download_to` jest w praktyce niepokryte przez ten test.
- Dowod: mutacja usuwajaca sprzatanie w galezi `except requests.RequestException` psuje **tylko** `test_error_mid_stream_cleans_tmp`:
  ```
  ### M2 http bez sprzatania tmp:
  FAILED tests/test_transport_http.py::TestDownloadTo::test_error_mid_stream_cleans_tmp
  1 failed, 1393 passed, 8 skipped
  ```
- Weryfikacja: mutacja w scratchpadzie + pelny przebieg pytest.
- Proponowana naprawa: w tescie wyczerpanych retry uzyc `side_effect`, ktory najpierw zwraca odpowiedz urywajaca sie w trakcie streamu (jak w `test_error_mid_stream_cleans_tmp`), a dopiero potem rzuca — wtedy asercja o pustym katalogu cos mierzy. Alternatywnie usunac te asercje jako mylaca.
- Pewnosc: wysoka

### A8-13 [Minor] `omit = */__init__.py` w konfiguracji coverage ukrywa fabryki providerow
- Plik: `pyproject.toml:74-76`
- Twierdzenie: `kartograf/providers/pl/__init__.py` (regula "5m => EVRF2007") i `kartograf/providers/cuzk/__init__.py` (walidacja `resolution`) zawieraja logike warunkowa, a globalny `omit` wyklucza je z pomiaru — luka w tej logice bylaby niewidoczna w raporcie.
- Dowod: `kartograf/providers/pl/__init__.py:35-40`
  ```python
  if resolution == "5m" and vertical_crs != "EVRF2007":
      logger.warning(...)
      vertical_crs = "EVRF2007"
  ```
  Pomiar bez `omit` (rcfile w scratchpadzie): `kartograf/providers/pl/__init__.py 14 0 100%`, `kartograf/providers/cuzk/__init__.py 11 0 100%` — czyli **obecnie** oba sa pokryte, problemem jest sama polityka pomiaru.
- Weryfikacja: powtorny przebieg `pytest --cov --cov-config=scratchpad/covrc` bez `omit`.
- Proponowana naprawa: zawezic `omit` do `*/tests/*` (pliki `__init__.py` bez logiki i tak dadza 100%), albo wprost wylaczyc z omit `providers/*/__init__.py`.
- Pewnosc: wysoka

### A8-14 [Minor] Testy bez asercji i nazwy nieopisujace zachowania
- Plik: `tests/test_auth_client.py:369`, `tests/test_metadata_cache.py:335`, `tests/test_parser_tm33.py:70`
- Twierdzenie: dwa testy w calej suite nie maja zadnej asercji (sa smoke-testami "nie rzuca"), a jedna nazwa opisuje inny scenariusz niz kod.
- Dowod:
  ```python
  def test_cleanup_no_process(self, _atexit):
      client = AuthProxyClient(); client._cleanup()  # Should not raise
  def test_vacuum(self, cache):
      cache.set_url(...); cache.clear(); cache.vacuum()  # Should not raise
  ```
  `tests/test_parser_tm33.py:70 def test_two_by_two` asercjonuje liste **9** kafli (siatka 3x3), nie 2x2.
  `tests/test_sources_registry.py:47 test_transport_kind_values` i `tests/test_parser_tm33.py:100 test_constants` to testy-detektory zmiany (asercja stalej na literale) — dopuszczalne dla wartosci serializowanych, ale nie mierza zachowania.
- Weryfikacja: analiza AST calego `tests/` (skrypt w scratchpadzie) — dokladnie 2 trafienia bez asercji; reszta z lektury.
- Proponowana naprawa: w `test_cleanup_no_process` asercjonowac `client._proxy_process is None` po wywolaniu; w `test_vacuum` sprawdzic `stats()["db_size_bytes"]` po `vacuum()`; przemianowac `test_two_by_two` na `test_three_by_three_grid` (albo zwezic bbox do 2x2).
- Pewnosc: wysoka

## Tabela pokrycia

Przebieg: `pytest tests/ -q -p no:cacheprovider --cov=kartograf --cov-report=term-missing` — **1402 passed, 3 warnings, 34.9 s**.
Pokrycie calkowite: **89,53%** (5216 instrukcji, 546 niepokrytych). Konfiguracja pomija `*/tests/*` i `*/__init__.py` (patrz A8-13).

| Plik | % | Stmts | Miss | Ocena niepokrytych linii |
|---|---|---|---|---|
| `kartograf/providers/corine.py` | 48% | 361 | 188 | **KRYTYCZNE** — caly tor CLMS/OAuth2 (GeoTIFF): `get_credentials_from_keychain` 82-129, `save_credentials_to_keychain` 146-193, `get_clms_credentials` 209-226, `get_access_token` 269-277, `_exchange_token` 281-329, `_download_via_clms*` 595-779, `_poll_clms_task*` 689-827. Patrz A8-3 |
| `kartograf/auth/proxy.py` | 59% | 175 | 71 | **KRYTYCZNE** — caly `do_POST` 195-301 (doklejanie `Authorization: Bearer` 226, brak tokenu 222-224, streaming `/download` 279-298), `send_json` 166-171. Patrz A8-4 |
| `kartograf/providers/base.py` | 73% | 66 | 18 | Mieszane: trywialne (`pass` w abstrakcyjnych 102/276, `__repr__`/`__str__` 409/413, domyslne `return` 71/152/192/355/366) + **realne**: `LandCoverProvider.download_by_godlo` 340-344 (godlo -> bbox -> `download_by_bbox`) i `get_file_extension` 174-176 (`ValueError` na nieznanym formacie) |
| `kartograf/providers/soilgrids.py` | 81% | 143 | 27 | Sciezki bledow: `_download_with_retry` 593-603, `_get_bbox_for_teryt` 470/521-525, `_save_response` 624-627 — brzegowe, ale realne |
| `kartograf/cli/soilgrids_cmd.py` | 83% | 95 | 16 | `cmd_soilgrids_hsg`: walidacja `--geometry`/`--bbox` 94-112 i finalny `except Exception` 164-171 — sciezki bledow CLI |
| `kartograf/cli/download_cmd.py` | 87% | 616 | 81 | **Realne**: sekwencyjny `_download_godlo_list` 652-663 (A8-5), skrot CRS w `_resolve_cz_geometry_bbox` 459 + jego blad 461-466 (A8-6), `_dispatch_area` `TransformError` 408-409, `_fetch` LAZ skip/fail 970-976, raport bledow LAZ 1003-1006. Reszta to `print()` w galeziach bledu |
| `kartograf/transport/http.py` | 89% | 37 | 4 | 63-66: sprzatanie `.tmp` w galezi `except Exception` (nie-`RequestException`) — brzegowe |
| `kartograf/core/geometry.py` | 91% | 148 | 14 | Sciezki bledow parsowania SHP/GPKG (111-115, 215-219) — brzegowe |
| `kartograf/providers/pl/bdot10k.py` | 92% | 227 | 19 | Sciezki bledow ZIP/GPKG (446-455, 549-552, 656-659) — brzegowe |
| `kartograf/cli/commands.py` | 92% | 26 | 2 | 104-105: entry point `main` — trywialne |
| `kartograf/cli/landcover_cmd.py` | 93% | 140 | 10 | Galezie bledow CLI — brzegowe |
| `kartograf/transform/crs.py` | 93% | 88 | 6 | 98/100-101 (`REMEDIES` lookup), 191-193 (`unavailable_operations` w komunikacie) — brzegowe |
| `kartograf/cli/cache_cmd.py` | 94% | 32 | 2 | 47/60 — trywialne |
| `kartograf/download/storage.py` | 94% | 96 | 6 | 89/111 (walidacja), 307-311 (`list_files`) — brzegowe |
| `kartograf/providers/cuzk/client.py` | 95% | 151 | 8 | 81-82, 240-242, 328-330 — galezie bledow ArcGIS, brzegowe |
| `kartograf/core/parser_registry.py` | 95% | 57 | 3 | Trywialne |
| `kartograf/providers/pl/gugik_laz.py` | 95% | 224 | 11 | 368-370/583-586 — galezie bledow WFS, brzegowe |
| `kartograf/auth/client.py` | 95% | 124 | 6 | 198-199/247-248/292-293 — obsluga bledow proxy, brzegowe |
| `kartograf/download/manager.py` | 95% | 187 | 9 | 487-504 — jedna galaz `download_bbox`; brzegowe |
| `kartograf/providers/pl/gugik_orto.py` | 96% | 179 | 8 | Brzegowe |
| `kartograf/landcover/manager.py` | 96% | 139 | 6 | Brzegowe |
| `kartograf/providers/pl/gugik.py` | 96% | 229 | 9 | 479/489/541-543/779-782 — brzegowe |
| `kartograf/core/parser_2000.py` | 96% | 251 | 9 | Trywialne/brzegowe |
| `kartograf/providers/cuzk/sheets.py` | 98% | 122 | 3 | Trywialne |
| `kartograf/core/parser_tm33.py` | 98% | 47 | 1 | Trywialne |
| `kartograf/hydrology/hsg.py` | 98% | 157 | 3 | 138/142/169 — walidacje, trywialne |
| `kartograf/core/sheet_parser.py` | 98% | 382 | 6 | Trywialne |
| `kartograf/cache/metadata.py` | 100% | 137 | 0 | — |
| `kartograf/cli/_parser.py` | 100% | 65 | 0 | — |
| `kartograf/cli/parse_cmd.py` | 100% | 64 | 0 | — |
| `kartograf/exceptions.py` | 100% | 11 | 0 | — |
| `kartograf/providers/cuzk/dmr.py` | 100% | 237 | 0 | — |
| `kartograf/providers/pl/gugik_nmpt.py` | 100% | 15 | 0 | — |
| `kartograf/sources/descriptor.py` | 100% | 54 | 0 | — |
| `kartograf/sources/registry.py` | 100% | 39 | 0 | — |
| `kartograf/sources/sidecar.py` | 100% | 68 | 0 | — |
| `kartograf/transport/mosaic.py` | 100% | 27 | 0 | — |
| **TOTAL** | **89,53%** | **5216** | **546** | prog `fail_under = 60` spelniony; progi warstwowe z DEVELOPMENT_STANDARDS 10.1 — nie (A8-7) |

Pliki `__init__.py` (poza pomiarem przez `omit`): zmierzone osobno — wszystkie **100%**, w tym `providers/pl/__init__.py` (14 stmts) i `providers/cuzk/__init__.py` (11 stmts).

## Inwentarz skip/xfail

Statycznych `skipif`, `xfail`, `importorskip` w `tests/` **nie ma** (grep: 0 trafien). Jedyny mechanizm pomijania:

| Lokalizacja | Rodzaj | Powod (dosl.) | Ile testow | Ocena |
|---|---|---|---|---|
| `tests/test_pl2000_verification.py:482` | `pytest.skip` w runtime, wewnatrz `except (ConnectionError, Timeout, RequestException)` | `f"WMS not reachable: {e}"` | 8 (parametryzacja `LIVE_WMS_SHEETS`: 5.176.14, 5.180.10, 6.179.12, 6.175.15, 6.185.20, 7.170.12, 7.180.8, 8.170.10) | Klasa oznaczona `@pytest.mark.live`, ale marker nie jest odfiltrowany w `addopts` — przy dostepnej sieci testy **wykonuja sie** (przebieg dal `1402 passed, 0 skipped`), offline daja `8 skipped`. `except` obejmuje `RequestException`, wiec takze HTTP 5xx konczy sie `skip` zamiast `fail`. Patrz A8-8 |

Testy siegajace do sieci mimo braku markera `live` (nie sa "skip", ale naleza do tego samego problemu) — 21 sztuk, wylistowane w A8-1.

## Pozytywy (max 5)

1. **Poprawka ADR-024 jest twardo przypieta.** Regresja do serwerowej reprojekcji (`imageSR=bbox.crs` zamiast wymuszonego `NATIVE_CRS` + lokalny warp) wywala **9 testow** w `tests/test_cuzk_dmr.py` (m.in. `test_warp_forces_the_pinned_operation`, `test_nodata_does_not_bleed_into_interpolation`, `test_target_crs_produces_target_grid_from_native_request`). To najlepiej zabezpieczony fragment etapu 1.
2. **Sidecary i polityka transformacji sa realnie testowane.** Wylaczenie zapisu sidecara w `DownloadManager` psuje 4 testy, usuniecie kasowania sidecara w `FileStorage.delete()` psuje 1, `allow_ballpark=True` psuje `test_ballpark_disabled_in_group_construction`. `tests/test_transform_crs.py` sprawdza takze przywracanie **globalnego** stanu sieci PROJ (`test_network_state_restored`, `test_probe_runs_under_policy_network_context`) — dokladnie tam, gdzie latwo o wyciek stanu miedzy testami.
3. **Fixtury CUZK to realne odpowiedzi serwera.** Wszystkie 6 plikow w `tests/fixtures/cuzk/` niesie sygnatury zywego ArcGIS REST (`"currentVersion":11.5`, `"cimVersion":"3.5.0"`, `falseX/falseY`, `wkid:102067/latestWkid:5514`), a nie recznie zmyslone struktury. `tests/test_cuzk_sheets.py` laduje je przez helper (`FIXTURES = Path(__file__).parent / ...`), `tests/test_cuzk_client.py:139` ma dedykowany `test_real_fixture_shape_parses`. `tests/test_cuzk_dmr.py` uzywa wartosci **wyprowadzonych** z fixtury (CTES96: PODIL 0.99, zasieg 5514) i uczciwie to dokumentuje w docstringu modulu.
4. **Brak duplikatow i brak zaleznosci od kolejnosci.** Analiza AST: **0** par testow o identycznym ciele; powtarzajace sie nazwy (`test_repr`, `test_str`, `test_supported_formats`) to rownolegla struktura roznych klas, nie kopie. Przebieg w odwroconej kolejnosci plikow: `1394 passed, 8 skipped` — bez zmian. Stan globalny jest resetowany tam, gdzie trzeba (autouse `reset_singleton` dla `AuthProxyClient`, `_isolate_cache` z `monkeypatch.chdir` w 4 klasach CZ w `test_cli.py`, ``_validated_layers`` jako pole instancji, nie klasy).
5. **Kilka testow jest napisanych wzorcowo — z jawnym dowodem, a nie samym `assert called`.** `tests/test_cli.py:2141,2165` uzywaja spy `patch.object(..., wraps=...)` i asercjonuja jednoczesnie `pinned.called` **oraz** `plain.assert_not_called()` (dowod, ze uzyto przypietej operacji, a nie ballparku). `tests/test_sidecar.py` wprost komentuje wlasne slabe miejsca (`"ta asercja sama w sobie nie dowodzi poprawnej selekcji"`) i doklada mocniejszy test obok.

## Podsumowanie liczbowe: C=0 I=7 M=7
