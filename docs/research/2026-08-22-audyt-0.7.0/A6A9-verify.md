# A6A9-verify — weryfikacja ustalen A6 (docs top-level vs kod) i A9 (docstringi)

Weryfikator: V6. Zakres: wszystkie ustalenia [Critical] i [Important] z
`A6-report.md` (A6-1..A6-15) i `A9-report.md` (A9-1..A9-5). Ustalenia [Minor]
(A6-16..A6-22, A9-6, A9-7) pominiete zgodnie z VERIFY_FORMAT.

Uwaga metodyczna: zadanie zabranialo ruchu sieciowego. Jedno wywolanie
(`kartograf download --bbox 419000,... --product orto --country pl`) mimo to
weszlo do GUGiK, bo walidacja CLI przepuscila je dalej — wynik odnotowuje
sekcja A6-1 i "Nowe ustalenia" (jest przydatnym dowodem, ale nie byl
zaplanowany). Pozostale reprodukcje sa offline.

---

### A6-1 — Przyklad `--bbox ... --product orto|nmpt` z README i PRD konczy sie bledem
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ kartograf download --bbox 419000,230000,426000,237000 --product orto -o ./out_orto
  Error: --product orto jest dostepny tylko dla PL; uzyj jawnie --country pl albo --country cz
  EXIT=1
  $ kartograf download --bbox 419000,230000,426000,237000 --product nmpt -o ./out_nmpt
  Error: --product nmpt jest dostepny tylko dla PL; ...   EXIT=1
  $ python -c "_countries_for_bbox(BBox(419000,230000,426000,237000,'EPSG:2180'))"
  ('CZ', 'PL')
  ```
  Blokada: `kartograf/cli/download_cmd.py`:338-341 (`_validate_cross_country`,
  check `"CZ" in countries and product != "nmt"`), wolana z `_dispatch_area`
  (l. 398) PRZED jakimkolwiek pobraniem.
- Uzasadnienie: `docs/SCOPE.md`:202 explicite obiecuje
  `kartograf download --bbox ... --product orto`, wiec funkcja jest w zakresie
  — pada wylacznie przez domyslne `--country auto`. To blad DOCS (przyklad
  musi zostac poprawiony), nie blad kodu: twarde odrzucenie zamiast cichego
  pomijania kraju jest swiadome (CHANGELOG l. 119-120 opisuje ten sam
  mechanizm dla `--product laz`). ISTOTNA KOREKTA audytu: proponowane
  dopisanie `--country pl` NIE naprawia przykladu — sam bbox lezy w Czechach
  (patrz "Nowe ustalenia" 1), wiec trzeba wymienic wspolrzedne.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `README.md`:49, `docs/PRD.md`:117, :123, :154, :183 —
  podmienic bbox na taki, ktory lezy w Polsce i poza prostokatem CZ (np.
  `530000,382000,533000,386000`, zweryfikowany jako `('PL',)`); przy
  przykladach `--bbox` dopisac zdanie o domyslnym `--country auto`. Testu nie
  ma i nie da sie tanio przypiac (przyklady w .md nie sa wykonywane) —
  ewentualnie test CLI `test_bbox_product_orto_rejected_when_cz_in_extent`
  pilnujacy komunikatu. S; ryzyko regresji: niskie.

### A6-2 — `--format GML` reklamowany w `--help` i `list-sources` konczy sie surowym tracebackiem
- Werdykt: DOWNGRADE(Important)
- Reprodukcja (offline, bez sieci):
  ```
  >>> Bdot10kProvider().download_by_admin_unit('1465', Path('/tmp/x.zip'), format='GML')
  ValueError :: Unsupported format: GML. Use 'GPKG' or 'SHP'
  is KartografError? False
  ```
  `kartograf/cli/landcover_cmd.py`:196-204 lapie tylko
  `NotImplementedError`/`DownloadError`/`ParseError`/`ValidationError` —
  `ValueError` wychodzi tracebackiem. Kontrakt reklamowany w
  `_parser.py`:252 (`choices=["GPKG","SHP","GML"]`), `landcover_cmd.py`:53
  ("Formats: GPKG, SHP, GML") i dodatkowo w publicznym API:
  `Bdot10kProvider.get_supported_formats()` -> `['GPKG','SHP','GML']`
  (`bdot10k.py`:845), a `providers/base.py`:385 mapuje `"GML" -> ".gml"`.
  Historia: `git show f2fc490:kartograf/providers/bdot10k.py` ma
  `raise ValueError(... Use 'GPKG' or 'SHP')` juz w pierwszym commicie land
  cover (v0.3.0) — GML nigdy nie byl zaimplementowany, mimo szablonu URL
  `OPENDATA_PATTERNS["GML"]` (`bdot10k.py`:108).
- Uzasadnienie: ustalenie realne i odtworzone, ale to defekt kosmetyczny
  sprzed trzech wydan (nie regresja 0.7.0): uzytkownik i tak dostaje exit 1,
  bez utraty danych i bez ruchu sieciowego. Stad Important, nie Critical.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: usunac `"GML"` z `choices` w `kartograf/cli/_parser.py`:252,
  z tekstu `kartograf/cli/landcover_cmd.py`:53 i z
  `Bdot10kProvider.get_supported_formats()` (`bdot10k.py`:845); szablon
  `OPENDATA_PATTERNS["GML"]` moze zostac (martwy, ale nieszkodliwy) albo
  zniknac razem. Test: `tests/test_cli.py` — `--format GML` konczy sie
  `SystemExit(2)` z argparse; `tests/test_landcover.py`:80-85 rozszerzyc o
  `assert "GML" not in formats`. Zaden istniejacy test nie asertuje "GML"
  (grep po `tests/` — tylko fixtury WFS w `test_gugik_laz.py`). S; ryzyko
  regresji: niskie.

### A6-3 — CHANGELOG 0.7.0 nie odnotowuje, ze `--country` domyslnie = `auto` i zmienia wynik istniejacych komend PL
- Werdykt: DESIGN-DECISION
- Reprodukcja:
  ```
  kartograf/cli/_parser.py:99-106 -> default="auto"
  $ kartograf download --help | grep country   ->  "(default: auto)"
  $ grep -n "country" docs/CHANGELOG.md  ->  105, 109, 119, 259 (zadna linia
    nie podaje wartosci domyslnej; brak wpisu w Breaking Changes / Changed)
  ```
  Zrodlo decyzji: `docs/superpowers/specs/2026-08-11-etap1-cz-fundament-dmr-design.md`:400
  — "`--country {pl,cz,auto}`, default `auto`".
- Uzasadnienie: `default="auto"` to swiadoma decyzja specu etapu 1, wiec kod
  jest w porzadku — ale CHANGELOG o skutkach milczy, a skutki sa realne i
  szersze niz opisuje audyt (patrz "Nowe ustalenia" 2: pod `auto` odpadaja
  takze `--system 2000` i `--vertical-crs KRON86`, nie tylko `--product`).
  Zgodnie z regula VERIFY_FORMAT ("docs milcza" => DOCS-ONLY).
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/CHANGELOG.md` sekcja `[0.7.0]` — dodac do `### Changed`
  (albo `### Breaking Changes`) wpis o domyslnym `--country auto`, o zasiegu
  prostokata CZ (do 18,86°E / 51,06°N), o dodatkowym pliku+sidecarze same-nodata
  oraz o LISCIE flag odrzucanych na takim obszarze (`--product {nmpt,orto,laz}`,
  `--system`, `--vertical-crs KRON86`) i o obejsciu `--country pl`. Test:
  istniejace `TestCountryDispatch`/`TestAutoSplit*` w `tests/test_cli.py` juz
  przypinaja zachowanie; zmiana jest wylacznie tekstowa. S; ryzyko regresji:
  niskie (zero zmian w kodzie).

