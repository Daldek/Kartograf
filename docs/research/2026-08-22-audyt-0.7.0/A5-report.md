# A5 — jakosc, spojnosc, duplikaty i martwy kod w pakiecie `kartograf/`

Zakres: przeczytane w calosci — `kartograf/__init__.py`, `kartograf/transport/http.py`,
`kartograf/sources/sidecar.py`, `kartograf/providers/pl/__init__.py`,
`kartograf/providers/pl/gugik_nmpt.py`, `kartograf/cli/commands.py`.
Przeczytane w istotnych fragmentach (wszystkie miejsca, ktorych dotycza ustalenia):
`kartograf/cli/download_cmd.py` (1432 l.), `kartograf/providers/corine.py` (1208 l.),
`kartograf/providers/soilgrids.py`, `kartograf/providers/pl/gugik.py`,
`kartograf/providers/pl/gugik_orto.py`, `kartograf/providers/pl/gugik_laz.py`,
`kartograf/providers/pl/bdot10k.py`, `kartograf/providers/cuzk/{client,sheets,dmr}.py`,
`kartograf/providers/base.py`, `kartograf/download/{manager,storage}.py`,
`kartograf/landcover/manager.py`, `kartograf/core/{sheet_parser,parser_2000,parser_tm33,parser_registry,geometry}.py`,
`kartograf/transform/crs.py`, `kartograf/auth/{proxy,client}.py`, `kartograf/hydrology/hsg.py`,
`kartograf/cache/metadata.py`, `kartograf/cli/{_parser,landcover_cmd,soilgrids_cmd,parse_cmd,cache_cmd}.py`.
Dokumenty odniesienia: `CLAUDE.md`, `docs/DEVELOPMENT_STANDARDS.md` (sekcje 4, 7, 8, 9, 11, 12),
`README.md`, `docs/PRD.md`.

Metoda:
- inwentarz AST wszystkich 514 definicji `def`/`class`/stalych UPPER_CASE na poziomie
  modulu + zliczenie wystapien kazdej nazwy w `kartograf/` i `tests/`
  (skrypt w scratchpadzie, `re.findall(r"\bNAZWA\b")` po wszystkich plikach `.py`);
- `.venv/bin/pip install vulture` + `.venv/bin/vulture kartograf/ --min-confidence 60`
  (49 trafien) oraz `--min-confidence 100` (0 trafien);
- `grep -rn --include=*.py` po repo (takze `--include=*.md`) dla weryfikacji kazdego
  kandydata na martwy kod;
- `diff -u` na wycietych blokach kodu dla potwierdzenia duplikatow;
- uruchomione snippety w `.venv/bin/python` (dowody w ustaleniach A5-1, A5-2, A5-4, A5-6);
- `.venv/bin/python -m ruff check kartograf/` (przechodzi), `-m mypy kartograf/` (33 bledy = baseline).

Nie sprawdzono:
- poprawnosci logicznej algorytmow (godla, bbox, transformacje, mozaikowanie) — obszar innych audytorow;
- `tests/` pod katem jakosci samych testow (uzywane tylko jako zrodlo wystapien nazw);
- zachowania na zywych endpointach (brak sieci; wszystkie dowody sa statyczne albo offline);
- plikow `docs/superpowers/**` (plany/specy historyczne) poza uzyciem ich jako kontekstu.

---

## Ustalenia

### A5-1 [Critical] Caly blok obslugi credentials CLMS w `corine.py` jest martwy — udokumentowana zmienna `CLMS_CREDENTIALS` nie dziala
- Plik: `kartograf/providers/corine.py`:67, :70, :132, :196 (blok ~160 linii); dokumentacja: `README.md`:190, `CLAUDE.md`:26
- Twierdzenie: jedyne miejsce w calym pakiecie, ktore czyta `os.environ["CLMS_CREDENTIALS"]`, to funkcja `get_clms_credentials()`, ktorej nikt nie wywoluje — udokumentowana w README sciezka konfiguracji CORINE GeoTIFF jest calkowicie nieaktywna, a poza macOS nie istnieje zadna dzialajaca alternatywa.
- Dowod:
  ```python
  # kartograf/providers/corine.py:196
  def get_clms_credentials() -> dict | None:
      ...
      creds_env = os.environ.get("CLMS_CREDENTIALS")   # l.212 — jedyne wystapienie w pakiecie
  ```
  ```
  README.md:190  "3. Zapisz credentials w zmiennej srodowiskowej `CLMS_CREDENTIALS` (JSON string ...)"
  ```
  `kartograf/auth/proxy.py` (jedyny zywy dostawca tokenu) nie zawiera ani jednego odwolania do `os.environ`; `CLMSCredentials.load_from_keychain()` zwraca `False` dla `platform.system() != "Darwin"`.
- Weryfikacja:
  - `grep -rn "get_clms_credentials\|save_credentials_to_keychain\|get_credentials_from_keychain\|CLMS_CREDENTIALS" --include='*.py' .` → wylacznie definicje w `corine.py` i jedno wywolanie `get_credentials_from_keychain()` **wewnatrz** martwego `get_clms_credentials()`; zero trafien w `tests/`;
  - uruchomione w `.venv/bin/python`:
    ```
    CLMS_CREDENTIALS='{"client_id":"x","private_key":"y","token_uri":"z"}' -> CorineProvider()
    use_proxy: True   clms_auth: None   has_clms_token: False
    ```
    czyli poprawnie ustawiona zmienna jest ignorowana i provider spada na podglad WMS/PNG.
- Proponowana naprawa: podpiac `get_clms_credentials()` w `CorineProvider.__init__` jako zrodlo `clms_credentials`, gdy nie podano ich jawnie (albo przekazac je do proxy przez `env` subprocessu), i usunac `save_credentials_to_keychain()` jako nieuzywany. Alternatywnie: usunac caly blok :67-:227 i skorygowac `README.md`:186-200 oraz `CLAUDE.md`:26, jasno pisząc, ze CORINE GeoTIFF dziala tylko na macOS z Keychainem.
- Pewnosc: wysoka

### A5-2 [Important] `LandCoverManager.download()` i `LandCoverManager.download_by_*()` generuja rozne nazwy plikow (jedna ze spacjami)
- Plik: `kartograf/landcover/manager.py`:194 i :398 vs :241, :274, :311
- Twierdzenie: te same zadanie wykonane przez dwie publiczne metody tej samej klasy (obie eksportowane przez `kartograf/__init__.py`) daje pliki o roznych nazwach — jedna sciezka normalizuje nazwe providera, druga wstawia do nazwy pliku surowe `provider.name` ze spacjami.
- Dowod:
  ```python
  # l.398 (uzywane przez download())
  provider_prefix = self._provider.name.lower().replace(" ", "_")
  filename = f"{provider_prefix}_godlo_{godlo}.gpkg"
  # l.311 (download_by_godlo())
  output_path = self._output_dir / f"{self._provider.name}_{godlo}.gpkg"
  ```
