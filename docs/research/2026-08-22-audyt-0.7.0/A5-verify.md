# A5-verify — weryfikacja ustalen raportu A5 (jakosc, duplikaty, martwy kod)

Weryfikator: V5. Galaz: `fix/release-0.7.0-audit`. Bez sieci, bez modyfikacji repo.
Wszystkie snippety uruchomione w `.venv/bin/python`.

---

### A5-1 — Caly blok obslugi credentials CLMS w `corine.py` jest martwy; udokumentowana zmienna `CLMS_CREDENTIALS` nie dziala
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ grep -rn "CLMS_CREDENTIALS" kartograf/ --include='*.py'
  kartograf/providers/corine.py:212:    creds_env = os.environ.get("CLMS_CREDENTIALS")   # jedyne miejsce w pakiecie

  $ CLMS_CREDENTIALS='{"client_id":"x","private_key":"y","token_uri":"z"}' .venv/bin/python -c ...
  CLI-path CorineProvider(): use_proxy= True  clms_auth= None
  get_clms_credentials() (nikt nie wola): {'client_id': 'x', ...}
  jawnie przekazane:        use_proxy= False clms_auth= CLMSAuth
  ```
  Pelna sciezka przesledzona: `cli/landcover_cmd.py`:86 `CorineProvider()` (bez credentials)
  -> `corine.py`:431 `_use_proxy = True` -> `_get_auth_proxy()` -> `auth/client.py`:86
  `subprocess.Popen([sys.executable, "-m", "kartograf.auth.proxy", ...])` **bez `env=`**
  (czyli env JEST dziedziczony) -> `auth/proxy.py`:52 `CLMSCredentials.load_from_keychain()`,
  ktory zaczyna od `if platform.system() != "Darwin": return False` i **nie ma ani jednego
  `os.environ`** (`grep os.environ kartograf/auth/` = 0 trafien).
- Uzasadnienie: rozroznienie, o ktore prosil brief — (a) BLOK w `corine.py`:67-227 jest martwy
  (`get_clms_credentials`/`save_credentials_to_keychain` = 0 wywolan, `get_credentials_from_keychain`
  wolane wylacznie z martwego `get_clms_credentials`); (b) FUNKCJA "CORINE jako GeoTIFF" **dziala**,
  ale tylko dwiema drogami: macOS Keychain przez proxy (ADR-002) albo jawne
  `CorineProvider(clms_credentials={...})` z biblioteki (`CLMSAuth` jest zywe: `corine.py`:432, 442).
  Zmienna `CLMS_CREDENTIALS` nie dziala nigdzie — jest w env subprocessu, ale nikt jej tam nie czyta.
  ADR-002 mowi wprost "Credentials pobierane z macOS Keychain", wiec zachowanie jest zgodne z ADR,
  a `README.md`:190 i `CLAUDE.md`:26 (oraz `CLAUDE.md` "Zmienne srodowiskowe") po prostu klamia.
  Severity Critical utrzymane: naruszony udokumentowany kontrakt CLI/README na non-macOS.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `README.md`:186-200 i `CLAUDE.md`:24-28 — usunac `CLMS_CREDENTIALS` z instrukcji,
  napisac wprost: "CORINE GeoTIFF wymaga macOS + Keychain (`security add-generic-password -s clms-token`)
  albo jawnego `CorineProvider(clms_credentials=...)` z poziomu biblioteki; na Linux/Windows bez
  jawnych credentials dziala tylko fallback WMS/PNG". Usuniecie martwego bloku `corine.py`:67-227
  (bez `CLMSAuth`) jest bezpieczne i opisane w sekcji "Martwy kod — potwierdzony", ale
  **nie mozna** go zrobic bez rownoczesnej korekty README (blok jest jedynym czytelnikiem env).
  Podpiecie `get_clms_credentials()` pod `CorineProvider.__init__` odradzam przed 0.7.0: wlaczyloby
  tryb direct z pominieciem izolacji z ADR-002 i wymaga zywego testu CLMS (brak sieci).
  Test przypinajacy: nowy `test_landcover.py::test_env_var_nie_wlacza_geotiff` (monkeypatch env ->
  `CorineProvider()._use_proxy is True`), S (<30 linii), ryzyko regresji: niskie.

---

### A5-2 — `LandCoverManager.download()` i `download_by_*()` generuja rozne nazwy plikow (jedna ze spacjami)
- Werdykt: CONFIRMED
- Reprodukcja (mock providera, `_write_sidecar` wylaczony):
  ```
  download(godlo=)      -> out/corine_land_cover_godlo_N-34-130-D.gpkg
  download_by_godlo()   -> out/CORINE Land Cover_N-34-130-D.gpkg
  download(teryt=)      -> out/corine_land_cover_teryt_1465.gpkg
  download_by_teryt()   -> out/CORINE Land Cover_1465.gpkg
  download(bbox=)       -> out/corine_land_cover_bbox_500000_300000_510000_310000.gpkg
  download_by_bbox()    -> out/CORINE Land Cover_bbox_500000_300000_510000_310000.gpkg
  ```
- Uzasadnienie: potwierdzone dla wszystkich trzech trybow, nie tylko godla. Obie sciezki sa publiczne
  (`LandCoverManager` w `kartograf/__all__`, `download_by_*` udokumentowane w `docs/CHANGELOG.md`:643).
  CLI uzywa wylacznie `download()` (`landcover_cmd.py`:181-192), wiec uzytkownik CLI tego nie zobaczy —
  dotyka to konsumentow biblioteki (Hydrograf/Hydrolog). Nazwa ze spacjami to realny problem
  przenoszalnosci (URL/skrypty shell), nie tylko kosmetyka.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/landcover/manager.py`:241, :274, :311 — zastapic trzy inline'owe
  konstrukcje wywolaniem `self._generate_output_path(teryt, bbox, godlo)` (usuwa ~10 linii,
  `_generate_output_path` zostaje jedynym miejscem regul). Przypina to istniejacy
  `tests/test_landcover.py::test_download_by_bbox_auto_path` i `::test_download_by_godlo_auto_path`;
  **wymaga poprawki jednej asercji**: `test_download_by_teryt_auto_path`:872 sprawdza
  `assert "TestProv" in str(auto_path)`, a po normalizacji bedzie `testprov` — zmienic na
  `assert "testprov" in str(auto_path).lower()`. Dopisac wpis BREAKING w `docs/CHANGELOG.md`
  (zmiana domyslnych nazw plikow `download_by_*`). S (<30 linii), ryzyko regresji: niskie.

