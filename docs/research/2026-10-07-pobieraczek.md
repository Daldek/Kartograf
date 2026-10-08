# Wtyczka QGIS "Pobieracz danych GUGiK" ("Pobieraczek") — analiza pod katem strategii kampanii

Data badania: 2026-10-07. Badanie wylacznie czytane (kod wtyczki NIE byl uruchamiany).
Jedyne wywolania sieciowe poza pobraniem kodu: kilka lekkich zapytan GetCapabilities/GetFeature(COUNT=1..2)
do WFS GUGiK (User-Agent `Kartograf-research/0.1`), zeby potwierdzic endpointy znalezione w kodzie wtyczki.

## 0. Identyfikacja

- Nazwa w repozytorium QGIS: "Pobieracz danych GUGiK" (slug `pobieracz_danych_gugik`), https://plugins.qgis.org/plugins/pobieracz_danych_gugik/
  ("Pobieraczek" to potoczna nazwa; w metadata.txt nie wystepuje).
- Autor: **EnviroSolutions Sp. z o.o.** (`author=EnviroSolutions Sp. z o.o.`, gis@envirosolutions.pl) — hipoteza potwierdzona.
- Repozytorium: https://github.com/envirosolutionspl/pobieracz_danych_gugik (issues: .../issues). Licencja: plik LICENSE w repo (typ nie sprawdzany — przed jakimkolwiek kopiowaniem kodu sprawdzic).
- Wersja analizowana: **1.3.9** (metadata.txt; commit `4d5fc8a`, 2026-09-23; ZIP z plugins.qgis.org ma ten sam hash w naglowku). QGIS min. 3.28; Qt5/Qt6.
- Lokalnie: archiwum `/tmp/claude-2001/pobieraczek/zip/p.zip`, klon `/tmp/claude-2001/pobieraczek/src` (git, 97 commitow; brak katalogu `tests/` w repo — wtyczka nie ma testow jednostkowych, tylko CI flake8/bandit/zgodnosc Qt w `.github/workflows`).
- Sciezki ponizej wzgledem korzenia repo wtyczki.

## 1. Uslugi/endpointy wyszukiwania arkuszy

Wtyczka ma DWA niezalezne mechanizmy wyszukiwania, oba na `mapy.geoportal.gov.pl/wss/service/PZGIK/...` (stale w `constants.py`):

### 1a. Zakladki "WMS/Geoportal" — WMS GetFeatureInfo (text/html), ten sam co Kartograf

- Endpointy (`constants.py`, ~linie 1-30): `NMT_EVRF_WMS_URL = .../PZGIK/NMT/WMS/SkorowidzeUkladEVRF2007?`,
  `NMT_GRID5M_WMS_URL = .../NMT/WMS/SheetsGrid5mEVRF2007?`, `NMT_KRON86_WMS_URL = .../NMT/WMS/SkorowidzeUkladKRON86?`,
  `NMPT_EVRF/KRON86`, `LAS_EVRF_WMS_URL = .../DanePomiaroweNMT/WMS/SkorowidzeUkladEVRF2007?`, `LAS_KRON86...`,
  `ORTOFOTOMAPA_WMS_URL = .../ORTO/WMS/SkorowidzeWgAktualnosci?`.
- Parametry zapytania (`constants.py` `WMS_GET_FEATURE_INFO_PARAMS`): WMS 1.3.0, `crs=EPSG:2180`, `width=height=101`, `i=j=50`,
  `INFO_FORMAT=text/html`; bbox to **kwadrat 100 x 100 m wokol punktu** (`bbox = '%f,%f,%f,%f' % (y-50, x-50, y+50, x+50)`, `nmt_api.py`).
  Nie ustawia `FEATURE_COUNT` (zachowanie serwera przy domyslnej wartosci — nie ustalono).
- **Wszystkie warstwy naraz, bez zaszytej listy:** `ServiceAPI.getAllLayers()` (`utils.py`) robi GetCapabilities i bierze
  kazda `Layer/Name`; potem jedno GetFeatureInfo z `layers=','.join(layers)` i `query_layers` tym samym
  (`nmt_api.py::getNmtListbyPoint1992`, `las_api.py`, `ortofoto_api.py`). To dokladnie to samo podejscie, ktore Kartograf ma
  w skorowidzu (warstwy z GetCapabilities) — roznica: Kartograf odpytuje warstwy sekwencyjnie wg wersji (rok), wtyczka wszystkie w jednym zapytaniu.
- Parsowanie: `wms/utils.py::getWmsObjects` wyciaga regexem `\{{1}.*\}{1}` obiekty `{...}` z HTML i dzieli `split(',')`/`split(':')`
  (kruche: przecinek lub dwukropek w wartosci psuje rekord; dwukropek jest obslugiwany specjalnie, przecinek nie).
  Dedup: `FilterUtils.removeDuplicatesFromListOfDicts` (frozenset par).
