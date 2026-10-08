# A4 — weryfikacja ustalen (V4)

Zakres: wszystkie ustalenia [Critical] i [Important] z `A4-report.md`
(A4-1..A4-14). [Minor] (A4-15..A4-20) pominiete zgodnie z VERIFY_FORMAT.

Srodowisko weryfikacji: `fix/release-0.7.0-audit`, `.venv/bin/python` (3.13),
offline (zero polaczen do CLMS/ISRIC/GUGiK — wszystkie serwery HTTP w
reprodukcjach sa lokalne albo zamockowane). Snippety w scratchpadzie
`/tmp/claude-1001/.../scratchpad/` (a41_env.py, a42_chunked.py, a43_teryt.py,
a43_centers.py, a44_usda.py, a45_nodata.py, a46_area.py, a47_bbox.py,
a48_fp.py, a410_proxy.py, a411_pipe.py, a412_api.py, a413_side.py,
a414b.py, new1b.py, new1c.py). Baseline testow potwierdzony:
`pytest tests/test_hsg.py tests/test_soilgrids.py tests/test_landcover.py
tests/test_auth_client.py tests/test_auth_proxy.py -q -p no:cacheprovider`
-> **212 passed, 3 warnings**. Zadnego pliku repo nie zmieniono.

---

### A4-1 — `CLMS_CREDENTIALS` nigdy nie jest czytane — CORINE zawsze cicho spada na PNG
- Werdykt: CONFIRMED
- Reprodukcja: `a41_env.py` (env ustawiony na poprawny JSON przed importem):
  ```
  get_clms_credentials() sam z siebie widzi env: True
  has_clms_token przy ustawionym CLMS_CREDENTIALS: False
  _use_proxy: True _clms_auth: None
  -> wybrana sciezka: WMS/PNG
  ```
  `grep -rn "get_clms_credentials" --include=*.py .` -> tylko definicja
  `corine.py:196` (zero wywolan w `kartograf/` i w `tests/`).
  `grep -rn "CLMS_CREDENTIALS"` w `kartograf/` -> wylacznie `corine.py:212`
  (wewnatrz martwej funkcji). `proxy.py:52-56` czyta wylacznie Keychain i na
  nie-Darwin konczy `logger.error("Keychain only available on macOS")`.
  `grep -rn "basicConfig" kartograf/` -> tylko `auth/proxy.py:33`, wiec
  `logger.info` o fallbacku faktycznie nie dociera do uzytkownika CLI
  (jedynym sygnalem jest `.png` w linii `Downloaded to: ...`).
- Uzasadnienie: mechanizm odtworzony 1:1 — zmienna srodowiskowa jest
  dziedziczona przez podproces, ale **nikt jej nie odczytuje** (ani rodzic,
  ani `CLMSCredentials` w proxy). README.md:190 i CLAUDE.md:26 obiecuja
  konfiguracje przez env; ADR-002 mowi tylko o Keychain, ale nie wyklucza
  env — dokumentacja produktowa jest wprost sprzeczna z kodem, wiec to nie
  jest DESIGN-DECISION, tylko niedokonczona implementacja + falszywe docs.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/auth/proxy.py` — w `CLMSCredentials` dodac
  `load_from_env()` czytajace `os.environ["CLMS_CREDENTIALS"]` i wolac je
  przed `load_from_keychain()` w `get_access_token`/`is_available` (sekret
  zostaje wtedy tylko w podprocesie — zgodnie z ADR-002; NIE zmieniac
  `load_from_keychain`, bo `tests/test_auth_proxy.py:19` pinuje jej zwrot
  `False` poza macOS). Dodatkowo `corine.py:559-561` z `logger.info` na
  `logger.warning` albo jawny `print` w `cli/landcover_cmd.py`. Test:
  nowy `test_load_from_env_*` w `tests/test_auth_proxy.py` +
  `test_health_credentials_available_from_env`. S; ryzyko regresji: niskie.

---

### A4-2 — `AuthProxyClient.download_file` zwraca `True` dla urwanego pobrania
- Werdykt: CONFIRMED
- Reprodukcja: `a42_chunked.py` — realny `ProxyHandler` + realny
  `AuthProxyClient.download_file`, lokalny upstream oddajacy jeden chunk
  100 B i zrywajacy polaczenie:
  ```
  download_file zwrocil: True
  plik istnieje: True rozmiar: 309
  poczatek: b'II*\x00AAAAAAAAAAAA'
  koniec  : b'...Content-Length: 56\r\n\r\n{"error": "Download failed: Response ended prematurely"}'
  ```
  W logu proxy widac dwie odpowiedzi na jedno zadanie: `200` i `502`.
- Uzasadnienie: potwierdzone dwie niezalezne wady w jednej sciezce —
  `ProxyHandler` wola `send_json(..., 502)` **po** `end_headers()`, doklejajac
  cala odpowiedz HTTP do ciala rastra, a klient sprawdza tylko
  `status_code == 200` i pisze bez pliku tymczasowego. Nastepstwo:
  `LandCoverManager._write_sidecar` dopisuje poprawny `.meta.json`
  (`horizontal_crs: EPSG:3035`) do uszkodzonego GeoTIFF-a. Sciezka jest
  osiagalna tylko przy dzialajacych credentials (dzis: macOS + Keychain),
  ale to nie zmienia klasy bledu — cichy sukces na uszkodzonych danych.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/auth/client.py:283-288` — zapis do
  `<plik>.<pid>_<tid>.tmp` + `rename` po pelnym odczycie, `unlink` w
  `except` (wzorzec `_save_response` z `corine.py:1107-1126`), a takze
  `unlink` czesciowego pliku w wariancie `status_code != 200`;
  `kartograf/auth/proxy.py:288-298` — po `end_headers()` nie wolac
  `send_json`, tylko zalogowac blad i `self.close_connection = True`.
  Test: `tests/test_auth_client.py` — nowy `test_download_file_stream_broken`
  (mock `iter_content` rzucajacy `requests.RequestException` w polowie)
  asertujacy `False` + brak pliku i brak `.tmp`. S; ryzyko regresji: niskie
  (istniejace `test_download_file_success/_failure` pozostaja zielone).

