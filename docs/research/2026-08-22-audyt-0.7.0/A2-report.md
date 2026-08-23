# A2 — Poprawnosc logiczna: providery PL, download, cache

Zakres (przeczytane w calosci):
- `kartograf/providers/base.py`
- `kartograf/providers/pl/__init__.py`, `gugik.py`, `gugik_nmpt.py`, `gugik_orto.py`, `gugik_laz.py`, `bdot10k.py`
- `kartograf/download/manager.py`, `kartograf/download/storage.py`
- `kartograf/cache/metadata.py`
Pomocniczo (czytane fragmentami, dla ustalenia osiagalnosci sciezek): `kartograf/cli/download_cmd.py`,
`kartograf/landcover/manager.py`, `kartograf/transport/http.py`, `tests/test_metadata_cache.py`,
`tests/test_cli.py`, `docs/PROGRESS.md`, `README.md`.

Metoda:
- pelne czytanie 10 plikow zakresu (`cat`/`awk` z numeracja), grep za osiagalnoscia sciezek
  (`_create_provider_and_storage`, `DownloadResult`, `MetadataCache`, `with_suffix`),
- 9 celowanych snippetow offline w `.venv/bin/python -c`/heredoc z mockami `requests` i sztucznym GPKG/ZIP
  (bez sieci; zadne zapytanie nie poszlo do GUGiK),
- `.venv/bin/python -m pytest tests/test_metadata_cache.py tests/test_parallel_download.py tests/test_storage.py
  tests/test_gugik_provider.py tests/test_gugik_nmpt.py tests/test_gugik_orto.py tests/test_gugik_laz.py
  tests/test_download_manager.py tests/test_landcover.py tests/test_wms_layer_validation.py -q -p no:cacheprovider`
  -> **441 passed** (zielono; wszystkie ponizsze ustalenia to luki, nie znane awarie).

Nie sprawdzono:
- wszystkiego, co wymaga realnej sieci (zywotnosc endpointow GUGiK WCS/WMS/WFS, faktyczna tresc
  GetFeatureInfo, paginacja WFS na realnym zbiorze >1000 kafli) — brak gwarancji sieci, oznaczone
  wprost w ustaleniu A2-8,
- zachowania na Windows (`Path.rename` vs `os.replace` przy nadpisywaniu) — brak platformy,
- `providers/cuzk/*`, `sources/*`, `transform/*` — poza przydzielonym obszarem (dotknieto tylko
  `transport/http.py` dla porownania wzorca retry).

## Ustalenia

### A2-1 [Critical] MetadataCache: nieblokowane odczyty na wspoldzielonym polaczeniu SQLite zwracaja URL innego arkusza
- Plik: `kartograf/cache/metadata.py`:151-158 (`get_url`), 236-240 (`get_teryt`), 289-293 (`get_sheet`), 69-72 (`connect(check_same_thread=False)`)
- Twierdzenie: zapisy sa chronione `self._write_lock`, ale wszystkie odczyty wykonuja
  `self._conn.execute(...)` bez blokady na wspoldzielonym polaczeniu, przez co przy dostepie z wielu
  watkow `get_url()` potrafi zwrocic URL **innego godla**, `None` mimo trafienia, albo rzucic
  `InterfaceError`/`TypeError`/`ValueError`.
- Dowod:
  ```python
  # metadata.py:151 — brak `with self._write_lock:` wokol odczytu
  cursor = self._conn.execute(
      """SELECT url, cached_at FROM url_cache
         WHERE godlo=? AND resolution=? AND vertical_crs=? AND product=?""",
      (godlo, resolution, vertical_crs, product),
  )
  row = cursor.fetchone()
  ```
  Wejscie: 300 wpisow `G0..G299` -> `https://opendata/G<i>.asc`, 8 watkow czytajacych
  te same klucze, **zero zapisow rownolegle**. Wyjscie:
  ```
  A) same odczyty, 8 watkow: OK=1028, wyjatki={'InterfaceError': 287, 'TypeError': 164, 'ValueError': 24}, ZLA_WARTOSC=897
     (w tym ~331 przypadkow zwrocenia URL-a INNEGO arkusza, np. 'https://opendata/G1.asc' na zapytanie o inny klucz)
  ```
  Skutek na sciezce uzytkownika: `GugikProvider._get_opendata_url` (gugik.py:448-454) zwraca ten URL
  bez zadnej weryfikacji, a `DownloadManager` zapisuje pobrany plik pod sciezka **zadanego** godla i
  wystawia sidecar z `request.godlo` = zadane godlo -> plik z innego arkusza z poprawnie wygladajaca
  nazwa i metadanymi. Dodatkowo `TypeError`/`ValueError` z cache'a nie sa `DownloadError`, wiec
  w trybie sekwencyjnym przerywaja calosc pobierania hierarchii (patrz A2-4).
