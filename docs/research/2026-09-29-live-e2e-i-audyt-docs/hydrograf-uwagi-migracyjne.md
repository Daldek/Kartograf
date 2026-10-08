# Uwagi migracyjne dla Hydrografa — przejscie na Kartograf 0.7.0 (2026-09-29)

**Zrodlo:** audyt D2 (`D2-docs-architektura-report.md`, sekcja 2, pozycje H-01..H-11
i obserwacje S-1/S-2), zweryfikowany ponownie na kodzie Kartografa (`develop`, stan
po fali dokumentacji 2026-09-29) i na plikach Hydrografa (TYLKO odczyt — repo
Hydrografu nie zostalo zmienione), plus wyniki testow na zywo 2026-09-29
(`L1`..`L7`). Kontroler kopiuje ten plik do
`docs/research/2026-09-29-live-e2e-i-audyt-docs/` w repo Kartografa.

**Kontekst:** Hydrograf pinuje Kartograf **v0.6.1**
(`backend/requirements.txt:52`), wiec jego dokumenty sa co do zasady spojne
z wersja zainstalowana. Ponizsze pozycje staja sie nieaktualne albo wymagaja
dzialania dopiero przy przejsciu na 0.7.0. Drzewo robocze Hydrografu ma
niezacommitowana reorganizacje dokumentow (`docs/integrations/` untracked,
`docs/KARTOGRAF_INTEGRATION.md` usuniety) — poprawki trzeba zgrac z ta praca.
Linie wg stanu dysku Hydrografu 2026-09-29.

## A. Zmiany blokujace przy upgradzie (bez nich cos przestanie dzialac)

### A1. Uklad cache NMT na dysku (H-01, H-10) — BREAKING ADR-026

- 0.6.1: `{output_dir}/nmt_5m/<hierarchia godla>/<godlo>.asc`
  i `{output_dir}/nmt_1m/...`. 0.7.0: `{output_dir}/nmt/pl_1992_5m_evrf2007/...`
  (1 m: `nmt/pl_1992_1m_<vcrs>/`, godla PL-2000: `nmt/pl_2000_...`) oraz sidecar
  `<plik>.meta.json` obok kazdego NOWO pobranego pliku.
- Kartograf NIE migruje istniejacego cache: pliki w starym ukladzie przestaja byc
  widziane jako pobrane, wiec `skip_existing` pobierze wszystko ponownie (cache
  Opolskiego: 3233 arkusze, 4,5 GB — Hydrograf `docs/PROGRESS.md:55`).
- **Pulapka `output_dir`:** Hydrograf podaje `output_dir=/data/nmt` (albo
  domyslne `../data/nmt/` w `backend/scripts/download_dem.py:297`). W 0.7.0
  sciezka to `/data/nmt/nmt/pl_1992_5m_evrf2007/N-34/131/C/c/1/1/...` (podwojne
  `nmt` — zmierzone `DownloadManager(output_dir="/data/nmt",
  provider=GugikProvider(resolution="5m")).storage.get_path(...)`). Do wyboru:
  `output_dir=/data` albo przeniesienie `/data/nmt/nmt_5m/` ->
  `/data/nmt/nmt/pl_1992_5m_evrf2007/`.
- Przed przeniesieniem sprawdzic `cellsize` w naglowku ASC: katalog `nmt_1m/`
  cache Hydrografu zawiera pliki 5 m (523 pliki, `cellsize 5.00` — raport L7).
  Pion (`_evrf2007`/`_kron86`) trzeba znac z wlasnej konfiguracji (0.6.1 nie
  pisal sidecarow; domyslnie EVRF2007, a 5 m jest tylko w EVRF2007).
- Pliki przeniesione nie dostana sidecarow (pobranie pominiete jako istniejace
  nie pisze sidecara). Pliki `.prj` dopisywane przez Hydrograf moga zostac —
  wycinek Kartografa scala arkusze z `.prj` i bez niego (VRT EPSG:2180).
- Do zmiany w dokumentach Hydrografu: `docs/integrations/KARTOGRAF.md` §6.3
  (`:439-448`) i przyklad sciezki `:335` (`cache/nmt/nmt_1m/...`);
  `docs/PROGRESS.md:55` (`/data/nmt/nmt_5m/`) i projekt archiwum
  `:1388-1391` (`archive/nmt_5m/...`) — warto odwzorowac nowym segmentem
  (`archive/nmt/pl_1992_5m_evrf2007/...`).
- Przy okazji (kod Hydrografu, do weryfikacji po jego stronie):
  `backend/scripts/bootstrap.py:1079` szuka istniejacych plikow przez
  `nmt_dir.glob("*.asc")` — nierekurencyjnie, wiec nie znajduje plikow
  w hierarchii godel ani w 0.6.1, ani w 0.7.0.

### A2. Import `Bdot10kProvider` (H-02) — BREAKING etapu 0, bez shimow