- Weryfikacja: uruchomione w `.venv/bin/python` (mock na `download_by_godlo` providera):
  ```
  m.download(godlo="N-34-130-D")      -> 'out/corine_land_cover_godlo_N-34-130-D.gpkg'
  m.download_by_godlo("N-34-130-D")   -> 'out/CORINE Land Cover_N-34-130-D.gpkg'
  ```
- Proponowana naprawa: `download_by_teryt`/`download_by_bbox`/`download_by_godlo` maja wolac `self._generate_output_path(...)` zamiast budowac nazwe inline (3x po 1-4 linie do usuniecia); `_generate_output_path` zostaje jedynym miejscem regul nazewnictwa.
- Pewnosc: wysoka

### A5-3 [Important] Kanoniczny downloader `transport.download_to` jest uzywany tylko przez CZ; 6 providerow ma wlasne kopie z INNYM harmonogramem retry
- Plik: `kartograf/transport/http.py`:42-57 vs `kartograf/providers/pl/gugik.py`:687, `.../gugik_orto.py`:477, `.../gugik_laz.py`:525, `.../bdot10k.py`:463, `kartograf/providers/corine.py`:1036, `kartograf/providers/soilgrids.py`:537 (+ 6 bajtowo identycznych `_save_response`)
- Twierdzenie: `transport/http.py` deklaruje sie jako "kanoniczny downloader", ale konsumuje go wylacznie `providers/cuzk/client.py`; szesc providerow trzyma wlasna kopie petli retry, ktora czeka **dwa razy dluzej** niz kanoniczna i uzywa innego prymitywu zapisu atomowego.
- Dowod:
  ```python
  # transport/http.py:42  -> proby 0,1,2 ; wait = 2**attempt = 1 s, 2 s ; os.replace()
  for attempt in range(retries):
      ...
      wait = RETRY_BACKOFF_BASE**attempt
  # providers/pl/gugik.py:720 (i 5 identycznych kopii) -> proby 1,2,3 ; wait = 2**attempt = 2 s, 4 s
  for attempt in range(1, self.MAX_RETRIES + 1):
      ...
      wait_time = self.RETRY_BACKOFF_BASE**attempt
  ```
  `_save_response` (gugik.py:763, gugik_orto.py:522, gugik_laz.py:567, bdot10k.py:533, corine.py:1107, soilgrids.py:608) to szesc bajtowo identycznych bloków 20-liniowych uzywajacych `temp_path.rename(output_path)`, podczas gdy kanoniczna wersja uzywa `os.replace()` i dodatkowo robi `output_path.parent.mkdir(parents=True, exist_ok=True)`.
- Weryfikacja: `grep -rn "download_to(" --include='*.py' kartograf/` → 3 wywolania, wszystkie w `providers/cuzk/client.py` (l.105, 110, 213); `sed`+`diff -u` na szesciu blokach `_save_response` → brak roznic poza nazwa pliku; odczyt wykladnikow petli.
- Proponowana naprawa: przepiac `_download_with_retry`/`_save_response` providerow na `transport.download_to` (podajac `session` i `timeout`), zostawiajac w providerach tylko budowanie URL; jesli przepiecie przed v0.7.0 jest za duze, zrownac przynajmniej harmonogram backoffu i zamienic `Path.rename` na `os.replace`, a z docstringa `transport/http.py` usunac slowo "kanoniczny".
- Pewnosc: wysoka

### A5-4 [Important] Regula "5m => EVRF2007" zyje w TRZECH miejscach, a trzecie zachowuje sie inaczej niz dwa pozostale
- Plik: `kartograf/download/manager.py`:175-181, `kartograf/providers/pl/__init__.py`:35-41, `kartograf/providers/pl/gugik.py`:194-201
- Twierdzenie: dokumentacja (`CLAUDE.md`, docstring fabryki) mowi o celowej redundancji w dwoch miejscach; faktycznie sa trzy, a `GugikProvider.__init__` **rzuca wyjatek** tam, gdzie manager i fabryka **cicho koryguja** wartosc — ta sama konfiguracja daje raz wyjatek, raz ostrzezenie.
- Dowod:
  ```python
  # providers/pl/__init__.py:35 i download/manager.py:175 — korekta + warning
  if resolution == "5m" and vertical_crs != "EVRF2007":
      logger.warning(f"Resolution 5m only supports EVRF2007, changing ...")
      vertical_crs = "EVRF2007"
  # providers/pl/gugik.py:194 — twardy blad
  if resolution == "5m":
      if vertical_crs not in self.SUPPORTED_VERTICAL_CRS_5M:
          raise ValueError("Resolution 5m is only available for EVRF2007, ...")
  ```
  Docstring `create_nmt_provider` twierdzi: "Egzekwuje regule 5m => EVRF2007 (identycznie jak DownloadManager)" — pomija trzecia, rozjezdzona implementacje.
- Weryfikacja: uruchomione w `.venv/bin/python`:
  ```
  GugikProvider(resolution="5m", vertical_crs="KRON86")      -> ValueError
  create_nmt_provider(resolution="5m", vertical_crs="KRON86") -> 5m EVRF2007
  DownloadManager(resolution="5m", vertical_crs="KRON86")     -> 5m EVRF2007
  ```
- Proponowana naprawa: zostawic egzekwowanie w jednym miejscu — `GugikProvider.__init__` (i tam zamienic `ValueError` na `ValidationError`, patrz A5-5) — a `create_nmt_provider` niech normalizuje przed konstrukcja; usunac kopie z `DownloadManager.__init__` i zaktualizowac docstring fabryki oraz `CLAUDE.md`.
- Pewnosc: wysoka

### A5-5 [Important] Rozjechana hierarchia wyjatkow: providery PL i rejestry rzucaja surowe `ValueError`/`KeyError`, CZ i `core/` rzucaja `ValidationError`
- Plik: `kartograf/providers/pl/gugik.py` (8x `raise ValueError`), `.../gugik_laz.py` (4x), `.../gugik_orto.py` (3x), `kartograf/providers/soilgrids.py` (4x `ValueError` + 2x `ValidationError`), `kartograf/providers/pl/bdot10k.py` (2x + 2x), `kartograf/core/parser_registry.py` (2x), `kartograf/sources/registry.py` (3x `KeyError`)
- Twierdzenie: `docs/DEVELOPMENT_STANDARDS.md` sekcja 11.1/11.2 nakazuje `ValidationError` dla zlego wejscia, a polowa pakietu rzuca surowe `ValueError` — konsument lapiacy `KartografError` (jak reklamuje `kartograf/exceptions.py`:22) przepusci blad walidacji providera PL; dwa moduly rzucaja OBA typy dla porownywalnych przypadkow.
- Dowod:
  ```python
  # providers/pl/bdot10k.py:189-192 — dwa rozne typy w sasiednich liniach
  raise ValidationError(f"Invalid TERYT code: {code}")
  raise ValueError(f"Unsupported format: {format}. Use 'GPKG' or 'SHP'")
  ```
