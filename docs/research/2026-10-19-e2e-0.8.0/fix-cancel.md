# fix-cancel: Ctrl-C z `--workers >= 2` i SIGTERM (branch `fix/e2e-cancel`, od develop @ bef87501)

Commity: `12dbf840` (fix: kod, testy, USAGE 9.3, llms.txt), `88127f4e` (docs: ARCHITECTURE, SCOPE, PRD, STANDARDS, README, CLAUDE.md).
Brama: `scripts/gate.sh` zielona (ruff, ruff format, mypy, pytest offline: 7180 passed, 18 deselected, 213 s), uruchomiona raz na koncu z korzenia worktree (po poprawce kolejnosci importow w testach).

## Statusy

| Znalezisko | Status |
|---|---|
| e2e-B P2-1 (arkusze imagery, kolejka po Ctrl-C) | fixed (odtworzone na zywo: 3 arkusze PL-2000 `--workers 2`; przypadek 42 arkuszy 12x12 km nie powtarzany - limit rozmiaru) |
| e2e-C P2-5 (BDOT10k 12 powiatow) | fixed (odtworzone na zywo, 459 MB w 125 s przed poprawka) |
| e2e-D P2-2 (cadastre prices, kolekcje) | fixed (odtworzone na zywo) |
| e2e-B P3-6 (SIGTERM, CLI) | fixed: kod 143, dokument `terminated`, sprzatanie |
| SIGTERM w serwerze MCP | **decision needed** - nie zmieniono (patrz nizej) |

## Przyczyna

`ThreadPoolExecutor` uzywany jako `with ...: submit(all); as_completed` - `KeyboardInterrupt` przychodzi tylko do watku glownego, a wyjscie z `with` robi `shutdown(wait=True)` bez `cancel_futures`: cala kolejka sie wykonywala i byla zatwierdzana, a trwajace transfery nie mialy jak sie zatrzymac (nic w watku roboczym nie sprawdza przerwania). Dodatkowo `BDOT10k` GPKG czyta paczke wlasna petla `iter_content` (poza `download_to`), wiec nawet po anulowaniu kolejki w locie dokanczal sie caly transfer (wykryte na zywo: 29,6 s do wyjscia, poprawione).

## Zmiany

- **Nowy modul `kartograf/interrupt.py`** (lisc, nic wewnetrznego): `run_parallel(work, items, *, workers, on_done=None) -> list` (wyniki w kolejnosci `items`, `on_done(ended, item, result)` w watku wolajacym w kolejnosci konca; przy dowolnym wyjatku petli - Ctrl-C, wyjatek jednostki, wyjatek `on_done` - ustawia flage stopu, `shutdown(wait=True, cancel_futures=True)` i podnosi wyjatek ponownie; jednostka, ktora nie ruszyla, nie startuje); `check_stop()`/`current_stop()` (flaga puli biezacego watku; poza pula brak efektu); `Stopped(KeyboardInterrupt)` - wyjatek zatrzymanej jednostki (zadne `except Exception` pakietu go nie polknie, to samo sprzatanie co Ctrl-C przy `--workers 1`); `Terminated(KeyboardInterrupt)`; `sigterm_interrupts()` (kontekst: SIGTERM -> `Terminated` w watku glownym; pierwszy sygnal przywraca SIG_DFL, wiec drugi zabija; bez efektu poza watkiem glownym i gdy SIGTERM nie ma domyslnej reakcji).
- **Wszystkie 5 pul pobierania na jednym pomocniku:** `download/manager.py::_download_many` (wyjatek inny niz `DownloadError` nadal -> status `failed`, przez opakowanie w watku), `download/collections.py::run_request`, `landcover/manager.py::_each_powiat` (zdjety nieuzywany `import concurrent.futures`), `download/laz.py::_run_laz_download`, `download/cz_laz.py::_run` (zdjety import `ThreadPoolExecutor, as_completed`).
- **Punkty sprawdzania stopu:** `transport/http.py` (poczatek kazdej proby w `download_to`/`get_with_retry`/`head_signal`, petla chunkow `_write_atomic`, pauza ponowienia `_pause` = `Event.wait` zamiast `time.sleep`; `import time` zostaje - testy patchuja `kartograf.transport.http.time.sleep`), `transport/aaigrid.py` (petla strumienia), `providers/pl/bdot10k.py` (3 jednolinijkowe `check_stop()`: petla `iter_content` paczki, petla ekstrakcji warstw, petla scalania warstw), `download/versions.py::commit_version` (pierwsza instrukcja: nic nie jest publikowane po stopie; obaj wolajacy `store_file` i `_download_version` sprzataja staging w `except BaseException`/`finally`).
- **SIGTERM / kod 143:** `error_report.py` (`Terminated` -> `code: terminated`, `exit_code: 143`, `TERMINATED_MESSAGE = "przerwano (SIGTERM)"`; wiersze w `ERROR_CODES` i `EXIT_CODES`: 143 `terminated`; opis 130 doprecyzowany), `cli/commands.py` (`main` w `with sigterm_interrupts()`; `_fail` bierze komunikat i kod z `error_report` zamiast literalow). Kod 143 = 128 + SIGTERM, konwencja powloki; 130 zostaje dla SIGINT.
- Dokumenty: USAGE 9.2 pkt 4 i 9.3 (tabele kodow: 143 i `terminated`; akapit "Przerwanie w CLI (Ctrl-C, SIGTERM)": semantyka kolejki, limity, `.incoming` po SIGKILL, MCP bez przechwytywania SIGTERM), `llms.txt` (kody), ARCHITECTURE (graf zaleznosci, drzewo, akapit "Przerwanie i pule watkow", kody 0/1/2/130/143), SCOPE (3 miejsca), PRD, STANDARDS Z10, README, CLAUDE.md (jedno miejsce: `0/1/2/130/143` - do decyzji koordynatora, czy zostaje).

