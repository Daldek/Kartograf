# Zad. 17 — raport implementera (opus)

**Status:** DONE_WITH_CONCERNS — dokumentacja, E2E i brama zamkniete; E2E nie wykazal defektu kodu tej fali, ale ujawnil dwie wlasnosci warpa (zamrozonego), ktore wymagaja decyzji kontrolera (sekcja "Watpliwosci").

BASE `08fb3d5` -> HEAD `fa1f771`:

| SHA | Temat |
|---|---|
| `fa1f771` | docs: synchronizacja po fali review max — wycinek PL (siatka arkuszy, R5, API biblioteki) |

Zero zmian w kodzie produkcyjnym i testach (`git show --stat HEAD`: wylacznie CLAUDE.md, README.md, docs/ARCHITECTURE.md, docs/CHANGELOG.md, docs/DECISIONS.md, docs/SCOPE.md). PROGRESS.md i ledger — nietkniete (liczby nizej sa dla kontrolera).

## Co zrobiono

### Step 1 — `docs/ARCHITECTURE.md`
- **4.3 przepisana w calosci** (8 krokow + "Nieudana budowa a poprzedni wynik" + `--geometry` + wylaczenia + wynik): API biblioteki (`download_pl_cutout`; kroki `prepare_pl_cutout` -> `select_pl_cutout_sheets` -> `run_pl_cutout`, typy wyniku), CLI jako nakladka (`_download_pl_cutout`, kazdy wyjatek = kod 1); (1) fail-fast (walidacje, pinned, skrot "plik istnieje" — CLI/`download_pl_cutout` przed selekcja, `run_pl_cutout` na wejsciu — i kontrola zgodnosci providera PRZED skrotem); (2) zapas zrodla `WARP_MARGIN_PX = 4`; (3) selekcja z +1 px (bbox i suma R-01), **`--geometry` + `EPSG:2180` bez zapasu 1 px** (ruling kontrolera, mozliwa skrajna kolumna/wiersz nodata), R-01 bez zmian z uzasadnieniem R2; (4) arkusze jako cache, R5 (NoCoverageError -> nodata + `missing_sheets`; logi: zbiorczy INFO w `run_pl_cutout` + per arkusz WARNING `No data for ...` z `DownloadManager`; CLI `Warning:` do 10 godel), inne porazki = `DownloadError`, zaden arkusz = `ValidationError`; znana luka fallbacku URL innego arkusza (checklista live); (5) mozaika: `_reject_pl2000_sheets`, siatka wiekszosci + ostrzezenie, VRT EPSG:2180/Float32 z `<NoDataValue>` = nodata ZRODLA, `tiled=False` domyslnie przy owijaniu, sortowanie, leniwe otwieranie; (6) crop 1:1 dla 2180 / `warp_to_grid` bez zmian; (7) kompresja pliku posredniego (kafle 512 tylko tam), kontrola dysku (dolne oszacowanie), `Info:` >= 1 GiB; (8) sidecar z biblioteki. Liczby: fakty planu, raport review max, pomiary E2E z tego zadania.
- Poza 4.3 (wszystko sprawdzone na kodzie): data dokumentu; sekcja 1 (sidecar wycinka pisze biblioteka); **sekcja 2 — graf importow zmierzony na nowo AST** (`download -> transform, transport` wylacznie w `cutout.py`; CLI nie importuje juz `transport`, z `transform` bierze tylko `TransformError`) — stare zdanie "download NIE importuje transport ani transform ... mozaika i warp zyja w CLI" bylo falszywe; drzewo modulow (`cutout.py`, `NoCoverageError`, `mosaic.py`, `download_sheets`); 3.1 (wiersz wycinka); 3.2 (`extra.missing_sheets`, rekord sklada `write_pl_cutout_sidecar`, `request` = `bbox_target`); 3.3 pkt 3 (nazwa = zadanie, nie dokladny zasieg rastra); indeks ADR (ADR-003, ADR-027).

