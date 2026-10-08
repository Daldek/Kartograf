# Weryfikacja planu wdrozenia ADR-030 (2026-10-07)

**Przedmiot:** `docs/research/2026-10-07-plan-adr030.md` wobec ADR-030
(`docs/DECISIONS.md:1436-1588`) i kodu na develop `4f2c416` (plan cytuje
`b17b3b1`; numery linii zgodne — commity po nim dotycza tylko docs).
**Glebokosc:** umiarkowana (celowane sprawdzenie, nie pelny audyt).
**Metoda:** lektura planu i ADR, odczyt kodu (plik:linia), skrypt
`/tmp/claude-2001/verify030/count_campaigns.py` (`.venv/bin/python -I`) na
fixturach `tests/fixtures/gugik_skorowidz/real_2026_10_06/`, grep surowych
GetCapabilities na `<katalog-danych>/.../2026-10-06-brzegowe/{a/raw/caps,b/raw/C12}`.
Bez zmian kodu, bez sieci.

## Werdykt: GOTOWY PO POPRAWKACH

Plan jest spojny z ADR-030, twierdzenia o kodzie i fixturach sie potwierdzaja
(12/12 sprawdzonych), fale nie maja kolizji plikow, zaleznosci miedzy falami
sa kompletne. Do poprawienia przed startem: cztery sprawy ISTOTNE (zadna nie
jest blokujaca — kazda ma poprawke na kilka linii planu), szesc DROBNYCH.

| Waga | Liczba |
|---|---|
| BLOKUJACY | 0 |
| ISTOTNY | 4 |
| DROBNY | 6 |

---

## 1. Zgodnosc z ADR-030 — pokrycie decyzji (a)-(j)

| Decyzja | Zadania | Pokrycie | Uwagi |
|---|---|---|---|
| (a) strategie, wszystkie tryby arkuszy | T4, T6, T7, T8 | pelne | `_fetch_sheet` (`manager.py:474`) jest jedynym torem dla godla, hierarchii i listy (`download_sheet` -> `download_hierarchy` -> `_download_many` -> `_download_single_sheet_task` -> `_fetch_sheet`), wiec rozgalezienie w T7 obejmuje wszystkie tryby |
| (b) `newest` sprawdza nowsza kampanie | T7 | pelne | skip per plik kampanii po `resolve_campaigns`; istnienie sciezki standardowej przestaje byc kryterium |
| (c) tozsamosc i uklad `kampanie/` | T1 | pelne | `CampaignRef`, `get_campaign_path` |
| (d) dowiazanie standardowe | T2, T7 | pelne, z odstepstwem Q7 | sidecar standardowy = zwykly plik (nie dowiazanie) — uzasadnione, patrz Q7 |
| (e) brak migracji | T2 (`linked_campaign` -> None), T7 | pelne | `test_legacy_regular_file_replaced_by_link` |
| (f) `--min-year` | T6, T7 (status `no_coverage` w liscie), T8 | pelne | komunikaty z data najnowszej kampanii |
| (g) odpornosc na nazwy warstw | T4, T6 | pelne, z odstepstwem Q1 | warstwa spoza wzorca NIE odpytywana + `logger.warning` dla rodziny produktu |
| (h) cache | T3, T6 | pelne | `campaigns_cache`, `scanned_from`, granica poza kluczem |
| (i) sidecar | T7 | pelne, z odstepstwem Q8 | `request.min_year` tylko gdy podane (ADR: "request zapisuje campaigns i min_year") |
| (j) wycinek, CZ, LAZ | T8 (wycinek+`all`, CZ), T5 (LAZ) | pelne, z rozszerzeniem Q2 | `--target-crs` + `--min-year` = blad (ADR wymienia tylko `all`); biblioteka: `run_pl_cutout` buduje wlasny `DownloadManager` bez `campaigns` (`cutout.py:714`), wiec `all` z biblioteki jest nieosiagalne — straz CLI wystarcza |

