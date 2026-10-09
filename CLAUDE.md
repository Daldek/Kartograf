# Instrukcje dla Claude Code

Kartograf pobiera dane przestrzenne z publicznych uslug GUGiK (PL), CUZK (CZ),
Copernicus i ISRIC (NMT/NMPT, ortofotomapa, LAZ, BDOT10k, CORINE, SoilGrids,
HSG) i zapisuje je w ukladzie `data/` z sidecarem metadanych. Dziala jako CLI
`kartograf` i biblioteka Python; jest czescia toolchainu hydrologicznego
(Hydrograf, Hydrolog, IMGWTools). Wprowadzenie: `README.md`; zakres:
`docs/SCOPE.md`.

## Zasady pracy (krytyczne)

Glowne zrodlo konwencji i procesu: `docs/DEVELOPMENT_STANDARDS.md`.

- Python wylacznie z `.venv`: `.venv/bin/python`, `.venv/bin/kartograf`
  (STANDARDS 6.1; zmienne srodowiskowe: 6.2).
- Pobrane dane zapisuj poza repo i poza `/tmp`, zawsze z jawnym `--output`;
  cache metadanych SQLite zostaje lokalnie, CLI uruchamiaj z korzenia repo
  (STANDARDS 6.4).
- Testy sa offline: `-m "not live"`; testy `live` tylko swiadomie
  (STANDARDS 6.3, 10.4).
- Brama przed commitem/merge: pytest offline zielone, `ruff check .` i
  `ruff format --check .` czyste, `mypy kartograf/ tests/` bez bledow
  (STANDARDS 6.3, 8.3, 18).
- Praca na `develop` (albo galezi krotkotrwalej z `develop`); Conventional
  Commits z opisem po polsku, docstringi i komentarze po angielsku,
  dokumentacja po polsku (STANDARDS 1.1, 2, 9.4).
- Na koniec sesji OBOWIAZKOWO zaktualizuj `docs/PROGRESS.md`; zmiany
  dopisuj na biezaco do `docs/CHANGELOG.md` (STANDARDS 15).
- `docs/DECISIONS.md` ma konce linii CRLF — zachowaj je przy edycji
  (STANDARDS 5.5).

## Mapa dokumentacji

| Czego szukasz | Gdzie |
|---|---|
| Stan prac, ostatnia sesja, backlog | `docs/PROGRESS.md` |
| Workflow sesji, kolejnosc lektury | `docs/DEVELOPMENT_STANDARDS.md` 15 |
| Srodowisko, zmienne (`CLMS_CREDENTIALS`, `KARTOGRAF_DEBUG`), komendy testow/lint/mypy | STANDARDS 6.1-6.3, 8.3 |
| Gdzie zapisywac pobrane dane | STANDARDS 6.4 |
| Git, commity, jezyk, testy, wyjatki, timeouty i retry (zasady) | STANDARDS 1-2, 9.4, 10-11, 13.4 |
| Roadmapa do v1.0.0 (podprojekty, kolejnosc, zasady) | `docs/SCOPE.md` 3.3 |
| Zakres, co jest poza nim, ograniczenia techniczne (timeouty per provider, CZ, `--country auto`), zaleznosci | `docs/SCOPE.md` 2, 3.1, 3.2, 4.2 |
| Wymagania produktowe (warstwy BDOT10k, parametry SoilGrids, lata CORINE) | `docs/PRD.md` |
| Moduly i zaleznosci miedzy warstwami | `docs/ARCHITECTURE.md` 2 |
| Deskryptory zrodel, sidecar `kartograf-meta/1`, `extra.parent_request` | ARCHITECTURE 3.1, 3.2, 3.4 |
| Uklad `data/`, kampanie `kampanie/` i dowiazania | ARCHITECTURE 3.3 |
| Godlo PL, skorowidz GUGiK, `MetadataCache`/`--force`, kampanie (`--campaigns`, `--min-year`, I-1) | ARCHITECTURE 4.1 |
| Lista arkuszy PL (R5, kody wyjscia), WCS `download_bbox` | ARCHITECTURE 4.2 |
| Wycinek PL `--target-crs` (ADR-027) | ARCHITECTURE 4.3 |
| CZ (CUZK), `--country auto` | ARCHITECTURE 4.4-4.6 |
| LAZ (ADR-029) | ARCHITECTURE 4.7 |
| Land cover, BDOT10k, CORINE, SoilGrids, HSG | ARCHITECTURE 4.8 |
| Nowe zrodlo albo kraj; nowy provider pokrycia terenu | ARCHITECTURE 5; STANDARDS 17 |
| Przyklady CLI i biblioteki, wynik pobrania, kampanie, CLMS, znane problemy | `docs/USAGE.md` 1-7 |
| Decyzje i ich erraty (indeks na poczatku pliku) | `docs/DECISIONS.md` |
| Historia zmian per wydanie | `docs/CHANGELOG.md` |
| Pelna lista opcji CLI / publiczne API | `kartograf <komenda> --help` / `kartograf/__init__.py` (`__all__`) |
