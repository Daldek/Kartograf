# Audyt dokumentacji Kartografa przed tagiem v0.8.0 (bez README.md)

Galaz `docs/audit-0.8.0` (worktree `<worktree>`, od develop e019126a).
Zakres: CLAUDE.md, llms.txt, docs/*.md (USAGE, ARCHITECTURE, SCOPE, PRD, DEVELOPMENT_STANDARDS,
DECISIONS, CHANGELOG [0.8.0], PROGRESS - tylko poczatek). Zrodlo prawdy: kod worktree
(`kartograf/catalog/commands/`, `__all__`, `catalog --params --json`, wyjatki, notices, SCHEMAS).
Bez zmian w kodzie i testach. Bez sieci (tylko `--help`, `catalog`, `parse`, walidacja bez sieci).

## Incydent proceduralny (naprawiony)
Pierwsze wywolanie `edit` poszlo sciezka wzgledna i trafilo w GLOWNY checkout
(`<repo>`: CLAUDE.md i USAGE.md, 3 hunki). Wykryte od razu,
cofniete odwrotnym zastosowaniem dokladnie tego diffu (`git apply -R`); stan glownego checkoutu:
`git status` czysty, HEAD e019126a (sprawdzone kilkakrotnie po powrocie). Wszystkie pozniejsze
edycje: sciezki bezwzgledne w worktree.

## Co sprawdzono (metody) i wynik

Automatyczne kontrole (skrypty w katalogu scratch, nie w repo):
- Komendy CLI w przykladach: 400 linii (CLAUDE, llms, USAGE, SCOPE, PRD, ARCHITECTURE, CHANGELOG 0.8.0,
  PROGRESS) przeszlo prawdziwy parser (`create_parser` + `parse_command` + `validate_command`);
  94 linie z placeholderami (`<godlo>`, `...`, `area.shp`) zastapione/pominiete; bledy tylko tam, gdzie
  przyklad jest celowo bledny (USAGE 9.2 brak `--vertical-crs`, 1.11 `--network gravity --teryt`) -
  tresc bledow zgodna z prawdziwym wyjsciem.
- Bloki Pythona: 54 bloki (USAGE, SCOPE, PRD, ARCHITECTURE, STANDARDS, CHANGELOG 0.8.0, llms) - skladnia,
  importy z `kartograf`/`__all__`, nazwy argumentow nazwanych i wymagane argumenty zgodne z sygnaturami.
- Cytaty `nazwa(arg, klucz=...)` w backtickach: 210 porownanych z sygnaturami (13 trafien: wszystkie
  to celowe opisy starej postaci albo `path` zamiast `hsg_path`, patrz P3 nizej).
- Flagi: 56 flag katalogu; w aktualnych dokumentach nieznana tylko `--campaigns` (CLAUDE.md, naprawione),
  reszta to historia (CHANGELOG starszych wersji, DECISIONS, PROGRESS).
- Odwolania: 271 odwolan "USAGE/ARCHITECTURE/STANDARDS/SCOPE/PRD n.m" - nierozwiazane tylko 9 w dzienniku
  PROGRESS (historia); 274 linki i kotwice markdown OK; sciezki plikow repo OK; zmienne srodowiskowe
  (CLMS_CREDENTIALS, KARTOGRAF_DEBUG, KARTOGRAF_PYTHON, XDG_CACHE_HOME, LOCALAPPDATA) OK.
- Schematy: 16 nazw `kartograf-*/1` w dokumentach = rejestr SCHEMAS = katalog; tabela ARCHITECTURE 3.6
  (klasy, moduly, klucze i ich kolejnosc) = kod; tabela narzedzi MCP USAGE 9.6 (29 wierszy: rodzina,
  adnotacje RO/ND/D/I/OW, funkcja, dokument) = `tool_specs()`; kody Notice (31) wszystkie w tabeli USAGE,
  poziomy info/warning zgodne; tabele kodow bledow i wyjscia = katalog (+ test).
- Liczby z kodu: ZABAGED 22, Data50 69, Data250 116, BDOT10k 15, granice specjalne PRG 44, 29 narzedzi MCP,
  36 komend-lisci + `catalog` z `--json`, 12 komend danych, rozmiary widokow katalogu (7,6 / 29,7 / 299 tys.
  znakow; MCP: tools/list 28 597, przeglad 7315 znakow) - zgodne z dokumentami.
- Graf zaleznosci ARCHITECTURE 2 policzony z AST: 1 niezgodnosc (naprawiona); drzewo modulow = pliki na dysku.
- Eksporty: SCOPE 2.10 = `__all__` (165 nazw) dokladnie; PRD 5 = `__all__` bez `list_partitions` (naprawione).
- DECISIONS: 47 wpisow = 47 wierszy indeksu, tytuly i daty zgodne, kotwice dzialaja; 3 statusy rozjechane
  miedzy indeksem a wpisem (naprawione); CRLF zachowane (0 samotnych LF, diff = 4 linie).
- Bateria 32 twierdzen USAGE o bledach "przed siecia" (kod 2 + tresc komunikatu) wykonana offline (`unshare -rn`):
  31 zgodnych, 1 niezgodnosc tylko w moim oczekiwaniu (nie dokumentacji).
- Testy dokumentacji (`pytest -m 'not live' tests/test_docs_tables.py tests/test_llms_txt.py
  tests/test_links.py tests/test_version.py`): 59 passed przed i po zmianach.

Czytane w calosci lub w duzej czesci: CLAUDE.md, llms.txt, USAGE (sekcje 1.1-1.11, 2, 3, 4, 5-9; ok. 90%),
CHANGELOG 0.8.0 (poczatek, wpisy interfejsu agentow, KD, BREAKING - ok. 40% linii; reszta tylko
automatycznie: sygnatury, usuniete nazwy `__all__` vs v0.7.2 - wszystkie 15 usunietych i 114 dodanych nazw
wystepuje w CHANGELOG), ARCHITECTURE (naglowek, sekcje 2, Moduly, 3.3.1, 3.5, 3.6, 4 wstep; reszta 4.x
wyrywkowo i automatycznie), SCOPE (2.1-2.3, 2.9, 3.2, 7), PRD (naglowek, 3.1, 5), STANDARDS (naglowek, 6, 11),
PROGRESS (tabela statusu, CP14, "START NASTEPNEJ SESJI"). Nieprzeczytane/niezweryfikowane linia po linii:
SCOPE 2.4-2.8 i 2.11-2.17, 3.1, 3.3, 4-6; PRD 3.2-3.27 (poza eksportami), 4, 6-9; STANDARDS poza 6 i 11;
ARCHITECTURE 4.1-4.11 (tylko kontrole automatyczne: identyfikatory, komunikaty, odwolania); CHANGELOG
0.8.0 wiersze ok. 330-440 i 850-1600 (tylko automatycznie); specyfikacje/plany w docs/superpowers (statusy
nie badane).

## Poprawki (commit 23430e70: 8 plikow, +53/-37)

| Plik | Co | Dlaczego |
|---|---|---|
| CLAUDE.md:74 | `--campaigns` -> `--all-campaigns` | flaga usunieta w 0.8.0 (CHANGELOG), katalog ma tylko `--all-campaigns` |
| CLAUDE.md:72 | "kampanie `kampanie/`" -> "wersje `versions/` (dawniej `kampanie/`)" | uklad 0.8.0 (ADR-036); ARCHITECTURE 3.3 opisuje `versions/` |
| USAGE:173-177 | tresc bledu `PL nie ma rozdzielczosci ...` z dopiskiem `; uklad wysokosci nieznany: 100m` | pelny komunikat z kodu (NMT 100 m); wykonane offline |
| USAGE:195-199 | godla 8-czlonowe PL-1992 podaje sie w `--sheet` (ADR-043 D10) | brak tej informacji; sprawdzone `validate_command` |
| USAGE 1.7 (`Info:`) | powody `index_unsupported` wg kodu (`_REASONS`), bez godel 8-czlonowych | godla 8-czlonowe sa od 0.8.0 pobierane (ADR-041 errata 4, ADR-043 D10, CHANGELOG, SCOPE, PRD) |
| USAGE sek. 7 | usuniety punkt "godla 8-czlonowe ... nie sa pobierane, raport wymienia je w `Info:`" | sprzeczny z kodem i ADR-041 errata 4 |
| USAGE 1.8 (przyklad limitu) | `2 plikow` -> `2 pliki` | kod: `count_text(count, *FILES)` |
| USAGE sek. 3 | `VersionedFile.unverified`: dodane `"unchecked"` (tryb domyslny) | docstring `fetch.py`, CHANGELOG (ADR-036 errata 3) |
| USAGE sek. 4 | kod Notice przy awarii skorowidza `UNVERIFIED_LOCAL` -> `CHECK_FAILED` | `manager.py:1878`, CHANGELOG (BREAKING) |
| USAGE 4.3 (wstep) | dopisane `geodesy download` | wszystkie 12 komend danych maja `--check-updates/--upgrade/--force` |
| ARCHITECTURE 2 (graf) | krawedzie `transport -> notices, providers` + dwie notatki | `unit_package.py`, `atom.py`, `index_records.py` (graf z AST rozni sie tylko tym) |
| ARCHITECTURE 4.1, 4.9 | usuniete przyklady godel 8-czlonowych jako "spoza SheetParser" | SheetParser przyjmuje je od planu E1 |
| CHANGELOG 0.8.0 (3 miejsca) | `--plan` bez trybu, `project init` bez `--output`, brak wartosci domyslnych: kod 1 -> 2; "Co zrobic: kod 2 - kod 1" -> "nic" | stan koncowy (ADR-046): bledy wejscia = 2 (wykonane: wszystkie trzy zwracaja 2); stara instrukcja migracji zepsulaby skrypty |
| DECISIONS | status ADR-044 (indeks = wpis: "D1, D6", "zostaje z"), ADR-045 i ADR-047 (wpis = indeks: erraty) | slownik statusow: indeks i wpis maja ten sam tekst; CRLF zachowane |
| PRD 5 | dodane `list_partitions`; lista usunietych symboli: `WMS_INDEX_ENDPOINTS` -> `WMS_SKOROWIDZE_ENDPOINTS` (nazwa z 0.7.2), dopisane `SUPPORTED_VERTICAL_CRS` | eksporty = `__all__`; `git grep` v0.7.2 potwierdza nazwy |
| PRD 3.1, SCOPE 2.1 | wzmianka o `full_m2`, `sheet_records`, `campaign_coverage` (ADR-047) | funkcja KD-1/KD-2 byla tylko w USAGE/ARCHITECTURE |
| STANDARDS naglowek | wersja 3.4/2026-10-16 -> 3.5/2026-10-18; nota 2.3: `GridMismatchError` usuniety w 0.8.0 | jest Nota 3.5 z 2026-10-18; klasa usunieta (CHANGELOG) |

## Do decyzji / zmiany kodu (nie zmieniano)

1. Data wydania: CHANGELOG `[0.8.0] - 2026-10-17`, SCOPE/PRD "Status: Wydanie v0.8.0 (2026-10-17)", PROGRESS CP14 -
   tag nie istnieje (`git tag`: ostatni v0.7.2), a wpis zawiera prace z 18-19.10. Zgodnie z CLAUDE.md
   daty/naglowki wydania ustala uzytkownik przy tagowaniu.
2. SCOPE: naglowek "Wersja 3.28, 2026-10-17" i tabela historii konczy sie na 3.28, mimo zmian z 18-19.10
   (sekcja 2.17 agentow, `list_partitions`, KD); PRD 4.8/2026-10-18, a dotkniety 19.10 - podbicie wersji/daty i wiersz
   historii wymaga decyzji.
3. llms.txt, sekcja "Serwer MCP": "Narzedzia 1:1 z komendami" wymienia 17 z 29 narzedzi (brak:
   `boundaries/cadastre/models3d/hydro/names/maps/geodesy_download`, `project_init`, `project_add`,
   `project_remove`, `project_verify`, `store_sidecar`). Test sprawdza tylko podzbior (`named <= tools`).
   Plik ma 147 linii (limit testu < 150) - uzupelnienie wymaga zawiniecia tekstu; nie zmieniano.
4. DECISIONS, relacje nie zapisane po obu stronach (slownik: "kazda relacja po obu stronach"):
   ADR-030 "czesciowo zastapiona przez ADR-032" vs ADR-032 tylko "uzupelnia ADR-030"; ADR-037 "uzupelniona przez
   ADR-044" vs ADR-044 "czesciowo zastepuje ADR-037 (S3-S4)"; ADR-036 "czesciowo zastepuje ADR-035
   (W-U3/W-U8)" vs ADR-035 wspomina to tylko w errata 3. Ktora strona jest wlasciwa - decyzja autora.
   (Pozostale ostrzezenia skryptu relacji to artefakty wielokrotnych klauzul.)
5. ARCHITECTURE: nowa krawedz `transport.index_records -> providers.pl.skorowidz_wfs` tworzy cykl pakietow
   providers <-> transport (bez cyklu modulow). Opisane w dokumencie; ewentualne przeniesienie to decyzja
   projektowa/zmiana kodu.
6. P3 bez zmian: SCOPE 2.9 komentarz `kartograf parse <godlo> # PL-1992 lub PL-2000` (parse obsluguje tez
   CZ SM5/TM33/ZTM); USAGE 1.4 zdanie o komendach przyjmujacych godla CZ pomija `elevation availability`
   (wypisuje je `kartograf parse`); cytaty `hsg_statistics(path)` w USAGE/ARCHITECTURE/CHANGELOG, a argument
   nazywa sie `hsg_path` (pozycyjnie dziala); CLAUDE.md wiersz 75 kieruje po ADR-034/`chunks.py` do
   ARCHITECTURE 4.2, a ADR-034 jest w 4.3; PROGRESS (historia) ma skrotowe nazwy `docs/plans-ab` itd.

## Waznosc
- P2 (mylace instrukcje): CHANGELOG kod wyjscia 1 zamiast 2 z "Co zrobic" (3 miejsca); USAGE: godla 8-czlonowe
  "nie sa pobierane" (2 miejsca) i `UNVERIFIED_LOCAL` zamiast `CHECK_FAILED`.
- P3: pozostale poprawki z tabeli i punkty 2-6 powyzej.
- P1: brak.

## Commity
- 23430e70 `docs: audyt dokumentacji przed v0.8.0 - spojnosc z kodem` (autor Daldek <git@debever.pl>, bez
  stopki Co-Authored-By; galaz `docs/audit-0.8.0`; bez merge i push).