- Weryfikacja: uruchomione w `.venv/bin/python`:
  ```
  try: GugikProvider(resolution="5m", vertical_crs="KRON86")
  except KartografError: ...
  -> NIE KartografError -> ValueError : Resolution 5m is only available for EVRF2007 ...
  ```
  Zliczenie per plik: `grep -rn "raise ValueError" --include='*.py' kartograf/ | awk -F: '{print $1}' | sort | uniq -c` → 37 wystapien w 14 plikach.
- Proponowana naprawa: zamienic `raise ValueError` na `raise ValidationError` w `providers/pl/*`, `providers/soilgrids.py`, `providers/corine.py`, `providers/base.py`, `core/parser_registry.py`, `download/storage.py` (`ValidationError` dziedziczy po `Exception`, wiec kod lapiacy `ValueError` przestanie dzialac — odnotowac jako BREAKING w `docs/CHANGELOG.md` dla v0.7.0). `KeyError` w `sources/registry.py` mozna zostawic (semantyka slownika), ale warto to zapisac w standardzie.
- Pewnosc: wysoka

### A5-6 [Important] Polityka "zero ballpark" z `transform/crs.py` obowiazuje tylko sciezke CZ — 9 miejsc uzywa surowego `Transformer.from_crs`
- Plik: `kartograf/transform/crs.py`:6-7 (deklaracja) vs `kartograf/core/geometry.py`:359, `kartograf/core/sheet_parser.py`:635, :864, `kartograf/core/parser_2000.py`:597, :694, :732, `kartograf/providers/corine.py`:1007, :1025, `kartograf/providers/soilgrids.py`:267
- Twierdzenie: modul polityki transformacji deklaruje, ze transformer ma byc budowany "WYLACZNIE" przez `TransformerGroup(..., allow_ballpark=False)`, a poza providerem CZ nikt tej polityki nie stosuje; najgrozniejszy przypadek to `core/geometry.py`, ktory transformuje CRS pochodzacy z **pliku uzytkownika** (`.prj` / `gpkg_spatial_ref_sys`).
- Dowod:
  ```python
  # transform/crs.py:6
  # 1. Transformer budowany WYLACZNIE przez TransformerGroup(..., allow_ballpark=False,
  #    always_xy=True) — Transformer.from_crs potrafi cicho zwrocic identycznosc.
  # core/geometry.py:359 — CRS zrodlowy pochodzi z pliku uzytkownika
  transformer = Transformer.from_crs(source_crs, target, always_xy=True)
  ```
- Weryfikacja: `grep -rn "Transformer.from_crs\|build_pinned_transform" --include='*.py' kartograf/` → 9 wywolan `from_crs` vs 2 wywolania `build_pinned_transform` (oba w `providers/cuzk/dmr.py`). Uruchomione w `.venv/bin/python`:
  ```
  EPSG:4314->EPSG:2180: pinned_ops=0  from_crs.desc='... + Ballpark geographic offset from DHDN to ETRF2000-PL + Poland CS92 ...'
  EPSG:31700->EPSG:2180: pinned_ops=0  from_crs.desc='... + Ballpark geographic offset from Dealul Piscului 1970 ...'
  ```
  czyli dla shapefile'a w DHDN/Stereo70 `--geometry` cicho przyjmie ballpark (blad rzedu setek metrow) i wybierze zle godla, mimo ze `TransformerGroup(allow_ballpark=False)` odrzucilby te pare.
- Proponowana naprawa: w `core/geometry.py:_transform_bbox` (i docelowo w `sheet_parser`/`parser_2000`) budowac transformer przez `kartograf.transform.crs.build_pinned_transform`, a `TransformUnavailableError` mapowac na `ValidationError` z remedium. Kandydat na eskalacje do Critical przez audytora poprawnosci — skutkiem jest cichy zly wynik, nie blad.
- Pewnosc: wysoka (fakt kodowy i zachowanie pyproj zweryfikowane; realny wplyw na wynik nie testowany na pliku)

### A5-7 [Important] `GugikLazProvider.download(url, ...)` lamie kontrakt `BaseProvider.download(godlo, ...)`
- Plik: `kartograf/providers/pl/gugik_laz.py`:478 vs `kartograf/providers/base.py`:74
- Twierdzenie: `GugikLazProvider` dziedziczy po `BaseProvider`, ale nadpisuje abstrakcyjna metode zmieniajac znaczenie pierwszego argumentu z godla na URL — kazdy kod polimorficzny (np. `DownloadManager`, ktory wola `provider.download(godlo, ...)`) potraktuje godlo jak adres URL.
- Dowod:
  ```python
  # base.py:74      def download(self, godlo: str, output_path: Path, timeout: int = 30) -> Path
  # gugik_laz.py:478 def download(self, url: str,  output_path: Path, timeout: int = DEFAULT_TIMEOUT) -> Path
  #   """Unlike the other providers, the first argument is the tile's download URL ..."""
  ```
- Weryfikacja: `grep -n "class GugikLazProvider" kartograf/providers/pl/gugik_laz.py` → `class GugikLazProvider(BaseProvider)`; inspekcja AST sygnatur wszystkich providerow (skrypt) potwierdza, ze pozostale piec ma `download(godlo: str, ...)`. Sciezka CLI omija problem osobnym przeplywem `_cmd_download_laz`, wiec dzis nie ma awarii — ale nic tego nie pilnuje.
- Proponowana naprawa: przemianowac metode na `download_tile(url, ...)` i albo nie dziedziczyc `BaseProvider`, albo zaimplementowac `download(godlo, ...)` rzucajaca `ValidationError` z jasnym komunikatem ("LAZ pobiera sie przez discover_tiles + download_tile").
- Pewnosc: wysoka