---

### A4-3 — SoilGrids: `--teryt` pobiera dane dla srodka wojewodztwa, nie dla powiatu
- Werdykt: CONFIRMED
- Reprodukcja: `a43_teryt.py` (zamockowana `requests.Session`, offline):
  ```
  TERYT 1465 -> bbox (590000, 450000, 650000, 510000) | srodek 20.7554E 52.1730N | 60x60 km
  TERYT 1401 -> bbox (590000, 450000, 650000, 510000) | srodek 20.7554E 52.1730N | 60x60 km
  TERYT 1419 -> bbox (590000, 450000, 650000, 510000) | srodek 20.7554E 52.1730N | 60x60 km
  identyczny bbox dla 1465/1401/1419: True   (odpowiedz WMS: pobrana i ZIGNOROWANA)
  ```
  Dodatkowo `a43_centers.py` — sama tablica `woj_centers` jest bledna takze
  na poziomie wojewodztwa: `02` (dolnoslaskie) -> **18.858E 50.837N**
  (Slask, ~170 km od Wroclawia), `08` (lubuskie) -> **17.114E 51.811N**
  (~130 km, Wielkopolska), `32` (zachodniopomorskie) -> **17.197E 53.341N**
  (~110 km). Czyli nawet gdyby zamiar byl "przyblizony bbox wojewodztwa",
  3 z 16 wpisow i tak lezy poza wlasnym wojewodztwem.
