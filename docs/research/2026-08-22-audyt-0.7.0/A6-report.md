# A6 — Dokumentacja top-level vs kod

Zakres: przeczytane W CALOSCI: `README.md`, `CLAUDE.md`, `docs/PROGRESS.md`,
`docs/SCOPE.md`, `docs/PRD.md`, `docs/CHANGELOG.md` (sekcja 0.7.0 w calosci,
starsze sekcje przejrzane pod katem wersji/naglowkow/linkow),
`docs/DECISIONS.md`, `docs/DEVELOPMENT_STANDARDS.md`,
`docs/IMPLEMENTATION_PROMPT.md`, `pyproject.toml`, `requirements.txt`,
`requirements-dev.txt`, `.gitignore`.

Metoda: czytanie pelnych plikow; `grep -rn` po `kartograf/` i `tests/`;
uruchomione komendy: `.venv/bin/kartograf --help` + `--version` + wszystkie
podkomendy `--help`, `.venv/bin/kartograf landcover list-sources`,
`.venv/bin/kartograf download --bbox ... --product orto|nmpt` (realne
uruchomienie przykladow z README/PRD), `.venv/bin/kartograf landcover download
--source bdot10k --teryt 1465 --format GML`, `pytest tests/ --collect-only -q`
(**1402**), pelny `pytest tests/ --cov=kartograf` (**1402 passed, 89.53%**),
`mypy kartograf/` (**33 bledy = baseline**), `git log --oneline v0.6.1..HEAD`
(74 commity, kazdy feat/fix/refactor sprawdzony wzgledem CHANGELOG),
introspekcja sygnatur przez `.venv/bin/python -c "import inspect; ..."`,
sprawdzenie istnienia wszystkich linkow wewnetrznych w .md, porownanie drzewa
`CLAUDE.md`/`SCOPE.md`/`DEVELOPMENT_STANDARDS.md`/`IMPLEMENTATION_PROMPT.md`
z `find kartograf -name '*.py'`.

Nie sprawdzono: (a) zachowania na zywych uslugach GUGiK/CUZK — audyt bez
sieci, wiec twierdzenia o dostepnosci warstw/endpointow przyjete z docs;
(b) `docs/research/**` i `docs/superpowers/**` (poza sprawdzeniem, ze linki do
nich istnieja) — poza moim obszarem; (c) tresci ADR-001..ADR-021 pod katem
zgodnosci z historycznym kodem (przeczytane, ale weryfikowalem tylko
twierdzenia nadal obowiazujace); (d) katalogu `out/` w korzeniu repo —
powstal 12:52 z pobrania CORINE innego agenta, nie mojego.

---

## Ustalenia

### A6-1 [Critical] Przyklad `--bbox ... --product orto|nmpt` z README i PRD konczy sie bledem
- Plik: `README.md`:49; `docs/PRD.md`:123, `docs/PRD.md`:154, `docs/PRD.md`:183
- Twierdzenie: udokumentowana komenda `kartograf download --bbox
  419000,230000,426000,237000 --product orto` (i jej wariant `--product nmpt`)
  nie dziala — domyslne `--country auto` wykrywa, ze bbox przecina prostokatna
  obwiednie CZ, a produkt inny niz `nmt` jest dla CZ odrzucany przed pobraniem.
- Dowod (README.md:48-49):
  ```
  # Selekcja obszaru: bbox albo plik geometrii (SHP/GPKG)
  kartograf download --bbox 419000,230000,426000,237000 --product orto
  ```
  Faktyczne wykonanie:
  ```
  $ kartograf download --bbox 419000,230000,426000,237000 --product orto -o ./out1
  Error: --product orto jest dostepny tylko dla PL; uzyj jawnie --country pl albo --country cz
  EXIT=1
  ```
  Zrodlo odrzucenia — `kartograf/cli/download_cmd.py`:338-341:
  ```python
  ("CZ" in countries and product != "nmt",
   f"--product {product} jest dostepny tylko dla PL"),
  ```
- Weryfikacja: uruchomione oba warianty (`--product orto` i `--product nmpt`)
  w `.venv/bin/kartograf` — oba zwracaja exit 1 przed jakimkolwiek ruchem
  sieciowym; dodatkowo `_countries_for_bbox(BBox(419000,230000,426000,237000,
  "EPSG:2180"))` zwraca `('CZ', 'PL')`.
- Proponowana naprawa: albo dopisac `--country pl` do tych przykladow w README
  i PRD, albo zmienic bbox na taki, ktory nie wchodzi w prostokat CZ (np.
  `--bbox 530000,382000,533000,386000`, zweryfikowany jako `('PL',)`). Pierwsze
  jest uczciwsze — pokazuje uzytkownikowi realny wymog po wprowadzeniu CZ.
- Pewnosc: wysoka

### A6-2 [Critical] `--format GML` reklamowany w `--help` i `list-sources` konczy sie surowym tracebackiem
- Plik: `kartograf/cli/_parser.py`:252 oraz `kartograf/cli/landcover_cmd.py`:53
  (kontrakt dokumentacyjny widziany przez uzytkownika); po stronie kodu
  `kartograf/providers/pl/bdot10k.py`:191-192
- Twierdzenie: `argparse` przyjmuje `--format GML` i `landcover list-sources`
  reklamuje ten format, ale provider go odrzuca `ValueError`-em, ktory nie ma
  handlera — uzytkownik dostaje traceback zamiast komunikatu.
- Dowod:
  ```
  kartograf/cli/_parser.py:252:        choices=["GPKG", "SHP", "GML"],
  kartograf/cli/landcover_cmd.py:53:    print("              Formats: GPKG, SHP, GML")
  kartograf/providers/pl/bdot10k.py:192:  raise ValueError(f"Unsupported format: {format}. Use 'GPKG' or 'SHP'")
  ```
  Faktyczne wykonanie:
  ```
  $ kartograf landcover download --source bdot10k --teryt 1465 --format GML -o ./out3
  Downloading land cover data from BDOT10k...
    TERYT: 1465
  Traceback (most recent call last):
  ...
  ValueError: Unsupported format: GML. Use 'GPKG' or 'SHP'
  EXIT=1
  ```