---

### A5-3 — Kanoniczny downloader `transport.download_to` jest uzywany tylko przez CZ; 6 providerow ma wlasne kopie z INNYM harmonogramem retry
- Werdykt: DESIGN-DECISION
- Reprodukcja:
  ```
  $ grep -rn "download_to(" --include='*.py' kartograf/
  kartograf/providers/cuzk/client.py:105, :110, :213   (3 wywolania, wszystkie CZ)

  $ sed -n '1,8p' kartograf/transport/http.py
  Kanoniczny downloader HTTP dla NOWEGO kodu (etap 1+).
  ...
  Istniejace providery maja wlasne, przetestowane implementacje tego wzorca
  i NIE sa przepinane w etapie 0.
  ```
  Spec etapu 0, sekcja 6.5 (`docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md`:422-434):
  "`http.py` — kanoniczny downloader dla **nowego** kodu (etap 1+). (...) Istniejace providery
  **nie sa** przepinane w etapie 0 (kazdy ma wlasna, przetestowana implementacje tego wzorca;
  ujednolicenie oportunistycznie pozniej)."
- Uzasadnienie: spec MOWI TO WPROST, a docstring modulu powtarza to slowo w slowo — audytor
  przeoczyl drugie zdanie docstringa i zaproponowal "usunac slowo kanoniczny" z dokumentu, ktory
  juz sam sie ogranicza do "nowego kodu (etap 1+)". Zarzut o backoff jest faktograficznie poprawny
  (kanoniczny: proby 0,1,2, czekanie 1 s i 2 s; kopie: proby 1,2,3, czekanie 2 s i 4 s — liczba prob
  identyczna, 3), ale to roznica w czasie oczekiwania, nie w wyniku. Zarzut o brak
  `mkdir(parents=True)` w kopiach jest **nietrafiony**: katalog tworza wywolujacy
  (`gugik.py`:410, :636, `gugik_laz.py`:513, `storage.py`:234, :286). ADR-022 dodatkowo odrzucil
  opcje C ("pelna ekstrakcja silnikow transportu juz teraz") z uzasadnieniem "ryzyko dla ~1060 testow
  bez zysku". `docs/PROGRESS.md` ("Nastepne kroki" / "Backlog") tego odroczenia NIE odnotowuje.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/PROGRESS.md` sekcja "Backlog" — jedna pozycja:
  "[ ] Ujednolicenie transportu: przepiecie `_download_with_retry`/`_save_response` 6 providerow PL/EU
  na `transport.download_to` (odroczone w etapie 0, spec 6.5; skutek uboczny: wyrownanie backoffu 2/4 s -> 1/2 s)".
  Zadnych zmian w kodzie. S, ryzyko regresji: brak.