- Uzasadnienie: potwierdzone. To nie jest udokumentowane ograniczenie —
  `docs/SCOPE.md:211` i `CLAUDE.md:145` wymieniaja `--teryt` wylacznie przy
  `bdot10k`, a `SCOPE.md` 3.2 "Ograniczenia techniczne" milczy o TERYT dla
  SoilGrids; docstring metody (`soilgrids.py:438-441`) wprost **klamie**
  ("Finds the bounding box for the given TERYT code using GUGiK WMS"),
  komentarz w kodzie sam sie przyznaje ("For now..."). Sciezka jest w pelni
  osiagalna z CLI — `_parser.py:221-225` nie ogranicza `--teryt` do zrodla
  `bdot10k`. Zwracanie prawdopodobnie blednych danych jako sukcesu jest
  gorsze niz brak funkcji.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/providers/soilgrids.py:378-531` — usunac
  `_get_bbox_for_teryt` wraz z martwym zapytaniem WMS i zamienic
  `download_by_teryt` na jawny `NotImplementedError`/`ValidationError`
  ("SoilGrids nie obsluguje wyboru po TERYT — uzyj --bbox/--godlo"),
  wzorem `CorineProvider.download_by_teryt` (`corine.py:873`); w
  `cli/landcover_cmd.py` komunikat juz jest lapany (`except NotImplementedError`,
  linia 197). Test: `tests/test_soilgrids.py` — zamienic testy TERYT na
  `pytest.raises(NotImplementedError)`. Wersja "zaimplementowac realne
  granice powiatow" = L i wykracza poza wydanie. S; ryzyko regresji: niskie
  (zmiana zachowania publicznego API, ale z blednych danych na jawny blad;
  wymaga wpisu w `docs/CHANGELOG.md` Breaking Changes).

---

### A4-4 — Klasyfikacja USDA odbiega od trojkata teksturowego
- Werdykt: CONFIRMED
- Reprodukcja: `a44_usda.py` — wlasna implementacja kanonicznych regul
  trojkata USDA (Soil Survey Manual: warunki `silt + 1.5*clay`,
  `silt + 2*clay`, `silt < 28`, `sand > 52`, `sand > 45`) porownana z
  `classify_usda_texture` na calym symplexie co 1% (5151 punktow):
  ```
  punktow symplexu: 5151, nieskla. w referencji: 0
  rozne klasy tekstur : 378 (7.3%)
  rozne grupy HSG     : 176 (3.4%)
    USDA=sandy_loam  kod=loamy_sand      HSG B->A  n=136  przyklad (clay,sand,silt)=(0, 70, 30)
    USDA=loam        kod=sandy_clay_loam HSG B->C  n= 35  przyklad (clay,sand,silt)=(20, 45, 35)
    USDA=clay_loam   kod=sandy_clay      HSG C->D  n=  5  przyklad (clay,sand,silt)=(35, 45, 20)
  ```
  Liczby i przyklady zgadzaja sie co do jednego z raportem A4. Najwieksze
  zrodlo bledu: `hsg.py:120` (`clay <= 15 and sand >= 70`) zastepuje ukosna
  granice `silt + 2*clay < 30` linia pionowa — stad 136 punktow gleb
  piaszczystych (dominujacych w PL) awansowanych z HSG B na A.
  Dodatkowo istniejacy test `tests/test_hsg.py:34`
  (`clay=12, sand=75, silt=13 == "loamy_sand"`) pinuje punkt, ktory w
  kanonicznym trojkacie jest `sandy_loam` (`silt+2*clay = 39 >= 30`).
- Uzasadnienie: sam odtworzylem referencje i roznice; brak jakiegokolwiek
  ADR/SCOPE/README dopuszczajacego uproszczenie progow — a docstring
  `hsg.py:102` deklaruje "standard USDA soil texture triangle". HSG jest
  deklarowanym wejsciem SCS-CN dla Hydrologa, wiec A vs B to inny CN.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/hydrology/hsg.py:116-169` (skalar) i `189-270`
  (wektor) — zastapic progi kanonicznymi 12 regulami i wygenerowac wersje
  wektorowa z tych samych warunkow (to jednoczesnie eliminuje A4-8 i
  nieosiagalna galaz z A4-16). Testy: `tests/test_hsg.py:31-69` i testy
  tablicowe (~140-190) trzeba zaktualizowac; dopisac test rownowaznosci
  skalar-vs-wektor na calym symplexie (petla 5151 punktow, <1 s) —
  przypina obie funkcje na stale. M; ryzyko regresji: srednie (zmienia
  wartosci wyjsciowe dla konsumentow — wymaga wpisu w `docs/CHANGELOG.md`).

---

### A4-5 — Piksele nodata inne niz 0 dostaja grupe HSG "B"
- Werdykt: CONFIRMED
- Reprodukcja: `a45_nodata.py` — potok 1:1 jak w `calculate_hsg_by_bbox`
  (g/kg -> `/CONVERSION_FACTOR` -> `classify_usda_texture_array` ->
  `texture_to_hsg_array` -> maska `(clay==0)&(sand==0)&(silt==0)`):
  ```
  tekstura: ['clay_loam', 'loam', 'loam', 'loam']
  HSG (0=nodata,1=A,2=B,3=C,4=D): [3, 2, 0, 2]
              ^poprawny  ^-32768  ^zera   ^NaN
  ```