- Weryfikacja: uruchomione; blad przed transferem, ale bez handlera.
  Regresja **przedistniejaca** (`git show v0.6.1:kartograf/cli/commands.py`
  ma `choices=["GPKG", "SHP", "GML"]` w linii 223 i ten sam tekst
  `Formats: GPKG, SHP, GML` w linii 1031) — nie jest to regresja 0.7.0, ale
  wychodzi z wydaniem.
- Proponowana naprawa: usunac `"GML"` z `choices` w `_parser.py` i z tekstu
  `list-sources`; jesli GML ma zostac obietnica, to `download_by_admin_unit`
  musi rzucac `ValidationError` (lapany przez CLI), nie golego `ValueError`.
- Pewnosc: wysoka

### A6-3 [Critical] CHANGELOG 0.7.0 nie odnotowuje, ze `--country` domyslnie = `auto` i zmienia wynik istniejacych komend PL
- Plik: `docs/CHANGELOG.md`:105-109 (sekcja `### Added` w `[0.7.0] - Unreleased`)
- Twierdzenie: `--country` ma `default="auto"`, wiec komenda z 0.6.1 typu
  `kartograf download --bbox <obszar w Polsce zachodniej/poludniowej>` w 0.7.0
  dodatkowo odpytuje CUZK i produkuje dodatkowy raster+sidecar wypelniony
  nodata (albo — dla `--product` innego niz `nmt`, patrz A6-1 — jest w calosci
  odrzucana). CHANGELOG opisuje `--country` wylacznie jako nowa funkcje w
  `### Added`, nigdzie nie podaje wartosci domyslnej i nie ma o tym wpisu w
  `### Breaking Changes` ani `### Changed`.
- Dowod — CHANGELOG (jedyna wzmianka o `--country`):
  ```
  - CLI `--country {pl,cz,auto}` z auto-podzialem bboxa/geometrii
    transgranicznej: obszar trafia do zrodel KAZDEGO przecietego kraju ...
  ```
  Kod, `kartograf/cli/_parser.py`:99-106:
  ```python
  download_parser.add_argument(
      "--country",
      choices=["pl", "cz", "auto"],
      default="auto",
  ```
  Skutek potwierdzony wlasnym ADR projektu (`docs/DECISIONS.md`:576-579):
  "Skutek: dodatkowy raster wypelniony `nodata` (`-9999`) + dodatkowy sidecar
  CZ bez uzytecznych danych".
- Weryfikacja: `--help` pokazuje `(default: auto)`; uruchomione
  `_countries_for_bbox` dla realnych bboxow — patrz A6-1 i A6-14.
- Proponowana naprawa: dodac do `### Changed` (albo `### Breaking Changes`)
  wpis: "`kartograf download --bbox/--geometry` domyslnie dziala z
  `--country auto`; obszar przecinajacy prostokatna obwiednie CZ (do 18,86°E /
  51,06°N) wysyla dodatkowe zapytanie do CUZK — w efekcie powstaje dodatkowy
  plik+sidecar (zwykle same nodata), a `--product {nmpt,orto,laz}` na takim
  obszarze jest odrzucany. Zachowanie sprzed 0.7.0 przywraca jawne
  `--country pl`."
- Pewnosc: wysoka

### A6-4 [Important] `pyproject.toml` — wersja, autor i opis nie nadaja sie do wydania 0.7.0
- Plik: `pyproject.toml`:7, `pyproject.toml`:8, `pyproject.toml`:12-15
- Twierdzenie: metadane dystrybucji rozjezdzaja sie z pakietem (`0.6.1` vs
  `kartograf.__version__ == "0.7.0-dev"`), autor ma adres-placeholder
  `piotr@example.com`, a `description`/`keywords` nie wspominaja o CUZK/Czechach
  ani o LAZ — czyli o dwoch glownych nowosciach wydania.
- Dowod:
  ```toml
  version = "0.6.1"
  description = "Tool for downloading spatial data from GUGiK (NMT, NMPT, Ortophoto, BDOT10k), Copernicus (CORINE) and ISRIC (SoilGrids)"
  authors = [ {name = "Piotr", email = "piotr@example.com"} ]
  keywords = ["nmt", "dem", "gugik", "gis", "terrain", "geodata", "bdot10k", "corine", "soilgrids", "land-cover", "ortophoto"]
  ```
  Rozjazd widoczny dla uzytkownika:
  ```
  $ kartograf --version
  kartograf 0.7.0-dev
  $ pip show kartograf | head -2
  Name: kartograf
  Version: 0.4.1        # metadane instalacji, nie 0.6.1/0.7.0
  ```
- Weryfikacja: uruchomione `kartograf --version` i `pip show`;
  `git grep "0.6.1"` — jedyne miejsce z wersja pakietu poza docs to
  `pyproject.toml`:7. Sama swiadoma decyzja "bump leniwie do wydania"
  (`docs/PROGRESS.md`:342-354) jest spojna, ale **wydanie 0.7.0 jest wlasnie
  tym momentem**.
- Proponowana naprawa: przy wydaniu ustawic `version = "0.7.0"`, poprawic
  `authors` na realny adres, uzupelnic `description` o "CUZK (DMR 5G/4G,
  Czechy)" i "LAZ", dodac keywordy `cuzk`, `czechia`, `dmr`, `laz`, `lidar`.
- Pewnosc: wysoka

### A6-5 [Important] Konfiguracja pakowania wciaga `tests` do dystrybucji
- Plik: `pyproject.toml`:43-44
- Twierdzenie: `[tool.setuptools.packages.find] where = ["."]` bez `include`/
  `exclude` powoduje, ze `find_packages(".")` znajduje takze `tests`
  (`tests/__init__.py` istnieje) i pakuje go jako top-level pakiet `tests` w
  site-packages.
