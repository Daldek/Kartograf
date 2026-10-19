# Instrukcje dla Claude Code

Kartograf pobiera dane przestrzenne z publicznych uslug GUGiK (PL), CUZK (CZ),
Copernicus i ISRIC (NMT/NMPT, ortofotomapa, LAZ, BDOT10k, CORINE, SoilGrids,
HSG) i zapisuje je w ukladzie `data/` z sidecarem metadanych. Dziala jako CLI
`kartograf`, biblioteka Python i serwer MCP `kartograf-mcp` (interfejs dla
agentow AI: `llms.txt`, `kartograf catalog --json`); jest czescia toolchainu
hydrologicznego (Hydrograf, Hydrolog, IMGWTools). Wprowadzenie: `README.md`;
zakres: `docs/SCOPE.md`.

## Zasady pracy (krytyczne)

Glowne zrodlo konwencji i procesu: `docs/DEVELOPMENT_STANDARDS.md`.

- Python wylacznie z `.venv`: `.venv/bin/python`, `.venv/bin/kartograf`
  (STANDARDS 6.1; zmienne srodowiskowe: 6.2).
- Pobrane dane zapisuj poza repo i poza `/tmp`, zawsze z jawnym `--output`;
  cache metadanych SQLite zostaje lokalnie, CLI uruchamiaj z korzenia repo
  (STANDARDS 6.4).
- Testy sa offline: `-m "not live"`; testy `live` tylko swiadomie
  (STANDARDS 6.3, 10.4).
- Brama przed commitem/merge: `scripts/gate.sh` (ruff check, ruff format
  --check, mypy, pytest offline; dziala tez z worktree) musi byc zielona
  (STANDARDS 6.3, 8.3, 18).
- Praca na `develop` (albo galezi krotkotrwalej z `develop`); Conventional
  Commits z opisem po polsku, docstringi i komentarze po angielsku,
  dokumentacja po polsku (STANDARDS 1.1, 2, 9.4).
- Commity bez stopki `Co-Authored-By` (decyzja uzytkownika 2026-10-09;
  stopki w starszej historii zostaja). Autor: `Daldek <git@debever.pl>`.
- Na koniec sesji OBOWIAZKOWO zaktualizuj `docs/PROGRESS.md`; zmiany
  dopisuj na biezaco do `docs/CHANGELOG.md` (STANDARDS 15).
- `docs/DECISIONS.md` ma konce linii CRLF — zachowaj je przy edycji
  (STANDARDS 5.5).

## Agenci z innych repozytoriow

Dotyczy agentow pracujacych w Hydrografie, Archiwiscie, IMGWTools i innych
repozytoriach, ktorzy edytuja Kartografa:

- zmiany wylacznie na galezi odchodzacej od `develop` (`feat/<temat>`,
  `fix/<temat>`); nigdy na `develop` ani `main`;
- bez merge do `develop`/`main`, bez push do nich i bez tagow;
- bez wpisow wydania (nowy naglowek `## [x.y.z] - data` w
  `docs/CHANGELOG.md`, zmiana `__version__`, tag) bez zgody uzytkownika;
  zmiane opisuje sie w sekcji nadchodzacego wydania (`## [Unreleased]`, gdy
  ostatnie wydanie jest otagowane) i w commicie;
- przed tagiem OBOWIAZKOWY przeglad: `git log develop..<galaz>`, przeglad
  diffu przez uzytkownika i `scripts/gate.sh` zielony; tag dopiero po jawnej
  zgodzie uzytkownika;
- interfejs maszynowy Kartografa: `llms.txt` (spis dla agentow),
  `kartograf catalog --json` (komendy, parametry, dozwolone wartosci,
  przyklady), `--json` w kazdej komendzie (dokumenty `kartograf-*/1`, blad
  `kartograf-error/1`, kody wyjscia 0/1/2/130/143) i serwer MCP `kartograf-mcp`
  (`kartograf[mcp]`); opis: `docs/USAGE.md`, sekcja 9;
- nie tworz `AGENTS.md`: reguly dla agentow sa w tym pliku.

## Mapa dokumentacji

