# Changelog

Wszystkie istotne zmiany w projekcie sa dokumentowane w tym pliku.

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.2] - Unreleased

### Naprawione

- Zapytanie o powiaty BDOT10k (WFS PRG) rozszerza obszar na zewnatrz
  z dokladnoscia do milimetra; wczesniej zaokraglenie do pelnych metrow
  moglo pominac powiat stykajacy sie z obszarem w pasie do 0,5 m,
  a `teryt_for_point` pytal raz o sam punkt, raz o kwadrat 2 m.
- WFS PRG: odpowiedz, w ktorej `numberReturned` rozni sie od liczby
  odczytanych kodow powiatow, konczy sie `DownloadError` zamiast cicho
  krotszej listy powiatow (i brakujacego pakietu BDOT10k).
- BDOT10k: opcja `timeout` (`Bdot10kProvider.download_by_bbox/godlo`,
  `LandCoverManager.download_by_bbox/godlo/download_all_counties`)
  dziala tez na zapytanie o powiat w WFS PRG; wczesniej to zapytanie
  mialo zawsze 30 s. Bez `timeout` w menedzerze zostaje 30 s.
- Godla z cyframi spoza ASCII (np. pelnej szerokosci `M-３３-８-A`,
  `6.１４５.２０`, CZ `７３０_５５５５`) sa odrzucane (`ParseError`);
  wczesniej PL-1992 i PL-2000 przechodzily walidacje i trafialy do sciezek
  i sidecarow w innej postaci niz godlo GUGiK. Co zrobic: podac godlo
  cyframi `0-9`.
- BDOT10k `keep_raw=True`: nieudany zapis oryginalnego ZIP przy ponownym
  pobraniu zostawia poprzedni GPKG i jego sidecar bez zmian (scalony GPKG
  zastepuje poprzedni dopiero po zapisie ZIP). Wczesniej poprzedni GPKG
  byl nadpisany, a potem usuniety, i zostawal sidecar bez pliku danych.

## [0.7.1] - 2026-10-09

### Dodane

- Roadmapa do v1.0.0 w dokumentacji (`docs/SCOPE.md` 3.3, `docs/PRD.md`
  sekcja 8): komplet publicznych danych GUGiK, gotowe dane dla kazdego
  produktu, manager danych (magazyn wersjonowany, manifest projektu),
  wtyczka QGIS i GUI webowe.
- Stabilne publiczne API: `get_with_retry`, `make_gugik_session`,
  `mosaic_and_crop`, `check_source_grid` eksportowane z `kartograf`.
- `MetadataCache(strict=True)`: blad SQLite konczy sie `CacheError`
  (nowy wyjatek) zamiast cichego wylaczenia cache.
- Sidecar: `sha256` i `size_bytes` pliku danych na gornym poziomie
  (wszystkie produkty). Sidecar arkusza NMT/NMPT/orto: w `extra.source`
  `height_rmse_m`, `position_rmse_m`, `archive_module`,
  `declared_vertical_crs` z rekordu skorowidza. Wpisy cache rekordow
  sprzed 0.7.1 sa odpytywane ponownie.
- Weryfikacja arkuszy GUGiK (B4): URL rekordu skorowidza musi zawierac
  godlo (NMT, NMPT, orto), a zasieg z naglowka ASC (NMT/NMPT) musi lezec
  w ramie godla (co najmniej 50 % powierzchni pliku, rama w ukladzie
  pliku — arkusze PL-2000 publikowane w EPSG:2180 przechodza);
  rozbieznosc = `DownloadError` arkusza, plik nie zostaje zapisany.
- `discover_teryts_for_bbox(bbox, *, session, cache)` i
  `teryt_for_point(x, y, crs, ...)`: kody TERYT powiatow z WFS PRG GUGiK
  (filtr po geometrii); blad uslugi albo lista obcieta stronicowaniem =
  `DownloadError`, pusta lista tylko przy poprawnej odpowiedzi bez
  obiektow. Odpowiedzi trafiaja do cache metadanych (nowa tabela
  `teryt_bbox_cache`; `cache stats`: `TERYT entries` liczy punkty i
  obszary).
- BDOT10k z wielu powiatow: `LandCoverManager.download_all_counties(bbox=
  | godlo=, layers=)` pobiera pakiet KAZDEGO powiatu przecinajacego obszar
  (TERYT z WFS PRG), opcjonalnie tylko wybrane warstwy (np. `PTWP`,
  `SWRS`); `Bdot10kProvider.download_package` zwraca `Bdot10kPackage`
  (`path`, `teryt`, `url`, `format`; eksport z `kartograf`).
  `LandCoverManager(cache=)` przekazuje cache metadanych providerom
  tworzonym po nazwie (BDOT10k, SoilGrids).
- Sidecar BDOT10k: `extra.source` (`url`, `teryt`, `format`) i `extra.http`
  (`etag`, `last_modified`, `content_length` z odpowiedzi; serwer paczek
  GUGiK podaje dzis tylko `Content-Length`). `keep_raw=True` zachowuje
  oryginalny ZIP GUGiK obok GPKG (pelny pakiet: `bdot10k_teryt_<TERYT>_GPKG.zip`
  bez tokenu warstw, ten sam plik niezaleznie od filtra `layers=`, z wlasnym
  sidecarem; tylko GPKG). `Bdot10kPackage` ma pola `http` i `raw_path`.
- Wycinek CZ w bibliotece: `download_cz_cutout(bbox, output_dir=,
  target_crs=, vertical_crs=, resolution=)` (np. EPSG:2180 + EVRF2007;
  siatka od zadanego obszaru, jak w CLI) i `run_cz_cutout` z wlasnym
  providerem; wynik `CzCutoutResult` z flaga `all_nodata` (takze
  w sidecarze i w logu), sidecar pisze biblioteka. Podzial obszaru na
  kraje: `countries_for_bbox`, `split_bbox_by_country`. CLI (`--bbox`/
  `--geometry` dla CZ) korzysta z tej samej implementacji — komunikaty
  i kody wyjscia bez zmian, sidecar wycinka CZ dostaje
  `extra.all_nodata` (`true`/`false`).
- `build_cutout_from_sheets(sheet_paths, bbox, target_crs, output_path, *,
  resolution, vertical_crs)`: wycinek NMT PL z lokalnych arkuszy bez
  zapytan sieciowych, wynik i sidecar pod sciezka podana przez
  wywolujacego (reguly siatki jak w `download_pl_cutout`). Brakujacy albo
  nieczytelny arkusz i `output_path` rowny arkuszowi wejsciowemu =
  `ValidationError` przed zapisem.
- `hsg_from_rasters(clay, sand, silt, *, bbox, crs, pixel_m, output_path)`:
  HSG z gotowych rastrow SoilGrids (g/kg) na jawnie podanej siatce, bez
  wartosci domyslnych (nodata wejsc tylko z tagu, jak w
  `calculate_hsg_by_bbox`); sidecar z `sha256` warstw wejsciowych
  (`extra.source_files`: `name`, `file`, `sha256`; `extra.source_layers`
  jak w `calculate_hsg_by_bbox` — lista nazw `clay`, `sand`, `silt`).
- Weryfikacja ukladu wysokosci rekordu skorowidza GUGiK (NMT/NMPT): pole
  `ukladWspolrzednychPionowych` musi odpowiadac zadanemu ukladowi
  (`PL-KRON86-NH` dla KRON86, `PL-EVRF2007-NH` dla EVRF2007); inna wartosc
  = `DownloadError` kampanii przed pobraniem pliku (`newest` i `all`, takze
  `GugikProvider.download`). Rekord bez tego pola jest przyjmowany.
  Nowe: `kartograf.download.campaigns.verify_record_vertical_crs`,
  `RECORD_VERTICAL_CRS`, `kartograf.providers.pl.require_nmt_vertical_crs`
  (`nmt_vertical_crs` bez zmian).

### Zmienione

- `DownloadManager.download_sheet()` ustawia `last_result` takze dla
  pojedynczego arkusza (jednoelementowy `DownloadResult`); dotad `None`.
  Co zrobic: kod, ktory po `download_sheet()` traktowal `last_result`
  jako `None`, moze czytac z niego wynik arkusza.
- Udokumentowano: przy kampaniach (`campaigns=`) zrodlem pochodzenia
  arkusza jest sidecar, nie `source_info()` (A12).
- Godla PL-1992 spoza zakresu nomenklatury (pas inny niz M/N, slup spoza
  33-35, arkusz 1:200 000 spoza 1-144, np. `N-34-999-D`) koncza sie
  `ParseError` przed jakimkolwiek zapytaniem sieciowym; dotad trafialy do
  uslug z bboxem `inf` albo poza Polska. Co zrobic: nic, jesli godla sa
  poprawne; kod, ktory dla takich godel oczekiwal `DownloadError` albo
  pustego wyniku, powinien lapac `ParseError` (albo `ValidationError`).
- `ParseError` dziedziczy po `ValidationError` — `except ValidationError`
  lapie tez bledy godel. Co zrobic: gdy kod obsluguje oba wyjatki osobno,
  `except ParseError` musi stac przed `except ValidationError`.
- Liczby w godle PL-1992 sa zapisywane bez zer wiodacych, jak w skorowidzu
  GUGiK (`M-33-036-A` -> `M-33-36-A`) — w sciezce, sidecarze i wyniku,
  takze w nazwach plikow land cover (`..._godlo_M-33-36-A`) i w domyslnej
  nazwie wyniku `kartograf soilgrids hsg --godlo`
  (`hsg_M-33-36-A_<glebokosc>.tif`). Pliki zapisane wczesniej pod godlem
  z zerami wiodacymi nie sa rozpoznawane; pobierz je ponownie.
- `find_sheets_for_bbox` zwraca tylko godla z zakresu nomenklatury PL-1992:
  obszar wychodzacy poza pasy M/N i slupy 33-35 (np. bbox przez 12E)
  daje godla tylko jego polskiej czesci, obszar calkowicie poza zakresem —
  pusta liste (dotad takze godla spoza zakresu, ktore nie maja danych).
  Co zrobic: nic — usuniete godla i tak nie mialy danych; kod, ktory
  traktowal pusta liste jako blad, dostaje ja teraz dla obszaru calkowicie
  poza Polska.
- `kartograf landcover download --source bdot10k` z `--bbox`, `--godlo`
  albo `--geometry` pobiera wszystkie powiaty z obszaru (dotad jeden, ze
  srodka obszaru — reszta obszaru po cichu bez danych) i drukuje linie
  `Downloaded to:` dla kazdego pliku.
- Plik BDOT10k nazywa sie zawsze `bdot10k_teryt_<TERYT>.gpkg` (`.zip` dla
  SHP), takze przy `--bbox`/`--godlo`/`--geometry` — zawiera caly pakiet
  powiatu. Dotychczasowe `bdot10k_bbox_*`/`bdot10k_godlo_*` nie sa
  rozpoznawane; pobierz obszar ponownie. Plik z filtrem warstw nosi ich
  kody w nazwie (`bdot10k_PTWP-SWRS_teryt_<TERYT>.gpkg`).
- `LandCoverManager.download_by_bbox`/`download_by_godlo` dla BDOT10k: obszar
  z kilku powiatow konczy sie `ValidationError` z lista kodow (uzyj
  `download_all_counties`), obszar bez powiatu — `NoCoverageError`; sidecar
  pliku jednego powiatu ma `extra.parent_request` (obszar zadania).
- `Bdot10kProvider.download_by_bbox` (i `LandCoverManager` dla BDOT10k)
  przyjmuje obszar w dowolnym obslugiwanym ukladzie — dotad uklad inny niz
  EPSG:2180 konczyl sie `ValueError`; obszar jest przeliczany do EPSG:2180
  przy zapytaniu PRG. Prywatne `Bdot10kProvider._get_teryt_for_point`
  (WMS GetFeatureInfo) i `WMS_ENDPOINT` usuniete bez zamiennika — uzyj
  `teryt_for_point`/`discover_teryts_for_bbox`.
- Biblioteka: `create_nmt_provider`, `DownloadManager` (bez providera albo
  z providerem bez wlasnego `vertical_crs`) i `download_pl_cutout` przy
  `resolution="5m"` i `vertical_crs="KRON86"` koncza sie `ValidationError`
  (NMT 5 m istnieje tylko w EVRF2007); dotad po cichu zamienialy uklad na
  EVRF2007 z ostrzezeniem w logu. Co zrobic: podaj `vertical_crs="EVRF2007"`
  (albo `resolution="1m"`, gdy potrzebny jest KRON86). CLI — patrz wpis
  nizej (tez blad).
- CLI: `kartograf download ... --resolution 5m --vertical-crs KRON86`
  (NMT PL: godlo, hierarchia, `--bbox`/`--geometry`, wycinek `--target-crs`,
  takze `--country auto`) konczy sie `Error: NMT 5m (PL) jest dostepny tylko
  w EVRF2007 ...` i kodem 1, zanim cokolwiek pojdzie w siec; dotad CLI
  zamienialo uklad na EVRF2007 z komunikatem `Info:` i pobieralo (kod 0).
  `--resolution 5m` bez `--vertical-crs` dziala jak dotad (EVRF2007). Co
  zrobic: pomin `--vertical-crs` albo podaj `--vertical-crs EVRF2007`;
  dla KRON86 uzyj `--resolution 1m`.
- Pobieranie arkuszy NMT/NMPT/orto GUGiK (CLI i `DownloadManager`, takze
  wycinek `--target-crs`) odrzuca rekordy i pliki, ktore w 0.7.0 przechodzily:
  URL rekordu bez godla, plik ASC poza rama godla (B4) oraz rekord NMT/NMPT
  deklarujacy inny uklad wysokosci niz zadany — `DownloadError` arkusza
  (kampanii), plik nie zostaje zapisany. Kontrole rekordu dzialaja przed
  pominieciem juz pobranej kampanii, a `--force` (`skip_existing=False`) ich
  nie wylacza. Co zrobic: sprawdz rekord w skorowidzu GUGiK (geoportal) —
  komunikat podaje godlo i rozbieznosc; to blad danych u zrodla, ktory
  warto zglosic GUGiK; dla innych arkuszy pobieranie trwa dalej (lista:
  porazka arkusza wg R5, `--campaigns all`: pozostale kampanie).
- Komunikat `Error: --campaigns all nie dziala z --target-crs` nie odsyla
  juz do "narzedzia 0.7.1" (skladanie kampanii nie ma przypisanego wydania,
  ADR-030 errata 6); kod wyjscia bez zmian.
- `kartograf download --year RRRR` i `--min-density N` z `--product`
  nmt/nmpt/orto koncza sie `Error:` i kodem 1 przed siecia (dotad opcje byly
  po cichu pomijane: kod 0 i najnowsze dane). Dotyczy wszystkich torow
  (godlo, hierarchia, lista arkuszy, `--bbox`, `--geometry`, `--target-crs`,
  `--country auto`, CZ); `--product laz` bez zmian. Wybor roku dla
  NMT/NMPT/orto bedzie w 0.7.2. Co zrobic: pomin opcje albo — dla roku —
  uzyj `--min-year RRRR` (najnowsza kampania nie starsza niz podany rok;
  tylko PL, bez `--target-crs`; dla zadan wylacznie CZ — CUZK nie ma wyboru
  roku, komunikat kaze pominac `--year`); skrypty przekazujace `--year`/
  `--min-density` do innych produktow niz LAZ musza je usunac.

### Naprawione

- Scalanie paczki BDOT10k nie pomija juz po cichu tabeli o powtorzonej
  nazwie — to `DownloadError`.
- BDOT10k: warstwy paczki sa rozpakowywane strumieniowo (bez wczytywania
  calej warstwy do pamieci), a `keep_raw` zapisuje ZIP bez drugiej kopii
  w pamieci. Blad wejscia-wyjscia przy rozpakowaniu, scalaniu albo zapisie
  ZIP (brak miejsca, brak pamieci) to `DownloadError` (CLI: `Error:` z opisem,
  kod 1), nie goly `OSError`. Nieudany zapis oryginalnego ZIP usuwa juz
  zapisany GPKG — nie zostaje plik danych bez sidecara.
- `cache stats`: `TERYT entries` liczy odpowiedzi PRG z `landcover download`
  (U5).

## [0.7.0] - 2026-10-08

Wydanie wielokrajowe. Najwazniejsze nowosci wzgledem 0.6.1:

- **Czechy (CUZK, etap 1):** NMT DMR 5G (2 m, kafle TM33) i DMR 4G (5 m,
  arkusze SM5) przez godlo albo `--bbox`/`--geometry`; `--country
  {pl,cz,auto}` (domyslnie `auto`) dzieli obszar przygraniczny na osobne
  pliki per kraj ze wspolnym `extra.parent_request`.
- **Nowy produkt LAZ:** chmury punktow LIDAR (ALS) z GUGiK przez WFS
  (`--product laz`), domyslnie najnowszy kafel per obszar (ADR-029).
- **Wycinek PL `--target-crs`:** jeden scalony GeoTIFF NMT dla bboxa albo
  geometrii w EPSG:2180/5514/3045, reprojekcja lokalna przypieta operacja
  (ADR-027); w bibliotece `download_pl_cutout`.
- **Kampanie GUGiK:** `--campaigns {newest,all}` i `--min-year`; pliki
  w `<segment>/kampanie/`, sciezka standardowa to dowiazanie twarde do
  najnowszej kampanii (ADR-030).
- **Nowy uklad `data/` i sidecar `.meta.json`:** segmenty
  `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]` (ADR-026), obok kazdego
  pobranego pliku metadane CRS/licencja/nodata/zadanie (klucze ADR-031).