- Dowod:
  ```toml
  [tool.setuptools.packages.find]
  where = ["."]
  ```
  Slad po poprzednim buildzie, `kartograf.egg-info/top_level.txt`:
  ```
  data
  docs
  kartograf
  tests
  ```
  `tests/__init__.py` nadal istnieje (`ls tests/__init__.py` -> OK).
- Weryfikacja: `ls tests/__init__.py` (istnieje), `cat
  kartograf.egg-info/top_level.txt` (zawiera `tests`); `docs`/`data` juz nie
  zostana wykryte (brak `__init__.py`), ale `tests` tak.
- Proponowana naprawa: dodac `include = ["kartograf*"]` (albo
  `exclude = ["tests*", "docs*"]`) do `[tool.setuptools.packages.find]` przed
  zbudowaniem artefaktow 0.7.0.
- Pewnosc: wysoka

### A6-6 [Important] `requirements*.txt` rozjechane z `pyproject.toml` i z ADR-007
- Plik: `requirements.txt`:1-5, `requirements-dev.txt`:5-15
- Twierdzenie: `requirements.txt` nie zawiera `pyshp` (obowiazkowa zaleznosc od
  v0.4.1), a `requirements-dev.txt` instaluje `black` i `flake8` — narzedzia,
  ktore ADR-007 uznaje za usuniete, i pomija `ruff`; wersje pytest/pytest-cov
  tez sie rozjezdzaja z `[project.optional-dependencies] dev`.
- Dowod:
  ```
  requirements.txt:      requests, pyproj, PyJWT[crypto], rasterio, numpy      (brak pyshp)
  requirements-dev.txt:  pytest>=7.4.0, pytest-cov>=4.1.0, black>=23.7.0, flake8>=6.1.0, mypy>=1.5.0
  pyproject.toml:47      dev = ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.8", "mypy>=1.13"]
  docs/DECISIONS.md ADR-007: "Usunieto [tool.black] z pyproject.toml i .flake8"
  ```
- Weryfikacja: `grep` po `pyshp` w `requirements.txt` (brak);
  `grep -rn "import shapefile" kartograf/` potwierdza, ze pyshp jest realnie
  uzywane (`core/geometry.py`); porownanie obu plikow z `pyproject.toml`.
- Proponowana naprawa: albo usunac oba pliki i zostawic
  `pip install -e ".[dev]"` jako jedyna sciezke (spojne z ADR-007 i sekcja 7.2
  DEVELOPMENT_STANDARDS "wszystko w pyproject.toml"), albo wygenerowac je
  z `pyproject.toml`. Zostawienie `black`/`flake8` w wydaniu jest mylace.
- Pewnosc: wysoka

### A6-7 [Important] SCOPE 2.4 mowi o 9 warstwach WMS ortofotomapy — w kodzie sa 4
- Plik: `docs/SCOPE.md`:118
- Twierdzenie: SCOPE deklaruje "9 warstw WMS (2018-2025+starsze)", podczas gdy
  kod ma 4 warstwy (2026/2025/2024/Starsze), a README i CHANGELOG mowia
  poprawnie o 4 — czyli SCOPE jest jedynym dokumentem z nieaktualna liczba.
- Dowod — `docs/SCOPE.md`:118: `- 9 warstw WMS (2018-2025+starsze)`
  vs `kartograf/providers/pl/gugik_orto.py`:70-75:
  ```python
  WMS_LAYERS = [
      "SkorowidzeOrtofotomapy2026",
      "SkorowidzeOrtofotomapy2025",
      "SkorowidzeOrtofotomapy2024",
      "SkorowidzeOrtofotomapyStarsze",
  ]
  ```
  vs `README.md`:142: "**4 warstwy WMS** - 2026, 2025, 2024 + Starsze".
- Weryfikacja: `grep -n "WMS_LAYERS" -A 20 kartograf/providers/pl/gugik_orto.py`;
  CHANGELOG 0.7.0 (l. 224-225) tez opisuje przejscie 9 -> 4.
- Proponowana naprawa: `docs/SCOPE.md`:118 -> "4 warstwy WMS (2026, 2025, 2024
  + Starsze — roczniki 2018-2023 skonsolidowane przez GUGiK)".
- Pewnosc: wysoka

### A6-8 [Important] Tabele timeoutow w trzech dokumentach nie zgadzaja sie z kodem
- Plik: `docs/DEVELOPMENT_STANDARDS.md`:657-662, `docs/IMPLEMENTATION_PROMPT.md`:110-117,
  `CLAUDE.md`:205, `docs/SCOPE.md`:279
- Twierdzenie: SoilGrids ma w kodzie `DEFAULT_TIMEOUT = 120`, nie 60 s
  (blad w DEVELOPMENT_STANDARDS i IMPLEMENTATION_PROMPT); a zbiorcze zdanie
  "Timeout: 30s dla GUGiK" (CLAUDE.md, SCOPE.md) jest nieprawdziwe dla
  ortofotomapy i LAZ, ktore maja 60 s. SCOPE dodatkowo w ogole nie wymienia
  CUZK.
- Dowod:
  ```
  kartograf/providers/soilgrids.py:122:     DEFAULT_TIMEOUT = 120
  kartograf/providers/pl/gugik.py:157:      DEFAULT_TIMEOUT = 30
  kartograf/providers/pl/gugik_orto.py:93:  DEFAULT_TIMEOUT = 60  # Ortofoto files are larger
  kartograf/providers/pl/gugik_laz.py:142:  DEFAULT_TIMEOUT = 60  # LAZ files are large
  kartograf/providers/corine.py:397:        DEFAULT_TIMEOUT = 60
  kartograf/providers/cuzk/dmr.py:61:       _DEFAULT_TIMEOUT = 60
  ```
  vs `docs/DEVELOPMENT_STANDARDS.md`:661 `| SoilGrids (ISRIC WCS) | 60s |`
  oraz `CLAUDE.md`:205 `- Timeout: 30s dla GUGiK, 60s dla Land Cover i CUZK`.