- Uzasadnienie: potwierdzone dla dwoch przypadkow — `-32768` (typowe nodata
  Int16) **i** `NaN` konczy jako HSG 2 = B. `grep -n "nodata" hsg.py` daje
  tylko linie 498-500 i 508: `clay_src.nodata`/`sand_src.nodata`/
  `silt_src.nodata` nie sa nigdzie odczytywane. Istniejacy
  `test_calculate_hsg_nodata_handling` pokrywa wylacznie wariant all-zero.
  Skutek: obszary bez danych trafiaja do rastra i do statystyk jako realna
  gleba grupy B.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/hydrology/hsg.py:475-500` — odczytac
  `*_src.nodata` przy otwieraniu kazdego rastra i zbudowac maske
  `(clay==nd_c) | (sand==nd_s) | (silt==nd_si) | ~np.isfinite(...)`
  (z fallbackiem na dotychczasowe all-zero, gdy `nodata is None`); maske
  stosowac po klasyfikacji jak dotad. Test: rozszerzyc
  `test_calculate_hsg_nodata_handling` o raster z `nodata=-32768` i o NaN.
  S; ryzyko regresji: niskie.

---

### A4-6 — `get_hsg_statistics` liczy powierzchnie w stopniach kwadratowych
- Werdykt: CONFIRMED
- Reprodukcja: `a46_area.py` — realny GeoTIFF (rasterio), realne
  `HSGCalculator.get_hsg_statistics`:
  ```
  liczba pikseli B: 10000
  area_ha (kod)   : 5.043317156435609e-06
  area_m2 (kod)   : 0.05043317156435609
  percent (kod)   : 100.0
  prawidlowo (~250m px, 10000 px): 62500.0 ha
  CLI wydrukuje: "  Group B: 100.0% (0.00 ha)"
  kontrola: ten sam raster w EPSG:2180 (250 m px) -> area_ha = 62500.0
  ```
- Uzasadnienie: potwierdzone — blad rzedu 1,24e10 (ok. 10 rzedow wielkosci).
  Raster HSG dziedziczy profil z rastra SoilGrids (`hsg.py:477`), a ten jest
  w EPSG:4326: `soilgrids.py:363` `OUTPUTCRS=.../EPSG/0/4326`, deskryptor
  `global.isric.soilgrids` w `sources/registry.py:219` deklaruje
  `horizontal_crs="EPSG:4326"`. Pole `percent` (liczone z pikseli) pozostaje
  poprawne; bledne sa wylacznie `area_m2`/`area_ha`, ktore CLI drukuje
  (`cli/soilgrids_cmd.py:153`).
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/hydrology/hsg.py:551-567` — jesli
  `src.crs.is_geographic`, liczyc pole komorki geodezyjnie (wektor wag na
  szerokosc geograficzna wiersza: `pyproj.Geod(ellps="WGS84")` albo
  `res_lon*res_lat*(111320**2)*cos(lat)`) i sumowac wagi maski zamiast
  mnozyc licznik przez staly `pixel_area`; dla CRS metrycznego zostawic
  obecny wzor. Test: `tests/test_hsg.py` — dwa syntetyczne rastry (4326 i
  2180) o tym samym pokryciu, asercja `area_ha` w granicach +/-2%.
  S/M; ryzyko regresji: niskie (nowa galaz, stara sciezka niezmieniona).

---

### A4-7 — Transformacja bbox po dwoch narozach zawezia zamawiany obszar
- Werdykt: CONFIRMED
- Reprodukcja: `a47_bbox.py`, arkusz `N-34-130-D` (18,0 x 19,4 km):
  ```
  kod (2 naroza) 4326 : (22.735906, 52.33378, 23.015087, 52.499488)
  transform_bounds    : (22.735906, 52.325146, 23.015087, 52.508176)
  utracone na poludniu: -0.008634 st lat = -961 m
  utracone na polnocy : -0.008688 st lat = -967 m
  strata pasa: 1.93 km z 19.4 km wysokosci = 9.9% powierzchni
  w pikselach: SoilGrids (250 m) 7.7 px; CORINE (100 m) 19.3 px
  3857 kod: (2530949.5, 6860703.7, 2562027.8, 6890948.1)
  3857 obw: (2530949.5, 6859131.0, 2562027.8, 6892537.0)
  WIDTH/HEIGHT = 179 194 | aspect px = 0.92268 | aspect bbox3857 = 1.02757 -> znieksztalcenie 11.37%
  ```