---

### A5-4 — Regula "5m => EVRF2007" zyje w TRZECH miejscach, a trzecie zachowuje sie inaczej
- Werdykt: DESIGN-DECISION
- Reprodukcja:
  ```
  GugikProvider(resolution='5m', vertical_crs='KRON86')       -> ValueError | KartografError? False
  create_nmt_provider(resolution='5m', vertical_crs='KRON86') -> 5m EVRF2007
  DownloadManager(resolution='5m', vertical_crs='KRON86')     -> 5m EVRF2007 | provider: EVRF2007
  ```
  Trzy lokalizacje potwierdzone: `download/manager.py`:175-181, `providers/pl/__init__.py`:35-41
  (bajtowo ten sam blok + warning), `providers/pl/gugik.py`:194-201 (`raise ValueError`).
- Uzasadnienie: oba zachowania sa udokumentowane w `docs/CHANGELOG.md` (v0.5.x, l. 533-538):
  "Automatyczna walidacja: 5m wymaga EVRF2007" dla `GugikProvider` **oraz**
  "`DownloadManager(resolution='5m')` - automatycznie wymusza EVRF2007". Docstring
  `create_nmt_provider` ("Egzekwuje regule 5m => EVRF2007 (identycznie jak DownloadManager)")
  jest prawdziwy — fabryka faktycznie jest identyczna z managerem. To nie jest rozjazd trzech kopii
  jednej reguly, tylko warstwowanie: normalizacja na brzegu (fabryka/manager) + twarda walidacja
  argumentow w rdzeniu (konstruktor providera). Zadna sciezka CLI ani biblioteczna nie daje
  zlego wyniku: CLI dla `--product nmt` idzie przez `create_nmt_provider`
  (`download_cmd.py`:82), a `--product nmpt/orto` nie ma 5m. Jedyna realna wada to typ wyjatku
  (`ValueError` zamiast `ValidationError`) — to jest A5-5, nie A5-4.
- Naprawa przed wydaniem 0.7.0: NIE (odlozyc)
- Zakres naprawy: nie dotyczy. Usuwanie kopii z `DownloadManager.__init__` przed wydaniem daloby
  regresje dla uzytkownikow konstruujacych manager z wlasnym providerem (manager przestalby korygowac),
  a zysk jest zerowy.

---

