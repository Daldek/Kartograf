# Wspolne zasady audytu dokumentacji (Kartograf, 2026-09-29)

**Kontekst.** Galaz `develop`, HEAD 6985765. Dwie fale zmian dotknely dokumentacji: (1) uklad `data/` + `--target-crs` PL (2026-08-28, ADR-026/027) i (2) fala naprawcza "review max" + wycinek PL w bibliotece (2026-09-28; zakres zmian: `git log --oneline 8cf1e5a..6985765`, pelny opis: `docs/PROGRESS.md` sekcja "Fala naprawcza po review max ..." i `docs/CHANGELOG.md` [0.7.0]). Uzytkownik pyta: **czy zaktualizowano CALA dokumentacje, ktorej dotykaja te zmiany?** W historii projektu dokumenty klamaly czesciej niz kod (kilkanascie przypadkow) — kazde twierdzenie weryfikuj na ZYWYM kodzie.

## Zasady
- Repo `/home/claude-agent/workspace/Kartograf` **TYLKO DO ODCZYTU** — nie zmieniaj niczego, nie commituj. Hydrograf (`/home/claude-agent/workspace/Hydrograf`) — tylko odczyt.
- Offline: mozesz uruchamiac `.venv/bin/kartograf --help` / `download --help`, `.venv/bin/python -c "..."` (importy, sygnatury), testy offline (`.venv/bin/python -m pytest <plik> -q -m "not live"`); zadnych pobran z sieci.
- Weryfikuj na kodzie: kazde twierdzenie o zachowaniu, sygnatury, nazwy, sciezki, liczby, przyklady. Szukaj tez BRAKOW: zachowania wprowadzonego przez fale, ktorego dokument nie opisuje, a powinien (np. nowe API, `NoCoverageError`, `missing_sheets`, `--force`, komunikaty `Warning:`/`Info:`, uklad `data/`).
- Dokumenty historyczne (`docs/research/`, `docs/superpowers/` — plany/specy, datowane sekcje PROGRESS/CHANGELOG starszych wersji) to zapis historii: nie wymagaja aktualizacji, ALE zglos, jesli ktorys dokument biezacy odsyla do nich jako do stanu obecnego.
- Nie uruchamiaj subagentow.

## Raport
- Pelny raport: `/home/claude-agent/workspace/Kartograf/.superpowers/sdd/2026-09-29-live-e2e-i-docs/<ID>-report.md`.
- Tabela znalezisk: `plik:linia | twierdzenie (cytat) | stan faktyczny (kod plik:linia / wynik polecenia) | kategoria (FALSZ / NIEAKTUALNE / BRAK / NIEPRECYZYJNE / NIESPOJNE miedzy dokumentami) | proponowana poprawka (gotowy tekst, polski ASCII bez diakrytykow tam, gdzie plik tak pisze)`.
- Osobno: lista sprawdzonych twierdzen, ktore sa PRAWDZIWE (krotko, z plik:linia) — zeby bylo widac zakres.
- Odpowiedz kontrolerowi krotko (<= 15 linii): liczba znalezisk per kategoria, 3-5 najwazniejszych jednym zdaniem, sciezka raportu.