- Weryfikacja: `grep -rn "DEFAULT_TIMEOUT" kartograf/`; wartosci odczytane
  wprost ze stalych klasowych. `docs/IMPLEMENTATION_PROMPT.md`:112 ("LAZ ...
  30s / 60s") jest bliskie prawdy (30 s dotyczy `discover_tiles`), ale 60 s dla
  SoilGrids w linii 117 juz nie.
- Proponowana naprawa: SoilGrids -> 120 s w obu dokumentach; w CLAUDE.md i
  SCOPE zamienic zdanie na "30 s dla NMT/NMPT (GUGiK), 60 s dla Ortofoto, LAZ,
  Land Cover i CUZK, 120 s dla SoilGrids".
- Pewnosc: wysoka

### A6-9 [Important] Sekcja `[0.7.0]` CHANGELOG ma po trzy/dwie kopie tych samych naglowkow
- Plik: `docs/CHANGELOG.md`:48, 188, 232 (`### Added`); 158, 209 (`### Fixed`);
  240, 252 (`### Tests`)
- Twierdzenie: jedno wydanie ma trzy sekcje `### Added`, dwie `### Fixed` i
  dwie `### Tests`. To lamie Keep a Changelog (na ktory powoluje sie naglowek
  pliku) i sprawia, ze czytelnik nie widzi kompletnej listy nowosci w jednym
  miejscu — LAZ i walidacja warstw orto sa "schowane" ponizej sekcji `Fixed`.
- Dowod (`awk` po naglowkach w zakresie 8-264):
  ```
   10: ### Breaking Changes
   48: ### Added
  122: ### Changed
  158: ### Fixed
  188: ### Added     <- druga
  209: ### Fixed     <- druga
  232: ### Added     <- trzecia
  240: ### Tests
  252: ### Tests     <- druga
  ```
- Weryfikacja: `awk 'NR>=8 && NR<=264 && /^### /{print NR": "$0}' docs/CHANGELOG.md`.
- Proponowana naprawa: scalic w jeden komplet `Breaking Changes / Added /
  Changed / Fixed / Tests` przed nadaniem daty wydania; przy scalaniu
  uzgodnic dwie rozne liczby testow (240: "1402 testy" vs 252 tez 1402, ale
  bloki opisuja rozne etapy).
- Pewnosc: wysoka

### A6-10 [Important] CHANGELOG 0.7.0 podaje sciezke `providers/gugik_laz.py`, ktora ta sama wersja usuwa
- Plik: `docs/CHANGELOG.md`:190
- Twierdzenie: wpis o LAZ wskazuje `kartograf/providers/gugik_laz.py`, podczas
  gdy tabela BREAKING 30 linii wyzej w tym samym wydaniu mowi, ze modul
  przeniosl sie do `kartograf/providers/pl/gugik_laz.py`.
- Dowod:
  ```
  docs/CHANGELOG.md:190:  - `GugikLazProvider` (`kartograf/providers/gugik_laz.py`) — pobieranie plików
  docs/CHANGELOG.md:19:   | `kartograf.providers.gugik_laz` | `kartograf.providers.pl.gugik_laz` |
  ```
  Stan faktyczny: `find kartograf -name 'gugik_laz.py'` ->
  `kartograf/providers/pl/gugik_laz.py` (jedyne wystapienie).
- Weryfikacja: `find kartograf -name '*.py' | sort` — brak
  `kartograf/providers/gugik_laz.py`.
- Proponowana naprawa: poprawic sciezke na `kartograf/providers/pl/gugik_laz.py`
  (analogiczne wystapienia w tym samym bloku sprawdzone — to jedyne).
- Pewnosc: wysoka

### A6-11 [Important] PRD §5 opisuje Public API sprzed 0.7.0, a §3.5-3.7 uzywaja nieistniejacego `output_dir=`
- Plik: `docs/PRD.md`:494-541 (§5), `docs/PRD.md`:238, 241, 294, 340 (`output_dir=`)
- Twierdzenie: (a) lista eksportow pomija `ParserTM33`, `CuzkDmrProvider`,
  `create_dmr_provider` i deklaruje `__version__, # "0.6.1"`; (b) przyklady
  `lc.download(teryt="1465", output_dir="./data")` sugeruja parametr, ktorego
  `LandCoverManager.download` nie ma — trafia on do `**kwargs` i jest **cicho
  ignorowany**, plik ladzie w sciezce auto-generowanej.
- Dowod — sygnatura:
  ```
  LandCoverManager.download(self, teryt=None, bbox=None, godlo=None, output_path=None, **kwargs)
  ```
  Eksperyment (mock providera, bez sieci):
  ```
  lc.download(teryt="1465", output_dir="./data")
  -> provider wywolany z: call('1465', PosixPath('data/landcover/bdot10k_teryt_1465.gpkg'), output_dir='./data')
  ```
  czyli `output_dir` nie wplywa na sciezke wyniku i nie powoduje bledu.
- Weryfikacja: `inspect.signature(LandCoverManager.download)` + uruchomiony
  snippet z `MagicMock` w `.venv/bin/python`; porownanie §5 z faktycznym
  `kartograf/__init__.py:53-93` (`__all__` ma 29 nazw + `__version__`).
- Proponowana naprawa: w §5 dopisac trzy brakujace eksporty i zmienic komentarz
  na `# "0.7.0"`; w §3.5/3.6/3.7 zamienic `output_dir="./data"` na
  `output_path=Path("./data/bdot10k_1465.gpkg")` (realny parametr).
- Pewnosc: wysoka

### A6-12 [Important] Przyklad HSG w IMPLEMENTATION_PROMPT rzuca `TypeError`
- Plik: `docs/IMPLEMENTATION_PROMPT.md`:282-286
- Twierdzenie: przyklad integracji z Hydrologiem wola
  `calc.calculate_hsg_by_godlo("N-34-130-D")` bez `output_path`, ktory jest
  argumentem wymaganym.
- Dowod:
  ```python
  # docs/IMPLEMENTATION_PROMPT.md:283-285
  calc = HSGCalculator()
  hsg_path = calc.calculate_hsg_by_godlo("N-34-130-D")
  ```
  Uruchomienie:
  ```
  TypeError HSGCalculator.calculate_hsg_by_godlo() missing 1 required positional argument: 'output_path'
  ```
  Sygnatura: `(self, godlo: str, output_path: Path, depth='0-5cm',
  stat='mean', keep_intermediate=False, timeout=120) -> Path`.
- Weryfikacja: uruchomiony snippet w `.venv/bin/python`; README (l. 103) ma
  ten sam wywolanie **poprawnie**, z `Path("./hsg.tif")` — czyli to lokalna
  rozbieznosc, nie zmiana API.
- Proponowana naprawa: `calc.calculate_hsg_by_godlo("N-34-130-D",
  Path("./hsg.tif"))`, jak w README.
- Pewnosc: wysoka

### A6-13 [Important] Teksty `--help` opisuja projekt sprzed 0.7.0 (tylko Polska, tylko BDOT10k/CORINE)
- Plik: `kartograf/cli/_parser.py`:24, 201, 375; `kartograf/cli/landcover_cmd.py`:51
- Twierdzenie: `--help` to podstawowa dokumentacja uzytkownika, a mowi rzeczy
  sprzeczne z README/CLAUDE.md/SCOPE: top-level opisuje narzedzie jako
  "Polish topographic map sheets" (mimo CZ/CUZK), `landcover` jako "BDOT10k or
  CORINE" (mimo `--source soilgrids` w tym samym parserze), `cache` jako cache
  "for WMS lookups" (mimo tabeli `sheet_cache` dla arkuszy CZ), a
  `list-sources` opisuje BDOT10k jako "land cover classes (PT)" (mimo 15
  warstw PT+SW od v0.5.0).
- Dowod:
  ```
  _parser.py:24:  description="Tool for parsing and downloading Polish topographic map sheets"
  _parser.py:201: description="Download land cover data from BDOT10k or CORINE"
  _parser.py:375: description="Manage the local SQLite metadata cache for WMS lookups"
  landcover_cmd.py:51: print("              Polish topographic database, land cover classes (PT)")
  ```
  Kontra: `kartograf landcover download --help` ma
  `--source {bdot10k,corine,soilgrids}`, a `Bdot10kProvider.get_available_layers()`
  zwraca 15 warstw (`[... 'PTZB', 'SWRS', 'SWKN', 'SWRM']`).
- Weryfikacja: uruchomione wszystkie `--help` oraz
  `kartograf landcover list-sources`; `get_available_layers()` wywolane w
  `.venv/bin/python` (15 pozycji).
- Proponowana naprawa: zaktualizowac cztery stringi przed wydaniem: "spatial
  data from GUGiK (PL) and CUZK (CZ)", "BDOT10k, CORINE or SoilGrids",
  "metadata cache (WMS lookups, TERYT, sheet index)", "land cover and
  hydrography layers (PT*, SW*)".
- Pewnosc: wysoka

### A6-14 [Important] Opis zasiegu falszywych zapytan do CUZK jest bledny — Krakow/Rzeszow NIE sa objete, Wroclaw TAK
- Plik: `CLAUDE.md`:223-225, `docs/SCOPE.md`:296-300, `docs/DECISIONS.md`:573-579
- Twierdzenie: wszystkie trzy dokumenty opisuja problem jako dotyczacy
  "poludniowej Polski ... okolic Krakowa/Rzeszowa". To jest odwrotnie: Krakow
  (19,9°E) i Rzeszow (~22°E) leza **poza** prostokatem CZ
  (`max_x = 18,86°E`), wiec sa bezpieczne, a objety jest caly pas do 51,06°N i
  na zachod od 18,86°E — m.in. Wroclaw, Opole, Legnica, Walbrzych, Zgorzelec,
  Rybnik. Uzytkownik z Wroclawia (ok. 120 km od granicy) nie ma szans
  przewidziec, ze jego komenda odpali zapytanie do CUZK.
- Dowod — obwiednia w kodzie (`kartograf/sources/registry.py`:316):
  ```python
  extent_wgs84=BBox(12.09, 48.55, 18.86, 51.06, "EPSG:4326"),
  ```
  Pomiar `_countries_for_bbox` na realnych bboxach:
  ```
  Wroclaw   (17.00,51.00,17.05,51.05) -> ('CZ', 'PL')
  Rybnik    (18.40,50.20,18.60,50.30) -> ('CZ', 'PL')
  Katowice  (19.00,50.25,19.05,50.30) -> ('PL',)
  Krakow    (19.90,50.00,19.95,50.07) -> ('PL',)
  ```
- Weryfikacja: uruchomione
  `kartograf.cli.download_cmd._countries_for_bbox` w `.venv/bin/python` dla
  czterech bboxow powyzej.
- Proponowana naprawa: we wszystkich trzech miejscach zamienic "poludniowa
  Polska ... okolic Krakowa/Rzeszowa" na "pas na zachod od 18,86°E i na
  poludnie od 51,06°N — m.in. Wroclaw, Opole, Legnica, Rybnik; Krakow i
  Rzeszow sa poza prostokatem".
- Pewnosc: wysoka

### A6-15 [Important] README nie opisuje dwoch nowych kontraktow wydania: domyslnego `--country auto` i sidecarow
- Plik: `README.md`:36-72 (sekcja "Uzycie"), `README.md`:126-129 (NMT Czechy),
  `README.md`:287 (Status)
- Twierdzenie: sidecar `<plik>.meta.json` powstaje po **kazdym** udanym
  pobraniu (nowy, zawsze widoczny artefakt), a `--country` domyslnie = `auto`
  (zmienia wynik komend PL). README wspomina sidecary tylko mimochodem w
  jednym zdaniu sekcji "Status" i nie mowi o domyslnym `auto` ani slowa —
  mimo ze CLAUDE.md (l. 207, 222-225) i SCOPE (3.2) opisuja oba.
- Dowod — jedyna wzmianka w README (l. 287):
  ```
  **Wersja 0.7.0-dev** - NMT Czechy (... , sidecary metadanych `.meta.json`).
  ```
  Kontra, `CLAUDE.md`:207: "Kazde udane pobranie tworzy sidecar
  `<plik>.meta.json` (metadane CRS/licencja/nodata)"; `--help`:
  "`--country ... (default: auto)`".
- Weryfikacja: pelne czytanie README; `grep -n "meta.json\|country" README.md`
  (2 trafienia sidecara, 3 trafienia `--country`, zadne nie podaje domyslnej).
- Proponowana naprawa: dodac do README krotka sekcje "Wynik pobrania"
  (plik + `<plik>.meta.json`, co niesie sidecar) oraz jedno zdanie przy
  przykladach bbox: "domyslnie `--country auto`; dla czystego PL uzyj
  `--country pl`".
- Pewnosc: wysoka

### A6-16 [Minor] Rozszerzenie `--bbox-crs` o EPSG:5514 i EPSG:3045 nie jest odnotowane w CHANGELOG/SCOPE/README
- Plik: `docs/CHANGELOG.md` (sekcja `[0.7.0]`), `docs/SCOPE.md`:189-218 (2.9)
- Twierdzenie: `--bbox-crs` przyjmuje teraz dwa nowe uklady, ktorych nie bylo
  w v0.6.1; CHANGELOG wymienia `--target-crs` i `--country`, ale nie
  `--bbox-crs`.
- Dowod:
  ```
  v0.6.1: --bbox-crs {EPSG:2180,EPSG:4326,EPSG:2176..2179}
  HEAD:   --bbox-crs {EPSG:2180,EPSG:4326,EPSG:2176..2179,EPSG:5514,EPSG:3045}
  grep w sekcji 0.7.0 po "bbox-crs" -> 0 trafien
  ```
- Weryfikacja: `git show v0.6.1:kartograf/cli/commands.py` vs
  `kartograf download --help`; `grep -in "bbox-crs" docs/CHANGELOG.md`
  w zakresie linii 8-264.
- Proponowana naprawa: dopisac do `### Added` jedna linie o rozszerzeniu
  `--bbox-crs` (razem z uwaga o skladni `--bbox=...` dla ujemnych wspolrzednych
  Krovaka, ktora jest dzis tylko w CLAUDE.md).
- Pewnosc: wysoka

### A6-17 [Minor] ADR-023 nadal ma niepoprawiona delte testow "+244"
- Plik: `docs/DECISIONS.md`:583-584
- Twierdzenie: ADR-023 mowi "1381 testow zielonych (+244 wzgledem stanu po
  etapie 0)", podczas gdy stan po etapie 0 to 1142, czyli delta = +239 —
  a `docs/PROGRESS.md`:435-436 explicite odnotowuje te korekte jako wykonana
  w audycie 2026-08-18.
