# A9 — Docstringi i komentarze vs faktyczne zachowanie

Zakres: wszystkie 51 plikow .py w `kartograf/` (znalezione `find kartograf -name '*.py'`),
kazdy przeczytany w calosci: `__init__.py`, `exceptions.py`, `auth/*`, `cache/*`,
`cli/*` (7 plikow), `core/*` (6 plikow), `download/*`, `hydrology/*`,
`landcover/*`, `providers/*` (w tym `pl/*` i `cuzk/*`), `sources/*`,
`transform/*`, `transport/*`.

Metoda: pelne czytanie kazdego pliku (Read); porownanie docstringow modulu/klas/
funkcji publicznych z sygnaturami i faktyczna implementacja; grep po
`docs/PROGRESS.md`/`docs/CHANGELOG.md`/`docs/DECISIONS.md` dla potwierdzenia
kontekstu znanych problemow; uruchomione snippety w `.venv/bin/python`:
- `find_sheets_for_bbox(bbox, target_scale=..., system="banana")` — sprawdzenie
  walidacji parametru `system`
- `inspect.getsource(MetadataCache.get_sheet)` — potwierdzenie stalej TTL
- proba `from kartograf.providers import GugikNmptProvider` / `CuzkDmrProvider`
  — potwierdzenie ImportError
- skrypt AST wyliczajacy publiczne klasy/funkcje/metody bez docstringu
  (tylko top-level modulu i bezposrednie metody klas, bez zagniezdzonych
  domkniec typu `sort_key`/`text`/`collect_descendants`)
- skrypt AST + heurystyka slownikowa PL/EN dla zliczenia jezyka docstringow
  per plik (uzyty wylacznie do oszacowania proporcji, nie jako zrodlo
  pojedynczych ustalen)

Nie sprawdzono: zgodnosci z ruff/mypy (poza zakresem — wykluczone w
instrukcji), testow (inny obszar audytu), plikow `tests/`, `docs/*.md`
(inny agent), literowek stylistycznych bez wplywu na znaczenie.

## Ustalenia

### A9-1 [Important] `find_sheets_for_bbox` nie waliduje parametru `system`
- Plik: kartograf/core/sheet_parser.py:885-931
- Twierdzenie: docstring deklaruje `system` jako ograniczony do `"1992"` lub
  `"2000"`, ale funkcja nie waliduje tej wartosci — kazda inna wartosc jest
  po cichu traktowana jak `"1992"` (PL-1992), bez `ValidationError`.
- Dowod:
  ```
  system : str
      Układ współrzędnych: "1992" (PL-1992) lub "2000" (PL-2000).
      Default: "1992" — pełna kompatybilność wsteczna.
  ...
  if system == "2000":
      ...
      return find_sheets_2000_for_bbox(bbox, target_scale)
  if target_scale not in SheetParser.SCALE_HIERARCHY:
      raise ValidationError(...)
  if bbox.crs not in ("EPSG:2180", "EPSG:4326"):
      raise ValidationError(...)
  ```
  Brak gałęzi `else` odrzucającej nieznane `system`.
- Weryfikacja: uruchomiony snippet:
  `find_sheets_for_bbox(BBox(19.0,50.0,19.1,50.1,"EPSG:4326"), target_scale="1:100000", system="banana")`
  → zwraca `['M-34-63-C']` (wynik PL-1992) zamiast rzucić `ValidationError`.
- Proponowana naprawa: dodać `if system not in ("1992", "2000"): raise
  ValidationError(...)` na początku funkcji, albo doprecyzować docstring, że
  wartości inne niż `"2000"` są traktowane jak `"1992"` (świadomy fallback).
- Pewność: wysoka

### A9-2 [Important] `providers/__init__.py` — docstring i eksporty nieaktualne (brak NMPT/Orto/CUZK)
- Plik: kartograf/providers/__init__.py:1-34
- Twierdzenie: docstring modułu wylicza "Currently supported providers" (6
  pozycji) i `__all__` reeksportuje 7 nazw, ale pomija realnie istniejące,
  wysyłane w `kartograf/__init__.py` providery: `GugikNmptProvider`,
  `GugikOrtoProvider`, `CuzkDmrProvider`/`create_dmr_provider` (cały pakiet
  `providers/cuzk/`, etap 1 / v0.7.0-dev).