## Testy regresyjne (offline)

- `tests/test_interrupt.py` (8): kolejnosc wynikow/postepu; Ctrl-C zatrzymuje trwajace i nie startuje zakolejkowanych (watek zablokowany w "transferze"), wywolanie wraca po zakonczeniu watkow, wyjatek to `KeyboardInterrupt`, nie `Stopped`; zatrzymana pula nic nie commituje (`commit_version`, brak katalogu wersji); blad jednostki zatrzymuje pule i jest podnoszony; hierarchia `Stopped`/`Terminated`; SIGTERM prawdziwym sygnalem (handler w bloku, przywrocony SIG_DFL, handler programu nietkniety, brak zmian poza watkiem glownym).
- `tests/test_transport_http.py::TestStoppedPool` (4): `download_to` staje miedzy chunkami i usuwa `.tmp`; pauza ponowienia (backoff 600 s) konczy sie ze stopem, bez drugiej proby; `get_with_retry`/`head_signal` nie wysylaja zapytania po stopie.
- Per tor: `test_parallel_download.py` (manager: `test_ctrl_c_downloads_and_commits_no_sheet_after_it`; BDOT10k: `test_ctrl_c_downloads_and_commits_no_powiat_after_it`), `test_laz_download.py` (LAZ PL), `test_cz_laz.py` (LAZ CZ, sesja ze strumieniem bez konca - zatrzymuje go tylko `download_to`). Kolekcje (`run_request`): bez osobnego testu toru (fixture ma tylko 2 jednostki); pokryte testami pomocnika i zywym przebiegiem `prices`.
- CLI: `tests/test_cli_errors.py` - prawdziwy SIGTERM w srodku komendy: tekst (`Error: przerwano (SIGTERM)`, 143) i `--json` (`terminated`, 143, stderr pusty); zaktualizowane tabele: `test_errors.py` (spec tabeli + `Terminated`), `test_cli_json.py`, `test_catalog.py`.
- Falsyfikacja: (1) mutacja pomocnika (stary `shutdown(wait=True)` bez stopu) wywala test Ctrl-C; (2) test toru managera uruchomiony na kodzie develop (shim `check_stop`) wywala sie: wystartowalo 16 z 16 arkuszy (`assert 16 <= 3`).
- Pomocnicze: `tests/interrupt_fakes.py` (`transfer`, `EndlessResponse`, `FirstThenTransfer`, `interrupted_after_first`).

## Dowody na zywo (CLI z worktree; dane pod `<katalog-danych>/fix-cancel`, skasowane; SIGINT/SIGTERM przez `Popen.send_signal`)

Przed (develop):