### Step 2 — ADR-027 (`docs/DECISIONS.md`)
Drugie uzupelnienie "2026-09-28 (R1, R3, fakty 5-8 ...)": siatka arkuszy (2180 + crop mozaiki przy warpie, zapas 1 px, E2E 0/80 601, przebudowa `--force`), normalizacja VRT (fakty 5-6), glosny blad PL-2000 (fakt 7, etap 2), selekcja przy 19°E (fakt 8), API biblioteki (R3, odrzut niezgodnego providera), R-01 bez zmian (R2), scalanie PL+CZ = etap 2 (R6), rozmiar (zn. 9). W Decyzji — odsylacze przy zdaniach nieaktualnych ("sam crop", "kazdy failed arkusz", "Sidecar pisze CLI"), `_PL_WARP_MARGIN_PX` -> `WARP_MARGIN_PX` (`download/cutout.py`, stara nazwa jako historyczna), Status z dopiskiem o uzupelnieniach.

### Step 3 — CLAUDE.md, README.md, SCOPE.md (+ CHANGELOG)
- CLAUDE.md: drzewo (NoCoverageError, mosaic snap/VRT, cutout R5, manager download_sheets), wskazowka EVRF2007 z bboxa (`--target-crs` / `download_pl_cutout`), punkt `--target-crs` PL (API biblioteki, VRT/mieszany cache, kontrola dysku + `Info:`, brak zapasu 1 px dla `--geometry`+2180, odsylacz do 4.3).
- README: przyklad `result.missing_sheets`, wskazowka `download_pl_cutout()` przy WCS, wiersz `extra.missing_sheets` w tabeli sidecara, kto pisze sidecary, funkcjonalnosc "Wycinek bbox", drzewo, liczby testow.
- SCOPE (3.8 -> 3.10; naglowek byl nieaktualny wzgledem stopki 3.9): 2.1 (API, siatka, R5), 2.10 (eksporty wycinka + `NoCoverageError`), 3.1 FUTURE (R6, wycinek z arkuszy PL-2000), 3.2 (l.339: R5 zamiast "failed arkusz = kod 1"), 4.1 drzewo, 6.2 liczby, historia.
- CHANGELOG: `### Changed` — kwalifikator "(tryb bbox i suma R-01)" + zdanie o braku zapasu dla `--geometry`+2180; `### Added` — brakujacy wpis `mosaic_and_crop(snap_to_source_grid=, assign_crs=, dtype=)` (spojnosc sekcji: bylo tylko `dst_kwds=`); wpis `--target-crs` — "sam crop na siatce arkuszy"; `### Tests` — nowy stan + historia + E2E.

**Grep z briefu (Step 3) — pozostale trafienia, kazde uzasadnione:**
| Trafienie | Uzasadnienie |
|---|---|
| DECISIONS.md:1023 `EPSG:2180 = sam crop` | tekst Decyzji 2026-08-28 z dopiskiem "od 2026-09-28 crop na siatce arkuszy — drugie uzupelnienie nizej" |
| DECISIONS.md:1025 `kazdy failed arkusz` | j.w., dopisek "zmienione 2026-09-28 ... uzupelnienie R5 nizej" |
| DECISIONS.md:1040 `_PL_WARP_MARGIN_PX` | tylko jako nazwa historyczna ("do 2026-09-28 stala CLI") obok aktualnej `WARP_MARGIN_PX` |
| DECISIONS.md:1071 `kazdy failed arkusz` | cytat w uzupelnieniu R5 ("Zastepuje ...") — poprawny |
| PROGRESS.md:100, 122, 136 | datowana sekcja sesji 2026-08-28 (rekord historyczny); PROGRESS aktualizuje kontroler na koniec fali — nietkniete |
| CHANGELOG `sam crop` (Added) | prawda (bez warpa); dopisane "na siatce arkuszy" |
| CLAUDE.md `sam crop` | zmienione na "crop bez warpa na siatce arkuszy" |
`_laz_uklad`, `_prepare_pl_cutout`, `_build_pl_cutout`, `_finalize_pl_cutout`, `odswiez albo nic` — zero trafien w CLAUDE/README/SCOPE/ARCHITECTURE/DECISIONS/CHANGELOG/PRD po zmianach. PRD.md przejrzany — nic o wycinku.