### A5-8 [Important] `docs/PRD.md` sekcja 5 "Public API" nie odpowiada faktycznym eksportom v0.7.0
- Plik: `docs/PRD.md`:494-540 vs `kartograf/__init__.py`:54-93
- Twierdzenie: PRD deklaruje sie jako lista eksportow `kartograf/__init__.py`, a pomija trzy eksporty dodane w etapie 1 (`ParserTM33`, `CuzkDmrProvider`, `create_dmr_provider`) i podaje wersje `"0.6.1"` zamiast `"0.7.0-dev"`.
- Dowod:
  ```
  docs/PRD.md:495   # kartograf/__init__.py exports:
  docs/PRD.md:538   __version__,  # "0.6.1"
  ```
  Brak w tej liscie: `ParserTM33`, `CuzkDmrProvider`, `create_dmr_provider` (obecne w `__all__`, l. 60, 82-83).
- Weryfikacja: uruchomione w `.venv/bin/python`:
  ```
  brak atrybutu dla __all__: []      publiczne nie w __all__: []      liczba __all__: 31
  ```
  czyli sam `__all__` jest w pelni spojny z modulem — rozjazd jest wylacznie po stronie PRD. `README.md`:107-110 jest poprawny i wymienia CZ.
- Proponowana naprawa: uzupelnic `docs/PRD.md` sekcja 5 o trzy brakujace nazwy i podbic komentarz wersji do `"0.7.0"`; ewentualnie zastapic liste odsylaczem do `kartograf/__init__.py` (tak jak zrobil to README).
- Pewnosc: wysoka

### A5-9 [Minor] Martwe symbole: `TEXTURE_NAMES`, `DLR_YEARS` oraz caly blok Keychain w `corine.py`
- Plik: `kartograf/hydrology/hsg.py`:46, `kartograf/providers/corine.py`:387, :67, :70, :132, :196
- Twierdzenie: piec symboli nie ma ani jednego uzycia w `kartograf/`, `tests/` ani w `__all__`; `DLR_YEARS` dodatkowo udaje aktywny, bo komentarz w innym module powoluje sie na niego jako na zrodlo prawdy.
- Dowod:
  ```python
  # hydrology/hsg.py:46
  TEXTURE_NAMES = {v: k for k, v in TEXTURE_CLASSES.items()}   # "Reverse mapping for display"
  # providers/corine.py:387
  DLR_YEARS = [1990]
  # landcover/manager.py:442 — komentarz odsylajacy do martwej stalej
  # 1990 musi odpowiadac CorineProvider.DLR_YEARS (WMS DLR, EPSG:4326);
  ```
  Faktyczna decyzja w kodzie nie uzywa `DLR_YEARS`: `corine.py`:922 `if year in self.EEA_YEARS: ... else: DLR`.
- Weryfikacja: `grep -rn --include='*.py' "\bTEXTURE_NAMES\b" .` → 1 trafienie (definicja); `"\bDLR_YEARS\b"` → 2 trafienia (definicja + komentarz, zero kodu); `"\bget_clms_credentials\b"` → 1; `"\bsave_credentials_to_keychain\b"` → 1; `"\bget_credentials_from_keychain\b"` → 2 (definicja + wywolanie z martwej funkcji). `TEXTURE_NAMES` nie jest w `kartograf/hydrology/__init__.py` (tam jest tylko `TEXTURE_CLASSES`).
- Proponowana naprawa: usunac `TEXTURE_NAMES` i `DLR_YEARS`; w `landcover/manager.py`:441-444 zastapic zaszyte `year == 1990` sprawdzeniem `year not in CorineProvider.EEA_YEARS`, zeby sidecar nie rozjechal sie po dodaniu kolejnego rocznika DLR. Blok Keychain — patrz A5-1.
- Pewnosc: wysoka

### A5-10 [Minor] `_download_pl_bbox` i `_download_pl_geometry` to 53 identyczne linie roznice jednego komunikatu
- Plik: `kartograf/cli/download_cmd.py`:755-808 vs :1378-1432 (a fragment budowy managera powtorzony jeszcze raz w `cmd_download`:546-571)
- Twierdzenie: budowa providera/storage/managera, blok podsumowania i obsługa bledow sa skopiowane w trzech miejscach jednego pliku; kopie sa dzis zgodne, wiec to dlug, nie blad.
- Dowod: `diff -u` wycietych blokow zwraca dokladnie dwie roznice — pusta linia i:
  ```
  -            f"for bbox (resolution: {resolution})"
  +            f"for geometry {filepath.name} (resolution: {resolution})"
  ```
- Weryfikacja: `sed -n '755,808p'` i `sed -n '1378,1432p'` do plikow w scratchpadzie + `diff -u`.
- Proponowana naprawa: wyodrebnic `_run_pl_sheets(args, godlo_list, parent_request, what: str)` przyjmujaca gotowa liste godel i etykiete zrodla; `_download_pl_bbox`/`_download_pl_geometry` skracaja sie do wyznaczenia listy godel.
- Pewnosc: wysoka

### A5-11 [Minor] Zduplikowane helpery geometryczne: `_bboxes_intersect` x2 i `_transform_bbox_to_wgs84` x3
- Plik: `kartograf/core/sheet_parser.py`:831 vs `kartograf/core/parser_2000.py`:629; `kartograf/core/sheet_parser.py`:850 vs `kartograf/providers/corine.py`:1014 vs `kartograf/providers/soilgrids.py`:251
- Twierdzenie: ciala funkcji sa identyczne (poza typem zwrotu w wariancie z `sheet_parser`), a komentarz w `parser_2000.py` jawnie przyznaje, ze kopiuje konwencje z `sheet_parser.py`.
- Dowod:
  ```python
  # parser_2000.py:629 — docstring: "zgodnie z konwencja z PL-1992 (sheet_parser.py)"
  return not (a.max_x < b.min_x or a.min_x > b.max_x or a.max_y < b.min_y or a.min_y > b.max_y)
  # identyczne cialo w sheet_parser.py:845
  ```
  `_transform_bbox_to_wgs84` w `corine.py` i `soilgrids.py` rozni sie wylacznie obecnoscia sekcji `Parameters` w docstringu.
- Weryfikacja: odczyt obu par + `grep -rn "def _bboxes_intersect\|def _transform_bbox_to_wgs84" --include='*.py' kartograf/`.
- Proponowana naprawa: przeniesc `_bboxes_intersect` do `kartograf/core/` jako jedna funkcje wspoldzielona przez oba parsery; `_transform_bbox_to_wgs84` w providerach zastapic wywolaniem `core.geometry._transform_bbox` (docelowo w wersji z przypieta operacja, patrz A5-6).
- Pewnosc: wysoka

