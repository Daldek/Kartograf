# fix-links: raport (branch `fix/e2e-links`, od develop @ bef87501)

Commity (Conventional Commits, bez Co-Authored-By):

- `bbf270e9` fix(links): potwierdzenie dowiazania trescia bez liczby dowiazan (cifs bez serverino)
- `a60d128a` docs(links): potwierdzanie dowiazan na udziale SMB bez serverino

Brama: `scripts/gate.sh` z korzenia worktree = **GATE OK (193 s)**: ruff check, ruff format --check,
mypy (`kartograf/ tests/`), pytest offline: **7170 passed, 18 deselected**.

## Zakres i wynik

| Znalezisko | Status |
|---|---|
| e2e-A P2-1: sciezka standardowa i `full_sheet/` cofaja sie na starszy lot na cifs bez `serverino` | **naprawione** (na zywo przed/po) |
| e2e-E P2-1: `link_target()` zwraca `None` dla prawidlowych dowiazan tuz po odczycie | **naprawione** (na zywo przed/po) |
| e2e-E P2-1 skutek uboczny: zbedny zapis sidecara dowiazania (i podmiana dowiazania) przy `lokalna wersja` po odczycie | **naprawione** (na zywo, PL i CZ, przed/po) |
| e2e-A D5 / e2e-E "Uwagi do dokumentacji": USAGE 4/7, ARCHITECTURE 3.3.1 nie opisuja skutku | **dokumentacja zaktualizowana** |

Nie zostala podjeta zadna decyzja produktowa "na zgadywanke"; dwie opcje do decyzji sa na koncu.

## Przyczyna (potwierdzona pomiarem na udziale)

Udzial `<scratch-dir>` jest cifs bez `serverino` (`vers=3.1.1,cache=strict,actimeo=1,closetimeo=1,nounix`):

- dwie nazwy jednego pliku maja rozne i-wezly (`samefile` zawsze False; np. ino 7324263 vs 7324296),
- **kazde `open()` sciezki (takze bez odczytu) ustawia `st_nlink == 1` dla TEJ sciezki na ok. 2-2,5 s**
  (druga nazwa, nieotwierana, zostaje przy 2). Pomiar: `stat` (a,b) = (2,2) w spoczynku, (1,2) zaraz po
  `open+read`, (2,2) po ok. 2,5 s.
- `_same_content_hardlink` wymagalo `st_nlink >= 2` OBU plikow, wiec: (1) dowiazanie czytane przez kogokolwiek
  w ostatnich sekundach (inny program, poprzednie uruchomienie, skrypt z `sha256sum`) uchodzilo za nieznana
  sciezke -> `ensure_link` przepinal ja na wybrany lot (przy `--max-year 2022` starszy = **cofniecie**) i
  przepisywal sidecar; (2) kazdy potwierdzajacy odczyt (hash) ustawial `st_nlink = 1` dla NASTEPNEGO
  wywolania, wiec `link_target` w petli dawal na zmiane wersje i `None` (E: 0/14; moja petla z okresem 1 s:
  `ok, NONE, ok, NONE ...`).

## Zmiana

`kartograf/download/links.py`:

- `_hold(link) -> _Held | None` (nowe, prywatne): cel z sidecara dowiazania (`extra.link == "hardlink"` +
  `extra.link_target`), potwierdzony `samefile` albo - gdy `samefile` False - trescia (`_same_content`:
  ten sam rozmiar i sha256 pliku = sha256 sidecara wersji). **Liczba dowiazan nie bierze udzialu w
  potwierdzeniu.** `_Held.lone` = liczby dowiazan (czytane PRZED odczytem pliku) obu sciezek < 2, czyli
  prawdopodobna niezalezna kopia.
- `linked_version(link)` = `_hold(...).version` (ten sam kontrakt zewnetrzny: Path albo None).
- `ensure_link`: liczy po `_hold`; "zostaje" jak dotad (ten sam cel bez `refresh`, nowszy klucz, rowny klucz bez
  `refresh`) i **wtedy nic nie zapisuje** - wyjatki: (a) `lone` (niezalezna kopia, np. po `rsync -a` bez
  `-H`) jest zamieniana w hardlink TEJ SAMEJ wersji (`changed=True`; nigdy innej, wiec nie cofa), (b) sidecar
  bedacy symlinkiem jest przepisywany jak dotad. Przepiecie na `target` bez zmian.