## Weryfikacja twierdzen na zywym kodzie (regula 5)
- Graf importow: skrypt AST (scratchpad `imports.py`) — krawedzie miedzypakietowe top-level vs leniwe; `grep` potwierdza: CLI importuje z `transform` tylko `TransformError`, z `transport` nic; `manager.py`/`storage.py` bez `transform`/`transport`.
- Przyklad sciezki w 4.3 odtworzony `prepare_pl_cutout` (offline): `data/nmt/pl_1992_1m_evrf2007/bbox/-499122.4858_-1088442.412_-496975.1716_-1086295.098.tif` — zgodny.
- Kolejnosci i komunikaty: `download_pl_cutout`/`run_pl_cutout`/`_download_pl_cutout` (skrot, kontrola providera, dysk, `Info:` >= 2**30, `Warning:` do 10), `_resolve_pl_sentinels` (wylaczenia), `cmd_download` (godlo+`--target-crs` PL po sentinelach, CZ w `_cmd_download_cz:1624` przed pobraniem), `prune_empty_dirs` (cutout + `_cz_download_bbox`), `_warp_to_grid` CZ (ta sama regula siatki, `except BaseException: unlink`), `_same_projection`, `_snap_outward`, `_vrt_xml`, `GugikProvider._get_opendata_url` (NoCoverageError / DownloadError czesciowy / fallback URL), `DownloadManager` (`No data for` na WARNING), brak konfiguracji logowania w CLI (WARNING idzie przez lastResort na stderr).

## Step 4 — E2E offline na realnych arkuszach 5 m

Skrypty (poza repo, `.superpowers/` jest ignorowane): `e2e/e2e_pl_cutout.py` (scenariusze a-f), `e2e/e2e_warp_diagnostics.py` (diagnostyka b); wyniki: `e2e/e2e_result.json`, `e2e/e2e_diag.json`. Katalog roboczy: scratchpad (`.../scratchpad/e2e_out`), nie repo.

Uklad: provider testowy `CacheCopyProvider` (`vertical_crs=EVRF2007`, `resolution=5m`, `descriptor_key=pl.gugik.nmt_5m`, `default_extension=.asc`) — `download(godlo, path)` KOPIUJE `Hydrograf/cache/nmt/nmt_5m/<hierarchia>/<godlo>.asc` do `path`, a dla `N-34-139-A-c-4-3` takze `<godlo>.prj` (realny WKT Hydrografu "ETRF2000-PL / CS92"); arkusz nieobecny w cache (indeks 1454 plikow) -> `NoCoverageError`. Uruchamiane `prepare_pl_cutout` + `select_pl_cutout_sheets` + `run_pl_cutout(provider=..., max_workers=4)` — `download_pl_cutout` zawsze buduje providera GUGiK (siec), wiec uzyto trzech krokow, ktore on sklada. **Zero patchy Kartografa** (`find_sheets_for_bbox` NIE podmieniany — prawdziwa selekcja miescila sie w cache). Straznik `socket.connect` (poza loopbackiem = blad) + `PROJ_NETWORK=OFF`: `network_attempts_blocked: []`. Cache Hydrografu tylko do odczytu: sha256 182 plikow `N-34/139` przed i po — identyczne; `find cache -newer <snapshot>` — pusto.