- Weryfikacja: uruchomiony snippet offline (`.venv/bin/python`, Python 3.13.5, sqlite3 3.46.1) — wynik wyzej.
  Kontrola naprawy: ten sam scenariusz z odczytem opakowanym w `with c._write_lock:` daje
  `OK=2400, wyjatki={}, zle=0`. Osiagalnosc: obecne CLI PL **nie** wstrzykuje cache do providerow
  (`grep -rn "MetadataCache\|cache=" kartograf/cli/*.py` -> tylko galaz CZ, jednowatkowa), wiec dzis
  bug jest osiagalny przez publiczne API biblioteki: `create_nmt_provider(cache=MetadataCache())`
  + `DownloadManager(max_workers>1)`. Klasa reklamuje watkowosc wprost
  (docstring modulu: "WAL mode for concurrent access support"), a `tests/test_metadata_cache.py::TestThreadSafety`
  testuje **wylacznie zapisy** (`test_concurrent_set_url_no_errors`, `set_teryt`, `clear`) — brak
  jakiegokolwiek testu rownoleglych odczytow, stad falszywe poczucie bezpieczenstwa.
- Proponowana naprawa: objac `with self._write_lock:` cale odczyty w `get_url`/`get_teryt`/`get_sheet`
  (od `execute` do `fetchone()` wlacznie) albo — lepiej — przejsc na polaczenie per watek
  (`threading.local()` + `sqlite3.connect` na watek); przy okazji dodac do `TestThreadSafety` test
  rownoleglych `get_url` porownujacy zwrocona wartosc z oczekiwana.
- Pewnosc: wysoka

### A2-2 [Critical] DownloadManager z jawnym `provider=` a bez `storage=` zapisuje NMPT/Orto do katalogu NMT i moze zwrocic plik NMT jako NMPT
- Plik: `kartograf/download/manager.py`:186 (`self._storage = storage or FileStorage(output_dir, resolution=resolution)`), 262-274 (`download_sheet`)
- Twierdzenie: konstruktor nie uzgadnia `provider` ze `storage` — przy podaniu samego `provider`
  (parametr publiczny, udokumentowany) katalog wynikowy jest wybierany wylacznie z `resolution`,
  wiec NMPT laduje w `nmt_1m/` z ta sama nazwa i rozszerzeniem co NMT; przy domyslnym
  `skip_existing=True` manager zwraca istniejacy plik **NMT** jako wynik pobrania NMPT, nie odpytujac serwera
  i nie wystawiajac sidecara.
- Dowod:
  ```
  NMT path : nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
  NMPT path: nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
  KOLIZJA  : True
  download_sheet(NMPT) -> nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc | tresc: NMT DATA
  sidecar istnieje: False
  ```
- Weryfikacja: uruchomiony snippet offline — `DownloadManager(output_dir=tmp, provider=GugikProvider())`
  tworzy plik z trescia "NMT DATA", nastepnie `DownloadManager(output_dir=tmp, provider=GugikNmptProvider()).download_sheet(godlo)`
  zwraca dokladnie ten plik. CLI jest odporne, bo `_create_provider_and_storage`
  (`cli/download_cmd.py`:64-78) zawsze zwraca **pare** provider+storage; dziura dotyczy publicznego API
  biblioteki (`README.md`:107 wymienia `GugikNmptProvider`/`GugikOrtoProvider` jako publiczne API,
  a `provider=` jest udokumentowanym parametrem `DownloadManager`).