- Uzasadnienie: potwierdzone co do cyfry. Istotne dla obu konsumentow:
  utracony pas 961/967 m to ~8 pikseli SoilGrids (250 m) i ~19 pikseli
  CORINE (100 m) na kazdej krawedzi poludnikowej — nie jest to bland
  zaokraglenia. Osobno potwierdzone znieksztalcenie proporcji podgladu WMS
  o 11,37% (`WIDTH`/`HEIGHT` z metrow EPSG:2180, `BBOX` z narozy w 3857).
  Zadne ADR/SCOPE nie opisuje tego jako swiadomego uproszczenia.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/providers/soilgrids.py:251-272`,
  `kartograf/providers/corine.py:994-1012` i `1014-1030` — zastapic pare
  `transformer.transform(...)` wywolaniem
  `transformer.transform_bounds(min_x, min_y, max_x, max_y, densify_pts=21)`
  (pyproj >= 3.6 juz wymagany); w `corine.py:544-548` liczyc
  `width_px`/`height_px` z bboxa docelowego (3857/4326), nie z metrow 2180.
  Testy: `tests/test_soilgrids.py:166` i `tests/test_landcover.py:805,816`
  sa luzne (zakresy) — przejda bez zmian; **wymagaja aktualizacji**
  `tests/test_landcover.py:698` (`WIDTH=100`) i `:715` (`WIDTH=4096`).
  Dopisac test asertujacy, ze zwrocony bbox zawiera obwiednie 4 narozy.
  S/M; ryzyko regresji: srednie (rosnie zamawiany obszar -> wieksze pliki;
  2 testy do przepiecia).

---

### A4-8 — float32: wersja wektorowa i skalarna rozjezdzaja sie na granicy clay = 15%
- Werdykt: CONFIRMED
- Reprodukcja: `a48_fp.py`:
  ```
  liczba rozbieznosci skalar-vs-wektor: 16
  wszystkie na clay==15?: True    zakres sand: 70 - 85
  zmiany HSG: {('A', 'B')}
  float32 clay/total*100 = np.float32(15.000001) <=15? False
  float64                = 15.0                  <=15? True
  pipeline array  -> sandy_loam      pipeline scalar -> loamy_sand
  ```
- Uzasadnienie: odtworzone dokladnie (16 punktow, wszystkie na `clay=15`,
  wszystkie zmieniajace HSG A<->B). Ten sam raster daje inna odpowiedz
  zaleznie od tego, czy uzytkownik wolal funkcje skalarna czy tablicowa —
  to niespojnosc publicznego API, nie tylko kosmetyka.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/hydrology/hsg.py:212-217` — normalizowac w
  float64 (`total = (clay + sand + silt).astype(np.float64)`). Docelowo
  znika razem z naprawa A4-4 (jedno zrodlo progow); jesli A4-4 zostanie
  odlozone, ta zmiana jest samodzielna i wystarczajaca. Test: parametryczny
  test rownowaznosci skalar-vs-wektor na symplexie (ten sam co w A4-4).
  S; ryzyko regresji: niskie.

---

### A4-9 — `TEXTURE_TO_HSG` przeczy docstringowi wlasnego modulu i cytowanej normie
- Werdykt: DESIGN-DECISION
- Reprodukcja: porownanie tekstu z kodem (bez snippetu — to ustalenie
  dokumentacyjne):
  ```
  hsg.py:10-13 (docstring):  Group A: sand, loamy sand, sandy loam
                             Group D: clay loam, silty clay, clay
  hsg.py:69:  "sandy_loam": "B",       # Can be A/B depending on structure
  hsg.py:74:  "clay_loam": "C",        # Can be C/D
  hsg.py:75:  "silty_clay_loam": "C",
  tests/test_hsg.py:104,112,113 — pinuja B/C/C
  ```