- Dowod:
  ```
  docs/DECISIONS.md:583-584:  1381 testow zielonych (+244 wzgledem stanu po etapie 0)
  docs/PROGRESS.md:435-436:   delta testow etapu 1 = +239 wzgledem 1142 (nie +244)
  ```
- Weryfikacja: arytmetyka 1381-1142=239; obie liczby (1142, 1381) potwierdzone
  w PROGRESS (l. 182, 271).
- Proponowana naprawa: `+244` -> `+239` w `docs/DECISIONS.md`:584.
- Pewnosc: wysoka

### A6-18 [Minor] `TransformError`/`TransformUnavailableError` nie sa eksportowane ani wymienione w SCOPE 2.10
- Plik: `docs/SCOPE.md`:238-244, `kartograf/__init__.py`:33-38, 86-90
- Twierdzenie: CHANGELOG 0.7.0 (l. 60) reklamuje `TransformError`/
  `TransformUnavailableError` jako czesc nowej polityki transformacji, ale nie
  ma ich w `__all__` — trzeba je importowac z `kartograf.transform.crs`.
  SCOPE 2.10 (jedyna lista publicznego API w docs) ich nie wymienia.
- Dowod: `kartograf/transform/crs.py`:26-31 definiuje obie klasy jako podklasy
  `KartografError`; `grep -n "TransformError" kartograf/__init__.py` -> brak.