- **Niezawodnosc:** jeden transport HTTP (ponowienia tylko siec/429/5xx),
  warstwy skorowidza GUGiK wylacznie z GetCapabilities, jawne
  `NoCoverageError` zamiast cichych zamiennikow, cache metadanych odporny
  na uszkodzenie.

### Zmiany lamiace (BREAKING)

#### Uklad `data/` i pliki wynikowe
- **Nowy uklad `data/`** (ADR-026): segmenty
  `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]` koduja jawnie kraj, uklad
  poziomy (PL: 1992/2000 — domkniecie odroczonego ADR-017) i pionowy
  (kron86/evrf2007/bpv; orto bez pionowego), np. `nmt/pl_1992_1m_evrf2007/`,
  `orto/pl_1992/`. `<uklad>` wynika z formatu godla KAZDEGO pliku z osobna
  (kropki -> `2000`, myslniki -> `1992`; kafle LAZ — `uklad_xy` kafla).
  Kartograf nie migruje `data/` automatycznie (tabela w "Przejscie
  z 0.6.1"). Katalog `landcover/` bez zmian (nazwy plikow CORINE/SoilGrids
  — nizej). Kanoniczny opis: `docs/ARCHITECTURE.md`
  sekcja 3.
- **Kampanie (ADR-030):** prawdziwe pliki NMT/NMPT/orto PL leza wylacznie
  w `<segment>/kampanie/<data>_<id>/<hierarchia godla>/<godlo>.<ext>`;
  sciezka standardowa `<segment>/<hierarchia>/<godlo>.<ext>` jest
  dowiazaniem twardym (albo kopia) do najnowszej lokalnej kampanii
  (szczegoly w Dodane, "Kampanie GUGiK"). Zwykly plik w sciezce
  standardowej (np. przeniesiony z 0.6.1) jest dla Kartografa nieznany:
  pierwsze uruchomienie pobiera go ponownie do `kampanie/` i zastepuje
  dowiazaniem. Kopiowanie `data/` tylko z zachowaniem hardlinkow
  (`rsync -aH`/`cp -a`), inaczej powstaje duplikat.
- **Domyslne `newest` pyta skorowidz przy kazdym uruchomieniu**, gdy cache
  rekordu (7 dni) wygasl, i pobiera nowsza kampanie, jesli sie pojawila;
  ponowne uruchomienie "bez sieci" dziala tylko w oknie cache.
- `FileStorage.list_files()` domyslnie zwraca sciezki standardowe — bez
  `kampanie/` i bez wiszacych dowiazan (`list_files(campaigns=True)` = tylko
  `kampanie/`).
- **BDOT10k `--format SHP` / `format="SHP"`** zapisuje archiwum ZIP
  z shapefile'ami pod rozszerzeniem `.zip` (np. `bdot10k_teryt_1465.zip`,
  sidecar obok) i zwraca te sciezke (takze przez bbox/godlo); w 0.6.1 ZIP
  trafial pod podana sciezke, zwykle `.gpkg`, ktora udawala GeoPackage.
  CLI drukuje faktyczna sciezke (review N1).
- **`LandCoverManager.download_by_teryt/download_by_bbox/download_by_godlo`
  bez `output_path` nazywaja pliki tak jak `download()`** — bylo
  `CORINE Land Cover_N-34-130-D.gpkg` (spacje, etykieta zrodla), jest
  `corine_2018_godlo_N-34-130-D.<ext>` (wzorzec nizej); rozszerzenie nadaje
  provider (CORINE `.tif`/`.png`, SoilGrids `.tif`). Skrypty skladajace
  sciezke wyniku z nazwy zrodla wymagaja poprawki (A5-2, N14).
- **`soilgrids hsg` nazywa domyslny plik z glebokoscia:**
  `hsg_<godlo>_<depth>.tif` (np. `hsg_N-34-130-D_0-5cm.tif`) i
  `hsg_bbox_<depth>.tif`; bylo `hsg_<godlo>.tif` / `hsg_bbox.tif`, wiec
  kolejne `--depth` po cichu nadpisywaly wynik. Sidecar HSG z `--godlo`
  / `calculate_hsg_by_godlo` zapisuje tez `request.sheet` (obok
  pochodnego `bbox`/`bbox_crs`); `--bbox`/`--geometry` bez `sheet`.
  Skrypty skladajace sciezke wyniku HSG wymagaja poprawki. Statystyka
  (`stat`) nie jest parametrem CLI (zawsze `mean`); w bibliotece nazwe
  pliku wybiera wywolujacy (`output_path`).
- **Nazwy plikow land cover niosa parametry tresci** (U3, cicha utrata
  danych w 0.6.1): `soilgrids ... --property clay`, a potem `--property
  sand` dla tego samego obszaru zapisywaly ten sam plik
  `soilgrids_bbox_<coords>.tif` — drugi wynik po cichu nadpisywal pierwszy;
  tak samo CORINE z innym `--year`. Nowy wzorzec
  `<zrodlo>[_<parametr>...]_<tryb>_<id>.<ext>`, `<zrodlo>` = wartosc
  `--source` (`bdot10k`/`corine`/`soilgrids`), parametry z wartosciami
  domyslnymi wlacznie:
  `soilgrids_<property>_<depth>_<stat>_bbox_<coords>.tif` (np.
  `soilgrids_clay_0-5cm_mean_bbox_770000_509000_772000_511000.tif`),
  `corine_<year>_godlo_N-34-130-D.tif` (`.png` z podgladu WMS); bylo
  `soilgrids_bbox_<coords>.tif` i `corine_land_cover_bbox_<coords>.<ext>`.
  BDOT10k bez zmian (`bdot10k_teryt_1465.gpkg`/`.zip` — format rozroznia
  rozszerzenie). Te same parametry = ta sama sciezka (ponowne pobranie
  nadpisuje jak dotad). Sidecar zapisuje parametry w `request`
  (`property`/`depth`/`stat`, `year`, `format`), a `nodata` wyniku GeoTIFF
  odczytuje z pliku (`null`, gdy plik go nie deklaruje). Pliki z 0.6.1
  (stare nazwy) nie sa rozpoznawane — Kartograf ich nie zmienia ani nie
  czyta.
- **`DownloadManager` bierze segment z providera:** bez jawnego `storage=`
  podkatalog pochodzi z deskryptora providera (bylo: zawsze segment NMT 1m,
  wiec `DownloadManager(provider=GugikNmptProvider())` pisal do katalogu NMT
  i przy `--force` nadpisywal jego pliki; teraz `nmpt/pl_<uklad>_1m_<vcrs>/`,
  A2-2), a uklad pionowy segmentu z PROVIDERA, nie z flagi managera
  `vertical_crs=` (`DownloadManager(provider=GugikProvider(vertical_crs=
  "KRON86"))` pisal do `nmt/pl_1992_1m_evrf2007/` obok sidecara z
  `EPSG:9650`; dotyczy biblioteki, nie CLI).
- **Katalogi wyjsciowe powstaja dopiero przy zapisie:** `LandCoverManager()`
  nie tworzy `output_dir` (domyslnie `./data/landcover`) w konstruktorze,
  a `MetadataCache()` nie tworzy pliku `.kartograf_cache.db` przy
  konstrukcji (szczegoly w Zmienione). Kod zakladajacy istnienie
  `output_dir` zaraz po `LandCoverManager(...)` musi utworzyc go sam.

#### Sidecar `.meta.json`
- **Sidecar jest nowy w 0.7.0** (obok kazdego pobranego pliku, schemat
  `kartograf-meta/1`, opis w Dodane). Klucze sa angielskie (ADR-031) —
  konsumenci czytajacy sidecary z wersji rozwojowych 0.7.0-dev musza
  przejsc na nowe nazwy; schemat zostaje `kartograf-meta/1` (przed 0.7.0 niewydany),
  bez warstwy zgodnosci:

  | Bylo (0.7.0-dev) | Jest |
  |---|---|
  | `request.godlo` (wszystkie tory) | `request.sheet` |
  | `extra.source.godlo` | `extra.source.sheet` |
  | `extra.source.aktualnosc` / `aktualnosc_rok` | `extra.source.acquisition_date` / `acquisition_year` |
  | `extra.source.uklad` | `extra.source.declared_crs` |
  | `extra.source.zrodlo_danych` | `extra.source.data_source` |
  | `extra.source.numer_zgloszenia`, `extra.campaign.zgloszenie` | `survey_work_id` (w obu) |
  | `extra.source.skorowidz` | `extra.source.index_url` |
  | `extra.source.dt_pzgik`, `extra.campaign.dt_pzgik` | `pzgik_date` (w obu) |
  | `extra.source.kolor` (orto) | `extra.source.color` |
  | `extra.godlo_kafla` / `rok` / `gestosc` (LAZ) | `extra.tile_sheet` / `year` / `nominal_density` |
  | `extra.uwaga` (CORINE PNG) | `extra.note` |
  | `extra.podil` (CZ SM5) | `extra.cz_share` |
  | `extra.sheet_sources[]`: `godlo`, `aktualnosc` | `sheet`, `acquisition_date` |

  `teryt` zostaje (nazwa wlasna rejestru). Kanoniczna tabela:
  `docs/ARCHITECTURE.md` 3.2. Skutki dla starych lokalnych danych —
  "Przejscie z 0.6.1", dane z 0.7.0-dev.

#### API biblioteki
- **Glebokie sciezki importu providerow zmienione bez shimow**
  (`from kartograf.providers.bdot10k import Bdot10kProvider` konczy sie
  `ModuleNotFoundError`); publiczne `from kartograf import ...` BEZ zmian.
  Tabela w "Przejscie z 0.6.1".
- **Wrapper `LandCoverProvider.download_by_teryt` zweza pozycyjna arnosc**:
  pozycyjnie przyjmuje tylko `teryt`, `output_path`, `timeout`; kolejny
  argument pozycyjny (np. `format` w `Bdot10kProvider.download_by_admin_unit`
  jako 4. argument) konczy sie `TypeError` — przekazuj go jako keyword
  (`format=...`).
- **`SoilGridsProvider.download_by_teryt()` rzuca `NotImplementedError`** —
  dotad zwracal jako sukces dane dla stalego obszaru 60x60 km wokol srodka
  WOJEWODZTWA (2-cyfrowy prefiks TERYT), identyczne dla kazdej gminy.
  Uzyj `download_by_bbox()` albo `download_by_godlo()` (A4-3).
- **`GugikProvider.download_bbox(vertical_crs="EVRF2007")` konczy sie
  `ValidationError`** z remedium, przed wyjsciem w siec — GUGiK wycofal
  endpoint WCS `DigitalTerrainModelFormatTIFFEVRF2007` (404 takze dla
  GetCapabilities), wiec WCS NMT 1m dziala wylacznie w KRON86; kanal WCS
  deskryptora `pl.gugik.nmt_1m` deklaruje tylko `EPSG:9650` (WCS NMPT nie
  jest tym objety). Wysokosci EVRF2007 z bboxa: `--bbox` (arkusze OpenData)
  albo wycinek `--target-crs`/`download_pl_cutout` (A1-4).
- **`find_sheets_for_bbox()`/`find_sheets_for_geometry()`: stykajace sie
  krawedzie nie sa przecieciem** — liczy sie dodatnie pole przeciecia, wiec
  bbox rowny arkuszowi w jego ukladzie (EPSG:4326 dla PL-1992, strefa
  2176-2179 dla PL-2000) zwraca TYLKO jego arkusze (bbox w EPSG:2180
  przechodzi przez szersza obwiednie WGS84 i zwraca takze sasiadow — np.
  9 godel dla `N-34-130-D-d-2-4`). Tak samo na linii siatki i na granicy
  stref PL-2000 (A1-7, A9-1):

  | zapytanie | bylo | jest |
  |---|---|---|
  | bbox arkusza `N-34-130-D`, `--scale 1:50000` | 9 godel | 4 (`N-34-130-D-a..d`) |
  | bbox arkusza `N-34-130-D-d-2-4` (1:10000) | 4 godla | 1 |
  | bbox arkusza `6.179.12.20` (PL-2000, `--scale 1:2000`) | 9 godel | 1 |
  | punkt / bbox zdegenerowany (<= ~2e-9 jednostki) | `[]` (PL-1992) / 4 godla (PL-2000) | 1 arkusz (ten na E/N od linii siatki) |

- **`find_sheets_for_bbox`/`find_sheets_2000_for_bbox`: walidacja wejscia**
  — nieznana wartosc `system=` konczy sie `ValidationError` zamiast cichego
  fallbacku do PL-1992; bbox odwrocony (`min > max`) albo z NaN/inf —
  `ValidationError` (dotad arkusz-smiec, np. `BBox(10, 10, 5, 5)` ->
  `L-33-1-D-c-4-3`, albo `ValueError`). Bbox-punkt nadal dozwolony.
- **`get_parent()`/`get_children()`/`get_all_descendants()` i `parse
  --hierarchy` dla 1:1000000 <-> 1:500000: poprawna geometria cwiartek** —
  cwiartka liczona z pozycji arkusza 1:200000 w siatce 12x12 (bloki 6x6:
  A = NW, B = NE, C = SW, D = SE), a nie z pasow po 36 kolejnych numerow.
  72 ze 144 arkuszy 1:200000 dostaje innego rodzica niz w 0.6.x,
  a `get_all_descendants()` arkusza 1:500000 zwraca wlasciwa cwiartke
  zamiast poziomego pasa (A1-1).
- **Usuniete publiczne atrybuty i metody klas eksportowanych w `kartograf`**
  (dostep konczy sie `AttributeError`):

  | Usuniete | Zamiast |
  |---|---|
  | `MetadataCache.get_url()` / `set_url()` | `get_record()` / `set_record()` (rekord skorowidza albo potwierdzony brak pokrycia; tabela `url_cache` usuwana przy otwarciu) |
  | `WMS_LAYERS` (`GugikProvider`, `GugikNmptProvider`, `GugikOrtoProvider`) | brak listy zaszytej — warstwy z GetCapabilities (`LAYER_PATTERN` providera) |
  | `GugikProvider.FORMAT_EXTENSIONS` (takze w `GugikNmptProvider`) | `get_file_extension()` (dziedziczone z `BaseProvider`) |
  | `GugikOrtoProvider.OPENDATA_URL_PATTERN` | brak — URL arkusza z rekordu skorowidza |
  | `RETRY_BACKOFF_BASE` (`GugikProvider`, `GugikNmptProvider`, `GugikOrtoProvider`, `Bdot10kProvider`, `CorineProvider`, `SoilGridsProvider`) | `kartograf.transport.http.RETRY_BACKOFF_BASE` (jeden backoff dla wszystkich); `MAX_RETRIES` providerow wskazuje `transport.http.MAX_RETRIES` (3) |
  | `CorineProvider.DLR_YEARS` | brak (martwy kod) |
  | `SoilGridsProvider.TERYT_WMS_ENDPOINT` | brak — `download_by_teryt()` rzuca `NotImplementedError` |

- **Auth proxy: usuniety endpoint `/token` i
  `AuthProxyClient.get_access_token()`** — oddawaly surowy token do procesu
  klienta, co przeczy roli proxy (izolacja credentials, ADR-002). Token
  trafia wylacznie do hostow `*.copernicus.eu` i `*.eea.europa.eu`: `/proxy`
  i `/download` przyjmuja tylko `https` (inny schemat = 403), `/proxy`
  odrzuca (403) kazdy host spoza listy (dotad pobieralo z dowolnego URL-a
  klienta), a `/download` przekazuje zadanie do hosta `https` spoza listy
  BEZ naglowka `Authorization` (presigned `DownloadURL` CLMS bywa na CDN)
  (A4-10).
- **Fasada `kartograf.cli.commands` nie re-eksportuje juz implementacji
  komend** — import z fasady konczy sie `ImportError`; kanoniczne sa moduly
  `cli/*_cmd.py`: publiczne `cmd_landcover_download`,
  `cmd_landcover_list_layers`, `cmd_landcover_list_sources`,
  `cmd_soilgrids_hsg` oraz prywatne `_cmd_download_bbox`,
  `_cmd_download_geometry`, `_download_godlo_list`,
  `_create_provider_and_storage` (z `kartograf.cli.download_cmd`). W fasadzie
  zostaja `main`, `create_parser`, dispatchery `cmd_parse`, `cmd_download`,
  `cmd_landcover`, `cmd_soilgrids`, `cmd_cache`, `create_progress_callback`
  i helpery formatujace `format_*` (A5-1, K9).
- **`NoCoverageError` jest podklasa `DownloadError`** (`except DownloadError`
  lapie oba), a `GridMismatchError` — podklasa `ValidationError`.
- **`import kartograf` laduje eagerly `rasterio`** (GDAL/PROJ) — eksporty CZ
  w `__init__.py` importuja `providers/cuzk/client.py`, ktory importuje
  `rasterio` na poziomie modulu; koszt ok. +60 ms przy imporcie. Zepsuty
  GDAL/PROJ (np. brakujaca biblioteka natywna) psuje sam `import kartograf`,
  nie dopiero pierwsze wywolanie rastrowe — istotne dla Hydrografu/Hydrologu
  (ADR-023, "Ustalenia dodatkowe" pkt 2).

#### CLI i zachowanie
- **Domyslnym krajem jest `--country auto`** — w 0.6.1 opcji `--country` nie
  bylo i kazde zadanie szlo do GUGiK. Dla `--bbox`/`--geometry` bez jawnego
  `--country`: obszar przecinajacy obwiednie dwoch krajow jest pobierany
  z KAZDEGO z nich (osobne pliki i sidecary, wspolny
  `extra.parent_request`); obwiednia CZ jest PROSTOKATNA (siega 18,86 E
  i 51,06 N), wiec zadanie z poludniowej Polski dostaje dodatkowo plik
  i sidecar z CUZK (poza faktyczna granica raster same-nodata z `Warning:`,
  nie blad) — obejscie: jawne `--country pl`. Opcje bez odpowiednika
  czeskiego rozstrzygaja kraj do `pl` (szczegoly w Dodane, "Wybor kraju")
  (A6-3, N6-2; ADR-023 pkt 4-5).