### A5-5 — Rozjechana hierarchia wyjatkow: providery PL i rejestry rzucaja surowe `ValueError`/`KeyError`
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  ValidationError MRO: ['ValidationError', 'KartografError', 'Exception', 'BaseException', 'object']
  try: GugikProvider(resolution='5m', vertical_crs='KRON86')
  except KartografError: ...
  -> NIE KartografError -> ValueError: Resolution 5m is only available for EVRF2007, got vertical_c...

  $ grep -rn "raise ValueError" --include='*.py' kartograf/ | awk -F: '{print $1}' | sort | uniq -c
  37 wystapien w 14 plikach (gugik.py 8, soilgrids.py 4, gugik_laz.py 4, gugik_orto.py 3, ...)
  $ sed -n '189,192p' kartograf/providers/pl/bdot10k.py
  raise ValidationError(f"Invalid TERYT code: {code}")
  raise ValueError(f"Unsupported format: {format}. Use 'GPKG' or 'SHP'")   # sasiednie linie, dwa typy
  ```
- Uzasadnienie: fakt kodowy potwierdzony, obietnica z `kartograf/exceptions.py`:14-15
  ("All custom exceptions in this package inherit from this class, allowing users to catch all
  Kartograf-specific errors with a single except clause") jest w praktyce mylaca dla ~37 sciezek
  walidacyjnych. ALE to zmiana hierarchii wyjatkow publicznego API, ktora regula weryfikacji
  wprost kwalifikuje jako "odlozyc": `ValidationError` NIE dziedziczy po `ValueError`, wiec kod
  konsumenta lapiacy `ValueError` przestanie dzialac, `docs/CHANGELOG.md`:534 dokumentuje
  `ValueError` jako kontrakt (`download_bbox()` dla 5m), a w `tests/` jest **30 asercji
  `pytest.raises(ValueError)` w 11 plikach**, ktore trzeba by przepisac.
- Naprawa przed wydaniem 0.7.0: NIE (odlozyc)
- Zakres naprawy: nie dotyczy 0.7.0. Do zaplanowania jako osobna zmiana BREAKING (najlepiej z
  przejsciowym `class ValidationError(KartografError, ValueError)`, ktory pozwala migrowac bez
  zrywania konsumentow) + wpis w `docs/DEVELOPMENT_STANDARDS.md` 11.1 o statusie `KeyError`
  w `sources/registry.py`.

---

### A5-6 — Polityka "zero ballpark" z `transform/crs.py` obowiazuje tylko sciezke CZ (9 miejsc uzywa `Transformer.from_crs`)
- Werdykt: DESIGN-DECISION
- Reprodukcja:
  ```
  $ grep -rn "Transformer.from_crs\|build_pinned_transform" --include='*.py' kartograf/
  9x from_crs (geometry.py:359, sheet_parser.py:635,:864, parser_2000.py:597,:694,:732,
               corine.py:1007,:1025, soilgrids.py:267)  vs  2x build_pinned_transform (cuzk/dmr.py)

  # ballpark realnie wpuszczany przez core/geometry.py:
  TransformerGroup(EPSG:4314 -> 2180, allow_ballpark=False) operacje: 0
  from_crs desc: ... + Ballpark geographic offset from DHDN to ETRF2000-PL + Poland CS92 + ...
  _transform_bbox(...) -> BBox(min_x=156955.76, min_y=468872.43, ...)   # wynik BEZ bledu

  # ale dla CRS-ow realnie wystepujacych u uzytkownikow Kartografa:
  EPSG:5514 -> 2180  ops_bez_ballpark=7  ballpark_w_from_crs=False
  EPSG:4326/2177/3045/32633/4258 -> 2180  ballpark_w_from_crs=False
  ```
- Uzasadnienie: spec etapu 0, sekcja "Nie wchodzi (jawnie poza zakresem)" (l. 149-151) mowi wprost:
  "migracja istniejacych wywolan pyproj (soilgrids, parser_2000, geometry) na `transform/crs.py`
  — zostaja jak sa, migracja oportunistyczna pozniej". To swiadome odroczenie, nie przeoczenie.
  Dodatkowo obniżam ocene realnego ryzyka: 8 z 9 wywolan to zaszyte pary wewnatrz-PL
  (2180<->4326/3857, strefy PL-2000), a jedyne wywolanie z CRS uzytkownika (`geometry.py`:359)
  wpuszcza ballpark **tylko dla egzotycznych datow historycznych** (DHDN, Stereo70) — dla wszystkich
  ukladow realnie uzywanych w PL/CZ, wlacznie z czeskim Krovakiem 5514 dodanym w etapie 1,
  `from_crs` NIE zwraca ballparku (sprawdzone wyzej). Blad rzedu 100-200 m przy arkuszu 1:10000
  o boku ~5,5 km moze przesunac wybor godla tylko przy krawedzi. `docs/PROGRESS.md`
  ("Nastepne kroki"/"Backlog") tego odroczenia nie odnotowuje, a docstring `transform/crs.py`:6
  ("Transformer budowany WYLACZNIE przez TransformerGroup") czyta sie jak deklaracja o zasiegu
  calego pakietu.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: (1) `kartograf/transform/crs.py`:2-4 — dopisac do naglowka jedno zdanie:
  "Polityka obowiazuje NOWY kod (etap 1+); migracja istniejacych wywolan pyproj w
  `core/geometry.py`, `core/sheet_parser.py`, `core/parser_2000.py`, `providers/corine.py`,
  `providers/soilgrids.py` odroczona (spec etapu 0, sekcja 'Nie wchodzi')".
  (2) `docs/PROGRESS.md` "Backlog" — pozycja: "[ ] `core/geometry.py:_transform_bbox` na
  `build_pinned_transform` (CRS z pliku uzytkownika; dzis mozliwy cichy ballpark dla obcych datow
  typu DHDN/Stereo70)". Bez zmian w logice. S, ryzyko regresji: brak.

---

### A5-7 — `GugikLazProvider.download(url, ...)` lamie kontrakt `BaseProvider.download(godlo, ...)`
- Werdykt: DOWNGRADE(Minor)
- Reprodukcja:
  ```
  $ .venv/bin/python -c "inspect.signature(...)"
  BaseProvider         (self, godlo: str, output_path: Path, timeout: int = 30) -> Path
  GugikProvider        (self, godlo: str, output_path: Path, timeout: int = 30) -> Path
  GugikNmptProvider    (self, godlo: str, output_path: Path, timeout: int = 30) -> Path
  GugikOrtoProvider    (self, godlo: str, output_path: Path, timeout: int = 60) -> Path
  GugikLazProvider     (self, url:   str, output_path: Path, timeout: int = 60) -> Path
  CuzkDmrProvider      (self, godlo: str, output_path: Path, timeout: int = 60) -> Path
  LAZ jest BaseProvider? True

  # wymuszone uzycie polimorficzne (DownloadManager + GugikLazProvider):
  WYNIK: DownloadError | Failed to download N-34-130-D-d-2-4.laz after 3 attempts:
         Invalid URL 'N-34-130-D-d-2-4': No scheme supplied.
  ```
- Uzasadnienie: naruszenie LSP jest realne, ale audytor sam odnotowal, ze zadna sciezka
  produkcyjna go nie wyzwala — i to potwierdzilem: `cmd_download` przechwytuje LAZ **przed**
  jakimkolwiek `DownloadManager` (`download_cmd.py`:529-530 `if product == "laz": return
  _cmd_download_laz(args)`), a `_cmd_download_laz`:972 wola `provider.download(tile.url, target)`
  swiadomie. Wymuszone uzycie polimorficzne nie daje cichego zlego wyniku, tylko **glosny**
  `DownloadError` z diagnostycznym komunikatem po ~6 s retry. Docstring metody (`gugik_laz.py`:485-491)
  ostrzega o roznicy wprost. To pasuje do definicji Minor ("nazewnictwo / kontrakt bez skutku"),
  nie Important ("blad na sciezce brzegowej").
- Naprawa przed wydaniem 0.7.0: NIE (odlozyc)
- Zakres naprawy: nie dotyczy. Proponowana przez audytora zmiana nazwy na `download_tile` jest
  BREAKING dla `kartograf.GugikLazProvider` (klasa w `kartograf/__all__`, `download` uzywane
  w `download_cmd.py`:972 i w testach `test_gugik_laz.py`) — do rozwazenia razem z etapem 2 CZ LAZ.

---

### A5-8 — `docs/PRD.md` sekcja 5 "Public API" nie odpowiada faktycznym eksportom v0.7.0
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ .venv/bin/python (diff listy z PRD vs kartograf.__all__)
  W __all__ ale brak w PRD: ['CuzkDmrProvider', 'ParserTM33', 'create_dmr_provider']
  liczba __all__: 31
  $ grep -n '__version__' docs/PRD.md
  538:    __version__,  # "0.6.1"      vs   kartograf/__init__.py:51  __version__ = "0.7.0-dev"
  ```