- Proponowana naprawa: gdy `storage is None`, wyprowadzic podkatalog z providera (np. z
  `provider.descriptor_key` przez `sources.registry`, tak jak robi to `FileStorage(subdir=...)` dla CZ),
  a nie z samego `resolution`; alternatywnie odrzucic `provider=` bez `storage=` wyjatkiem `ValidationError`.
- Pewnosc: wysoka

### A2-3 [Critical] `download_hierarchy` obiecuje w docstringu `Raises DownloadError`, a polyka bledy — 100% niepowodzen konczy sie exit code 0
- Plik: `kartograf/download/manager.py`:305-313 (docstring), 437-450 (`except DownloadError` -> `continue`), 452-457 (log)
- Twierdzenie: publiczna metoda deklaruje wyjatek, ktorego nigdy nie rzuca, i zwraca `list[Path]` bez
  informacji o niepowodzeniach; wywolujacy (w tym CLI) nie ma jak odroznic pelnego sukcesu od pelnej porazki.
- Dowod:
  ```
  Raises
  ------
  DownloadError
      If any download fails          # manager.py:307-310 — kontrakt niedotrzymany
  ```
  ```
  Failed to download N-34-130-D-d-2-1: brak pokrycia
  ... (4 z 4 arkuszy)
  exit code przy 100% niepowodzen: 0
  ```
  Dla porownania, ta sama awaria na pojedynczym arkuszu 1:10000:
  ```
  pojedynczy arkusz 1:10000, niepowodzenie -> exit code: 1
  ```
  Dodatkowo log `f"{len(downloaded_paths)}/{total} successful"` (manager.py:452-455) zlicza jako
  "successful" rowniez arkusze **pominiete** (`downloaded_paths.append(target_path)` w galezi skipped,
  manager.py:409 oraz 510-511).
- Weryfikacja: dwa uruchomione snippety offline z `main(["download", ...])` i providerem-mockiem
  rzucajacym `DownloadError` — wyniki wyzej. Skutek: `kartograf download N-34-130-D-d-2` (bardzo
  typowe wywolanie, godlo grubsze niz 1:10000 rozwijane do hierarchii) sygnalizuje skryptom sukces,
  mimo ze nie powstal ani jeden plik.
- Proponowana naprawa: zwracac z `download_hierarchy` istniejacy juz `DownloadResult`
  (succeeded/failed/skipped — patrz A2-5) zamiast `list[Path]`, poprawic docstring, i uzaleznic
  exit code CLI od `len(result.failed)`; minimalnie: doprowadzic komunikat i kod wyjscia do stanu,
  w ktorym "0 pobranych plikow przy N bledach" konczy sie kodem != 0.
- Pewnosc: wysoka

### A2-4 [Important] Rozjazd obslugi bledow: tryb sekwencyjny przerywa cala hierarchie na wyjatku spoza DownloadError, rownolegly go izoluje
- Plik: `kartograf/download/manager.py`:394/437 (`_download_hierarchy_sequential`, tylko `except DownloadError`) vs 366-378 + 485-504 (`_download_single_sheet_task` + `except Exception` w `as_completed`)
- Twierdzenie: dla identycznego wejscia wynik zalezy od `max_workers` — przy 1 (domyslna wartosc
  biblioteki) pierwszy wyjatek niebedacy `DownloadError` przerywa pobieranie i pozostale arkusze nie
  sa nawet probowane; przy >1 (domyslna wartosc CLI to 4) ten sam wyjatek jest policzony jako "failed",
  a reszta arkuszy pobiera sie normalnie.
- Dowod (provider rzuca `ConnectionResetError` na pierwszym arkuszu z czterech):
  ```
  workers=1: WYJATEK ConnectionResetError: nagly reset TCP; prob=1 (reszta arkuszy NIE probowana)
  workers=4: OK, pobrano 3/4, prob=4
  ```