- **Pobranie hierarchii albo listy arkuszy z porazkami konczy sie kodem 1**
  i `Error: N z M arkuszy nie pobrano (blad pobrania, nie brak danych):
  <godla> — ponow pobranie` z pelna lista — bylo: kod 0 mimo
  brakujacych arkuszy; dotyczy godla oraz `--bbox`/`--geometry` (A2-3).
  Sam brak pokrycia czesci arkuszy daje `Warning:` i kod 0 (Dodane, "NMT PL").
- **Brak danych zrodla to `NoCoverageError`, nie cichy zamiennik:** przy
  wyborze arkusza GUGiK zamiast pliku PL-1992 pod godlem PL-2000, pliku
  0,5 m pod zadaniem 1 m albo arkusza potomnego; dla PL-2000 1:10000
  z samymi potomkami podpowiedz `--scale 1:2000`. Awaria warstwy skorowidza
  albo GetCapabilities to `DownloadError` zamiast przejscia do starszej
  kampanii lub zaszytej listy warstw (K3, K4, S4).
- **CLI odrzuca `--product nmpt --resolution 5m` oraz `--product orto
  --vertical-crs ...`** zamiast cicho je ignorowac (V2-N1).
- **Usuniety format `GML`** — `--format GML`, pozycja w `landcover
  list-sources` i `get_supported_formats()`; nigdy nie byl zaimplementowany
  (zadanie konczylo sie plikiem GPKG) (A6-2).
- **Selekcja arkuszy z bboxa EPSG:2180 przecinajacego poludnik 19°E zwraca
  wiecej arkuszy** — obwiednia WGS84 liczona z zageszczonych krawedzi (opis
  w Poprawione); mozliwe arkusze nadmiarowe spoza bboxa.
- **HSG: kanoniczne progi trojkata USDA** (ADR-025) — skosne granice normy
  (`silt + 1.5*clay`, `silt + 2*clay`) zastapily przyblizenia liniami
  pionowymi/poziomymi, reguly stoja w jednym miejscu, wiec
  `classify_usda_texture()` (skalar) i `classify_usda_texture_array()`
  (tablica, uzywana przez `calculate_hsg_by_bbox`) daja identyczne wyniki
  (rownowaznosc przypieta testem na calym symplexie co 1%). Skutek na 5151
  punktach symplexu, "bylo -> jest":

  | zmiana HSG | punktow | udzial symplexu | zmiana tekstury |
  |---|---|---|---|
  | A -> B | 136 | 2,64% | `loamy_sand` -> `sandy_loam` |
  | C -> B | 85 | 1,65% | `sandy_clay_loam` -> `loam` (36), `sandy_clay_loam` -> `sandy_loam` (28), `clay_loam` -> `loam` (21) |
  | D -> C | 5 | 0,10% | `sandy_clay` -> `clay_loam` |
  | **razem** | **226** | **4,39%** | (klasa tekstury zmienia sie dla 427 punktow = 8,29%) |

  Kazda zmiana jest o dokladnie jedna grupe. `TEXTURE_TO_HSG` bez zmian
  (swiadome, udokumentowane odstepstwo od TR-55: `sandy_loam`=B,
  `clay_loam`/`silty_clay_loam`=C) (A4-4, A4-8).
- **HSG: piksele nodata dostaja 0 ("brak danych")**, nie grupe B (szczegoly
  w Poprawione).

### Przejscie z 0.6.1
- **Istniejacy cache `data/` nie jest reuzywany** — arkusze NMT/NMPT/orto
  z 0.6.1 (`nmt_1m/`, `nmt_5m/`, `nmpt/`, `orto/`) zostana pobrane ponownie,
  takze po recznym przeniesieniu do nowych segmentow (zwykly plik w sciezce
  standardowej bez sidecara z `extra.link` jest nieznany, ADR-030). Reczna
  migracja nie oszczedza transferu: zaplanuj miejsce i czas pierwszego
  pobrania, stare katalogi usun po nim. Katalog `landcover/` bez zmian
  (nazwy plikow — punkt nizej). Tabela
  odpowiedniosci katalogow (np. dla wlasnych skryptow czytajacych `data/`):

  | Stara sciezka | Nowa sciezka |
  |---|---|
  | `nmt_1m/` (godla 1992) | `nmt/pl_1992_1m_<vcrs>/` |
  | `nmt_1m/` (godla kropkowe 2000) | `nmt/pl_2000_1m_<vcrs>/` |
  | `nmt_5m/` | `nmt/pl_<uklad>_5m_evrf2007/` |
  | `nmpt/` | `nmpt/pl_<uklad>_1m_<vcrs>/` |
  | `orto/` | `orto/pl_<uklad>/` (CIR: `orto/pl_<uklad>_cir/`, B/W: `orto/pl_<uklad>_bw/`) |
  | `laz/` (tylko 0.7.0-dev) | `laz/pl_<uklad>_<vcrs>/` |
  | `cz_dmr5g/` (tylko 0.7.0-dev) | `nmt/cz_dmr5g_<vcrs>/` |
  | `cz_dmr4g/` (tylko 0.7.0-dev) | `nmt/cz_dmr4g_<vcrs>/` |

  Stare `nmt_5m/`, `nmpt/` i `orto/` trzymaly oba systemy godel razem, wiec
  jeden stary katalog odpowiada dwom segmentom.
- **Pliki CORINE/SoilGrids w `landcover/`** maja nowe nazwy z parametrami
  (`soilgrids_bbox_<coords>.tif` -> `soilgrids_<property>_<depth>_<stat>_bbox_<coords>.tif`,
  `corine_land_cover_bbox_<coords>.tif` -> `corine_<year>_bbox_<coords>.tif`;
  analogicznie `godlo_<godlo>`). Stary plik SoilGrids nie mowi, ktorego
  parametru dotyczy (sidecar go nie zapisal), wiec bezpieczniej pobrac
  ponownie niz zmieniac nazwe; plik CORINE mozna przemianowac recznie,
  jesli rocznik jest znany (w 0.6.1 domyslnie 2018). Skrypty skladajace
  nazwe wyniku powinny brac sciezke zwracana przez `LandCoverManager.download()`
  (CLI: `Downloaded to:`). BDOT10k bez zmian.
- **Importy** — przeniesione moduly providerow (bez shimow); prywatne
  `Bdot10kProvider._get_teryt_for_point()` nadal istnieje:

  | Stary import | Nowy import |
  |---|---|
  | `kartograf.providers.gugik` | `kartograf.providers.pl.gugik` |
  | `kartograf.providers.gugik_nmpt` | `kartograf.providers.pl.gugik_nmpt` |
  | `kartograf.providers.gugik_orto` | `kartograf.providers.pl.gugik_orto` |
  | `kartograf.providers.bdot10k` | `kartograf.providers.pl.bdot10k` |
  | `kartograf.providers.landcover_base` | `kartograf.providers.base` |

  Najprosciej: `from kartograf import Bdot10kProvider` (i pozostale klasy).
- **Jeden raster NMT dla obszaru** — zamiast skladac mozaike samemu (albo
  z `kartograf.transport.mosaic.mosaic_and_crop`, ktore NIE jest
  eksportowane w `kartograf` i jest krokiem wewnetrznym) uzyj
  `kartograf.download_pl_cutout` (EVRF2007/KRON86, 1 m/5 m, cel
  EPSG:2180/5514/3045; arkusz bez danych = nodata + `missing_sheets`);
  z wlasnym providerem, sesja albo `MetadataCache` — kroki
  `prepare_pl_cutout` -> `select_pl_cutout_sheets` ->
  `run_pl_cutout(provider=...)`.
- **Pozostale zmiany widoczne dla konsumenta:** sidecar `<plik>.meta.json`
  obok kazdego pobranego pliku (konsument, np. Hydrograf, czyta klucze
  angielskie ADR-031); `except DownloadError` lapie tez `NoCoverageError`;
  `import kartograf` wymaga dzialajacego `rasterio`; argumenty
  `download_by_teryt` po `timeout` tylko jako keyword; w CLI dla zadan
  z poludniowej Polski podawaj `--country pl`, jesli plik CUZK jest
  niepotrzebny.
- **Dane z wersji rozwojowych 0.7.0-dev** (nie dotyczy uzytkownikow 0.6.1):
  - `laz/`, `cz_dmr5g/`, `cz_dmr4g/` mozna przeniesc wedlug tabeli wyzej —
    sa pomijane po samym istnieniu pliku (bez kampanii); `<vcrs>` odczytaj
    z sidecara (`vertical_crs`). Wczesniejszy plaski uklad wycinkow CZ
    (`cz_dmr5g_<coords>.tif` w korzeniu wyjscia) zastapil
    `<segment>/bbox/<coords>.tif`.
  - Rastry CZ i wycinki PL -> EPSG:5514 z sidecarem `S-JTSK to ETRS89 (3)`
    liczono slowacka operacja EPSG:4829 — moga byc przesuniete o 1-5 m
    (np. 1,25 m na poludnie dla kafli TM33, 4,92 m w zachodnich Czechach).
    CLI drukuje `Info:` przy ich pominieciu, ale nie przebudowuje
    automatycznie: uruchom ponownie z `--force`.
  - Wycinki PL zbudowane przed przyciaganiem cropu do siatki arkuszy maja
    tresc przesunieta o ulamek piksela i te same nazwy plikow — przebuduj
    z `--force` (pobiera ponownie takze arkusze) albo taniej: usun sam plik
    wycinka i uruchom bez `--force` (arkusze z cache zostana uzyte).
  - Sidecary z polskimi kluczami nie sa migrowane: sidecar kampanii bez
    `extra.campaign.pzgik_date` daje klucz dowiazania z nazwy katalogu
    (dolne oszacowanie), wpisy `sheet_sources` bez `sheet` nie licza sie
    jako niepelne arkusze przy pominieciu wycinka, a wpis
    `record_cache`/`campaigns_cache` z polskimi kluczami jest chybieniem
    cache (skorowidz odpytywany ponownie, wpis nadpisany). Odswiezenie
    sidecarow: `--force`.
  - Wpisy cache rekordow sprzed podpowiedzi `NoCoverageError.hints` nie maja
    podpowiedzi do wygasniecia TTL (7 d).
  - Symlink w sciezce standardowej (sprzed errata 4 ADR-030) to sciezka
    nieznana; plik kampanii jest lokalny, wiec `newest` go nie pobiera,
    tylko zastepuje symlink hardlinkiem.

### Dodane

#### Czechy (CUZK, etap 1)
- **`providers/cuzk/`:** `CuzkClient` — pierwszy silnik sterowany
  deskryptorem (URL-e wylacznie z `AccessChannel.endpoint`): `query()`
  z paginacja i filtrem nadmiarowego wyboru po stronie klienta,
  `export_image()` z kafelkowaniem i nadpisaniem CRS, `fetch_file()` (ZIP
  openzu -> TIFF+TFW); `SheetIndex`/`SheetInfo` — indeks arkuszy SM5/TM33
  z KladyMapovychListu (arkusz SM5 po godle: `SheetIndex.sm5_sheet`);
  `CuzkDmrProvider` + fabryka `create_dmr_provider` (jedno miejsce czeskich
  domyslow) — DMR 5G (2 m, godlo TM33) i DMR 4G (5 m, godlo SM5), bbox przez
  `exportImage`; naprawa metadanych CRS w plikach DMR4G-TIFF i w wynikach
  `exportImage`. Tylko `nmt`; `nmpt`/`orto`/`laz` dla CZ to etap 2.
- **`exportImage` natywnie w EPSG:5514:** serwer CUZK dostaje zadania
  wylacznie w ukladzie natywnym (deskryptory `server_reprojection=False`,
  A1-6). Sufit uslugi 15000 x 4100 px, realna bariera ~8 Mpx — klient
  kafelkuje z budzetem 4 Mpx na zapytanie, kafle kotwiczone w narozniku NW
  zadania (ostatni wiersz mozaiki bez `-9999`, szwy bit w bit, bez
  przesuniec tresci miedzy kaflami). Piksel ma dokladnie 2 m/5 m (snap od
  naroza NW, takze dla pojedynczego wycinka); bbox wyniku moze roznic sie
  od zadania o <= pol piksela na krawedziach E/S. Uszkodzony kafel konczy
  sie `DownloadError` z posprzatanym plikiem wynikowym (A3-1, A3-3, K6, N3).
- **Reprojekcja lokalna przypieta operacja (ADR-024):** `--target-crs`
  i kafel TM33 (warp na siatke EPSG:3045; arkusz SM5 jest 1:1) liczy
  `rasterio.warp` z wymuszonym pipeline'em operacji (`COORDINATE_OPERATION`),
  wspolnym z torem PL (`transform/raster.warp_to_grid`). Krok S-JTSK ->
  ETRS89 to czeska EPSG:1622/1623 (1,0 m), nie slowacka EPSG:4829.
  Kafelkowanie i mozaika po stronie natywnej (przed warpem — szwy nie sa
  utrwalane interpolacja), nodata nie wchodzi do interpolacji, zapis
  atomowy; nieudana reprojekcja (takze z `--force`) nie kasuje poprzedniego
  wycinka/kafla. Brak bezpiecznej operacji poziomej przerywa w konstruktorze
  providera, przed transferem; polityki poziome przekazuja `probe_point`,
  wiec lokalna siatka obcego kraju (np. `sk_gku`) zwracajaca `inf` jest
  odrzucana (K2, A1-2).
- **Transformacja pionowa Bpv -> EVRF2007** (opcjonalna, `--vertical-crs
  EVRF2007`): EPSG:8357 -> EPSG:5621, przypieta operacja 0,1 m, offset
  +0,11..+0,15 m rosnacy S->N, liczona per piksel; raster bez
  geotransformacji jest odrzucany (A3-5). `KRON86` dla CZ jest
  nieosiagalny (siatki GUGiK niepubliczne).
- **`core/parser_tm33.py` — `ParserTM33`:** obliczalna siatka kafli TM33
  2x2 km (EPSG:3045, godlo `{E_km}_{N_km}` = naroznik SW; nieparzyste
  kilometry, np. `301_5550`, sa niepoprawne), wzorowana na `Parser2000`;
  w `parser_registry` jako `cz_tm33`/`cz_sm5` (przed fallbackiem pl1992;
  wzorce `CZ_TM33_PATTERN`/`CZ_SM5_PATTERN`).
- **Rejestr:** deskryptory `cz.cuzk.dmr5g`/`cz.cuzk.dmr4g`, `CountryProfile`
  dla CZ (obwiednia prostokatna w EPSG:4326, ADR-023), `all_countries()`;
  `AccessChannel.endpoint` — jedyne zrodlo URL-i silnikow sterowanych
  deskryptorem (kanaly PL maja `endpoint=""`, zrodlem prawdy sa stale
  providerow).
- **Godlo SM5 bez `--resolution` pobiera 5 m** (takze pod `--country
  auto`); jawne `--resolution 2m` z godlem SM5 to `Error:` (kod 1) przed
  utworzeniem providera, bez sieci. Kafel TM33 i `--bbox`/`--geometry` CZ:
  domyslnie 2 m (albo 5 m). Biblioteka: `CuzkDmrProvider`/
  `create_dmr_provider` sa zwiazane z rozdzielczoscia i dla SM5 wymagaja
  `resolution="5m"`.
- **CZ `--bbox`/`--geometry` daje zawsze jeden wycinek**
  `<segment>/bbox/<coords>.tif` (np.
  `nmt/cz_dmr5g_bpv/bbox/-447000_-1114000_-446000_-1113000.tif`); nieudany
  wycinek nie zostawia pustego katalogu `bbox/`.
- **`Downloading ...` w torze CZ dopiero przy starcie transferu** (godlo,
  `--bbox`/`--geometry`, takze pod `auto`): nieznany arkusz SM5, awaria
  zapytania indeksu albo niepoprawny kafel TM33 daja samo `Error:`.
  Biblioteka: `CuzkDmrProvider.download`/`download_bbox` przyjmuja
  keyword-only `on_download: Callable[[], None] | None`, wolany raz, po
  walidacjach, tuz przed pobraniem pliku SM5 / pierwszym `exportImage`.
- **Indeks SM5 w cache:** tabela `sheet_cache` (TTL 30 dni),
  `kartograf cache stats` drukuje `Sheet entries`; `--force` odpytuje indeks
  na nowo i zapisuje go (`MetadataCache(refresh=True)`, D16).
- **Sidecar CZ:** `transform.horizontal = "pinned: <opis operacji>
  (<dokladnosc> m)"` symetrycznie do `transform.vertical` — takze dla kafli
  TM33 pobranych godlem (reprojekcja 5514 -> 3045 jest opisana); sciezka SM5
  (pliki openzu w 5514) bez czesci poziomej; `extra.cz_share`.

#### Wybor kraju (`--country`) i pogranicze
- **`--country {pl,cz,auto}`** (domyslnie `auto`): godlo — kraj z formatu
  godla; obszar — kazdy kraj z przecinajaca sie prostokatna obwiednia
  (pod `auto` przyciety do niej), osobne pliki ze wspolnym
  `extra.parent_request` (oryginalny bbox zadania, jego uklad i
  **probowane** — niekoniecznie pobrane — kraje), bez scalania PL+CZ (R6).
  Tryb godlowy nie dostaje `parent_request`.