| przypadek | sygnal po | wyjscie po sygnale | wersje po przerwaniu |
|---|---|---|---|
| `cadastre download --product prices --country pl --bbox 22.8,51.8,23.8,52.3 --bbox-crs EPSG:4326 --workers 2` | SIGINT 4 s | kod 130 po 4,1 s | **6 z 6** (1 gotowa w chwili sygnalu) |
| `imagery download --product orto --country pl --bbox 7500100,5776100,7504700,5776900 --bbox-crs EPSG:2178 --sheet-system 2000 --scale 1:2000 --workers 2` | SIGINT 2 s | kod 130 po 12,3 s | **3 z 3** |
| `landcover download --product bdot10k --bbox 18.80,50.20,19.05,50.40 --bbox-crs EPSG:4326 --workers 2 --json` | SIGINT 5 s | proces zywy po 120 s (zabity SIGKILL) | 6 (459 MB) |

Po:

| przypadek | sygnal po | wyjscie po sygnale | wersje |
|---|---|---|---|
| prices | SIGINT 4 s / 5,5 s / 7 s | 0,4 s / 0,8 s / 0,3 s, kod 130 | 0 / 2 / 5 = dokladnie jednostki z paska postepu "ukonczone" przed sygnalem |
| orto 3 arkusze | SIGINT 2 s / 8 s | 1,6 s / 2,4 s, kod 130 | 0 / 1 (ukonczony) |
| bdot10k `--json` | SIGINT 8 s | 0,2 s, kod 130, `kartograf-error/1` `interrupted` | 0 |
| bdot10k `--json` (przed poprawka toru BDOT10k) | SIGINT 8 s | 29,6 s (transfer w locie nie slyszal stopu) | 0 |
| bdot10k `--json` | SIGINT 25 s | 3,8 s | 0 (zadna paczka nie zdazyla) |
| orto 3 arkusze | **SIGTERM** 8 s | 0,5 s, **kod 143**, `Error: przerwano (SIGTERM)` | 0 |
| bdot10k `--json` | **SIGTERM** 8 s | 0,3 s, **kod 143**, dokument `terminated` (`exception: Terminated`, `exit_code: 143`, stderr pusty) | 0 |
| prices | **SIGTERM** 5,5 s | kod 143, `Error: przerwano (SIGTERM)`, ale po 15,2 s (patrz limity: sondy HEAD) | 0 |

We wszystkich przebiegach po poprawce: brak `.incoming` i plikow `.tmp`.

## Znane limity (nie zmieniane)

- Zapytanie zablokowane na sieci (czekanie na naglowki albo na kolejne bajty) konczy sie z limitem czasu; strumien staje po biezacym chunku (1 MiB; BDOT10k 8 KiB). Jeden przebieg `prices` na SIGTERM zajal 15 s z tego powodu (sondy rozmiaru HEAD w toku).
- Pule sond (`executor.map`: `DownloadManager.check_year_range`/`inspect_sheets`, `collections._within_volume` HEAD, `availability._heads`) zostaly bez zmian: `map` samo anuluje kolejke, czekaja tylko na biezace zapytania; ich pauzy ponowien nie slysza stopu (poza `run_parallel`). Do rozwazenia: przeniesienie na `run_parallel` (jednolinijkowe, ale `_within_volume` jest w pliku edytowanym przez FixLandcoverSoil/FixCollections).
- Zagniezdzone `run_parallel` w jednostce puli nie dziedziczy stopu zewnetrznej (takie zagniezdzenie nie wystepuje).
- Lokalne fazy po transferze (kopia GPKG na SMB w BDOT10k, rozpakowanie czlonu ZIP w `unit_package`) nie sa przerywalne w srodku pojedynczej operacji na pliku; stop jest sprawdzany przed `commit_version`.
- Zmiana zachowania: wyjatek jednostki inny niz `DownloadError`/`NoCoverageError` (np. `OSError` zapisu) w kolekcjach/landcover/LAZ zatrzymuje pule od razu (dotad dopiero po calej kolejce); `DownloadManager` nadal zamienia go na status `failed` jednostki.

## DECYZJA: SIGTERM w serwerze MCP (nie zaimplementowano)