- Mapowanie pol rekordu -> kolumny raportu w `constants.py::HEADERS_MAPPING` (`NMT_HEADERS`, `LAS_HEADERS`, ...): potwierdza ten sam
  zestaw atrybutow, ktory zna Kartograf: `url`, `godlo`, `aktualnosc`, `aktualnoscRok`, `charakterystykaPrzestrzenna`, `bladSredniWysokosci`,
  `ukladWspolrzednych`, `ukladWysokosci`, `calyArkuszWyeplnionyTrescia`, `numerZgloszeniaPracy`, `zrDanych` (NMT/NMPT) / `zrodloDanych` (orto), `dt_pzgik`, `kolor`, `wielkoscPiksela`.
- UWAGA na pisownie: wtyczka uzywa klucza **`calyArkuszWyeplnionyTrescia`** ("Wyeplniony"), a fixtury Kartografa
  (`tests/fixtures/gugik_skorowidz/real_2026_10_06/...`) zawieraja **`calyArkuszWypelnionyTrescia`**. Wniosek (nie sprawdzany na zywo
  w samej wtyczce): jesli serwer zwraca "Wypelniony", filtr "caly arkusz" we wtyczce nie dopasuje niczego, gdy uzytkownik wybierze wartosc inna niz "wszystkie";
  kolumna raportu tez bedzie pusta. Kartograf (`skorowidz.py:144`) obsluguje oba warianty — zostawic.
- Dla NMT w EVRF2007 wtyczka odpytuje dwa serwisy (1 m `SkorowidzeUkladEVRF2007` i 5 m `SheetsGrid5mEVRF2007`) i **skleja listy** (`nmt_api.py`);
  w KRON86 tylko `SkorowidzeUkladKRON86`. Rozdzielczosc rozroznia potem po `charakterystykaPrzestrzenna` (filtr "piksel od/do").
  Issue #295 (otwarty): brak filtra 1 m / 5 m wprost; issue #211 (zamkniete): kiedys wtyczka nie znajdowala 1 m.
- Pokrycie obszaru (wielokat/linia) = **probkowanie punktami**: `LayersUtils.createPointsFromPolygon` (siatka `qgis:creategrid` + wierzcholki uproszczonego
  wielokata), `createPointsFromLineLayer` (`densifyByDistance`). Gestosc: NMT 400 m, NMPT 200 m, LAZ 250 m, ortofoto 1000 m (domyslna `pointsFromVectorLayer(density=1000)`),
  `pobieracz_danych_gugik.py` ~linie 701, 873, 2371. Jedno zapytanie GetFeatureInfo (+ GetCapabilities) na punkt. Konsekwencja (wniosek z kodu): arkusz
  mniejszy niz oczko siatki moze zostac pominiety — wtyczka nie gwarantuje kompletnosci; Kartograf operuje na arkuszach, wiec ten problem go nie dotyczy.

### 1b. Zakladka "WFS" — **maszynowe skorowidze WFS z geometria** (to jest ten brakujacy endpoint)

- `constants.py` ~519-528 `WFS_URL_MAPPING`:
  ```
  'Ortofotomapa':          '.../PZGIK/ORTO/WFS/Skorowidze'
  'Prawdziwa Ortofotomapa':'.../PZGIK/ORTO/WFS/SkorowidzPrawdziwejOrtofotomapy'
  'LIDAR (PL-KRON86-NH)':  '.../PZGIK/DanePomiaroweLidarKRON86/WFS/Skorowidze'
  'LIDAR (PL-EVRF2007-NH)':'.../PZGIK/DanePomiaroweLidarEVRF2007/WFS/Skorowidze'
  'NMT (PL-KRON86-NH)':    '.../PZGIK/NumerycznyModelTerenuKRON86/WFS/Skorowidze'
  'NMT (PL-EVRF2007-NH)':  '.../PZGIK/NumerycznyModelTerenuEVRF2007/WFS/Skorowidze'
  'NMPT (PL-KRON86-NH)' / 'NMPT (PL-EVRF2007-NH)': '.../NumerycznyModelPokryciaTerenu{KRON86,EVRF2007}/WFS/Skorowidze'
  ```
- Kod: `wfs/wfs_service.py::WfsFetch.getWfsListbyLayer1992` (QGIS `QgsVectorLayer(..., "WFS")`, WFS 2.0.0, `srsname=EPSG:2180`,
  filtr `intersects($geometry, geomFromWKT(...))` z uproszczonym i zaaggregowanym wielokatem); typenames z GetCapabilities
  (`wfs/utils.py::getTypenamesFromWFS`, slownik Title->Name). Uzytkownik wybiera **jedna warstwe-rok** w `wfs_layer_cmbbx`.
  Plik do pobrania pochodzi z atrybutu `feat['url_do_pobrania']` (`pobieracz_danych_gugik.py::downloadWfsForLayer`, ~linia 460); deduplikacja po URL.