- **Opcje tylko-PL rozstrzygaja `auto` do `pl`:** `--product nmpt|orto`,
  `--system`, `--vertical-crs KRON86`, `--resolution 1m` na obszarze
  spornym daja `Info: --country auto -> pl (...)` na stderr (takze z `-q`)
  zamiast kodu 1 (ADR-023 pkt 5, N6-2). Opcje nierozwiazywalne dla kraju
  (`--resolution 2m`/`--vertical-crs Bpv` na obszarze siegajacym PL;
  `--product` inny niz `nmt`, `1m`, `KRON86`, `--system` dla CZ) sa
  odrzucane przed pobraniem z podpowiedzia jawnego `--country`;
  `--product laz` na obszarze siegajacym CZ — `Error:` z podpowiedzia
  `--country pl`. `--target-crs` dziala dla obu krajow i nie rozstrzyga
  wyboru.
- **Przyciecie do obwiedni** drukuje `Info:` tylko, gdy naprawde ogranicza
  pobieranie (`--geometry` bez `--target-crs` wyznacza arkusze PL z calej
  geometrii — bez Info dla PL; czesc CZ bywa przycinana); nietkniete
  krawedzie PL pozostaja oryginalne (bez poszerzenia przez round-trip CRS).
  Wycinki niosa przyciety zasieg w nazwie pliku i `request.bbox`, tryb listy
  `--bbox` wyznacza arkusze z przycietego bboxa (sidecary z `request.sheet`);
  jawne `--country pl` nie przycina. Bbox calkowicie poza obwiedniami =
  `Error:` kod 1 bez sieci (S3).
- **Kody wyjscia:** 0, gdy co najmniej jeden kraj dostarczyl wynik; porazka
  drugiego daje `Warning: czesc <kraj> zadania zakonczyla sie bledem (patrz
  Error wyzej) — pobrano <kraj>; kod 0 (...)` (bez zgadywania przyczyny:
  brak pokrycia albo awaria zrodla); kod 1, gdy padly wszystkie kraje albo
  `--country` bylo jawne (A3-2, ADR-023 pkt 4). Wycinek PL/CZ w calosci
  nodata daje `Warning:` i kod 0 (N2). `Info:`/`Warning:` ida na stderr
  mimo `-q`.
- **`--bbox-crs`** przyjmuje takze `EPSG:5514` (S-JTSK) i `EPSG:3045`
  (ETRS89 / UTM 33N) obok `EPSG:2180`, `EPSG:4326`, `EPSG:2176-2179`
  (ujemne bboxy Krovaka podawaj jako `--bbox=...`). Bbox albo plik geometrii
  w ukladzie czeskim opuszcza Krovaka przypieta operacja, nie domyslnym
  transformerem (dla PL inaczej siatka i nazwa wycinka bylyby przesuniete
  o ~1,2 m); `parent_request.bbox_crs` niesie wtedy uklad pliku.
- **`--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}`** w trybie
  `--bbox`/`--geometry` dla obu krajow (CZ: wycinek `exportImage`, PL:
  scalony wycinek); godlo + `--target-crs` = blad. Na pograniczu `--country
  auto --target-crs` powstaja dwa wycinki PL+CZ ze wspolnym
  `parent_request`. `--vertical-crs {KRON86,EVRF2007,Bpv}`.
- **Domyslne wartosci per kraj:** `--resolution`/`--vertical-crs`/`--system`
  bez podania rozwiazywane dopiero po ustaleniu kraju (PL:
  1m/EVRF2007/1992; CZ: 2m/Bpv, `--system` nie dotyczy).

#### LAZ — chmury punktow LIDAR (ADR-029)
- **`GugikLazProvider`** — pliki `.laz` (dane pomiarowe ALS) przez **WFS**
  (`DanePomiaroweLidarEVRF2007` / `DanePomiaroweLidarKRON86`), discovery
  obszarowe: godlo (<= 1:10000) / `--bbox` / `--geometry` -> bbox EPSG:2180
  -> `discover_tiles()` (WFS GetFeature). BBOX i envelope WFS w kolejnosci
  osi (N,E), straz przeciecia odrzuca kafle spoza obszaru (K1). Kafle sa
  drobniejsze niz 1:10000; godlo kafla jest etykieta (nieparsowalne),
  `url_do_pobrania` brany wprost z WFS. Metadane WFS: `akt_rok`,
  `akt_data`, `char_przestrz` (gestosc), `uklad_xy`, `czy_ark_wypelniony`,
  rama `msGeometry`.
- **Wybor kafli wg pokrycia obszaru** (domyslnie, bez `--year`): kafle od
  najnowszego `akt_rok` (w roku nowsza `akt_data`); starszy kafel jest
  pomijany, gdy jego czesc wspolna z obszarem pokrywaja wybrane juz kafle
  (ramy w EPSG:2180, kazda +1 m tolerancji, `COVERAGE_TOLERANCE_M`), wiec
  PL-1992 i PL-2000 tego samego miejsca sie nie dubluja. Kafel wnoszacy
  niepokryty kawalek zostaje (caly); kafel `czy_ark_wypelniony=NIE` nie
  wypiera starszych; kafel, ktorego rama nie przecina obszaru (tylko
  obwiednia), jest pomijany. `--year` = tylko ten rok, dedup pokryciowy
  w roku. Pominiete kafle: `Info:` na stderr (takze z `-q`), w bibliotece
  `superseded`. Nowy modul `core/coverage.py` (przeciecie, roznica i bufor
  wypuklych wielokatow, bez nowych zaleznosci).
- **Roczniki:** lista lat wylacznie z WFS GetCapabilities
  (`_fetch_available_years`/`_get_available_years`, cache w pamieci tylko
  udanych odpowiedzi; awaria = `DownloadError`). Jawny `--year` sprawdzany
  wobec GetCapabilities danej uslugi przed GetFeature: nieistniejacy rok =
  `rocznik ... nie istnieje w usludze ... (dostepne: ...)` bez sugestii
  ponowienia; awaria discovery rocznika = `DownloadError` z rokiem
  i informacja o niekompletnym wyniku; `No LAZ tiles found` oznacza komplet
  poprawnych odpowiedzi (N7).
- **CLI:** `kartograf download <godlo|--bbox|--geometry> --product laz`
  z flagami `--year`, `--vertical-crs` (domyslnie EVRF2007),
  `--min-density` (gestosc NOMINALNA z WFS — faktyczna bywa kilkukrotnie
  wyzsza, E16), `--campaigns`, `--min-year`; pobieranie rownolegle
  (`--workers`), pomijanie istniejacych plikow. Porazka choc jednego kafla =
  `Error: N z M kafli LAZ nie pobrano ...` z PELNA lista, kod 1 (pobrane
  kafle zostaja).
- **Uklad:** `laz/pl_<uklad>_<vcrs>/<hierarchia godla>/<oryginalna
  nazwa>.laz`, `<uklad>` per kafel z `uklad_xy` (`LazTile.uklad`);
  wartosc nierozpoznana = `ValidationError`, a discovery pomija taki kafel
  z ostrzezeniem w logu (bez zgadywania z formatu godla).
  `FileStorage.get_raw_path(..., uklad=)` — sciezka dla nieparsowalnego
  godla bez `SheetParser`; ten sam segment co CLI daje `uklad=tile.uklad`,
  bez niego uklad wynika z formatu godla.
- **API biblioteki:** `kartograf.download.laz` — `download_laz_area(bbox,
  ...)`, `run_laz_download(selection, ...)`, `LazDownloadResult`
  (`downloaded`/`skipped`/`failed`/`superseded`), `LazTileFailure`,
  `write_laz_sidecar`; `GugikLazProvider.select_tiles(...)` zwraca
  `LazTileSelection` (`tiles`, `superseded` = `SupersededLazTile`),
  a `discover_tiles` = `select_tiles(...).tiles`; `select_tiles` waliduje
  `min_year` jak `DownloadManager`. `LazTile` z polami `footprint` (rama
  w EPSG:2180, osie E,N), `date`, `full_sheet` (z wartosciami domyslnymi).
  Eksporty w `kartograf`: `GugikLazProvider`, `LazTile`, `LazTileSelection`,
  `SupersededLazTile`, `download_laz_area`, `run_laz_download`,
  `LazDownloadResult`, `LazTileFailure`. Porazka kafla nie jest wyjatkiem
  (`result.failed`). Jedna sesja HTTP na watek (`SessionPerThread`),
  sesja wstrzyknieta (`session=`) wygrywa zawsze.
- **Sidecar kafla:** `request.year`/`request.min_density` (gdy podane),
  `extra.tile_sheet`, `extra.year`, `extra.nominal_density`; w trybie
  `--bbox`/`--geometry` `extra.parent_request` (bbox w podanym ukladzie,
  `countries: ["PL"]`). Provider bez `descriptor_key` dostaje
  `pl.gugik.laz`; nieudany zapis loguje `kartograf.sources.sidecar`.

#### Wycinek PL `--target-crs` (ADR-027)
- **CLI:** `--target-crs` z `--bbox`/`--geometry` PL daje jeden scalony
  GeoTIFF `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif` (mozaika arkuszy GUGiK
  + crop + lokalny warp przypieta operacja). Tylko `nmt` i PL-1992;
  czytelne bledy dla godla, `--product nmpt|orto|laz`, `--system 2000`.
- **`EPSG:2180`** = crop na siatce pikseli arkuszy (obszar rozszerzony na
  zewnatrz o < 1 px, wartosci 1:1, `transform: null`, nazwa pliku niesie
  wspolrzedne zadania). Narozniki pikseli arkuszy GUGiK leza w polowie
  miedzy wielokrotnosciami piksela (5 m: 5k + 2,5 m; 1 m: k + 0,5 m), czesc
  arkuszy 5 m kampanii 2022 ma inna faze: arkusze o roznych fazach daja
  `GridMismatchError(ValidationError)` z `.off_grid` i kod 1 z podpowiedzia
  innego `--target-crs`. **Inny cel** — W1: warp kazdego arkusza osobno,
  odchylenia fazy w `extra.off_grid_sheets` (S5).
- **Selekcja arkuszy** (`select_pl_cutout_sheets`) ma zapas 1 piksela (tryb
  bbox i suma R-01); `--geometry` z `EPSG:2180` (bez sumy R-01) zapasu nie
  ma — skrajna kolumna albo wiersz moze byc nodata (`docs/ARCHITECTURE.md`
  4.3). `--geometry` obejmuje CALA obwiednie geometrii bez maskowania,
  a przy reprojekcji arkusze to suma godel geometrii i godel obwiedni
  z zapasem (obwiednia wypelniona danymi; koszt: przy rzadkiej geometrii
  pobieraja sie arkusze calej obwiedni). Arkusz wydany przez skorowidz
  w ukladzie PL-2000 pod godlem PL-1992 konczy budowe bledem z opisem;
  starego arkusza PL-2000 w cache PL-1992 nie miesza sie — usun go i ponow.
- **Braki danych:** arkusz bez danych GUGiK (`NoCoverageError`) = nodata +
  `Warning:` + `extra.missing_sheets` (`PlCutoutResult.missing_sheets`);
  inna awaria pobrania = kod 1; obszar bez danych w zadnym arkuszu =
  `ValidationError`. Wynik w calosci pusty mimo pobranych arkuszy:
  `PlCutoutResult.all_nodata=True`, `Warning:`, `extra.all_nodata: true`
  (E15). Arkusze niepelnej kampanii: `extra.sheet_sources[].full_sheet`,
  `PlCutoutResult.partial_sheets`, pusty wycinek z nich ostrzega
  o niepelnej kampanii, nie o braku danych (E13). Lokalna kampania uzyta
  przy awarii skorowidza: `PlCutoutResult.unverified`,
  `extra.unverified_sheets`, `Warning:` (I-1).
- **Pomijanie istniejacego wyniku:** po samym istnieniu pliku;
  `PlCutoutResult(skipped=True)` odtwarza `missing_sheets`,
  `off_grid_sheets` i `all_nodata` z sidecara (bez czytania rastra), CLI
  powtarza ostrzezenia. Arkusze reuzyte dopisuja `extra.parent_requests`
  bez utraty oryginalnego `parent_request`. `--force` przebudowuje wycinek
  i pobiera ponownie jego arkusze; tanszy rebuild: usun sam wycinek.
- **Kampanie:** wycinek jest zawsze `newest` i czyta arkusze przez
  dowiazania; `--campaigns all` lub `--min-year` z `--target-crs` =
  `Error:` kod 1 przed siecia.
- **Biblioteka** (`kartograf.download.cutout`, eksport w `kartograf`):
  `download_pl_cutout(bbox, target_crs, ..., cache=)` oraz kroki
  `prepare_pl_cutout` (fail-fast, bez sieci; niefaktyczny pion =
  `ValidationError`) -> `select_pl_cutout_sheets` -> `run_pl_cutout`
  (nie przyjmuje `campaigns`), typy `PlCutout`, `PlCutoutSheets`,
  `PlCutoutResult`. CLI jest nakladka na te funkcje. `run_pl_cutout`
  z wstrzyknietym providerem o innym pionie albo rozdzielczosci konczy sie
  `ValidationError` przed pobraniem. Bbox w ukladzie czeskim z etykieta
  malymi literami albo ze spacjami (`"epsg:5514"`) opuszcza Krovaka
  przypieta operacja jak `"EPSG:5514"` (m-2).