### A6-4 — `pyproject.toml`: wersja, autor i opis nie nadaja sie do wydania 0.7.0
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  pyproject.toml:7   version = "0.6.1"
  pyproject.toml:13  {name = "Piotr", email = "piotr@example.com"}
  $ kartograf --version            -> kartograf 0.7.0-dev
  $ pip show kartograf | head -3   -> Version: 0.4.1
                                      Summary: Tool for downloading NMT ... from GUGiK
  ```
  `description`/`keywords` (l. 8, 15) nie wymieniaja CUZK/Czech ani LAZ.
- Uzasadnienie: rozjazd potwierdzony trzema roznymi zrodlami wersji
  (0.4.1 zainstalowana / 0.6.1 w pyproject / 0.7.0-dev w kodzie). Leniwy bump
  byl spojna decyzja na `develop`, ale wydanie jest momentem, w ktorym metadane
  dystrybucji staja sie kontraktem publikowanym na PyPI.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `pyproject.toml` — `version = "0.7.0"`, realny adres autora,
  `description` + `keywords` o CUZK/CZ/DMR/LAZ. Test: `tests/test_integration.py`:56
  i `tests/test_cli.py`:3660 asertuja `__version__ == "0.7.0-dev"` — musza zostac
  zaktualizowane w tym samym commicie co `kartograf/__init__.py`:51, inaczej
  suita pada natychmiast. S; ryzyko regresji: niskie (jeden powiazany bump w 3
  plikach).

### A6-5 — Konfiguracja pakowania wciaga `tests` do dystrybucji
- Werdykt: CONFIRMED
- Reprodukcja: `find_packages` nie da sie uruchomic — `.venv` nie ma
  `setuptools` (`ModuleNotFoundError: No module named 'setuptools'`), a
  `python -m build` tym samym tez nie. Dowody posrednie, jednoznaczne:
  ```
  pyproject.toml:43-44   [tool.setuptools.packages.find] / where = ["."]   (brak include/exclude)
  $ ls tests/__init__.py                  -> istnieje (35 B)
  $ cat kartograf.egg-info/top_level.txt  -> data / docs / kartograf / tests
  $ find data docs -maxdepth 2 -name __init__.py   -> brak
  ```
- Uzasadnienie: `find_packages(where=".")` wykrywa kazdy katalog z
  `__init__.py`; `tests/__init__.py` istnieje, wiec `tests` trafi do wheela
  jako top-level pakiet (`data`/`docs` w `top_level.txt` to slad po starszej
  konfiguracji — dzis nie maja `__init__.py`). Kolizja nazwy `tests` w
  site-packages jest klasycznym problemem pakowania.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `pyproject.toml`:43-44 — dopisac `include = ["kartograf*"]`.
  Test: brak sensownego testu jednostkowego; weryfikacja recznie przez
  `python -m build` + `unzip -l dist/*.whl | grep -c '^.*tests/'` == 0 (wymaga
  doinstalowania `build`/`setuptools`). S; ryzyko regresji: niskie.

### A6-6 — `requirements*.txt` rozjechane z `pyproject.toml` i z ADR-007
- Werdykt: DOWNGRADE(Minor)
- Reprodukcja (porownanie linia po linii):
  ```
  requirements.txt      : requests>=2.31.0, pyproj>=3.6.0, PyJWT[crypto]>=2.8.0,
                          rasterio>=1.3.0, numpy>=1.24.0        (BRAK pyshp>=2.3.0)
  pyproject dependencies: te same + pyshp>=2.3.0
  requirements-dev.txt  : pytest>=7.4.0, pytest-cov>=4.1.0, black>=23.7.0,
                          flake8>=6.1.0, mypy>=1.5.0            (BRAK ruff)
  pyproject [dev]       : pytest>=8.0, pytest-cov>=5.0, ruff>=0.8, mypy>=1.13
  ADR-007 (DECISIONS.md:122): "Usunieto [tool.black] z pyproject.toml i .flake8"
  $ grep -rn "import shapefile" kartograf/  -> core/geometry.py:134 (pyshp realnie uzywane)
  ```
- Uzasadnienie: rozjazd jest realny, ale oba pliki sa SIEROTAMI — `README.md`:29
  instruuje `pip install -e .`, w repo nie ma CI ani Dockerfile'a, a jedyna
  wzmianka w docs to historyczny wpis `docs/CHANGELOG.md`:579. Zaden
  udokumentowany przeplyw ich nie czyta, wiec ryzyko dla uzytkownika jest
  hipotetyczne — stad Minor zamiast Important. Sprzecznosc z ADR-007
  (black/flake8 w wydaniu) zostaje jako dlug porzadkowy.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: usunac `requirements.txt` i `requirements-dev.txt` (spojne z
  ADR-007 i DEVELOPMENT_STANDARDS 7.2 "wszystko w pyproject.toml"); alternatywa
  — dosynchronizowac (dodac `pyshp`, zamienic black/flake8 na ruff, podniesc
  progi pytest/mypy). Zaden test tych plikow nie dotyka. S; ryzyko regresji:
  niskie.

### A6-7 — SCOPE 2.4 mowi o 9 warstwach WMS ortofotomapy — w kodzie sa 4
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  docs/SCOPE.md:118                       - 9 warstw WMS (2018-2025+starsze)
  kartograf/providers/pl/gugik_orto.py:70-75  WMS_LAYERS = [ ...2026, ...2025, ...2024, ...Starsze ]  (4)
  README.md:142                           4 warstwy WMS - 2026, 2025, 2024 + Starsze
  ```
- Uzasadnienie: SCOPE jest jedynym dokumentem z nieaktualna liczba; README i
  CHANGELOG opisuja konsolidacje 9 -> 4 poprawnie. Czysta niezgodnosc tekstu z
  kodem, bez wplywu na dzialanie (runtime i tak koryguje liste przez
  `_get_validated_layers()`).
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/SCOPE.md`:118 -> "4 warstwy WMS (2026, 2025, 2024 +
  Starsze — roczniki 2018-2023 skonsolidowane przez GUGiK)". Test: brak
  (dokument); posrednio pilnuje tego `tests/test_gugik_orto.py` na liscie
  `WMS_LAYERS`. S; ryzyko regresji: niskie.

### A6-8 — Tabele timeoutow w trzech dokumentach nie zgadzaja sie z kodem
- Werdykt: CONFIRMED
- Reprodukcja (`grep -rn "DEFAULT_TIMEOUT" kartograf/`):
  ```
  soilgrids.py:122        120        <-> DEVELOPMENT_STANDARDS.md:661  "SoilGrids | 60s"
                                     <-> IMPLEMENTATION_PROMPT.md:117  "60s"
  pl/gugik.py:157          30
  pl/gugik_orto.py:93      60        <-> CLAUDE.md:205 / SCOPE.md:279  "30s dla GUGiK"
  pl/gugik_laz.py:142      60        <-> j.w.
  pl/bdot10k.py:117        60
  corine.py:397            60
  cuzk/dmr.py:61           60
  ```
- Uzasadnienie: dwie niezaleznie falszywe liczby — SoilGrids 60 zamiast 120
  (dwa dokumenty) oraz zbiorcze "30s dla GUGiK", nieprawdziwe dla Orto/LAZ
  (60 s). Dodatkowo `docs/SCOPE.md`:279 w ogole nie wymienia CUZK, mimo ze
  IMPLEMENTATION_PROMPT ma juz dla niego wiersz.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/DEVELOPMENT_STANDARDS.md`:661 i
  `docs/IMPLEMENTATION_PROMPT.md`:117 — SoilGrids 120 s; `CLAUDE.md`:205 i
  `docs/SCOPE.md`:279 — "30 s dla NMT/NMPT (GUGiK), 60 s dla Ortofoto, LAZ,
  BDOT10k, Land Cover i CUZK, 120 s dla SoilGrids". Test: brak (dokumenty).
  S; ryzyko regresji: niskie.

### A6-9 — Sekcja `[0.7.0]` CHANGELOG ma po trzy/dwie kopie tych samych naglowkow
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ awk '/^## \[/{print NR": "$0} NR>=8&&NR<=264&&/^### /{print NR": "$0}' docs/CHANGELOG.md
    8: ## [0.7.0] - Unreleased
   10: ### Breaking Changes    48: ### Added      122: ### Changed
  158: ### Fixed              188: ### Added      209: ### Fixed
  232: ### Added              240: ### Tests      252: ### Tests
  265: ## [0.6.1] - 2026-03-24
  ```
- Uzasadnienie: liczby zgadzaja sie co do linii z raportem A6. Lamie Keep a
  Changelog (deklarowany w naglowku pliku, l. 5) i rozbija liste nowosci —
  LAZ (l. 188-208) i walidacja warstw orto (l. 232+) sa ponizej pierwszej
  sekcji `### Fixed`, wiec czytelnik szukajacy "co nowego" ich nie zobaczy.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/CHANGELOG.md` l. 8-264 — scalic w jeden komplet
  `Breaking Changes / Added / Changed / Fixed / Tests`, przy scalaniu uzgodnic
  dwa bloki `### Tests` (240 i 252 opisuja rozne etapy, obie podaja 1402).
  Test: brak; kontrola recznym `awk` jak wyzej. M (duze przenoszenie blokow
  tekstu); ryzyko regresji: niskie, ale sredni koszt przegladu (latwo zgubic
  wpis przy scalaniu — zalecany diff wpis-po-wpisie).

### A6-10 — CHANGELOG 0.7.0 podaje sciezke `providers/gugik_laz.py`, ktora ta sama wersja usuwa
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  docs/CHANGELOG.md:190  - `GugikLazProvider` (`kartograf/providers/gugik_laz.py`) ...
  docs/CHANGELOG.md:19   | `kartograf.providers.gugik_laz` | `kartograf.providers.pl.gugik_laz` |
  $ find kartograf -name gugik_laz.py  ->  kartograf/providers/pl/gugik_laz.py  (jedyne)
  ```
- Uzasadnienie: ta sama sekcja wydania podaje dwie sprzeczne sciezki; obowiazuje
  ta z tabeli BREAKING. Czysta pomylka redakcyjna.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/CHANGELOG.md`:190 -> `kartograf/providers/pl/gugik_laz.py`.
  Test: brak. S; ryzyko regresji: niskie.

### A6-11 — PRD §5 opisuje Public API sprzed 0.7.0, a §3.5-3.7 uzywaja nieistniejacego `output_dir=`
- Werdykt: CONFIRMED (oba czlony)
- Reprodukcja:
  ```
  (a) >>> set(kartograf.__all__) - set(<lista z PRD §5>)
      {'CuzkDmrProvider', 'ParserTM33', 'create_dmr_provider'}
      len(__all__) = 31, kartograf.__version__ = '0.7.0-dev'
      docs/PRD.md:539   __version__,  # "0.6.1"
  (b) >>> inspect.signature(LandCoverManager.download)
      (self, teryt=None, bbox=None, godlo=None, output_path=None, **kwargs)
      >>> m.download(teryt='1465', output_dir='./ELSEWHERE')   # provider zamockowany
      call('1465', PosixPath('data/..._teryt_1465.gpkg'), output_dir='./ELSEWHERE')
  ```
  `output_dir` przechodzi przez `**kwargs` do
  `LandCoverProvider.download_by_teryt(..., **kwargs)` i jest CICHO ignorowany
  — sciezka wyniku pozostaje autogenerowana z `output_dir` konstruktora.
  Wystapienia w PRD: l. 238, 241, 294, 340 (l. 99 dotyczy `DownloadManager`,
  gdzie `output_dir` jest poprawny).
- Uzasadnienie: obie czesci odtworzone. Wariant (b) jest grozniejszy niz
  brzmi — nie ma bledu, wiec konsument Hydrografa moze latami wierzyc, ze
  steruje katalogiem wyjsciowym. Kontekst PRD: nota 3.5 celowo zamraza PRD na
  v0.6.1, ale sama zapowiada koniec tego stanu ("celowo nieopisany DO CZASU
  WYDANIA 0.7.0") — czyli nota NIE wystarcza na release 0.7.0; to decyzja do
  zgloszenia product ownerowi, nie blad audytora. Blad `output_dir=` jest
  niezalezny od snapshotu (dotyczy API v0.6.1, ktore tez go nie mialo).
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/PRD.md`:238, 241, 294, 340 — `output_dir="./data"` ->
  `output_path=Path("./data/bdot10k_1465.gpkg")` (realny parametr); §5 (l. 494-541)
  — dopisac `ParserTM33`, `CuzkDmrProvider`, `create_dmr_provider`, zmienic
  komentarz na `# "0.7.0"`. Osobno do decyzji PO: podniesc caly PRD do 0.7.0
  (rekomendacja) albo dopisac w naglowku, ze zrodlem prawdy dla 0.7.0 jest
  `docs/SCOPE.md` 2.2 — przy drugim wariancie trzeba usunac z PRD liczby
  z 0.7.0 (§2.1 "~89% pokrycia"), bo dokument jest dzis hybryda. Test: brak.
  S (poprawki punktowe) / M (pelne podniesienie PRD); ryzyko regresji: niskie.

### A6-12 — Przyklad HSG w IMPLEMENTATION_PROMPT rzuca `TypeError`
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  >>> inspect.signature(HSGCalculator.calculate_hsg_by_godlo)
  (self, godlo: str, output_path: Path, depth='0-5cm', stat='mean', keep_intermediate=False, timeout=120)
  >>> HSGCalculator().calculate_hsg_by_godlo("N-34-130-D")
  TypeError :: ... missing 1 required positional argument: 'output_path'
  docs/IMPLEMENTATION_PROMPT.md:285   hsg_path = calc.calculate_hsg_by_godlo("N-34-130-D")
  README.md:103                       calc.calculate_hsg_by_godlo("N-34-130-D", Path("./hsg.tif"))   <- poprawnie
  ```
- Uzasadnienie: lokalna rozbieznosc jednego dokumentu, nie zmiana API —
  README ma to samo wywolanie poprawnie. Przyklad opisuje integracje z
  Hydrologiem, wiec jest kopiowany 1:1 przez konsumenta.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/IMPLEMENTATION_PROMPT.md`:285 — dopisac
  `Path("./hsg.tif")` jak w README. Test: brak. S; ryzyko regresji: niskie.

### A6-13 — Teksty `--help` opisuja projekt sprzed 0.7.0 (tylko Polska, tylko BDOT10k/CORINE)
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  _parser.py:24   description="Tool for parsing and downloading Polish topographic map sheets"
  _parser.py:201  description="Download land cover data from BDOT10k or CORINE"
  _parser.py:375  description="Manage the local SQLite metadata cache for WMS lookups"
  landcover_cmd.py:51  "Polish topographic database, land cover classes (PT)"
  kontra: --source {bdot10k,corine,soilgrids};  get_available_layers() -> 15 warstw
          (12x PT* + SWRS/SWKN/SWRM);  cache ma tabele sheet_cache (CZ),
          a CLI wspiera --country cz / CUZK
  ```
- Uzasadnienie: `--help` jest pierwsza dokumentacja uzytkownika i sprzeczna z
  README/CLAUDE.md/SCOPE w czterech miejscach naraz. Zmiana jest czysto
  tekstowa; `grep -rn` po tych stringach w `tests/` daje 0 trafien, wiec zaden
  test ich nie asertuje.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/cli/_parser.py`:24, 201, 375 i
  `kartograf/cli/landcover_cmd.py`:51 — cztery stringi ("spatial data from
  GUGiK (PL) and CUZK (CZ)", "BDOT10k, CORINE or SoilGrids", "metadata cache
  (WMS lookups, TERYT, sheet index)", "land cover and hydrography layers
  (PT*, SW*)"). Test: opcjonalny `test_cli.py` asertujacy obecnosc "CUZK" i
  "SoilGrids" w `--help`. S; ryzyko regresji: niskie.

### A6-14 — Opis zasiegu falszywych zapytan do CUZK jest bledny — Krakow/Rzeszow NIE sa objete
- Werdykt: DOWNGRADE(Minor)
- Reprodukcja (`_countries_for_bbox` na kwadratach +-0,01° wokol punktu):
  ```
  extent CZ (sources/registry.py:316): BBox(12.09, 48.55, 18.86, 51.06, EPSG:4326)
  Krakow (19.94, 50.06)   -> ('PL',)        Rzeszow  (22.00, 50.04) -> ('PL',)
  Wroclaw centrum (17.03, 51.11) -> ('PL',) Legnica  (16.17, 51.21) -> ('PL',)
  Zgorzelec (15.01, 51.15) -> ('PL',)       Katowice (19.02, 50.26) -> ('PL',)
  Opole  (17.93, 50.67) -> ('CZ','PL')      Walbrzych (16.28, 50.78) -> ('CZ','PL')
  Rybnik (18.55, 50.10) -> ('CZ','PL')      Wroclaw pd. (17.00-17.05, 51.00-51.05) -> ('CZ','PL')
  ```
- Uzasadnienie: fakt potwierdzony — Krakow (19,94°E) i Rzeszow (22,0°E) leza
  na wschod od `max_x = 18,86°E`, wiec sa poza prostokatem. ALE audyt myli
  sie co do zasiegu bledu: falszywy przyklad "okolic Krakowa/Rzeszowa" jest
  TYLKO w `docs/DECISIONS.md`:576-577 (ADR-023). `CLAUDE.md`:222-225 i
  `docs/SCOPE.md`:296-300 podaja poprawne liczby ("lon<18,86°E, lat<51,06°N")
  i zadnego miasta nie nazywaja — sa co najwyzej nieprecyzyjne w slowie
  "poludniowa". Do tego proponowana przez audyt zamiana jest sama bledna:
  Wroclaw (centrum 51,11°N), Legnica (51,21°N) i Zgorzelec (51,15°N) leza na
  POLNOC od 51,06°N, wiec tez sa poza prostokatem. Jedna zla ilustracja w
  wewnetrznym ADR (liczby obok niej sa poprawne) => Minor.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `docs/DECISIONS.md`:576-577 — zamiast "pas siegajacy np.
  okolic Krakowa/Rzeszowa" wpisac "pas na zachod od 18,86°E i na poludnie od
  51,06°N — m.in. Opole, Walbrzych, Rybnik, poludniowe obrzeza Wroclawia;
  Krakow, Rzeszow i centrum Wroclawia sa poza prostokatem"; opcjonalnie
  doprecyzowac slowo "poludniowa" w `CLAUDE.md`:222 i `docs/SCOPE.md`:296.
  Test: brak (dokument); wartosci pilnuje `sources/registry.py`:316. S;
  ryzyko regresji: niskie.

### A6-15 — README nie opisuje dwoch nowych kontraktow wydania: domyslnego `--country auto` i sidecarow
- Werdykt: CONFIRMED
- Reprodukcja (`grep -n "meta.json\|--country\|sidecar" README.md`):
  ```
  5    - **NMT (CZ)** ... `--country {pl,cz,auto}`
  56-58  przyklady --country cz / --country auto
  128  - CLI - `--country {pl,cz,auto}`; `auto` na pograniczu dzieli zadanie ...
  236  drzewo katalogow: "sources/  # ... + sidecar metadanych"
  287  Status: "**Wersja 0.7.0-dev** - ... sidecary metadanych `.meta.json`"
  ```
  Zadna linia nie mowi, ze `auto` jest WARTOSCIA DOMYSLNA, i zadna nie
  opisuje, co konkretnie powstaje po pobraniu (plik + `<plik>.meta.json`).
  Kontra: `CLAUDE.md`:207 ("Kazde udane pobranie tworzy sidecar ...") i
  `--help` ("(default: auto)").
- Uzasadnienie: README jest jedyna dokumentacja, ktora widzi nowy uzytkownik,
  a oba kontrakty (dodatkowy plik po kazdym pobraniu; domyslny auto-split)
  zmieniaja to, co uzytkownik dostaje na dysku. Luka opisowa, nie blad kodu.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `README.md` — krotka sekcja "Wynik pobrania" (plik danych +
  `<plik>.meta.json`, co niesie sidecar: CRS poziomy/pionowy, nodata,
  licencja, request) oraz jedno zdanie przy blokach `--bbox`/`--geometry`
  ("domyslnie `--country auto`; dla czystego PL uzyj `--country pl`"). Test:
  brak. S; ryzyko regresji: niskie.

---

### A9-1 — `find_sheets_for_bbox` nie waliduje parametru `system`
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  >>> find_sheets_for_bbox(BBox(19.0,50.0,19.1,50.1,'EPSG:4326'), '1:100000', system='banana')
  ['M-34-63-C']            # cichy fallback do PL-1992, bez ValidationError
  >>> find_sheets_for_bbox(..., system=2000)      # int zamiast str
  ['M-34-63-C']            # PL-1992, mimo intencji PL-2000
  ```
  `kartograf/core/sheet_parser.py`:918-920 — jedyny warunek to
  `if system == "2000": ...`, bez galezi odrzucajacej nieznane wartosci;
  docstring (l. 903-905) deklaruje `"1992" lub "2000"`.
- Uzasadnienie: przypadek `system=2000` (int) jest realistyczny i daje CICHO
  ZLA odpowiedz (godla PL-1992 zamiast PL-2000) — to nie jest kosmetyka
  docstringu, tylko luka kontraktu publicznej funkcji eksportowanej w
  `kartograf.__all__`. Z CLI nieosiagalne (`choices=["1992","2000"]`), wiec
  dotyczy konsumentow biblioteki (Hydrograf).
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/core/sheet_parser.py` — na poczatku
  `find_sheets_for_bbox` dodac
  `if system not in ("1992", "2000"): raise ValidationError(...)`; analogicznie
  rozwazyc `find_sheets_for_geometry` (`core/geometry.py`:506-546, ktora tylko
  przekazuje dalej). Sprawdzone, ze to bezpieczne: CLI woła te funkcje dopiero
  po `_resolve_pl_sentinels` (`download_cmd.py`:121 — `None -> "1992"`), a w
  `tests/` nie ma wywolania z `system=None`/inna wartoscia (jedyne
  `system=None` w `test_cli.py`:2184 idzie przez sentinele). Test:
  `tests/test_sheet_parser.py` — `pytest.raises(ValidationError)` dla
  `system="banana"` i `system=2000`. S; ryzyko regresji: niskie.

### A9-2 — `providers/__init__.py` — docstring i eksporty nieaktualne (brak NMPT/Orto/CUZK)
- Werdykt: DOWNGRADE(Minor)
- Reprodukcja:
  ```
  >>> from kartograf.providers import GugikNmptProvider   -> ImportError
  >>> from kartograf.providers import GugikOrtoProvider   -> ImportError
  >>> from kartograf.providers import CuzkDmrProvider     -> ImportError
  >>> from kartograf.providers import create_dmr_provider -> ImportError
  >>> from kartograf import GugikNmptProvider, CuzkDmrProvider   -> OK
  __all__ w providers/__init__.py: 7 nazw; docstring wylicza 6 "currently supported"
  ```
- Uzasadnienie: fakt potwierdzony, ale skutek jest natychmiast widoczny
  (`ImportError` przy imporcie, nie cichy zly wynik), a sam docstring
  wskazuje kanoniczna powierzchnie ("canonical surface: `from kartograf
  import ...`") — konsument nie ma jak napisac dzialajacego, ale blednego
  kodu. Niekompletne wyliczenie w docstringu pakietu wewnetrznego => Minor.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `kartograf/providers/__init__.py`:1-17 — dopisac do listy
  `GugikNmptProvider`, `GugikOrtoProvider` i pakiet `providers.cuzk`
  (`CuzkDmrProvider`, `create_dmr_provider`) albo jednym zdaniem zaznaczyc, ze
  modul reeksportuje tylko podzbior historyczny. Uwaga: dopisanie samych
  importow/`__all__` (wariant "naprawa kodu") to rozszerzenie publicznej
  powierzchni — do rozwazenia po wydaniu, nie w nim. Test: brak (docstring);
  ewentualnie test importow, jesli wybrany bedzie wariant kodowy. S; ryzyko
  regresji: niskie (wariant docstringowy) / srednie (wariant z eksportami).

### A9-3 — `GugikProvider.download_bbox()` — przyklad w docstringu zaklada dzis martwy endpoint WCS EVRF2007
- Werdykt: CONFIRMED (jako luka dokumentacyjna kodu)
- Reprodukcja: nie da sie offline — zadanie zabrania ruchu sieciowego, wiec
  404 na `.../WCS/DigitalTerrainModelFormatTIFFEVRF2007` NIE byl odtwarzany
  na zywo. Zweryfikowane sa natomiast oba czlony tekstowe:
  ```
  kartograf/providers/pl/gugik.py:78-86  WCS_ENDPOINTS zawiera EVRF2007; komentarz
                                         mowi tylko "5m is NOT available via WCS"
  gugik.py:608-615 (docstring download_bbox, Examples):
        >>> provider = GugikProvider()          # domyslnie vertical_crs="EVRF2007"
        >>> path = provider.download_bbox(bbox, Path("./area.tif"))
  docs/PROGRESS.md:170-177: "GUGiK usunal endpoint WCS NMT EVRF2007 ... Skutek:
        download_bbox NMT 1m dziala dzis tylko z vertical_crs='KRON86'"
  ```
- Uzasadnienie: ustalenie dotyczy dokumentacji kodu, nie gwarancji sieciowej —
  i w tej warstwie jest bezsporne: projekt ma udokumentowany, wciaz otwarty
  problem uslugowy, o ktorym `gugik.py` nie mowi ani slowa, a jego jedyny
  przyklad `Examples` prowadzi wlasnie ta sciezka. Naprawy samego endpointu
  (aktualizacja `WCS_ENDPOINTS`/`COVERAGE_IDS`, walidacja WCS analogiczna do
  WMS) NIE mozna zrobic w wydaniu bez zywej weryfikacji u GUGiK — PROGRESS
  slusznie kieruje ja "do osobnego zgloszenia".
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `kartograf/providers/pl/gugik.py` — komentarz przy
  `WCS_ENDPOINTS["EVRF2007"]` ("znany problem uslugowy: endpoint zwraca 404 od
  2026-08, patrz docs/PROGRESS.md") + w docstringu `download_bbox` sekcja
  `Notes` z tym samym ostrzezeniem i przykladem zmienionym na
  `GugikProvider(vertical_crs="KRON86")`. Test: brak (docstring; test na zywy
  404 bylby testem `live`). S; ryzyko regresji: zerowe (bez zmian logiki).
  Naprawa kodu endpointu: NIE (odlozyc) — wymaga sieci i decyzji o walidacji WCS.

### A9-4 — `MetadataCache` — `sheet_cache` pominiety w docstringu modulu; `ttl_seconds` go nie dotyczy
- Werdykt: CONFIRMED (oba czlony)
- Reprodukcja:
  ```
  metadata.py:1-10   docstring modulu wymienia tylko url_cache i teryt_cache
  metadata.py:24-28  DEFAULT_TTL_SECONDS = 7d ; SHEET_TTL_SECONDS = 30d
  metadata.py:46-48  docstring: "ttl_seconds ... Time-to-live for cache entries"
  metadata.py:297    if time.time() - cached_at >= SHEET_TTL_SECONDS   # nie self._ttl_seconds

  >>> c = MetadataCache(db_path='./ttl_test.db', ttl_seconds=1)
  >>> c.set_sheet('cz_tm33','302_5550',{'a':1}); c.set_url(...); sleep(1.2)
  get_url   po 1.2 s przy ttl=1: None        # wygaslo, zgodnie z docstringiem
  get_sheet po 1.2 s przy ttl=1: {'a': 1}    # NIE wygaslo — 30 dni na sztywno
  ```
- Uzasadnienie: odtworzone empirycznie. To nie jest sama niekompletnosc opisu:
  parametr publicznego konstruktora obiecuje kontrole TTL, ktorej dla jednej z
  trzech tabel nie ma — konsument moze bez ostrzezenia dostac 30-dniowy,
  nieodswiezalny indeks arkuszy CZ. `CLAUDE.md` wie o tym ("sheet_cache: 30d"),
  docstring nie.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `kartograf/cache/metadata.py`:1-10 — dopisac trzecia
  pozycje ("sheet index lookups (system+godlo -> payload) for CUZK sheet
  providers"); l. 46-48 — dodac zdanie "Does not apply to `sheet_cache`, which
  uses a separate fixed TTL of 30 days (`SHEET_TTL_SECONDS`)". Test: brak
  (docstring); zachowanie TTL juz przypina `tests/test_cache.py`. S; ryzyko
  regresji: zerowe.

### A9-5 — `FileStorage.delete()` — docstring nie wspomina o kasowaniu sidecara `.meta.json`
- Werdykt: DOWNGRADE(Minor)
- Reprodukcja (lektura `kartograf/download/storage.py`:313-335):
  ```
  """Delete file for given godło. ... Returns: True if file was deleted ..."""
  path.unlink()
  # Sidecar metadanych nie moze przezyc pliku danych.
  path.with_name(path.name + ".meta.json").unlink(missing_ok=True)
  ```
  Brak galezi warunkowej — sidecar kasowany zawsze, gdy plik danych istnial.
- Uzasadnienie: fakt potwierdzony, ale efekt uboczny jest dokladnie tym,
  czego konsument chce (sidecar bez pliku danych bylby smieciem), jest
  wytlumaczony komentarzem inline i opisany w `CLAUDE.md` ("`delete()` usuwa
  tez sidecar"). Nie da sie na tej podstawie napisac blednego kodu => Minor.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `kartograf/download/storage.py`:315 — jedno zdanie w
  docstringu: "Also deletes the companion `<file>.meta.json` sidecar, if
  present." Test: brak potrzeby (zachowanie juz przypiete w
  `tests/test_storage.py`). S; ryzyko regresji: zerowe.

---

## Tabela

| ID | Werdykt | Naprawa 0.7.0 | Rozmiar | Ryzyko |
|---|---|---|---|---|
| A6-1 | CONFIRMED | DOCS-ONLY | S | niskie |
| A6-2 | DOWNGRADE(Important) | TAK | S | niskie |
| A6-3 | DESIGN-DECISION | DOCS-ONLY | S | niskie |
| A6-4 | CONFIRMED | TAK | S | niskie |
| A6-5 | CONFIRMED | TAK | S | niskie |
| A6-6 | DOWNGRADE(Minor) | DOCS-ONLY | S | niskie |
| A6-7 | CONFIRMED | DOCS-ONLY | S | niskie |
| A6-8 | CONFIRMED | DOCS-ONLY | S | niskie |
| A6-9 | CONFIRMED | DOCS-ONLY | M | niskie |
| A6-10 | CONFIRMED | DOCS-ONLY | S | niskie |
| A6-11 | CONFIRMED | DOCS-ONLY | S/M | niskie |
| A6-12 | CONFIRMED | DOCS-ONLY | S | niskie |
| A6-13 | CONFIRMED | TAK | S | niskie |
| A6-14 | DOWNGRADE(Minor) | DOCS-ONLY | S | niskie |
| A6-15 | CONFIRMED | DOCS-ONLY | S | niskie |
| A9-1 | CONFIRMED | TAK | S | niskie |
| A9-2 | DOWNGRADE(Minor) | DOCS-ONLY | S | niskie |
| A9-3 | CONFIRMED | DOCS-ONLY | S | zerowe |
| A9-4 | CONFIRMED | DOCS-ONLY | S | zerowe |
| A9-5 | DOWNGRADE(Minor) | DOCS-ONLY | S | zerowe |

Bilans: 20 ustalen zweryfikowanych — 14 CONFIRMED, 5 DOWNGRADE (A6-2
Critical->Important; A6-6, A6-14, A9-2, A9-5 Important->Minor),
1 DESIGN-DECISION (A6-3), 0 REFUTED. Napraw kodowych przed wydaniem: 5
(A6-2, A6-4, A6-5, A6-13, A9-1 — wszystkie S, wszystkie z niskim ryzykiem
regresji). Pozostale 15 to DOCS-ONLY.

## Nowe ustalenia przy okazji (max 3, tylko jesli Critical/Important i z dowodem)

1. **[Critical] Przykladowy bbox `419000,230000,426000,237000` z README:49 i
   PRD:117/123/154/183 lezy w calosci w Czechach, a nie w Polsce.** Transformacja
   wlasnym kodem projektu:
   `_bbox_to_wgs84(BBox(419000,230000,426000,237000,'EPSG:2180'))` ->
   `17,870-17,969°E / 49,932-49,996°N` — to okolice Opawy (Opava, CZ), ok. 6 km
   na poludnie od granicy. Konsekwencja: proponowana przez A6-1 naprawa
   ("dopisac `--country pl`") NIE naprawia przykladu. Przy jawnym
   `--country pl` komenda przechodzi walidacje i konczy sie bledem po stronie
   danych: `Error: No orthophoto data available for M-33-84-B-a-4-4` (EXIT=1;
   to jedyne moje wywolanie, ktore weszlo do sieci — patrz uwaga metodyczna).
   Dotyczy tez PRD:117, czyli przykladu **czystego NMT** bez `--product`,
   ktorego audyt A6 w ogole nie zglosil. Naprawa: podmienic wspolrzedne we
   wszystkich 5 miejscach na bbox faktycznie polski (S, DOCS-ONLY).

2. **[Important] Domyslne `--country auto` lamie w poludniowo-zachodniej Polsce
   nie tylko `--product`, ale takze `--system` i `--vertical-crs KRON86` —
   czyli komendy udokumentowane od v0.5.0/v0.4.0.** Reprodukcja na bboxie
   lezacym w calosci w Polsce (okolice Raciborza, 18,2°E / 50,1°N):
   ```
   $ kartograf download --bbox 442802,248390,444802,250390 --vertical-crs KRON86
   Error: KRON86 nie jest osiagalny dla CZ (siatki GUGiK niepubliczne); uzyj jawnie --country pl albo --country cz
   $ kartograf download --bbox 442802,248390,444802,250390 --system 2000
   Error: --system dotyczy tylko PL; uzyj jawnie --country pl albo --country cz
   $ kartograf download --bbox 6514308,5551561,6516308,5553561 --bbox-crs EPSG:2177 --system 2000
   Error: --system dotyczy tylko PL; ...
   ```
   (ten sam `--system 2000` z bboxem polnocnym, np. przykladem z CLAUDE.md
   `6500000,5895000,...` w strefie 6 -> `('PL',)`, dziala). To rozszerza A6-3:
   CHANGELOG musi wymienic pelna liste flag odrzucanych pod `auto`, bo dla
   uzytkownika PL-2000 z Gornego Slaska jest to twarda regresja wzgledem
   v0.6.1 (exit 1 zamiast pobrania), a nie tylko "dodatkowy plik nodata".
   Naprawa: DOCS-ONLY w CHANGELOG/README/SCOPE (S). Wariant kodowy
   (nie odrzucac flagi PL, gdy dotyczy tylko galezi PL) = zmiana semantyki
   `_validate_cross_country` — NIE w tym wydaniu.

3. **[Important] `--format GML` to phantom takze w publicznym API biblioteki,
   nie tylko w CLI.** `Bdot10kProvider().get_supported_formats()` zwraca
   `['GPKG', 'SHP', 'GML']` (`bdot10k.py`:845), a `providers/base.py`:385
   mapuje `"GML" -> ".gml"` — konsument (Hydrograf) moze wiec wybrac format z
   listy zadeklarowanej przez sam provider i dostac `ValueError` z
   `download_by_admin_unit`. Zaden test nie asertuje "GML"
   (`grep -rn GML tests/` -> tylko fixtury WFS w `test_gugik_laz.py`;
   `test_landcover.py`:80-85 sprawdza wylacznie GPKG i SHP), wiec usuniecie
   jest bezpieczne. Rozszerza A6-2 o trzecie miejsce do poprawienia.