**Odstepstwa od litery ADR.** Plan wskazuje jako errate tylko Q1 (g) i Q7 (d).
Faktycznie od litery odbiegaja takze: Q2 (nowy zakaz `--target-crs` +
`--min-year`, (j)), Q5 (pomijanie warstw tylko w `all`, (g) mowi o
`--min-year` bez rozroznienia strategii) i Q8 (`request.min_year` warunkowo,
(i)). Kazde z nich jest uzasadnione (sekcja 5), ale errata ADR-030 musi
objac wszystkie piec — patrz problem I-4.

**Czego plan nie przemilcza, a warto odnotowac:** ADR (j) nazywa odrzucenie
wycinka z `all` `ValidationError` (wyjatek biblioteki). Plan realizuje to w
CLI (`_resolve_pl_sentinels`). Skoro `run_pl_cutout` nie przyjmuje
`campaigns`, biblioteka nie ma jak zazadac `all` dla wycinka — nie ma luki,
ale T10 powinno to zapisac w ARCHITECTURE 4.3 ("wycinek zawsze `newest`").

---

## 2. Zweryfikowane twierdzenia o kodzie i fixturach

| # | Twierdzenie planu | Wynik | Dowod |
|---|---|---|---|
| 1 | Jedyne miejsce skip arkusza: `manager.py:494-498` (`target_path.exists()`) | POTWIERDZONE | `manager.py:494-498`: `target_path = self._storage.get_path(...)`; `if skip_existing and target_path.exists(): ... return target_path, True`. Zaden inny `.exists()` w `manager.py` nie decyduje o skip |
| 2 | CLI E15 `download_cmd.py:989-1009` liczy `existed` PRZED pobraniem | POTWIERDZONE | `:992-995`: `target = manager.storage.get_path(...)`; `existed = skip_existing and isinstance(target, Path) and target.exists()`; `:1005` drukuje "Skipped" po `existed` |
| 3 | Pozostale miejsca skip: `cutout.py:698,:881`, CLI `:1372`, `laz.py:169`, CZ `:1802,:1881` | POTWIERDZONE + 1 POMINIETE | grep `.exists()` potwierdza wszystkie; plan POMIJA `cutout.py:589` (`check_pl_cutout_disk_space`: `if storage.get_path(leaf, ".asc").exists(): continue`) — patrz D-3 |
| 4 | `list_files` (`storage.py:454-482`) po zmianie zwroci linki + pliki `kampanie/` + wiszace linki | POTWIERDZONE | `:480-482`: `files.extend(root.glob(pattern))` bez zadnego filtra; `Path.glob` zwraca wiszace symlinki (plan: eksperyment 0.1, zgodne z semantyka `glob`, ktora nie wywoluje `exists()`) |
| 5 | `delete` (`:428-452`) nie usuwa wiszacego linku | POTWIERDZONE | `:447`: `if path.exists(): path.unlink()` — `exists()` podaza za linkiem, dla wiszacego = False -> `return False` |
| 6 | `write_sidecar` pisze przez symlink (nieatomowo) | POTWIERDZONE | `sources/sidecar.py:225-227`: `sidecar_path.write_text(payload + "\n", ...)` — `write_text` otwiera cel symlinku |
| 7 | `_note_reuse` (tmp + `os.replace`) zastapilby symlinkowany sidecar plikiem | POTWIERDZONE | `manager.py:813-818`: `tmp = sidecar.with_name(...)`; `tmp.write_text(...)`; `os.replace(tmp, sidecar)` — `replace` podmienia wpis katalogu, nie cel |
| 8 | `_fetch_wms_layers` cicho pomija nazwy spoza `LAYER_PATTERN`; GetCapabilities zawiera `default`, `WMS`, `Zasiegi*` | POTWIERDZONE | `skorowidz.py:405-415`: tylko `fullmatch` dodaje do `layers`, brak `else`. Surowe XML: NMT/NMPT (5 plikow) = `default`, `WMS` + warstwy skorowidza; orto `b/raw/C12/caps.xml` = `default`, `WMS`, `SkorowidzeOrtofotomapy{2024,2025,2026,Starsze}`, `SkorowidzeOrtofotomapyZasiegi{2024,2025,2026,Starsze}` |
| 9 | Odpytanie niepasujacej warstwy przewraca arkusz (`DownloadError`) | POTWIERDZONE | `query_skorowidz_layer` `:247-257`: `if not is_skorowidz_answer(text): raise DownloadError(...)`; `_resolve_record` `:333-343` odpytuje KAZDA warstwe z listy az do dopasowania, bez `try` |
| 10 | C14 N-34-139-C-a-3-1 pod `all` (PL-1992, 1.0 m): `84183, 83233, 78047, 73021`; newest = 84183 (2025, NIE pelny); odpada 77944 (0,5 m) i PL-2000 | POTWIERDZONE | skrypt: 7 rekordow -> 4 kampanie dokladnie w tej kolejnosci; `select_sheet_record` na warstwie 2025 = 84183 (2026 pusta); odrzucone `73580`/`75064` (PL-2000 `7.171.21.*`) i `77944` (0,5 m) |
| 11 | N-34-139-C-a-3-2: 2025-04-04 ma `81467` (PL-2000) i `81468` (PL-1992) z tym samym `dt_pzgik` | POTWIERDZONE | skrypt: `81468 2025-04-04 2025-06-04` przyjety, `81467 7.171.21.23 2000 2025-04-04` odrzucony; arkusz ma 8 kampanii PL-1992 1 m (newest 83998, warstwa 2026) |
| 12 | Orto M-34-90-C-b-4-4 RGB: 7 kampanii `84466, 81437, 76530, 73121, 70500, 69792, 75`; CIR `84465`/`81436`; N-34-139-A-c-1-1 RGB 10 kampanii 2007-2025 | POTWIERDZONE | skrypt: RGB dokladnie ta lista (84466 i 73121 niepelne); CIR 4 (`84465, 81436, 76529, 69791`); N-34-139-A-c-1-1 RGB 10 (`83235 ... 43`), CIR 5. Rekordy zawieraja tez godla nadrzedne (`M-34-90-C-b-4`) i PL-2000 (`7.111.18.18`) — filtr tokenu godla je odrzuca |
| 13 | `.xyz`: N-33-69-A-d-3-2 `72675` (2019) ma URL `.xyz`; 5 m `76969` ma `.ASC`; dzis `.xyz` zapisalby sie jako `.asc` | POTWIERDZONE | skrypt: `72675 2019-04-29 ext=xyz`, `76969 ext=ASC`; `manager.py:494` buduje sciezke z `self._default_ext` (`.asc`), a `gugik.py:270-278` pobiera `record.url` do tej sciezki bez kontroli rozszerzenia |
| 14 | Orto `73900`: `aktualnosc` 2014-03-13, `dt_pzgik` 2021-04-06 (roznica 7 lat) | DODATKOWE | potwierdza decyzje (f): granica z `aktualnosc`, nie `dt_pzgik`; `sort_key` plasuje 73900 miedzy 2017 a 2013 wg `aktualnosc` |
| 15 | `expand_sheets` deduplikuje godla (R1) | POTWIERDZONE | `manager.py:426-435`: `seen: set[str]`, `if leaf not in seen` |
| 16 | Stub conftest ma 4 warstwy NMT EVRF2007 i 4 orto w kolejnosci realnej (T6 `queried_layers` asercje) | POTWIERDZONE | `tests/conftest.py:104-109`, `:160-168` |
| 17 | `grep "_resolve_record(" tests/` = 0; 78 testow `test_download_manager.py`; 307 `test_cli.py` | POTWIERDZONE | grep: 0 / 78 / 307 |
| 18 | `download_to` nie rzuca `NoCoverageError` (sketch `_fetch_campaigns` `except NoCoverageError: raise` jest martwy) | POTWIERDZONE | `transport/http.py:140` — jedyne `raise DownloadError` |