### A5-12 [Minor] Walidacja warstw WMS zduplikowana miedzy `gugik.py` i `gugik_orto.py` z rozjechanym kluczem sortowania i stylem logowania
- Plik: `kartograf/providers/pl/gugik.py`:245-367 vs `kartograf/providers/pl/gugik_orto.py`:134-246
- Twierdzenie: ~90 linii (`_fetch_wms_layers` + `_get_validated_layers`) powtorzonych z rozna semantyka sortowania i dwoma roznymi stylami logowania w tej samej rodzinie providerow.
- Dowod:
  ```python
  # gugik.py:296 — trzy kubelki: rok malejaco, potem "iStarsze", potem bez roku
  if not year_match: return (2, 0)
  if "iStarsze" in name: return (1, -year)
  return (0, -year)
  # gugik_orto.py:189 — dwa kubelki: rok malejaco, potem bez roku ("Starsze")
  if not year_match: return (1, 0)
  return (0, -int(year_match.group(1)))
  ```
  Logowanie: `gugik.py`:346-360 uzywa f-stringow, `gugik_orto.py`:222-246 lazy `%s` (standard sekcja 12.2 wymaga `%s`).
- Weryfikacja: odczyt obu blokow; `grep -n "_fetch_wms_layers\|_get_validated_layers" kartograf/providers/pl/*.py`.
- Proponowana naprawa: wyciagnac wspolny `_fetch_skorowidze_layers(endpoint, prefix, exclude=None, timeout=10)` do modulu pomocniczego w `providers/pl/`, parametryzujac prefiks, wykluczenie i klucz sortowania; oba providery zachowuja tylko swoje stale.
- Pewnosc: wysoka

### A5-13 [Minor] Fasada `cli/commands.py` re-eksportuje 9 nazw, ktorych nikt nie importuje (w tym 5 prywatnych w `__all__`)
- Plik: `kartograf/cli/commands.py`:13-63
- Twierdzenie: `main` (entry point) i czesc nazw uzywanych przez testy sa uzasadnione, ale `_download_godlo_list`, `_cmd_download_bbox`, `_cmd_download_laz`, `_cmd_download_geometry`, `_write_laz_sidecar`, `cmd_landcover_download`, `cmd_landcover_list_layers`, `cmd_landcover_list_sources`, `cmd_soilgrids_hsg` nie sa importowane ani przez kod, ani przez testy; dodatkowo umieszczanie nazw z `_` w `__all__` przeczy konwencji "protected" ze standardu 4.1.
- Dowod:
  ```python
  # cli/commands.py:56-62 — prywatne nazwy w publicznym __all__
  "_create_provider_and_storage", "_download_godlo_list", "_cmd_download_bbox",
  "_cmd_download_laz", "_cmd_download_geometry", "_resolve_laz_bbox", "_write_laz_sidecar",
  ```
- Weryfikacja: zliczenie wystapien w `tests/` per nazwa: `_create_provider_and_storage`=13, `_resolve_laz_bbox`=11, `create_parser`=54, `format_sheet_info`=12, `create_progress_callback`=8, natomiast `_download_godlo_list`=0, `_cmd_download_bbox`=0, `_cmd_download_laz`=0, `_cmd_download_geometry`=0, `_write_laz_sidecar`=0, `cmd_landcover_download`=0, `cmd_landcover_list_layers`=0, `cmd_landcover_list_sources`=0, `cmd_soilgrids_hsg`=0. `grep -rn "cli.commands"` w kodzie produkcyjnym: tylko `pyproject.toml:36` (entry point `main`) i `kartograf/cli/__init__.py:9`.
- Proponowana naprawa: **pytanie do decyzji, nie blad** — albo (a) zostawic fasade jako celowy punkt zgodnosci i wtedy usunac z niej 9 nieuzywanych nazw oraz wyprowadzic prywatne 2 (`_create_provider_and_storage`, `_resolve_laz_bbox`) z `__all__` (import w testach nadal zadziala), albo (b) uznac, ze fasada niesie tylko `main`, a testy przepiac na moduly per komenda.
- Pewnosc: wysoka

### A5-14 [Minor] Docstringi: 21% po polsku wbrew standardowi 9.4; logowanie f-stringami wbrew standardowi 12.2
- Plik: m.in. `kartograf/cli/download_cmd.py` (20/29 docstringow po polsku), `kartograf/core/parser_2000.py` (17/30), `kartograf/core/sheet_parser.py` (15/33), `kartograf/providers/cuzk/dmr.py` (11/21), `kartograf/transport/http.py` (2/2)
- Twierdzenie: standard mowi "Docstrings i komentarze w kodzie — po angielsku", a caly nowy kod (etap 0/1) jest po polsku; rownolegle logowanie miesza f-stringi (92 wywolania) z zalecanym `%s` (64).
- Dowod:
  ```
  docstringi razem=510, z polskim=105 (21%)
  cli/download_cmd.py: 20/29 ; core/parser_2000.py: 17/30 ; core/sheet_parser.py: 15/33
  ```
  (skrypt AST + heurystyka slownikowa, prog: >=2 polskie slowa funkcyjne w docstringu)
  ```
  grep -rc 'logger\.(debug|info|warning|error|exception)\(f"' kartograf/ -> 92
  ```
- Weryfikacja: skrypt w scratchpadzie po AST wszystkich modulow + `grep -rc`. Uwaga: to swiadomy rozjazd (nowe moduly pisano po polsku), wiec kluczowa jest DECYZJA, nie sama poprawka.
- Proponowana naprawa: zaktualizowac `docs/DEVELOPMENT_STANDARDS.md` sekcja 9.4 do faktycznego stanu (np. "docstringi po polsku, bez znakow diakrytycznych") zamiast konserwowac martwy zapis; osobno — dopisac do `pyproject.toml` regule ruff `G` (`flake8-logging-format`), zeby ustalic jeden styl logowania.
- Pewnosc: wysoka

### A5-15 [Minor] Braki adnotacji typow i docstringow w sygnaturach, glownie w warstwie CLI i konstruktorach providerow
- Plik: `kartograf/cli/download_cmd.py`:60, :864, :1022, :1074, :1129; `kartograf/providers/pl/gugik_nmpt.py`:108; `kartograf/providers/pl/{gugik,gugik_orto,gugik_laz,bdot10k}.py` (parametr `cache`); `kartograf/providers/soilgrids.py`:134; `kartograf/hydrology/hsg.py`:328, :394; `kartograf/transform/crs.py`:63
- Twierdzenie: 23 funkcje maja co najmniej jeden argument bez adnotacji, 18 nie ma adnotacji zwrotu, 9 publicznych callables nie ma docstringa — mimo wymogu standardu 8.2 ("type hints wymagane dla wszystkich argumentow funkcji publicznych i wartosci zwracanych").
- Dowod:
  ```python
  # cli/download_cmd.py:60 — zero adnotacji
  def _create_provider_and_storage(product, output_dir, vertical_crs, resolution):
  # providers/pl/gugik_nmpt.py:108 — klasa potomna gubi adnotacje rodzica
  def __init__(self, session=None, vertical_crs="EVRF2007", cache=None):
  ```
  Publiczne bez docstringa: `auth/proxy.py:324 main`, `providers/cuzk/dmr.py:158 name`, `:162 base_url`, `:166 default_extension`, `:170 resolution`, `core/sheet_parser.py:550 collect_descendants`.