| Czego szukasz | Gdzie |
|---|---|
| Stan prac, ostatnia sesja, backlog | `docs/PROGRESS.md` |
| Workflow sesji, kolejnosc lektury | `docs/DEVELOPMENT_STANDARDS.md` 15 |
| Srodowisko, zmienne (`CLMS_CREDENTIALS`, `KARTOGRAF_DEBUG`), komendy testow/lint/mypy | STANDARDS 6.1-6.3, 8.3 |
| Gdzie zapisywac pobrane dane | STANDARDS 6.4 |
| Git, commity, jezyk, testy, wyjatki, timeouty i retry (zasady) | STANDARDS 1-2, 9.4, 10-11, 13.4 |
| Roadmapa do v1.0.0 (podprojekty, kolejnosc, zasady) | `docs/SCOPE.md` 3.3 |
| Katalog produktow GUGiK/CUZK (statusy, probki, pulapki uslug) i plany podprojektu 3 (A-E, grupy CLI, raport dostepnosci) | `docs/research/2026-10-13-katalog-produktow/raport.md`; `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md` |
| Zakres, co jest poza nim, ograniczenia techniczne (timeouty per provider, CZ, `--country auto`), zaleznosci | `docs/SCOPE.md` 2, 3.1, 3.2, 4.2 |
| Wymagania produktowe (warstwy BDOT10k, parametry SoilGrids, lata CORINE) | `docs/PRD.md` |
| Moduly i zaleznosci miedzy warstwami | `docs/ARCHITECTURE.md` 2 |
| Deskryptory zrodel, sidecar `kartograf-meta/1`, `extra.parent_request` | ARCHITECTURE 3.1, 3.2, 3.4 |
| Uklad `data/`, wersje `versions/` (dawniej `kampanie/`), dowiazania i `full_sheet/` | ARCHITECTURE 3.3 |
| Odczyt magazynu bez zapisu (Archiwista): `iter_store`, `list_segments`, `list_partitions` (czesci segmentu), `read_sidecar`, obrysy, koszt na wpis, watki | ARCHITECTURE 3.3.1; ADR-045 (errata 2) |
| Godlo PL, skorowidz GUGiK, `MetadataCache`/`--force`, kampanie (`--all-campaigns`, `--min-year`, `--full-sheet`, I-1) | ARCHITECTURE 4.1 |
| Lista arkuszy PL (R5, kody wyjscia), WCS `download_bbox` (siatka zrodla, kawalki `transport/chunks.py`, ADR-034) | ARCHITECTURE 4.2 |
| Wycinek `--cutout --horizontal-crs`, `--sheet-system` (ADR-027, ADR-038) | ARCHITECTURE 4.3 |
| CZ (CUZK), `--country auto` | ARCHITECTURE 4.4-4.6 |
| LAZ (ADR-029) | ARCHITECTURE 4.7 |
| Land cover, BDOT10k, CORINE, SoilGrids, HSG | ARCHITECTURE 4.8 |
| CLI = API: `download_data`/`check_data`, `Notice`, wspolny cache, testy zgodnosci (CLI tylko tlumaczy) | STANDARDS 7.3; ARCHITECTURE 4 (wstep); ADR-037 |
| Interfejs dla agentow AI: dokumenty JSON `kartograf-*/1`, `--json`, kody wyjscia i bledow, katalog komend, serwer MCP, `llms.txt` | `docs/USAGE.md` 9; ARCHITECTURE 3.6, 4.11; STANDARDS 7.3 (Z8-Z11); ADR-046; spec `docs/superpowers/specs/2026-10-18-agent-interface-design.md` |
| Nowa komenda albo grupa CLI (deklaracja w katalogu komend) | STANDARDS 17.2; ARCHITECTURE 4.11 |
| Jedna komenda bramy (ruff, ruff format, mypy, pytest offline; tez z worktree) | `scripts/gate.sh`; STANDARDS 6.3 |
| Nowe zrodlo albo kraj; nowy provider pokrycia terenu | ARCHITECTURE 5; STANDARDS 17 |
| Przyklady CLI i biblioteki, wynik pobrania, kampanie, CLMS, znane problemy | `docs/USAGE.md` 1-7 |
| Decyzje i ich erraty (indeks na poczatku pliku) | `docs/DECISIONS.md` |
| Historia zmian per wydanie | `docs/CHANGELOG.md` |
| Pelna lista opcji CLI / publiczne API | `kartograf <grupa> <komenda> --help` albo `kartograf catalog --json` / `kartograf/__init__.py` (`__all__`) |
