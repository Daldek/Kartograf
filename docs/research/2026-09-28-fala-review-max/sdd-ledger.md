# SDD ledger — plan: docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md

Spec: docs/research/2026-08-28-uklad-data-target-crs-pl/2026-08-30-code-review-max.md + rozstrzygniecia R1-R6 i fakty 1-11 w planie (uzytkownik, 2026-09-28).
Baseline (HEAD 5b5ffa4, 2026-09-28): 1787 passed; mypy 32 bledy (lista: mypy-baseline.txt, bez numerow linii).
Ruling: praca bezposrednio na develop, bez worktree — CLAUDE.md ("ZAWSZE pracuj na develop") + Global Constraints planu, poprzednie fale tak samo — koszt pomylki: brak izolacji galezi (niski: commit per zadanie, nic nie pushujemy, historia do cofniecia).
Ruling: briefy wycinane wlasnym brief.sh (naglowki "### Zad. N:"), nie skryptem task-brief (szuka "Task N") — koszt pomylki: brak (ta sama tresc).
Ruling: reviewer zadania i re-reviewer wykonuja jedna kontrolowana mutacje w drzewie roboczym (wyjatek od read-only szablonu) — feedback uzytkownika "zadaj dowodow mutacyjnych, re-reviewerzy powtarzaja mutacje"; proces sekwencyjny, wiec bez kolizji — koszt pomylki: brudne drzewo, jesli reviewer nie przywroci (kontrola: git status po kazdym review).
Task 0: complete (commits 5b5ffa4..81e71cb — raport review f02f51c, plan 81e71cb; pamiec: feedback_design_questions.md + project_uklad_data_target_crs_pl.md)