- Weryfikacja: uruchomiony snippet offline (`DownloadManager(max_workers=1|4)` +
  `MagicMock(spec=GugikProvider)`), wynik wyzej. Klasy wyjatkow, ktore realnie tedy przechodza:
  `OSError` z zapisu na dysk (`_save_response`), `ParseError` z `FileStorage.get_path`, oraz
  `TypeError`/`ValueError`/`InterfaceError` z cache'a (A2-1).
- Proponowana naprawa: wyciagnac jedna wspolna funkcje obslugi pojedynczego arkusza
  (`_download_single_sheet_task` juz istnieje) i uzywac jej rowniez w petli sekwencyjnej, lapiac
  `Exception` w obu trybach — zniknie rozjazd i podwojenie logiki progresu.
- Pewnosc: wysoka

### A2-5 [Important] `DownloadResult` jest w publicznym `__all__`, ale nigdy nie powstaje — martwy typ udajacy aktywny
- Plik: `kartograf/download/manager.py`:59-86 (definicja), `kartograf/__init__.py`:31 i 67 (eksport)
- Twierdzenie: dataclass opisany jako "Result of a batch/hierarchy download operation" nie jest
  konstruowany w zadnym miejscu biblioteki; jedyne uzycia to testy, ktore tworza go recznie — przez co
  dokumentowany sposob odczytania `failed`/`skipped` nie istnieje (i wprost blokuje naprawe A2-3).
- Dowod:
  ```
  $ grep -rn "DownloadResult(" kartograf/ | grep -v "class DownloadResult"
  (brak wynikow, exit=1)
  $ grep -rn "DownloadResult" --include=*.py kartograf/
  kartograf/__init__.py:31: from kartograf.download.manager import DownloadManager, DownloadProgress, DownloadResult
  kartograf/__init__.py:67: "DownloadResult",
  kartograf/download/manager.py:60: class DownloadResult:
  ```
- Weryfikacja: uruchomiony grep (wynik wyzej); `tests/test_parallel_download.py:28-56` konstruuje
  obiekt recznie, wiec zielone testy nie wykrywaja, ze produkcja go nie uzywa.
- Proponowana naprawa: albo zwracac `DownloadResult` z `download_hierarchy` (rekomendowane, spina sie
  z A2-3), albo usunac typ z `__all__` i z modulu wraz z jego testami, zeby publiczne API nie obiecywalo
  nieistniejacej funkcji.
- Pewnosc: wysoka

### A2-6 [Important] `Bdot10kProvider` zwraca sciezke do pliku, ktorego nie utworzyl (rozjazd `with_suffix(".gpkg")` vs wartosc zwracana)
- Plik: `kartograf/providers/pl/bdot10k.py`:609 (`output_gpkg = output_path.with_suffix(".gpkg")`) vs 515 (`return output_path`)
- Twierdzenie: przy `format="GPKG"` dane sa zapisywane pod `output_path.with_suffix(".gpkg")`, ale
  `_download_with_retry` zwraca oryginalny `output_path`; gdy wywolujacy poda inne rozszerzenie (lub
  brak rozszerzenia), dostaje sciezke do nieistniejacego pliku, a sidecar/dalsze przetwarzanie zostana
  przypiete do pustego miejsca.
- Dowod (wejscie: `download_by_admin_unit("1465", tmp/"powiat_1465.zip")`, odpowiedz to prawidlowy ZIP z GPKG):
  ```
  zwrocono : /tmp/.../powiat_1465.zip
  istnieje : False
  faktycznie zapisano: ['PTLZ.gpkg', 'powiat_1465.gpkg']
  ```
- Weryfikacja: uruchomiony snippet offline (sztuczny GPKG zbudowany przez `sqlite3`, spakowany do ZIP,
  `session` = `MagicMock`). Przez CLI nieosiagalne — `LandCoverManager._generate_output_path`
  (`landcover/manager.py`:405-417) zawsze generuje nazwy `.gpkg`, a `cli/landcover_cmd.py`:154 wystawia
  tylko katalog wyjsciowy; dziura dotyczy publicznego API providera.