- **Mozaika i zasoby:** arkusze owijane w VRT z jawnym EPSG:2180 i Float32
  (arkusz ASC z samymi liczbami calkowitymi nie zamienia mozaiki w Int32,
  arkusze z `.prj` i bez niego sie mieszaja), lista zrodel sortowana;
  zrodla otwierane leniwie (wycinek z > 1024 arkuszy nie konczy sie "Too
  many open files"; limit deskryptorow Linux 1024, macOS 256); plik
  posredni mozaiki kompresowany (deflate, kafle 512 px, BigTIFF gdy
  trzeba). Przed siecia kontrola wolnego miejsca — DOLNE oszacowanie
  (wynik + arkusze bez pliku w sciezce standardowej, policzone wstepnie;
  pod `newest` arkusz z nowsza albo usunieta kampania zostanie pobrany mimo
  dowiazania), `Info:` dla wycinkow >= 1 GiB, bez twardego limitu. Obie
  sciezki zapisu atomowe: nieudana budowa nie niszczy poprzedniego pliku
  i nie zostawia pustego `bbox/`.

#### Kampanie GUGiK (ADR-030)
- **CLI `--campaigns {newest,all}`** (domyslnie `newest`) i **`--min-year
  RRRR`** (1900..2100, inaczej `Error:` bez sieci); tylko PL (GUGiK).
  `newest` = regula ADR-028, rozwiazywana przy kazdym uruchomieniu (siec po
  wygasnieciu cache 7 d), pobiera tylko brakujace kampanie. `all` = KAZDY
  rekord po twardym filtrze ADR-028 ze wszystkich warstw, bez limitu liczby
  kampanii (`logger.info` z liczba, raz na arkusz).
- **`--min-year`** = granica na roku `aktualnosc` (nie `dt_pzgik`), dla obu
  strategii; rekord bez ustalonego roku jej nie spelnia (`all`: pominiety;
  `newest`: `NoCoverageError` "starsza niz min_year" z data tej kampanii,
  lista/hierarchia: status `no_coverage`). Rok z nazwy warstwy sluzy tylko
  w `all` do pominiecia zapytania warstwy (gorny rok < granicy); `Starsze`
  zawsze odpytywane.
- **Uklad:** `<segment>/kampanie/<data>_<id>/<hierarchia godla>/<godlo>.<ext>`
  + `.meta.json`; `<data>` = `aktualnosc` rekordu, `<id>` = pierwszy segment
  liczbowy nazwy pliku w URL, inaczej `u` + 8 znakow hex `sha1(URL)`.
- **Dowiazanie sciezki standardowej:** raz na arkusz po zebraniu kampanii,
  hardlink, a gdy niedostepny — kopia z `Warning: hardlink niedostepny na
  tym systemie plikow — sciezka standardowa jest KOPIA najnowszej kampanii
  dla N arkuszy (...) (extra.link=copy)` (kod bez zmian). Bez symlinkow
  (errata 4: symlink z Linuksa na udziale SMB jest nieczytelny dla klientow
  Windows, a udzialy ograniczaja dlugosc celu). Sidecar sciezki
  standardowej to zwykly plik z `extra.link` (`hardlink`/`copy`)
  i `extra.link_target` (jedyne zrodlo celu). Dowiazanie przestawiane
  tylko na kampanie o kluczu `(aktualnosc, dt_pzgik, url)` scisle wiekszym
  niz klucz biezacego celu (z sidecara, a gdy nieczytelny — z nazwy
  katalogu); inaczej bez zmian (nigdy wstecz). Kontrola istnienia: cel
  z sidecara (`samefile` dla hardlinku); usuniety katalog kampanii albo
  brak sidecara = brak pliku (ponowne pobranie/dowiazanie).
- **Format z pola `format` rekordu** (nie z rozszerzenia URL); plik zawsze
  z rozszerzeniem kanonicznym `.asc`/`.tif` (rekord 72675 z URL `.xyz` to
  AAIGrid = zwykla kampania `.asc`); brak pola (orto, stare wpisy cache) =
  format domyslny produktu. Po pobraniu weryfikacja tresci (naglowek
  AAIGrid / sygnatura TIFF); nieznany format albo niezgodna tresc =
  porazka kampanii (`DownloadError` z nazwa formatu, plik usuniety), nigdy
  ciche `.asc`. Plik kampanii bez sidecara (przerwany przebieg) przechodzi
  weryfikacje tresci przed odtworzeniem sidecara.
- **Sidecar pliku kampanii jest obowiazkowy** (`emit_sidecar(required=True)`,
  zapis atomowy): porazka zapisu = porazka kampanii (plik danych usuniety,
  dowiazanie nieprzestawione); pozostale sidecary best-effort.
  `extra.campaign` = `{id, date, survey_work_id, source, full_sheet,
  pzgik_date}`, `request.campaigns` zawsze, `request.min_year` tylko gdy
  podany.
- **Porazki:** czesciowa porazka `all` na arkuszu (np. niepoprawna
  `aktualnosc` jednej kampanii) = kod 1 z pelna lista, pozostale kampanie
  pobrane, dowiazanie na najnowsza poprawna; porazka dowiazania (nawet
  kopii) = porazka arkusza (kod 1, lista idzie dalej takze przy
  `--workers 1`, pobrane kampanie zostaja). Wyscig bez blokad: rownolegle
  wywolania na tej samej sciezce moga chwilowo zostawic dowiazanie na
  starszej kampanii; kolejne `newest`/`all` je naprawia (pliki
  w `kampanie/` nietkniete).
- **Awaria skorowidza przy `newest` (I-1, errata 5):** blad TRANSPORTU
  rozwiazywania rekordu (siec, HTTP 429/5xx; nie brak pokrycia, nie inne
  4xx ani raport OGC) na arkuszu z istniejaca lokalna kampania nie jest
  porazka — arkusz pominiety z lokalnej kampanii (dowiazanie bez zmian),
  `Warning: <godlo>: skorowidz GUGiK niedostepny — uzyto lokalnej kampanii
  bez sprawdzenia nowszej (...)` na stderr takze z `-q` (lista: jedno
  `Warning:` z godlami), kod bez zmian. `--campaigns all`, `--min-year`,
  `--force` i brak lokalnej kampanii — blad jak dotad.
- **Podsumowanie `all`** (bez `-q`, takze pojedyncze godlo): `Downloaded
  <n> campaign files for <m> sheets to <dir> (<k> already existed)`
  (n = pobrane, k = juz lokalne).
- **CZ i LAZ:** zadanie bez PL (godlo CZ takze pod `auto`, obszar/geometria
  z jawnym `--country cz`, obszar w calosci czeski pod `auto`) z opcjami
  kampanii = `Error: CZ (CUZK) nie ma kampanii — --campaigns all/--min-year
  dotycza tylko PL` (kod 1, bez sieci); obszar pod `auto` z PL i CZ = jedno
  `Info:`, CZ pobierane dalej (biezaca wersja danych CUZK). LAZ:
  `--campaigns all` = wszystkie kafle, ktorych rama przecina obszar, bez
  deduplikacji ADR-029 (kafel przeciety tylko obwiednia pomijany);
  `--min-year` = dolna granica `akt_rok`; `--min-year` i `--year`
  wykluczaja sie (`Error:`); LAZ bez dowiazan.
- **Biblioteka:** `DownloadManager(campaigns=, min_year=)`,
  `DownloadManager.last_sheet` (`SheetFetch`: `godlo`, `path`, `skipped`,
  `downloaded`, `reused`, `link`, `unverified`), `DownloadResult.
  campaign_files`, `reused_campaign_files`, `copied`, `unverified` (godlo ->
  tresc bledu); eksporty `kartograf.CampaignRef`, `kartograf.SheetFetch`;
  moduly `download/campaigns.py` (`CampaignRef`, `validate_campaign_args`,
  `verify_file_format` — `OSError` odczytu jako `DownloadError`)
  i `download/links.py`; `FileStorage.get_campaign_path`,
  `FileStorage.list_files(campaigns=)`. Providery PL: `resolve_campaigns`,
  `download_record`, `record_source`, `_resolve_record(parser, timeout,
  query)`; skorowidz: `select_campaign_records`, `layer_upper_year`,
  `LAYER_FAMILY` (warstwa z rodziny produktu spoza `LAYER_PATTERN` =
  `logger.warning`, nie jest odpytywana). Biblioteka bez `MetadataCache`
  pyta skorowidz przy kazdym `download_sheet` (takze arkusza juz
  pobranego) — przekaz cache providerowi.
- **Cache:** tabela `campaigns_cache` (lista kampanii arkusza, TTL 7 dni,
  `--min-year` poza kluczem; po skanie czesciowym obsluguje tylko granice
  >= granicy skanu, nizsza = ponowny skan), `kartograf cache stats`
  drukuje `Campaign entries`.

#### NMT PL i skorowidz GUGiK
- **`NoCoverageError(DownloadError)`** — zrodlo nie ma danych dla arkusza
  (wszystkie warstwy skorowidza odpowiedzialy); `DownloadResult.no_coverage`
  (podzbior `failed`), podpowiedzi `NoCoverageError.hints` /
  `DownloadResult.no_coverage_hints`.
- **Lista arkuszy PL** (`--bbox`/`--geometry` bez `--target-crs`, takze
  hierarchia godla): brak danych jednego arkusza nie przerywa pozostalych
  (R5 probuje wszystkie, niezaleznie od `--workers`); `NoCoverageError` =
  `Warning:` i `DownloadProgress.status == "no_coverage"` (`∅` w CLI);
  >= 1 plik i tylko braki pokrycia -> kod 0, wszystkie bez danych albo
  twarda awaria -> kod 1 z pelna lista. Pojedynczy arkusz bez danych ->
  kod 1. Podpowiedzi (np. `uzyj --scale 1:2000` dla PL-2000 1:10000) jako
  `Info:` na stderr (bez duplikatow, max 5 linii + "i K innych"), bez
  podsumowania `Downloaded 0 ...` (O-3/O-6/O-7, S2).
- **Wybor rekordu (ADR-028):** twardy filtr godla (caly token), ukladu,
  rozdzielczosci 1 m/5 m, RGB orto i daty; w pierwszej pasujacej warstwie
  wygrywa najnowsza `aktualnosc`, potem `dt_pzgik`, URL, niezaleznie od
  flagi pelnego arkusza (K4). Rekord niepelnego arkusza (`full_sheet:
  false`) wygrywa, gdy jest najnowszy, ale CLI drukuje `Warning:` (tor
  godla, listy i wycinka, takze przy skip), a `extra.source.full_sheet` to
  zapisuje (E13). Podpowiedz `NoCoverageError` o arkuszu w innym ukladzie
  ma postac `<godlo> (<skala>) — uzyj tego godla lub --system X --scale Y`
  (takze orto; D14).
- **Arkusze PL-2000 opublikowane we wspolrzednych EPSG:2180** (zaobserwowane
  w strefie 7, np. `7.125.11.19`, `7.173.21.01`, z niecalkowitym `cellsize`
  0,99937 m): sidecar zapisuje faktyczny uklad pliku (`horizontal_crs:
  EPSG:2180`), deklaracje rekordu w `extra.source.declared_crs`
  (`PL-2000:S7`), plik lezy w segmencie wg godla; CLI drukuje `Warning: N
  arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: <godlo>
  (godlo: EPSG:2178, plik: EPSG:2180)` na stderr (tor godla, listy
  i hierarchii, takze przy skip i `-q`; fakt czytany z sidecara), kod bez
  zmian; biblioteka loguje to samo przez `kartograf.sources.sidecar` (E17).
  Pozostale arkusze PL-2000 maja w sidecarze EPSG strefy 2176-2179 (N8).
- **Ortofotomapa: wariant koloru w sciezce** — RGB domyslnie
  (`GugikOrtoProvider(color="RGB")`, najnowszy rekord RGB, K5) w
  `orto/pl_<uklad>/`, `color="CIR"` (podczerwien) w `orto/pl_<uklad>_cir/`,
  B/W w `orto/pl_<uklad>_bw/`; nowe `BaseProvider.storage_variant`,
  `FileStorage(variant=...)` (E12).
- **`DownloadManager`:** `download_sheets(godla, ...)`
  i `expand_sheets(godla)` (lista godel, grubsze PL-1992 rozwijane do
  1:10000, duplikaty raz; porazki zbierane w `last_result`); `last_result`
  (`DownloadResult`: succeeded/failed/skipped/no_coverage ostatniego
  `download_hierarchy()`/`download_sheets()`, kasowane na wejsciu do
  `download_sheet()`/`download_hierarchy()`/`download_sheets()`; CLI
  ustala z niego kod wyjscia, A2-5); `sidecar_extra=` (pola scalane do
  `extra` kazdego sidecara, np. `parent_request`); `download_sheet(on_download=)`.
- **Fabryka `create_nmt_provider()`** (`providers/pl/__init__.py`) — jedno
  miejsce polskich domyslow NMT; regula "NMT 5m tylko w EVRF2007" w jednym
  miejscu (`kartograf.providers.pl.nmt_vertical_crs`), skutek: korekta do
  EVRF2007 — CLI (`--resolution 5m --vertical-crs KRON86`) drukuje `Info:`
  na stderr (takze z `-q`), fabryka loguje, `prepare_pl_cutout` odrzuca
  niefaktyczny pion `ValidationError` (D11).
- **Jeden parser wartosci ukladu GUGiK** `sources.registry.parse_pl_uklad`
  (`PL-1992`, `PL-2000:S5..S8`, biale znaki obcinane) dla rekordow
  skorowidza, `horizontal_crs_for_uklad` (sidecar) i `LazTile.uklad`;
  wartosc nietypowa (np. `PL-2000` bez strefy) odrzucana spojnie (rekord
  bez ukladu, kafel LAZ pominiety z ostrzezeniem, `ValidationError`)
  (E11, D3).

#### Sidecar `.meta.json` i uklad `data/`
- **Sidecar `<plik>.meta.json`** po kazdym udanym pobraniu (schemat
  `kartograf-meta/1`: dataset, CRS-y poziomy/pionowy, nodata, licencja,
  `request`, `kartograf_version`, `transform`, `extra`) — kontrakt dla
  Hydrografa. Blad zapisu nie przerywa pobrania (wyjatek: plik kampanii).
  Pola `extra` m.in.: `source` (pochodzenie arkusza), `sheet_sources`,
  `missing_sheets`, `off_grid_sheets`, `all_nodata`, `unverified_sheets`,
  `parent_request`, `parent_requests`, `campaign`, `link`/`link_target`,
  `fallback`, `derived`. Wspolne opakowanie `sources.sidecar.emit_sidecar`
  (format operacji `pinned_label`); `build_metadata(capability=, nodata=)`
  — jawny wybor kanalu po capability i jawne `nodata` (`exportImage` CUZK
  zwraca `noDataValue: null`). Sidecary PL w trybie `--bbox`/`--geometry`
  maja `extra.parent_request` (wspolny klucz grupowania z CZ i LAZ).
- **`kartograf_version` w sidecarze i `kartograf --version`** dla wersji
  `dev` podaja `<wersja>+<krotki SHA>` (np. `0.7.0-dev+6db4408`), przy
  niezacommitowanych zmianach w `kartograf/` z sufiksem `.dirty`
  (`kartograf/_version.py::build_version`, leniwie, cache na proces); bez
  gita albo poza repozytorium — samo `__version__`. Wydania, `__version__`
  i `User-Agent` bez zmian.
- **Uklady pionowe -> kody** (`vertical_crs_code`): `KRON86` = `EPSG:9650`,
  `EVRF2007` = `EPSG:5621` (rodzina, wspolna dla PL i CZ), `EVRF2007-PL` =
  `EPSG:9651` (realizacja polska), `Bpv` = `EPSG:8357` (Baltic 1957, CUZK);
  sidecary PL deklaruja realizacje polska (`resolve_vertical_crs`).
- **Segmenty z deskryptorow:** `SourceDescriptor.storage_subdir` to
  szablon z `{uklad}`/`{vcrs}`, sciezke daje `resolve_subdir(uklad=,
  vertical_crs=)` (czesciowe wypelnienie legalne, vcrs malymi literami);
  `FileStorage(vertical_crs=)` (domyslnie `"EVRF2007"`),
  `FileStorage(subdir=...)`; `{uklad}` rozwiazywany per godlo; nierozwiazany
  placeholder albo pusty wymiar (`vertical_crs=''`, takze przez
  `DownloadManager` z providerem o pustym pionie) = `ValidationError`
  zamiast segmentu `nmt/pl_1992_1m_`. Jedna fabryka segmentu providera
  `download.storage.storage_for_provider` i nazwa wycinka
  `download.storage.bbox_cutout_path` (PL i CZ).

#### Land cover, HSG, CORINE
- **HSG ma sidecar** (`kartograf soilgrids hsg` /
  `HSGCalculator.calculate_hsg_by_bbox`): deskryptor
  `global.isric.soilgrids`, `extra.derived = "hsg"`, warstwy zrodlowe,
  glebokosc, statystyka.
- **CORINE bez credentials CLMS:** sidecar podgladu PNG (WMS) deklaruje
  faktyczny CRS — `EPSG:3857` (EEA Discomap) lub `EPSG:4326` (DLR, rok
  1990) — zamiast `EPSG:3035` (tylko GeoTIFF z CLMS) i niesie
  `extra.fallback = "wms_png"` z `extra.note` "podglad WMS, nie dane".
- **`LandCoverProvider.download_by_admin_unit`/`validate_admin_unit`**
  (kanoniczne) + `download_by_teryt`/`validate_teryt`/`source_url` jako
  dzialajace aliasy zgodnosciowe.

#### Cache metadanych
- **`MetadataCache.get_record/set_record`** — rekord skorowidza
  (`{"source": ...}`) albo potwierdzony brak pokrycia z trescia podpowiedzi
  (`{"no_coverage": true, "message": ..., "hints": ...}`), TTL 7 dni;
  trafienie negatywne odtwarza ten sam `NoCoverageError`.
  `stats()["record_count"]`, `kartograf cache stats` drukuje `Record
  entries`. CLI podpina cache rekordow w torach PL (N6).
- **`MetadataCache(refresh=True)`** — odczyty = chybienie, zapisy normalnie;
  `--force` w torach PL i CZ omija ODCZYT cache, ale zapisuje swiezy wybor,
  wiec kolejny przebieg bez `--force` dostaje nowy rekord (E14, D16).
- Nowe: `MetadataCache.db_path`, `MetadataCache.error`, parametr
  `on_disabled=`, klucze `stats()` `db_exists` i `error` (opis
  w Zmienione).

#### Biblioteka i architektura zrodel
- **`kartograf/sources/`** — deskryptory zrodel jako dane (zero IO przy
  imporcie): `SourceDescriptor`, `AccessChannel`, `TransportKind`,
  `LicenseInfo`, `CountryProfile` + rejestr (`get_source`, `sources_for`,
  `get_country`, `all_countries`, `vertical_crs_code`,
  `resolve_vertical_crs`).
- **`kartograf/transform/crs.py`** — twarda polityka transformacji:
  `TransformerGroup(allow_ballpark=False)`, filtr dokladnosci, probe
  odrzucajacy siatki obcych krajow (`inf`), kontrola `isfinite`,
  `TransformError`/`TransformUnavailableError` z remedium, `KNOWN_PATHS`;
  `PinnedTransform` niesie pare ukladow (`src_crs`/`dst_crs`), przyjmuje
  skalary lub tablice `numpy` i udostepnia `gdal_operation()` (pipeline PROJ
  dla `COORDINATE_OPERATION` z korekta kolejnosci osi — cel northing-first
  bez `axisswap` dawal raster w calosci nodata); `build_pinned_transform`
  wykonuje probe wewnatrz kontekstu `network.set_network_enabled(...)`;
  wspolne `CONTENT_POLICY` i `WARP_MARGIN_PX` dla torow PL i CZ (D9).
- **`kartograf.transform.raster.warp_to_grid`** — lokalna reprojekcja rastra
  (pojedyncza mozaika albo lista arkuszy, W1) z wymuszona operacja
  przypieta (ADR-024).
- **`kartograf/transport/`** — `download_to()` i `get_with_retry()` (opis
  w Zmienione, "Transport HTTP") oraz `mosaic_and_crop()` (rasterio.merge +
  przyciecie, propagacja nodata; wynik zapisywany przez
  `merge(dst_path=...)` — szczyt pamieci ~1,06x rozmiaru rastra, A3-4;
  opcje `dst_kwds=`, `snap_to_source_grid=`, `assign_crs=`, `dtype=`,
  domyslnie wylaczone — uzywa ich wycinek PL; zrodlo spoza siatki
  wiekszosci = ostrzezenie w logu). `check_source_grid`, `has_valid_pixels`.
- **`kartograf.core.bbox`:** `BBox` (`kartograf.BBox`,
  `core.sheet_parser.BBox`, `core.geometry.BBox` to ta sama klasa),
  `validate_bbox`, `transform_bbox` (gesta obwiednia: 21 punktow na
  krawedz, cache transformerow, operacja przypieta przez `transformer=` —
  duck typing), `is_czech_crs`; `transform/bbox.py::envelope_from_2180`
  dla CORINE/SoilGrids (D19).
- **`kartograf/core/parser_registry.py`** — rejestr systemow godel (literal
  `SYSTEMS`: pl2000, cz_tm33, cz_sm5, fallback pl1992; `detect_system`
  zawsze zwraca `SheetSystem`); `SheetParser` i `FileStorage` deleguja do
  rejestru (wyniki identyczne).
- **CLI podzielone na moduly** `cli/_parser.py`, `parse_cmd.py`,
  `download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`, `cache_cmd.py`;
  `cli/commands.py` to fasada z entry pointem `main` (bez zmian).
- **`KARTOGRAF_DEBUG=1`** — pelny traceback zamiast skroconego `Error: ...`
  dla kazdego wyjatku docierajacego do bariery `main` (takze
  `KartografError`; N1-1, N17).

### Zmienione

#### Transport HTTP
- **Jeden transport dla wszystkich providerow:** pliki GUGiK
  (NMT/NMPT/orto/LAZ/BDOT10k), CORINE, SoilGrids i CUZK pobiera
  `transport.http.download_to` z hakami `validate=` (CORINE/SoilGrids:
  `reject_error_document` — raport XML/HTML WMS/WCS bez ponowien) i `save=`
  (BDOT10k GPKG: rozpakowanie ZIP); zapytania (skorowidz, WFS LAZ, TERYT
  BDOT10k, `CuzkClient.query`) — `get_with_retry` (opcjonalne `params=`).
  Zastepuje szesc kopii petli pobierania w providerach (D1).
- **Polityka ponowien:** max 3 proby (`MAX_RETRIES`, niekonfigurowalne),
  ponawiane tylko bledy sieci, HTTP 429 i 5xx; inne 4xx (np. 404 przy
  blednej nazwie pokrycia WCS) koncza od razu z komunikatem `HTTP <kod>
  (bez ponowien)`. Naglowek `Retry-After` (sekundy albo data HTTP) wydluza
  przerwe, max 60 s (`MAX_RETRY_AFTER`). Jeden backoff: 2 s, potem 4 s
  (`backoff_delay`). `DownloadError.status_code` niesie kod HTTP ostatniej
  proby (dotad `None`). Bledy tresci (JSON, raport OGC) nie sa ponawiane.
  Zapytanie TERYT BDOT10k i indeks CUZK sa ponawiane (dotad jedna proba).
  Nowe: `is_retryable`, `retry_wait`, `http_status`, `http_failure`
  (N5, N9).
- **Zapis atomowy przez `os.replace`** (takze scalanie GPKG BDOT10k) zamiast
  `Path.rename` — na Windows `--force` nad pobranym arkuszem padal na
  `FileExistsError`. Katalog docelowy powstaje dopiero po udanej odpowiedzi
  HTTP (nieudane pobranie nie zostawia pustego katalogu).
- **Komunikaty `DownloadError` po polsku** (`HTTP 404 (bez ponowien)`,
  `po 3 probach`); blad pobrania pliku NMT/NMPT/orto podaje nazwe pliku
  z URL, nie godlo (`84183_1852496_N-34-139-C-a-3-1.asc (OpenData): HTTP
  404`).
- **Sesje:** jedna sesja HTTP na watek (`transport.http.SessionPerThread`,
  `make_gugik_session`: keep-alive, `User-Agent: kartograf/<wersja>`) we
  wszystkich providerach GUGiK, BDOT10k, CORINE (takze zapytania CLMS
  w trybie bezposrednim) i SoilGrids — zamiast nowej, niezamykanej
  `requests.Session()` na kazde wywolanie; providery trzymaja
  `self._sessions` (D2). Zapytania GetCapabilities/GetFeatureInfo
  skorowidza z sesja per watek i ponowieniami (S1).

#### NMT PL i skorowidz GUGiK
- **Warstwy skorowidza (NMT/NMPT/orto) wylacznie z GetCapabilities** —
  wspolne `skorowidz._fetch_wms_layers` z `LAYER_PATTERN` providera (orto:
  `SkorowidzeOrtofotomapy<rok>`/`Starsze`, bez wariantow `Zasiegi`),
  warstwy roczne malejaco, zbiorcze i `Starsze` na koncu, cache w pamieci
  tylko udanych odpowiedzi. Bez list zaszytych i bez fallbacku: awaria
  GetCapabilities = `DownloadError`. GetCapabilities ma timeout providera
  (30 s NMT/NMPT, 60 s orto albo `timeout=` z `download()`) zamiast
  zaszytych 10 s (N3, E10).
- **Diagnoza awarii skorowidza:** awaria wszystkich warstw = niedostepnosc
  uslugi, nie "brak pokrycia dla godla" (A2-9); czesciowa awaria przy braku
  arkusza w pozostalych = "brak pokrycia niepewny" (`DownloadError`, kod 1).
  Odpowiedz bedaca raportem wyjatku OGC (`ServiceExceptionReport`,
  `ows:ExceptionReport`, np. `LayerNotDefined` z HTTP 200) albo uszkodzony
  szablon GetFeatureInfo to nieudane zapytanie warstwy, nie brak arkusza
  (dotad dawaly falszywy `NoCoverageError`, a w wycinku nodata, ktore
  kolejne przebiegi pomijaly); URL w odpowiedzi nadal wygrywa, strona HTML
  bez znacznikow OGC (pusty szablon MapServera) to brak arkusza (I-2, N1).
- **`DownloadManager.download_sheet` zwraca (i opisuje sidecarem) sciezke
  zwrocona przez provider** — jak `download_hierarchy`/`download_sheets`;
  wczesniej sciezke docelowa managera. Tryb sekwencyjny i rownolegly maja
  jedna tresc "pobierz arkusz" (`_fetch_sheet`) i jeden raport postepu
  (`downloading` tylko sekwencyjnie) (D10).
- **Listy godel rozwijanych do hierarchii** (`--bbox`/`--geometry`)
  pobierane sekwencyjnie, rownoleglosc wewnatrz kazdej hierarchii — znika
  zwielokrotnienie watkow (dotad do `--workers`^2 zadan do GUGiK) (A2-3).
- **`DownloadManager` z providerem znajacym swoj pion** nie loguje korekty
  "5m tylko EVRF2007" (pion pochodzi z providera); CLI z `--resolution 5m
  --vertical-crs KRON86` tworzy provider skorygowany przez
  `create_nmt_provider` (D11).

#### Cache metadanych
- **Plik otwierany leniwie:** `MetadataCache()` nie tworzy
  `.kartograf_cache.db` przy konstrukcji — plik i schemat powstaja przy
  pierwszym zapisie (`set_*`); odczyty na braku pliku to chybienie,
  `stats()` zwraca zera (klucz `db_exists`), `clear()`/`vacuum()`/`close()`
  nic nie tworza. `kartograf cache path|stats|clear` w katalogu bez bazy jej
  nie tworza (`Database size: - (file not created yet)`). Otwarcie (WAL,
  tabele, migracja starej bazy — usuniecie `url_cache`) pod istniejacym
  lockiem.
- **Uszkodzony cache nie blokuje pobierania:** blad SQLite przy otwarciu,
  odczycie albo zapisie (smieci zamiast bazy, ucieta baza, brak uprawnien,
  `database is locked`) wylacza cache na reszte zycia instancji — odczyty
  to chybienie, zapisy no-op, `stats()` zwraca zera i klucz `error`
  (`MetadataCache.error`); jedno ostrzezenie na instancje (`logger.warning`
  albo `on_disabled=`), bez wyjatku, thread-safe. CLI pobierania drukuje
  ``Warning: cache metadanych nieczytelny (<sciezka>): <blad> — praca bez
  cache; uzyj `kartograf cache clear` albo usun plik`` (stderr, takze
  z `-q`; kod wedlug wyniku pobrania), a przy blokadzie przez inny proces
  `Warning: cache metadanych zablokowany przez inny proces (...)` bez rady
  usuniecia. `kartograf cache clear` usuwa nieczytelny plik z `-wal`/`-shm`
  (`Usunieto nieczytelny plik cache: <sciezka>`, kod 0; brak prawa albo
  blokada = `Error:`, kod 1), `cache stats` drukuje ``Error: cache
  nieczytelny: <sciezka> (<blad>) — uzyj `kartograf cache clear` `` (kod 1),
  `cache path` bez zmian. Wczesniej lista arkuszy konczyla sie porazka
  KAZDEGO arkusza (`file is not a database`, kod 1).

#### Land cover, HSG, BDOT10k
- **Katalog wyjsciowy land cover powstaje dopiero przy zapisie pliku**
  (`download_to` po udanej odpowiedzi): `LandCoverManager()` i `kartograf
  landcover list-layers` nie zostawiaja katalogow; BDOT10k, CORINE
  i SoilGrids nie tworza go przed zapytaniem (nieudane pobranie, np.
  HTTP 404, nie zostawia pustego katalogu).
- **HSG: katalog wyjsciowy dopiero przy zapisie** — `kartograf soilgrids
  hsg` i `HSGCalculator.calculate_hsg_by_bbox`/`_by_godlo` tworza katalog
  tuz przed zapisem rastra (brakujacy plik `--geometry` albo blad SoilGrids
  nie zostawia pustego `./data/hsg`).
- **`Bdot10kProvider.DEFAULT_TIMEOUT` = 120 s** jako domyslna wartosc
  `download_by_admin_unit/godlo/bbox` (zapytanie TERYT 30 s) (N11).
- **BDOT10k GPKG skladany w lokalnym katalogu tymczasowym** i przenoszony
  do celu kopia obok + `os.replace` (udzialy sieciowe SMB/CIFS bez blokad
  zakresow bajtow konczyly SQLite `database is locked`); sprzatanie takze
  przy wyjatku.
- **CORINE i SoilGrids:** obwiednia bboxa z EPSG:2180 przez
  `envelope_from_2180` (wynik bez zmian, D19).

#### CLI
- **`Downloading <godlo> ...`** drukowane dopiero przy starcie pobrania
  (`download_sheet(on_download=)`), nie przy `Skipped`/`Error:`;
  pojedyncze godlo pominiete jako istniejace drukuje `Skipped <godlo> -
  already exists at ...` zamiast `Downloaded to` (decyduje
  `manager.last_sheet.skipped`); `Error:` nie poprzedza pusta linia, gdy
  pasek postepu nie wystartowal.
- **Teksty `--help`** opisuja CZ/CUZK, warstwy SW w BDOT10k, SoilGrids, LAZ,
  HSG, `sheet_cache`, kampanie; `--scale` po polsku z odeslaniem do
  `docs/USAGE.md` 1.6, `--resolution` opisuje SM5 (tylko 5m) vs TM33/bbox
  (2m domyslnie lub 5m) (A6-13).
- Wewnetrznie: jeden helper bledu transformacji (`Error: ... Remedium:
  ...`, `_print_transform_error`, D6) i jeden naglowek listy arkuszy
  (`_print_sheet_list`, D15); tresc komunikatow bez zmian.

#### Pakiet i zaleznosci
- **`pyproject.toml`:** wersja dynamiczna z `kartograf.__version__`
  (usuniety rozjazd `0.6.1` vs `0.7.0-dev`; `dynamic = ["version"]`);
  `[tool.setuptools.packages.find] include = ["kartograf*"]` (`tests/` poza
  dystrybucja); opis i keywords o CUZK/DMR/LAZ (A6-4, A6-5, A6-6).
- **Licencja jako wyrazenie SPDX (PEP 639):** `license = "MIT"` +
  `license-files = ["LICENSE"]`, bez klasyfikatora licencji, prawdziwe
  `authors`; build-system `setuptools>=77.0.3` (bez `wheel`) — build bez
  izolacji wymaga setuptools >= 77, dystrybucje maja `Metadata-Version:
  2.4` z `License-Expression: MIT` i LICENSE w `dist-info/licenses/`,
  upload na PyPI wymaga twine >= 6.x.
- **Paczka zrodlowa (sdist) z kompletnymi testami:** `MANIFEST.in`
  (`graft tests`) dolacza `tests/conftest.py`, `tests/__init__.py`
  i `tests/fixtures/` — testy offline przechodza z rozpakowanego sdist
  (wheel nadal bez `tests/`). Klasyfikator `Programming Language :: Python
  :: 3.13`.

#### Jakosc kodu i brama
- **Brama:** testy offline (`pytest tests/ -m "not live"`), prog pokrycia
  `fail_under` w `pyproject.toml`, `ruff check .` i `ruff format --check .`
  na calym repo (takze skrypty `docs/research/`), `mypy kartograf/ tests/`
  bez bledow. `.claude/` w `.gitignore` i poza ruff/mypy. Testy `live`
  wymagaja sieci i nie naleza do bramki (`pytest -m live`, tylko swiadomie).
- **mypy bez bledow:** poprawki wylacznie typujace, bez `# type:
  ignore`/`cast`; widoczny skutek: brak `private_key` w poswiadczeniach
  CLMS konczy sie jawnym komunikatem (proxy: `None` + log, tryb
  bezposredni: `DownloadError`) zamiast bledu z PyJWT. `affine` w
  `ignore_missing_imports`. Usuniety `from __future__ import annotations`
  (Python 3.12; odwolania wprzod w `core/sheet_parser.py` w cudzyslowie).
- **Testy offline:** `tests/conftest.py` przewraca kazdy test otwierajacy
  gniazdo spoza loopbacku (wyjatek: marker `live`) i stubuje GetCapabilities
  skorowidza; testy odkrywania warstw wylaczaja stub markerem
  `real_wms_layers`. Fixtury z surowych odpowiedzi serwerow
  (`tests/fixtures/gugik_skorowidz/`, `gugik_laz/`, `gugik_asc/`, `cuzk/`).
  Naprawy maja testy przypinajace (RED przed poprawka, GREEN po); testy
  `live` WMS PL-2000 sprawdzaja prawdziwe rekordy/CRS (N5).
- **Wycinek PL zweryfikowany offline na realnych arkuszach 5 m:** cel
  EPSG:2180 bez rozbieznosci wartosci wzgledem arkusza zawierajacego srodek
  piksela; cel EPSG:5514 zgodny z niezaleznym warpem GDAL kazdego arkusza
  (odchylenia przy szwach — `docs/ARCHITECTURE.md` 4.3).
- **Deduplikacja wewnetrzna** (bez zmiany zachowania): `GugikWcsMixin`
  (`providers/pl/wcs.py`: `WCS_FORMATS`, `_construct_wcs_url`,
  `get_supported_formats` dla NMT/NMPT i orto), `validate_godlo`
  w `SkorowidzLayersMixin`, `skorowidz.coverage_hints`, wspolne
  `warp_to_grid` w torze CZ (D8, D13, D14). Usunieta nieosiagalna galaz
  `--product laz` w dyspozycji obszarowej i martwe fallbacki
  `getattr(args, "vertical_crs", "KRON86")` (N5-1).

#### Dokumentacja
- Nowe `docs/ARCHITECTURE.md` (architektura, kontrakty danych, uklad
  `data/`) i `docs/USAGE.md` (przewodnik: przyklady CLI i biblioteki, wynik
  pobrania, kampanie, CLMS, znane problemy; 1.6 "Kiedy `--scale` jest
  niezbedne": skala docelowa = skala arkuszy GUGiK, PL-1992 bez flagi,
  PL-2000 zwykle `--scale 1:2000`). Przyklady bez zbednego `--scale
  1:10000` przy godle PL-1992, `kartograf download CTES96` bez
  `--resolution`.
- `docs/DEVELOPMENT_STANDARDS.md` (15-17) glownym zrodlem konwencji
  (`IMPLEMENTATION_PROMPT.md` usuniety); `README.md` skrocony do
  wprowadzenia; `CLAUDE.md` ograniczony do zasad krytycznych i odsylaczy;
  indeks ADR wylacznie w `docs/DECISIONS.md` (errata 1 ADR-009).
- Dokumentacja zgodna z zachowaniem: ponowienia tylko dla sieci/429/5xx,
  arkusz za granica w trybie listy = `Warning:` i kod 0, lista timeoutow,
  krawedz `cli -> transport` w ARCHITECTURE 2, docstringi
  `LandCoverManager`/`MetadataCache`/`download_pl_cutout` (N2, N4, N10,
  N13, N16). Raporty weryfikacji na zywo w `docs/research/` (etap 1 CZ,
  pogranicza i pas morski, przypadki brzegowe, kampanie ADR-030).

### Usuniete

#### API biblioteki, CLI i providery
- Martwy kod CLMS/Keychain w `providers/corine.py` (`KEYCHAIN_SERVICE`,
  `get_credentials_from_keychain`, `save_credentials_to_keychain`,
  `get_clms_credentials`) — credentials czyta wylacznie podproces auth
  proxy; `CorineProvider.DLR_YEARS` (A5-1).
- Zaszyte `WMS_LAYERS` i fallback na nie (takze przestarzale warstwy NMPT)
  — warstwy z GetCapabilities; `GugikProvider.FORMAT_EXTENSIONS`
  i nadpisanie `get_file_extension`, `GugikOrtoProvider.OPENDATA_URL_PATTERN`,
  atrybuty `RETRY_BACKOFF_BASE` providerow, `SoilGridsProvider.TERYT_WMS_ENDPOINT`
  (tabela w BREAKING).
- `MetadataCache.get_url/set_url` i tabela `url_cache` (usuwana przy
  otwarciu bazy).
- Endpoint `/token` auth proxy i `AuthProxyClient.get_access_token()`.
- Format `GML` (A6-2).
- Re-eksporty implementacji komend z fasady `cli/commands.py` (BREAKING).
- Modul `kartograf.providers.landcover_base` (klasy w
  `kartograf.providers.base`) i stare moduly providerow poza
  `providers/pl/`.
- Prywatne `core.geometry._transform_bbox` (4 narozniki) — zastepuje je
  `core.bbox.transform_bbox` (K6).

#### Pakiet i dokumentacja
- `requirements.txt` i `requirements-dev.txt` — jedynym zrodlem zaleznosci
  jest `pyproject.toml`.
- `IMPLEMENTATION_PROMPT.md` (tresc w `docs/DEVELOPMENT_STANDARDS.md`).

### Poprawione

#### Parsery i selekcja arkuszy
- **Selekcja arkuszy z obwiedni miedzy ukladami:** `SheetParser.get_bbox`,
  `Parser2000.get_bbox`, selekcja PL-1992/PL-2000 i czytniki SHP/GPKG
  (`read_feature_bboxes`/`get_overall_bbox`/`find_sheets_for_geometry`)
  licza obwiednie jedna funkcja `core.bbox.transform_bbox` (21 punktow na
  krawedz) zamiast 4 naroznikow: bbox EPSG:2180 przez poludnik 19°E nie
  gubi pasa przy gornej krawedzi (dla bboxa 20 km pomijano 6 arkuszy; za
  cene mozliwych arkuszy nadmiarowych), arkusze grube przez 19°E (np.
  `N-34`) maja poprawna dolna krawedz (-468 m), obiekt SHP/GPKG przez 19°E
  nie traci ~65 m na polnocy, `find_sheets_for_bbox(..., system="2000")`
  z bboxa WGS84 przez poludnik osiowy strefy (15/18/21/24°E) nie gubi
  wiersza arkuszy (np. 16 zamiast 8). Arkusze 1:10000 bez zmian (1e-6 m).
  To samo dla wycinka PL i selekcji kafli LAZ z bboxa WGS84 (`min_y`
  wycinka nizej o ~479 m) oraz rozpoznawania krajow pod `auto`.
- **Wydajnosc:** `SheetParser.get_bbox("EPSG:2180")` buduje transformer raz
  na proces (200 wywolan: 1371 ms -> 8 ms); czytniki SHP/GPKG — jeden
  transformer na warstwe.
- **Biale znaki wokol godla:** `detect_system`, `path_parts`,
  `SheetIndex.sm5_sheet` i `CuzkDmrProvider.download` obcinaja je spojnie
  z parserami; CLI obcina pozycyjne godlo `download`/`parse` (`kartograf
  download " 302_5550"` nie trafia do toru PL z mylacym `Nieprawidlowe godlo
  PL-1992`).
- **`kartograf parse 6`:** sam numer strefy PL-2000 (5-8) daje komunikat, ze
  to strefa, z najgrubszym formatem `strefa.pas.slup` (np. `6.179.12`),
  takze z jawnym `uklad=` w `SheetParser`; ogolny blad godla podaje formaty
  PL-1992 i PL-2000 z przykladami.
- **`--geometry`:** punktowe SHP daja bbox zdegenerowany zamiast
  `AttributeError`; GPKG bez obwiedni w naglowku czyta punkt z WKB (takze
  Z/M i EWKB z flaga SRID), pusta geometria pomijana, nieobslugiwany typ =
  `ValidationError` zamiast cichego pominiecia rekordu (A1-3, A1-5).

#### CLI
- **Walidacja bboxa w CLI:** `kartograf download --bbox` (PL, CZ, LAZ),
  `landcover download --bbox` i `soilgrids hsg --bbox` parsuja bbox jednym
  `cli._parser.parse_bbox_arg` — bbox odwrocony, NaN/inf albo zla liczba
  wartosci = `Error: Invalid bbox format: <powod>. Expected: ...` na stderr
  i kod 1 (dotad arkusz-smiec, pobieranie albo `Error: ValueError`;
  podpowiedz nie idzie na stdout) (K7b).
- **`kartograf landcover download`** z blednym `--property`/`--depth`/
  `--stat` (SoilGrids) albo `--year` (CORINE) konczy sie `Error: <tresc>`
  i kodem 1 przed siecia, bez `ValueError:` i podpowiedzi `KARTOGRAF_DEBUG`
  (N8).
- **`main()` ma bariere na wyjatki:** blad spoza `KartografError` =
  `Error: <Typ>: <komunikat>` z podpowiedzia `KARTOGRAF_DEBUG=1` i kod 1
  zamiast tracebacku (N1-1).

#### NMT PL i skorowidz GUGiK
- **Parser rekordow skorowidza** rozpoznaje URL-e `.ASC` niezaleznie od
  wielkosci liter (H1).
- **Nieaktualne nazwy warstw skorowidza** (NMT 1m/EVRF2007, orto) — zaszyte
  listy z 0.6.1 zawieraly warstwy wycofane (np. `SkorowidzeNMT2023`; roczne
  warstwy orto 2018..2023 scalone w `SkorowidzeOrtofotomapyStarsze`), nie
  znaly nowych rocznikow (2026), a orto dostawalo "Invalid layer(s) given
  in the LAYERS parameter"; usunieta przyczyna (warstwy z GetCapabilities).

#### Cache i storage
- **`MetadataCache`:** odczyty pod tym samym lockiem co zapisy (rownolegle
  odczyty potrafily oddac wiersz innego klucza, A2-1); `__del__` nie
  importuje i nie rzuca przy zamykaniu interpretera (`ImportError:
  sys.meta_path is None`).
- **`FileStorage.delete()`** usuwa takze sidecar `.meta.json`.

#### Land cover, HSG, CORINE, auth proxy
- **`Bdot10kProvider`** zwraca sciezke faktycznie zapisanego pliku `.gpkg`
  (sidecar nie laduje obok nieistniejacego pliku, A2-6).
- **`CLMS_CREDENTIALS` jest czytane:** zmienna trafia do podprocesu auth
  proxy (przed Keychain), wiec CORINE GeoTIFF dziala takze na Linux
  i Windows — dotad jedynym zrodlem byl Keychain macOS (A4-1).
- **Auth proxy i klient:** urwany strumien nie dokleja odpowiedzi 502 do
  ciala rastra (pobranie bez `Content-Length` ramkowane jako chunked),
  `download_file()` pisze przez plik tymczasowy i sprawdza
  `Content-Length` (bylo: `True` i uszkodzony GeoTIFF, A4-2); start proxy
  i singleton pod lockiem, uchwyt podprocesu i watek drenujacy stderr jako
  stan klasowy (dwa watki nie startuja dwoch proxy, rownolegly CORINE nie
  miesza GeoTIFF z PNG); po `kill()` podproces odbierany (`wait`, bez
  zombie), strumieniowana odpowiedz `/download` zamykana; brak credentials
  nie uruchamia podprocesu (`AuthProxyClient.is_available()` = False poza
  macOS), odczyt portu z timeoutem, stderr drenowany (N4-1, A4-11, A4-13,
  A4-14).
- **SoilGrids i CORINE:** obwiednia bboxa przez `transform_bounds()` zamiast
  dwoch naroznikow (zamawiany obszar byl o ~10% za waski); CORINE liczy
  proporcje obrazu WMS z obwiedni metrycznej (galaz DLR 1990 tracila 1,7x
  rozdzielczosci pionowej) (A4-7).
- **HSG:** piksele nodata (`-32768`, `NaN`, wartosc nodata rastra) dostaja
  0 ("brak danych"), nie grupe B (A4-5); `soilgrids hsg --stats` liczy
  powierzchnie geodezyjnie dla rastrow EPSG:4326 (bylo `0.00 ha`, A4-6).

## [0.6.1] - 2026-03-24

### Fixed
- **NMT 5m: naprawione nazwy warstw WMS**
  - `WMS_LAYERS["5m"]["EVRF2007"]`: `SkorowidzeNMT2022` → `SkorowidzeNMT2022iStarsze`
  - Usunieta nieistniejaca warstwa `SkorowidzeNMT2021iStarsze`
  - Dodana brakujaca warstwa `SkorowidzeNMT2025`
  - Bledne nazwy powodowaly brak wynikow przy pobieraniu NMT 5m mimo dostepnosci danych

### Added
- **Walidacja warstw WMS przez GetCapabilities**
  - `_fetch_wms_layers()` — pobiera liste dostepnych warstw z WMS GetCapabilities
  - `_get_validated_layers()` — porownuje hardcoded warstwy z live WMS, auto-aktualizacja przy rozbieznosci
  - Lazy validation: tylko przy pierwszym wywolaniu `_get_opendata_url()`
  - Graceful fallback: jesli GetCapabilities niedostepne, uzywa hardcoded warstw
  - Warning logowany przy wykryciu rozbieznosci miedzy hardcoded a live
  - In-memory cache per instancja providera (bez lock, benign duplicate OK)
  - Osobny timeout 10s dla GetCapabilities
  - Dziala dla GugikProvider (NMT) i GugikNmptProvider (NMPT) przez dziedziczenie
  - GugikOrtoProvider nieobslugiwany (inna hierarchia dziedziczenia)

### Tests
- **1007 testow** (+17 nowych)
  - Nowy `tests/test_wms_layer_validation.py` — 17 testow dla walidacji warstw WMS

---

## [0.6.0] - 2026-03-03

### Added
- **Parallel downloads with ThreadPoolExecutor**
  - `DownloadManager(max_workers=4)` — configurable thread pool for hierarchy downloads
  - `DownloadResult` dataclass — structured results with succeeded/failed/skipped tracking
  - `_download_hierarchy_parallel()` — concurrent sheet downloads with progress callbacks
  - `LandCoverManager.download_batch()` — parallel batch download for land cover data
  - CLI: `--workers`/`-w` flag on `kartograf download` (default: 4)
  - Thread-safe temp filenames in all providers (`pid_threadid.tmp` pattern)
- **SQLite metadata cache (MetadataCache)**
  - `kartograf/cache/metadata.py` — SQLite WAL mode, TTL 7 days, thread-safe writes
  - URL cache for GUGiK OpenData lookups (NMT, NMPT, Orto)
  - TERYT cache for BDOT10k point-to-TERYT resolution
  - `prune_expired()` — automatic cleanup of stale entries
  - Integrated with GugikProvider, GugikNmptProvider, GugikOrtoProvider, Bdot10kProvider
  - CLI: `kartograf cache stats|clear|path`
- **PL-2000 BBox verification tests**
  - 67 new tests: reference values, hierarchy consistency, live WMS, edge cases
  - `@pytest.mark.live` marker for GUGiK WMS integration tests
- **Public API: eksport MetadataCache i DownloadResult**
  - `from kartograf import MetadataCache, DownloadResult`

### Tests
- **990 testow** (+155 nowych)

---

## [0.5.0] - 2026-03-02

### Added
- **PL-2000 sheet naming system — full support**
  - `Parser2000` class for parsing PL-2000 godla (format `zone.row.column[.subdivisions]`)
  - 5 skal: 1:10000, 1:5000, 1:2000, 1:1000, 1:500
  - 4 strefy merydianowe: 5 (EPSG:2176), 6 (EPSG:2177), 7 (EPSG:2178), 8 (EPSG:2179)
  - BBox calculation z transformacja CRS (pyproj)
  - Hierarchia: get_parent(), get_children(), get_all_descendants(), get_hierarchy_up()
  - `find_sheets_2000_for_bbox()` — BBox to PL-2000 godla lookup
- **SheetParser auto-detekcja PL-1992 vs PL-2000**
  - `SheetParser("6.179.12")` automatycznie rozpoznaje PL-2000
  - `SheetParser("N-34-130-D")` automatycznie rozpoznaje PL-1992
  - Walidacja zgodnosci uklad/format
- **find_sheets_for_bbox: parametr system="1992"|"2000"**
  - `find_sheets_for_bbox(bbox, system="2000")` zwraca godla PL-2000
  - `find_sheets_for_geometry()` rowniez obsluguje parametr system
- **CLI: pelna obsluga PL-2000**
  - `kartograf parse 6.179.12.20` — auto-detekcja, wyswietla strefe i CRS
  - `kartograf download --bbox ... --system 2000` — pobieranie z godlami PL-2000
  - `--bbox-crs` rozszerzony o EPSG:2176-2179
- **FileStorage: obsluga sciezek PL-2000**
  - Struktura katalogow: `nmt_2000_1m/6/179/12/20/6.179.12.20.asc`
    (uwaga 2026-08-22: podkatalog `nmt_2000_1m` nie zostal zrealizowany —
    arkusze PL-2000 ladowaly w `nmt_<res>/` obok PL-1992, patrz ADR-017
    i docstring `FileStorage`; rozdzielenie katalogow odlozone.
    **Domkniete w 0.7.0** — ADR-026 dal PL-2000 wlasne segmenty
    `nmt/pl_2000_<res>_<vcrs>/`; patrz Breaking Changes 0.7.0)
- **Public API: eksport Parser2000 i find_sheets_2000_for_bbox**
  - `from kartograf import Parser2000, find_sheets_2000_for_bbox`

### Removed
- **BDOT10k: usunięto filtrowanie po kategorii (--category pt/hydro)**
  - Pobierany jest cały plik BDOT10k bez podziału na kategorie
  - Usunięto stałe `PT_LAYERS`, `HYDRO_LAYERS`, `CATEGORY_FILTERS`
  - Usunięto parametr `category` z `download_by_teryt()`, `_download_with_retry()`, `_extract_gpkg_from_zip()`
  - Usunięto argument CLI `--category`
  - `_extract_gpkg_from_zip()` wyciąga i scala wszystkie warstwy GPKG z ZIP
  - `get_available_layers()` zwraca wszystkie 15 warstw (PT* + SW*)

### Fixed
- **download_sheet(): PL-2000 sub-10k godla pobierane bezposrednio**
  - Godla PL-2000 w skalach 1:5000, 1:2000, 1:1000, 1:500 sa teraz pobierane
    jako pojedyncze pliki, bez proby rozwijania do 1:10000
- **CLI: dynamiczne etykiety skal**
  - `format_hierarchy()` — naglowek "from current to X" zamiast hardcoded "1:1000000"
  - `format_children()` — "finest scale X" zamiast hardcoded "1:10000"

### Tests
- **835 testow** (+199 nowych; w trakcie prac bylo 849 — 14 testow
  `--category` usunieto w tej samej wersji razem z flaga, ADR-016)

---

## [0.4.1] - 2026-02-08

### Fixed
- **BDOT10k: rtree spatial indices preserved during GPKG merge**
  - After merging multiple GPKG files, only the base (first) file kept its rtree index
  - New `_copy_rtree_index()` method copies rtree virtual table, data, and `gpkg_extensions` entry
  - All merged layers now retain spatial indices for fast spatial queries

### Added
- **Geometry file selection (`--geometry FILE`)**
  - Support for SHP (via pyshp) and GPKG (via sqlite3 + envelope parsing) input files
  - Per-feature bbox extraction for precise tile selection (not entire file bbox)
  - `find_sheets_for_geometry()` — public API for geometry → godla lookup
  - `get_overall_bbox()` — union bbox for landcover/soilgrids
  - CRS auto-detection from .prj (SHP) and gpkg_spatial_ref_sys (GPKG)
  - New dependency: `pyshp>=2.3.0`
- **CLI: `--geometry` and `--layer` for all download commands**
  - `kartograf download --geometry area.shp` — NMT tiles intersecting features
  - `kartograf download --geometry area.gpkg --layer catchments` — GPKG layer selection
  - `kartograf landcover download --source bdot10k --geometry area.shp`
  - `kartograf soilgrids hsg --geometry area.shp`

### Tests
- **636 testow** (+62 nowych)
  - 31 testow `test_geometry.py`: envelope parsing, SHP/GPKG reading, CRS transform, find_sheets_for_geometry, get_overall_bbox
  - 12 testow CLI geometry: download/landcover/soilgrids --geometry, mutual exclusivity
  - 5 testow `TestBdot10kRtreeIndex`: merge preserves indices, no geometry, no index, extensions copied, base preserved

---

## [0.4.0] - 2026-02-07

### Added
- **NMPT (Numeryczny Model Pokrycia Terenu / Digital Surface Model)**
  - `GugikNmptProvider` — dziedziczy z GugikProvider, nadpisuje endpointy NMPT
  - Tylko rozdzielczość 1m, vertical CRS: KRON86 lub EVRF2007
  - Download: godło → OpenData ASC, bbox → WCS GeoTIFF
- **Ortofotomapa (Standard Resolution, 25cm)**
  - `GugikOrtoProvider` — osobna klasa, format TIF
  - Brak vertical CRS (2D RGB), 9 warstw WMS (2018-2025+starsze)
  - Download: godło → OpenData TIF, bbox → WCS GeoTIFF
- **CLI `--product {nmt,nmpt,orto}` — wybór produktu w komendzie download**
  - `kartograf download N-34-130-D-d-2-4 --product nmpt` — pobiera NMPT
  - `kartograf download --bbox ... --product orto` — pobiera ortofoto
  - Domyślnie: nmt (bez zmian)
- **`find_sheets_for_bbox()` — reverse lookup: bbox → godła arkuszy**
  - Algorytm hierarchicznego przycinania (matematyczny, bez WFS)
  - Obsługa EPSG:2180 i EPSG:4326
  - Dowolna skala docelowa (1:1M do 1:10k)
  - Zoptymalizowane wyszukiwanie 1:200k (siatka 12x12)
- **CLI `kartograf download --bbox` — pobieranie NMT dla bbox**
  - `--bbox min_x,min_y,max_x,max_y` — współrzędne bbox
  - `--bbox-crs {EPSG:2180,EPSG:4326}` — CRS bbox (domyślnie EPSG:2180)
  - `godlo` staje się opcjonalny (godlo XOR --bbox)
  - Automatyczne wykrywanie arkuszy i pobieranie w pętli
- **Automatyczne rozwijanie godeł do 1:10000 w `download_sheet()`**
  - `download_sheet("N-34-130-D-d-2")` (1:25000) → automatycznie pobiera 4 arkusze 1:10000
  - `download_sheet("N-34-130-D-d")` (1:50000) → pobiera 16 arkuszy 1:10000
  - Dla godeł 1:10000 zachowanie bez zmian (pojedynczy plik)
  - Nowy parametr `on_progress` — callback postępu przy rozwijaniu hierarchii
  - Zwracany typ: `Path` (1:10000) lub `list[Path]` (coarser scales)
  - CLI dostosowane — wyświetla liczbę pobranych plików przy rozwijaniu

### Tests
- **574 testow, pokrycie 83.95% (cel 80% osiagniety)**
  - Nowy `tests/test_gugik_nmpt.py` — 21 testow dla GugikNmptProvider
  - Nowy `tests/test_gugik_orto.py` — 25 testow dla GugikOrtoProvider
  - Nowy `tests/test_auth_client.py` — 30 testow dla AuthProxyClient
  - Nowy `tests/test_auth_proxy.py` — 24 testy dla CLMSCredentials, ProxyHandler
  - Rozszerzony `tests/test_cli.py` — +12 testow (product CLI), +11 testow (landcover/soilgrids CLI)
  - Rozszerzony `tests/test_storage.py` — +8 testow (product storage)
  - Rozszerzony `tests/test_download_manager.py` — +3 testy (default_ext)
  - Rozszerzony `tests/test_landcover.py` — +38 testow
  - Rozszerzony `tests/test_hsg.py` — +6 testow

### Fixed
- Poprawiony komunikat błędu przy braku pokrycia NMT 5m — zamiast technicznego "No ASC file found in any WMS layer" wyświetla czytelną informację o braku pokrycia danego obszaru w GUGiK

### Changed
- **FileStorage: podkatalogi `1m`/`5m` → `nmt_1m`/`nmt_5m`**
  - Nowy parametr `product` w FileStorage (np. product="nmpt", product="orto")
  - Struktura: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`
- **DownloadManager: dynamiczne rozszerzenie pliku**
  - `_default_ext` pobierane z `provider.default_extension` zamiast hardcoded `.asc`
- **BaseProvider: nowa property `default_extension`** (domyślnie `.asc`)
- Migracja z black + flake8 na ruff (pyproject.toml)
- Usuniecie .flake8, dodanie .editorconfig
- Standaryzacja dokumentacji wg shared/standards
- Przepisanie CLAUDE.md (7 sekcji, ~148 linii)
- Przepisanie PROGRESS.md (4 sekcje, skondensowane z 785 linii)
- Rozbudowanie DEVELOPMENT_STANDARDS.md (722 linii, 15 sekcji wg shared/standards)
- Rozbudowanie IMPLEMENTATION_PROMPT.md (284 linii, 11 sekcji, aktualny kontekst v0.3.2)
- Aktualizacja README.md, PRD.md, SCOPE.md
- Auto-naprawa kodu przez `ruff check --fix` (63 poprawki: importy, type annotations)

### Added
- Konfiguracja ruff (linter + formatter) w pyproject.toml
- Plik .editorconfig
- Sekcja [project.optional-dependencies] dev w pyproject.toml
- docs/DECISIONS.md — rejestr 9 decyzji architektonicznych (ADR)

### Removed
- Plik .flake8 (konfiguracja pokryta przez ruff)
- Sekcja [tool.black] z pyproject.toml

---

## [0.3.2] - 2026-01-21

### Changed - Storage Structure and Default Vertical CRS

- **Domyślny układ wysokościowy zmieniony na EVRF2007**
  - `GugikProvider`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - `DownloadManager`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - CLI: `--vertical-crs` domyślnie `EVRF2007`
  - Kronsztadt 86 (KRON86) jest przestarzały i dostępny jako opcja legacy

- **Nowa struktura katalogów z rozdzielczością**
  - `FileStorage`: nowy parametr `resolution` (domyślnie `"1m"`)
  - Pliki NMT są teraz rozdzielone według rozdzielczości:
    ```
    data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 1m
    data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 5m
    ```
  - `DownloadManager` automatycznie przekazuje `resolution` do `FileStorage`
  - Domyślne rozszerzenie pliku zmienione z `.tif` na `.asc`

### Breaking Changes

- **Struktura katalogów** - pliki NMT są teraz zapisywane w podkatalogu `1m/` lub `5m/`
  - Stara ścieżka: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
  - Nowa ścieżka: `data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`

- **Domyślny vertical_crs** - zmieniony z `KRON86` na `EVRF2007`
  - Aby używać starego układu: `--vertical-crs KRON86`

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (EVRF2007 domyślnie)
kartograf download N-34-130-D-d-2-4
# → data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m
# → data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Użyj starego układu Kronsztadt (legacy)
kartograf download N-34-130-D-d-2-4 --vertical-crs KRON86
```

---

## [0.3.1] - 2026-01-21

### Added - NMT Resolution Selection

- **Wybór rozdzielczości NMT** - Obsługa danych NMT w dwóch rozdzielczościach
  - `1m` (GRID1) - wysoka rozdzielczość, domyślna
  - `5m` (GRID5) - niższa rozdzielczość, tylko dla EVRF2007

- **GugikProvider** - Nowy parametr `resolution`
  - `GugikProvider(resolution="5m", vertical_crs="EVRF2007")`
  - Nowe endpointy WMS dla 5m: `SheetsGrid5mEVRF2007`
  - Automatyczna walidacja: 5m wymaga EVRF2007
  - Nowe metody: `get_supported_resolutions()`, `is_wcs_available()`
  - `download_bbox()` rzuca ValueError dla 5m (WCS niedostępne)

- **DownloadManager** - Nowy parametr `resolution`
  - `DownloadManager(resolution="5m")` - automatycznie wymusza EVRF2007

- **CLI** - Nowa opcja `--resolution`
  - `kartograf download N-34-130-D --resolution 5m`
  - Skrót: `-r 5m`

**Ograniczenia 5m:**
- Dostępne tylko w układzie EVRF2007
- Brak obsługi WCS (download_bbox) - tylko arkusze OpenData

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (domyślnie)
kartograf download N-34-130-D-d-2-4

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m

# Pobierz hierarchię w 5m
kartograf download N-34-130-D --scale 1:10000 -r 5m
```

### Changed

- **Testy** - 365 testów (18 nowych dla resolution)

### Fixed - Cross-Project Compatibility (2026-01-21)

- **Public API exports** - Uzupełniono brakujące eksporty w głównym module
  - Dodano `SoilGridsProvider` do `kartograf/__init__.py`
  - Dodano `HSGCalculator` do `kartograf/__init__.py`
  - Teraz możliwy import: `from kartograf import SoilGridsProvider, HSGCalculator`

### Fixed - QA Review (2026-01-21)

- **Synchronizacja wersji** - Ujednolicono wersję we wszystkich plikach
  - `pyproject.toml`: 0.3.0 → 0.3.1
  - `kartograf/__init__.py`: 0.3.0-dev → 0.3.1
  - `README.md`: zaktualizowano status i liczbę testów

- **Synchronizacja zależności** - Uzupełniono brakujące zależności
  - `pyproject.toml`: dodano `rasterio>=1.3.0`, `numpy>=1.24.0`
  - `requirements.txt`: dodano `PyJWT[crypto]>=2.8.0`

- **Testy** - Naprawiono test wersji w `test_integration.py`

- **Dokumentacja** - Dodano sekcję QA Review do `PROGRESS.md`

---

## [0.3.0] - 2026-01-18

### Added - SoilGrids i Hydrologic Soil Groups (HSG)

- **SoilGridsProvider** - Provider dla ISRIC SoilGrids (dane glebowe)
  - Globalne dane glebowe w rozdzielczości 250m
  - WCS Endpoint: `https://maps.isric.org/mapserv`
  - **11 parametrów glebowych:**
    - `bdod` - Gęstość objętościowa (kg/dm³)
    - `cec` - Pojemność wymiany kationowej (cmol/kg)
    - `cfvo` - Fragmenty gruboziarniste (%)
    - `clay` - Zawartość gliny (%)
    - `nitrogen` - Azot całkowity (g/kg)
    - `ocd` - Gęstość węgla organicznego (kg/m³)
    - `ocs` - Zasób węgla organicznego (t/ha)
    - `phh2o` - pH w H2O
    - `sand` - Zawartość piasku (%)
    - `silt` - Zawartość pyłu (%)
    - `soc` - Węgiel organiczny (g/kg)
  - **6 głębokości:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
  - **5 statystyk:** mean, Q0.05, Q0.5, Q0.95, uncertainty
  - Transformacja CRS: EPSG:2180 → WGS84

- **HSGCalculator** - Kalkulacja Hydrologic Soil Groups dla metody SCS-CN
  - `kartograf/hydrology/hsg.py` - moduł hydrologiczny
  - Klasyfikacja tekstury gleby wg trójkąta USDA (12 klas)
  - Mapowanie tekstury do HSG (A, B, C, D)
  - **Grupy hydrologiczne:**
    - A - wysoka infiltracja (piasek, piasek gliniasty)
    - B - umiarkowana infiltracja (glina piaszczysta, glina)
    - C - wolna infiltracja (glina ilasta)
    - D - bardzo wolna infiltracja (ił)
  - Automatyczne pobieranie clay/sand/silt z SoilGrids
  - Statystyki pokrycia dla każdej grupy HSG

- **CLI soilgrids** - Nowe komendy CLI
  - `kartograf landcover download --source soilgrids --property <param> --depth <głębokość>`
  - `kartograf landcover list-layers --source soilgrids`
  - `kartograf soilgrids hsg --godlo <godło>` - kalkulacja HSG
  - Opcje HSG: `--depth`, `--output`, `--keep-intermediate`, `--stats`

**Przykłady użycia:**
```bash
# Pobierz węgiel organiczny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc

# Pobierz zawartość gliny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Oblicz HSG dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats
```

### Added - Land Cover (Pokrycie Terenu)

- **LandCoverProvider** - Nowa abstrakcja dla providerów danych pokrycia terenu
  - Metody: `download_by_teryt()`, `download_by_bbox()`, `download_by_godlo()`
  - Wspólny interfejs dla różnych źródeł danych

- **Bdot10kProvider** - Provider dla BDOT10k (GUGiK)
  - Pobieranie paczek powiatowych przez TERYT
  - Pobieranie przez WMS GetFeatureInfo dla URL paczki
  - Pobieranie przez godło arkusza (konwersja na bbox)
  - **12 warstw pokrycia terenu (PT*):**
    - PTGN - Grunty nieużytkowe
    - PTKM - Tereny komunikacyjne
    - PTLZ - Tereny leśne
    - PTNZ - Tereny niezabudowane
    - PTPL - Place
    - PTRK - Roślinność krzewiasta
    - PTSO - Składowiska
    - PTTR - Tereny rolne
    - PTUT - Uprawy trwałe
    - PTWP - Wody powierzchniowe
    - PTWZ - Tereny zabagnione
    - PTZB - Tereny zabudowane
  - Automatyczne scalanie warstw PT* z ZIP do jednego GeoPackage
  - Format wyjściowy: GeoPackage (.gpkg), SHP

- **CorineProvider** - Provider dla CORINE Land Cover (Copernicus)
  - Europejska klasyfikacja pokrycia terenu (44 klasy)
  - Dostępne lata: 1990, 2000, 2006, 2012, 2018
  - **Trzy źródła danych (w kolejności priorytetu):**
    1. **CLMS API** - GeoTIFF z kodami klas (wymaga OAuth2)
    2. **EEA Discomap WMS** - Podgląd PNG (lata 2000-2018)
    3. **DLR WMS** - Fallback dla 1990
  - OAuth2 RSA authentication dla CLMS API
  - Przechowywanie credentials w macOS Keychain (serwis: `clms-token`)

- **LandCoverManager** - Zarządzanie pobieraniem danych pokrycia terenu
  - Dispatch do odpowiedniego providera
  - Obsługa wielu metod selekcji obszaru

- **CLI landcover** - Nowe komendy CLI
  - `kartograf landcover download --source bdot10k --teryt <kod>`
  - `kartograf landcover download --source corine --year <rok> --godlo <godło>`
  - `kartograf landcover list-sources`
  - `kartograf landcover list-layers --source bdot10k`

### CLMS API Authentication - Auth Proxy

CorineProvider używa **Auth Proxy** dla bezpiecznej autentykacji CLMS API:

**Architektura bezpieczeństwa:**
```
CorineProvider → localhost HTTP → AuthProxy (subprocess) → Keychain → CLMS API
```

- Credentials (klucz prywatny RSA) są izolowane w osobnym procesie
- Główna aplikacja nigdy nie widzi credentials
- Tylko odpowiedzi API są przekazywane do aplikacji

**Nowe moduły:**
- `kartograf/auth/proxy.py` - serwer HTTP izolujący credentials
- `kartograf/auth/client.py` - klient automatycznie uruchamiający proxy

**Konfiguracja:**
1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (JSON)
3. Zapisz do Keychain:
   ```bash
   security add-generic-password -a "$USER" -s "clms-token" -w '<json_credentials>'
   ```

**Tryby pracy:**
```python
# Domyślny (bezpieczny) - używa proxy
provider = CorineProvider()

# Bezpośredni (dla testów) - credentials widoczne
provider = CorineProvider(clms_credentials={...}, use_proxy=False)
```

**Uwaga:** Jeśli credentials nie są skonfigurowane, CorineProvider automatycznie używa WMS (podgląd PNG zamiast GeoTIFF z kodami klas).

### Dependencies

- Dodano `PyJWT[crypto]>=2.8.0` - JWT generation dla OAuth2
- Dodano `rasterio>=1.3.0` - przetwarzanie rastrów GeoTIFF
- Dodano `numpy>=1.24.0` - operacje na tablicach

### Technical Details

- 347 testów (42 dla landcover, 28 dla soilgrids, 34 dla HSG)
- Formatowanie: black, flake8

### Sources

- BDOT10k: https://www.geoportal.gov.pl/en/data/topographic-objects-database-bdot10k/
- CORINE Land Cover: https://land.copernicus.eu/en/products/corine-land-cover
- EEA Discomap: https://image.discomap.eea.europa.eu
- DLR EOC: https://geoservice.dlr.de/eoc/land/wms
- ISRIC SoilGrids: https://soilgrids.org/
- SoilGrids Documentation: https://docs.isric.org/globaldata/soilgrids/

---

## [0.2.0] - 2026-01-18

### Changed - Nowa architektura pobierania

**Uproszczona logika pobierania:**
- **Godło → OpenData (ASC)** - pobieranie arkusza przez godło zawsze daje plik ASC
- **BBox → WCS (GeoTIFF)** - pobieranie przez bounding box daje GeoTIFF/PNG/JPEG

**Zmiany API:**
- `download_sheet(godlo)` - zawsze pobiera ASC (usunięto parametr `format`)
- `download_hierarchy(godlo, target_scale)` - pobiera wszystkie arkusze jako ASC
- `download_bbox(bbox, filename, format)` - **nowa metoda** dla pobierania przez bbox
- Usunięto `construct_url()` z publicznego API
- `DownloadManager` nie przyjmuje już parametru `format` w konstruktorze

### Added

- **Pobieranie ASC przez OpenData** - Automatyczne wyszukiwanie URL przez WMS GetFeatureInfo
  - Zapytania do warstw: `SkorowidzeNMT2019`, `SkorowidzeNMT2018`, `SkorowidzeNMT2017iStarsze`
  - Pobieranie z `opendata.geoportal.gov.pl`

- **SheetParser.get_bbox()** - Obliczanie bounding box arkusza
  - Obsługiwane CRS: `EPSG:2180` (PL-1992), `EPSG:4326` (WGS84)
  - Transformacja współrzędnych przez `pyproj`

- **BBox** - Nowy typ danych w public API

- **GugikProvider.download_bbox()** - Pobieranie przez bounding box z WCS

### Dependencies

- Dodano `pyproj>=3.6.0` do wymagań

### Technical Details

- 245 testów

## [0.1.0] - 2026-01-17

### Added

- **SheetParser** - Parser for Polish topographic map sheet identifiers (godlo)
  - Support for scales 1:1,000,000 to 1:10,000
  - Support for "1992" coordinate system layout
  - Hierarchy navigation: `get_parent()`, `get_children()`, `get_hierarchy_up()`
  - Descendant enumeration: `get_all_descendants(target_scale)`
  - Special handling for 1:500k to 1:200k division (36 sheets per section)

- **DownloadManager** - Coordinated download of NMT data
  - Single sheet download: `download_sheet(godlo)`
  - Hierarchy download: `download_hierarchy(godlo, target_scale)`
  - Progress callbacks with `DownloadProgress` dataclass
  - Skip existing files option for resumable downloads
  - Missing sheets detection: `get_missing_sheets()`

- **GugikProvider** - Integration with GUGiK WCS service
  - GeoTIFF and Arc/Info ASCII Grid format support
  - Retry logic with exponential backoff (3 attempts)
  - 30-second timeout per request

- **FileStorage** - Hierarchical file storage management
  - Automatic directory structure based on godlo components
  - Atomic writes (temp file + rename)
  - Path generation: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif`

- **CLI** - Command-line interface
  - `kartograf parse <godlo>` - Display sheet information
  - `kartograf parse <godlo> --hierarchy` - Show hierarchy to 1:1M
  - `kartograf parse <godlo> --children` - Show direct children
  - `kartograf download <godlo>` - Download single sheet
  - `kartograf download <godlo> --scale <scale>` - Download hierarchy
  - Options: `--format`, `--output`, `--force`, `--quiet`

- **Public API** - Clean imports from main module
  - `from kartograf import SheetParser, DownloadManager`
  - All exceptions: `KartografError`, `ParseError`, `ValidationError`, `DownloadError`
  - Providers: `BaseProvider`, `GugikProvider`

- **Test Coverage** - 97% coverage with 235 tests
  - Unit tests for all modules
  - Integration tests for complete workflows

### Technical Details

- Python 3.12+ required
- Single dependency: `requests>=2.31.0`
- Project structure follows src layout
- Configured with black, flake8, pytest

[0.7.2]: https://github.com/Daldek/Kartograf/compare/v0.7.1...develop
[0.7.1]: https://github.com/Daldek/Kartograf/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/Daldek/Kartograf/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/Daldek/Kartograf/compare/4cec5d87b9aad1ffdb59693ec7163c7c97540983...v0.6.1
[0.6.0]: https://github.com/Daldek/Kartograf/compare/v0.5.0...4cec5d87b9aad1ffdb59693ec7163c7c97540983
[0.5.0]: https://github.com/Daldek/Kartograf/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Daldek/Kartograf/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Daldek/Kartograf/compare/402d8091dc02dfacb77619950fc06504bea6d7ec...v0.4.0
[0.3.2]: https://github.com/Daldek/Kartograf/compare/v0.3.1...402d8091dc02dfacb77619950fc06504bea6d7ec
[0.3.1]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.1
[0.3.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.0
[0.2.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.2.0
[0.1.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.1.0