Zadne twierdzenie nie zostalo obalone. Jedno pominiecie (twierdzenie 3).

---

## 3. Wykonalnosc fal

**Kolizje plikow w jednej fali:** BRAK.
- Fala 1: T1 (`campaigns.py`, `storage.py`, `test_campaigns.py`, `test_storage.py`) | T2 (`links.py`, `test_links.py`) | T3 (`cache/metadata.py`, `cli/cache_cmd.py`, `test_metadata_cache.py`) | T4 (`skorowidz.py`, `gugik*.py` tylko `LAYER_FAMILY`, `test_skorowidz.py`, `test_wms_layer_validation.py`, `test_real_gugik_responses.py`, fixtury caps) | T5 (`gugik_laz.py`, `download/laz.py`, `test_laz_campaigns.py`). Wszystkie wymienione pliki testowe istnieja. `tests/test_cli.py` nie asertuje tresci `cache stats` (grep `Sheet entries`/`Record entries` poza `test_metadata_cache.py` = 0), wiec zmiana `cache_cmd.py` w T3 nie dotyka cudzych testow.
- Fala 4: T8 (`_parser.py`, `download_cmd.py`, `test_cli.py`) | T9 (`__init__.py`, `test_pl_cutout.py`, `test_campaigns_flow.py`) — rozlaczne. `CHANGELOG`, `conftest.py`, `kartograf/__init__.py` — po jednym wlascicielu (T10, nikt, T9).
- `conftest.py` nie jest edytowany; T4/T6 potrzebuja markera `real_wms_layers` — istnieje (`pyproject.toml:76`).