## Pre-flight (opus, symulacja calego planu na kopii repo): preflight-report.md
Tabela par zadan (a) i samospojnosci zadan (b): w preflight-report.md sekcje (a)/(b). Wynik: 2 BLOCKING, 5 IMPORTANT, 14 MINOR; z poprawkami stan koncowy zielony (1835 passed, 8 live deselected), mypy = baseline.
Ruling: P-01 (Zad. 4/9/17) — przyjete: `_same_projection` (equals LUB rowny slownik PROJ) + test parametryzowany po WKT1_GDAL / WKT1_ESRI / tekscie .prj Hydrografu — powod: kazdy WKT1 EPSG:2180 (takze realny .prj Hydrografu) nie przechodzi `equals` — koszt pomylki: CRS o identycznych parametrach odwzorowania, ale innym opisie datum, przejdzie jako 2180 (dla ukladow PL bez znaczenia).
Ruling: P-02 (Zad. 9) — przyjete: test rampy porownuje wycinek z `warp_to_grid` idealnego rastra (bit-w-bit), Step 1a usuniety — powod: residuum ~2,6 cm to wlasnosc zamrozonego etapu warp GDAL, nie mozaiki — koszt pomylki: test nie mierzy bezwzglednej dokladnosci warpu (to nie jest cel tej fali; E2E 17(b) porownuje z niezaleznym warpem GDAL).
Ruling: P-03 (Zad. 12) — wariant A: w 10 istniejacych testach (lista w raporcie) patch `kartograf.core.geometry.read_source_crs` per test; `tests/test_pl_cutout.py` do plikow i commitu — powod: kod produkcyjny bez tolerancji "pod testy"; testy zostaja uczciwe — koszt pomylki: 10 edycji testow.
Ruling: P-04 (Zad. 8) — przyjete: `test_without_target_crs_behaviour_unchanged` zachowuje wlasne patche `_DL` — koszt: brak.
Ruling: P-05 (Zad. 4) — przyjete: zapas 64 w tescie deskryptorow VRT (160 maskowal mutacje; poprawny kod < 6) — koszt: brak.
Ruling: P-06 (Zad. 7) — przyjete: mutacja (3) w `_download_hierarchy_sequential` (wariant [1]) — koszt: brak.
Ruling: P-07 (Zad. 9) — parametryzacja obu kolejnosci `[a, b]` i `[b, a]` (RED na [a, b]) — koszt: brak.
Ruling: P-08..P-21 (MINOR) — przyjete wg tekstow z raportu; P-16: bramki `-m "not live"`, baseline OFFLINE = 1779 (1787 zawiera 8 testow sieciowych `live`) — koszt pomylki: brak.
Ruling: poprawki pre-flight nanoszone na plik planu (commit docs(plan)), briefy wycinane z poprawionego planu — jedno zrodlo wymagan zamiast "WIAZACYCH POPRAWEK" w dispatchach — koszt: jeden commit planu.
Task 1: dispatched (BASE 81e71cb, sonnet)
Task 1: complete (commits 81e71cb..d72ce37, review clean — sonnet review, weryfikacja twierdzen na kodzie + 2 testy regresyjne)
Plan: poprawki pre-flight zacommitowane (dbc5926); briefy 2-17 wyciete z poprawionego planu; COMMON-CONTEXT odswiezony
Task 2: dispatched (BASE dbc5926, sonnet)
Ruling: stopka Co-Authored-By w commitach subagentow = model, ktory pisze commit (wg ich system-remindera), nie sztywne 'Opus 5.5' z Global Constraints — atrybucja ma byc prawdziwa — koszt pomylki: kosmetyczny (stopki mieszane w historii).
Task 2: complete (commits dbc5926..26ab9cb, review clean — reviewer powtorzyl mutacje ExitStack: FAIL na t065.tif jak w raporcie)
Task 3: dispatched (BASE 26ab9cb, sonnet; review opus)
Task 3: implementer DONE (784ea47); incydent procesowy: git checkout na niezacommitowanym mosaic.py skasowal implementacje — odtworzona z wczesniejszego Read; review (opus) porownuje kod z briefem linia po linii. Regula w IMPLEMENTER_COMMON: mutacje tylko po commicie.
Task 3: minor (deferred): tolerancja floor(q + tol) w _snap_outward bez testu lustrzanego (dolna krawedz na siatce z szumem FP, np. BBox(0.7,0.5,1.0,1.0) na siatce 0.1 -> szerokosc 4); remis 'pierwsze w kolejnosci' bez testu
Task 3: minor (deferred): _snap_outward nie odrzuca zrodla odbitego (t.a <= 0 or t.e >= 0) — dzis nieosiagalne (GUGiK polnocne, CZ bez snap)
Task 3: complete (commits 26ab9cb..784ea47, review clean — opus: kod = brief na poziomie AST, 840 prob FP bez bledu; 2 minory odlozone)
Task 4: dispatched (BASE 784ea47, opus; review opus)
Ruling: Zad. 4 — VRT <NoDataValue> = nodata ZRODLA (meta["nodata"]), nie nodata mozaiki (odstepstwo od briefu) — wersja z briefu odslanialaby -9999 zrodla i w zakladce przykrywala wazne dane (dowod: test_wrapping_keeps_each_source_own_nodata); dla PL (nodata -9999 = zrodlo) wynik identyczny — koszt pomylki: brak znany.
Task 4: minor (deferred): _same_projection dla .prj WKT1_ESRI kosztuje ~25 ms/zrodlo (~30 s na 1200 arkuszy; .prj Hydrografu 0,28 ms) — kandydat na lru_cache po tekscie WKT
Task 4: minor (deferred): owijanie VRT dziedziczy uklad blokow VRT (min(128,w) x min(128,h)); pierwsze zrodlo szersze niz 128 px i nizsze niz 128 px z wysokoscia niepodzielna przez 16 -> RasterBlockError przy zapisie (np. 200x100); poprawka: kwds.setdefault('tiled', False) przy owijaniu; realne arkusze GUGiK (min 407x432) bezpieczne — pulapka do przekazania Zad. 9/11
Task 4: minor (deferred): komentarz testu fd (tests/test_transport_mosaic.py:417-419) — prog maskowania to 100, a test lapie przekazanie OTWARTYCH VRT do merge (nie samo trzymanie ich otwartych)
Task 4: minor (deferred): docstring mosaic.py:174 'maskowanie takie jak bez owijania' — prawda tylko dla nodata; zrodlo z wewnetrznym pasmem maski traci maske w VRT (ASC nie dotyczy)
Task 4: minor (deferred): _same_projection odrzuca WKT1 EPSG:2180 z TOWGS84[0,...] (stary GDAL 2.x) z komunikatem 'ma CRS EPSG:2180, a wymuszany jest EPSG:2180'; mozliwy trzeci fallback na to_epsg()
Task 4: minor (deferred): testy owijania na malych wspolrzednych — brak testu owijania+snap na realnych wspolrzednych PUWG-92 (pokrywa Zad. 9)
Task 4: complete (commits 784ea47..dc45432, review clean — opus: odstepstwo nodata przyjete, mutacja 4b odtworzona, CZ bajt-w-bajt)
Task 5: dispatched (BASE dc45432, sonnet; review sonnet)
Task 5: complete (commits dc45432..8c124fc, review clean — sonnet: naprawa dokladna (0 punktow poza obwiednia, 9 bboxow x 2001 probek), mutacja odtworzona)
Task 6: dispatched (BASE 8c124fc, sonnet; review sonnet)
Task 6: minor (deferred): docstring publicznej GugikProvider.download() (gugik.py:406-409) wymienia w Raises tylko DownloadError — bez wzmianki o NoCoverageError
Task 6: complete (commits 8c124fc..2856f41, review clean — sonnet: klasyfikacja trojstanowa wyczerpujaca, no_coverage ⊆ failed strukturalnie, mutacja odtworzona)
Task 7: dispatched (BASE 2856f41, sonnet; review sonnet)
Task 7: minor (deferred): docstring klasy DownloadManager (manager.py:122-126) — last_result 'set only by download_hierarchy' nieaktualne (ustawia tez download_sheets)
Task 7: minor (deferred): download_sheets parsuje kazdy lisc dwa razy (expand_sheets + SheetParser) — nieszkodliwe
Task 7: complete (commits 2856f41..3ce32a1, review clean — sonnet: reuse maszynerii hierarchii, mutacja dedup odtworzona 3/4)
Task 8: dispatched (BASE 3ce32a1, opus; review opus)
Ruling: Zad. 8 — zachowany pusty print() przed 'Downloaded to' w _download_pl_cutout (odstepstwo od kodu briefu) — bez niego linia podsumowania zlewa sie z paskiem postepu, gdy ostatni arkusz byl z cache — koszt: brak.
Ruling: Zad. 8 — kontrola 'No sheets found for the given geometry' po sumie R-01 (kod briefu) — rozni sie tylko dla zdegenerowanej geometrii — koszt: inny komunikat w przypadku brzegowym.
Task 8: minor (deferred): _CZ_CRS w download/cutout.py porownuje stringi doslownie — wywolanie biblioteczne z 'epsg:5514' pojdzie niepinowana transformacja; kandydat na wkid()
Task 8: note for Zad. 17: stare nazwy prywatnych funkcji/stalych w docs/ARCHITECTURE.md 4.3 (l.360-361, 370, 404) i docs/DECISIONS.md:1035 — do przepisania w Zad. 17
Task 8: review (opus) = Needs fixes: Important 1 (plan-mandated): run_pl_cutout ufa cutout.vertical_crs/resolution zamiast wstrzyknietego providera -> arkusze KRON86 w segmencie evrf2007 (zmierzone); poprawka: ValidationError przy niezgodnosci + test
Ruling: Task 8 Important 1 (plan-mandated) — naprawiamy: regula projektu 'segment niesie pion FAKTYCZNY providera' (ADR-026, manager.py) jest nadrzedna wobec kodu planu — koszt pomylki: odrzucenie wolania z providerem o innej rozdzielczosci/pionie, ktore i tak dawaloby zly cache.
Ruling: Task 8 minory 2A-2C (testy: reuse cache arkuszy przy force=False, sidecar_extra/parent_request w arkuszach toru wycinka, regula 5m=>EVRF2007 w download_pl_cutout) + asercja listy wszystkich nieudanych arkuszy — WCHODZA do rundy naprawczej 1 razem z Important 1 (odstepstwo od 'minory poza petla'): Zad. 9-11 przerabiaja run_pl_cutout, a bez tych testow regresja przeszlaby niezauwazona (feedback uzytkownika: dowody mutacyjne) — koszt: kilka testow.
Task 8: minor (deferred): duplikacja walidacji parametrow download_pl_cutout vs prepare_pl_cutout (cutout.py:424-429 vs 145-150) i wyrazenia klucza deskryptora (plan-mandated)
Task 8: fix round 1/5 dispatched (resume implementera; FIX_BASE c00a426)
Ruling: Task 8 — kontrola zgodnosci providera z wycinkiem przed skrotem 'plik istnieje' (niezgodny provider = blad zawsze, takze gdy wycinek istnieje) — bledna konfiguracja ma byc glosna — koszt: wolajacy z niezgodnym providerem nie dostanie 'skipped'.
Task 8: fix round 1/5 (5 addressed, 0 open — provider/cutout mismatch guard; testy 2A-2D; commits c00a426..96a57de)
Task 8: minor (deferred): run_pl_cutout nie waliduje wstrzyknietej storage wobec wycinka (jak DownloadManager)
Task 8: complete (commits 3ce32a1..96a57de, review clean po rundzie 1)
Task 9: dispatched (BASE 96a57de, opus; review opus)
Ruling: Zad. 9 — tryb --geometry + EPSG:2180 BEZ zapasu 1 px w selekcji (brak sumy R-01) — mozliwa kolumna nodata (<1 px) na brzegu obwiedni, zgodna z kontraktem 'nodata tylko tam, gdzie nie siega pobrany arkusz'; dopisac do ARCHITECTURE 4.3 w Zad. 17 — koszt pomylki: skrajna kolumna nodata w rzadkim trybie.
Task 9: note: implementer zastosowal poprawke pulapki blokow VRT (kwds.setdefault('tiled', False) przy owijaniu, commit f2cee75, 3 testy) — minor z Zad. 4 zamkniety
Task 9: minor (deferred -> Zad. 17): CHANGELOG ### Changed 'Selekcja arkuszy wycinka ma zapas 1 piksela' bez kwalifikatora — dopisac '(tryb bbox i suma R-01)'; geometry+EPSG:2180 bez zapasu (ruling wyzej)
Task 9: minor (deferred): komunikat ValidationError PL-2000 w bibliotece wspomina flagi CLI (--target-crs, --system 2000)
Task 9: minor (deferred): kolejnosc 'odrzut PL-2000 przed mkdir' nie broniona testem (opcjonalna asercja braku katalogu bbox/ w tescie CLI PL-2000)
Task 9: complete (commits 96a57de..924157c, review clean — opus: mutacja snap odtworzona 12325/12325, maks. 0,639 m)
Task 10: dispatched (BASE 924157c, opus; review opus)
Task 10: minor (deferred): podwojne linie stderr w wycinku — per-arkusz logger.warning('No data for ...') z managera (Zad. 6) + zbiorczy Warning: z CLI
Task 10: note (checklista live, Zad. 17): arkusz poza pokryciem, dla ktorego skorowidz zwraca URL INNEGO arkusza (fallback), nie staje sie NoCoverageError — pobiera sie jako inny arkusz (PL-2000 lapie straz z Zad. 9, ten sam uklad — nie)
Task 10: note for Zad. 17: stale docs/ARCHITECTURE.md:386 i docs/SCOPE.md:339 (kazdy failed arkusz = kod 1)
Task 10: minor (deferred): brak testu jednoczesnej obecnosci parent_request + missing_sheets w sidecarze (tests/test_pl_cutout.py:779) i asercji braku katalogu w test_all_sheets_without_data_is_an_error (:1469)
Task 10: DEFERRED-LOAD-BEARING (naprawic w fali finalnej): gugik._get_opendata_url traktuje odpowiedz 2xx bez URL (np. OGC ServiceExceptionReport / strona bledu proxy z HTTP 200) jako NoCoverageError -> przy R5 trwala dziura nodata po chwilowym bledzie; tania straz: body z 'ServiceException' (lub nie-HTML) = blad transportu
Task 10: minor (deferred, ruling w fali finalnej): per-arkusz logger.warning('No data for ...') w managerze (Zad. 6) zalewa stderr w wycinku (lastResort, -q nie tlumi) — propozycja: INFO dla NoCoverageError
Task 10: minor (deferred): run_pl_cutout z pustym PlCutoutSheets -> 'GUGiK nie ma danych dla zadnego z 0 arkuszy' (obwinia GUGiK za puste zadanie); docstring CLI nie mowi, ze brak danych we WSZYSTKICH arkuszach = kod 1
Task 10: note (checklista live): czy GUGiK odpowiada na arkusze po stronie czeskiej / nad morzem czysta pusta odpowiedzia GetFeatureInfo (przeslanka R5)
Task 10: complete (commits 924157c..608a386, review clean — opus: klasyfikacja, CLI, sidecar i ADR sprawdzone na kodzie; mutacja fatal=failed odtworzona 4/4)
Task 11: dispatched (BASE 608a386, sonnet; review sonnet)
Task 11: minor (deferred): grid_shape/estimated_bytes dla EPSG:2180 licza z nieprzyciagnietego bbox_target (wynik rosnie o <1 px/strone przez snap) — pomijalne
Task 11: complete (commits 608a386..209ca14, review clean — sonnet: mutacja kontroli dysku odtworzona)
Task 12: dispatched (BASE 209ca14, sonnet; review sonnet)
Ruling: Task 12 Important (plan-mandated) — duplikacja 3-liniowego idiomu 'obwiednia w ukladzie pliku + etykieta EPSG' w _geometry_envelope (download_cmd.py:604-609) i _resolve_cz_geometry_bbox (:578-583) — odlozone do fali finalnej (kandydat na wspolny helper) — powod: sasiednie funkcje, rozne dalsze kroki, niskie ryzyko — koszt pomylki: przyszla poprawka idiomu w dwoch miejscach.
Task 12: minor (deferred): wykrycie CRS czeskiego przez to_epsg() — .prj ESRI dla Krovaka moze nie dac 5514 i cicho wpasc w sciezke niepinowana (to samo ograniczenie co w rodzenstwie i wkid())
Task 12: minor (deferred): kazde --geometry czyta CRS pliku dwa razy (koszt pomijalny)
Task 12: complete (commits 209ca14..b3477f4, review clean — sonnet: mutacja odtworzona, roznica 1,155 m)
Task 13: dispatched (BASE b3477f4, sonnet; review sonnet)
Task 13: minor (deferred): prune_empty_dirs wywolane w dwoch galeziach except w _cz_download_bbox (download_cmd.py:1582, 1585-1587) — plan-mandated, trywialne
Task 13: complete (commits b3477f4..d4632ab, review clean — sonnet: mutacja try/except odtworzona; tor CZ bez zmian)
Task 14: dispatched (BASE d4632ab, sonnet; review sonnet)
Task 14: complete (commits d4632ab..3a3e863, review clean — sonnet: 5 wolajacych sprawdzonych, mutacja odtworzona 4/4)
Task 15: dispatched (BASE 3a3e863, sonnet; review sonnet)
Task 15: complete (commits 3a3e863..2f4c4b1, review clean — sonnet: kaskada 1:1, mutacja get_raw_path odtworzona 3/3; ARCHITECTURE 4.7 poprawione przy okazji)
Task 16: dispatched (BASE 2f4c4b1, sonnet; review sonnet)
Task 16: minor (deferred): galaz passthrough rozdzielczosci w FileStorage._subdir nieosiagalna (walidacja SUPPORTED_RESOLUTIONS) — sprzed tej fali
Task 16: complete (commits 2f4c4b1..6e49687, review clean — sonnet: szablony = rejestr znak w znak, mutacja odtworzona)
Task 17: dispatched (BASE 6e49687, opus; review opus)
Task 17: note (backlog): GDAL dobiera skale przeprobkowania per kawalek (XSCALE/YSCALE) — wartosci warpu zaleza lekko od zasiegu mozaiki (E2E: srednio 2,7 mm, maks. 0,15 m wobec niezaleznego warpu per arkusz; przy XSCALE=YSCALE=1 < 3,2 mm); dotyczy tez toru CZ — kandydat etapu 2
Task 17: minor (deferred): komenda 'pytest tests/' w CLAUDE.md/README uruchamia tez 8 testow sieciowych live (bramka offline = -m 'not live')
Task 17: review (opus) = Approved (0 Critical/0 Important); E2E odtworzone niezaleznie (JSON 0 roznic poza czasami; SHA-256 182 plikow cache Hydrografu bez zmian); graf importow zgodny z AST; 12 twierdzen docs sprawdzonych na kodzie
Task 17: minor (controller, Zakonczenie): PROGRESS — linia E2E, checklista live (f)-(j) (wskazniki 'checklista live' w ARCHITECTURE.md:481/:502 nie maja jeszcze celu), nieaktualne PROGRESS.md:720-721 ('offline sprawdzone tylko na siatce syntetycznej'), liczby 1854 / 92,9 %
Task 17: minor (deferred -> fala finalna): ARCHITECTURE.md:596-598 — cytat E2E (e) w 'Nieudana budowa a poprzedni wynik' nic nie dowodzi (porazka POBRANIA rzuca przed build_pl_cutout); usunac nawias albo prawdziwa porazka budowy
Task 17: minor (deferred -> fala finalna): ARCHITECTURE.md:458/:473 — 'porazka arkusza nie przerywa listy / kazda inna = DownloadError' prawdziwe dla rodziny DownloadError; sekwencyjnie (max_workers=1, domyslne w bibliotece) OSError zapisu wylatuje z download_sheets/run_pl_cutout jako OSError (rownolegle — zbierane); :400 'zamienia KAZDY wyjatek przygotowania, selekcji' — prepare lapie tylko TransformError/ValidationError, select tylko ValidationError
Task 17: minor (deferred -> fala finalna): ARCHITECTURE.md:283/:556 '< 0,5 px' -> 'do 0,5 px' (round half-to-even, max(1,...)); :543 '0 z 80 601' dotyczy bboxa calkowitego (ulamkowy: 0 z 79 799)
Task 17: note: E2E przez prepare/select/run zamiast download_pl_cutout (brak parametru provider w download_pl_cutout) — kompozycja download_pl_cutout (regula 5m=>EVRF2007, wczesny skrot) pokryta testami jednostkowymi, nie E2E
Task 17: complete (commits 6e49687..84bd0a8, review clean — opus; minory do fali finalnej/Zakonczenia)
Final: review calej fali dispatched (81e71cb..84bd0a8, pakiet review-final-81e71cb..84bd0a8.diff, brief FINAL-REVIEW-BRIEF.md; model fable, fallback opus)
Final: review (fable) = With fixes — 0 Critical / 2 Important / 11 Minor (final-review-report.md); I-1: wiazanie --force/--workers CLI -> run_pl_cutout niebronione (mutacja force=False przechodzi 312/312, --force = cichy no-op); I-2: DEFERRED-LOAD-BEARING potwierdzony (2xx bez URL = NoCoverageError); triaz ledgera: 9 NAPRAW TERAZ; tor CZ bajt w bajt, Hydrograf bez trafien, ~25 twierdzen docs prawdziwych
Ruling: fala finalna = JEDEN dispatch (opus): I-1+m-1, I-2, m-2 (_CZ_CRS niezalezne od wielkosci liter), m-6/m-7 (docstringi), m-8 (komendy testow), m-9a/b/c (precyzja ARCHITECTURE 4.3), m-10 (jedno zdanie o zaleznosci download -> providers.cuzk.dmr.bbox_to_crs); PROGRESS/artefakty/pamiec = kontroler (Zakonczenie planu) — powod: triaz NAPRAW TERAZ reviewera + tanie poprawki w tym samym pliku — koszt pomylki: nieco wiekszy diff fali.
Ruling: I-2 — straz WYLACZNIE negatywna: odpowiedz 2xx BEZ URL, ktorej body zawiera 'ServiceException' albo 'ExceptionReport', liczy sie do transport_errors (-> 'unavailable' albo 'niepewny', nigdy NoCoverageError); URL w odpowiedzi zawsze wygrywa; bez kontroli Content-Type i bez kontroli pozytywnej ('brak <html' = blad) przed checklista live — powod: realnej pustej odpowiedzi GetFeatureInfo nikt nie zapisal, kontrola pozytywna moglaby zamienic KAZDY brak pokrycia w kod 1 (R5 zlamane w druga strone); realny wyzwalacz: nieaktualna nazwa warstwy przy nieudanym GetCapabilities -> LayerNotDefined z HTTP 200 — koszt pomylki: strona bledu z 200 bez znacznikow OGC nadal liczy sie jako brak pokrycia (widoczne: Warning: + missing_sheets).
Ruling: m-11 — per-arkusz logger.warning('No data for ...') w DownloadManager ZOSTAJE WARNING (zamyka 'ruling w fali finalnej' z Zad. 10) — powod: tryby listy arkuszy (bez --target-crs) nie maja innego sygnalu per arkusz — koszt pomylki: glosny stderr przy wycinkach na wybrzezu.
Ruling: m-3 (kontrola dysku po stalym '.asc'), m-4 (arkusze spoza siatki wiekszosci -> extra.off_grid_sheets + Warning: po checkliscie live (f)), m-5 (download_pl_cutout(provider=, storage=) addytywnie), przeniesienie bbox_to_crs do transform/ (etap 2, dotyka CZ) oraz 'pobranie ASC bez kontroli Content-Type — strona bledu z 200 zapisana jako .asc zostaje w cache' (Declined reviewera) -> backlog w PROGRESS — powod: addytywne API / zalezne od checklisty live / dotyka zamrozonego toru CZ albo transportu — koszt pomylki: Hydrograf sklada trzy kroki, zeby wstrzyknac providera.
Ruling: m-8 — domyslne komendy testow w CLAUDE.md/README z -m "not live" + osobna, jawna linia dla testow live — powod: CLAUDE.md deklaruje testy offline, bramka P-16 jest offline; mozliwosc uruchomienia live zostaje udokumentowana — koszt pomylki: przyszle sesje domyslnie pomijaja 8 testow sieciowych.
Ruling: pozycje triazu ZOSTAW / JUZ NIEAKTUALNE (final-review-report.md, sekcja 'Triaz ledgera') przyjete z uzasadnieniami reviewera; warte sladu trafiaja do backlogu PROGRESS — koszt pomylki: drobny dlug techniczny.
Final: fala naprawcza dispatched (FIX_BASE 84bd0a8, opus; brief final-fix-brief.md, raport final-fix-report.md)
Final: fala naprawcza DONE_WITH_CONCERNS (commits 84bd0a8..61f60de: 899001f test --force/--workers, 89d4694 straz OGC 2xx, 5f25f4c _CZ_CRS niezalezne od wielkosci liter, 83b4a96 docstringi, e98016c komendy testow offline, 61f60de ARCHITECTURE 4.3/2); 1861 passed + 8 deselected, pokrycie 92,92 %, mypy = baseline, tor CZ 74 PASS; poza litera briefu (do oceny re-reviewera): docstringi 'never raise' download_sheets/run_pl_cutout, test 'URL wygrywa', wyciag OGC regexem
Final: note (proces): nieswiezy .pyc po git checkout przy mutacji zachowujacej rozmiar pliku w tej samej sekundzie (pyc waliduje mtime w sekundach + rozmiar) — mutacje uruchamiac z PYTHONPYCACHEPREFIX=$(mktemp -d); dopisane do REREVIEW_COMMON
Final: note (Zakonczenie): liczby testow 1854 w README/CHANGELOG/SCOPE -> 1861 / 92,92 % (commit zamykajacy kontrolera)
Final: scoped re-review dispatched (review-84bd0a8..61f60de.diff, opus)
Final: re-review (opus) = All findings addressed (6/6), brak nowych Critical/Important; reviewer powtorzyl 6 mutacji (swiezy pycache) + wlasna N-1 (przezywa 1861/1861); brama na 61f60de: 1861 passed + 8 deselected, ruff czysty, mypy lista = baseline, CZ/raster/PROGRESS bez zmian
Ruling: N-1 (test 'URL wygrywa' broni tylko URL z godlem; straz wstawiona przed fallbackiem 'URL innego arkusza' przezywa suite) — zaparkowane -> backlog (parametr testu: odpowiedz fallbackowa + znacznik OGC) — powod: dzisiejszy kod poprawny, realna odpowiedz z URL nie niesie znacznikow OGC — koszt pomylki: przyszly refaktor moglby odrzucac odpowiedzi fallbackowe (glosno: blad warstwy, kod 1).
Ruling: N-2 (regex wyciagu OGC kwadratowy dla patologicznego body bez '</': 360 KB -> 49 s) — zaparkowane -> backlog (ograniczenie '.{0,2000}?' albo prefiks body) — powod: wymaga patologicznej odpowiedzi 2xx bez URL; realne ksztalty 4 ms / 560 KB — koszt pomylki: wolne zapytanie warstwy przy patologicznej odpowiedzi.
Ruling: N-3 (nawias ARCHITECTURE 4.3 'przy wejsciu zwalidowanym przez CLI nie wystepuje' — kontrprzyklad --bbox nan/inf) — zaparkowane -> backlog 'walidacja --bbox: NaN/inf i min > max' (luka sprzed fali; opis skutku w docs dokladny) — koszt pomylki: nieprecyzyjny nawias do czasu walidacji.
Ruling: N-4 (komentarz testu 'Cieszyn (PL)' — bbox lezy po stronie CZ) i nit ARCHITECTURE 3.3 ('do 0,5 px' bez zastrzezenia max(1,...), ktore jest w 4.3) — zaparkowane jako nity bez wplywu na zachowanie — koszt pomylki: mylacy komentarz w tescie.
Ruling: synchronizacja liczb testow (README/CHANGELOG/SCOPE: 1854 -> 1861 offline + 8 live, pokrycie 92,9 %) w commicie zamykajacym kontrolera — powod: ksiegowosc Zakonczenia (liczby zmierzone przez implementera i re-reviewera), nie znalezisko review — koszt pomylki: brak.
Final: complete (commits 84bd0a8..61f60de, re-review clean, 4 minory zaparkowane z rulingami)
Zakonczenie: brama koncowa kontrolera na 61f60de (swiezy pycache): 1861 passed + 8 deselected, pokrycie 92,92 %, ruff/format czyste, mypy lista = baseline (32), smoke CLI --help/--target-crs choices i importy publiczne OK; PROGRESS (sekcja sesji, pkt 2/3/12/13, backlog), liczby testow README/CHANGELOG/SCOPE -> 1861, artefakty -> docs/research/2026-09-28-fala-review-max/, pamiec; commit zamykajacy docs(progress)