- Uzasadnienie: komentarze w samej tablicy ("Can be A/B depending on
  structure", "Can be C/D") pokazuja, ze odstepstwo od klasycznej tabeli
  TR-55 jest **swiadome** — to decyzja projektowa, nie przypadek. Ale nie ma
  jej w `docs/DECISIONS.md`, a docstring modulu (`hsg.py:9-16`) i sekcja
  README o HSG podaja liste sprzeczna z tablica. Zmiana samej tablicy
  zmienia CN u Hydrologa i wymaga decyzji produktowej, wiec nie nadaje sie
  na wydanie; sprzeczne docs — owszem.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `kartograf/hydrology/hsg.py:9-16` — usunac sprzeczna liste
  klas z docstringu modulu i zastapic odsylaczem do ADR; nowy wpis w
  `docs/DECISIONS.md` (ADR-025) opisujacy przyjete mapowanie
  tekstura->HSG i uzasadnienie odstepstwa od TR-55 (`sandy_loam`=B,
  `clay_loam`/`silty_clay_loam`=C); wzmianka w README w sekcji HSG, zeby
  Hydrolog wiedzial, jakie CN dostaje. Test: brak (docs); istniejace
  `test_group_*_textures` juz pinuja tablice. S; ryzyko regresji: zadne.

---

### A4-10 — Auth proxy nie uwierzytelnia klienta i przekazuje token na dowolny URL
- Werdykt: CONFIRMED
- Reprodukcja: `a410_proxy.py` — realny `ProxyHandler` z podstawionym
  obiektem credentials, klient `urllib`, lokalny "atakujacy" serwer
  zapisujacy naglowki (wszystko na 127.0.0.1, zero sieci):
  ```
  GET /health bez jakiegokolwiek sekretu -> (200, b'{"status": "ok", "credentials_available": true}')
  GET /token  bez jakiegokolwiek sekretu -> (200, b'{"access_token": "SEKRETNY-TOKEN-CLMS"}')
  POST /proxy na obcy host -> 200 {"status_code": 200, ..., "body": "ok"}
  naglowek odebrany przez 'atakujacego': {'auth': 'Bearer SEKRETNY-TOKEN-CLMS', 'path': '/steal'}
  ```
- Uzasadnienie: mocniej niz w raporcie — nie tylko "zadanie zostalo
  przyjete", ale token **faktycznie wyszedl** w naglowku `Authorization` do
  hosta spoza `land.copernicus.eu`, a `GET /token` oddaje go wprost kazdemu
  procesowi lokalnemu bez zadnego sekretu. To wywraca teze ADR-002
  ("credentials nie opuszczaja procesu proxy") — proxy chroni klucz
  prywatny, ale nie chroni tokena. Osobno potwierdzone: `_cleanup` wisi
  tylko na `atexit` (`client.py:63`) — po `os._exit`/SIGKILL rodzica
  podproces proxy zostaje jako osierocony serwer nasluchujacy (widziany
  `pgrep -fa "kartograf.auth.proxy"` po moich testach).
- Naprawa przed wydaniem 0.7.0: TAK (czesciowo)
- Zakres naprawy: `kartograf/auth/proxy.py:199-301` — allowlista hostow
  (`land.copernicus.eu` + hosty z `DownloadURL`) sprawdzana przez
  `urlparse(target_url).hostname` w `/proxy` i `/download`, odrzucanie
  `403` poza lista; usunac endpoint `/token` (`proxy.py:184-189`) razem z
  `AuthProxyClient.get_access_token` — `CorineProvider` z nich nie korzysta
  (`grep -rn "get_access_token" kartograf/providers/` -> tylko tryb direct
  w `CLMSAuth`). Test: `tests/test_auth_proxy.py` — `test_proxy_rejects_foreign_host`
  i `test_token_endpoint_removed`. S; ryzyko regresji: niskie.
  **Odlozone (NIE w 0.7.0):** sekret wspoldzielony rodzic-dziecko
  (`X-Proxy-Auth`) i twardy lifecycle (`SIGKILL`-safe) — to zmiana
  protokolu miedzy dwoma modulami + osobny ADR, poza zakresem wydania.

---

### A4-11 — `stderr` podprocesu proxy jest rura, ktorej nikt nie czyta
- Werdykt: CONFIRMED
- Reprodukcja: `a411_pipe.py` + `a411_child.py` (dziecko pisze linie o
  dokladnie takiej dlugosci jak realny wpis proxy, rodzic czyta wylacznie
  1 linie stdout — jak `client.py:100`):
  ```
  port: PORT-OK
  po 5 s: proces zakonczony? False (rc=None)
  linii zapisanych zanim sie zablokowal: 800
  -> PODPROCES ZABLOKOWANY na write() do niedrenowanej rury stderr
  ```
  800 linii x ~74 B = ~59 KB, czyli zgodnie z 64 KB buforem rury na Linuxie.
  Ze zliczen: `ProxyHandler.log_message` (proxy.py:160-162) daje ~1 linie na
  zadanie; jedno pobranie CORINE to 1 x `@datarequest_post` + do 60 pollingow
  (`CLMS_MAX_WAIT`/`CLMS_POLL_INTERVAL` = 600/10) + 1 `/download` + 1
  `/health` = ~63 zadania, czyli **granica ~880 linii wypada po ok. 14
  pobraniach w jednym procesie** — jeszcze latwiej niz szacowal raport.
- Uzasadnienie: mechanizm odtworzony deterministycznie; realny
  `cli._proxy_process.stderr is not None` potwierdzony osobno w `a413_side.py`.
  Skutek: proxy przestaje odpowiadac, `_poll_clms_task_proxy` wisi do
  `CLMS_MAX_WAIT` (600 s) i konczy timeoutem.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/auth/client.py:94-97` — watek-drenaz
  przepisujacy `stderr` dziecka do `logger.debug` (uruchamiany zaraz po
  `Popen`, `daemon=True`), albo `stderr=subprocess.DEVNULL` jesli logi maja
  byc porzucone; przy okazji `proxy.py:160-162` `logger.info` ->
  `logger.debug`. Test: `tests/test_auth_client.py` — asercja, ze po
  `_start_proxy` istnieje watek drenazu / ze `stderr` nie jest `PIPE`.
  S; ryzyko regresji: niskie.

---

### A4-12 — `SoilGridsProvider.download_by_admin_unit` rzuca `NotImplementedError`
- Werdykt: DOWNGRADE(Minor)
- Reprodukcja: `a412_api.py`:
  ```
  SoilGridsProvider
     download_by_admin_unit   zdefiniowane w: LandCoverProvider
     download_by_teryt        zdefiniowane w: SoilGridsProvider
  Bdot10kProvider
     download_by_admin_unit   zdefiniowane w: Bdot10kProvider
     download_by_teryt        zdefiniowane w: LandCoverProvider
  SoilGridsProvider().download_by_admin_unit('1465', ...) -> NotImplementedError:
      SoilGridsProvider does not support TERYT downloads
  ```
- Uzasadnienie: mechanizm CONFIRMED (nadpisany jest wylacznie przestarzaly
  alias), ale **przeslanka ustalenia jest falszywa**: raport mowi "mimo
  dzialajacej obslugi TERYT", a A4-3 dowodzi, ze ta obsluga nie dziala —
  zwraca bbox innego obszaru. Faktyczny stan jest odwrotny do opisanego:
  kanoniczna nazwa zachowuje sie **bezpiecznie** (jawny blad), a
  przestarzaly alias jest ta wadliwa sciezka. Konsument, ktory zastosuje sie
  do migracji z CHANGELOG-a, nic nie traci. Po naprawie A4-3 (usuniecie
  `download_by_teryt` z SoilGrids) ustalenie znika samo. Stad Minor:
  niespojnosc kontraktu warta uprzatniecia, ale bez skutku uzytkowego.
- Naprawa przed wydaniem 0.7.0: NIE (odlozyc)
- Zakres naprawy: n/d — rozwiazuje sie przy A4-3. Jesli A4-3 zostanie
  odlozone, wtedy `SoilGridsProvider.download_by_teryt` przemianowac na
  `download_by_admin_unit` (S), ale **nie wolno** tego robic samodzielnie,
  bo rozszerzyloby bledna sciezke A4-3 na kanoniczna nazwe.

---

### A4-13 — `CorineProvider()` uruchamia podproces auth proxy takze tam, gdzie nie moze on miec credentials
- Werdykt: CONFIRMED
- Reprodukcja: `a413_side.py` (`subprocess.Popen` opakowany szpiegiem):
  ```
  platform: Linux
  has_clms_token: False
  podprocesy uruchomione: [['.../.venv/bin/python', '-m', 'kartograf.auth.proxy', '--port', '0']]
  podproces zyje po sprawdzeniu: True
  stderr to rura?: True
  port proxy: 43977
  ```
- Uzasadnienie: potwierdzone — sprawdzenie "czy mam token" ma efekt uboczny
  w postaci procesu Pythona i otwartego portu localhost zyjacego do konca
  interpretera, mimo ze `platform.system() != "Darwin"` przesadza wynik od
  razu. Sprzega sie z A4-10 (otwarty, nieuwierzytelniony port) i A4-11
  (ten sam proces trzyma niedrenowana rure). Koszt ponoszony przy kazdym
  `kartograf landcover download --source corine`.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/auth/client.py:151-160` — na poczatku
  `is_available()` zwrocic `False` bez `_ensure_proxy()`, gdy nie ma zadnego
  zrodla credentials (`platform.system() != "Darwin" and not
  os.environ.get("CLMS_CREDENTIALS")`); naturalnie laczy sie z A4-1 (po
  dodaniu obslugi env warunek pozostaje poprawny). Test:
  `tests/test_auth_client.py` — `test_is_available_short_circuits_without_creds`
  (patch `platform.system` na "Linux", asercja `Popen` nie wolany).
  S; ryzyko regresji: niskie.

---

### A4-14 — `_start_proxy`: blokujacy `readline()` bez limitu czasu, nieudany podproces nie jest sprzatany
- Werdykt: CONFIRMED
- Reprodukcja: `a414b.py` (dziecko, ktore nigdy nie drukuje portu) oraz
  wariant z dzieckiem konczacym sie bez portu:
  ```
  start_proxy (dziecko konczy sie bez portu) -> False
    _proxy_process ustawiony? True | poll: 3
    -> brak terminate()/wait(); obiekt martwego procesu zostaje w singletonie

  PROXY_STARTUP_TIMEOUT = 10 s
  po 12 s _start_proxy zakonczony? False | wynik: []
    -> WISI na stdout.readline(); PROXY_STARTUP_TIMEOUT nie chroni tej fazy
  ```
- Uzasadnienie: oba mechanizmy odtworzone deterministycznie (raport ocenial
  je tylko przez lekture). Prawdopodobienstwo wystapienia w praktyce jest
  niskie (wymaga podprocesu, ktory ani nie drukuje portu, ani nie konczy
  sie), ale skutek to zawis CLI bez limitu czasu, wiec podtrzymuje
  [Important]. Naprawa lezy w tej samej funkcji co A4-11 i A4-13.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/auth/client.py:99-113` — odczyt portu w watku z
  `join(PROXY_STARTUP_TIMEOUT)` (albo `selectors` na `stdout`), a w kazdej
  sciezce bledu `terminate()` + `wait(timeout=5)` i
  `self._proxy_process = None`, zeby `_ensure_proxy` mogl czysto sprobowac
  ponownie. Test: `tests/test_auth_client.py:73` (`test_start_proxy_no_port`)
  rozszerzyc o asercje `mock_proc.terminate.called` i
  `client._proxy_process is None`. S; ryzyko regresji: niskie (zmiana w
  jednej metodzie, istniejace testy startu proxy mockuja `Popen`).

---

## Tabela

| ID | Werdykt | Naprawa 0.7.0 | Rozmiar | Ryzyko |
| --- | --- | --- | --- | --- |
| A4-1 | CONFIRMED | TAK | S | niskie |
| A4-2 | CONFIRMED | TAK | S | niskie |
| A4-3 | CONFIRMED | TAK | S | niskie |
| A4-4 | CONFIRMED | TAK | M | srednie |
| A4-5 | CONFIRMED | TAK | S | niskie |
| A4-6 | CONFIRMED | TAK | S/M | niskie |
| A4-7 | CONFIRMED | TAK | S/M | srednie |
| A4-8 | CONFIRMED | TAK | S | niskie |
| A4-9 | DESIGN-DECISION | DOCS-ONLY | S | zadne |
| A4-10 | CONFIRMED | TAK (allowlista + usuniecie `/token`; sekret klienta odlozony) | S | niskie |
| A4-11 | CONFIRMED | TAK | S | niskie |
| A4-12 | DOWNGRADE(Minor) | NIE (odlozyc — znika przy A4-3) | — | — |
| A4-13 | CONFIRMED | TAK | S | niskie |
| A4-14 | CONFIRMED | TAK | S | niskie |

## Nowe ustalenia przy okazji (max 3, tylko jesli Critical/Important i z dowodem)

### N4-1 [Important] `AuthProxyClient` nie ma zadnej synchronizacji — rownolegle pobranie CORINE cicho spada na podglad PNG
- Plik: `kartograf/auth/client.py`:100-142 (`_start_proxy`/`_ensure_proxy`),
  konsument: `kartograf/landcover/manager.py`:378-383 (`download_batch`,
  `max_workers=4` domyslnie) przez `CorineProvider.has_clms_token`
  (`corine.py`:449-460, wolane w `download_by_bbox`:530).
- Twierdzenie: `_start_proxy` ustawia `AuthProxyClient._proxy_port` dopiero
  **po** powrocie z blokujacego `readline()`, a `_ensure_proxy` w drugim
  watku sprawdza `self._proxy_process.poll() is None` i zwraca `True`, gdy
  proxy jeszcze startuje. `is_available()` idzie wtedy pod
  `f"{self.proxy_url}/health"` = **`"None/health"`**, dostaje
  `requests.RequestException` i zwraca `False`. W `download_batch` oznacza
  to, ze czesc pozycji wsadu zapisze GeoTIFF z kodami klas, a czesc — cichy
  podglad PNG z WMS, bez zadnego bledu; sidecary beda poprawne dla obu, wiec
  rozjazd formatu wyjdzie dopiero u konsumenta (Hydrograf).
- Dowod (offline, `new1c.py`; podproces proxy sztucznie spowolniony o 1 s,
  co odpowiada zimnemu startowi interpretera):
  ```
  watek rownolegly: _ensure_proxy() -> True | proxy_url -> None
  ```
  oraz `new1b.py` (dwa watki, singleton, ten sam obiekt klienta):
  ```
  watek A (startuje proxy) is_available -> False
  watek B (rownolegly)     proxy_url    -> None  is_available -> False
  port po wszystkim: 34319
  => B dostal False mimo startujacego proxy? True
  ```
  Grep potwierdza brak jakiegokolwiek zamka: `grep -n "Lock\|RLock" kartograf/auth/client.py` -> brak trafien.
- Proponowana naprawa: `threading.Lock` (klasowy) wokol `_ensure_proxy` /
  `_start_proxy` w `kartograf/auth/client.py`, dodatkowo warunek
  `if self._proxy_port and self._proxy_process` -> sprawdzac oba **pod
  zamkiem**. Test: dwa watki wolajace `is_available()` z podstawionym
  wolnym `Popen`, asercja identycznego wyniku. S; ryzyko regresji: niskie.
- Pewnosc: wysoka co do mechanizmu (odtworzony); skutek "mieszany wsad
  GeoTIFF/PNG" wymaga dzialajacych credentials, wiec dzis jest osiagalny
  tylko na macOS z Keychainem (patrz A4-1) — po naprawie A4-1 stanie sie
  osiagalny wszedzie.