**Zaleznosci:** kompletne. T2 nie importuje `CampaignRef` (klucz = krotka) — zgodne z fala 1. T7 (fala 3) uzywa `get_campaign_path`/`CampaignRef` (T1), `ensure_standard_link` (T2), `resolve_campaigns`/`download_record`/`record_source` (T6). T6 (fala 2) uzywa `get_campaigns`/`set_campaigns` (T3) i `select_campaign_records`/`layer_upper_year` (T4). T8 uzywa `download_laz_area(campaigns=, min_year=)` (T5) i `last_sheet`/`DownloadResult.campaign_files` (T7). T9 uzywa `SheetFetch` (T7). Klucz sidecara w T2 `(extra.campaign.date, extra.campaign.dt_pzgik or "", extra.source.url)` jest zgodny z tym, co T7 zapisuje (`CampaignRef.to_extra()` + `record_source` = `to_source(endpoint)`, ktore ma `url`, `skorowidz.py:61`).

**Ukryta zaleznosc testowa (D-4):** `tests/test_sidecar.py:381` i `tests/test_download_manager.py:143,:225` buduja `DownloadManager(provider=GugikProvider())` — prawdziwy provider dostanie `supports_campaigns = True` w T6, wiec w T7 te testy przejda na tor kampanii. Ich asercje (`parts[:2]`, sidecar standardowy z `extra.source.uklad`) powinny przezyc (sidecar standardowy kopiuje `extra` celu), ale `tests/test_sidecar.py` nie jest w wlasnosci zadnego zadania.

---

## 4. Testy i mutacje dla top 5 ryzyk