- Proponowana naprawa: `_extract_gpkg_from_zip` powinien zwracac faktycznie zapisana sciezke, a
  `_download_with_retry` zwracac ja zamiast `output_path` (albo wymuszac `.gpkg` juz w
  `download_by_admin_unit` i odrzucac niezgodne rozszerzenie `ValidationError`).
- Pewnosc: wysoka

### A2-7 [Important] Fallback `urls[0]` w `_get_opendata_url` akceptuje i cache'uje URL cudzego arkusza
- Plik: `kartograf/providers/pl/gugik.py`:536-539 (NMT), `kartograf/providers/pl/gugik_orto.py`:373-375 (Orto)
- Twierdzenie: gdy zaden z URL-i zwroconych przez GetFeatureInfo nie zawiera zadanego godla, kod bierze
  pierwszy z brzegu bez jakiejkolwiek kontroli zasiegu i **zapisuje go w cache pod kluczem zadanego godla**,
  co utrwala potencjalnie bledne przypisanie na caly TTL (7 dni).
- Dowod:
  ```python
  # gugik.py:536-539
  logger.debug(f"Found OpenData URL (no exact match): {urls[0]}")
  self._cache_url(godlo, urls[0])
  return urls[0]
  ```
  Wejscie: zapytanie o `N-34-130-D-d-2-4`, odpowiedz WMS zawiera wylacznie
  `.../74253_1234567_M-34-63-A-a-1-1.asc` (arkusz spod Krakowa, ~400 km dalej). Wyjscie:
  ```
  V7 zwrocony URL dla N-34-130-D-d-2-4 -> 74253_1234567_M-34-63-A-a-1-1.asc
  V7 zapisany w cache pod kluczem godla: N-34-130-D-d-2-4
  ```
- Weryfikacja: uruchomiony snippet offline z podstawiona odpowiedzia WMS i `MagicMock` jako cache.
  Nie weryfikowano, jak czesto GUGiK realnie zwraca URL o godle innym niz zapytane (wymagaloby sieci) —
  fallback istnieje wlasnie dlatego, ze nazwy blokow dostawczych bywaja inne niz zadany arkusz, ale
  kod nie odroznia "inna nazwa, ten sam obszar" od "inny obszar".
- Proponowana naprawa: przy braku dopasowania nazwy zweryfikowac przecinanie sie zasiegu (jak
  `GugikLazProvider._intersects`, gugik_laz.py:457-472) albo przynajmniej **nie** zapisywac URL-a
  fallbackowego do cache i podniesc `logger.debug` do `logger.warning`.
- Pewnosc: srednia

### A2-8 [Important] Domyslny endpoint WCS NMT EVRF2007 jest martwy (404 wg wlasnej dokumentacji projektu), a `download_bbox` uzywa go domyslnie; README/SCOPE/CLAUDE.md o tym milcza
- Plik: `kartograf/providers/pl/gugik.py`:84-85 (`WCS_ENDPOINTS["EVRF2007"]`), 167 (`vertical_crs: str = "EVRF2007"` — domyslne), `kartograf/download/manager.py`:144
- Twierdzenie: `DownloadManager().download_bbox(...)` w domyslnej konfiguracji buduje URL do endpointu,
  ktory wedlug `docs/PROGRESS.md` zwraca HTTP 404, wiec konczy sie `DownloadError` po 3 probach i ~6 s
  uspienia; ograniczenie nie jest wymienione ani w README, ani w `docs/SCOPE.md`, ani w sekcji
  "Ograniczenia" `CLAUDE.md` (ktora wspomina jedynie brak WCS dla 5m).
- Dowod:
  ```
  V4 domyslny WCS URL: https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFFEVRF2007
  ```
  ```
  docs/PROGRESS.md:170-177
  **Znany problem uslugowy (...):** GUGiK usunal endpoint WCS NMT EVRF2007
  (`.../WCS/DigitalTerrainModelFormatTIFFEVRF2007` -> HTTP 404 na poziomie Apache, takze GetCapabilities);
  (...) Skutek: `download_bbox` NMT 1m dziala dzis tylko z `vertical_crs="KRON86"`.
  ```