- **Potwierdzone na zywo (2026-10-07)** — odpowiedzi serwera:
  - GetCapabilities NMT EVRF2007 WFS: feature types `gugik:SkorowidzNMT2018` ... `gugik:SkorowidzNMT2026` (osobna warstwa na rok), `DefaultCRS urn:ogc:def:crs:EPSG::2180`,
    wersje WFS 1.0.0/1.1.0/2.0.0, formaty m.in. `application/gml+xml; version=3.2`, `text/xml; subtype=gml/3.1.1`.
  - LIDAR EVRF2007: `gugik:SkorowidzDanychPomiarowychLIDAR2018..2026`; NMPT EVRF2007: `gugik:SkorowidzNMPT2019..2026`;
    ortofotomapa: `gugik:SkorowidzOrtofomapy1957..2026` (literowka "Ortofomapy" w nazwie jest po stronie serwera; osobna warstwa na KAZDY rok, takze archiwalne).
  - Przykladowy rekord NMT 2025 (`GetFeature ... TYPENAMES=gugik:SkorowidzNMT2025&COUNT=2`):
    ```
    <gugik:godlo>N-33-58-A-c-3-2</gugik:godlo> <gugik:akt_rok>2025</gugik:akt_rok> <gugik:asortyment>NMT</gugik:asortyment>
    <gugik:format>ARC/INFO ASCII GRID</gugik:format> <gugik:char_przestrz>0.50 m</gugik:char_przestrz> <gugik:blad_sr_wys>0.15</gugik:blad_sr_wys>
    <gugik:uklad_xy>PL-1992</gugik:uklad_xy> <gugik:modul_archiwizacji>1:5000</gugik:modul_archiwizacji> <gugik:uklad_h>PL-EVRF2007-NH</gugik:uklad_h>
    <gugik:nr_zglosz>DFT.7201.024.2024</gugik:nr_zglosz> <gugik:akt_data>...<gml:timePosition>2025-01-30</gml:timePosition>
    <gugik:czy_ark_wypelniony>NIE</gugik:czy_ark_wypelniony>
    <gugik:url_do_pobrania>https://opendata.geoportal.gov.pl/NumDaneWys/NMT/84020/84020_1844084_N-33-58-A-c-3-2.asc</gugik:url_do_pobrania>
    <gugik:zrodlo_danych>Skaning laserowy</gugik:zrodlo_danych> <gugik:dt_pzgik>...2026-05-26 <gugik:blad_sr_syt>0.20
    ```
    plus `gugik:msGeometry` = **wielokat rzeczywistego zasiegu danych w EPSG:2180** (nie prostokat arkusza — przyklad: 17-wierzcholkowy
    wielokat o wymiarach ~2,4 x 2,1 km, `czy_ark_wypelniony=NIE`). `numberMatched="unknown"`, odpowiedz ma atrybut `next=...&STARTINDEX=2` (paginacja serwerowa).
  - LAZ (`SkorowidzDanychPomiarowychLIDAR2025`): `godlo` (np. `N-33-58-A-d-1-2-4-1`, modul 1:1250), `format=LAZ`, **`char_przestrz=5 p/m2` (gestosc punktow)**, `blad_sr_wys`, `blad_sr_syt`,
    `uklad_xy`, `uklad_h`, `url_do_pobrania` (`.../NumDaneWys/DanePomiaroweLAZ/84016/84016_1844450_<godlo>.laz`), `czy_ark_wypelniony`, `nr_zglosz`, `dt_pzgik`.
  - Ortofoto (`SkorowidzOrtofomapy2025`): `piksel=0.1`, `kolor=RGB|CIR`, `zrodlo_danych`, `uklad_xy`, `modul_archiwizacji`, `nr_zglosz`, `akt_data`, `czy_ark_wypelniony`, `url_do_pobrania`, `dt_pzgik`, **`wlk_pliku_mb`** (rozmiar pliku — przydatne do kontroli miejsca/limitow).
  - Nazwy pol WFS sa inne niz w WMS HTML (`akt_rok` vs `aktualnoscRok`, `czy_ark_wypelniony` vs `calyArkuszWypelnionyTrescia`, `char_przestrz` vs `charakterystykaPrzestrzenna`, `uklad_h`, `url_do_pobrania` vs `url`).
