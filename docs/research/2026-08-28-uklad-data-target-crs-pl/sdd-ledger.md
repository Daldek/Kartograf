# SDD ledger — plan: docs/superpowers/plans/2026-08-28-uklad-data-i-target-crs-pl.md

Spec: docs/superpowers/specs/2026-08-28-uklad-data-i-target-crs-pl-design.md (binding authority)
Branch: develop (praca bezposrednio, decyzja D7 w specu)
Tryb: team-driven-development = superpowers:subagent-driven-development + tiering modeli
  (sonnet = implementacja z gotowego kodu planu + reviewery per-task; opus = zadania
  z osadem + reviewery trudnych diffow; fable = finalny review calej galezi)
Ekstraktor briefow: .superpowers/sdd/2026-08-28-uklad-data-i-target-crs-pl/task-brief-pl
  (skillowy scripts/task-brief nie rozumie naglowkow "### Zad. N")

## Setup (2026-08-28)

- Workspace: `.superpowers/sdd/2026-08-28-uklad-data-i-target-crs-pl/`
- Briefy Zad. 1-12 wyekstrahowane (`task-N-brief.md`, 59-825 linii)
- Pliki wspolne dispatchow: `IMPLEMENTER_COMMON.md`, `REVIEWER_COMMON.md`,
  `REREVIEW_COMMON.md`
- **Baseline zmierzony na develop @ ae6d072: 1716 testow PASS, 33 bledy mypy**
  (zgadza sie z Global Constraints planu; `baseline.txt`)

## Pre-flight

- [x] pre-flight scan planu zlecony agentowi opus -> `preflight-report.md`

## Postep

### Pre-flight: wynik i rulingi (2026-08-28)