- Weryfikacja: URL zbudowany offline snippetem (`_construct_wcs_url`) — wynik wyzej. Status 404 samego
  endpointu **nie weryfikowano** (brak gwarancji sieci); zrodlem twierdzenia jest `docs/PROGRESS.md`:170-177,
  potwierdzone niezaleznie w pamieci projektu.
- Proponowana naprawa: przed wydaniem 0.7.0 albo dodac walidacje endpointu WCS analogiczna do
  `_get_validated_layers` z czytelnym komunikatem "uzyj --vertical-crs KRON86", albo — minimalnie —
  dopisac ograniczenie do `README.md`, `docs/SCOPE.md` i sekcji "Ograniczenia" w `CLAUDE.md`.
- Pewnosc: srednia (kod: wysoka, stan uslugi: z dokumentacji projektu, bez ponownej weryfikacji live)

### A2-9 [Important] Bledy serwera WMS (5xx) sa raportowane uzytkownikowi jako "brak pokrycia danymi"
- Plik: `kartograf/providers/pl/gugik.py`:541-551, analogicznie `gugik_orto.py`:377-386
- Twierdzenie: `except requests.RequestException: continue` traktuje awarie uslugi identycznie jak brak
  danych, wiec po przejsciu wszystkich warstw uzytkownik dostaje `DownloadError` sugerujacy, ze obszar
  nie ma pokrycia — co kieruje diagnoze w zla strone (i, w polaczeniu z A2-3, moze cicho wyzerowac
  cala hierarchie).
- Dowod (wejscie: kazde zapytanie WMS rzuca `requests.HTTPError("500 Server Error")`):
  ```
  V5 komunikat: No NMT 1m data available for N-34-130-D-d-2-4 (vertical_crs=EVRF2007).
                This area may not have 1m coverage in GUGiK. Chec...
  ```
- Weryfikacja: uruchomiony snippet offline (`session.get.side_effect = requests.HTTPError`).
- Proponowana naprawa: zliczac bledy transportowe osobno od "warstwa odpowiedziala, ale bez URL-a"
  i gdy **zadna** warstwa nie odpowiedziala poprawnie, rzucac `DownloadError` z trescia wskazujaca na
  awarie uslugi (z ostatnim bledem w komunikacie), a nie na brak pokrycia.
- Pewnosc: wysoka

### A2-10 [Minor] Martwa galaz `laz` w `_create_provider_and_storage` produkujaca niekompatybilna pare provider+manager
- Plik: `kartograf/cli/download_cmd.py`:74-78 (galaz), 529-530 (wczesniejszy `return _cmd_download_laz(args)`)
- Twierdzenie: wszystkie trzy wywolania `_create_provider_and_storage` (linie 556, 762, 1386) leza za
  wczesnym returnem dla `product == "laz"`, wiec galaz jest nieosiagalna; jest przy tym pulapka, bo
  `GugikLazProvider.download(url, ...)` ma inna semantyke pierwszego argumentu niz
  `BaseProvider.download(godlo, ...)`, wiec `DownloadManager` wyslalby godlo jako URL.
- Dowod: `grep -rn "_create_provider_and_storage" kartograf/` -> definicja + 3 wywolania (556/762/1386),
  wszystkie po linii 529; `tests/test_cli.py::TestCreateProviderAndStorage` (768-804) pokrywa `nmt`,
  `nmpt`, `orto` — galezi `laz` nie testuje nikt.
- Weryfikacja: grep + odczyt kolejnosci instrukcji w `cmd_download`.
- Proponowana naprawa: usunac galaz `laz` z `_create_provider_and_storage` (przeplyw LAZ ma wlasna
  fabryke w `_cmd_download_laz`, linie 907/949).
- Pewnosc: wysoka

### A2-11 [Minor] `MetadataCache.__del__` halasuje przy zamykaniu interpretera
- Plik: `kartograf/cache/metadata.py`:413-419 (`import contextlib` wewnatrz `__del__`)
- Twierdzenie: lokalny import w destruktorze zawodzi podczas shutdownu interpretera, wypisujac na stderr
  `Exception ignored in: <function MetadataCache.__del__>` / `ImportError: sys.meta_path is None`.