| Ryzyko | Testy | Mutacje | Ocena |
|---|---|---|---|
| 1. Link nigdy na starsza kampanie | T2 `test_ensure_link_never_regresses_to_older_campaign`; T7 `test_newest_after_all_keeps_link_on_newer_local_campaign` | T2 (a) `>=`->`>`, (b) usuniecie warunku; T7 (b) `local[0]` zamiast `max(sort_key)` | DOBRE. Luka: gdy sidecar kampanii-celu jest nieczytelny/brak (`cur_key is None`), `ensure` przestawia link na starsza kampanie — regres przez tylne drzwi (D-1) |
| 2. Wspolbieznosc | T7 `test_parallel_all_campaigns_writes_each_file_once` (4 arkusze x 4 kampanie); T2 `test_ensure_link_replaces_older_target_set_by_other_process` | brak mutacji dla R1 | SLABE jako test (rozne godla = brak wyscigu o link; test nie padnie przy zadnej realistycznej mutacji). Ochrona jest strukturalna (`expand_sheets` dedup, `manager.py:426-435`) — dopisac test z DUPLIKATAMI godel w liscie (`download_sheets([G, G])` -> jedno pobranie, jeden link) i mutacje "usun `seen`" (D-6). R2 (dwa procesy) swiadomie bez blokad — akceptowalne |
| 3. Przestarzala kopia | T2 `test_copy_detected_via_sidecar_on_next_run`, `test_copy_with_size_mismatch_is_replaced`, `test_refresh_recopies_when_target_redownloaded`; T7 `test_force_redownload_relinks_copy` | T2 (d) pominiecie `refresh`, (e) brak kontroli rozmiaru; T7 (c) `refresh=False` | DOBRE dla biezacego procesu. Luka: kampania podmieniona przez INNY proces/`--force` z innego katalogu roboczego przy tym samym rozmiarze — kopia zostaje stara (D-5: tani test `st_mtime`) |
| 4. Sidecar przez link | T2 `test_standard_sidecar_is_regular_file_even_if_symlink_existed` (bajtowe porownanie sidecara kampanii); T7 `test_note_reuse_never_writes_through_symlink` | T2 (f) `write_text` na istniejacej sciezce | DOBRE. Dowod z kodu: `_note_reuse` czyta przez link, ale pisze `os.replace` (`manager.py:818`), wiec nawet symlinkowany sidecar zostalby zastapiony plikiem, nie nadpisany przez link. T11 grep `write_sidecar(` domyka |
| 5. Czesciowa porazka `all` | T7 `test_all_partial_campaign_failure_is_hard_failure_but_links_best_local` (`fail_urls={84183}`, link -> 83233, pliki 3 pozostalych) | T7 (e) przerwanie petli na pierwszym bledzie | DOBRE — 84183 jest PIERWSZE w kolejnosci, wiec `break` zostawia 0 plikow i test pada; przeniesienie `raise` przed blok linku tez pada (asercja linku). Uwaga: po `DownloadError` `campaign_files` dla arkusza nie trafia do `DownloadResult` (plan to przyznaje) |

Pozostale mutacje T1/T3/T4/T6/T8 sa trafnie dobrane (kazda ma jeden test,
ktory bez niej nie pada; plan sam wskazuje, gdzie trzeba dopisac asercje —
T1 (c), T6 (f)).

---

## 5. Ocena Q1-Q10