| Scenariusz | Wynik |
|---|---|
| **a) EPSG:2180, bbox calkowity** `642000,480500,644000,481500` (szew `-4-3`/`-4-4`; selekcja = dokladnie te 2 arkusze) | siatka: poczatek `(641997.5, 481502.5)`, **faza mod 5 = 2,5 / 2,5**; rozszerzenie **2,5 m na kazda strone**; 201 x 401 px; **0 / 80 601 pikseli rozbieznych** z arkuszem zawierajacym srodek piksela; 0 konfliktow (zaden piksel wazny w 2 arkuszach — fakt 1); **nodata 0**; nazwa = wspolrzedne zadania; sidecar `horizontal_crs EPSG:2180`, `transform: null`, `request` = zadanie, `extra` = `parent_request` |
| **a) EPSG:2180, bbox ulamkowy** `642001.3,480502.7,643998.9,481497.1` | faza 2,5 / 2,5; rozszerzenie W 3,8 / S 0,2 / E 3,6 / N 0,4 m (< 5 m); **0 / 79 799** rozbieznych; nodata 0 |
| **a) mieszany cache** (`.prj` przy `-4-3`) vs cache bez `.prj` | piksele identyczne (`array_equal` = True) — `_same_projection` przepuscil realny WKT Hydrografu |
| **b) EPSG:5514**, ten sam bbox (selekcja te same 2 arkusze) | wynik 231 x 415 px, nodata 0; **piksele = bit w bit odtworzenie** "mosaic_and_crop z parametrami build_pl_cutout + reproject jak warp_to_grid"; vs niezalezny warp GDAL kazdego arkusza (ta sama operacja `pinned`, ta sama siatka), 95 865 px waznych w obu (100 %): **srednio 2,74 mm, maks. 0,667 m**; > 1 cm: 6 915 px. Rozbicie (diagnostyka): dalej niz 1 px od szwu — srednio 2,71 mm, **maks. 0,146 m**; w pasie 1 px szwu (748 px) — maks. 0,667 m. `tolerance=0` (dokladny transformer) — praktycznie bez zmian (srednio 2,74 mm) -> to NIE aproksymacja transformera. **`XSCALE=YSCALE=1` w obu warpach: poza 1 px od szwu srednio 0,032 mm, maks. 3,2 mm, 0 px > 1 cm; wszystkie 87 px > 1 cm lezy <= 1 px od szwu** (maks. 0,649 m — tam warp pojedynczego arkusza widzi tylko czesc sasiadow bilinear: GDAL pomija piksel docelowy, gdy piksel zrodla pod probka to nodata). Wniosek: brak przesuniecia o ulamek piksela (przed naprawa zn. 1 rampa: srednio 0,35 m); roznice poza szwem to domyslna, per-kawalek skala resamplingu GDAL (zalezna od zasiegu zrodla) |
| **b) siatka warpa** | `bounds != bbox_target`: E krawedz 1,61 m wewnatrz, S 0,76 m na zewnatrz (< 0,5 px) — `round(415,32) = 415`, `round(230,85) = 231` od naroznika NW; ta sama regula w `_warp_to_grid` CZ |
| **c) arkusz BRAK w cache**: bbox `650500,480800,652500,481800` (szew `N-34-139-A-d-4-3` w cache / `-4-4` brak) | selekcja 2 arkusze, provider wolany dla obu; `missing_sheets = ("N-34-139-A-d-4-4",)` = sidecar `extra.missing_sheets`, obok `extra.parent_request`; **0 / 80 601** rozbieznych; **nodata 33 775 (41,9 %) = dokladnie piksele, w ktorych zaden pobrany arkusz nie ma danych**, 0 nodata tam, gdzie arkusz ma dane; nodata tylko na wschod od szwu (min x srodka nodata 651 650 >= min x ramki `-4-4` 651 626,3); logi: WARNING `kartograf.download.manager` "No data for N-34-139-A-d-4-4: ..." + INFO `kartograf.download.cutout` "Brak danych GUGiK dla 1 arkuszy wycinka: N-34-139-A-d-4-4" |
| **d) reuse cache** (usuniety wynik, provider rzucajacy `DownloadError` przy kazdym wywolaniu) | **0 wywolan providera**, wynik bajt w bajt (sha256) i piksele identyczne; drugie wywolanie bez `force` -> `skipped=True` |
| **e) awaria z `force=True`** (ten sam provider) | `DownloadError: 2 z 2 arkuszy nie pobrano (blad pobrania, nie brak danych): ...`; **poprzedni wynik bajt w bajt**, 0 plikow `.mosaic.`/`.warp.` |
| **f) kompresja pliku posredniego** (mozaika b, 439 x 271 px, `dst_kwds` jak `build_pl_cutout`) | 476 280 B -> 224 395 B (**2,12x**), piksele identyczne; ASC tych 2 arkuszy: 6,005 B/wartosc |
| oszacowanie dysku | a_int: estymacja 2 624 598 B <= faktycznie 2 852 056 B (arkusze + wynik) — dolne oszacowanie trzyma (a_frac: 2 622 998 <= 2 848 848) |