- Weryfikacja: `grep`; `python -c "import kartograf; print('TransformError' in
  kartograf.__all__)"` -> False.
- Proponowana naprawa: albo dopisac je do `__all__` i do SCOPE 2.10, albo
  w SCOPE/CHANGELOG jawnie napisac, ze sa dostepne pod
  `kartograf.transform.crs`. Dziedziczenie po `KartografError` sprawia, ze
  `except KartografError` dziala — wiec to nie jest blad, tylko luka opisowa.
- Pewnosc: wysoka

### A6-19 [Minor] DEVELOPMENT_STANDARDS 14.2 uzywa nieistniejacej zmiennej `CLMS_CLIENT_ID`
- Plik: `docs/DEVELOPMENT_STANDARDS.md`:687
- Twierdzenie: przyklad "ALWAYS use environment variables for secrets" pokazuje
  `os.getenv("CLMS_CLIENT_ID")`, a projekt czyta `CLMS_CREDENTIALS` (JSON).
  Ta sama fikcyjna nazwa byla juz usunieta z CLAUDE.md w audycie 2026-08-18
  (`docs/PROGRESS.md`:431-432), ale tutaj zostala.
- Dowod:
  ```
  docs/DEVELOPMENT_STANDARDS.md:687:  client_id = os.getenv("CLMS_CLIENT_ID")
  kartograf/providers/corine.py:212:  creds_env = os.environ.get("CLMS_CREDENTIALS")
  ```
- Weryfikacja: `grep -rn "CLMS_CLIENT_ID" kartograf/` -> 0 trafien;
  `grep -rn "CLMS_CREDENTIALS" kartograf/` -> `providers/corine.py`:201, 212.
- Proponowana naprawa: zamienic przyklad na `os.environ.get("CLMS_CREDENTIALS")`
  albo na neutralna nazwe (`os.getenv("MY_API_KEY")`), zeby nie sugerowac
  nieistniejacego kontraktu.
- Pewnosc: wysoka