- `from kartograf.providers.bdot10k import Bdot10kProvider` konczy sie w 0.7.0
  `ModuleNotFoundError` (zmierzone). Uzyj `from kartograf import Bdot10kProvider`
  albo `kartograf.providers.pl.bdot10k`. Prywatne `_get_teryt_for_point()` nadal
  istnieje (zmierzone), wiec guard i test kontraktowy Hydrografu przejda po
  zmianie importu.
- Kod: `backend/scripts/download_landcover.py:342`. Dokumenty:
  `docs/integrations/KARTOGRAF.md:211` i `:298`.
- Pozostale importy Hydrografu (`from kartograf import DownloadManager,
  GugikProvider, BBox, SheetParser, find_sheets_for_bbox,
  find_sheets_for_geometry, HSGCalculator, LandCoverManager`,
  `kartograf.core.geometry.BBox`, `kartograf.landcover.LandCoverManager`,
  `kartograf.hydrology.HSGCalculator`) dzialaja takze w 0.7.0 (D2, pomiar).

## B. Dokumentacja Hydrografu do uzupelnienia

### B1. Semantyka bledow skorowidza (H-03, H-09)

- `docs/integrations/KARTOGRAF.md` §6.1 (`:414`, `:423`) i §7.1 (`:463-471`):
  w 0.7.0 plik to `kartograf/providers/pl/gugik.py`; jesli wszystkie warstwy
  odpowiedza bez arkusza — `NoCoverageError` (podklasa `DownloadError`: zrodlo
  nie ma danych, np. morze, strona czeska; ponawianie nic nie da); jesli czesc
  zapytan padnie (takze odpowiedz 2xx z raportem wyjatku OGC), a reszta nie ma
  arkusza — `DownloadError` ("brak pokrycia niepewny"); wszystkie padly —
  `DownloadError` ("unavailable"). Wiersz do tabeli 7.1: "`NoCoverageError` |
  GUGiK nie ma danych arkusza | nie ponawiac; w wycinku `download_pl_cutout`
  = nodata + `missing_sheets`".
- `docs/PROGRESS.md:1384` (blad zgloszony w sesji 93): stan `develop`
  Kartografa — punkt (2) (falszywe "No NMT 5m data" przy awarii warstw)
  NAPRAWIONY; punkt (1) (cichy download starszej edycji po bledzie nowszej
  warstwy) NADAL OTWARTY — znany blad Kartografa **K3**, potwierdzony na zywo
  2026-09-29 (dwa przebiegi `--force` tego samego wycinka roznily sie w 21 %
  pikseli). Lista 92 podejrzanych arkuszy Opolskiego pozostaje aktualna.
- `docs/PROGRESS.md:1385` (nowa sesja HTTP per zapytanie): nadal otwarte w
  Kartografie — znany blad **S1** (zapytania skorowidza bez ponowien i bez
  wspolnej sesji). Obejscie Hydrografu (`GugikProvider(session=..., cache=...)`,
  w 0.7.0 takze `create_nmt_provider(session=, cache=)`) dziala dalej.
- `docs/PROGRESS.md:1386` (brak pelnego rekordu skorowidza): nadal prawda;
  sidecar arkusza w 0.7.0 niesie `request = {"godlo": ...}`, bez URL-a i daty
  kampanii (dotyczy K3/K4).

### B2. Nazwy warstw (H-04)

- `docs/integrations/KARTOGRAF.md:417-421`: w 0.7.0 warstwy 1 m/EVRF2007 to
  `SkorowidzeNMT2026, 2025, 2024, 2023iStarsze` (5 m bez zmian: 2025, 2024,
  2023, 2022iStarsze); runtime i tak koryguje je przez GetCapabilities.

### B3. WCS i wycinek NMT jako API (H-05)