**Liczby do PROGRESS (propozycja jednej linii):** E2E offline 2026-09-28 (realne arkusze 5 m, cache Hydrografu, provider kopiujacy, zero patchy): 2180 — faza 2,5, 0/80 601 i 0/79 799 rozbieznych, nodata 0, mieszany `.prj` = bez `.prj`; 5514 — bit w bit = mozaika+warp_to_grid, vs niezalezny warp GDAL srednio 2,7 mm / maks. 0,15 m poza szwem (z XSCALE=YSCALE=1: 0,03 mm / 3,2 mm); brak arkusza -> missing_sheets + 33 775 px nodata wylacznie w jego miejscu; reuse cache 0 wywolan; porazka z force zostawia poprzedni wynik; kompresja posredniego 2,12x.

### Dowody, ze E2E ma zeby (mutacje PO commicie, przywracane `git checkout -- kartograf/download/cutout.py`, `git status` czysty po kazdej)
| # | Mutacja | Wynik E2E |
|---|---|---|
| M1 | `snap_to_source_grid=True` -> `False` | a_int: **42 889 / 80 000 rozbieznych**, faza 0/0, rozszerzenie 0; a_frac: 0 rozbieznych, ale **faza 1,3/2,1** (siatka przesunieta — lapie kontrola fazy); b: srednio **6,4 cm**, maks. **2,22 m**, 73 115 / 95 865 px > 1 cm (vs 2,7 mm) |
| M2 | `assign_crs="EPSG:2180"` -> `None` | exit 1: `ValidationError: mosaic_and_crop: niezgodne CRS wejsc: ['EPSG:2180', 'None']` (realny `.prj` Hydrografu obok arkusza bez) |
| M3 | `fatal = [g for g in failed if g not in no_data]` -> `fatal = list(failed)` | exit 1: `DownloadError: 1 z 2 arkuszy nie pobrano (blad pobrania, nie brak danych): N-34-139-A-d-4-4` |

## Step 5 — brama jakosci (HEAD przed commitem = drzewo `fa1f771`, zmiany wylacznie w docs)
```
.venv/bin/python -m pytest tests/ -q -m "not live"
===================== 1854 passed, 8 deselected in 27.18s ======================
.venv/bin/python -m pytest tests/ --cov=kartograf -q -m "not live" 2>&1 | tail -3
TOTAL                                   5903    421    93%
Required test coverage of 60.0% reached. Total coverage: 92.87%
===================== 1854 passed, 8 deselected in 34.71s ======================
.venv/bin/python -m ruff check kartograf/ tests/        -> All checks passed!
.venv/bin/python -m ruff format --check kartograf/ tests/ -> 87 files already formatted
mypy kartograf/ -> Found 32 errors in 9 files; grep error: | sed | sort > mypy-after.txt; diff mypy-baseline.txt mypy-after.txt -> pusty (32 = 32)
```
CHANGELOG `### Tests`: "1854 testy offline, pokrycie 92,9%" (+ historia 1779 -> 1854, +75).