- Weryfikacja: skrypt AST w scratchpadzie (`hints.py`) po calym pakiecie; wynik zgodny z `mypy` baseline 33 (nie dodaje nowego dlugu).
- Proponowana naprawa: uzupelnic adnotacje w wymienionych 23 sygnaturach (`cache: MetadataCache | None = None`, `provider: BaseProvider`, `tile: LazTile`, `args: argparse.Namespace`), dopisac jednolinijkowe docstringi do 4 property `CuzkDmrProvider` (reszta providerow je ma).
- Pewnosc: wysoka

### A5-16 [Minor] Osiem funkcji przekracza 100 linii
- Plik: `kartograf/cli/_parser.py`:13 (385 l.), `kartograf/cli/download_cmd.py`:469 (151 l.), `kartograf/hydrology/hsg.py`:394 (140 l.), `kartograf/cli/soilgrids_cmd.py`:39 (133 l.), `kartograf/providers/pl/gugik.py`:422 (130 l.), `kartograf/cli/download_cmd.py`:894 (115 l.), `kartograf/auth/proxy.py`:193 (109 l.), `kartograf/providers/soilgrids.py`:424 (108 l.)
- Twierdzenie: dlugosc sama w sobie nie jest bledem, ale `cmd_download` (151 l.) laczy trzy odpowiedzialnosci — walidacje wyboru trybu, dyspozycje per kraj i wykonanie trybu godlowego.
- Dowod: pomiar `end_lineno - lineno + 1` po AST; `create_parser` (385 l.) to plaska deklaracja argparse — zostawic bez zmian.
- Weryfikacja: skrypt AST w scratchpadzie.
- Proponowana naprawa: z `cmd_download` wydzielic `_validate_selection(args) -> int | None` i `_run_pl_godlo(args) -> int`, zostawiajac w `cmd_download` sama dyspozycje (~40 l.). Pozostale siedem — bez zmian przed v0.7.0.
- Pewnosc: wysoka

### A5-17 [Minor] Rozjechane slownictwo: `uklad` vs `SheetSystem.id`, `sheets` vs `tiles`, martwy domyslny `"KRON86"` w CLI
- Plik: `kartograf/core/parser_registry.py`:111, :120, :129, :138 vs `kartograf/core/sheet_parser.py` (`uklad = "1992"/"2000"`), `kartograf/providers/cuzk/sheets.py`:144; `kartograf/cli/download_cmd.py`:550, :757, :1381
- Twierdzenie: to samo pojecie ma dwa slowniki wartosci — `parser.uklad` to `"1992"/"2000"/"cz_tm33"/"cz_sm5"`, a `SheetSystem.id` to `"pl1992"/"pl2000"/"cz_tm33"/"cz_sm5"`; wartosci CZ pokrywaja sie, PL nie, wiec kazde porownanie miedzy warstwami cicho zawiedzie dla PL. Rownolegle: `find_sheets_for_bbox` / `find_sheets_2000_for_bbox` / `find_tiles_tm33_for_bbox` / `sm5_sheets_for_bbox` / `tm33_tiles_for_bbox` mieszaja "sheets" i "tiles" dla tej samej operacji.
- Dowod:
  ```python
  # core/parser_registry.py:137   SheetSystem(id="pl1992", ...)
  # download/manager.py:256       if parser.uklad != "2000" and parser.scale != "1:10000":
  # cli/download_cmd.py:550       vertical_crs = getattr(args, "vertical_crs", "KRON86")
  ```
  Trzeci fragment: domyslna wartosc `"KRON86"` przeczy udokumentowanemu domyslnemu `EVRF2007` (`_parser.py`:140 + `_resolve_pl_sentinels`:118) i jest nieosiagalna, bo argparse zawsze ustawia atrybut — martwy, mylacy fallback powielony 3x.
- Weryfikacja: `grep -rn "uklad = \|id=\"" kartograf/core/parser_registry.py kartograf/providers/cuzk/sheets.py kartograf/core/parser_tm33.py`; `grep -n 'vertical_crs", "KRON86"' kartograf/cli/download_cmd.py` → l. 550, 757, 1381.
- Proponowana naprawa: usunac trzy fallbacki `"KRON86"` (zostawic `args.vertical_crs`); w dluzszym terminie doprowadzic `parser.uklad` do wartosci `SheetSystem.id` (BREAKING — do CHANGELOG) albo udokumentowac mapowanie w `parser_registry`.
- Pewnosc: wysoka

### A5-18 [Minor] Udokumentowane w `CLAUDE.md` timeouty nie zgadzaja sie z kodem
- Plik: `CLAUDE.md` sekcja "Ograniczenia" vs `kartograf/providers/pl/gugik_orto.py`:93, `.../gugik_laz.py`:142, `kartograf/providers/soilgrids.py`:122
- Twierdzenie: dokumentacja mowi "Timeout: 30s dla GUGiK, 60s dla Land Cover i CUZK", a w kodzie sa cztery rozne wartosci, w tym 60 s dla dwoch produktow GUGiK i 120 s dla SoilGrids.
- Dowod:
  ```
  providers/pl/gugik.py:157       DEFAULT_TIMEOUT = 30
  providers/pl/gugik_orto.py:93   DEFAULT_TIMEOUT = 60   # Ortofoto files are larger
  providers/pl/gugik_laz.py:142   DEFAULT_TIMEOUT = 60   # LAZ files are large
  providers/soilgrids.py:122      DEFAULT_TIMEOUT = 120
  ```
  Dodatkowo `LandCoverProvider` w `base.py` ma trzy rozne domyslne timeouty w rodzenstwie metod (`download_by_bbox`=60, `download_by_admin_unit`=120, `download_by_godlo`=60).
- Weryfikacja: `grep -rn "DEFAULT_TIMEOUT\s*=" --include='*.py' kartograf/`.
- Proponowana naprawa: poprawic zdanie w `CLAUDE.md` na "Timeout: 30 s NMT/NMPT, 60 s Orto/LAZ/BDOT10k/CORINE/CUZK, 120 s SoilGrids" i ujednolicic domyslne timeouty rodzenstwa w `LandCoverProvider`.
- Pewnosc: wysoka