Zbadane na zywo (serwer bez klienta, stdin otwarty): oryginalny `kartograf-mcp` nie konczy sie na pierwszy SIGINT w 15 s (graceful cancel glownego zadania czeka na watek czytajacy stdin; potrzebny drugi Ctrl-C albo EOF stdin). Probne `sigterm_interrupts()` w `mcp_server.main` dalo to samo dla SIGTERM (wisi do EOF stdin) - **regres wzgledem domyslnego SIGTERM (natychmiastowe zakonczenie)**, wiec zmiane cofnieto: `kartograf/mcp_server.py` bez diffu. Standard klientow MCP: zamknij stdin, po czasie SIGTERM, potem SIGKILL.
Opcje: (A) zostawic domyslne zakonczenie przez SIGTERM (stan obecny; opisane w USAGE 9.3: MCP nie przechwytuje SIGTERM; po zabiciu zostaje `.incoming`, sprzatane po 24 h); (B) zatrzymanie kooperacyjne: rejestr stopu serwera (`stop_all()` + zakres `stoppable()` wokol `_execute.work`), sygnal obslugiwany w petli zdarzen (`anyio.open_signal_receiver`), trwajace wywolania koncza sie `Stopped` -> wynik `kartograf-error/1`, ograniczone czekanie, potem `os._exit(143/130)` (konieczne: czytnik stdin z SDK to niedemoniczny watek zablokowany na odczycie, wiec bez `os._exit` nie ma czystego wyjscia przy otwartym stdin). ~60 linii + test podprocesowy; dotyka udokumentowanej semantyki "wywolanie anulowane przez klienta jest porzucane, nie zatrzymywane" (`_execute`). Rekomendacja: (A) do v0.8.0, (B) jako osobne zadanie, jesli sprzatanie `.incoming` po zamknieciu klienta MCP ma znaczenie.

## Proponowany wpis CHANGELOG ([0.8.0], styl istniejacy)

- Ctrl-C przy `--workers >= 2` zatrzymuje pobieranie: kolejka (arkusze PL, kolekcje, powiaty BDOT10k, kafle LAZ PL i CZ) jest anulowana, trwajace transfery staja po biezacym kawalku, a jednostki niedokonczone przed przerwaniem nie sa pobierane ani zatwierdzane (dotad komenda czekala na cala kolejke i zatwierdzala ja: 12 powiatow BDOT10k, 6 powiatow RCN, 3 arkusze orto po Ctrl-C). Kod 130 i `kartograf-error/1` `interrupted` jak przy `--workers 1`; wersje zatwierdzone przed przerwaniem zostaja. Zmiana zachowania: wyjatek jednostki puli inny niz `DownloadError` (np. blad zapisu) zatrzymuje pule od razu, a nie po calej kolejce.
- SIGTERM (`timeout`, `docker stop`) w CLI dziala jak Ctrl-C: sprzatanie katalogu roboczego `versions/.incoming/`, `Error: przerwano (SIGTERM)` albo `kartograf-error/1` z kodem `terminated` i kod wyjscia 143 (dotad proces ginal bez komunikatu i zostawial resztki). Nowy kod wyjscia 143 i kod bledu `terminated` w tabelach USAGE 9.3, `kartograf catalog` i `llms.txt` (zmiana addytywna; 130 zostaje dla Ctrl-C). Serwer MCP bez zmian.
- Biblioteka: nowy modul `kartograf.interrupt` (`run_parallel`, `check_stop`, `Stopped`, `Terminated`, `sigterm_interrupts`); `Terminated` i `Stopped` sa podklasami `KeyboardInterrupt`.

## Proponowana errata ADR (DECISIONS.md, CRLF)

ADR-018 errata 2 (2026-10-19, e2e 0.8.0): Pule pobierania (`DownloadManager`, kolekcje, powiaty BDOT10k, kafle LAZ PL i CZ) ida przez jednego pomocnika `kartograf.interrupt.run_parallel`. Wyjatek w watku oczekujacym (Ctrl-C, blad jednostki) anuluje niezaczete jednostki i ustawia flage stopu, ktora trwajace jednostki widza w `check_stop()` (transport HTTP: przed proba, miedzy chunkami, zamiast pauzy ponowienia; `commit_version`); jednostka konczy sie `Stopped` (podklasa `KeyboardInterrupt`), wiec dziala to samo sprzatanie co przy `--workers 1`, a nic nie jest zatwierdzane po przerwaniu. Flaga jest per pula (watek lokalny `threading.local`), bez globalnego stanu.
ADR-046 errata (kody wyjscia): dodany kod wyjscia 143 (`terminated`, 128 + SIGTERM) i kod bledu `terminated` (`kartograf.interrupt.Terminated`); CLI `main` przechwytuje SIGTERM (`sigterm_interrupts`), serwer MCP nie.