### A6-20 [Minor] IMPLEMENTATION_PROMPT 8.1 kaze implementowac zdeprecjonowany alias
- Plik: `docs/IMPLEMENTATION_PROMPT.md`:228
- Twierdzenie: instrukcja "Zaimplementuj metody: download_by_teryt,
  download_by_bbox, download_by_godlo" kieruje nowego providera na alias
  zgodnosciowy zamiast na kanoniczna `download_by_admin_unit`, wprowadzona
  w etapie 0 tego wlasnie wydania.
- Dowod:
  ```
  kartograf/providers/base.py:278: def download_by_admin_unit(...)
  kartograf/providers/base.py:293: def download_by_teryt(...)  """Deprecated alias for download_by_admin_unit."""
  ```
- Weryfikacja: `grep -n "def download_by" kartograf/providers/base.py`.
- Proponowana naprawa: `download_by_admin_unit` (kanoniczna), `download_by_bbox`,
  `download_by_godlo`; alias `download_by_teryt` dziedziczy sie z bazy.
- Pewnosc: wysoka

### A6-21 [Minor] DEVELOPMENT_STANDARDS 10.1 deklaruje progi 80%/60%, ktorych zadne narzedzie nie egzekwuje
- Plik: `docs/DEVELOPMENT_STANDARDS.md`:476-483, `pyproject.toml`:78-79
- Twierdzenie: tabela obiecuje >=80% dla core i >=60% dla CLI/utility, ale
  konfiguracja ma jeden globalny prog `fail_under = 60` — brak podzialu per
  warstwa, wiec regres core ponizej 80% przejdzie bez alarmu.
- Dowod:
  ```
  docs/DEVELOPMENT_STANDARDS.md:478-479: Core >= 80% | CLI, utility >= 60%
  pyproject.toml:79: fail_under = 60
  ```
  Faktyczne pokrycie globalne: 89.53% (pomiar ponizej), wiec dzis prog nie
  jest naruszony — chodzi o brak egzekwowania, nie o naruszenie.
- Weryfikacja: `pytest tests/ --cov=kartograf` -> "Required test coverage of
  60.0% reached. Total coverage: 89.53%".
- Proponowana naprawa: albo dopisac notke "prog 80% dla core jest regula
  przegladowa, narzedziowo egzekwowane jest 60% globalnie", albo dodac
  osobny run coverage z `--cov=kartograf/core --cov=kartograf/providers
  --cov-fail-under=80`.
- Pewnosc: wysoka

### A6-22 [Minor] `docs/PRD.md` jako snapshot v0.6.1 nie nadaje sie na dokument wydania 0.7.0 (osobne ustalenie do decyzji)
- Plik: `docs/PRD.md`:4-14, 494-541, 596-606
- Twierdzenie: PRD swiadomie zatrzymano na v0.6.1 (nota 3.5), co bylo sensowne
  na `develop`, ale w momencie wydania 0.7.0 PRD staje sie jedynym dokumentem
  produktowym opisujacym zakres, ktory juz nie odpowiada wydanej wersji: brak
  CZ/CUZK jako Core Feature, brak sidecarow w Non-Functional Requirements,
  `Status: Production (v0.6.1)`, `__version__ # "0.6.1"`, §7.3 mowi wylacznie
  o macOS Keychain (pomija `CLMS_CREDENTIALS`), a §2.1 juz dzis niesie liczby
  z 0.7.0 (~89% pokrycia) — czyli snapshot i tak nie jest czysty.
- Dowod:
  ```
  docs/PRD.md:7:   **Status:** Production (v0.6.1)
  docs/PRD.md:9-14: PRD pozostaje snapshotem zakresu wydania v0.6.1 ... Zakres CZ/CUZK
                    ... jest celowo nieopisany do czasu wydania 0.7.0
  docs/PRD.md:53:  | Test coverage (core) | >= 80% | ~89% (osiagniety) |   <- liczba z 0.7.0
  docs/PRD.md:539: __version__,  # "0.6.1"
  docs/PRD.md:591: - Credentials stored in macOS Keychain
  ```
- Weryfikacja: pelne czytanie PRD; `grep -rn "CLMS_CREDENTIALS" kartograf/`
  potwierdza, ze zmienna srodowiskowa jest sciezka pierwsza, a Keychain
  fallbackiem (`providers/corine.py`:201-212).
- Proponowana naprawa (rekomendacja): przy wydaniu podniesc PRD do wersji 4.0
  minimalnym nakladem — (1) `Status: Production (v0.7.0)`; (2) nowa sekcja
  **3.2 NMT Czechy (CUZK)** wzorowana na SCOPE 2.2 (DMR 5G/4G, `--country`,
  `--target-crs`, Bpv/EVRF2007), przed obecna 3.2; (3) w §4.1 dorysowac
  `CuzkDmrProvider -> CUZK ArcGIS REST` (dzis diagram nie zna CZ);
  (4) §5 zsynchronizowac z `__all__` (3 brakujace nazwy + `# "0.7.0"`);
  (5) §7.2 dopisac "sidecar `<plik>.meta.json` po kazdym udanym pobraniu";
  (6) §7.3 dopisac `CLMS_CREDENTIALS`. Alternatywa "zostawic snapshot" jest
  dopuszczalna tylko przy jednoczesnym dodaniu do naglowka zdania kierujacego
  na SCOPE 2.2 jako zrodlo prawdy dla 0.7.0 — ale wtedy trzeba usunac z PRD
  liczby z 0.7.0 (pokrycie ~89% w §2.1), bo dzis dokument jest hybryda.
- Pewnosc: wysoka (opis stanu), srednia (wybor wariantu naprawy — to decyzja
  product ownera)

---

## Pozytywy (max 5)

1. Drzewo modulow w `CLAUDE.md` zgadza sie z `find kartograf -name '*.py'`
   co do pliku (jedyne pominiecia to `__init__.py` paczek bez logiki) —
   to najlepiej utrzymany fragment dokumentacji; `SCOPE.md` 4.1,
   `DEVELOPMENT_STANDARDS.md` 7.1 i `IMPLEMENTATION_PROMPT.md` 3 sa z nim
   spojne i poprawnie odsylaja do CLAUDE.md jako zrodla prawdy.