---

## Pozytywy (max 5)
1. `kartograf/__init__.py` — `__all__` (31 pozycji) jest w 100% spojne z faktycznym namespace'em modulu: zero nazw bez atrybutu, zero publicznych nazw poza `__all__` (zweryfikowane runtime).
2. `raise ... from e` jest stosowane konsekwentnie: 13 na 13 `raise` wewnatrz `except ... as e` zachowuje lancuch wyjatkow (standard 11.3, zero naruszen).
3. Zero `TODO`/`FIXME`/`XXX`/`HACK` w calym pakiecie — kod nie jest zaminowany notatkami "do dokonczenia".
4. `ruff check` przechodzi bez uwag, `vulture --min-confidence 100` nie znajduje nic, a `mypy` daje dokladnie udokumentowany baseline 33 bledow — nowy kod etapu 1 nie dolozyl dlugu.
5. `GugikNmptProvider` to wzorcowa specjalizacja: 125 linii samych stalych i jeden `super().__init__` — zero skopiowanej logiki pobierania (kontrast z A5-3).

## Podsumowanie liczbowe: C=1 I=7 M=10

---

## Inwentarz

### (a) Martwe symbole (0 uzyc poza wlasna definicja; sprawdzone `grep -rn --include=*.py` po `kartograf/` + `tests/`)

| Symbol | Plik:linia | Wystapienia w repo | Uwaga |
|---|---|---|---|
| `KEYCHAIN_SERVICE` | `providers/corine.py`:67 | 4 (wszystkie w martwych funkcjach ponizej) | A5-1 |
| `get_credentials_from_keychain` | `providers/corine.py`:70 | 2 (def + wywolanie z martwego `get_clms_credentials`) | A5-1 |
| `save_credentials_to_keychain` | `providers/corine.py`:132 | 1 (def) | A5-1 |
| `get_clms_credentials` | `providers/corine.py`:196 | 1 (def) | A5-1, jedyny czytelnik `CLMS_CREDENTIALS` |
| `TEXTURE_NAMES` | `hydrology/hsg.py`:46 | 1 (def) | A5-9, nie w `hydrology/__init__.py` |
| `DLR_YEARS` | `providers/corine.py`:387 | 2 (def + komentarz w `landcover/manager.py`:442) | A5-9 |
| re-eksport `_download_godlo_list` | `cli/commands.py`:19 | 0 poza fasada | A5-13 |
| re-eksport `_cmd_download_bbox` | `cli/commands.py`:15 | 0 poza fasada | A5-13 |
| re-eksport `_cmd_download_laz` | `cli/commands.py`:17 | 0 poza fasada | A5-13 |
| re-eksport `_cmd_download_geometry` | `cli/commands.py`:16 | 0 poza fasada | A5-13 |
| re-eksport `_write_laz_sidecar` | `cli/commands.py`:22 | 0 poza fasada | A5-13 |
| re-eksport `cmd_landcover_download` |  `cli/commands.py`:27 | 0 poza fasada | A5-13 |
| re-eksport `cmd_landcover_list_layers` | `cli/commands.py`:28 | 0 poza fasada | A5-13 |
| re-eksport `cmd_landcover_list_sources` | `cli/commands.py`:29 | 0 poza fasada | A5-13 |
| re-eksport `cmd_soilgrids_hsg` | `cli/commands.py`:38 | 0 poza fasada | A5-13 |
| fallback `getattr(args, "vertical_crs", "KRON86")` | `cli/download_cmd.py`:550, 757, 1381 | 3 (nieosiagalne — argparse zawsze ustawia atrybut) | A5-17 |

**Uzywane WYLACZNIE przez testy** (nie martwe — to zadeklarowane publiczne API `FileStorage`/`DownloadManager`/registry, ale bez konsumenta produkcyjnego; do decyzji, nie do usuniecia w ciemno):
`FileStorage.write_atomic` (`download/storage.py`:255), `.delete` (:313), `.ensure_directory` (:219),
`.list_files` (:337), `.get_size` (:358), `DownloadManager.get_missing_sheets` (`download/manager.py`:618),
`DownloadProgress.progress_percent` (:52), `LandCoverManager.get_available_providers` (`landcover/manager.py`:457),
`LandCoverManager.download_batch` (:316), `CorineProvider.get_clc_classes` (`providers/corine.py`:1149),
`GugikProvider.get_supported_resolutions` (`providers/pl/gugik.py`:792), `.get_supported_vertical_crs_for_resolution` (:796),
`.is_wcs_available` (:834), `sources.registry.sources_for` (`sources/registry.py`:332),
`core.parser_tm33.find_tiles_tm33_for_bbox` (:68), `ParserTM33.tile_for` (:57),
`SheetIndex.sm5_sheets_for_bbox` / `.tm33_tiles_for_bbox` (`providers/cuzk/sheets.py`:112, :124 — jawnie oznaczone w planie jako fundament etapu 2),
`core.parser_2000.SHEET_DIMENSIONS_2000` (:22), `TransportKind.ARCGIS_QUERY` / `.OGC_API_FEATURES` (`sources/descriptor.py`:24-25 — rezerwacja pod etap 3),
`transform.crs.KNOWN_PATHS` (:127 — stala dokumentacyjna).

**Aliasy zgodnosciowe z CHANGELOG 0.7.0 — potwierdzone jako uzywane:**
- `LandCoverProvider.source_url` (`providers/base.py`:237) — uzywany produkcyjnie w `base.py`:413 (`__str__`) + 4 asercje w testach; **zywy**.
- `LandCoverProvider.download_by_teryt` (`base.py`:293) — uzywany produkcyjnie w `landcover/manager.py`:198, 242 + 8 miejsc w testach; **zywy** (manager wola alias, nie kanoniczne `download_by_admin_unit`).
- `LandCoverProvider.validate_teryt` (`base.py`:403) — tylko testy (11 wystapien), zero uzyc produkcyjnych.

**Nie sa martwe (mimo trafienia vulture):** `ProxyHandler.do_GET`/`do_POST`/`log_message` (`auth/proxy.py`:160, 173, 193) — callbacki `BaseHTTPRequestHandler` wolane przez framework; pola dataclass w `sources/descriptor.py`, `sources/sidecar.py`, `transform/crs.py` — serializowane przez `asdict()`.

### (b) Duplikaty (pliki + linie + czy sa rozjechane)