Raport: `preflight-report.md` (1 BLOKUJACY, 4 WAZNE, 12 DROBNYCH; ~90 konkretow
planu sprawdzonych na zywym repo, rozjechane 4). Warstwa mechaniczna planu
(numery linii, sygnatury, patch targety, slice'y) potwierdzona jako zgodna.

Wszystkie rulingi materializuja sie jako sekcja **"WIAZACE POPRAWKI DO BRIEFU"**
dopisana na koncu odpowiedniego `task-N-brief.md` — brief zostaje jedynym
zrodlem wymagan implementera.

- **R-01 (D-01, BLOKUJACY) -> Zad. 8 (+ dziedziczy Zad. 9).** Plan tnie mozaike
  dokladnie do `bbox_2180`, a warpuje na OBWIEDNIE tego prostokata w ukladzie
  docelowym — wynik ma z definicji puste kliny narozne (zmierzone ~300 x 227 m
  przy zadaniu 3000 x 4000 m, ~9 % powierzchni) i traci ~1 px krawedzi
  zadanego obszaru na halo bilinear. Tor CZ rozwiazuje to od 0.7.0-dev
  odwrotnym kierunkiem: `_native_request_bbox` = cel przeliczony wstecz
  + `_WARP_MARGIN_PX = 4` (`providers/cuzk/dmr.py:92,310-320`).
  **Decyzja: kopiujemy wzorzec CZ.** Crop i selekcja arkuszy ida z bboxa
  2180 POWIEKSZONEGO (back-obwiednia `bbox_target` + 4 px), grid wyniku bez
  zmian. Spec 6.1 pkt 2 cytuje `mosaic_and_crop(sheet_paths, bbox_2180, tmp)`
  doslownie, ale spec 6.2 obiecuje wycinki PL i CZ "gotowe do nalozenia" —
  litera przegrywa z celem, ktory sama ustanawia.
  *Koszt jesli zle:* pobranie garstki dodatkowych arkuszy na krawedzi
  i wiekszy crop tymczasowy; zasieg i siatka WYNIKU sie nie zmieniaja,
  wiec pomylka jest odwracalna jedna zmiana stalej.
- **R-02 (D-02) -> Zad. 2.** Do "PELNEJ listy" churnu dopisany
  `tests/test_storage.py:427` (`assert "/nmt_1m/" in str(path)`, blizniak
  wymienionego :434). Potwierdzone na repo.
  *Koszt jesli zle:* zaden — bez tego Step 5 konczy sie czerwona suita.
- **R-03 (D-03) -> Zad. 9.** `TestBorderTwoCutouts` dostaje fixture
  `_isolate_cache` (kopia z `TestAutoSplitBBox`, `test_cli.py:3697-3702`) —
  inaczej `MetadataCache()` z `_cmd_download_cz` tworzy `.kartograf_cache.db`
  w korzeniu repo. *Koszt jesli zle:* zaden.
- **R-04 (D-04) -> Zad. 11.** Druga weryfikacja CHANGELOG-a dostaje
  `| grep -v "pl.gugik.nmt_1m"`; `docs/CHANGELOG.md:62` to KLUCZ DESKRYPTORA,
  nie sciezka, i ma zostac nietkniety. *Koszt jesli zle:* falszywy alarm bramy
  dokumentacyjnej i ryzyko regresji tresci CHANGELOG-a.
- **R-05 (D-05) -> Zad. 11.** Numery linii `docs/PROGRESS.md` w planie sa
  sprzed commita `ae6d072` (przesuniecie o 58 linii; A1-9 jest na 741-744).
  Kotwiczymy na TRESCI (`- [ ] A1-9`, `## Backlog`), nie na numerach.
- **R-06 (D-06) -> Zad. 2.** Dwie asercje z planu maja 104-105 znakow przy
  `line-length = 88` — rozbic na `storage = ...` + `assert ...`.
- **R-07 (D-07) -> Zad. 7 i 8.** `_APEX_2180 = (530050.0, 382050.0)` to
  okolice Piotrkowa Trybunalskiego (19,43 E / 51,30 N), NIE Cieszyn. Punkt
  zostaje (operacja 2180->5514 ma tam 0,5 m), klamliwy komentarz znika.
  *Koszt jesli zle:* zerowy funkcjonalnie; alternatywa (zmiana punktu)
  pociagnelaby przeliczenie oczekiwan w dwoch nowych plikach testowych.
- **R-08 (D-08) -> Zad. 3.** `test_default_storage_5m_kron86_corrected_to_evrf`
  jest ZIELONY juz przed implementacja (FileStorage wypelnia `{vcrs}` swoim
  defaultem) — to test REGRESYJNY, nie RED. Implementer ma to wiedziec, zeby
  nie "naprawial" zielonego testu.
- **R-09 (D-09) -> Zad. 2.** Warunek `system is not None` ZOSTAJE mimo
  martwej galezi: `parser_registry.detect_system` deklaruje
  `-> SheetSystem | None` (`parser_registry.py:36`), wiec bez niego mypy
  zglosilby nowy blad — a brama Zad. 12 zabrania nowego dlugu. Dostaje
  komentarz jak precedens w `download_cmd.py:610-613`.
- **R-10 (D-10) -> Zad. 8.** `bbox_to_crs(bbox_2180, args.target_crs, pinned)`
  — trzeci argument istnieje (`providers/cuzk/dmr.py:564-566`); bez niego
  `TransformerGroup` liczy sie dwa razy i pod dwiema roznymi politykami.
  Back-obwiednia z R-01 (kierunek target->2180) buduje wlasna operacje,
  bo `pinned` jest kierunkowy — tak samo robi CZ.
- **R-11 (D-11) -> Zad. 8.** `TransformPolicy(...)` wycinka PL jako nazwana
  stala `_PL_HORIZONTAL_POLICY` (lustro `_HORIZONTAL_POLICY` toru CZ).
- **R-12 (D-12) -> Zad. 9.** `_download_pl_geometry` z `--target-crs`
  i `bbox=None` dostaje jawny `ValidationError` zamiast utajonego
  `AttributeError` na `bbox.crs`.
- **R-13 (D-13) PARKED, drobne.** Budowa sciezki wycinka poza `FileStorage`
  omija walidator `_ensure_resolved`. Zostaje: identyczny wzorzec ma juz
  `_cz_download_bbox:1346-1351`, oba wymiary sa podane jawnie, a przeciaganie
  tego przez FileStorage powiekszyloby zakres Zad. 8. Do triazu w finalnym
  review. *Koszt jesli zle:* teoretyczna klamra w nazwie katalogu wycinka.
- **R-14 (D-14) -> Zad. 8.** Komentarz przy `if failed_sheets: return 1`
  sugeruje warunkowosc od `--target-crs`, ktorej nie ma (kod istnieje dzis,
  `download_cmd.py:981-983`) — przeformulowac.
- **R-15 (D-15) -> Zad. 10.** Kolejnosc zadan ZOSTAJE (Zad. 11 odsyla do
  ARCHITECTURE.md, wiec musi byc po nim). ARCHITECTURE.md przez jeden commit
  odsyla do ADR-026/027 dopisywanych w Zad. 11 — stan koncowy galezi jest
  spojny, a przestawienie zadan stworzyloby zaleznosc w druga strone.
  Zakres kopiowania indeksu ADR zawezony do `DECISIONS.md:8-802` (802, nie
  925 — 925 to naglowek WEWNATRZ komentarza-szablonu).
  *Koszt jesli zle:* jeden posredni commit z wisiacym odsylaczem.
- **R-16 (D-16) -> Zad. 11.** Plan slusznie odmawia dopisania wiersza
  `capability` do tabeli sidecara w README (`ResultMetadata`,
  `sources/sidecar.py:23-42`, nie ma takiego pola) — ale to rozjazd z litera
  specu 10.3 poza sekcja "Odstepstwa". Odnotowany tutaj, zeby review mial
  gdzie go zobaczyc.
- **R-17 (D-17) -> wszystkie briefy.** Numery linii w planie sa WSKAZOWKA,
  nie kotwica (5 drobnych przesuniec, m.in. `TestDescriptorProviderConsistency`
  236 zamiast 237). Implementerzy kotwicza na TRESCI — reguła trafia do
  `IMPLEMENTER_COMMON.md`.

### Wykonanie

Task 1: dispatch (sonnet), BASE=ae6d072 — `SourceDescriptor.resolve_subdir`
Task 1: implementer DONE (commit fb1d0bb; 1722 passed = 1716+6, ruff clean, mypy 33 bez zmian)
Task 1: review dispatch (sonnet), paczka review-ae6d072..fb1d0bb.diff
Task 1: review CZYSTY — SPEC OK, JAKOSC APPROVED; reviewer niezaleznie potwierdzil 1722 PASS i mypy 33 (identyczna lista plik:linia)
Task 1: minor (deferred): redundantny lokalny import w `_descriptor()` w tests/test_sources_registry.py (pochodzi z briefu; sprzatnac przy okazji edycji pliku)
Task 1: minor (deferred): `resolve_subdir(vertical_crs="")` podstawia pusty string -> wiszacy podkreslnik w segmencie; konsumenci (Zad. 2/3/5) maja normalizowac brak wartosci do None, nie do ""
Task 1: complete (commits ae6d072..fb1d0bb, review clean)
Task 2: dispatch (sonnet), BASE=fb1d0bb — szablony segmentow: rejestr + FileStorage + CZ CLI + churn asercji
Task 2: implementer DONE (commit 2a6a327; 1734 passed = 1722+12, ruff clean, mypy 32 (-1: download_cmd.py:1347 znikl zgodnie z przewidywaniem planu)); R-02/R-06/R-09 zastosowane
Task 2: review dispatch (opus — najwiekszy diff planu, 59 kB), paczka review-fb1d0bb..2a6a327.diff
Task 2: review CZYSTY — SPEC OK, JAKOSC APPROVED. Reviewer potwierdzil niezaleznie: 1734 PASS, ruff clean, mypy 32 przez SET-DIFF wobec czystego checkoutu fb1d0bb (zniknal dokladnie download_cmd.py:1347, zero nowych). Punkty (a)-(f) dispatchu wszystkie OK; 3 "odstepstwa formatowe" implementera zweryfikowane jako faktycznie tylko formatowe.
Task 2: minor (deferred): `FileStorage(vertical_crs="")` daje cichy wiszacy podkreslnik (`nmt/pl_1992_1m_/`) zamiast bledu — storage.py:141-142; naprawa `if self._vertical_crs:`. Dzis nieosiagalne (choices argparse, _SUPPORTED_VERTICAL, sentinele PL), ale Zad. 3-5 dokladaja zrodla tej wartosci. Powiazane z minorem Task 1.
Task 2: minor (deferred): docstring `list_files` (storage.py:393) mowi "Searches within the resolution subdirectory" — przeszukuje teraz DWA katalogi (1992 i 2000)
Task 2: minor (deferred): docstring konstruktora (storage.py:83-84) daje nieaktualny przyklad `subdir="cz_dmr5g"` zamiast szablonu `nmt/cz_dmr5g_{vcrs}`
Task 2: minor (deferred): `_cz_download_bbox` (download_cmd.py:1349-1352) sklada sciezke bez `_ensure_resolved` — wzmocnienie R-13 (ten sam wzorzec dotyczy wycinka PL w Zad. 8)
Task 2: minor (deferred): `test_product_none_backward_compatible` nie broni juz katalogu produktu "nmt" (darmowe wzmocnienie: `assert "nmt" in parts`)
Task 2: minor (deferred): polskie wtrety w angielskim storage.py (komunikat ValidationError :151, komentarz R-09 :164-166) — tresc nakazana briefem/rulingiem, plik ma juz polskie wtrety (:84, :384)
Task 2: complete (commits fb1d0bb..2a6a327, review clean)
Task 3: dispatch (sonnet), BASE=2a6a327 — DownloadManager przekazuje faktyczny pion do segmentu
Task 3: implementer DONE (commit cdb7588; 1736 passed = 1734+2, ruff clean, mypy 32 bez zmian)
Task 3: review dispatch (sonnet), paczka review-2a6a327..cdb7588.diff
Task 3: review CZYSTY — SPEC OK, JAKOSC APPROVED, zero ustalen Krytycznych/Waznych. Reviewer potwierdzil w kodzie (nie na slowo raportu), ze uzyto zmiennej PO korekcie 5m=>EVRF2007 (manager.py:191-197 vs :210,215).
Task 3: minor (deferred) ESKALACJA: to zadanie POSZERZA osiagalnosc zaparkowanego drobiazgu `vertical_crs=""`. Reviewer ustalil: wszystkie 3 wywolania z CLI (download_cmd.py:661,938,1576) podaja `storage=` jawnie, wiec galaz `storage is None` nie odpala sie z CLI — ale `DownloadManager` to publiczne API (uzywa go Hydrograf) i `DownloadManager(provider=<custom>, vertical_crs="")` bez `storage=` realnie dotrze teraz do segmentu. Trzeci raz ta sama jednolinijkowa naprawa (`if self._vertical_crs:` w storage.py:141) — PRIORYTET dla fali naprawczej po finalnym review.
Task 3: complete (commits 2a6a327..cdb7588, review clean)
Task 4: dispatch (sonnet), BASE=cdb7588 — CLI PL: _create_provider_and_storage przekazuje faktyczny pion
Task 4: implementer DONE (commit cd8b616; 1739 passed = 1736+3, ruff clean, mypy 32 bez zmian); teza raportu: `vertical_crs=""` nie dociera tu do FileStorage (provider waliduje przeciw SUPPORTED_VERTICAL_CRS zanim storage powstanie) — do weryfikacji przez review
Task 4: review dispatch (sonnet), paczka review-cdb7588..cd8b616.diff
Task 4: review CZYSTY — SPEC OK, JAKOSC APPROVED. Reviewer zweryfikowal w runtime, ze test 5m/KRON86 faktycznie broni (surowa flaga dalaby `..._5m_kron86`), i potwierdzil teze o nieosiagalnosci pustego stringa ta sciezka.
Task 4: minor (deferred): task-4-report.md:166 pisze "ValidationError", a `GugikProvider.__init__` (providers/pl/gugik.py:204,211) rzuca zwykly `ValueError` — nieścisłość w TEKSCIE raportu, kod bez zmian; wniosek raportu pozostaje prawdziwy
Task 4: complete (commits cdb7588..cd8b616, review clean)
Task 5: dispatch (sonnet), BASE=cd8b616 — CLI LAZ: segment per kafel (uklad_xy -> {uklad})
Task 5: implementer DONE (commit 7a29ce7; 1745 passed = 1739+6, ruff clean, mypy 32 bez zmian); domkniety efekt uboczny Zad. 2 (segment LAZ ignorowal --vertical-crs), potwierdzony empirycznie przed fixem
Task 5: review dispatch (sonnet), paczka review-cd8b616..7a29ce7.diff; do weryfikacji: wyscig cache `_storage_for` pod ThreadPoolExecutor + czy nowe asercje faktycznie broni segmentu
Task 5: review — SPEC OK, JAKOSC APPROVED, ale 1x [Wazne]: zaden test nie broni PIONOWEJ strony segmentu LAZ. Reviewer potwierdzil funkcjonalna poprawnosc niezaleznie (resolve_subdir(uklad="2000", vertical_crs="KRON86") -> "laz/pl_2000_kron86", FileStorage daje te sciezke), ale zaden test nie wola CLI z `--product laz --vertical-crs KRON86`, wiec przyszla regresja (usuniecie `vertical_crs=` z `_storage_for`) przeszlaby niezauwazona — domyslne EVRF2007 maskuje blad dokladnie tak, jak maskowal go przed ta lataka.
Task 5: Ruling: PRZYJMUJE ustalenie mimo ze brief zada tylko asercji `pl_2000_evrf2007` (Step 1) i spec 13 pkt 3 tez wymienia tylko evrf2007. Powod: caly sens Zad. 5 to DWA wymiary segmentu ({uklad} ORAZ {vcrs}), a wymiar pionowy zostalby bez ochrony regresyjnej — i to na defekcie, ktory JUZ raz przeslizgnal sie niezauwazony (efekt uboczny Zad. 2 przeszedl przez testy LAZ, bo szukaja plikow przez rglob i uzywaja domyslnego pionu). Litera planu testow przegrywa z celem zadania. Koszt jesli zle: jeden dodatkowy test CLI (~15 linii), zero zmian w kodzie produkcyjnym.
Task 5: fix round 1/5 dispatch — wznowienie oryginalnego implementera, FIX_BASE=7a29ce7
Task 5: fix round 1/5 — implementer DONE (commit db8b950; 1746 passed = 1745+1, ruff clean, mypy 32). Test `test_laz_segment_carries_vertical_crs_from_flag` udowodniony mutacyjnie (usuniecie `vertical_crs=` -> FAIL `pl_2000_evrf2007` vs oczekiwane `pl_2000_kron86`; przywrocenie -> PASS); KRON86 przechodzi walidacje sentineli dla LAZ; kod produkcyjny zerowy diff netto wzgledem 7a29ce7
Task 5: scoped re-review dispatch (sonnet), paczka review-7a29ce7..db8b950.diff — z obowiazkiem samodzielnego powtorzenia mutacji
Task 5: re-review 1/5 — WSZYSTKIE USTALENIA ZAMKNIETE. Re-reviewer samodzielnie przeprowadzil mutacje (usunal `vertical_crs=` w _storage_for -> FAIL `pl_2000_evrf2007` vs `pl_2000_kron86`), przywrocil plik i potwierdzil PASS + czyste drzewo; potwierdzil zerowy diff netto kodu produkcyjnego (`git diff 7a29ce7..HEAD -- kartograf/` puste), addytywnosc diffu testow (zero usunietych linii), 1746 PASS, ruff clean, mypy 32. Test asertuje segment dla kafla I sidecara + niezalezna kotwice `vertical_crs == "EPSG:9650"`.
Task 5: complete (commits cd8b616..db8b950, review clean po 1 rundzie naprawczej)
Task 6: dispatch (sonnet), BASE=db8b950 — mosaic_and_crop: dst_kwds (GTiff + CRS dla wejsc ASC)
Task 6: implementer DONE (commit b7f139d; 1747 passed = 1746+1, ruff clean, mypy 32 bez zmian); jedyny konsument CZ (providers/cuzk/client.py:182) wola bez dst_kwds
Task 6: review dispatch (sonnet), paczka review-db8b950..b7f139d.diff — nacisk na nietykalnosc toru CZ i semantyke scalania nad nodata
Task 6: review CZYSTY — SPEC OK, JAKOSC APPROVED, zero Krytycznych/Waznych. Reviewer porownal stara i nowa logike linia po linii dla obu przypadkow (nodata=None -> None, nodata=X -> {"nodata": X}) i potwierdzil ROWNOWAZNOSC toru CZ; niezaleznym skryptem pokazal, ze bez dst_kwds wynik ma driver=AAIGrid/crs=None, czyli test faktycznie bada mechanizm.
Task 6: minor (deferred): `kwds: dict` bez parametrow generycznych (mosaic.py:58) — zgodne ze stylem modulu, mypy milczy
Task 6: complete (commits db8b950..b7f139d, review clean)
Task 7: dispatch (OPUS — geometryczne jadro: warp z wymuszona operacja, axis-swap, maskowanie nodata), BASE=b7f139d
Task 7: implementer DONE (commit d400c58; 1750 passed = 1747+3, ruff clean, mypy 32, zero bledow w nowym module). Zmierzyl nosnosc kazdej pulapki ADR-024 na torze PL: bez COORDINATE_OPERATION wierzcholek ucieka ~122 m (GDAL gubi datum shift 2180->5514, dokladnie jak serwer CUZK w ADR-024); bez axisswap wynik ma 0 WAZNYCH PIKSELI (cichy raster-nodata — zrodlo 2180 jest northing-first); maskowanie nodata dziala (min wazna 859,48 przy dziurze -9999).
Task 7: przekazane do Zad. 8 przez implementera: (1) tor PL nie ma testu nodata-bleed, ktory ma tor CZ — kandydat do Zad. 8; (2) `warp_to_grid` przy bledzie kasuje TAKZE wczesniej istniejacy `dst_path` (semantyka z CZ) — istotne, jesli Zad. 8 warpuje w miejsce istniejacego pliku
Task 7: review dispatch (OPUS), paczka review-b7f139d..d400c58.diff — z obowiazkiem porownania kopii z oryginalem CZ linia po linii i samodzielnego powtorzenia >=1 pomiaru
Task 7: review — SPEC OK, ale JAKOSC: CHANGES REQUESTED (2x Wazne). Reviewer znormalizowal oba ciala funkcji i zdiffowal mechanicznie: kopia jest IDENTYCZNA linia w linie z oryginalem CZ (dmr.py:500-561) poza sygnatura — zero cichego dryfu. Powtorzyl oba pomiary pulapek i potwierdzil (121,9 m bez COORDINATE_OPERATION; valid=0 bez axisswap).
Task 7: [Wazne] 1 — `src_crs` to parametr MARTWY. Dowod pomiarowy reviewera: dla tego samego rastra i tego samego `pinned` (2180->5514) podanie src_crs = 2180/4326/3857/32633/5514 daje PIEC IDENTYCZNYCH wynikow (dE=-0.50 dN=-0.50 valid=38394) — przy wymuszonym COORDINATE_OPERATION GDAL bierze pipeline za jedyne zrodlo prawdy. W oryginale CZ bylo to bezpieczne (NATIVE_CRS = stala uzgodniona z budowa pinned); parametryzacja rozdzielila dwa zrodla prawdy bez spinajacej ich kontroli.
Task 7: Ruling: PRZYJMUJE. Zad. 8 buduje `pinned` i osobno podaje `src_crs` — bledna para dalaby cicho zly wynik, a martwy parametr daje falszywe poczucie asekuracji. Zweryfikowalem wykonalnosc naprawy: `PinnedTransform` ma pola `src_crs`/`dst_crs` (crs.py:64-65), a `build_pinned_transform` je WYPELNIA (crs.py:219-225), wiec guard realnie zadziala. Koszt jesli zle: 3 linie walidacji + test.
Task 7: [Wazne] 2 — maskowanie nodata niestrzezone, a "oczywisty" test bylby PUSTY. Dowod rozniczkowy reviewera (ktorego raport implementera NIE zawieral): przy zrodle deklarujacym nodata w profilu usuniecie src_nodata/dst_nodata NIC nie zmienia (rasterio domysla sie z rasterio.band), min wazna 859,48 w obu wariantach. Pulapka gryzie dopiero przy zrodle BEZ zadeklarowanego nodata: min wazna spada do -9890,69 (nodata wchodzi do interpolacji bilinearnej). Ta konfiguracja jest osiagalna na torze PL — `mosaic.py:24` ma `nodata: float | None = None` i wpisuje kwds["nodata"] tylko gdy caller poda wartosc.
Task 7: Ruling: PRZYJMUJE, ale test ma powstac TU, nie w Zad. 8 (reviewer proponowal przekazac wymaganie dalej). Powod: `transform/raster.py` jest wlascicielem argumentow src_nodata/dst_nodata, wiec ochrona nalezy do jego testu jednostkowego; test w Zad. 8 bylby integracyjny i — na fixturze deklarujacej nodata — atrapa. To 4. test ponad 3 przewidziane briefem. Koszt jesli zle: jeden dodatkowy test jednostkowy.
Task 7: minor (deferred): asercja "zapisu atomowego" testuje tylko sciezke sukcesu (test_transform_raster.py:88) — zaden test nie wstrzykuje bledu, wiec kolejnosc os.replace i `except BaseException` nie sa bronione
Task 7: minor (deferred): docstring cichego filtra GDAL skrocony wzgledem oryginalu — wypadlo zdanie, ze filtr jest waski i zdejmowany natychmiast, wiec nie ukrywa innych bledow GDAL
Task 7: fix round 1/5 dispatch — wznowienie oryginalnego implementera (opus), FIX_BASE=d400c58
Task 7: fix round 1/5 — implementer DONE (commit 14baa39; 1754 passed = 1747+7, ruff clean, mypy 32). Oba dowody mutacyjne przeprowadzone: bez guardu padaja 2 testy na "DID NOT RAISE" (niezgodna para przechodzi CICHO; przy zlym bbox.crs GDAL tylko loguje i produkuje pusty raster); bez src_nodata/dst_nodata test nodata pada z min = -9890.686, co do miejsca po przecinku zgodne z pomiarem reviewera -> fixtura nie jest atrapa (ma asercje `ds.nodata is None`). Przywrocenie po kazdej mutacji potwierdzone md5sum + czystym git status.
Task 7: implementer przyznal wprost, ze jego pierwotna "Pulapka 3 — POMIAR" nie byla rozniczkowa i nie dowodzila nosnosci maskowania — luka w rozumowaniu, nie tylko w raporcie
Task 7: dwie rzeczy ponad literalny ruling (do oceny w re-review): (a) guard porownuje uklady SEMANTYCZNIE (`_same_crs`), bo falszywy odrzut zdrowego wywolania jest gorszy niz przepuszczenie rownowaznego zapisu; (b) dodatkowy test na regule "tylko pola nie-None" + ustalenie, ze ta tolerancja jest defensywna i nieobserwowalna end-to-end (`gdal_operation()` i tak rzuca TransformError przy None)
Task 7: dla Zad. 8 — `warp_to_grid` moze teraz rzucic `TransformError` TAKZE za niespojna pare ukladow
Task 7: scoped re-review dispatch (sonnet), paczka review-d400c58..14baa39.diff — z obowiazkiem samodzielnego powtorzenia OBU mutacji
Task 7: re-review 1/5 — WSZYSTKIE USTALENIA ZAMKNIETE. Re-reviewer samodzielnie przeprowadzil OBA dowody mutacyjne z identycznym wynikiem (mutacja A: 2 testy guardu padaja na DID NOT RAISE; mutacja B: min -9890.685546875, zgodne co do 3. miejsca po przecinku z raportem), zweryfikowal fixture (`declare_nodata=False` -> `"nodata": None` w profilu + straznik `assert ds.nodata is None`), przywrocil pliki po md5sum. Ocena dodatkow: `_same_crs` bez ryzyka (fail-closed przy bledzie parsowania); `test_guard_skips_unknown_pinned_pair` sprzezony z trescia komunikatu z crs.py — kruchosc przy refaktorze, nie blad logiki, nie blokuje.
Task 7: complete (commits b7f139d..14baa39, review clean po 1 rundzie naprawczej)
Task 8: dispatch (OPUS — rdzen funkcji, 825-linijkowy brief + 5 wiazacych poprawek, w tym zmiana projektu R-01), BASE=14baa39
Task 8: implementer DONE (14baa39..e9e8d89; 1772 passed = 1754+19-1, ruff clean, mypy 32 baseline)
Task 8: R-01 ZWERYFIKOWANY POMIAREM, nie oszacowaniem: bez zapasu zrodla ten sam wycinek 5514 ma 3034/17484 px nodata (17,4%), z zapasem 0. Pre-flight szacowal ~9% — realny efekt jest DWUKROTNIE wiekszy. Pomiar zakonserwowany jako test `test_target_5514_full_coverage_from_source_bbox`.
Task 8: sciezka PL bez --target-crs udowodniona A/B (kod przed vs po, 9 scenariuszy): identyczne rc/stdout/stderr/args; jedyna roznica to kolejnosc wywolan, a w dwoch sciezkach bledu provider powstaje teraz mimo bledu — implementer zweryfikowal, ze konstruktor providera i FileStorage nie robia zadnego IO ani mkdir
Task 8: do rozstrzygniecia: (1) przy --force porazka budowy wycinka kasuje POPRZEDNI plik (zmierzone); (2) `--geometry --target-crs` dla PL jest juz przepuszczane, ale wycinka nie robi — domena Zad. 9
Task 8: review dispatch (opus) PADL na bledzie API przed wykonaniem jakiejkolwiek pracy — re-dispatch swiezego reviewera (opus) z tym samym briefem
Task 8: review CZYSTY — SPEC OK, JAKOSC APPROVED, zero Krytycznych/Waznych. Reviewer ODTWORZYL pomiar R-01 co do piksela (3034/17484 = 17,4% bez zapasu, 0 z zapasem) i potwierdzil, ze test go faktycznie lapie (mutacja bbox_source_2180 -> bbox_2180 przewraca go). Zniknal DOKLADNIE jeden test — `test_pl_bbox_with_target_crs_rejected` — usuniecie sluszne, bo asertowal odrzucenie, ktore brief celowo odwraca; bilans 1754+19-1 zgodny z --collect-only. Wszystkie 5 poprawek (R-01/R-10/R-11/R-14/R-07) zweryfikowane. Pion w sidecarze faktyczny. Tor CZ nietkniety (tylko import bbox_to_crs).
Task 8: minor (deferred): dowod A/B ma luke — dla `5m` + `KRON86` nowa kolejnosc DOKLADA linie na stderr (warning fabryki o korekcie 5m=>EVRF2007, ktory w sciezce sukcesu i tak by padl). Komunikat bledu i kod wyjscia NIENARUSZONE; harness implementera uzywal domyslnego 1m/EVRF2007, stad "identyczne we wszystkich 9 scenariuszach". Sprostowanie zakresu dowodu, nie naprawa.
Task 8: Ruling: `--force` + porazka budowy kasuje poprzedni wycinek TAKZE gdy porazka nastapila przed dotknieciem celu (np. blad w mosaic_and_crop, ktory pisze tylko do tmp). PRZYJMUJE jako semantyke "odswiez albo nic" — jest juz w trzech miejscach (transform/raster.py:132-134, tor CZ, wycinek), a rozjazd PL vs CZ bylby gorszy niz nadmiarowosc; tor CZ jest nietykalny przed wydaniem, wiec naprawa "w obu" i tak nie wchodzi w gre. Osiagalne tylko pod --force (bez niego skrot "already exists" wraca wczesniej). Do udokumentowania w Zad. 11. Koszt jesli zle: uzytkownik z --force traci poprzedni wycinek przy nieudanym odswiezeniu.
Task 8: Ruling: skreslam "ustalenie nr 3" z raportu implementera (`_PL_NODATA` jako stala rzekomo rozjezdzajaca sie z danymi). Reviewer ZMIERZYL: arkusz z `NODATA_value -32768` przepuszczony przez `mosaic_and_crop(nodata=-9999.0)` daje wynik [-9999, 100] — rasterio przemapowuje nodata zrodla na nodata celu, a sidecar opisuje PLIK WYNIKOWY. Stala jest poprawna; nie przekazuje tego dalej.
Task 8: minor (deferred): niesymetryczne importy z transform.crs (build_pinned_transform lokalnie, bo "testy podmieniaja operacje w module") — design-by-test, konsekwencja mala
Task 8: do Zad. 9 (pointery): (a) help `--target-crs` w _parser.py juz obiecuje wycinek dla --geometry — Zad. 9 ma to domknac; (b) `test_skip_existing_short_circuits_before_download` asertuje tylko `dl.assert_not_called()` i nie przybija NOWEJ kolejnosci (skrot przed selekcja arkuszy) — jeden mock `find_sheets` z assert_not_called domknalby regresje
Task 8: complete (commits 14baa39..e9e8d89, review clean)
Task 9: dispatch (OPUS — tryb geometry + scenariusze pograniczne), BASE=e9e8d89
Task 9: implementer DONE (e9e8d89..d7a3aee; 1774 passed = 1772+2, ruff clean, mypy 32 bez zmian). R-12 zrealizowany wariantem "jawny guard" (parametr zostaje opcjonalny) — wariant "parametr wymagany" kolidowal z wymogiem addytywnosci ze Step 4. Sciezka geometry bez --target-crs udowodniona trzema sposobami (analiza sterowania, 80 istniejacych testow geometrii, porownanie obserwowalnych efektow wywolania 3-arg vs z bbox).
Task 9: review dispatch (opus), paczka review-e9e8d89..d7a3aee.diff
Task 9: review — SPEC OK (+2 testy to POPRAWNA liczba: brief definiuje dokladnie 2 metody, --collect-only 19->21), ale JAKOSC: CHANGES REQUESTED (2x Wazne). R-03 zweryfikowane empirycznie (pytest z korzenia repo nie tworzy .kartograf_cache.db); R-12 oceniony jako wlasciwy wariant; R-01 nie zduplikowany; tor CZ nietkniety.
Task 9: [Wazne] 1 — NOWY TEKST POMOCY OBIECUJE ZACHOWANIE, KTOREGO KOD NIE MA. Help (_parser.py:115-117) i blizniaczy komentarz (download_cmd.py:1938-1941) mowia "w trybie --geometry po OBWIEDNI geometrii, z nodata miedzy rozlacznymi obiektami". Dowod reviewera: geometria NIGDY nie dociera do warstwy rastrowej — `_finalize_pl_cutout` dostaje tylko sciezki arkuszy i bbox, `_build_pl_cutout` robi `mosaic_and_crop(sheet_paths, bounds)` i nic nie maskuje. Nodata jest wylacznie tam, gdzie nie siega ZADEN pobrany arkusz, a arkusz 1:10000 to ~5,5 x 4,6 km — dwa rozlaczne obiekty odlegle o kilkaset metrow leza w tym samym arkuszu, wiec miedzy nimi jest REALNA WYSOKOSC, nie nodata.
Task 9: Ruling: PRZYJMUJE — i odnotowuje, ze to DEFEKT SAMEGO PLANU, nie implementera: sekcja Interfaces Zad. 9 twierdzi "obszary miedzy rozlacznymi obiektami geometrii wypelnia nodata (spec 6.1 + 6.2)", co jest falszywe. Uzytkownik czytajacy help jako obietnice maskowania moglby wziac wypelnienie miedzy obiektami za dane odciete — odwrotnosc bezpiecznego odczytu. Naprawa: help i komentarz opisuja fakt (cala obwiednia, bez maskowania do obiektow). KONSEKWENCJA MIEDZYZADANIOWA: to samo falszywe twierdzenie moze trafic do dokumentacji w Zad. 11 — pointer dodany do briefu Zad. 11. Koszt jesli zle: zdanie w helpie.
Task 9: [Wazne] 2 — linia czyniaca cala funkcjonalnosc osiagalna z CLI (`bbox=part` w _dispatch_area:523) NIE MA ZADNEGO TESTU. Dowod: `grep -rn "_download_pl_geometry" tests/` = jedno trafienie, wywolanie BEZPOSREDNIE z pominieciem _dispatch_area; zaden test nie przechodzi `--geometry` + `--target-crs` dla PL przez `main()`. Po cofnieciu tej linii trafia sie w guard R-12 -> kod 1, i suita zostaje ZIELONA. Reviewer sprawdzil skryptem, ze scalona sciezka dziala (rc 0, plik + sidecar z horizontal_crs=EPSG:2180) — to luka w pokryciu, nie blad.
Task 9: Ruling: PRZYJMUJE. Jedna linia, od ktorej zalezy osiagalnosc calej funkcji z CLI, nie moze byc niestrzezona — zwlaszcza ze plan konczy sie brama jakosci, ktora te linie przepuscilaby. Koszt jesli zle: jeden test integracyjny.
Task 9: minor (deferred): `TestBorderTwoCutouts` idzie trybem --bbox i NIE broni niczego z Zad. 9 (broni Zad. 8 / kryterium 13.6) — nie liczyc go jako pokrycie tego zadania
Task 9: minor (deferred): jedyny test wlasciwy Zad. 9 pokrywa tylko sciezke BEZ warpa (`_pl_args` domyslnie target_crs="EPSG:2180" -> pinned is None, sam crop); galaz 5514/3045 w trybie geometry nietknieta, mechanika wspoldzielona z torem bbox
Task 9: minor (deferred): guard R-12 robi `raise` zamiast `print + return 1` jak reszta funkcji — dzis nieosiagalne, ale pod --country auto przerwaloby petle po krajach i skasowalo semantyke czesciowego sukcesu
Task 9: minor (deferred): znany limit — przy celu != 2180 w trybie geometry arkusze wybiera geometria, a crop idzie do bboxa powiekszonego; gdy krawedz geometrii pokryje sie z krawedzia arkusza, halo interpolatora moze dac 1 px artefaktu na brzegu
Task 9: fix round 1/5 dispatch — wznowienie oryginalnego implementera (opus), FIX_BASE=d7a3aee
Task 9: fix round 1/5 — implementer DONE (commit c393a11; 1775 passed = 1772+3, ruff clean, mypy 32). Ustalenie 1 naprawione w TRZECH miejscach, nie dwoch — implementer znalazl to samo falszywe zdanie takze w docstringu `_download_pl_geometry` (weszlo doslownie z briefu, Step 3a); po naprawie `grep "rozlacznymi obiektami" kartograf/ tests/` = zero trafien; bledny odsylacz "(spec 6.2)" usuniety. Dowod mutacyjny ustalenia 2: pod mutacja nowy test pada z rc=1 i komunikatem guardu R-12, a suita BEZ tego testu daje 1774 PASS przy calkowicie zepsutej funkcjonalnosci — empiryczne potwierdzenie luki. Linia 523 po przywroceniu byte-identyczna z d7a3aee.
Task 9: Ruling (dzialanie wyprzedzajace): falszywe twierdzenie o nodata zostaje w SAMYM PLANIE (linie 2350 i 2516) — sprawdzilem, ze NIE ma go w specu ani w briefach 10/11, ale Zad. 10/11 opisuja `--target-crs` wlasnymi slowami i moglyby je odtworzyc. Dopisalem do briefow 10 i 11 sekcje ostrzegawcza z prawdziwym opisem zachowania + polecenie udokumentowania semantyki "odswiez albo nic" przy --force. Koszt jesli zle: dwa akapity w briefach.
Task 9: scoped re-review dispatch (sonnet), paczka review-d7a3aee..c393a11.diff — z obowiazkiem samodzielnego powtorzenia mutacji i grepa za parafrazami falszywej obietnicy
Task 9: re-review 1/5 — WSZYSTKIE USTALENIA ZAMKNIETE. Re-reviewer przeszedl sciezke danych samodzielnie (_download_pl_geometry -> _finalize_pl_cutout -> _build_pl_cutout: zaden obiekt geometrii tam nie dociera) i potwierdzil, ze NOWY tekst jest prawdziwy, a nie jednym falszem zastapionym drugim; powtorzyl grep za parafrazami (trafiaja wylacznie w nowy, poprawny tekst); powtorzyl mutacje `bbox=part` (test pada z komunikatem guardu R-12), przywrocil plik, potwierdzil czyste drzewo; potwierdzil ze suita nie tworzy .kartograf_cache.db w korzeniu.
Task 9: complete (commits e9e8d89..c393a11, review clean po 1 rundzie naprawczej)
=== WSZYSTKIE ZADANIA FUNKCJONALNE (1-9) ZAMKNIETE. Stan: 1775 testow PASS, mypy 32, ruff clean. ===
Task 10: dispatch (OPUS — nowy kanoniczny docs/ARCHITECTURE.md; dokument opisujacy system musi byc weryfikowany wzgledem kodu), BASE=c393a11
Task 10: implementer DONE (commit f04cfb4; 1775 passed bez zmian, ruff clean, mypy 32). Diagram warstw z briefu NIE zgadzal sie z kodem — implementer zmierzyl zaleznosci AST-em (`download` nie importuje transport/transform/cache; `landcover` importuje `download`, nie `cache`; `core` ma jeden leniwy import do `providers`) i dokument niesie graf ZMIERZONY + jawna note. Falszywego twierdzenia o nodata nie przepisal; sekcja 4.3 opisuje fakt + semantyke "odswiez albo nic" przy --force.
Task 10: dla Zad. 11 (pointer od implementera): README.md ma dzis NIEPRAWDZIWY wiersz tabeli sidecara ("bez zadnego przeliczenia (pliki PL) cale pole to null") — po ADR-027 wycinek PL ma `transform.horizontal`
Task 10: review dispatch (opus), paczka review-c393a11..f04cfb4.diff
Task 10: review — SPEC OK, JAKOSC: CHANGES REQUESTED (1x Krytyczne, 2x Wazne). Reviewer potwierdzil wlasnym skryptem AST graf zaleznosci z sekcji 2 (odrzucenie diagramu z briefu bylo trafne), odtworzyl realnym FileStorage wszystkie sciezki z tabeli migracji, sprawdzil tabele storage_subdir 1:1 z _SOURCES i komplet 25 tytulow ADR.
Task 10: [Krytyczne] rozmiar arkusza 1:10000 zawyzony ~2,4x. ZWERYFIKOWALEM SAM: `SheetParser("N-34-130-D-d-2-4").get_bbox(crs="EPSG:2180")` = 2253 x 2432 m, nie ~5,5 x 4,6 km (~4,5 x 4,9 km to godlo SZESCIOCZLONOWE, opisane w repo jako 1:25000; patrz core/sheet_parser.py:65-69 — 7-czlonowe godlo jest tu nazwane "1:10000", choc GUGiK mowi o module archiwizacji 1:5000).
Task 10: Ruling: TO MOJ BLAD, nie implementera. Liczba przyszla z review Zad. 9, przekazalem ja NIEZWERYFIKOWANA w wiazacej poprawce do briefow, implementer Zad. 9 wpisal ja do komentarza kodu (download_cmd.py:1947), a implementer Zad. 10 do dokumentu (ARCHITECTURE.md:388). Wystepuje DOKLADNIE w tych dwoch miejscach (grep). Naprawiam OBA w rundzie naprawczej Zad. 10 — mimo ze komentarz w kodzie nalezy do zamknietego Zad. 9 — bo zostawienie znanej nieprawdy w komentarzu przy jednoczesnej naprawie dokumentu byloby swiadomym rozjazdem. Skutek merytoryczny: przy arkuszu 2,25 km dwa obiekty oddalone o ~3 km moga miec miedzy soba caly NIEWYBRANY arkusz, wiec teza "miedzy obiektami jest realny teren" wymaga zlagodzenia, nie tylko korekty liczby.
Task 10: [Wazne] "powiekszony bbox steruje selekcja arkuszy" — nieprawdziwe w trybie --geometry (tam arkusze wyznacza find_sheets_for_geometry per obiekt, a cutout powstaje POTEM i wplywa tylko na siatke wyniku i crop). Zgodne z moim wlasnym rulingiem R-01 dla Zad. 9; dokument nadmiernie uogolnia. PRZYJMUJE.
Task 10: [Wazne] "kazdy sidecar zadania dostaje extra.parent_request" — nieprawdziwe dla LAZ (`_write_laz_sidecar` buduje extra z godlo_kafla/rok/gestosc/url, `_cmd_download_laz` nigdy nie wola `_build_parent_request`), a LAZ przyjmuje --bbox/--geometry. Konsument grupujacy po tym kluczu zgubi kafle LAZ. Ta sama nieprawda jest juz w README.md:148 -> pointer do Zad. 11. PRZYJMUJE.
Task 10: fix round 1/5 dispatch — wznowienie oryginalnego implementera (opus), FIX_BASE=f04cfb4
Task 10: fix round 1/5 — implementer DONE (commit 4b54dce; 1775 passed, ruff clean, mypy 32; `grep -rn "5,5 x 4,6" kartograf/ docs/` = 0 trafien). Zmierzyl sam (N-34-130-D-d-2-4 -> 2252,6 x 2432,4 m; kontrolnie M-34-76-A-a-1-1 -> 2255,4 x 2331,1 m), poprawil dokument I komentarz kodu, zlagodzil teze (pas nodata JEST mozliwy przy obiektach oddalonych o wiecej niz arkusz). `_parser.py` nie niosl ani liczby, ani tezy — nietkniety. Zmiana w kodzie to jeden hunk czysto komentarzowy (3-/7+), zero logiki.
Task 10: scoped re-review dispatch (sonnet), paczka review-f04cfb4..4b54dce.diff
Task 10: re-review 1/5 — WSZYSTKIE USTALENIA ZAMKNIETE (3 + wszystkie 5 drobiazgow). Re-reviewer zmierzyl arkusz sam (2252,6 x 2432,4 m — zgodne co do dziesiatych), potwierdzil grepem zero trafien starej liczby, zweryfikowal oba twierdzenia o selekcji arkuszy i o LAZ odczytem kodu, i potwierdzil ze `git diff -- kartograf/` to dokladnie jeden hunk czysto komentarzowy (3-/7+, zero instrukcji/sygnatur/stalych), a `git diff -- tests/` puste.
Task 10: minor (deferred, do Zad. 11): wiersz `extra` w tabeli sidecara (ARCHITECTURE.md:207) brzmi "parent_request, a dla LAZ takze godlo_kafla/..." — przy nieuwaznej lekturze mozna odczytac, jakby LAZ dostawal OBA klucze; sekcja 3.4 to prostuje, wiec nie falsz, ale warto doprecyzowac
Task 10: complete (commits c393a11..4b54dce, review clean po 1 rundzie naprawczej)
Task 11: dispatch (OPUS — 6 dokumentow naraz: ADR-026/027, CHANGELOG breaking, CLAUDE, README, SCOPE, PROGRESS), BASE=4b54dce
Task 11: implementer DONE (commit c5d0072; 1775 passed, ruff clean, mypy 32 bez zmian). Znalazl KOLEJNA nieprawde w gotowym tekscie briefu: zdanie do ADR-023 pkt 6 powolywalo sie na nieistniejaca "liste opcji nierozwiazywalnych z pkt 5", a `--target-crs` nigdy nie byl na liscie rozstrzygajacej kraj — zapisal zgodnie z `_pl_only_flags`. ODMOWIL napisania sekcji "Opcje" w ADR-026/027, bo brief jej nie dostarczyl, a zmyslanie wariantow byloby niesprawdzalnym twierdzeniem o historii decyzji. Naprawil 3 zlecone nieprawdy (README parent_request/LAZ, README transform.horizontal, ARCHITECTURE wiersz extra), kazda zweryfikowana na kodzie.
Task 11: review dispatch (opus), paczka review-4b54dce..c5d0072.diff
Task 11: review — SPEC OK, JAKOSC: CHANGES REQUESTED (3x Wazne, 3x Drobne). Potwierdzone mocne strony: 3 zlecone nieprawdy naprawione i zweryfikowane na kodzie; korekta falszywego tekstu briefu (ADR-023) trafna — `_pl_only_flags` (download_cmd.py:426-452) faktycznie nigdy nie zawieral --target-crs; falszywe twierdzenie o nodata NIE przeniknelo do zadnego z 7 plikow; bledny rozmiar arkusza nigdzie nie przepisany; ASCII zachowane.
Task 11: [Wazne] 1 — TABELA MIGRACJI zaklamuje `{uklad}` na sztywne `pl_1992` w dwoch wierszach (CHANGELOG.md:21 i :23 + blizniacze ARCHITECTURE.md:275,:277). Reviewer odtworzyl realnym FileStorage: `orto` + godlo 2000 -> `data/orto/pl_2000/...`, `5m` + godlo 2000 -> `data/nmt/pl_2000_5m_evrf2007/...`. Ta sama tabela poprawnie pisze `pl_<uklad>` dla nmpt i laz — czyli jest wewnetrznie niespojna. Skutek: uzytkownik z plikami orto albo NMT 5m z godel PL-2000 przeniesie je wg tabeli do katalogu, do ktorego Kartograf nigdy nie zajrzy -> pobierze je po raz drugi. PRZYJMUJE — to najbardziej weryfikowalny fragment zadania i dokladnie ta obietnica, ktora tabela ma spelniac.
Task 11: [Wazne] 2 — pominiecie sekcji "Opcje" w ADR-026/027 opiera sie na FALSZYWYM precedensie. Implementer napisal w raporcie "ADR-024 i ADR-025 jej nie maja"; reviewer pokazal, ze OBA maja pelne bloki `**Opcje:**` (DECISIONS.md:696 i :841), a 24 z 27 ADR-ow ja ma. Naglowek rejestru (DECISIONS.md:4) obiecuje "rozwazone opcje". PRZYJMUJE CZESCIOWO: sama odmowa ZMYSLANIA historii decyzji byla sluszna i podtrzymuje ja, ale material istnieje i jest sprawdzalny (spec zapisuje D1 jako "Wariant A"; Konsekwencje ADR-027 same nazywaja odrzucony wariant). Naprawa = odsylacz do sekcji 2 specu + przeniesienie juz udokumentowanych alternatyw, NIE wymyslanie nowych.
Task 11: [Wazne] 3 — status ADR-013 przeczy indeksowi: DECISIONS.md:218 nadal "Status: Przyjeta", a ARCHITECTURE.md:550 i sam ADR-026 mowia o zastapieniu. Konwencja rejestru zapisuje zastapienie w polu Status (precedens ADR-014, DECISIONS.md:237). Czytelnik skanujacy statusy widzi ADR-013 jako obowiazujacy. PRZYJMUJE.
Task 11: [Drobne->do naprawy] brak kwalifikatora `--target-crs` przy "wycinkach PL" (CLAUDE.md:114-116, SCOPE.md:272) oraz bezwarunkowe "PL zwraca liste arkuszy, CZ jeden plik" (CLAUDE.md:258, SCOPE.md:335) — od ADR-027 prawdziwe tylko BEZ flagi. Doklejam do rundy naprawczej: to ta sama klasa bledu (dokumentacja klamie o zachowaniu), ktora ten plan tropi od poczatku.
Task 11: minor (deferred -> Zad. 12): SCOPE.md:475 nadal "1716 testow" (jest 1775); brief zamrozil dla Zad. 12 tylko stopke README — Zad. 12 musi objac OBA pliki
Task 11: minor (deferred): CHANGELOG.md:648 (sekcja [0.5.0], brief zakazal ruszania) mowi w czasie terazniejszym "arkusze PL-2000 laduja w nmt_<res>/", a nowa korekta ADR-017 tam kieruje
Task 11: fix round 1/5 dispatch — wznowienie oryginalnego implementera (opus), FIX_BASE=c5d0072
Task 11: fix round 1/5 — implementer DONE (commit c75e9aa; 1775 passed, ruff clean, mypy 32; git diff --name-only = same .md). U1: oba wiersze poprawione w CHANGELOG I ARCHITECTURE (tabele zdiffowane jako identyczne), WSZYSTKIE wiersze odtworzone realnym FileStorage dla godla 1992 i 2000, dodane zdanie ze jeden stary katalog rozchodzi sie na dwa segmenty; potwierdzil tez, ze `_5m_evrf2007` slusznie zostaje SZTYWNE (fabryka koryguje KRON86->EVRF2007 przed FileStorage). U2: przyznal wprost, ze jego uzasadnienie bylo falszywe; sekcje Opcje dopisane wylacznie z materialu cytowalnego (D1/D2/D4/D5, D6 + spec sekcja 6), zero wymyslonych alternatyw. U3+U4: status ADR-013 poprawiony forma czesciowa wg precedensu; kwalifikator wycinka dodany w 4 wskazanych miejscach + w ARCHITECTURE 3.3 regula 3, ktora niosla te sama bezwarunkowa obietnice.
Task 11: minor (deferred, POZA ZAKRESEM PLANU): implementer zglasza, ze ADR-005 ma identyczny problem statusu co ADR-013. To niespojnosc SPRZED tego planu — nie rozszerzam zakresu, do triazu w finalnym review albo do backlogu.
Task 11: scoped re-review dispatch (sonnet), paczka review-c5d0072..c75e9aa.diff
Task 11: re-review 1/5 — WSZYSTKIE 4 USTALENIA ZAMKNIETE. Re-reviewer odtworzyl realnym FileStorage oba wiersze tabeli dla godel 1992 i 2000, potwierdzil wyjatek `_5m_evrf2007` (create_nmt_provider koryguje pion PRZED FileStorage, wiec segment `pl_*_5m_kron86` jest nieosiagalny normalnym przeplywem CLI), zdiffowal obie tabele jako identyczne, skontrolowal KAZDA pozycje nowych sekcji "Opcje" wobec specu (D1-D8 istnieja doslownie, zero wymyslonych alternatyw), potwierdzil precedens formy statusu ADR-013 (:274, :653, :990) i zweryfikowal wszystkie 5 miejsc kwalifikatora wycinka wobec download_cmd.py:1219 vs 1693-1707. Diff wylacznie 5 plikow .md, brak diakrytykow w nowych liniach plikow ASCII.
Task 11: complete (commits 4b54dce..c75e9aa, review clean po 1 rundzie naprawczej)
Task 12: dispatch (opus — brama jakosci + kryteria akceptacji 13.1-13.8), BASE=c75e9aa
Task 12: implementer DONE (commit a9afc3f; 1775 passed, pokrycie 93% (92,63%), ruff clean, mypy 32 — dowod przez DIFF LIST BLEDOW vs baseline ae6d072, nie przez sama liczbe). Brama: 8/8 kryteriow 13.1-13.8 SPELNIONYCH, 0 niespelnionych; sciezki 13.2-13.5 sprawdzone faktycznie (realny FileStorage/resolve_subdir + main() z zamockowana warstwa pobierania), walidacje 13.7 realnym CLI. 1 pozycja DO WERYFIKACJI LIVE: tresc wycinka PL na realnych arkuszach GUGiK (offline dowod jest syntetyczny — tak kwalifikuje to sam spec), zapisana jako rozszerzona checklista release w PROGRESS pkt 12 (a)-(e). Oba znane triaze naprawione (ADR-005, uwaga CHANGELOG [0.5.0]).
Task 12: ustalenia o kodzie (nienaprawiane, kod nietkniety): mypy storage.py:101 to dlug SPRZED planu mimo przebudowy pliku; `list_files()` przy szablonie {uklad} listuje oba uklady naraz (nieudokumentowane); warning fallbacku `_laz_uklad` idzie przez logging, nie na stderr jak reszta CLI
Task 12: review dispatch (sonnet), paczka review-c75e9aa..a9afc3f.diff
Task 12: review CZYSTY — SPEC OK, JAKOSC APPROVED. Reviewer odtworzyl metode diffu mypy przez osobny `git worktree` i potwierdzil: dokladnie 1 blad zniknal, 0 nowych; pozorna "nowosc" storage.py:101 to przesuniecie tego samego bledu z :96 w baseline, poprawnie rozpoznane po TRESCI komunikatu, nie po numerze linii. Odtworzyl od zera kryteria 13.2/13.4/13.7 wlasnym skryptem (mock wylacznie warstwy download + uruchomienie zainstalowanego .venv/bin/kartograf) — identyczne sciezki i komunikaty, wiec dowody nie sa odczytem z dokumentacji. Potwierdzil UCZCIWOSC kwalifikacji "live-only" (conftest strukturalnie blokuje gniazda, wiec dowod na realnych danych GUGiK jest offline fizycznie niemozliwy; dowod syntetyczny jest nietautologiczna asercja geometryczna).
Task 12: complete (commits c75e9aa..a9afc3f, review clean)
=== WSZYSTKIE 12 ZADAN ZAMKNIETE. Stan koncowy: 1775 testow PASS (start 1716), pokrycie 93%, mypy 32 (start 33), ruff clean. Kryteria akceptacji 13.1-13.8: 8/8 spelnionych, 1 pozycja do weryfikacji live przed tagiem. ===
Final review: pierwszy dispatch na fable PADL — wyczerpane kredyty uzycia Fable 5 ("You're out of usage credits"). Re-dispatch na opusa (najmocniejszy DOSTEPNY model) z tym samym briefem. Uwaga na przyszlosc: sprawdzony podzial rol z etapu 1 (fable = finalny review calej galezi) jest dzis niedostepny bez doladowania kredytow.

=== FINALNY REVIEW CALEJ GALEZI (opus, po padzie fable na kredytach) ===
Werdykt: GOTOWE PO NAPRAWACH. 1 Krytyczne, 7 Waznych, reszta drobne; triaz 21 pozycji: 8 do naprawy przed merge, 9 do backlogu, 4 nieaktualne/zalatwione.
Final: [KRYTYCZNE] gwarancja R-01 nie obowiazuje w trybie --geometry i NIE JEST BRONIONA w trybie --bbox. Dowod (a): mutacja `sheet_bbox = bbox` (usuniecie poszerzonego bboxa z selekcji) przechodzi 1775/1775 — jedyny test R-01 wola `_build_pl_cutout` wprost, podajac juz poszerzony bbox, wiec nie broni SELEKCJI. Dowod (b): w trybie geometry arkusze wybiera find_sheets_for_geometry PRZED zbudowaniem cutout, wiec zapas nigdy nie wplywa na selekcje; zmierzone 8,4% pikseli nodata (1475/17484) vs 0% w torze bbox, a powrot obwiedni celu do 2180 rosnie o ~7,5% boku na strone (20 km -> 1512 m).
Final: Ruling: KORYGUJE WLASNE WCZESNIEJSZE ROZSTRZYGNIECIE. W R-01 dla Zad. 9 kazalem NIE rozszerzac selekcji w trybie geometry (obawa o setki arkuszy przy rzadkiej geometrii wieloobiektowej). Pomiar pokazuje, ze kosztem tej oszczednosci jest ramka nodata na KRAWEDZIACH wyniku — takze tam, gdzie geometria dochodzi do obwiedni. Skoro wynik i tak obejmuje CALA obwiednie (tak stanowi dokumentacja po naprawie w Zad. 9), uczciwym domknieciem obietnicy jest wypelnienie jej danymi. Tryb --geometry --target-crs jest NOWY w tym wydaniu, wiec blast radius = 0. Koszt jesli zle: przy rzadkiej geometrii wieloobiektowej pobierze sie wiecej arkuszy — do odkrecenia jedna galezia warunku.
Final: Ruling: N-08 — usuwam `target_path.unlink(missing_ok=True)` z `_build_pl_cutout` zamiast dokumentowac utrate danych. Reviewer wykazal, ze linia jest ZBEDNA (obie galezie zapisu sa juz atomowe przez os.replace), a bez niej stary plik przetrwa nieudane odswiezenie; sciezka sukcesu nie zmienia sie ani o bit. Analogiczny unlink w transform/raster.py ZOSTAJE (kopia wzorca toru CZ, nietykalnego przed wydaniem).
Final: pozostale Wazne: N-02 (siodmy przypadek dokumentu opisujacego nieistniejace zachowanie — "zapas steruje siatka wyniku", a siatka idzie z bbox_target); N-03 (DownloadManager buduje segment z wlasnego pionu, nie providera -> KRON86 i EVRF2007 znow w jednym katalogu, osiagalne z API biblioteki); N-04 (FileStorage(vertical_crs="") -> cichy segment, CZWARTA eskalacja); N-05 (brak wpisow KNOWN_PATHS dla dwoch nowych par — galaz lamie regule, ktora sama spisala); N-06 (caly przeplyw 5 m niebroniony — 4 mutacje przechodza); N-07 (atomowosc zapisu i sprzatanie po awarii nieprzetestowane — 3 mutacje przechodza; scenariusz: polzapisany GeoTIFF uznany potem przez skip_existing za wazny cache).
Final: fala naprawcza — JEDNA, zbiorcza (opus), brief w final-fix-brief.md (N-01..N-11 + sekcja NIE RUSZAC), BASE=a9afc3f
Final: fala naprawcza DONE (f2bd0e4..03b5bac, 5 commitow; 1787 passed = 1775+12, ruff clean, mypy 32 baseline, pokrycie 92,74%, git status czysty). ZAMKNIETE 11 z 11 (N-01..N-11), zadna pozycja nie okazala sie niemozliwa; 21 dowodow mutacyjnych (A..U), kazda mutacja przywrocona.
Final: dwa swiadome odstepstwa fixera od litery briefu: N-03 uzywa `isinstance(str)` zamiast golego getattr (dla `Mock(spec=GugikProvider)` atrybut zwraca Mock i wywracal budowe sciezki) i ma DWA testy, bo mutacja "pion z providera" i mutacja "vertical_crs= w FileStorage" to dwie ROZNE dziury; N-05 wiaze tabele KNOWN_PATHS ze ZMIERZONA dokladnoscia (0.5 / 0.0), nie tylko z obecnoscia wpisu.
Final: Ruling: akceptuje literalny warunek `cutout.pinned is not None` w N-01. Dla celu EPSG:2180 `bbox_source_2180 is bbox_2180` (zapas zerowy), wiec nie ma ramki do wypelnienia — pozostale nodata w `--geometry --target-crs EPSG:2180` to zaprojektowana dziura MIEDZY rozlacznymi obiektami, nie artefakt zapasu. Fixer udokumentowal to jawnie w ARCHITECTURE 4.3. Koszt jesli zle: jeden warunek do poszerzenia.
Final: scoped re-review fali (opus) — JEDYNY, drugiej fali nie bedzie
Final: re-review fali — WSZYSTKIE 11 USTALEN ZAMKNIETE. Re-reviewer powtorzyl samodzielnie 16 mutacji (wiecej niz wymagane 5), kazda pada zgodnie z deklaracja; zmierzyl niezaleznie dokladnosci KNOWN_PATHS (2180->5514 = 0.5, 2180->3045 = 0.0, pyproj 3.7.2/PROJ 9.5.1) i potwierdzil tabele; potwierdzil (a) sume godel bez duplikatow i stabilna, (b) nietknieta sciezke bez --target-crs (broniona asercja TOZSAMOSCI obiektu), (c) prawdziwosc dokumentacji dla celu 2180. Odstepstwo N-03 (`isinstance(str)`) NIE maskuje przypadku produkcyjnego — wszystkie realne providery daja str, rozjazd dotyczy wylacznie `Mock(spec=...)`. Sekcja "NIE RUSZAC" respektowana w calosci; tor CZ, landcover i sciezka PL bez flagi czyste. Brama: 1787 passed, ruff clean, mypy 32, pokrycie 92,74%, drzewo czyste.
Final: [Wazne] NOWE, w samym diffie fali — OSMY przypadek klasy "dokument obiecuje zachowanie, ktorego kod nie ma", wprowadzony przez fale, ktora te klase zamykala. CHANGELOG (wpis 0.7.0) i ARCHITECTURE 4.3 mowia BEZWARUNKOWO "nieudana budowa wycinka NIE niszczy poprzedniego pliku", ale `_build_pl_cutout` deleguje zapis do `warp_to_grid`, ktora — zgodnie z moim rulingiem — zachowala `except BaseException: dst_path.unlink()`. Wiec dla `--target-crs EPSG:5514|EPSG:3045` (glowne zastosowanie flagi) awaria wewnatrz warpu NADAL kasuje poprzedni plik. Zmierzone przez re-reviewera bez patchowania warp_to_grid: "poprzedni wynik istnieje po awarii warpu: False". Test `test_failed_build_keeps_previous_result` mockuje `warp_to_grid`, wiec tej luki nie widzi.
Final: Ruling: MOJ RULING N-08 BYL POLOWICZNY. Kazalem zostawic `unlink` w transform/raster.py "bo to kopia wzorca toru CZ, ktorego przed wydaniem nie ruszamy" — to uzasadnienie bylo bledne: `transform/raster.py` jest modulem WYLACZNIE polskim (tor CZ ma wlasna kopie w providers/cuzk/dmr.py), wiec zdjecie tam `unlink` NIE dotyka toru czeskiego. Zostawilem asymetrie, ktora zamienila prawdziwa naprawe w polowiczna i uczynila dokumentacje falszywa.
Final: residual load-bearing -> zgodnie ze skillem NIE ma drugiej fali naprawczej; pozycja idzie do uzytkownika przy domykaniu galezi, z rekomendacja.
Final: minor (deferred): nowe `find_sheets_for_bbox` w `_download_pl_geometry:1989` bez try/except ValidationError (bliźniak w torze bbox ma) — praktycznie nieosiagalne, ale przeciek wyszedlby poza petle krajow
Final: minor (deferred): `descriptor.resolve_subdir` nadal podstawia pusty string (descriptor.py:99-100) — N-04 zalatane tylko w warstwie FileStorage; po N-03 nieosiagalne z realnym providerem