## Odstepstwa / decyzje
1. `download_pl_cutout` nie byl uruchamiany wprost (buduje providera GUGiK — siec); E2E przez trzy kroki, ktore sklada (brief dopuszczal "`download_pl_cutout` / `prepare` + `select` + `run`").
2. Scenariusz c) na naturalnej krawedzi cache (`N-34-139-A-d-4-4` naprawde nie ma w cache Hydrografu), nie na sztucznie "ukrytym" arkuszu; a) i b) w obszarze `N-34-139-A-c-4-*` jak w briefie.
3. Dodatkowe scenariusze d)-f) i diagnostyka b) — poza minimum briefu; dostarczaja liczb dla twierdzen w ARCHITECTURE 4.3 (reuse cache, "poprzedni wynik przezywa", kompresja).
4. ARCHITECTURE poprawiona takze poza 4.3 (sekcje 1-3, 6) — twierdzenia tam byly falszywe po R3 (graf importow, kto pisze sidecar); SCOPE: naglowek 3.8 -> 3.10 (byl rozjechany ze stopka 3.9).
5. W nowym tekscie tylko ASCII bez diakrytykow (README/SCOPE maja diakrytyki w starych zdaniach — tych slow nie ruszalem; `git diff | grep` diakrytykow w dodanych liniach = wylacznie niezmienione slowa edytowanych linii). Znaki `—` i `°` jak w calej istniejacej dokumentacji.

## Watpliwosci (do decyzji kontrolera)
1. **Skala resamplingu GDAL w warpie (zamrozony `warp_to_grid`, tak samo `_warp_to_grid` CZ).** GDAL liczy `XSCALE`/`YSCALE` per kawalek z proporcji okien celu i zrodla; przy obroconym ukladzie docelowym wartosc zalezy od zasiegu zrodla, wiec piksele wycinka moga minimalnie zalezec od zasiegu mozaiki (zmierzone: mozaika vs pojedyncze arkusze — srednio 2,7 mm, lokalnie do 0,15 m na stromym terenie przy 5 m; z `XSCALE=YSCALE=1` < 3,2 mm). To nie regresja tej fali (warp zamrozony — Global Constraints), ani przesuniecie geometrii. Opisane w ARCHITECTURE 4.3 jako "kandydat na etap 2" — jesli kontroler woli inne sformulowanie/backlog, to jedno zdanie. Do rozwazenia: `XSCALE=1, YSCALE=1` w obu warpach (zmiana wynikow — test porownawczy + checklista live).
2. **Zasieg rastra warpa != `bbox_target`** (E/S krawedz do < 0,5 px; E2E 1,61 m / 0,76 m przy 5 m). Stara ARCHITECTURE 4.3 twierdzila "bounds == bbox_target" (pomiar 186 x 94 px byl przypadkiem szczegolnym). Poprawione w docs (4.3 krok 6, 3.3 pkt 3); kod bez zmian (siatka calkowita od naroznika NW, jak CZ).
3. Podwojne komunikaty dla braku danych w CLI (per arkusz `No data for ...` WARNING z managera przez lastResort + zbiorczy `Warning:` CLI) — minor odlozony z Zad. 10; opisany w docs zgodnie z kodem.
4. Poza zakresem, nie zmieniane: CLAUDE.md/README zalecaja `pytest tests/` (bez `-m "not live"` odpala 8 testow sieciowych — P-16); README tabela sidecara "nodata odczytana z pliku" (dla wycinka PL stala -9999.0 — opisane w ARCHITECTURE 3.2).

## Pliki
- `/home/claude-agent/workspace/Kartograf/docs/ARCHITECTURE.md`
- `/home/claude-agent/workspace/Kartograf/docs/DECISIONS.md`
- `/home/claude-agent/workspace/Kartograf/docs/CHANGELOG.md`
- `/home/claude-agent/workspace/Kartograf/docs/SCOPE.md`
- `/home/claude-agent/workspace/Kartograf/CLAUDE.md`
- `/home/claude-agent/workspace/Kartograf/README.md`
- E2E (poza repo): `.superpowers/sdd/2026-09-28-fala-review-max-i-wycinek-biblioteczny/e2e/{e2e_pl_cutout.py,e2e_warp_diagnostics.py,e2e_result.json,e2e_diag.json}`; `mypy-after.txt` w katalogu SDD.