| # | Co | Kopie | Rozjazd zachowania? |
|---|---|---|---|
| 1 | `_download_with_retry` (petla retry) | `providers/pl/gugik.py`:687, `pl/gugik_orto.py`:477, `pl/gugik_laz.py`:525, `pl/bdot10k.py`:463, `corine.py`:1036, `soilgrids.py`:537 vs `transport/http.py`:25 | **TAK** — backoff 2 s+4 s (kopie) vs 1 s+2 s (kanoniczny); `Path.rename` vs `os.replace`; brak `mkdir(parents=True)` w kopiach. A5-3 |
| 2 | `_save_response` (zapis atomowy) | `pl/gugik.py`:763, `pl/gugik_orto.py`:522, `pl/gugik_laz.py`:567, `pl/bdot10k.py`:533, `corine.py`:1107, `soilgrids.py`:608 | Nie — 6 kopii bajtowo identycznych (20 l. kazda) |
| 3 | `_make_request` | `pl/gugik.py`:748, `pl/gugik_orto.py`:515 (+ warianty w pozostalych) | Nie — rozni sie tylko docstringiem |
| 4 | Stale `MAX_RETRIES = 3`, `RETRY_BACKOFF_BASE = 2` | `pl/gugik.py`:158-159, `pl/gugik_orto.py`:94-95, `pl/gugik_laz.py`:144-145, `pl/bdot10k.py`:118-119, `corine.py`:400-401, `soilgrids.py`:123-124, `transport/http.py`:22 | Nie (wartosci rowne), ale 7 kopii jednej stalej |
| 5 | Walidacja warstw WMS (`_fetch_wms_layers` + `_get_validated_layers`, ~90 l.) | `pl/gugik.py`:245-367 vs `pl/gugik_orto.py`:134-246 | **TAK** — inny klucz sortowania (3 vs 2 kubelki) i inny styl logowania (f-string vs `%s`). A5-12 |
| 6 | Regula "5m => EVRF2007" | `download/manager.py`:175, `providers/pl/__init__.py`:35, `providers/pl/gugik.py`:194 | **TAK** — 2x korekta+warning, 1x `raise ValueError`. Brief zakladal 2 miejsca — sa 3. A5-4 |
| 7 | Blok "provider+storage+manager+podsumowanie" w CLI | `cli/download_cmd.py`:546-571 (godlo), :755-808 (bbox), :1378-1432 (geometry) | Nie — 53 linie identyczne, jedyna roznica to komunikat i `sidecar_extra`. A5-10 |
| 8 | `_bboxes_intersect` | `core/sheet_parser.py`:831 vs `core/parser_2000.py`:629 (`_bboxes_intersect_2000`) | Nie — cialo identyczne |
| 9 | `_transform_bbox_to_wgs84` | `core/sheet_parser.py`:850, `corine.py`:1014, `soilgrids.py`:251 | Nie (poza typem zwrotu w `sheet_parser`) — 3 kopie `Transformer.from_crs("EPSG:2180","EPSG:4326")` |
| 10 | Odczyt Keychain (`security find-generic-password -s clms-token`) | `providers/corine.py`:70-129 vs `auth/proxy.py`:52-88 | **TAK** — wersja w `corine.py` obsluguje `CLMS_CREDENTIALS` i jest martwa, wersja w `proxy.py` jest zywa i env-var NIE obsluguje. A5-1 |
| 11 | Zapis sidecara (4 implementacje `best-effort`) | `download/manager.py`:668, `landcover/manager.py`:419, `cli/download_cmd.py`:864 (`_write_laz_sidecar`), :1022 (`_write_cz_sidecar`) | Nie — rozne pola sa uzasadnione (LAZ nie ma `.asc`, CZ ma `transform`), obsługa bledu identyczna we wszystkich 4 |
| 12 | Generowanie sciezki wyjsciowej w `LandCoverManager` | `landcover/manager.py`:398 (`_generate_output_path`) vs :241, :274, :311 (inline) | **TAK** — rozne nazwy plikow, jedna ze spacjami. A5-2 |
| 13 | Reprezentacja "rocznik 1990 = DLR" | `corine.py`:387 (`DLR_YEARS`, martwa), `corine.py`:922 (`year in EEA_YEARS`), `landcover/manager.py`:444 (`year == 1990`) | **TAK** — trzy niezalezne kodowania jednego faktu, jedno martwe. A5-9 |

Sprawdzone i **bez istotnego duplikatu**: `core/parser_2000.py` vs `core/parser_tm33.py` (TM33 to 93 linie czystej arytmetyki siatki, PL-2000 to hierarchia 5 skal — wspolna jest tylko konwencja nazw i `_bboxes_intersect`, poz. 8); `corine.py` vs `soilgrids.py` w warstwie WCS/WMS (rozne protokoly i rozne parametry — wspolne sa tylko poz. 1, 2, 9); `gugik_nmpt.py` (czysta specjalizacja przez dziedziczenie).

### (c) TODO / FIXME / XXX / HACK

**Zero trafien** w calym pakiecie.
Komenda: `grep -rn "TODO\|FIXME\|XXX\|HACK" --include='*.py' kartograf/` → brak wyniku.
(Uwaga: `# noqa: BLE001` wystepuje 7x jako swiadome wyciszenie przy sidecarach i odczycie nodata — z komentarzem uzasadniajacym, nie traktuje tego jako dlug.)

### (d) Funkcje > 100 linii (pomiar `end_lineno - lineno + 1` po AST)

| Plik:linia | Funkcja | Linie | Propozycja |
|---|---|---|---|
| `cli/_parser.py`:13 | `create_parser` | 385 | zostawic — plaska deklaracja argparse, podzial pogorszylby czytelnosc |
| `cli/download_cmd.py`:469 | `cmd_download` | 151 | wydzielic `_validate_selection(args)` i `_run_pl_godlo(args)` (A5-16) |
| `hydrology/hsg.py`:394 | `calculate_hsg_by_bbox` | 140 | wydzielic pobranie trzech warstw SoilGrids do `_fetch_texture_layers(bbox)` |
| `cli/soilgrids_cmd.py`:39 | `cmd_soilgrids_hsg` | 133 | wydzielic blok statystyk (`--stats`) do `_print_hsg_stats(path)` |
| `providers/pl/gugik.py`:422 | `_get_opendata_url` | 130 | wydzielic parsowanie odpowiedzi GetFeatureInfo do `_extract_url_from_html(text)` |
| `cli/download_cmd.py`:894 | `_cmd_download_laz` | 115 | wydzielic petle rownolegla po kaflach do `_fetch_laz_tiles(...)` |
| `auth/proxy.py`:193 | `ProxyHandler.do_POST` | 109 | wydzielic budowe zadania proxy do `_forward(body, headers)` |
| `providers/soilgrids.py`:424 | `_get_bbox_for_teryt` | 108 | wydzielic zapytanie do uslugi TERYT do `_query_teryt_geometry(teryt)` |