- Dowod:
  ```
  - GugikProvider: Downloads NMT data from GUGiK ...
  - GugikLazProvider: Downloads LAZ point-cloud data from GUGiK (via WFS)
  - LandCoverProvider: Abstract base for land cover data providers
  - Bdot10kProvider: Downloads land cover data from BDOT10k (GUGiK)
  - CorineProvider: Downloads CORINE Land Cover data (Copernicus/GIOŚ)
  - SoilGridsProvider: Downloads soil property data from ISRIC SoilGrids
  ```
  (brak wzmianki o NMPT/Orto/CUZK); `__all__` w tym samym pliku też ich nie
  zawiera.
- Weryfikacja: uruchomione importy —
  `from kartograf.providers import GugikNmptProvider` i
  `from kartograf.providers import CuzkDmrProvider` obie kończą się
  `ImportError: cannot import name '...' from 'kartograf.providers'`, mimo że
  `from kartograf import GugikNmptProvider, CuzkDmrProvider` (top-level)
  działa.
- Proponowana naprawa: albo dopisać brakujące importy/eksporty i zaktualizować
  listę w docstringu, albo jawnie zaznaczyć w docstringu, że ten moduł
  reeksportuje tylko podzbiór historyczny, a kanoniczna, kompletna lista jest
  w `kartograf/__init__.py` (częściowo to już sugeruje zdanie o "stable
  package API", ale wyliczenie nazw i tak wprowadza w błąd).
- Pewność: wysoka

### A9-3 [Important] `GugikProvider.download_bbox()` — przykład w docstringu zakłada dziś martwy endpoint WCS EVRF2007
- Plik: kartograf/providers/pl/gugik.py:568-648 (docstring), WCS_ENDPOINTS:81-86
- Twierdzenie: docstring i `Examples` dla `download_bbox()` prezentują domyślne
  użycie (`GugikProvider()` = `vertical_crs="EVRF2007"`) jako działającą ścieżkę,
  ale wg `docs/PROGRESS.md` GUGiK usunął endpoint WCS EVRF2007 (HTTP 404) —
  `download_bbox` dla NMT 1m działa dziś wyłącznie z `vertical_crs="KRON86"`.
  Żaden komentarz w `gugik.py` (ani w `WCS_ENDPOINTS`, ani w docstringu klasy/
  metody) o tym nie informuje.
- Dowod (kod):
  ```
  WCS_ENDPOINTS = {
      "KRON86": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/"
      "DigitalTerrainModelFormatTIFF",
      "EVRF2007": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/"
      "DigitalTerrainModelFormatTIFFEVRF2007",
  }
  ...
  >>> provider = GugikProvider()
  >>> bbox = BBox(min_x=450000, ..., crs="EPSG:2180")
  >>> path = provider.download_bbox(bbox, Path("./area.tif"))
  ```
  Dowod (dokumentacja projektu, `docs/PROGRESS.md:170-177`):
  ```
  Znany problem uslugowy (poza zakresem etapu 0, kod WCS bajt-w-bajt
  niezmieniony): GUGiK usunal endpoint WCS NMT EVRF2007
  (.../WCS/DigitalTerrainModelFormatTIFFEVRF2007 -> HTTP 404 na poziomie
  Apache, takze GetCapabilities); ... Skutek: download_bbox NMT 1m dziala dzis
  tylko z vertical_crs="KRON86". Do osobnego zgloszenia: aktualizacja
  WCS_ENDPOINTS/COVERAGE_IDS w providers/pl/gugik.py ...
  ```
- Weryfikacja: brak dostępu do sieci w tym audycie (wymagane przez zadanie) —
  nie odtwarzano live 404; ustalenie oparte na udokumentowanym, wcześniej
  zweryfikowanym stanie w `docs/PROGRESS.md` (ten sam plik potwierdza status
  jako wciąż nierozwiązany do "osobnego zgłoszenia"). Kod `gugik.py` sam w
  sobie nie ma żadnej wzmianki o tym stanie.
- Proponowana naprawa: dopisać w `gugik.py` (docstring `download_bbox` +
  komentarz przy `WCS_ENDPOINTS["EVRF2007"]`) ostrzeżenie o znanym problemie
  usługowym i odesłanie do `docs/PROGRESS.md`, ewentualnie zmienić przykład w
  docstringu na `vertical_crs="KRON86"`.
- Pewność: średnia (zależy od aktualnego stanu usługi GUGiK, którego nie
  weryfikowano na żywo w tej sesji; ustalenie liczy się do dokumentacji, nie do
  gwarancji sieciowej)

### A9-4 [Important] `MetadataCache` — sidecar arkuszy (`sheet_cache`) pominięty w docstringu modułu; `ttl_seconds` nie dotyczy `sheet_cache`
- Plik: kartograf/cache/metadata.py:1-10 (docstring modułu), 24-28 (stałe), 59-67 (docstring klasy/`__init__`)
- Twierdzenie: (a) docstring modułu opisuje tylko dwie z trzech tabel cache
  (`url_cache`, `teryt_cache`), pomijając `sheet_cache` (indeks arkuszy CZ,
  dodany w etapie 1); (b) docstring `ttl_seconds` w `__init__`/klasie sugeruje,
  że ten parametr kontroluje TTL "cache entries" ogólnie, ale `sheet_cache`
  używa NIEZALEŻNEJ, stałej modułowej `SHEET_TTL_SECONDS = 30 dni`, całkowicie
  ignorując `self._ttl_seconds` przekazane przez użytkownika.
- Dowod:
  ```
  This module provides the MetadataCache class that caches:
  - OpenData URL lookups (godlo -> URL) for NMT/NMPT/Ortofoto providers
  - TERYT code lookups (point -> TERYT) for BDOT10k provider
  ```
  (brak `sheet_cache`)
  ```
  ttl_seconds : int, optional
      Time-to-live for cache entries in seconds. Default is 7 days
      (604800 seconds). Entries older than TTL are considered stale.
  ...
  def get_sheet(self, system: str, godlo: str) -> dict | None:
      """Zwroc zdekodowany payload arkusza albo None (brak/wygasly)."""
      ...
      if time.time() - cached_at >= SHEET_TTL_SECONDS:   # NIE self._ttl_seconds
  ```
- Weryfikacja: `inspect.getsource(MetadataCache.get_sheet)` potwierdza użycie
  modułowej stałej `SHEET_TTL_SECONDS`, nie `self._ttl_seconds` — instancja
  utworzona jako `MetadataCache(ttl_seconds=1)` nadal wygasi wpisy
  `sheet_cache` dopiero po 30 dniach, nie po 1 sekundzie.
- Proponowana naprawa: dopisać `sheet_cache` do listy w docstringu modułu;
  w docstringu `__init__`/klasy dodać zdanie, że `ttl_seconds` NIE dotyczy
  `sheet_cache`, który ma stałe, oddzielne TTL 30 dni (uzasadnione w komentarzu
  przy stałej, ale nie w publicznym docstringu parametru).
- Pewność: wysoka

### A9-5 [Important] `FileStorage.delete()` — docstring nie wspomina o kasowaniu sidecara `.meta.json`
- Plik: kartograf/download/storage.py:313-335
- Twierdzenie: publiczny docstring metody `delete()` opisuje wyłącznie
  usunięcie pliku danych ("Delete file for given godło" / Returns: "True if
  file was deleted"), ale implementacja dodatkowo usuwa towarzyszący sidecar
  `<plik>.meta.json` — efekt uboczny nieudokumentowany w docstringu (jest tylko
  komentarz inline tłumaczący *dlaczego*, nie *co*, w publicznym API).
- Dowod:
  ```
  def delete(self, godlo: str, ext: str = ".asc") -> bool:
      """
      Delete file for given godło.
      ...
      Returns
      -------
      bool
          True if file was deleted, False if it didn't exist
      """
      path = self.get_path(godlo, ext)
      if path.exists():
          path.unlink()
          # Sidecar metadanych nie moze przezyc pliku danych.
          path.with_name(path.name + ".meta.json").unlink(missing_ok=True)
          return True
      return False
  ```
- Weryfikacja: nie weryfikowano dodatkowo (czytanie kodu wystarcza — brak
  gałęzi warunkowej pomijającej kasowanie sidecara).
- Proponowana naprawa: dopisać do docstringu zdanie w stylu "Also deletes the
  companion `<file>.meta.json` sidecar, if present."
- Pewność: wysoka

### A9-6 [Minor] Dwujęzyczność docstringów (PL/EN) w całym pakiecie
- Plik: cały `kartograf/` (zbiorczo)
- Twierdzenie: norma (`docs/DEVELOPMENT_STANDARDS.md` §9.4) wymaga
  docstringów wyłącznie po angielsku, ale repo jest w praktyce dwujęzyczne —
  starszy kod (etap 0 i wcześniej: `providers/pl/*`, `providers/base.py`,
  `download/*`, `hydrology/*`, `landcover/*`, `cli/parse_cmd.py` itd.) jest
  konsekwentnie po angielsku, a nowszy kod (etap 1, CZ: `providers/cuzk/*`,
  `sources/*`, `transform/crs.py`, `transport/*`, `core/parser_2000.py`,
  `core/parser_registry.py`, `core/parser_tm33.py`, `core/sheet_parser.py`,
  `cache/metadata.py` (częściowo), `cli/download_cmd.py`) jest w większości po
  polsku.
- Dowod (heurystyczne zliczenie docstringów wg słownika PL/EN + AST, ~510
  docstringów łącznie): PL ≈ 155, EN ≈ 307, mieszane/niejednoznaczne ≈ 48.
  Przykład tego samego pliku niespójnego wewnętrznie:
  `core/parser_2000.py` — docstring modułu po angielsku ("This module
  provides the Parser2000 class..."), ale większość docstringów metod po
  polsku ("Inicjalizuje parser dla podanego godla PL-2000...").
- Weryfikacja: skrypt AST + słownikowa heurystyka PL/EN (przybliżenie, nie
  metoda formalna — liczby orientacyjne, nie precyzyjny audyt lingwistyczny).
- Proponowana naprawa: decyzja projektowa — albo jawnie udokumentować w
  `DEVELOPMENT_STANDARDS.md`, że kod etapu 1 (CZ) świadomie pisany po polsku
  (jak reszta dokumentacji projektu) i złagodzić §9.4, albo zaplanować
  stopniowe tłumaczenie nowego kodu na angielski zgodnie z obowiązującą normą.
  Nie zgłaszam per-plik, żeby nie generować dziesiątek identycznych ustaleń.
- Pewność: wysoka (co do faktu dwujęzyczności), niska (co do dokładnych liczb)

### A9-7 [Minor] Publiczne metody/funkcje bez docstringu
- Plik: zbiorczo (lista lokalizacji)
- Twierdzenie: standard (§9.2, §15 checklist: "Docstrings dla publicznych
  funkcji/klas") wymaga docstringów dla publicznych klas/metod/funkcji; te
  pozycje ich nie mają (funkcje pomocnicze zagnieżdżone wewnątrz innych funkcji
  — jak `sort_key`, `text`, `collect_descendants` — są pominięte jako
  nie-publiczne w praktyce, mimo braku podkreślenia w nazwie).
- Lista lokalizacji:
  - `kartograf/auth/proxy.py:324` — funkcja modułowa `main()`
  - `kartograf/providers/cuzk/dmr.py:158` — `CuzkDmrProvider.name` (property)
  - `kartograf/providers/cuzk/dmr.py:162` — `CuzkDmrProvider.base_url` (property)
  - `kartograf/providers/cuzk/dmr.py:166` — `CuzkDmrProvider.default_extension` (property)
  - `kartograf/providers/cuzk/dmr.py:170` — `CuzkDmrProvider.resolution` (property)
- Weryfikacja: skrypt AST (`ast.get_docstring`) po całym `kartograf/`,
  ograniczony do funkcji top-level modułu i metod bezpośrednio w klasach
  (wykluczone domknięcia zagnieżdżone w innych funkcjach).
- Proponowana naprawa: dopisać jednolinijkowe docstringi (wzór: analogiczne
  property w `GugikProvider`/`GugikOrtoProvider`, np. `"""Return current
  resolution."""`).
- Pewność: wysoka

## Inwentarz

| Plik | Docstring modulu OK? | Liczba niezgodnosci | Jezyk |
|---|---|---|---|
| kartograf/__init__.py | Tak | 0 | EN |
| kartograf/exceptions.py | Tak | 0 | EN |
| kartograf/auth/__init__.py | Tak | 0 | EN |
| kartograf/auth/client.py | Tak | 0 | EN |
| kartograf/auth/proxy.py | Tak | 0 (patrz A9-7) | EN |
| kartograf/cache/__init__.py | Tak | 0 | EN |
| kartograf/cache/metadata.py | Czesciowo (A9-4) | 2 | mix |
| kartograf/cli/__init__.py | Tak | 0 | EN |
| kartograf/cli/_parser.py | Tak | 0 | EN |
| kartograf/cli/cache_cmd.py | Tak | 0 | EN |
| kartograf/cli/commands.py | Tak | 0 | mix |
| kartograf/cli/download_cmd.py | Tak | 0 | mix |
| kartograf/cli/landcover_cmd.py | Tak | 0 | EN |
| kartograf/cli/parse_cmd.py | Tak | 0 | EN |
| kartograf/cli/soilgrids_cmd.py | Tak | 0 | EN |
| kartograf/core/__init__.py | Tak (ogolnikowy, nie odswiezony po dodaniu parser_2000/tm33/registry/geometry, ale nie mylacy) | 0 | EN |
| kartograf/core/geometry.py | Tak | 0 | EN |
| kartograf/core/parser_2000.py | Tak | 0 | mix |
| kartograf/core/parser_registry.py | Tak | 0 | PL |
| kartograf/core/parser_tm33.py | Tak | 0 | PL |
| kartograf/core/sheet_parser.py | Czesciowo (A9-1) | 1 | mix |
| kartograf/download/__init__.py | Tak | 0 | EN |
| kartograf/download/manager.py | Tak | 0 | EN |
| kartograf/download/storage.py | Czesciowo (A9-5) | 1 | EN |
| kartograf/hydrology/__init__.py | Tak | 0 | EN |
| kartograf/hydrology/hsg.py | Tak | 0 | EN |
| kartograf/landcover/__init__.py | Tak | 0 | EN |
| kartograf/landcover/manager.py | Tak | 0 | EN |
| kartograf/providers/__init__.py | Nie (A9-2) | 1 | EN |
| kartograf/providers/base.py | Tak | 0 | mix |
| kartograf/providers/corine.py | Tak | 0 | EN |
| kartograf/providers/cuzk/__init__.py | Tak | 0 | PL |
| kartograf/providers/cuzk/client.py | Tak | 0 | PL |
| kartograf/providers/cuzk/dmr.py | Tak | 0 (patrz A9-7: 4 property bez docstringu) | PL |
| kartograf/providers/cuzk/sheets.py | Tak | 0 | PL |
| kartograf/providers/pl/__init__.py | Tak | 0 | PL |
| kartograf/providers/pl/bdot10k.py | Tak | 0 | EN |
| kartograf/providers/pl/gugik.py | Czesciowo (A9-3) | 1 | EN |
| kartograf/providers/pl/gugik_laz.py | Tak | 0 | EN |
| kartograf/providers/pl/gugik_nmpt.py | Tak | 0 | EN |
| kartograf/providers/pl/gugik_orto.py | Tak | 0 | EN |
| kartograf/providers/soilgrids.py | Tak | 0 | EN |
| kartograf/sources/__init__.py | Tak | 0 | PL |
| kartograf/sources/descriptor.py | Tak | 0 | PL |
| kartograf/sources/registry.py | Tak | 0 | PL |
| kartograf/sources/sidecar.py | Tak | 0 | PL |
| kartograf/transform/__init__.py | Tak | 0 | PL |
| kartograf/transform/crs.py | Tak | 0 | PL |
| kartograf/transport/__init__.py | Tak | 0 | PL |
| kartograf/transport/http.py | Tak | 0 | PL |
| kartograf/transport/mosaic.py | Tak | 0 | PL |

## Pozytywy (krotko, max 5 punktow)
- `kartograf/providers/cuzk/*` i `kartograf/transform/crs.py`: docstringi
  gesto opisuja "dlaczego" (np. ADR-024, przyczyny odrzucen transformacji),
  dokladnie zgodne z faktycznym kodem — najbardziej rzetelna czesc bazy.
- `download_sheet()` (manager.py): `Returns`/`Raises` scisle zgodne z
  faktyczna sygnatura (`Path | list[Path]`, `DownloadError`, `ParseError`).
- Konsekwentne uzycie stylu NumPy (`Parameters`/`Returns`/`Raises`) w calym
  kodzie "polskim" GUGiK/BDOT10k/CORINE/SoilGrids (etap 0).
- Limity czasowe (30s GUGiK NMT, 60s Land Cover/Orto/LAZ) i domyslne
  `max_workers` (1 biblioteka / 4 CLI) sa spojne miedzy docstringami,
  sygnaturami i `CLAUDE.md`.
- `GugikOrtoProvider`/`GugikLazProvider`: docstringi jawnie tlumacza
  nietypowe decyzje (dedykowana sesja HTTP, WMS 401 dla LAZ) zamiast je
  przemilczec.

## Podsumowanie liczbowe: C=0 I=5 M=2