- Stala `ORTOFOTOMAPA_WFS_URL` i filtry ortofoto WFS: `wfs/utils.py::filterWfsFeaturesByUsersInput` (kolor, zrodlo_danych, uklad_xy, piksel od/do) po atrybutach `kolor`, `zrodlo_danych`, `uklad_xy`, `piksel` — to samo, co zwraca serwer powyzej.
- **Wazne dla Kartografa:** wtyczka NIE uzywa tego WFS do wyboru kampanii (brak filtra roku/najnowszej w zakladce WFS; wybor roku = wybor warstwy), ale endpoint istnieje, jest stabilny
  w uzyciu produkcyjnym wtyczki i daje (a) geometrie zasiegu kampanii, (b) paginacje, (c) wszystkie lata archiwalne w jednym serwisie, (d) maszynowe pola bez parsowania HTML.
  Czy WFS jest tak samo aktualny jak WMS (np. rekordy dodane tego samego dnia) — nie ustalono; trzeba porownac z fixturami `real_2026_10_06`.
- Inne uzywane API: ULDK `https://uldk.gugik.gov.pl/` — tylko jako ping sprawdzenia internetu (`ServiceAPI.checkInternetConnection`); `rest.envirosolutions.pl/dzialki` (wlasne API EnviroSolutions
  dla TERYT: wojewodztwa/powiaty/gminy). Paczki BDOT10k: `https://opendata.geoportal.gov.pl/bdot10k/...` i `.../Archiwum/bdot10k/`; BDOO, PRG (`integracja.gugik.gov.pl/PRG/pobierz.php?`), PRNG, EGiB (WFS `integracja.gugik.gov.pl/eziudp/...`).

## 2. Wybor kampanii/roku i filtry w UI

Dla NMT/NMPT/LAZ/ortofoto (zakladki WMS) — `pobieracz_danych_gugik.py::filterNmtList` (~801), `filterLasList` (~945), `filterOrtoList` (~630):

- Pobiera WSZYSTKIE rekordy ze wszystkich warstw-lat dla punktow, potem filtruje lokalnie. Brak wyboru kampanii z listy dla arkusza.
- Checkbox **"Pobierz tylko aktualne dane"** (`nmt_newest_chkbx`, `orto_newest_chkbx`, `laz_newest_chkbx`) **domyslnie wlaczony**
  (`pobieracz_danych_gugik_base.py` ~236, ~393). Tooltip: "Gdy zostanie znalezione wiecej niz 1 zobrazowanie dla danego arkusza ... zostanie pobrane tylko jedno - najnowsze."
- Filtry w grupie (`*_filter_groupBox`): uklad XY (`ukladWspolrzednychPoziomych`), **data od / do** (po polu `aktualnosc`, domyslnie od 1995-01-01; nie rok, tylko data),
  "caly arkusz wypelniony trescia" (wszystkie/TAK/NIE), rozmiar oczka/piksela od-do (`charakterystykaPrzestrzenna` / `wielkoscPiksela`), blad sredni wysokosci od-do (`bladSredniWysokosci`; NMT, LAZ),
  dla ortofoto dodatkowo **kolor** (RGB/CIR) i **zrodlo danych**. Format NMT (ARC/INFO ASCII GRID vs ASCII XYZ GRID) — osobne radio.
  Uklad wysokosci (KRON86/EVRF2007) = radio wybierajace USLUGE, nie filtr rekordow.