2. Liczby jakosciowe sa prawdziwe i **spojne miedzy dokumentami**: 1402 testy
   (README, CLAUDE-adjacent PROGRESS, SCOPE 6.2, CHANGELOG, DEVELOPMENT_STANDARDS
   7.1) — zmierzone 1402 passed; pokrycie ~89% — zmierzone 89.53%; baseline
   mypy 33 — zmierzone 33.
3. Wszystkie linki wewnetrzne w `.md` (docs/*, docs/research/*,
   docs/superpowers/*) wskazuja na istniejace pliki — 0 martwych odnosnikow.
4. `SCOPE.md` 2.10 odwzorowuje `kartograf/__init__.py.__all__` 1:1 (29 nazw),
   lacznie z nowosciami CZ — to jedyna w pelni aktualna lista publicznego API
   w repo.
5. Sekcja `### Breaking Changes` w CHANGELOG 0.7.0 jest wzorowa: trzy zmiany,
   kazda z tabelka stare/nowe i wskazaniem konsumenta (Hydrograf/Hydrolog);
   tabela mapowania kodow EPSG zgadza sie z `sources/registry.py`:21-24.

---

## Checklista release (przejscie `-dev` -> `0.7.0`)

Miejsca, ktore trzeba zmienic przy nadawaniu wersji. Kolejnosc = zaleznosci.

**Wersja (kod + testy):**
1. `kartograf/__init__.py`:51 — `__version__ = "0.7.0-dev"` -> `"0.7.0"`
2. `tests/test_integration.py`:56 — `assert __version__ == "0.7.0-dev"` -> `"0.7.0"`
3. `tests/test_cli.py`:3660 — `assert __version__ == "0.7.0-dev"` -> `"0.7.0"`
   (bez p. 2-3 suita padnie natychmiast po bumpie)
4. `pyproject.toml`:7 — `version = "0.6.1"` -> `"0.7.0"` (patrz A6-4)

**CHANGELOG:**
5. `docs/CHANGELOG.md`:8 — `## [0.7.0] - Unreleased` -> `## [0.7.0] - RRRR-MM-DD`
6. `docs/CHANGELOG.md`:833 — `[0.7.0]: .../compare/v0.6.1...HEAD` ->
   `.../compare/v0.6.1...v0.7.0`
7. Scalic zdublowane `### Added` / `### Fixed` / `### Tests` (A6-9)
8. Poprawic sciezke `providers/gugik_laz.py` -> `providers/pl/gugik_laz.py` (A6-10)
9. Dodac wpis o domyslnym `--country auto` (A6-3) i o `--bbox-crs` +5514/+3045 (A6-16)

**Dokumenty ze statusem/wersja:**
10. `docs/SCOPE.md`:6 i :449 — "v0.7.0 (Unreleased) ... ostatni wydany tag:
    v0.6.1" -> "v0.7.0 (wydana RRRR-MM-DD)"
11. `docs/SCOPE.md`:12 i :63 — `v0.7.0-dev` -> `v0.7.0`
12. `docs/SCOPE.md`:431-443 — dodac wiersz historii (wersja 3.8, "wydanie 0.7.0")
13. `README.md`:126 — "### NMT Czechy (CUZK, od 0.7.0-dev)" -> "od 0.7.0"
14. `README.md`:287 — "**Wersja 0.7.0-dev**" -> "**Wersja 0.7.0**"
15. `CLAUDE.md`:9 i :70 — "etap 1, v0.7.0-dev" -> "etap 1, v0.7.0"
16. `docs/IMPLEMENTATION_PROMPT.md`:7 i :20 — `v0.7.0-dev` -> `v0.7.0`
17. `docs/DEVELOPMENT_STANDARDS.md`:8 — `(v0.7.0-dev)` -> `(v0.7.0)`
18. `docs/PROGRESS.md`:27 — "wersja `0.7.0-dev`" -> `0.7.0`; sekcja
    "Nastepne kroki" p. 1-3 wymaga przepisania (merge wykonany, push i tag
    do odhaczenia)
19. `docs/PRD.md`:7, :539, :634 — decyzja z A6-22 (podniesc do 0.7.0 albo
    jawnie oznaczyc jako snapshot historyczny)

**Metadane dystrybucji (przed `python -m build`):**
20. `pyproject.toml`:43-44 — dodac `include = ["kartograf*"]`, inaczej `tests`
    trafi do wheela (A6-5)
21. `pyproject.toml`:12-13 — realny adres autora zamiast `piotr@example.com`
22. `pyproject.toml`:8, :15 — `description`/`keywords` o CUZK/CZ i LAZ
23. `requirements.txt` / `requirements-dev.txt` — dosynchronizowac albo usunac (A6-6)

**Blokery tresci (nie sa "-dev", ale nie powinny wyjsc z wydaniem):**
24. `README.md`:49 i `docs/PRD.md`:123/154/183 — przyklady, ktore dzis zwracaja
    exit 1 (A6-1)
25. `kartograf/cli/_parser.py`:252 + `landcover_cmd.py`:53 — `GML` (A6-2)
26. `kartograf/cli/_parser.py`:24/201/375 — teksty `--help` (A6-13)

**Po wydaniu:**
27. `git tag -a v0.7.0` (`docs/DEVELOPMENT_STANDARDS.md` 1.2) + push `develop`
    na origin (74 commity lokalnie wzgledem `v0.6.1`; `docs/PROGRESS.md`:486
    mowi o "71 commitach" wzgledem `origin/develop` — inna baza, obie liczby
    moga byc prawdziwe, ale warto je uzgodnic w PROGRESS po pushu)
28. Zalozyc nastepny cykl: `kartograf/__init__.py` -> `0.8.0-dev`, nowa sekcja
    `## [Unreleased]` w CHANGELOG

---

## Podsumowanie liczbowe: C=3 I=12 M=7