- Uzasadnienie: porownanie tekst-vs-kod wykonane maszynowo; PRD gubi dokladnie trzy eksporty
  etapu 1 i podaje wersje starsza o dwa wydania. Sam `__all__` jest w 100% spojny z modulem
  (zero nazw bez atrybutu, zero publicznych nazw poza `__all__`) — blad jest wylacznie w PRD.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/PRD.md`:495-540 — dopisac `ParserTM33` do bloku "# Core",
  `CuzkDmrProvider` i `create_dmr_provider` do bloku "# Providers", zmienic komentarz
  `# "0.6.1"` na `# "0.7.0"`; naglowek "# Download (NMT/NMPT/Orto)" uzupelnic o LAZ.
  Nic tego nie przypina testem — rozwazyc zastapienie listy odsylaczem do `kartograf/__init__.py`
  (tak zrobil `README.md`:107-110). S, ryzyko regresji: brak.

---

## Tabela

| ID | Werdykt | Naprawa 0.7.0 | Rozmiar | Ryzyko |
|---|---|---|---|---|
| A5-1 | CONFIRMED | DOCS-ONLY | S | niskie |
| A5-2 | CONFIRMED | TAK | S | niskie |
| A5-3 | DESIGN-DECISION | DOCS-ONLY | S | brak |
| A5-4 | DESIGN-DECISION | NIE (odlozyc) | — | — |
| A5-5 | CONFIRMED | NIE (odlozyc) | — | — |
| A5-6 | DESIGN-DECISION | DOCS-ONLY | S | brak |
| A5-7 | DOWNGRADE(Minor) | NIE (odlozyc) | — | — |
| A5-8 | CONFIRMED | DOCS-ONLY | S | brak |