| Q | Rekomendacja planu | Ocena |
|---|---|---|
| Q1 | warstwa spoza `LAYER_PATTERN` NIE odpytywana; `logger.warning` dla rodziny produktu (`LAYER_FAMILY`) | **ZGODA.** Dowod: kazdy realny GetCapabilities ma `default` i `WMS`, orto dodatkowo 4 `Zasiegi*`; `query_skorowidz_layer` rzuca `DownloadError` na odpowiedz spoza szablonu (`skorowidz.py:253-256`), a `_resolve_record` nie ma `try` wokol warstwy — literalna realizacja ADR przewrocilaby KAZDY arkusz. Errata (g) konieczna |
| Q2 | `--target-crs` + `--min-year` = `Error:` przed siecia | **ZGODA.** Nazwa wycinka nie niesie granicy, skip po istnieniu pliku oddalby wycinek pod inna granica. Najtansze. Errata (j) |
| Q3 | `.xyz` jako plik kampanii z rozszerzeniem z URL, link tylko do formatu providera, `newest` z `.xyz` -> link bez zmian + warning | **ZASTRZEZENIE (I-2).** Dla `newest`, ktorego najnowszy rekord to `.xyz`, `download_sheet` zwroci sciezke standardowa, ktora NIE istnieje (albo wskazuje starsza kampanie), CLI wypisze `Downloaded to <nieistniejacy>`, status listy `completed`, a wycinek przewroci sie na odczycie. Plan musi zdefiniowac wynik: albo twarda porazka arkusza (`DownloadError` "kampania w formacie .xyz nieobslugiwana — uzyj --campaigns all"), albo `SheetFetch.path` = plik kampanii. Rekomendacja: `DownloadError` (prosto, uczciwie), `all` zachowuje plik `.xyz` z warningiem |
| Q4 | skip wycinka po istnieniu pliku wyniku, bez zmian w 0.7.0 | **ZGODA.** Wycinek to produkt pochodny; `--force` przebudowuje; alternatywa = siec przy kazdym skip. Zapis w CHANGELOG/ARCHITECTURE |
| Q5 | pomijanie warstw tylko w `all` | **ZGODA.** W `newest` pierwsza warstwa z dopasowaniem konczy szukanie, wiec pominiecie oszczedza wylacznie zapytania, ktore i tak dalyby brak pokrycia, a kosztem jest utrata daty do komunikatu (f) i uzaleznienie `record_cache` od granicy (h). Errata (g) — plan tego nie wymienia jako erraty |
| Q6 | wolumen `all` orto: tylko dokumentacja + zalecenie `--min-year` | **ZGODA z uwaga.** 10 kampanii RGB dla N-34-139-A-c-1-1 potwierdzone. Dodatkowy przebieg resolve w CLI jest zbedny — ale podsumowanie `Downloaded <n> campaign files` jest po fakcie; tani kompromis: `logger.info` liczby kampanii per arkusz w `_fetch_campaigns` (zero kosztu, widoczne w DEBUG) |
| Q7 | sidecar standardowy = ZWYKLY plik (kopia sidecara kampanii + `extra.link` + `extra.link_target`) | **ZGODA.** Symlinkowany sidecar nie moze niesc `extra.link` innego niz cel; `_note_reuse` (`manager.py:818` `os.replace`) i tak zamienilby go w plik. Errata (d) |
| Q8 | `request.campaigns` zawsze, `request.min_year` tylko gdy podane; LAZ `request.campaigns` tylko gdy `all` | **ZGODA.** Wzor E16 LAZ; sidecary `newest` LAZ bez zmian = brak szumu w diffach testow. Errata (i) — plan nie wymienia |
| Q9 | godlo CZ pod `auto` + `all`/`--min-year` -> `Info:` i tor CZ | **ZASTRZEZENIE (I-3).** Precedens w kodzie mowi inaczej: dla godla CZ `_reject_non_nmt_for_cz` (`download_cmd.py:902-904`) daje `Error:` kod 1 dla `--product nmpt/orto` TAKZE pod `auto` — godlo jednoznacznie wskazuje kraj, wiec "opcja dotyczy tylko czesci PL" jest pusta (czesci PL nie ma). Rekomendacja: `Error:` jak dla jawnego `--country cz` (spojnosc z nmpt/orto); `Info:` zostaje dla OBSZARU pod `auto` z CZ wsrod krajow. Jesli uzytkownik potwierdzi litere ADR — zapisac w CLAUDE.md, ze godlo CZ + `all` zachowuje sie inaczej niz godlo CZ + `nmpt` |
| Q10 | czesciowa porazka `all` = twarda porazka arkusza (kod 1), pobrane kampanie zostaja, link na najnowsza pobrana | **ZGODA.** Spojne z R5 ("kazda twarda awaria -> kod 1") i z idempotencja (ponowny przebieg reuzywa pliki) |

---

## 6. Lista problemow

### ISTOTNE