- Dowod: powtorzone w wyjsciu kilku snippetow tej sesji (5 wystapien w jednym uruchomieniu).
- Weryfikacja: uruchomione snippety offline.
- Proponowana naprawa: przeniesc `import contextlib` na poziom modulu (lub zastapic `try/except Exception: pass`).
- Pewnosc: wysoka

### A2-12 [Minor] `close()` zostawia `_conn = None` bez strazy — kazde pozniejsze uzycie to `AttributeError`
- Plik: `kartograf/cache/metadata.py`:405-411
- Twierdzenie: po `close()` metody `stats()`/`get_url()`/`set_url()` wywalaja sie surowym
  `AttributeError: 'NoneType' object has no attribute 'execute'` zamiast czytelnego bledu.
- Dowod: `stats() po close(): AttributeError 'NoneType' object has no attribute 'execute'`
- Weryfikacja: uruchomiony snippet offline.
- Proponowana naprawa: dodac straz `if self._conn is None: raise RuntimeError("MetadataCache jest zamkniety")`
  w prywatnym helperze uzywanym przez wszystkie metody.
- Pewnosc: wysoka

### A2-13 [Minor] `ttl_seconds` uzytkownika nie dotyczy `sheet_cache`; granica TTL rozjezdza sie miedzy `get_*` a `prune_expired`
- Plik: `kartograf/cache/metadata.py`:28 (`SHEET_TTL_SECONDS` — stala modulu), 297, 163 (`>=`) vs 387/393 (`<`)
- Twierdzenie: `MetadataCache(ttl_seconds=1)` nie skraca zycia wpisow `sheet_cache` (zawsze 30 dni),
  a wpis o wieku dokladnie `ttl` jest uznany za wygasly w `get_url` i jednoczesnie nieusuwany przez `prune_expired`.
- Dowod:
  ```
  sheet po 1h przy ttl_seconds=1s: {'a': 1}   (SHEET_TTL= 2592000 s)
  prune_expired usunal sheet? 0
  dokladnie na granicy: get_url -> None       (prune uzywa `cached_at < cutoff`, wiec ten wpis zostaje w bazie)
  ```
- Weryfikacja: uruchomiony snippet offline.
- Proponowana naprawa: przyjac `sheet_ttl_seconds` jako parametr konstruktora (domyslnie
  `SHEET_TTL_SECONDS`) i ujednolicic porownanie na `<=`/`<` w obu miejscach.
- Pewnosc: wysoka

### A2-14 [Minor] Rozjazd backoffu miedzy "kanonicznym" downloaderem a kopiami w providerach PL
- Plik: `kartograf/transport/http.py`:56-62 (`RETRY_BACKOFF_BASE**attempt`, `attempt` od 0 -> 1 s, 2 s) vs `providers/pl/gugik.py`:738-741, `gugik_orto.py`:505-508, `gugik_laz.py`:550-553, `bdot10k.py`:523-526 (`attempt` od 1 -> 2 s, 4 s)
- Twierdzenie: cztery kopie wzorca retry maja inny harmonogram niz modul opisany jako "Kanoniczny
  downloader HTTP" (laczne oczekiwanie 3 s vs 6 s), mimo ze jego docstring deklaruje ten sam wzorzec.
- Dowod: `transport/http.py`:4-7 "Wzorzec: (...) retry z backoffem wykladniczym. Istniejace providery
  maja wlasne, przetestowane implementacje tego wzorca"; petle `for attempt in range(retries)` vs
  `for attempt in range(1, self.MAX_RETRIES + 1)`.
- Weryfikacja: czytanie obu implementacji (bez uruchomienia — roznica jest arytmetyczna i wprost widoczna).
- Proponowana naprawa: przy okazji etapu 2 przepiac providery PL na `transport.http.download_to`
  (duplikacja jest dzis swiadoma, ale docstring sugeruje rownowaznosc, ktorej nie ma).
- Pewnosc: wysoka