- `docs/integrations/KARTOGRAF.md` §6.4 (`:450-459`): endpoint WCS EVRF2007 jest
  wycofany przez GUGiK (404), a `download_bbox` z EVRF2007 konczy sie w 0.7.0
  `ValidationError` przed siecia (kod: `kartograf/providers/pl/gugik.py`, stale
  `WCS_ENDPOINTS` i `WITHDRAWN_WCS_VERTICAL_CRS`; odsylacz "`gugik.py` ok.
  :81-85" jest nieaktualny).
- Nowa sekcja (propozycja §6.5): **wycinek NMT PL jako API** —
  `from kartograf import download_pl_cutout`: jeden GeoTIFF dla bboxa albo
  geometrii z arkuszy OpenData (nie WCS; EVRF2007 i KRON86, 1 m i 5 m). Cel
  `EPSG:2180` = crop na siatce arkuszy (wartosci 1:1), `EPSG:5514`/`EPSG:3045`
  = lokalny warp przypieta operacja. Arkusz bez danych GUGiK = nodata
  + `result.missing_sheets`; kazda inna awaria pobrania = `DownloadError`.
  Z wlasnym providerem/sesja/cache: `prepare_pl_cutout` ->
  `select_pl_cutout_sheets` -> `run_pl_cutout(provider=...)`. Kandydat na krok
  "VRT mosaic" (wyjatek (b) ADR-057). Znane bledy 0.7.0-dev istotne tu: K3/K4
  (wybor pliku arkusza), S5 (arkusze 5 m o roznych fazach siatki — np. kampania
  2022 pod Krakowem), K2 (cel EPSG:5514).

### B4. Pobieranie listy arkuszy (H-06, H-11)

- `docs/integrations/KARTOGRAF.md` §8.4 (`:530-547`): od 0.7.0
  `manager.download_sheets(sheets)` — porazki zbierane w
  `manager.last_result.failed`; braki danych (`NoCoverageError`) sa w `failed`
  i dodatkowo w `last_result.no_coverage` (podzbior `failed`) — petla
  `download_sheet` przerywa sie na pierwszym wyjatku. Przyklad
  z `output_dir="./data/nmt/"` da w 0.7.0 podwojne `nmt` w sciezce (patrz A1).
- `docs/PROGRESS.md:1385` (obejscie przez wlasna sesje i `MetadataCache`):
  dla wycinka `download_pl_cutout` nie przyjmuje providera — z wlasna
  sesja/cache trzeba 3 krokow (`run_pl_cutout(provider=GugikProvider(session=...,
  cache=...))`). W Kartografie `MetadataCache` nie jest podlaczony w zadnym
  torze PL (znany blad **N6**).

### B5. ADR-057 i backlog upstreamu (H-07, H-08)

- `docs/DECISIONS.md:1236, 1239-1241, 1248-1249` (ADR-057): publicznym API
  rastra NMT w 0.7.0 jest `download_pl_cutout` (eksport w `kartograf`, decyzja R3
  Kartografa pod Hydrograf); `mosaic_and_crop` to wewnetrzny krok
  w `kartograf.transport.mosaic`, nie w `kartograf.__all__`.
  `discover_teryts_for_bbox()` to funkcja Hydrografu
  (`backend/scripts/download_landcover.py`) i propozycja do upstreamu —
  w Kartografie nie istnieje (ani w kodzie, ani w backlogu), wiec zdanie
  o "nowszych publicznych API (`discover_teryts_for_bbox`, `mosaic_and_crop`)"
  jest nieprecyzyjne.
- `docs/PROGRESS.md:1383`: "Upstream do Kartografa (przy 0.7.0):
  `download_pl_cutout` (juz na develop Kartografa) zamiast wlasnego
  mozaikowania; `discover_teryts_for_bbox()` — do zgloszenia jako propozycja".

## C. Znane bledy Kartografa 0.7.0-dev istotne dla Hydrografa

Pelna lista i status: Kartograf `docs/PROGRESS.md`, "Znane bledy (testy na zywo
2026-09-29)" i Backlog "Do naprawy". Najwazniejsze dla przeplywow Hydrografa:

- **K3** — starsza kampania arkusza po chwilowym bledzie nowszej warstwy
  skorowidza (utrwalona w cache); to blad (1) z sesji 93 Hydrografu.
- **K4** — wybor pliku arkusza: pierwszy URL zawierajacy godlo (w skorowidzu
  1 m bywaja pliki 0,5 m; w warstwie zbiorczej wygrywa najstarsza kampania —
  stwierdzone dla 1 m).
- **S1** — zapytania skorowidza bez ponowien i wspolnej sesji (obejscie
  Hydrografu: wlasna `requests.Session`).
- **S5** — arkusze 5 m nie zawsze leza na siatce `5k + 2,5 m` (kampania 2022 pod
  Krakowem: kazdy arkusz inna faza) — warto sprawdzic wlasna mozaike VRT
  Hydrografu na takim obszarze.
- **N6** — `MetadataCache` niepodlaczony w torach PL Kartografa.
- **K2** — przy danych CZ: tresc po reprojekcji przesunieta do ~5 m (operacja
  S-JTSK slowacka).
- **K1** — LAZ (Hydrograf dzis nie uzywa): kafle z innego miejsca.

## D. Obserwacje poboczne (nie z fal Kartografa)

- **S-1** `Hydrograf/docs/SCOPE.md:431` — "Zrodlo: PIG (Panstwowy Instytut
  Geologiczny) via Kartograf v0.6.1" dla HSG; Kartograf liczy HSG z SoilGrids
  (ISRIC) — `HSGCalculator` (tak tez opisuje `KARTOGRAF.md` §13). Poprawka:
  "Zrodlo: SoilGrids (ISRIC) via Kartograf `HSGCalculator` (v0.6.1)".
- **S-2** `Hydrograf/README.md:96`, `docs/IMPLEMENTATION_PROMPT.md:47`,
  `docs/CROSS_PROJECT_ANALYSIS.md:297` odsylaja do
  `docs/integrations/KARTOGRAF_INTEGRATION.md`, ktorego na dysku nie ma (jest
  `docs/integrations/KARTOGRAF.md`, untracked; `CLAUDE.md` wskazuje juz nowa
  nazwe) — czesc niezacommitowanej reorganizacji uzytkownika.