- Usuniete `_same_content_hardlink` (jedyne odwolania: docs, PROGRESS - historyczne).
- Wyniki na dysku lokalnym (`samefile` True): identyczne jak przedtem (ta sama sciezka, zero dodatkowych odczytow).
  Roznica na ext4 tylko dla niezaleznej kopii: `linked_version`/`link_target` zwraca teraz wersje, ktorej tresc
  plik ma (wczesniej `None`); `ensure_link` nadal zamienia kopie w hardlink (test `..._restored_as_hardlink`),
  a kopia NOWSZEJ wersji nie jest juz cofana na starsza (wczesniej relink na wybrana).

`kartograf/store.py::link_target`: tylko docstring (kontrakt bez zmian w sygnaturze).

## Testy regresyjne (offline; symuluja cifs bez serverino na prawdziwym hardlinku)

Nowy helper `tests/smb_share.py` (`no_stable_inodes`: `os.path.samefile` False; `report_one_link`: `os.stat`/`os.lstat`
zwracaja `st_nlink == 1` dla wskazanych sciezek albo wszystkich) - uzywany w `monkeypatch.context()`.

- `tests/test_links.py`:
  - `test_link_does_not_move_back_while_smb_reports_one_link[False/True]` (e2e-A: nie cofa na starszy, nic nie
    przepisane: inode dowiazania i sidecara, mtime i bajty sidecara bez zmian),
  - `test_local_version_with_one_reported_link_writes_nothing` (e2e-E skutek uboczny),
  - `test_link_stays_on_newer_version_when_every_path_reports_one_link` (liczba 1 takze dla pliku wersji),
  - `test_independent_copy_of_a_newer_version_is_not_moved_back`, `..._of_the_version_is_restored_as_hardlink`
    (ext4: kopia -> hardlink tej samej wersji),
  - `test_lone_copy_is_restored_without_inode_identity`.
  Zmienione istniejace: `test_regular_file_claiming_hardlink_is_not_trusted` -> `..._restored_as_hardlink`
  (pierwsza asercja `linked_version(kopia) is None` odwrocona - swiadoma zmiana opisana wyzej),
  `test_single_link_copy_rejected_without_inode_identity` -> `test_lone_copy_is_restored_...` (zamiast "kopia
  nie jest dowiazaniem" - "kopia jest ta wersja, ale wraca do hardlinku"); lokalny `_no_inode_identity` zastapiony
  helperem.
- `tests/test_store_api.py::test_link_target_is_stable_while_smb_reports_one_link` (4 warianty: link/`full_sheet/`
  x liczba 1 tylko dla dowiazania/dla wszystkich; 3 kolejne wywolania zgodne; zmieniona tresc -> `None`).
- `tests/test_manager_campaigns.py::test_manager_range_keeps_link_on_newer_flight_while_smb_reports_one_link`
  (caly `DownloadManager` z `max_year=2022`, dowiazanie zostaje na 2025, `link_outside_range`).

Sprawdzone, ze nowe/zmienione testy PADAJA na kodzie develop (pristine `git archive`, 7 z `test_links.py`,
5 ze `store_api`/`manager_campaigns`) i przechodza po zmianie.

## Dowody na zywo (udzial cifs bez serverino; dane pod `<katalog-danych>/fix-links/...`)

Dane: `N-33-58-A-c-1-3` 0,5 m EVRF2007 `--full-sheet` (std -> 2025 sha `84458fd0`, `full_sheet/` -> 2022 sha `78b8e279`).
Kod "przed" = develop bef87501 (domyslny import venv / `git archive` w /tmp), "po" = worktree.

1. **e2e-A, przed**: uruchomienie 1 (`... --full-sheet -o <katalog-danych>/repro-A2`), `sha256sum` sciezek
   (dowolny odczyt), uruchomienie 2 z `--max-year 2022`: rc 0, wydruk tylko
   `...asc: lokalna wersja 2022-09-04_79054` (bez Warning/Info o dowiazaniu), sha std **78b8e279** = cofniete.
   UWAGA: dwa uruchomienia bez odczytu pomiedzy (przerwa ok. 2 s ze startem Pythona) NIE odtwarzaja bledu -
   wyzwalaczem jest odczyt sciezki w ciagu ok. 2,5 s przed sprawdzeniem (u testera robil go skrypt zbierajacy
   sha); powtorzone tak samo jak w raporcie.
   **Po**: ten sam skrypt na swiezym magazynie: run 2 rc 0, `Info: 1 dowiazan wskazuje lokalny lot spoza tego
   zadania (dowiazanie nigdy nie cofa sie na starszy lot)` + `sciezka standardowa -> dowiazanie 2025-01-30_84020`,
   std **84458fd0**, full 78b8e279. Petla 3x (odczyt + run 2): std 84458fd0 za kazdym razem; dodatkowo proces
   odczytujacy std co 0,1 s przez caly run 2 (stale `nlink=1`): std 84458fd0, inode/mtime std, full i obu
   sidecarow **bez zmian** przed/po.
2. **e2e-E `link_target`, przed** (petla: 1. wywolanie, 2 zaraz po, 4 s przerwy): `ok, NONE, NONE, NONE, NONE`;
   os czasu z okresem 1 s: `ok, NONE, NONE, ok, NONE, ok, NONE, ok ...` (kazde `ok` odczytuje plik i ustawia
   nlink = 1 dla nastepnego). **Po**: `ok` w kazdym wywolaniu (2 petle, lacznie 15 wywolan, takze przy `nlink=1`).
3. **e2e-E skutek uboczny, przed**: po `sha256sum` sciezki `elevation download` (lokalna wersja) zmienil inode
   dowiazania (7828785 -> 7828801) i przepisal sidecar (mtime 13:53:08 -> 13:54:02); CZ (`CTES96`,
   `--vertical-crs Bpv`, jak w E): inode 7829068 -> 7829083, sidecar 14:07:09 -> 14:07:24. **Po**: inode i mtime
   sidecara bez zmian w obu torach.
4. Biblioteka (skrypt na zywo): (a) po odczycie dowiazania `ensure_link(link, starszy, refresh=True)` zostaje na
   nowszym bez zapisu; (a2) lokalna wersja bez zapisu; (a3) `link_target` 10/10 w petli co 0,1 s (przed: 1/10);
   (c) oba pliki otwarte tuz przed (nlink 1/1): zostaje na nowszym, `changed=True` (podmiana na ten sam plik
   przeszla bez bledu na cifs), nlink 2; (b) niezalezna kopia (nlink 1/1, `cp`) -> `changed=True`, hardlink
   NOWSZEJ wersji (nie cofnieta), potem no-op. Przed: (a), (a2), (a3), (c), (b) wszystkie FAIL (cofniecie/zapis).

## Dokumentacja

- USAGE 4 ("Wymagane hardlinki", "Kopiowanie `data/`") i USAGE 7 (koszt potwierdzania; dodane: tak samo
  `link_target`; liczba dowiazan zmienia sie po kazdym odczycie, takze samego sprawdzenia).
- ARCHITECTURE 3.3 regula 6 (kontrola dowiazania; `links._same_content`, `_hold`, `_Held.lone`) i 3.3.1 (`link_target`).
- Docstringi `links.py` (modul, `_hold`, `_same_content`, `linked_version`, `ensure_link`) i `store.py::link_target`.
- Nie ruszone (poza zakresem lub cudze): CHANGELOG, PROGRESS, DECISIONS, `llms.txt`/katalog (brak wzmianek o SMB/hardlinkach),
  USAGE 2 `link_target` (akapit sasiaduje z poprawkami FixStoreProject; pozostaje prawdziwy).

## Proponowany wpis CHANGELOG (Naprawione, styl [0.8.0], ASCII)

```
- Dowiazanie na udziale SMB/cifs bez `serverino` (sciezka standardowa i `full_sheet/`) nie cofa sie juz na
  starszy lot, gdy plik byl chwile wczesniej czytany (inny program, poprzednie uruchomienie): klient cifs
  zglasza wtedy `st_nlink` = 1 przez kilka sekund, a potwierdzenie trescia wymagalo `st_nlink` >= 2 obu
  plikow, wiec sciezka uchodzila za nieznana i byla przepinana na wybrany (starszy) lot - np. `--max-year 2022`
  zaraz po pobraniu z `--full-sheet`, bez Warning/Info (test na zywo 2026-10-19). Ta sama przyczyna dawala
  `link_target` = `None` na przemian z poprawnym wynikiem (kazdy potwierdzajacy odczyt ustawial `st_nlink` = 1
  dla nastepnego wywolania) i zbedny zapis (podmiana dowiazania, przepisany sidecar) przy `lokalna wersja`.
  Potwierdzenie bez stabilnych i-wezlow opiera sie teraz na tresci (rozmiar i SHA-256 z sidecara wersji), bez
  liczby dowiazan. Plik o tresci wersji liczy sie jako ta wersja takze jako niezalezna kopia (np. po `rsync -a`
  bez `-H`); `link_target` zwraca wtedy wersje (dotad `None`), a pobranie zamienia kopie z powrotem
  w dowiazanie tej samej wersji. Dysk lokalny i udzialy ze stabilnymi i-wezlami: bez zmian.
```

## Propozycja errata ADR (nie edytowalem DECISIONS.md)

```
ADR-036, errata (2026-10-19, e2e 0.8.0): potwierdzenie dowiazania na udziale bez stabilnych numerow i-wezlow
(SMB bez `serverino`) opiera sie wylacznie na tresci: ten sam rozmiar i SHA-256 pliku = SHA-256 z sidecara wersji,
na ktora wskazuje sidecar dowiazania. Warunek "obie sciezki maja wiecej niz 1 link" (akapit przy "Magazyn wymaga
systemu plikow z hardlinkami") USUNIETY: klient cifs zglasza `st_nlink` = 1 dla sciezki po jej otwarciu (takze po
odczycie potwierdzajacym) przez kilka sekund, wiec warunek cofal dowiazanie na starszy lot ("nigdy wstecz"
naruszone) i dawal niestabilne `link_target`. Sciezka o tresci wersji JEST ta wersja (`links._hold`);
niezalezna kopia (zadna ze sciezek nie zglasza drugiej nazwy) jest zamieniana przez `ensure_link` w hardlink TEJ
samej wersji. ADR-045: `link_target(kopia)` zwraca wersje zamiast `None`; kontrakt "confirmed on disk" = ta sama
tresc, nie ta sama i-wezel.
```

## Zrodla niepewnosci i decyzje do podjecia

1. **Semantyka `link_target`/`linked_version` dla niezaleznej kopii (ext4 tez).** Wybrana: zwraca wersje (identyfikacja
   po tresci, naprawa hardlinku osobno w `ensure_link`). Alternatywa B: zwracac `None` dla `_Held.lone` (jedna
   linia w `linked_version`) - zachowuje stare `None` dla kopii, ale przywraca zalezosc wyniku od liczby dowiazan
   (oba pliki otwarte < 2,5 s wczesniej => znow `None`; Archiwista czytajaca wersje i dowiazania w jednej petli
   moze to trafic). Rekomendacja: zostawic A. Do decyzji, jesli Archiwista liczy "oszczednosc miejsca" po `link_target`.
2. **Siatka bezpieczenstwa "tresc = znana lokalna wersja" bez uzytecznego sidecara dowiazania** (np. nieudany zapis
   sidecara po przepieciu, ADR-030 errata 10 M-8; sidecar skasowany recznie): dalej "sciezka nieznana" -> relink na
   wybrana wersje, wiec po `--max-year` starszym niz wersja trzymana przez dowiazanie MOZE sie cofnac (udokumentowany
   projekt M-8, poza reprodukcja e2e). Wymaga zapisu tresc-scan (pelny odczyt linku + `list_versions` + sha) i zmiany
   zdania "sidecar = JEDYNE zrodlo celu" w module/ADR-030. Nie wdrozone: wymaga decyzji; rekomendacja: nie teraz.
3. Odrzucone warianty potwierdzania: ponowny `stat` po >= 2 s (niemozliwe do ograniczenia: u E do ok. 50 s, a
   potwierdzajacy odczyt sam otwiera okno), tolerancyjne "max(nlink) >= 2" (zalezy od przejsciowej liczby, zawodzi,
   gdy otwarto oba pliki), wykrywanie FS z `/proc/self/mountinfo` (tylko Linux, kruche), sonda zapisu (link+samefile
   przy kazdym uruchomieniu = zapis do magazynu).
4. Rezydualne: gdy OBA pliki zglaszaja `nlink = 1` (np. wersja i dowiazanie otwarte < 2,5 s wczesniej), `ensure_link`
   moze podmienic dowiazanie na hardlink TEJ SAMEJ wersji (`changed=True`, bezpieczne, na cifs bez bledu - sprawdzone
   na zywo); nigdy na inna wersje.

## Uwaga procesowa

`git stash` jest WSPOLNY dla wszystkich worktree (jeden `refs/stash`): moje `git stash pop` zastosowalo w moim drzewie
niezacommitowane zmiany FixStoreProject (store.py/store_geometry.py), a ich pop - moje `links.py`. Naprawione
(zamiana lataczkami `git diff`/`git apply`, bez utraty), ostrzezenie wyslane do wszystkich agentow. Wniosek dla
koordynatora: przed integracja sprawdzic `git diff` w `fix/e2e-store-project` (powinno zawierac tylko ich pliki).

## Stan po pracy

- Worktree czysty, 2 commity na `fix/e2e-links`; scratch w /tmp i dane pod
  `<katalog-danych>/fix-links/` sprzatniete.