- Brak: filtra "tylko rok X", progu gestosci punktow LAZ wprost (jest tylko "rozmiar oczka od-do" na polu `charakterystykaPrzestrzenna`, w las_api parsowane `float(...split()[0])` — czyli "5 p/m2" -> 5.0, ale filtr `ParsingUtils.getSafelyFloat`), wyboru 1 m/5 m wprost (issue #295 otwarty).
- Bledy w filtrach dat: `if self.dockwidget.nmt_from_dateTimeEdit.date():` jest zawsze prawdziwe (obiekt QDate), wiec filtr dat dziala zawsze (domyslnie 1995-01-01 .. dzis) — to skutkuje poprawnie, ale nie jako "opcjonalny" filtr.
- Zakladka WFS: filtr tylko dla ortofoto (kolor, zrodlo, uklad, piksel od-do); dla NMT/NMPT/LIDAR brak jakichkolwiek filtrow poza wyborem warstwy-roku.

## 3. Wiele kampanii tego samego arkusza i arkusze niepelne

- `FilterUtils.onlyNewest` (`utils.py`, ~linia 130):
  ```python
  if godlo not in updated_dict or aktualnosc > updated_dict[godlo].get('aktualnosc'):
      updated_dict[godlo] = data_file
  ```
  Klucz = samo `godlo`; porownanie po polu `aktualnosc` (tekst "YYYY-MM-DD"; w LAZ po `_convertAttributes` obiekt `date`). **Nie uwzglednia**:
  `calyArkuszWypelnionyTrescia`, pokrycia, rozdzielczosci (1 m vs 5 m ma ten sam godlo!), formatu (ASC vs XYZ), koloru ortofoto (RGB vs CIR przy tym samym godle — "losowe pobieranie RGB i CIR", issue #220),
  `dt_pzgik` ani numeru zgloszenia. Remis `aktualnosc` -> wygrywa pierwszy rekord (kolejnosc odpowiedzi serwera, niedeterministyczna z punktu widzenia uzytkownika).
  Konsekwencja: wtyczka ma dokladnie ten blad, o ktorym pisze zadanie — najnowsza, ale niepelna kampania (np. 0,9 % arkusza) wygrywa nad starsza pelna, a w NMT 1 m + 5 m dla tego samego godla zostanie jedna (wg daty).
  Filtr "caly arkusz = TAK" jest jedyna ochrona, jest recznie wlaczany i (por. pkt 1a) moze byc martwy z powodu literowki klucza.
- Gdy checkbox "tylko aktualne" jest wylaczony: pobierane sa WSZYSTKIE kampanie wszystkich arkuszy (po filtrach) — odpowiednik `all` w Kartografie.
- Brak logiki scalania/maskowania (mozaikowania) wielu kampanii; wtyczka tylko pobiera pliki. Brak sprawdzania rzeczywistego zasiegu (a WFS go ma — pkt 1b).
- Brak ostrzezenia o niepelnosci arkusza w UI.
- Dedup wyszukiwania: dedup rekordow po frozenset par (`removeDuplicatesFromListOfDicts`); issue #245/PR #246 (duplikacja `las_list` — zamkniete).

## 4. Nazewnictwo i uklad plikow

- `ServiceAPI.retreiveFile` (`utils.py`): `file_name = url.split('/')[-1]`, plik trafia **plasko** do jednego katalogu `destFolder` (bez podkatalogow produkt/rok/uklad).
  Nazwy GUGiK zawieraja identyfikator zgloszenia i rekordu: `84020_1844084_N-33-58-A-c-3-2.asc`, `.../DanePomiaroweLAZ/84016/84016_1844450_<godlo>.laz`,
  `.../ortofotomapa/84022/84022_1594540_N-33-58-A-c-1-3.tif` — **czesc przed godlem rozrozniala kampanie**, wiec rozne kampanie tego samego arkusza NIE nadpisuja sie nawzajem (zalozenie z przykladow URL; brak testow w repo).
- Prefiksy tylko dla paczek (BDOT10k `bdot10k_`, archiwalny BDOT `archiwalne_bdot10k_<rok>_`, BDOO `bdoo_rok<rok>_`, EGiB, PRG, osnowa, Budynki3D LOD1/LOD2).
- Przed pobraniem `cleanupFile(path)` **usuwa istniejacy plik o tej nazwie** (zawsze pobiera od nowa; brak cache, brak wznawiania, brak sprawdzania rozmiaru/sumy); po bledzie usuwa plik czesciowy.
- Obok danych tworzony jest raport TXT `pobieracz_<nmt|nmpt|las|ortofoto>_<YYYYMMDDHHMMSS>.txt` (`FileUtils.createReport`, naglowki z `HEADERS_MAPPING`, CSV bez cudzyslowow;
  w `LAS_HEADERS` literowka `'aktulnosc'` -> pusta kolumna). To odpowiednik naszego sidecara, ale jeden zbiorczy plik na zadanie, bez CRS/licencji/nodata.
- Po zakonczeniu: `FileUtils.openFile(destFolder)` otwiera katalog w menedzerze plikow (dla kazdego pobranego pliku).
- Brak rozrozniania kampanii w sciezce (rok/numer zgloszenia) — Kartograf (ADR-026) jest tu znacznie bardziej uporzadkowany.

## 5. Infrastruktura GUGiK: rownoleglosc, ponowienia, limity, UA, cache

- **Rownoleglosc:** brak. Kazde zadanie to jeden `QgsTask` (`tasks/downloadNmtTask.py`, `downloadLasTask.py`, `downloadOrtoFotoTask.py`), plik po pliku sekwencyjnie w petli `for`.
  Wyszukiwanie punktow tez sekwencyjne w watku GUI (z `QCoreApplication.processEvents()` i modalnym "Trwa wyszukiwanie danych...").
- **Ponowienia:** tylko dla metadanych: `ServiceAPI.getRequest` (`utils.py`) petla `while attempt <= MAX_ATTEMPTS` (`MAX_ATTEMPTS = 3` => faktycznie 4 proby) ze stalym `time.sleep(2)`, timeout `TIMEOUT_MS*2 = 10 s`.
  Dla plikow: jedna proba Qt (`TimeoutAttribute = 5000 ms`) + jedna proba zastepcza przez `requests` (`_downloadFileWithRequests`) — bez backoffu.
- **Fallback SSL:** `NetworkUtils._getSessionWithLegacySsl` + `LegacySslAdapter`: `OP_LEGACY_SERVER_CONNECT`, `check_hostname=False`, `verify_mode=CERT_NONE`, `verify=False`, `urllib3.disable_warnings`.
  Wprowadzone po issue #266 ("Nawiazanie sesji SSL zakonczone bledem" przy `opendata.geoportal.gov.pl`, kwiecien 2026). Wtyczka wiec rutynowo wylacza weryfikacje certyfikatu — NIE do przejecia.
  Wazne informacyjnie: w 2026-04 serwery GUGiK odrzucaly niektore klienty na handshake SSL (legacy renegotiation).
- **User-Agent:** `USER_AGENT_HEADER = "Pobieracz-QGIS-Client/1.0"` + `Connection: close` ustawiane TYLKO w sesji `requests` (fallback); sciezka Qt uzywa domyslnego UA QGIS. Nie przekazuje kontaktu.
- **Limity/obciazenie:** brak limitu zapytan, brak throttlingu miedzy punktami (1 GetCapabilities + 1 GetFeatureInfo na punkt, brak cache GetCapabilities — `getAllLayers` jest wolane PRZY KAZDYM punkcie; tzn. dla N punktow 2N zapytan, wczytujacych pelny XML),
  brak ograniczenia na rozmiar. Issue #250 (zamkniete): QGIS zawieszal sie przy pobieraniu duzego obszaru; rozwiazanie = potwierdzenie "Znaleziono N plikow ... Czy pobrac?" i komunikat dla duzych zadan, bez twardego limitu.
- **Cache:** brak (ani metadanych, ani plikow). Uzywa `QgsBlockingNetworkRequest` + `QgsNetworkAccessManager` proxy QGIS (issue #210 proxy). Nie ustalono, czy QGIS cache HTTP wplywa na GetFeatureInfo.
- **HTTP Range / wznawianie:** nie uzywane (zgodne z naszym odkryciem, ze `opendata.geoportal.gov.pl` nie obsluguje Range).
- Kontrola poprawnosci pobrania: stala `MIN_FILE_SIZE = 9000` istnieje w `constants.py`, ale (grep) nie jest uzywana w sciezce `retreiveFile`; walidacja pliku (rozmiar/format) — nie ustalono / brak.

## 6. LAZ i ortofoto

- **LAZ:** dwa tory. (1) WMS GetFeatureInfo (`las_api.py::getLasListbyPoint1992`) na `PZGIK/DanePomiaroweNMT/WMS/SkorowidzeUkladEVRF2007|KRON86` — czyli WMS DZIALA dla wtyczki bez 401
  (Kartograf w pamieci/wiedzy ma "WMS dla LAZ zwraca 401" — inny serwis/sciezka; endpointy `DanePomiaroweNMT/WMS` tu dzialaja w produkcji wtyczki; nie weryfikowano na zywo). W komentarzu `ortofoto_api.py` na gorze widac stary wzorzec
  `.../DanePomiarowe/5020/..._M-34-52-C-d-1-3-2.las` i nowy `.../DanePomiaroweLAZ/.../*.laz` (od v0.7.0 wtyczka pobiera LAZ zamiast LAS).
  (2) WFS `DanePomiaroweLidar{KRON86,EVRF2007}/WFS/Skorowidze` (pkt 1b) z geometria i `char_przestrz` ("5 p/m2").
  Uklad wysokosci wybierany radio (`las_evrf2007_rdbtn`) -> inny serwis. Rok: tylko filtr dat `aktualnosc` od-do + "tylko aktualne"; gestosc: pole "rozmiar oczka od-do" (`charakterystykaPrzestrzenna`),
  blad wysokosci od-do, caly arkusz. W LAZ `_convertAttributes` konwertuje `aktualnosc` -> `date`, `charakterystykaPrzestrzenna` -> `float(split()[0])`, `aktualnoscRok` -> `int`.
  Kafle LAZ to arkusze 1:1250 (`modul_archiwizacji`), godlo ma 8 segmentow (`N-33-58-A-d-1-2-4-1`). Issue #222 (zamkniete): "Nie znajduje danych do pobrania LAZ".
- **Ortofoto:** WMS `ORTO/WMS/SkorowidzeWgAktualnosci` (warstwy rocznikowe z GetCapabilities) lub WFS `ORTO/WFS/Skorowidze` (warstwa na rok). Filtry: kolor (RGB/CIR), uklad, zrodlo danych, piksel od-do,
  caly arkusz, daty. Domyslnie "wszystkie" kolory -> przy "tylko aktualne" RGB i CIR tego samego godla konkuruja o jeden slot (issue #220 "losowe pobieranie RGB i CIR"); poprawka w v1.3.0: "Dodanie filtracji dla pobierania Ortofotomapy WFS" (tylko zakladka WFS).
  Rozdzielczosc: `wielkoscPiksela` (WMS) / `piksel` (WFS, np. `0.1`); rozmiar pliku w WFS `wlk_pliku_mb`.
- NMT: formaty ARC/INFO ASCII GRID i ASCII XYZ GRID (radio), uklad wysokosci wybor uslugi, patrz pkt 1-2. NMPT: analogicznie (200 m probkowanie).
- BDOT10k: paczki powiatowe/wojewodzkie/krajowe (SHP/GML/GPKG, geoparquet tylko dla kraju), pobierane po TERYT z `opendata.geoportal.gov.pl/bdot10k/`; archiwalne po roku. Bez wyboru warstw (cala paczka) — jak w Kartografie (ADR-016).

## 7. Co przejac / czego unikac

Warto przejac (do rozwazenia w ADR/planie strategii kampanii):
1. **WFS skorowidze (`.../WFS/Skorowidze`) jako zrodlo rekordow w formacie maszynowym** — zwlaszcza `msGeometry` (rzeczywisty zasieg danych) + `czy_ark_wypelniony` do wykrywania niepelnych kampanii (przypadek 0,9 %);
   pozwoli policzyc pokrycie (pole przeciecia z prostokatem arkusza) i wybrac "najnowsza, ktora pokrywa >= X %" zamiast samej `aktualnosc`. Atrybuty rok: `akt_rok`, gestosc LAZ: `char_przestrz`, rozmiar ortofoto: `wlk_pliku_mb`.
   Wymaga: sprawdzenia spojnosci WFS vs WMS (swiezosc, brak kampanii, zgodnosc URL), ewentualnie jako ZRODLO UZUPELNIAJACE przy WMS (np. przy `strategy=all` i lata archiwalne ortofoto 1957+).
2. Warstwa-rok w WFS = naturalny dolny prog roku (`year_from`): wystarczy pominac warstwy `< rok` bez pytania o nie; WMS tez ma warstwy rocznikowe, ale z agregatem `...2023iStarsze` (granulacja roczna tracona).
3. Raport TXT dla uzytkownika (zawartosc pol skorowidza obok plikow) — Kartograf ma lepsze sidecary `.meta.json`; mozna dodac pola kampanii (`aktualnosc`, `numerZgloszeniaPracy`, `calyArkuszWypelnionyTrescia`, `dt_pzgik`) do `extra`, jesli jeszcze nie ma.
4. Potwierdzenie "Znaleziono N plikow. Pobrac?" przed duzym pobraniem (u nas: `--dry-run`/lista; wtyczka dodala po issue #250).
5. Wtyczka przechowuje nazwe pliku z URL (zawiera numer zgloszenia + id rekordu) — Kartograf powinien zachowac to rozroznienie w nazwie/sciezce dla `strategy=all` (inaczej kolizje nazw przy roznych kampaniach tego samego arkusza — sprawdzic w naszym FileStorage).

Czego unikac (bledy wtyczki widoczne w kodzie i issues):
1. `onlyNewest` po samym `godlo` + `aktualnosc` — ignoruje pelnosc arkusza, rozdzielczosc (1 m/5 m), kolor (RGB/CIR), format; remis nierozstrzygany. (Dokladnie nasz przypadek niepelnej najnowszej kampanii.)
2. Kruche parsowanie HTML GetFeatureInfo regexem + `split(',')`/`split(':')` (`wms/utils.py`) — przecinek w wartosci lamie rekord; nasz parser skorowidza jest lepszy; nie cofac sie.
3. Probkowanie punktami zamiast arkuszami (brak gwarancji kompletnosci) oraz GetCapabilities przy KAZDYM punkcie bez cache.
4. Wylaczanie weryfikacji SSL (`verify=False`, `CERT_NONE`, `OP_LEGACY_SERVER_CONNECT`) jako domyslny fallback — nie kopiowac; jesli GUGiK znowu zerwie handshake (issue #266), obsluzyc swiadomie.
5. Niespojny kontrakt zwrotny (`getNmtListbyPoint1992` zwraca krotke `(bool, lista|str)`, NMPT listę — issue #300/PR #301: znaki komunikatu dopisywane do listy rekordow -> `AttributeError`); u nas bledy = wyjatki (`NoCoverageError`), zachowac.
6. Literowki kluczy (`calyArkuszWyeplnionyTrescia`, `'aktulnosc'`) — cichy brak dopasowania; trzymac test na prawdziwych fixturach (mamy).
7. Brak wznawiania/weryfikacji pobranego pliku, nadpisywanie przy kazdym pobraniu, sekwencyjne pobieranie i brak backoffu — Kartograf ma juz lepiej; nic nie przejmowac.
8. Dosc dziwny dedup/regresje: duplikacja `las_list` (#245), `ValueError: could not convert string to float: '1.00 m'` (#243) — dane skorowidza maja jednostki w polach liczbowych ("1.00 m", "5 p/m2", "0.50 m"); uwaga przy parsowaniu `char_przestrz` w WFS.
9. Dla duzych obszarow wtyczka zawiesza QGIS (issue #250) — u nas potrzebny limit/`--max-sheets` i komunikat o liczbie plikow przed pobraniem.

## 8. Czego nie ustalono

- Licencja wtyczki (typ) i warunki ponownego uzycia kodu — nie sprawdzano zawartosci LICENSE.
- Domyslny `FEATURE_COUNT` serwera GetFeatureInfo i czy wiele rekordow z tej samej warstwy-roku dla jednego punktu jest zwracanych wszystkie (wtyczka go nie ustawia).
- Rzeczywista rozbieznosc/zgodnosc skorowidzy WFS vs WMS (kompletnosc rekordow, swiezosc) — tylko probki (`COUNT=1..2`), nie porownywano z fixturami `real_2026_10_06`.
- Limity serwera GUGiK (rate limiting, WAF) — wtyczka nie dokumentuje; brak informacji w issues.
- Czy wtyczka rzeczywiscie nie nadpisuje plikow kampanii o tej samej nazwie (zalozenie z formatu URL, nie z testu).
- Wplyw cache QGIS na zapytania metadanych.
- Zawartosc wiekszosci issues (przeczytano tytuly wszystkich ~100 ostatnich i tresci #211, #220, #222, #243, #245, #250, #266, #295, #300, #301; nie czytano komentarzy).

## Zrodla

- https://plugins.qgis.org/plugins/pobieracz_danych_gugik/ (strona wtyczki; wersja 1.3.9 z 2026-09-23)
- https://github.com/envirosolutionspl/pobieracz_danych_gugik (kod; commit 4d5fc8a), issues: #211, #220, #222, #243, #245, #250, #266, #295, #300, #301
- Pliki: `constants.py`, `nmt_api.py`, `nmpt_api.py`, `las_api.py`, `ortofoto_api.py`, `utils.py` (`FilterUtils.onlyNewest`, `ServiceAPI`, `NetworkUtils`, `LayersUtils`), `wms/utils.py`,
  `wfs/wfs_service.py`, `wfs/utils.py`, `pobieracz_danych_gugik.py` (`filterNmtList`, `filterLasList`, `filterOrtoList`, `downloadWfsForLayer`), `pobieracz_danych_gugik_base.py` (UI), `tasks/download*Task.py`
- Zywe sondy 2026-10-07: `https://mapy.geoportal.gov.pl/wss/service/PZGIK/NumerycznyModelTerenuEVRF2007/WFS/Skorowidze`, `.../DanePomiaroweLidarEVRF2007/WFS/Skorowidze`, `.../ORTO/WFS/Skorowidze`, `.../NumerycznyModelPokryciaTerenuEVRF2007/WFS/Skorowidze` (GetCapabilities + GetFeature COUNT<=2)

## Errata koordynatora (2026-10-07, weryfikacja na zywo)

**Punkt "msGeometry = rzeczywisty zasieg danych" jest NIEPRAWDZIWY dla NMT.**
`NumerycznyModelTerenuEVRF2007/WFS/Skorowidze`, GetFeature (WFS 2.0.0,
`BBOX=...,urn:ogc:def:crs:EPSG::2180`) dla N-34-139-C-a-3-1 w warstwie
`gugik:SkorowidzNMT2025`: dwa obiekty — pelny `83233_1744736` (TAK) i
`84183_1852496` (NIE, faktycznie 0,9 % pokrycia, plik 255x422 px). Oba maja
IDENTYCZNA geometrie: wielokat ramy arkusza, 17 wierzcholkow, 4,958 km2.
Tak samo N-34-144-C-c-2-2 (17,9 % pokrycia, geometria 4,972 km2 = rama).
Pokrycia kampanii NIE da sie wyznaczyc z WFS. Surowe odpowiedzi:
`<katalog-danych>/kartograf/e2e/2026-10-07-pokrycie-kampanii/*.xml`.

Co z WFS jest uzyteczne (potwierdzone): warstwy **jednoroczne**
`gugik:SkorowidzNMT2018..2026` (bez warstw zbiorczych "iStarsze"), format
maszynowy GML, zapytanie bboxem obszaru zwraca wszystkie arkusze roku jednym
zapytaniem (zamiast GetFeatureInfo per arkusz i warstwa), pola
`czy_ark_wypelniony`, `char_przestrz`, `url_do_pobrania`. Pole `akt_data`
w tej odpowiedzi nie wystapilo pod ta nazwa (do ustalenia: nazwa pola daty
w NMT). Brak warstw sprzed 2018 w EVRF2007 (KRON86 — nie sprawdzono).
Zgodnosc rekordow WFS z WMS — nie sprawdzono systematycznie (2 arkusze zgodne).