### A2-15 [Minor] `GugikOrtoProvider.OPENDATA_URL_PATTERN` nie ogranicza rozszerzenia pliku (NMT wymaga `.asc`)
- Plik: `kartograf/providers/pl/gugik_orto.py`:83 vs `kartograf/providers/pl/gugik.py`:523-526
- Twierdzenie: wzorzec `url:"(https://[^"]+)"` zlapie dowolny URL w odpowiedzi HTML, wiec fallback
  `urls[0]` (A2-7) moze wskazac zasob niebedacy ortofoto.
- Dowod: `ORTO regex znajduje: ['https://opendata.geoportal.gov.pl/ortofotomapa/00/00_x.tif', 'https://mapy.geoportal.gov.pl/logo.png']`
- Weryfikacja: uruchomiony snippet offline na sztucznym HTML.
- Proponowana naprawa: zawezic wzorzec do `https://opendata[^"]+\.tif` (symetrycznie do NMT).
- Pewnosc: wysoka

### A2-16 [Minor] `validate_admin_unit` przepuszcza 7-cyfrowy TERYT gminy, dla ktorego BDOT10k nie ma paczek
- Plik: `kartograf/providers/base.py`:393-401 (`len(code) in (4, 7)`) vs `kartograf/providers/pl/bdot10k.py`:105-109 (wzorce URL tylko dla powiatow)
- Twierdzenie: kod gminy przechodzi walidacje i buduje URL, ktory na pewno nie istnieje — zamiast
  szybkiego `ValidationError` uzytkownik czeka 3 proby z ~6 s uspienia i dostaje `DownloadError`.
- Dowod:
  ```
  validate_admin_unit('1465011') -> True
  URL dla gminy 7-cyfrowej      -> https://opendata.geoportal.gov.pl/bdot10k/schemat2021/GPKG/14/1465011_GPKG.zip
  ```
- Weryfikacja: uruchomiony snippet offline (URL zbudowany, zapytania nie wyslano).
- Proponowana naprawa: nadpisac `validate_admin_unit` w `Bdot10kProvider` na 4 cyfry (docstring
  `download_by_admin_unit` juz mowi wylacznie o powiecie) albo dodac osobne wzorce URL dla gmin.
- Pewnosc: wysoka

## Pozytywy
1. Atomowy zapis jest zrobiony poprawnie i spojnie we wszystkich czterech providerach PL: unikalny
   `pid_threadid.tmp`, `rename` dopiero po pelnym zapisie, `unlink` w `except` — zweryfikowano, ze
   przerwanie w trakcie `iter_content` nie zostawia czesciowego pliku pod docelowa nazwa.
2. `GugikNmptProvider` nadpisuje komplet tego, co powinien, i nic wiecej: `WMS_LAYERS`,
   `WMS_SKOROWIDZE_ENDPOINTS`, `WCS_ENDPOINTS`, `COVERAGE_IDS`, `SUPPORTED_RESOLUTIONS`,
   `SUPPORTED_VERTICAL_CRS_5M`, `_CACHE_PRODUCT="nmpt"`, `name`, `descriptor_key="pl.gugik.nmpt"` —
   sprawdzone runtime, klucze cache NMT/NMPT/Orto sa rozlaczne.
3. Regula "5m => EVRF2007" jest w obu kopiach (`pl/__init__.py`:36-41 i `manager.py`:176-181)
   **identyczna** co do warunku, komunikatu i efektu; `GugikProvider.__init__` domyka ja twardym
   `ValueError`, wiec nie da sie zbudowac providera 5m/KRON86 zadna droga.
4. `FileStorage.delete()` faktycznie usuwa sidecar razem z danymi (zweryfikowane), a `get_raw_path`
   poprawnie omija `SheetParser` dla nieparsowalnych godel LAZ w obu formatach (PL-1992 i PL-2000).
5. `_get_validated_layers` (NMT i Orto) ma poprawny fallback: kazdy blad sieci/parsowania/pustej listy
   konczy sie uzyciem wartosci hardcoded, a nie wyjatkiem — pobieranie dziala offline; wynik jest
   memoizowany na czas zycia instancji.

## Podsumowanie liczbowe: C=3 I=6 M=7