---

## Martwy kod — potwierdzony

Kazda pozycja zweryfikowana `grep -rn "\b<NAZWA>\b"` po `kartograf/` + `tests/` + `README.md` + `docs/`
oraz sprawdzona wzgledem `kartograf/__init__.py::__all__` (zadna z ponizszych nazw tam nie wystepuje).
**15 martwych symboli + 2 martwe fragmenty kodu = 17 pozycji do usuniecia.**

### Symbole (15)

| # | Symbol | Plik:linia | Dowod |
|---|---|---|---|
| 1 | `KEYCHAIN_SERVICE` | `kartograf/providers/corine.py`:67 | 4 uzycia, wszystkie w martwych funkcjach 2-4 ponizej; zywa, niezalezna kopia jest w `auth/proxy.py`:41 |
| 2 | `get_credentials_from_keychain` | `kartograf/providers/corine.py`:70 | 2 trafienia: definicja + wywolanie z martwego `get_clms_credentials`:222 |
| 3 | `save_credentials_to_keychain` | `kartograf/providers/corine.py`:132 | 1 trafienie (sama definicja) |
| 4 | `get_clms_credentials` | `kartograf/providers/corine.py`:196 | 1 trafienie (sama definicja); jedyny czytelnik `CLMS_CREDENTIALS` w calym repo |
| 5 | `TEXTURE_NAMES` | `kartograf/hydrology/hsg.py`:46 | 1 trafienie; brak w `kartograf/hydrology/__init__.py` (tam tylko `TEXTURE_CLASSES`) |
| 6 | `DLR_YEARS` | `kartograf/providers/corine.py`:387 | 2 trafienia: definicja + komentarz `landcover/manager.py`:442; realna decyzja to `corine.py`:922 `if year in self.EEA_YEARS` |
| 7 | re-eksport `_cmd_download_bbox` | `kartograf/cli/commands.py`:15 (+`__all__`:59) | 0 uzyc w `tests/`, 0 poza fasada |
| 8 | re-eksport `_cmd_download_geometry` | `kartograf/cli/commands.py`:16 (+`__all__`:61) | 0 uzyc w `tests/` |
| 9 | re-eksport `_cmd_download_laz` | `kartograf/cli/commands.py`:17 (+`__all__`:60) | 0 uzyc w `tests/` |
| 10 | re-eksport `_download_godlo_list` | `kartograf/cli/commands.py`:19 (+`__all__`:58) | 0 uzyc w `tests/` |
| 11 | re-eksport `_write_laz_sidecar` | `kartograf/cli/commands.py`:22 (+`__all__`:62) | 0 uzyc w `tests/` |
| 12 | re-eksport `cmd_landcover_download` | `kartograf/cli/commands.py`:27 (+`__all__`:45) | 0 uzyc w `tests/` |
| 13 | re-eksport `cmd_landcover_list_layers` | `kartograf/cli/commands.py`:28 (+`__all__`:46) | 0 uzyc w `tests/` |
| 14 | re-eksport `cmd_landcover_list_sources` | `kartograf/cli/commands.py`:29 (+`__all__`:47) | 0 uzyc w `tests/` |
| 15 | re-eksport `cmd_soilgrids_hsg` | `kartograf/cli/commands.py`:37 (+`__all__`:49) | 0 uzyc w `tests/` |