**I-1. E15 w CLI: `manager.last_sheet.skipped` na atrapie managera.**
`tests/test_cli.py` buduje `Mock()` jako manager (`_mock_manager`, 8 uzyc;
`:632` i inne) — `manager.last_sheet` bedzie `Mock`, `.skipped` tez `Mock`
(prawdziwy), wiec CLI wypisze "Skipped" zamiast "Downloaded to" i padna
testy `:740`, `:1924`, `:3820`, `:3837` (i inne), wbrew kryterium T8 ("307
zielone, zmiany tylko w testach E15"). Dzisiejszy kod ma analogiczna straz
`isinstance(target, Path)` (`download_cmd.py:995`).
*Poprawka planu (T8, 1.8):* `fetch = manager.last_sheet; skipped =
isinstance(fetch, SheetFetch) and fetch.skipped` (import `SheetFetch` z
`kartograf.download.manager`); mutacja (h): `getattr(fetch, "skipped",
False)` -> pada test z atrapa managera asertujacy "Downloaded to".

**I-2. `newest` z kampania `.xyz`: nieistniejaca sciezka standardowa (Q3, R17).**
Opis w sekcji 5/Q3. Plan musi okreslic `SheetFetch.path`, wynik
`download_sheet`, status listy i komunikat CLI dla przypadku "zadna
kampania w formacie providera".
*Poprawka planu (T7, R17):* w `_fetch_campaigns` gdy `local` niepuste, a
`linkable` puste -> `raise DownloadError(f"{godlo}: najnowsza kampania
{ref.dirname} ma format {ext} nieobslugiwany jako sciezka standardowa —
plik zachowany w kampanie/; uzyj --campaigns all", godlo=godlo)` (status
`failed`, kod 1); test `test_xyz_newest_is_hard_failure_but_file_kept`.
W `all` z co najmniej jedna kampania `.asc` — jak w planie (warning).

**I-3. Q9: godlo CZ pod `auto` + `all`/`--min-year` — niespojnosc z
istniejacym precedensem.** `download_cmd.py:902-904`: godlo CZ + PL-only
produkt = `Error:` niezaleznie od `auto`. Plan proponuje `Info:` dla
PL-only opcji kampanii. Dwie rozne reguly dla tej samej sytuacji (godlo
jednoznacznie CZ + opcja tylko-PL).
*Poprawka planu:* przedstawic uzytkownikowi jako pytanie z tym precedensem;
rekomendacja: `Error:` (tabela 1.8 wiersz "godlo CZ pod auto" -> `Error:`,
test `test_cz_godlo_auto_with_all_is_error`); `Info:` tylko dla obszaru.

**I-4. Errata ADR-030 niekompletna.** Plan deklaruje errate dla Q1 i Q7;
od litery ADR odbiegaja takze Q2 ((j): nowy zakaz `--min-year` z
`--target-crs`), Q5 ((g): pomijanie warstw tylko w `all`) i Q8 ((i):
`request.min_year` warunkowo).
*Poprawka planu (T10 / krok koordynatora):* lista erraty = (d) Q7, (g) Q1 +
Q5, (i) Q8, (j) Q2 (+ Q9 jesli rozstrzygniete inaczej niz litera).
DECISIONS.md jest CRLF — osobny, swiadomy krok, jak plan juz zaznacza.

### DROBNE

**D-1. `ensure_standard_link` przestawia link na STARSZA kampanie, gdy
sidecar celu jest nieczytelny/brak** (`cur_key is None` -> warunek
"zostaw" nie zachodzi). Zapis sidecara kampanii jest best-effort, wiec to
realna, choc rzadka sciezka regresu (Review Focus 1).
*Poprawka (T2, 1.3):* fallback klucza z nazwy katalogu kampanii
`<date>_<id>` -> `(date, "", "")` (data z `cur.parents[k].name` gdzie
`parts` zawiera `kampanie`); test
`test_missing_target_sidecar_still_prevents_regression`; mutacja: usun
fallback -> test pada.

**D-2. Komunikat `no_coverage` z cache `campaigns_cache` przy
`scanned_from`.** Wpis `{"no_coverage": True, "message": "Brak kampanii
od roku 2024 (...)", "scanned_from": 2024}` jest wazny dla `min_year=2025`
(`_covers`) i odda komunikat z granica 2024 zamiast 2025.
*Poprawka (T6):* przy trafieniu `no_coverage` z `scanned_from is not None`
budowac komunikat na nowo z biezacym `min_year` (nie `cached["message"]`);
asercja w `test_all_cache_partial_scan_valid_only_for_higher_bound`.

**D-3. Tabela 0.1 pomija `cutout.py:589`** (`check_pl_cutout_disk_space`:
arkusz ze sciezka standardowa `exists()` = nie liczony do pobrania). Pod
`newest` z nowsza kampania plik i tak zostanie pobrany — szacunek
"na pewno nie wystarczy" pozostaje dolnym ograniczeniem, wiec zachowanie
jest akceptowalne, ale T11 grep `.exists()` ma to ocenic swiadomie.
*Poprawka:* dopisac wiersz do 0.1 ("bez zmian — dolne ograniczenie;
wiszacy link = `exists()` False = liczony") i wzmianke w docstringu.

**D-4. `tests/test_sidecar.py:381` i `test_download_manager.py:143,:225`
uzywaja prawdziwego `GugikProvider()`** — po T6 (`supports_campaigns =
True`) i T7 wejda w tor kampanii. Asercje najpewniej przezyja (sidecar
standardowy kopiuje `extra` celu), ale `test_sidecar.py` nie ma wlasciciela.
*Poprawka:* dopisac `tests/test_sidecar.py` do T7 ("tylko jesli pada") i
wymienic te trzy testy w kryterium T7 jako kontrolowane.

**D-5. Przestarzala kopia o tym samym rozmiarze bez `refresh`** (kampania
podmieniona przez inny proces albo `--force` uruchomiony gdzie indziej).
*Poprawka (T2 `linked_campaign`):* dla `extra.link == "copy"` traktowac
`target.stat().st_mtime > link.stat().st_mtime` jak niezgodnosc (None ->
ponowna kopia); test `test_copy_older_than_target_is_replaced`.

**D-6. Test R1 nie cwiczy zadnego wyscigu** (4 rozne godla). Ochrona jest
w `expand_sheets` (`manager.py:426-435`), ktorego zaden test kampanii nie
pilnuje.
*Poprawka (T7):* `test_duplicate_godla_in_list_download_once_and_link_once`
(`download_sheets([G, G, G])`, `max_workers=4`, `downloads == [url]`,
jeden `ensure`); mutacja: usun `seen` z `expand_sheets` -> test pada
(albo udokumentowac, ze `test_parallel_all...` jest tylko smoke).

---

## 7. Drobne uwagi redakcyjne (bez wagi)

- 1.6: `DownloadManager.__init__` — `getattr(provider, "supports_campaigns",
  False) is True` trafnie omija `Mock(spec=GugikProvider)`; warto dodac
  do docstringu, ze `FakeCampaignProvider` w testach MUSI miec atrybut
  klasowy (`True`), nie instancyjny `Mock`.
- Sketch `_fetch_campaigns`: `except NoCoverageError: raise` jest martwy
  (`download_to` rzuca tylko `DownloadError`, `http.py:140`) — usunac albo
  zostawic z komentarzem "na przyszlosc".
- T6 `test_nmpt_inherits_campaigns`: `GugikNmptProvider` ma wlasne
  `_CACHE_PRODUCT = "nmpt"` i `WMS_SKOROWIDZE_ENDPOINTS` (`gugik_nmpt.py:63,:93`)
  — hook `_skorowidz_query` w `GugikProvider` musi czytac te atrybuty przez
  `self`, nie przez `GugikProvider.` (plan tego nie precyzuje; mutacja
  "endpoint z klasy bazowej" -> test NMPT pada).
- Sekcja 6 krok 8: "84466 (0,07 m)" — w fixturach orto
  `charakterystykaPrzestrzenna` jest `None`; rozdzielczosc musi pochodzic
  z innego pola rekordu (nie ma znaczenia dla kodu, ale opis kroku live
  powinien wskazac pole, zeby weryfikator wiedzial, co porownac).

---

## 8. Top 5 problemow (jednym zdaniem)

1. I-1: `manager.last_sheet.skipped` na atrapie `Mock()` jest prawdziwe, wiec E15 wypisze "Skipped" i przewroci istniejace testy CLI — potrzebna straz `isinstance(fetch, SheetFetch)`.
2. I-2: `newest` z najnowsza kampania `.xyz` zwraca nieistniejaca sciezke standardowa jako sukces — zdefiniowac twarda porazke arkusza.
3. I-3: dla godla CZ pod `auto` kod daje `Error:` przy `--product nmpt`, a plan proponuje `Info:` przy `--campaigns all` — ujednolicic (rekomendacja: `Error:`).
4. I-4: errata ADR-030 musi objac Q1, Q2, Q5, Q7 i Q8, nie tylko Q1 i Q7.
5. D-1: brak/nieczytelny sidecar kampanii-celu pozwala `ensure_standard_link` cofnac link na starsza kampanie — fallback klucza z nazwy katalogu `<date>_<id>`.
