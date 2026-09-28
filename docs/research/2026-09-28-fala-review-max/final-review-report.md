# Finalny review fali naprawczej 0bf3d9f..fa1f771 (Kartograf, develop)

**Data:** 2026-09-28  
**Reviewer:** fable (finalny review calej galezi, wg `FINAL-REVIEW-BRIEF.md`)  
**Zakres:** 22 commity (`git log --oneline 0bf3d9f..fa1f771`), 28 plikow, +3937/-828.  
**Metoda:** COMMON-CONTEXT (R1-R6, fakty 1-11) -> spec review max -> plan (Kontekst,
Przeglad zadan, Poza zakresem, Review Focus, Zad. 17, Zakonczenie) -> pakiet diffu
`review-final-0bf3d9f..fa1f771.diff` czytany **w 9 partiach** (docs 58-1778, kod
1778-4618, testy 4618-7649; dwie partie przez pliki persisted) + zywy kod wszystkich
modulow produkcyjnych toru wycinka (`cutout.py`, `mosaic.py`, `manager.py`,
`gugik.py`, `download_cmd.py`, `storage.py`, `descriptor.py`, `raster.py`,
`cuzk/client.py`, `core/geometry.py`) -> ledger + raporty Zad. 10 i 17 -> dwie
kontrolowane mutacje (przywrocone, `git status --short` pusty) -> 74 testy CZ
uruchomione osobno. Hydrograf czytany wylacznie do odczytu (grep + 3 pliki).

---

### Strengths

- **Podzial biblioteka/CLI jest czysty i spojny.** `download/cutout.py` nie ma
  `print`/argparse; `_download_pl_cutout` (`cli/download_cmd.py:948-1059`) to
  faktycznie nakladka: prepare -> skrot -> select -> komunikaty -> run -> Warning.
  Kolejnosc krokow w `run_pl_cutout` (kontrola providera -> skrot -> dysk ->
  `download_sheets` -> klasyfikacja R5 -> `_reject_pl2000_sheets` -> mozaika
  (sort, snap, VRT, kompresja tylko przy warpie) -> warp -> sidecar -> sprzatanie)
  jest identyczna dla `download_pl_cutout` i dla CLI; regula 5m => EVRF2007
  wchodzi w obu wejsciach przez providera (fabryka), a `_require_matching_provider`
  zamyka rozjazd segmentu.
- **R5 jest strukturalnie poprawne.** Jedyny `raise NoCoverageError` w repo
  (`gugik.py:590`) jest osiagalny wylacznie przy `transport_errors == 0`; manager
  trzyma `no_coverage` jako podzbior `failed` w OBU galeziach (sekwencyjnej
  i rownoleglej — testy parametryzowane `workers=[1, 4]`, a rownolegla jest
  domyslna w CLI); `fatal = failed - no_coverage` w `run_pl_cutout:584`.
- **Tor CZ realnie nietkniety.** `git diff --stat -- kartograf/providers/cuzk
  kartograf/transform/raster.py` pusty; wywolanie `client.py:182` bez nowych
  parametrow trafia w sciezke `wrap=False, snap=False`, ktorej semantyka jest
  identyczna ze stara (patrz C); 74 testy CZ zielone.
- **Zero shimow.** `_prepare_pl_cutout`, `_build_pl_cutout`, `_finalize_pl_cutout`,
  `_PlCutout`, `_laz_uklad`, `_PL_*` zniknely z kodu i testow (grep czysty poza
  nazwa historyczna w ADR-027 i datowanym PROGRESS).
- **Testy w wiekszosci bronia zachowania, nie mockow**: siatka arkuszy na
  syntetycznych arkuszach z narozami `k + 0,5` (fakt 1), rampa 5514 bit w bit
  z niezaleznym `warp_to_grid`, realny `.prj` Hydrografu (P-01/P-21), obie
  kolejnosci wejsc (P-07), kontrola dysku PRZED `download_sheets`, `RasterioIOError`
  w CLI -> kod 1, pogranicze `--country auto` z arkuszem bez danych -> dwa wycinki
  i kod 0. E2E offline na realnych arkuszach 5 m odtworzone niezaleznie (Zad. 17).
- **Dokumentacja tym razem w zdecydowanej wiekszosci mowi prawde**: ~25 twierdzen
  sprawdzonych na kodzie (lista w D) — zadne nie opisuje zachowania odwrotnego.

---

### Issues

#### Critical

Brak.

#### Important