Fasada musi zachowac: `main`, `create_parser` (54 uzycia w testach), `format_sheet_info` (12),
`format_hierarchy`, `format_children`, `format_descendants`, `create_progress_callback` (8),
`_create_provider_and_storage` (13), `_resolve_laz_bbox` (11), `cmd_parse`, `cmd_download`,
`cmd_landcover`, `cmd_soilgrids`, `cmd_cache` — potwierdzone
`grep -rn "from kartograf.cli.commands import" tests/`.

### Fragmenty kodu (2)

| # | Co | Plik:linia | Dowod |
|---|---|---|---|
| 16 | fallback `getattr(args, "vertical_crs", "KRON86")` — 3 kopie | `kartograf/cli/download_cmd.py`:550, :757, :1381 | `_parser.py`:138-140 ustawia `default=None`, wiec argparse ZAWSZE tworzy atrybut (`hasattr(a,'vertical_crs') == True`, `a.vertical_crs is None`) — trzeci argument `getattr` jest nieosiagalny; dodatkowo `_resolve_pl_sentinels`:120 ustawia `EVRF2007` przed kazdym z trzech miejsc |
| 17 | galaz `elif product == "laz":` (provider+storage dla LAZ) | `kartograf/cli/download_cmd.py`:74-78 | patrz "Nowe ustalenia" nr 1 |

### Korekta inwentarza raportu A5

Raport A5 (sekcja "Aliasy zgodnosciowe", `A5-report.md`:389) twierdzi, ze
`LandCoverProvider.validate_teryt` (`providers/base.py`:403) ma "tylko testy (11 wystapien),
zero uzyc produkcyjnych". To **nieprawda**: `kartograf/providers/soilgrids.py`:414 zawiera
`if not self.validate_teryt(teryt):`. Symbol jest zywy — nie usuwac.
Pozostale pozycje list "uzywane wylacznie przez testy" i "nie sa martwe mimo trafienia vulture"
zweryfikowalem grepem i sa poprawne.

---

## Nowe ustalenia przy okazji (max 3, tylko jesli Critical/Important i z dowodem)

### N5-1 [Important] Galaz `product == "laz"` w `_create_provider_and_storage` jest nieosiagalna i nieprzetestowana — martwy kod udajacy aktywny
- Plik: `kartograf/cli/download_cmd.py`:74-78 (galaz) vs :529-530 (short-circuit)
- Dowod:
  ```python
  # download_cmd.py:529 — cmd_download przechwytuje LAZ ZANIM powstanie provider/storage
  if product == "laz":
      return _cmd_download_laz(args)
  # ...dopiero potem, w trzech miejscach:
  # :556 (godlo), :762 (_download_pl_bbox), :1386 (_download_pl_geometry)
  provider, storage = _create_provider_and_storage(product, output_dir, vertical_crs, resolution)
  # ...ktore obsluguja galaz nigdy nie osiagalna:
  elif product == "laz":                                    # :74
      provider = GugikLazProvider(vertical_crs=vertical_crs)
      storage = FileStorage(output_dir, product="laz")
  ```
- Weryfikacja: `_download_pl_bbox`/`_download_pl_geometry` sa wolane wylacznie z
  `_cmd_download_bbox`:723 / `_cmd_download_geometry` -> `_dispatch_area`:418, :421, a te z
  `cmd_download`:534, :538 — wszystkie **za** short-circuitem `product == "laz"` z :529.
  `grep -rn "_create_provider_and_storage(" tests/ | grep -i laz` -> 0 trafien (trzy testy w
  `test_cli.py`:774-800 pokrywaja `nmt`/`nmpt`/`orto`). Skutek: galaz sugeruje, ze LAZ przechodzi
  przez `DownloadManager`, a nie przechodzi — i jest zrodlem falszywego wrazenia, ze
  `GugikLazProvider` jest uzywany polimorficznie (patrz A5-7).
- Proponowana naprawa: usunac galaz `elif product == "laz"` (5 linii) i dopisac w docstringu
  `_create_provider_and_storage` "LAZ ma osobny przeplyw `_cmd_download_laz`"; ewentualnie
  zamienic na `raise ValidationError`. S, ryzyko regresji: niskie (zaden test tego nie dotyka).