**I-1. Wiazanie `--force` (i `--workers`) z CLI do `run_pl_cutout` nie jest bronione
zadnym testem — mutacja przechodzi 312/312, a `--force` na istniejacym wycinku
staje sie cichym no-opem.**  
`kartograf/cli/download_cmd.py:1035-1036` (`max_workers=getattr(args, "workers", 4)`,
`force=args.force`); harness CLI `tests/test_pl_cutout.py::_pl_args` ma na stale
`force=False, workers=1`, a jedyny test `force=True` (`TestLibraryApi::
test_download_pl_cutout_end_to_end_skip_and_force`) omija CLI.  
Dlaczego to wazne: `run_pl_cutout` ma WLASNY skrot `if not force and
target_path.exists(): return skipped` (`cutout.py:554`). Gdy CLI przestanie
przekazywac `force`, jego wlasny skrot (`:990`) przepuszcza `--force`, a biblioteka
zwraca `skipped=True` i CLI drukuje `Downloaded to <stary plik>` — dokladnie
scenariusz, ktory CHANGELOG nakazuje uzytkownikom po tej fali ("wycinki zbudowane
wczesniej przebuduj z `--force`"). Zmierzone mutacja M1 (sekcja Mutacje): rc=0,
`download_sheets` niewolane, plik 17 B nietkniety, 312 testow PASS.  
Naprawa: jeden test CLI w `TestDownloadPlBboxCutout` — istniejacy plik wyniku
z dummy trescia + `_pl_args(tmp_path, force=True)`; asercje: tresc pliku sie
zmienila, `manager.download_sheets.call_args.kwargs["skip_existing"] is False`
(to broni tez `skip_existing = not force`, ktore CHANGELOG opisuje jako "`--force`
pobiera ponownie takze arkusze"). Analogicznie jedna asercja
`self.dm.call_args.kwargs["max_workers"] == args.workers` z `workers=3` (M2).

**I-2. DEFERRED-LOAD-BEARING z ledgera potwierdzony na kodzie: odpowiedz HTTP 2xx
bez URL (OGC `ServiceExceptionReport`, strona bledu proxy z 200) liczy sie jako
"warstwa odpowiedziala i nie ma arkusza" -> `NoCoverageError` -> pod R5 trwala
dziura nodata w pliku pomijanym potem jako istniejacy.**  
`kartograf/providers/pl/gugik.py:537-563, 571-596`: po `raise_for_status()` jedynym
kryterium jest `re.findall(r'url:"(https://opendata[^"]+\.asc)"', response.text)`;
brak trafienia = brak pokrycia na tej warstwie. `NoCoverageError` pada, gdy
WSZYSTKIE warstwy (3-4) tak odpowiedza. "Czysta pusta" odpowiedz w fixturach to
syntetyczne `<html><body>No data</body></html>` (`tests/test_gugik_provider.py:474`)
— w repo, docs/research i pamieci NIE ma zapisu, jak naprawde wyglada pusta
odpowiedz GetFeatureInfo GUGiK ani z jakim `Content-Type`.  
Ocena: **Important, do naprawy przed checklista live**, nie Critical — bo (1) nie
ma dowodu, ze ta usluga odpowiada bledem z kodem 200 (typowe 5xx/404 lapie
`raise_for_status`), (2) skutek nie jest cichy: CLI `Warning:` wymienia arkusze,
sidecar/wynik niosa `missing_sheets`, (3) awaria calkowita (wszystkie arkusze bez
URL) konczy sie `ValidationError` i kodem 1. Ale przy czesciowo zapelnionym cache
(Hydrograf!) jeden przebieg w czasie degradacji uslugi buduje wycinek z dziurami,
ktory kolejne przebiegi pomijaja — to jest wlasnie klasa bledu, ktora R5 mial
wykluczyc ("chwilowy blad nigdy nie zostawia trwalej dziury").  
Wlasciwa straz (tania, bez ryzyka dla R5): po `raise_for_status()`
```python
text = response.text
if "ServiceException" in text or "ExceptionReport" in text:
    transport_errors += 1
    last_error = DownloadError(f"warstwa {layer}: OGC exception w odpowiedzi 2xx")
    logger.warning(...)
    continue
```
+ opcjonalnie `Content-Type` zawierajacy `xml`/`json` (GetFeatureInfo zada
`text/html`) jako blad transportu. NIE robic kontroli pozytywnej ("brak `<html`
= blad") przed checklista live — pusta odpowiedz moze byc pustym body/`text/plain`
i wtedy KAZDY brak pokrycia stalby sie kodem 1 (odwrotny blad, tez lamiacy R5).
Test: fixture `<ServiceExceptionReport>...` z `status_code=200` na wszystkich
warstwach -> `DownloadError` i `not isinstance(..., NoCoverageError)`. Checklista
live: zapisac realne body + `Content-Type` pustej odpowiedzi dla arkusza nad
morzem i po stronie czeskiej (juz jest jako note Zad. 10) i wtedy ewentualnie
zaostrzyc do kontroli pozytywnej.

#### Minor

- **m-1.** `cli/download_cmd.py:1035` — `--workers` nie dociera do zadnego testu
  toru wycinka (mutacja M2: `max_workers=1` przechodzi 312/312); regresja bylaby
  wylacznie wydajnosciowa (4x wolniej). Naprawa: asercja z I-1.
- **m-2.** `download/cutout.py:125` — `_bbox_to_2180` porownuje `bbox.crs in
  _CZ_CRS` doslownie; wywolanie biblioteczne z `"epsg:5514"` idzie po cichu
  niepinowanym transformerem (obejscie ADR-024 w NOWYM publicznym API), podczas gdy
  CLI (`wkid()`) jest na to odporne. 1 linia: `bbox.crs.upper()` albo `wkid()`.
  (ledger Zad. 8)
- **m-3.** `download/cutout.py:494` — `estimate_pl_cutout_bytes` sprawdza cache po
  stalym `".asc"`, a manager po `provider.default_extension`; dla wstrzyknietego
  providera z innym rozszerzeniem arkusze z cache licza sie jako "do pobrania"
  (zawyzenie moze odrzucic zadanie, ktore sie miesci). Przekazac rozszerzenie
  providera albo wziac je z deskryptora.
- **m-4.** `transport/mosaic.py:256-264` + `download/cutout.py` — arkusz spoza
  siatki wiekszosci jest przepisywany najblizszym sasiadem (przesuniecie do 0,5 px)
  wylacznie z `logger.warning` (lastResort na stderr); CLI nie daje `Warning:`,
  a sidecar nadal deklaruje `transform: null` i "wartosci 1:1". Dla 5 m nieosiagalne
  (fakt 1), dla 1 m — checklista live (f). Jesli live pokaze mieszane fazy
  kampanii 1 m: `extra.off_grid_sheets` w sidecarze + `Warning:` w CLI.
- **m-5.** `download/cutout.py:632` — `download_pl_cutout` nie przyjmuje
  `provider=`/`storage=`/`session=`/`cache=`; Hydrograf (nazwany konsument) i E2E
  Zad. 17 musza skladac trzy kroki recznie, a `download_pl_cutout` (regula 5m,
  wczesny skrot) ma pokrycie tylko jednostkowe. Addytywny parametr `provider=`
  (z ta sama kontrola `_require_matching_provider`) domknalby to.
- **m-6.** `download/manager.py:122-126, 299-302, 374-377` — trzy docstringi
  twierdza, ze `last_result` ustawia "only `download_hierarchy`"; od Zad. 7 ustawia
  je tez `download_sheets` (publiczne API, ktore `run_pl_cutout` na tym opiera).
  (ledger Zad. 7)
- **m-7.** `providers/pl/gugik.py:406-409` — `GugikProvider.download()` w `Raises`
  wymienia tylko `DownloadError`; `NoCoverageError` (podklasa, nosna dla R5) jest
  udokumentowana tylko w `_get_opendata_url`. (ledger Zad. 6)
- **m-8.** `CLAUDE.md:130,133`, `README.md:355,358` — komendy testowe bez
  `-m "not live"` odpalaja 8 testow sieciowych (P-16 ustalil bramke offline;
  CLAUDE.md steruje kazda przyszla sesja). (ledger Zad. 17)
- **m-9.** `docs/ARCHITECTURE.md` (4.3) — trzy nieprecyzje z ledgera Zad. 17
  potwierdzone na kodzie: (a) "zamienia KAZDY wyjatek przygotowania, selekcji ...
  na kod 1" — `prepare` lapie tylko `TransformError`/`ValidationError`, `select`
  tylko `ValidationError` (`download_cmd.py:985-989, 1003-1005`), reszta idzie do
  bariery `main()`; (b) cytat E2E (e) pod "Nieudana budowa a poprzedni wynik"
  dotyczy porazki POBRANIA (rzuca przed `build_pl_cutout`) — dowodem jest
  `test_failed_build_keeps_previous_result`; (c) "< 0,5 px" -> "do 0,5 px"
  (`round` half-to-even w `warp_to_grid:99-100`), "0 z 80 601" tylko dla bboxa
  calkowitego (ulamkowy: 79 799).
- **m-10.** `download/cutout.py:175,126` — tor PL importuje generyczny
  `bbox_to_crs` z `providers/cuzk/dmr.py` (zaleznosc `download -> providers.cuzk`,
  graf w ARCHITECTURE 2 tego nie pokazuje: "download -> providers" jest prawda,
  ale to ZAMROZONY modul CZ). Przeniesienie `bbox_to_crs` do `transform/` = etap 2
  (dotyka CZ), teraz tylko zdanie w ARCHITECTURE.
- **m-11.** `download/manager.py:512,582` + CLI — kazdy arkusz bez danych daje
  linie `No data for <godlo>: ...` (WARNING przez lastResort na stderr) obok
  zbiorczego `Warning:` CLI; na wybrzezu to dziesiatki linii. Kosmetyczne;
  proponowany ruling: zaakceptowac (tryby listy arkuszy potrzebuja tej linii).
  (ledger Zad. 10)

---

### Nazwane ryzyka A-G

**A. Defekty miedzyzadaniowe w torze wycinka PL.** Sprawdzone: kolejnosc krokow
w `run_pl_cutout` (`cutout.py:552-629`), `download_pl_cutout` (`:654-683`)
i `_download_pl_cutout` (`download_cmd.py:972-1059`) — spojna (opis w Strengths);
obie drogi podaja `prepare_pl_cutout` pion FAKTYCZNY providera; selekcja dostaje
`bbox_source_2180 +/- 1 px` (bbox i suma R-01), a crop `bbox_source_2180`;
`_reject_pl2000_sheets` przed `mkdir`; kompresja tylko przy `pinned`;
`tiled=False` przez `setdefault` przy owijaniu, nadpisane jawnymi kaflami 512
przy warpie; sidecar po budowie; `prune_empty_dirs` przy KAZDYM wyjatku budowy.
Wyjatki: biblioteka — `ValidationError`/`TransformError` (prepare, select),
`DownloadError` (fatal), `ValidationError` (zaden arkusz), reszta przezroczysta;
CLI — `TransformError`/`ValidationError` z prepare/select -> kod 1,
`except Exception` wokol `run_pl_cutout` -> kod 1 (test `RasterioIOError`),
`--country auto` czesciowy sukces zachowany (`test_border_pl_sheet_without_data_
still_gives_both_cutouts`). Wynik: **brak defektu kodu**; luka testowa I-1/m-1.

**B. R5 end-to-end.** Sprawdzone: jedyne miejsce `raise NoCoverageError`
(`gugik.py:590`) i warunki dojscia: URL z cache -> return; brak endpointu/warstw ->
`DownloadError`; petla warstw: `RequestException` -> `transport_errors += 1`;
2xx z URL -> return (z fallbackiem "inny arkusz" + warning); 2xx bez URL -> nic;
po petli: wszystkie transport -> `DownloadError`, czesc transport ->
`DownloadError` "niepewny", zero transport i zero URL -> `NoCoverageError`.
Manager: `except NoCoverageError` przed `except DownloadError` (poprawna
kolejnosc podklas) w obu galeziach; "unexpected exception" w puli -> `failed`
bez `no_coverage` -> w wycinku fatalne (kierunek bezpieczny). Wynik: definicja
"wszystkie warstwy odpowiedzialy" znaczy "HTTP 2xx z dowolnym body" — **I-2**.
Druga znana luka (fallback URL innego arkusza tego samego ukladu -> dziura bez
wpisu w `missing_sheets`) jest udokumentowana w ARCHITECTURE 4.3 krok 4 i w
checkliscie live — zostaje tam (patrz Declined).

**C. Wspolny `mosaic_and_crop` a tor CZ.** Sprawdzone diffem starej i nowej
funkcji dla wywolania `client.py:182` (`mosaic_and_crop(tile_paths, bbox,
output_path, nodata=no_data)`: `assign_crs=None`, `dtype=None`, `snap=False`):
metadane czytane sekwencyjnie zamiast `ExitStack` (te same pola), kontrola CRS
`{str(m["crs"])}` = stara `{str(src.crs)}`, ta sama kontrola rozdzielczosci
i kolejnosc, `bounds` = bbox bez zmian, `merge(paths, ...)` zamiast datasetow
(fakt 3: bit w bit), `dst_kwds=kwds or None` identyczne, `setdefault(driver/
tiled)` wylacznie pod `if wrap`. Uruchomione `tests/test_cuzk_client.py
tests/test_cuzk_dmr.py`: 74 passed. Wynik: **identyczne zachowanie**; jedyna
zmiana dla CZ to leniwe zrodla (zamierzona).

**D. Kod vs dokumentacja.** Zweryfikowane na kodzie (wszystkie PRAWDZIWE):
CLAUDE.md — drzewo modulow (`cutout.py`, `NoCoverageError`, `download_sheets`,
snap/VRT), `LazTile.uklad` jako wyjatek reguly `pl_1992/pl_2000`, caly punkt
`--target-crs` (API, R5, siatka, VRT, PL-2000 = blad, dysk, `Info:` >= 1 GiB,
brak sumy i zapasu dla `--geometry`+2180, `os.replace`, tor CZ kasuje);
ARCHITECTURE — graf importow (cutout importuje `transform.crs` przy imporcie,
`transport`/`raster` leniwie; CLI z `transform` bierze tylko `TransformError`),
3.1 `{uklad}`, 3.2 (`request` = `bbox_target`, `extra.missing_sheets`), 3.3 pkt 3,
4.3 kroki 1-8 (walidacje i kolejnosc skrotu/kontroli providera, `WARP_MARGIN_PX
= 4`, +1 px, R-01, `skip_existing = not force`, INFO/WARNING/`Warning:` do 10,
`_reject_pl2000_sheets` `>= 1 000 000`, tolerancja 1e-6, siatka wiekszosci
z remisem "pierwsze" (`Counter.most_common` stabilny), `<NoDataValue>` = zrodlo,
`tiled=False`, sortowanie, leniwe zrodla, kompresja/BIGTIFF/512 tylko przy
warpie, `estimated_bytes` z `bbox_target`, 5,5 B, probe do istniejacego
katalogu, `prune_empty_dirs` w obu torach), 4.7 LAZ; CHANGELOG — Added/Changed/
Fixed (w tym `--force` z tanszym wariantem, "brak pokrycia niepewny", `parent_
request.bbox_crs` = uklad pliku, `resolve_subdir('')`), Tests 1854/92,9 %;
ADR-027 (korekta `--force`, R-01 w obu trybach, uzupelnienia R5/R1/R3);
README (sygnatura i przyklad `download_pl_cutout`, `result.missing_sheets`,
wiersz `extra.missing_sheets`, kto pisze sidecary, 1854+8); SCOPE (2.10 eksporty
= `__all__`, 3.2 R5, 3.1 etap 2). Rozjazdy: wylacznie nieprecyzje m-8/m-9 (zadna
nie opisuje odwrotnosci kodu); grep starych nazw w docs czysty.

**E. Global Constraints.** `git diff 0bf3d9f..fa1f771 --stat -- kartograf/
providers/cuzk kartograf/transform/raster.py` -> pusty. Shimy: grep
`_prepare_pl_cutout|_build_pl_cutout|_finalize_pl_cutout|_PlCutout|_laz_uklad|
_PL_NODATA|_PL_PIXEL|_RESOLUTION_SUBDIRS|_PRODUCT_SUBDIRS` w `kartograf/`,
`tests/` = 0 trafien (docs: tylko nazwa historyczna w ADR-027 i datowany
PROGRESS). Semantyka: zapis atomowy bez kasowania poprzedniego wyniku
(`build_pl_cutout` + `warp_to_grid`, test `test_failed_build_keeps_previous_
result`), `--country auto` czesciowy sukces (test pogranicza), kod 1 bez
tracebacku (`except Exception` + bariera `main()`), tryby bez `--target-crs`
nietkniete (`_download_godlo_list` bez zmian, `test_without_target_crs_
behaviour_unchanged`). CHANGELOG: wpis "przebuduj z `--force`" obecny
(`docs/CHANGELOG.md:614-620`) — a I-1 pokazuje, ze sam mechanizm `--force` w CLI
nie ma straznika.

**F. Konsument Hydrograf (tylko odczyt).** Importy: `BBox`, `SheetParser`,
`find_sheets_for_bbox`, `find_sheets_for_geometry`, `DownloadManager`,
`GugikProvider`, `LandCoverManager`, `HSGCalculator`, `Bdot10kProvider`
(`backend/scripts/download_dem.py:89,227,376`, `utils/sheet_lookup.py:11`,
`scripts/bootstrap.py`, `core/cn_calculator.py`). Uzycie NMT: `GugikProvider(
resolution=)` + `DownloadManager(output_dir=, provider=, resolution=)` +
`manager.download_sheet(sheet, skip_existing=)` w petli z `except Exception`
(`download_dem.py:101-127`). Trafienia na nazwy zmienione/usuniete w fali
(`_laz_uklad`, `_PL_*`, `_*_SUBDIRS`, `mosaic_and_crop`, `last_result`,
`expand_sheets`, tresc "No NMT ... data available"): **brak**. Zmiany zachowania
widoczne dla Hydrografu: `find_sheets_for_bbox` moze zwrocic WIECEJ arkuszy dla
szerokich bboxow przecinajacych 19°E (naprawa faktu 8; testy Hydrografu maja
wpisane na stale wyniki przy 16,9°E — nieobjete); `NoCoverageError` jest podklasa
`DownloadError` z niezmieniona trescia (KARTOGRAF.md:423 "jesli zadna warstwa nie
zwroci pliku — DownloadError" pozostaje prawda). Wynik: **brak trafien**.

**G. Testy.** Punkty kompozycji z A i ich obrona: kontrola dysku przed siecia
(`test_disk_check_blocks_before_download` — `download_sheets.assert_not_called`),
klasyfikacja R5 w puli watkow (`test_no_coverage_is_subset_of_failed[4]`),
wyjatek spoza Kartografa w CLI (`test_build_error_returns_1`), 5m+KRON86 w CLI
(`test_5m_kron86_...`, l. 685-697), obwiednia geometrii CZ przypieta operacja
(roznica 1,155 m lapana `abs=1e-6`), suma R-01 (`test_geometry_target_5514_
covers_whole_envelope`), sortowanie/VRT/snap na realnych fazach. Luki, ktore
REALNIE przepuszczaja regresje (udowodnione mutacja): I-1 (`--force`), m-1
(`--workers`). Luki teoretyczne pominiete: brak testu, ze `--geometry`+2180 NIE
robi sumy (mutacja zmienialaby tylko zbior arkuszy, nie wynik).

---

### Triaz ledgera

Format: `<zadanie>: <skrot> -> NAPRAW TERAZ | ZOSTAW (backlog) | JUZ NIEAKTUALNE — powod`.

- Task 3: tolerancja `floor(q + tol)` bez testu lustrzanego + remis bez testu -> ZOSTAW (backlog) — `test_snap_keeps_bbox_already_on_grid` broni gornej krawedzi, dolna to symetryczny kod; remis dla GUGiK nieosiagalny.
- Task 3: `_snap_outward` nie odrzuca zrodla odbitego -> ZOSTAW (backlog) — nieosiagalne dla obu torow.
- Task 4: `_same_projection` ~25 ms/zrodlo dla WKT1_ESRI -> ZOSTAW (backlog) — realny `.prj` Hydrografu 0,28 ms; `lru_cache` po tekscie WKT gdy pojawia sie inny konsument.
- Task 4: dziedziczenie kafli VRT (RasterBlockError) -> JUZ NIEAKTUALNE — zamkniete w Zad. 9 (`kwds.setdefault("tiled", False)`, 3 testy).
- Task 4: komentarz testu fd (`test_transport_mosaic.py:417-419`) -> ZOSTAW (backlog) — kosmetyka testu.
- Task 4: docstring `mosaic.py:174` "maskowanie jak bez owijania" -> ZOSTAW (backlog) — prawda dla nodata; wewnetrzne pasma maski nie wystepuja w ASC; jedno zdanie przy okazji.
- Task 4: WKT1 z `TOWGS84[0,...]` odrzucany -> ZOSTAW (backlog) — bez realnej probki; trzeci fallback `to_epsg()` po pojawieniu sie przypadku.
- Task 4: brak testu owijania+snap na realnych wspolrzednych -> JUZ NIEAKTUALNE — `TestSheetGrid` (PUWG-92, fazy 0,5) + E2E Zad. 17.
- Task 6: docstring `GugikProvider.download()` bez `NoCoverageError` -> NAPRAW TERAZ — publiczne API, R5 sie na tym opiera, 1 linia (m-7).
- Task 7: docstring `DownloadManager` "`last_result` set only by `download_hierarchy`" -> NAPRAW TERAZ — falszywe od Zad. 7 w 3 miejscach (`manager.py:122-126, 299-302, 374-377`), publiczne API (m-6).
- Task 7: `download_sheets` parsuje kazdy lisc dwa razy -> ZOSTAW (backlog) — nieszkodliwe.
- Task 8: `_CZ_CRS` porownuje stringi doslownie -> NAPRAW TERAZ — 1 linia zamyka ciche obejscie ADR-024 w nowym publicznym API (m-2).
- Task 8: duplikacja walidacji `download_pl_cutout` vs `prepare_pl_cutout` (plan-mandated) -> ZOSTAW (backlog) — celowe fail-fast przed fabryka providera.
- Task 8: `run_pl_cutout` nie waliduje wstrzyknietej `storage` -> ZOSTAW (backlog) — CLI buduje ja z tego samego providera; biblioteka: kandydat razem z m-5.
- Task 9: CHANGELOG bez kwalifikatora "(tryb bbox i suma R-01)" -> JUZ NIEAKTUALNE — wpisany w Zad. 17 (`CHANGELOG.md:330`).
- Task 9: komunikat `ValidationError` PL-2000 wspomina flagi CLI -> ZOSTAW (backlog) — remedium jest uzyteczne dla obu odbiorcow.
- Task 9: kolejnosc "odrzut PL-2000 przed mkdir" bez testu -> ZOSTAW (backlog) — skutek (brak pustego `bbox/`) broni `prune_empty_dirs` + `test_failed_build_leaves_no_empty_bbox_dir`.
- Task 10: podwojne linie stderr (per arkusz WARNING + zbiorczy `Warning:`) -> ZOSTAW (backlog) — proponowany ruling: zaakceptowac; tryby listy arkuszy potrzebuja linii per arkusz (m-11).
- Task 10: DEFERRED-LOAD-BEARING (2xx bez URL = `NoCoverageError`) -> NAPRAW TERAZ — I-2: straz negatywna (`ServiceException`/`ExceptionReport` w body = blad transportu) + test + pozycja checklisty live.
- Task 10: per-arkusz `logger.warning` -> INFO (ruling w fali finalnej) -> ZOSTAW (backlog) — ruling: zostaje WARNING (ten sam manager obsluguje tryby, gdzie brak danych JEST bledem).
- Task 10: `run_pl_cutout` z pustym `PlCutoutSheets` obwinia GUGiK; docstring CLI o kodzie 1 -> ZOSTAW (backlog) — nieosiagalne z CLI/`select_pl_cutout_sheets`.
- Task 10: brak testu `parent_request` + `missing_sheets` naraz; brak asercji katalogu w `test_all_sheets_without_data_is_an_error` -> ZOSTAW (backlog) — `extra` skladane ze slownika, oba klucze niezalezne; katalog broni `prune_empty_dirs`.
- Task 11: `grid_shape`/`estimated_bytes` z nieprzyciagnietego `bbox_target` -> ZOSTAW (backlog) — < 1 px, dolne oszacowanie z definicji.
- Task 12 (Ruling, Important plan-mandated, odlozone do fali finalnej): duplikacja idiomu obwiedni w `_geometry_envelope` / `_resolve_cz_geometry_bbox` -> ZOSTAW (backlog) — bez zmiany zachowania; wspolny helper przy etapie 2 (tor CZ wtedy odmrozony).
- Task 12: `to_epsg()` dla ESRI `.prj` Krovaka moze nie dac 5514 -> ZOSTAW (backlog) — to samo ograniczenie co `wkid()`; potrzebna realna probka `.prj`.
- Task 12: `--geometry` czyta CRS pliku dwa razy -> ZOSTAW (backlog) — pomijalne.
- Task 13: `prune_empty_dirs` w dwoch galeziach `except` (`_cz_download_bbox`) -> ZOSTAW (backlog) — plan-mandated, trywialne, galezie roznia sie obsluga.
- Task 16: galaz passthrough rozdzielczosci w `FileStorage._subdir` nieosiagalna -> ZOSTAW (backlog) — sprzed fali, martwy kod bez skutku.
- Task 17: `pytest tests/` w CLAUDE.md/README odpala 8 testow live -> NAPRAW TERAZ — CLAUDE.md steruje kazda sesja; 4 linie (m-8).
- Task 17 (controller, Zakonczenie): PROGRESS (E2E, checklista (f)-(j), liczby 1854/92,9 %, nieaktualne :720-721) -> NAPRAW TERAZ — to zamkniecie fali wg planu.
- Task 17: ARCHITECTURE.md:596-598 cytat E2E (e) nic nie dowodzi -> NAPRAW TERAZ — zamienic na `test_failed_build_keeps_previous_result` (m-9b).
- Task 17: ARCHITECTURE.md:458/:473/:400 rodziny wyjatkow, "KAZDY wyjatek" -> NAPRAW TERAZ — jedno-dwa slowa, "docs lie" to najczestszy blad projektu (m-9a).
- Task 17: ARCHITECTURE.md:283/:556 "< 0,5 px" -> "do 0,5 px"; :543 80 601 vs 79 799 -> NAPRAW TERAZ — liczby (m-9c).
- Task 17 (note, backlog): skala resamplingu GDAL `XSCALE/YSCALE` -> ZOSTAW (backlog) — etap 2, dotyczy tez zamrozonego CZ.
- Task 17 (note): E2E przez prepare/select/run, bo `download_pl_cutout` nie ma `provider=` -> ZOSTAW (backlog) — m-5 (addytywny parametr) w nastepnej fali API.
- Task 8/10 (note for Zad. 17: stare nazwy w ARCHITECTURE/DECISIONS, stale zdania ARCHITECTURE:386/SCOPE:339) -> JUZ NIEAKTUALNE — wykonane w Zad. 17 (grep czysty).
- Task 10 (note, checklista live: fallback URL innego arkusza; czysta pusta odpowiedz GetFeatureInfo) -> ZOSTAW (checklista live) — druga pozycja to warunek wstepny I-2 (zapisac body + `Content-Type`).

**NAPRAW TERAZ: 9 pozycji** (Task 6, Task 7, Task 8 `_CZ_CRS`, Task 10 DEFERRED-LOAD-BEARING, Task 17 x5).

---

### Mutacje

Kazda w drzewie roboczym po odczycie zywego kodu; przywrocenie
`git checkout -- kartograf/cli/download_cmd.py`; `git status --short` pusty po
kazdej i na koncu. Komenda testow: `.venv/bin/python -m pytest
tests/test_pl_cutout.py tests/test_cli.py -q -m "not live"` (312 testow).

| # | Mutacja (kod produkcyjny) | Wynik testow | Dowod zachowania | Wniosek |
|---|---|---|---|---|
| M1 | `cli/download_cmd.py:1036` `force=args.force,` -> `force=False,` | **312 passed** | skrypt `scratchpad/demo_force.py` (harness `_run` z `force=True`, istniejacy plik 17 B): baseline `rc=0 download_sheets_called=True rebuilt=True size=57980`; pod M1 `rc=0 download_sheets_called=False rebuilt=False size=17` | wiazanie `--force` CLI->biblioteka niebronione; `--force` = cichy no-op, `Downloaded to` wypisane (I-1) |
| M2 | `cli/download_cmd.py:1035` `max_workers=getattr(args, "workers", 4),` -> `max_workers=1,` | **312 passed** | harness ma `workers=1`, `self.dm.call_args` sprawdzany tylko dla `sidecar_extra` | `--workers` w torze wycinka niebronione (m-1) |

Po przywroceniu: `pytest tests/test_pl_cutout.py -k "TestDownloadPlBboxCutout or
TestLibraryApi"` -> 21 passed; `git status --short` -> pusty.

Mutacje rozwazone i odrzucone, bo test je zabija (sprawdzone lektura testu, nie
uruchomione): zawezenie `except Exception` w `_download_pl_cutout`
(`test_build_error_returns_1`, `RasterioIOError`); przesuniecie kontroli dysku za
`download_sheets` (`test_disk_check_blocks_before_download`); surowa flaga
`args.vertical_crs` zamiast pionu providera przy 5m+KRON86 (test l. 685-697);
etykieta WKT zamiast `EPSG:<kod>` w `_geometry_envelope`
(`test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl`,
`abs=1e-6`); usuniecie `no_coverage` z galezi rownoleglej managera
(`test_no_coverage_is_subset_of_failed[4]`); brak `uklad=tile.uklad` w LAZ
(`test_laz_writes_sidecar_next_to_tile`, literalny segment).

---

### Declined to judge

- Fallback "pierwszy znaleziony URL" w `_get_opendata_url:554-563` dla arkusza
  tego samego ukladu: plik pod cudzym godlem laduje w swoim miejscu, obszar
  zadanego arkusza = nodata bez wpisu w `missing_sheets` — zachowanie sprzed fali,
  jawnie opisane w ARCHITECTURE 4.3 krok 4 i w checkliscie live (ledger Zad. 10).
- `bbox_to_crs` (generyczny pinned transform bboxa) zyje w zamrozonym
  `providers/cuzk/dmr.py` i jest importowany przez tor PL — sprzed fali; ruch
  = etap 2 (m-10 tylko jako zdanie w docs).
- Pobranie ASC (`_download_with_retry`/`transport/http.py`) bez kontroli
  `Content-Type`: strona bledu HTML z 200 zapisze sie jako `.asc`, mozaika padnie
  (kod 1, nie dziura), ale uszkodzony arkusz zostaje w cache i jest pomijany jako
  istniejacy az do recznego usuniecia — poza fala (transport nietkniety); warto
  jako pozycja backlogu obok I-2.
- Powierzchnia wyjatkow trybu `--geometry` (`shapefile`/`sqlite3` dla uszkodzonego
  pliku -> bariera `main()`, nie `Error:` z galezi) — niezmieniona wzgledem stanu
  sprzed fali (`get_overall_bbox` juz wczesniej czytal plik w tym samym miejscu).
- `--geometry` + `EPSG:2180` bez sumy R-01 i bez zapasu 1 px (skrajna kolumna
  nodata) — ruling kontrolera Zad. 9, udokumentowane.
- R2 (pierscien zamiast calej obwiedni), R6 (scalanie PL+CZ), reprojekcja arkuszy
  PL-2000, podwojna obwiednia przy ukladzie zadania = `--target-crs`, `round`
  w `warp_to_grid`, `XSCALE/YSCALE` — "Poza zakresem" planu.
- Remis siatki wiekszosci rozstrzygany kolejnoscia wejscia — udokumentowany.
- `download_pl_cutout` tworzy `GugikProvider` bez `cache=`/`session=` — wzor
  fabryki sprzed fali (CLI tak samo).
- Zmiana poziomu logu dla arkusza bez danych w trybach listy arkuszy (`error`
  -> `warning "No data for"`) — kod wyjscia bez zmian, semantyka zachowana.

---

### Recommendations

1. **Fala naprawcza (jeden dispatch, przed checklista live):** I-1 (test CLI
   `force=True` + asercja `skip_existing is False` + asercja `max_workers`), I-2
   (straz negatywna w `_get_opendata_url` + test `ServiceExceptionReport` z 200),
   oraz 9 pozycji NAPRAW TERAZ z triazu (docstringi `manager.py`/`gugik.py`,
   `_CZ_CRS` przez `upper()`/`wkid()`, `-m "not live"` w CLAUDE.md/README, trzy
   nieprecyzje ARCHITECTURE, PROGRESS). Kazda z dowodem mutacyjnym.
2. **Checklista live** (PROGRESS pkt 12): dopisac do (j) "bbox nad morzem"
   zapis realnego body i `Content-Type` pustej odpowiedzi GetFeatureInfo oraz
   arkusza po stronie czeskiej — to dane wejsciowe do ewentualnej kontroli
   pozytywnej w I-2; (f) siatka 1 m — jesli fazy kampanii sie roznia, m-4
   (`extra.off_grid_sheets` + `Warning:`).
3. **Backlog API** (po 0.7.0): `download_pl_cutout(provider=, storage=)`
   addytywnie (m-5) — Hydrograf jako konsument biblioteczny bedzie chcial
   wstrzyknac wlasny provider/cache; `estimate_pl_cutout_bytes` z rozszerzeniem
   providera (m-3); `bbox_to_crs` do `transform/` razem z odmrozeniem CZ (m-10).
4. Nie ruszac: R-01 (R2), toru CZ, `warp_to_grid` — zgodnie z planem.

---

### Assessment

**Ready to merge? With fixes.** Kod fali jest poprawny i spojny miedzyzadaniowo
(0 Critical): tor wycinka PL kompozycyjnie trzyma sie R1/R3/R5, tor CZ jest
bajt w bajt nietkniety, dokumentacja po raz pierwszy w tej galezi nie klamie
o zachowaniu. Dwie pozycje Important sa tanie (jeden test CLI dla `--force`,
jedna straz + test w `_get_opendata_url`) i powinny wejsc razem z 9 pozycjami
NAPRAW TERAZ w jednej fali naprawczej przed checklista live i bumpem 0.7.0;
nic nie blokuje dalszej pracy na `develop`.

Kontrola koncowa: `git status --short` pusty (poza ignorowanym `.superpowers/`).
